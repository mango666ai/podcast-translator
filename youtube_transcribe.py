"""
YouTube → 文字（转写）· project5 播客工具的轻量转录入口

区别于 podcast_addon 主流程（翻译+TTS+发布），本脚本只做「下载 + 转写为文字」，
用于把一批 YouTube 演讲/播客转成逐字稿（learn-in-public / 内容消化）。

流程：yt-dlp（--cookies-from-browser chrome）下载音频(mp3) → whisperX 转写 → txt + 带时间戳 json。
断点续跑：已存在产物自动跳过。

输入：sources_youtube.txt —— 每行一个 YouTube URL，`#` 开头为注释，URL 后可跟 ` | 备注标题`
输出：youtube_transcripts/<videoid>.txt / .json （目录已 gitignore，不推公开仓）

用法（用 venv 的 python 跑）：
    VENV_PY=../VideoLingo/.venv/bin/python3.11   # 注意：venv 在 project5_podcast/VideoLingo 下
    "$VENV_PY" youtube_transcribe.py --lang en
    "$VENV_PY" youtube_transcribe.py --lang en --only Yz03ERsfDDM   # 只跑某个(冒烟)
"""
import sys
import re
import json
import time
import argparse
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
VENV_PY = HERE.parent / "VideoLingo" / ".venv" / "bin" / "python3.11"
SOURCES = HERE / "sources_youtube.txt"
OUT_DIR = HERE / "youtube_transcripts"
AUDIO_DIR = OUT_DIR / "_audio"

# whisperX（复用 project8/config 的参数取向）
WHISPER_MODEL = "large-v3"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_BATCH_SIZE = 8

VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/watch\?v=)([\w-]{11})")


def parse_sources(path: Path) -> list:
    """→ [(video_id, url, note), ...]"""
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        url, _, note = line.partition("|")
        url = url.strip()
        note = note.strip()
        m = VIDEO_ID_RE.search(url)
        vid = m.group(1) if m else url
        items.append((vid, url, note))
    return items


def download_audio(url: str, out_mp3: Path) -> bool:
    if out_mp3.exists() and out_mp3.stat().st_size > 0:
        print(f"  ↩ 音频已存在，跳过下载")
        return True
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "yt-dlp", "--cookies-from-browser", "chrome",
        "-x", "--audio-format", "mp3", "--audio-quality", "5",
        "-o", str(out_mp3.with_suffix("")), url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    actual = out_mp3 if out_mp3.exists() else out_mp3.with_suffix(".mp3")
    if r.returncode != 0 or not actual.exists():
        print(f"  ✗ 下载失败：{r.stderr.strip()[-300:]}")
        return False
    if actual != out_mp3:
        actual.rename(out_mp3)
    print(f"  ✓ 音频：{out_mp3.name} ({out_mp3.stat().st_size // 1024 // 1024}MB)")
    return True


_MODEL = None


def get_model(language):
    global _MODEL
    if _MODEL is None:
        import whisperx
        print(f"加载 whisperX {WHISPER_MODEL}（{WHISPER_DEVICE}/{WHISPER_COMPUTE_TYPE}）… 首次下载模型 ~3GB")
        _MODEL = whisperx.load_model(WHISPER_MODEL, device=WHISPER_DEVICE,
                                     compute_type=WHISPER_COMPUTE_TYPE, language=language)
    return _MODEL


def transcribe(mp3: Path, language) -> list:
    model = get_model(language)
    t0 = time.time()
    kw = {"batch_size": WHISPER_BATCH_SIZE}
    if language:
        kw["language"] = language
    result = model.transcribe(str(mp3), **kw)
    segs = result.get("segments", [])
    print(f"  ✓ 转写 {len(segs)} 段（{result.get('language','?')}），耗时 {time.time()-t0:.0f}s")
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en", help="语种码；en/zh…，空串=自动检测")
    ap.add_argument("--only", default=None, help="只处理该 video_id（冒烟）")
    args = ap.parse_args()
    language = args.lang or None

    if not SOURCES.exists():
        sys.exit(f"✗ 缺少 {SOURCES}")
    items = parse_sources(SOURCES)
    if args.only:
        items = [it for it in items if it[0] == args.only]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"共 {len(items)} 个待转\n")
    ok = 0
    for i, (vid, url, note) in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {vid}  {note}")
        txt = OUT_DIR / f"{vid}.txt"
        if txt.exists() and txt.stat().st_size > 0:
            print("  ↩ 已有转写，跳过\n"); ok += 1; continue
        mp3 = AUDIO_DIR / f"{vid}.mp3"
        if not download_audio(url, mp3):
            print(); continue
        segs = transcribe(mp3, language)
        (OUT_DIR / f"{vid}.json").write_text(json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
        full = "\n".join(s.get("text", "").strip() for s in segs).strip()
        header = f"# {note}\n# {url}\n\n" if note else f"# {url}\n\n"
        txt.write_text(header + full, encoding="utf-8")
        ok += 1
        print(f"  → {txt.name}\n")
    print(f"完成：{ok}/{len(items)}")


if __name__ == "__main__":
    main()
