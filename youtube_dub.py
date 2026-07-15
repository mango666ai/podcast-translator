"""
YouTube 转写 → 中文字幕 + 中文配音（复用 podcast_addon 的翻译/TTS 能力）

前置：youtube_transcribe.py 已产出 youtube_transcripts/<id>.json（英文分段，含 start/end/text）

流程：
  ② 翻译：claude headless 批量把英文分段译成中文（免费，走 Max 订阅）
     → youtube_dub/<id>__<中文短标题>/...（中文字幕 / 中文小样 / 完整中文音频）
  ③ 配音（可选，烧 MiniMax TTS 额度）：逐段 TTS → ffmpeg 拼接
     → youtube_dub/<id>/<id>_zh[_sampleN].mp3

用法（用 VideoLingo/.venv 的 python3.11 跑）：
  "$VENV_PY" youtube_dub.py <video_id> --no-audio        # 只出中文字幕(免费)
  "$VENV_PY" youtube_dub.py <video_id> --demo             # 翻译全片 + 前 6 段慢速小样
  "$VENV_PY" youtube_dub.py <video_id> --sample 12        # 翻译全片 + 只配前 12 段做样本
  "$VENV_PY" youtube_dub.py <video_id> --voice Wise_Woman --speed 0.82
"""
import sys
import re
import json
import argparse
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
TRANS_DIR = HERE / "youtube_transcripts"
OUT_ROOT = HERE / "youtube_dub"
STATUS_CSV = HERE / "podcast_status.csv"
CLAUDE_BIN = str(Path.home() / ".local/bin/claude")
BATCH = 25
DEFAULT_DEMO_SEGMENTS = 6
DEFAULT_SPEED = 0.82


def _safe_name(text: str, limit: int = 32) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\\/:*?\"<>|#\[\]\(\)（）「」『』，,。.!！?？\s]+", "", text)
    return text[:limit] or "未命名"


def _title_from_status(video_id: str) -> str:
    if not STATUS_CSV.exists():
        return ""
    for line in STATUS_CSV.read_text(encoding="utf-8").splitlines()[1:]:
        cols = line.split(",")
        if cols and cols[0] == video_id and len(cols) > 1:
            return cols[1].strip()
    return ""


def _title_from_transcript(video_id: str) -> str:
    txt = TRANS_DIR / f"{video_id}.txt"
    if not txt.exists():
        return video_id
    first = txt.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
    return first or video_id


def display_title(video_id: str) -> str:
    return _title_from_status(video_id) or _title_from_transcript(video_id)


def _legacy_sample(video_id: str) -> Path:
    return OUT_ROOT / video_id / "bilingual_sample.json"


def _speed_label(speed: float) -> str:
    return f"慢速{speed:.2f}" if speed < 1.0 else f"正常{speed:.2f}"


def call_claude(prompt: str) -> str:
    r = subprocess.run([CLAUDE_BIN, "-p", prompt], capture_output=True, text=True, timeout=240)
    if r.returncode != 0:
        stderr = r.stderr.lower()
        if any(k in stderr for k in ["rate limit", "usage limit", "quota", "5-hour"]):
            print("⚠️ Claude 配额耗尽，稍后重试"); sys.exit(0)
        raise RuntimeError(f"claude 失败: {r.stderr[:200]}")
    return r.stdout


def extract_json(text: str):
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    blob = m.group(1) if m else re.search(r"\{[\s\S]+\}", text).group(0)
    return json.loads(blob)


def translate(segs: list, title: str) -> list:
    out = []
    for i in range(0, len(segs), BATCH):
        batch = segs[i:i + BATCH]
        lines = "\n".join(f"[{j}] {s.get('text', '').strip()}" for j, s in enumerate(batch))
        prompt = (
            f"你是专业视频翻译。把下面英文演讲片段译成自然、口语化、适合朗读配音的中文，意译为主、保留信息点。\n"
            f"视频主题：{title}\n"
            f"按序号一一对应，**只**返回 JSON（无其他文字）：\n"
            f'```json\n{{"segments":[{{"i":0,"zh":"中文"}}]}}\n```\n'
            f"原文：\n{lines}"
        )
        data = extract_json(call_claude(prompt))
        zh = {d["i"]: d.get("zh", "") for d in data.get("segments", [])}
        for j, s in enumerate(batch):
            out.append({**s, "text_zh": zh.get(j, "")})
        print(f"  翻译 {min(i + BATCH, len(segs))}/{len(segs)} 段")
    return out


