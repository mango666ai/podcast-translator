"""
YouTube 转写 → 中文字幕 + 中文配音（复用 podcast_addon 的翻译/TTS 能力）

前置：youtube_transcribe.py 已产出 youtube_transcripts/<id>.json（英文分段，含 start/end/text）

流程：
  ② 翻译：OpenAI GPT 批量把英文分段译成中文
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
import csv
import time
from pathlib import Path
from llm_openai import call_gpt

HERE = Path(__file__).parent
TRANS_DIR = HERE / "youtube_transcripts"
OUT_ROOT = HERE / "youtube_dub"
STATUS_CSV = HERE / "podcast_status.csv"
BATCH = 25
DEFAULT_DEMO_SEGMENTS = 6
DEFAULT_SPEED = 0.82


def _safe_name(text: str, limit: int = 32) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\\/:*?\"<>|#\[\]\(\)（）「」『』，,。.!！?？\s]+", "", text)
    return text[:limit] or "未命名"


def _row_from_status(video_id: str) -> dict:
    if not STATUS_CSV.exists():
        return {}
    with STATUS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("video_id") == video_id:
                return row
    return {}


def _title_from_status(video_id: str) -> str:
    return _row_from_status(video_id).get("中文短标题", "").strip()


def _source_from_status(video_id: str) -> str:
    return _row_from_status(video_id).get("source", "").strip()


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


def extract_json(text: str):
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    blob = m.group(1) if m else re.search(r"\{[\s\S]+\}", text).group(0)
    return json.loads(blob)


def translate(segs: list, title: str, source: str = "") -> list:
    out = []
    for i in range(0, len(segs), BATCH):
        batch = segs[i:i + BATCH]
        lines = "\n".join(f"[{j}] {s.get('text', '').strip()}" for j, s in enumerate(batch))
        prompt = (
            f"你是专业视频翻译。把下面英文演讲片段译成自然、口语化、适合朗读配音的中文，意译为主、保留信息点。\n"
            f"视频主题：{title}\n"
            f"来源信息：{source or '未知'}\n"
            f"按序号一一对应，**只**返回 JSON（无其他文字）：\n"
            f'```json\n{{"segments":[{{"i":0,"zh":"中文"}}]}}\n```\n'
            f"原文：\n{lines}"
        )
        data = extract_json(call_gpt(prompt, json_mode=True))
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


def build_timestamps(bil: list, title: str, max_points: int = 8) -> list:
    """从双语分段里挑候选点，让 LLM 只负责选章节位置+起标题，时间戳始终来自真实数据，不给模型编造空间。"""
    if not bil:
        return []
    total = bil[-1].get("end") or bil[-1].get("start") or 0
    interval = max(total / (max_points * 1.5), 45)
    candidates = []
    last_t = -1e9
    for s in bil:
        start = s.get("start", 0)
        zh = s.get("text_zh", "").strip()
        if zh and start - last_t >= interval:
            candidates.append({"idx": len(candidates), "start": start, "text": zh[:60]})
            last_t = start
    if not candidates:
        return []
    lines = "\n".join(f"[{c['idx']}] {c['text']}" for c in candidates)
    prompt = (
        "你是中文播客编辑。下面是一集播客按时间顺序抽样的候选片段（已编号）。\n"
        f"从中选出 6-{max_points} 个适合当作话题切换点的位置，每个配一个 6-14 字的中文话题标签。\n"
        "只能使用给出的编号，不要编造编号，也不要自己编时间。按编号从小到大排列。\n"
        f"节目：{title}\n"
        "只返回 JSON（无其他文字）：\n"
        '```json\n{"chapters":[{"idx":0,"label":"..."}]}\n```\n'
        f"候选片段：\n{lines}"
    )
    try:
        data = extract_json(call_gpt(prompt, json_mode=True))
    except Exception as e:
        print(f"  ⚠️ 时间戳生成失败，跳过：{e}")
        return []
    idx_to_start = {c["idx"]: c["start"] for c in candidates}
    out = []
    for ch in data.get("chapters", []):
        start = idx_to_start.get(ch.get("idx"))
        if start is None:
            continue
        mm, ss = divmod(int(start), 60)
        out.append((f"{mm:02d}:{ss:02d}", ch.get("label", "").strip()))
    out.sort(key=lambda x: x[0])
    return out


def write_notes_if_needed(bil: list, title: str, source: str, path: Path):
    """节目笔记：来源 / 本期播客简介 / 本期嘉宾 / 时间戳 / 精彩内容 / 播客信息补充。"""
    if path.exists() and "## 本期嘉宾" in path.read_text(encoding="utf-8"):
        return
    text = "\n".join(s.get("text_zh", "").strip() for s in bil if s.get("text_zh", "").strip())
    text = text[:12000]
    prompt = (
        "你是中文播客编辑。根据下面中文演讲稿，生成播客节目笔记需要的四段内容，只返回 JSON（无其他文字）：\n"
        '```json\n{"intro":"...","guests":"...","highlights":["...","...","..."],"extra":"..."}\n```\n'
        f"节目：{title}\n"
        f"来源：{source or '来源待确认'}\n"
        "字段要求：\n"
        "- intro：本期播客简介，3-5 句，说清楚这期讲什么、为什么值得听，不要夸大\n"
        "- guests：本期嘉宾/主持人介绍，写清姓名、身份、所属公司；不确定的信息不要编造，写"
        "\"未在原视频中明确\"\n"
        "- highlights：3-6 条精彩内容，每条一句话，覆盖不同话题点，不要重复\n"
        "- extra：播客信息补充，必须包含\"AI 中文译制版，声音克隆自原视频/主持人\"的说明，"
        "并提示可能存在语气或断句不自然\n"
        f"中文演讲稿：\n{text}"
    )
    data = extract_json(call_gpt(prompt, json_mode=True))

    timestamps = build_timestamps(bil, title)
    ts_block = "\n".join(f"- {t} {label}" for t, label in timestamps) or "（本集较短，暂不提供时间戳）"
    highlights_block = "\n".join(f"- {h}" for h in data.get("highlights", []) if h.strip())

    notes = (
        f"# {title} - 节目笔记\n\n"
        f"## 来源\n{source or '来源待确认'}\n\n"
        f"## 本期播客简介\n{data.get('intro', '').strip()}\n\n"
        f"## 本期嘉宾\n{data.get('guests', '').strip()}\n\n"
        f"## 时间戳\n{ts_block}\n\n"
        f"## 精彩内容\n{highlights_block}\n\n"
        f"## 播客信息补充\n{data.get('extra', '').strip()}\n"
    )
    path.write_text(notes, encoding="utf-8")
    print(f"✓ 节目笔记：{path}")


def write_bilingual_transcript(bil: list, title: str, path: Path):
    """英文原文 + 中文翻译逐句对照，带时间戳，供核对翻译质量/阅读，不用于播放器同步。"""
    lines = [f"# {title} — 中英对照文字稿", ""]
    for s in bil:
        en = s.get("text", "").strip()
        zh = s.get("text_zh", "").strip()
        if not en and not zh:
            continue
        mm, ss = divmod(int(s.get("start", 0)), 60)
        lines.append(f"[{mm:02d}:{ss:02d}]")
        if en:
            lines.append(f"EN: {en}")
        if zh:
            lines.append(f"ZH: {zh}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 双语对照：{path}")


def _synthesize_with_retry(synthesize, text: str, out: Path, *, voice: str, speed: float, attempts: int = 3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            synthesize(text, out, voice=voice, speed=speed)
            return
        except Exception as e:
            last_error = e
            if out.exists() and out.stat().st_size < 5000:
                out.unlink()
            if attempt < attempts:
                wait = attempt * 5
                print(f"  TTS 重试 {attempt}/{attempts - 1}：{e}；{wait}s 后重试")
                time.sleep(wait)
    raise last_error


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
    source = _source_from_status(a.video_id)
    safe_title = _safe_name(title)
    prefix = f"{a.video_id}__{safe_title}"

    job = OUT_ROOT / prefix
    job.mkdir(parents=True, exist_ok=True)

    bilp = job / f"{prefix}__双语分段.json"
    if bilp.exists():
        bil = json.loads(bilp.read_text(encoding="utf-8"))
        if not (a.demo or a.sample or a.no_audio) and len(bil) < len(segs):
            print(f"⚠️ 已有翻译只有 {len(bil)}/{len(segs)} 段，完整音频模式将重做全片翻译")
            bil = translate(segs, title, source)
            bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            print(f"↩ 复用已有翻译 {len(bil)} 段")
    elif a.demo and _legacy_sample(a.video_id).exists():
        bil = json.loads(_legacy_sample(a.video_id).read_text(encoding="utf-8"))
        bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"↩ 复用旧小样翻译 {len(bil)} 段")
    else:
        print(f"翻译《{title}》{len(segs)} 段…")
        bil = translate(segs, title, source)
        bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")

    srtp = job / f"{prefix}__中文字幕.srt"
    write_srt(bil, srtp)
    print(f"✓ 中文字幕：{srtp}")
    write_bilingual_transcript(bil, title, job / f"{prefix}__双语对照.md")
    write_notes_if_needed(bil, title, source, job / f"{prefix}__简介与亮点.md")

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
            _synthesize_with_retry(synthesize, t, out, voice=a.voice, speed=a.speed)
            print(f"  TTS {i + 1}/{n} speed={a.speed}")
        except Exception as e:
            print(f"  TTS {i + 1} 失败: {e}")
            raise
    if a.sample or a.demo:
        outmp3 = job / f"{prefix}__中文配音小样_{n:02d}段_{_speed_label(a.speed)}.mp3"
    else:
        outmp3 = job / f"{prefix}__完整中文音频_{_speed_label(a.speed)}.mp3"
    _concat(paths, outmp3)
    print(f"✓ 中文配音：{outmp3}")


if __name__ == "__main__":
    main()