def _fmt(t: float) -> str:
    h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(bil: list, path: Path):
    out = []
    for i, s in enumerate(bil, 1):
        out += [str(i), f"{_fmt(s['start'])} --> {_fmt(s['end'])}", s.get("text_zh", "").strip(), ""]
    path.write_text("\n".join(out), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--voice", default="Wise_Woman")
    ap.add_argument("--speed", type=float, default=DEFAULT_SPEED, help="MiniMax 语速，默认 0.82，比之前小样更慢")
    ap.add_argument("--demo", action="store_true", help=f"生成小样：默认前 {DEFAULT_DEMO_SEGMENTS} 段")
    ap.add_argument("--sample", type=int, default=0, help="只配前 N 段（0=全片）")
    ap.add_argument("--no-audio", action="store_true", help="只出中文字幕，不配音（免费）")
    a = ap.parse_args()

    tj = TRANS_DIR / f"{a.video_id}.json"
    if not tj.exists():
        sys.exit(f"✗ 找不到转写 {tj}（先跑 youtube_transcribe.py）")
    segs = json.loads(tj.read_text(encoding="utf-8"))
    title = display_title(a.video_id)
    safe_title = _safe_name(title)
    prefix = f"{a.video_id}__{safe_title}"

    job = OUT_ROOT / prefix
    job.mkdir(parents=True, exist_ok=True)

    bilp = job / f"{prefix}__双语分段.json"
    if bilp.exists():
        bil = json.loads(bilp.read_text(encoding="utf-8"))
        if not (a.demo or a.sample or a.no_audio) and len(bil) < len(segs):
            print(f"⚠️ 已有翻译只有 {len(bil)}/{len(segs)} 段，完整音频模式将重做全片翻译")
            bil = translate(segs, title)
            bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            print(f"↩ 复用已有翻译 {len(bil)} 段")
    elif a.demo and _legacy_sample(a.video_id).exists():
        bil = json.loads(_legacy_sample(a.video_id).read_text(encoding="utf-8"))
        bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"↩ 复用旧小样翻译 {len(bil)} 段")
    else:
        print(f"翻译《{title}》{len(segs)} 段…")
        bil = translate(segs, title)
        bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")

    srtp = job / f"{prefix}__中文字幕.srt"
    write_srt(bil, srtp)
    print(f"✓ 中文字幕：{srtp}")

    if a.no_audio:
        print("（--no-audio：跳过配音）"); return

    from tts_minimax import synthesize, _concat, _make_silence
    seg_dir = job / "seg"; seg_dir.mkdir(exist_ok=True)
    n = DEFAULT_DEMO_SEGMENTS if a.demo and not a.sample else (a.sample or len(bil))
    paths = []
    speed_tag = f"speed_{a.speed:.2f}"
    for i, s in enumerate(bil[:n]):
        out = seg_dir / f"{prefix}__{speed_tag}__seg_{i:04d}.mp3"; paths.append(out)
        if out.exists() and out.stat().st_size > 0:
            continue
        t = s.get("text_zh", "").strip()
        if not t:
            _make_silence(out); continue
        try:
            synthesize(t, out, voice=a.voice, speed=a.speed); print(f"  TTS {i + 1}/{n} speed={a.speed}")
        except Exception as e:
            print(f"  TTS {i + 1} 失败: {e}"); _make_silence(out)
    if a.sample or a.demo:
        outmp3 = job / f"{prefix}__中文配音小样_{n:02d}段_{_speed_label(a.speed)}.mp3"
    else:
        outmp3 = job / f"{prefix}__完整中文音频_{_speed_label(a.speed)}.mp3"
    _concat(paths, outmp3)
    print(f"✓ 中文配音：{outmp3}")


if __name__ == "__main__":
    main()
