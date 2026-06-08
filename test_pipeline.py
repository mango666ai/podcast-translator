"""
主链路验证：下载 → 转录 → 翻译
跳过 diarization，单说话人模式

用法：
    python test_pipeline.py <YouTube_URL_或_本地音频路径> [--duration 60]

示例：
    python test_pipeline.py "https://www.youtube.com/watch?v=ugvHCXCOmm4" --duration 90
    python test_pipeline.py ./test.mp3 --duration 90

--duration: 只处理前 N 秒（默认 90 秒，快速验证用）
"""

import sys
import os
import json
import re
import subprocess
import time
import argparse
import tempfile
from pathlib import Path

# 把 VideoLingo 加入 path
VIDEOLINGO_DIR = Path(__file__).parent.parent / "VideoLingo"
sys.path.insert(0, str(VIDEOLINGO_DIR))

WORK_DIR = Path(__file__).parent / "work"
WORK_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────
# Step 1: 下载音频
# ─────────────────────────────────────────
def download_audio(url: str, out_dir: Path, cookies_file: str = None) -> Path:
    out_path = out_dir / "audio.%(ext)s"
    print(f"\n[1/3] 下载音频...")

    # 自动检测 cookies.txt（放在 podcast_addon/ 目录下即可）
    default_cookies = Path(__file__).parent / "cookies.txt"
    if cookies_file is None and default_cookies.exists():
        cookies_file = str(default_cookies)
        print(f"  使用 cookies: {default_cookies.name}")

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "--cookies-from-browser", "chrome",
        "--remote-components", "ejs:github",
        "-o", str(out_path),
        url,
    ]

    if cookies_file:
        cmd += ["--cookies", cookies_file]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp 失败:\n{result.stderr[:300]}")

    # 找到输出文件
    for f in out_dir.glob("audio.*"):
        print(f"  ✓ 下载完成: {f.name} ({f.stat().st_size // 1024}KB)")
        return f
    raise FileNotFoundError("下载后找不到音频文件")


def use_local_audio(path: str, out_dir: Path) -> Path:
    import shutil
    src = Path(path)
    dst = out_dir / src.name
    shutil.copy2(src, dst)
    print(f"\n[1/3] 使用本地文件: {src.name} ({src.stat().st_size // 1024}KB)")
    return dst


# ─────────────────────────────────────────
# Step 2: 转录（whisperX，不做 diarization）
# ─────────────────────────────────────────
def transcribe(audio_path: Path, duration_limit: int = None) -> list:
    print(f"\n[2/3] 转录中（whisperX large-v3，Mac CPU/MPS）...")
    print(f"  注意：首次运行会下载模型 ~3GB，请耐心等待")

    import whisperx

    # 如果限制时长，先用 ffmpeg 截取
    if duration_limit:
        clipped = audio_path.parent / f"audio_clip_{duration_limit}s.mp3"
        if not clipped.exists():
            subprocess.run([
                "ffmpeg", "-y", "-i", str(audio_path),
                "-t", str(duration_limit),
                "-acodec", "copy",
                str(clipped),
            ], capture_output=True)
        audio_path = clipped
        print(f"  ✓ 截取前 {duration_limit} 秒")

    t0 = time.time()
    device = "cpu"  # Mac 用 cpu（MPS whisperX 支持尚不稳定）

    model = whisperx.load_model(
        "large-v3",
        device=device,
        language="en",
        compute_type="int8",  # CPU 用 int8 加速
    )
    result = model.transcribe(
        str(audio_path),
        batch_size=8,
        language="en",
    )
    segments = result["segments"]
    elapsed = time.time() - t0
    print(f"  ✓ 转录完成：{len(segments)} 段，耗时 {elapsed:.1f}s")

    # 保存转录结果
    transcript_path = audio_path.parent / "transcript.json"
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    return segments


# ─────────────────────────────────────────
# Step 3: 翻译（Claude Code headless）
# ─────────────────────────────────────────
TRANSLATE_PROMPT = """你是专业播客翻译，将以下英文播客片段翻译成中文。

要求：
- 意译为主，保留所有信息点
- 说人话，不要逐词直译
- 适合朗读，自然流畅
- 注意上下文连贯性

原文片段（每行一段，格式为"[序号] 原文"）：
{segments_text}

请严格按以下 JSON 格式返回，不要有任何其他内容：
```json
{{
  "segments": [
    {{"id": 0, "text_zh": "中文翻译"}},
    {{"id": 1, "text_zh": "中文翻译"}}
  ]
}}
```"""


CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")

def call_claude(prompt: str) -> str:
    result = subprocess.run(
        [CLAUDE_BIN, "-p", prompt, "--model", "claude-sonnet-4-6"],
        capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        stderr = result.stderr.lower()
        if any(k in stderr for k in ["rate limit", "usage limit", "quota"]):
            print("⚠️  Claude Code 配额耗尽，请稍后重试（重新运行脚本即可续跑）")
            sys.exit(0)
        raise RuntimeError(f"claude 失败: {result.stderr[:200]}")
    return result.stdout


def extract_json(text: str) -> dict:
    from json_repair import repair_json
    m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    raw = m.group(1) if m else None
    if raw is None:
        m2 = re.search(r"\{[\s\S]+\}", text)
        raw = m2.group(0) if m2 else text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = repair_json(raw)
        return json.loads(repaired)


def translate(segments: list, work_dir: Path, chunk_size: int = 10) -> list:
    print(f"\n[3/3] 翻译中（Claude Code headless，每 {chunk_size} 段一批）...")

    results = []
    total_chunks = (len(segments) + chunk_size - 1) // chunk_size

    for chunk_idx in range(total_chunks):
        cache_path = work_dir / f"translation_chunk_{chunk_idx:03d}.json"

        # 命中缓存直接用
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                chunk_result = json.load(f)
            results.extend(chunk_result)
            print(f"  chunk {chunk_idx+1}/{total_chunks} ✓ (cached)")
            continue

        # 构建这个 chunk 的 segments
        start = chunk_idx * chunk_size
        chunk_segs = segments[start: start + chunk_size]

        lines = "\n".join(
            f"[{i}] {seg.get('text', '').strip()}"
            for i, seg in enumerate(chunk_segs)
        )
        prompt = TRANSLATE_PROMPT.format(segments_text=lines)

        t0 = time.time()
        raw = call_claude(prompt)
        elapsed = time.time() - t0

        try:
            data = extract_json(raw)
            chunk_translations = [s["text_zh"] for s in sorted(data["segments"], key=lambda x: x["id"])]
        except Exception as e:
            print(f"  chunk {chunk_idx+1} JSON 解析失败，重试一次: {e}")
            raw = call_claude(prompt)
            data = extract_json(raw)
            chunk_translations = [s["text_zh"] for s in sorted(data["segments"], key=lambda x: x["id"])]

        # 和原始 segments 合并
        chunk_result = []
        for seg, zh in zip(chunk_segs, chunk_translations):
            chunk_result.append({
                "start": seg.get("start"),
                "end": seg.get("end"),
                "text_en": seg.get("text", "").strip(),
                "text_zh": zh,
            })

        # 落盘缓存
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(chunk_result, f, ensure_ascii=False, indent=2)

        results.extend(chunk_result)
        print(f"  chunk {chunk_idx+1}/{total_chunks} ✓ ({elapsed:.1f}s)")

    return results


# ─────────────────────────────────────────
# 输出双语对照
# ─────────────────────────────────────────
def save_bilingual(results: list, work_dir: Path):
    out_md = work_dir / "bilingual.md"
    out_json = work_dir / "bilingual.json"

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# 双语对照\n\n")
        for seg in results:
            start = seg.get("start") or 0
            mm, ss = divmod(int(start), 60)
            f.write(f"**[{mm:02d}:{ss:02d}]**\n")
            f.write(f"- EN: {seg['text_en']}\n")
            f.write(f"- ZH: {seg['text_zh']}\n\n")

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n  ✓ 双语对照已保存: {out_md}")
    return out_md


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="YouTube URL 或本地音频路径")
    parser.add_argument("--duration", type=int, default=90,
                        help="只处理前 N 秒（默认 90，设 0 处理全部）")
    parser.add_argument("--no-tts", action="store_true",
                        help="跳过 TTS 合成步骤（只输出 bilingual.md）")
    parser.add_argument("--voice", default="zh-CN-XiaoxiaoNeural",
                        help="edge-tts 声音（默认 zh-CN-XiaoxiaoNeural）")
    args = parser.parse_args()

    # 创建本次 job 目录
    import hashlib
    job_id = hashlib.md5(args.input.encode()).hexdigest()[:8]
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    print(f"Job 目录: {job_dir}")

    # Step 1: 获取音频
    audio_path = job_dir / "audio_check.mp3"
    if audio_path.exists() or any(job_dir.glob("audio.*")):
        existing = next(job_dir.glob("audio*"), None)
        if existing and "clip" not in existing.name:
            print(f"\n[1/3] 已有音频: {existing.name}，跳过下载")
            audio_path = existing
    else:
        if args.input.startswith("http"):
            audio_path = download_audio(args.input, job_dir)
        else:
            audio_path = use_local_audio(args.input, job_dir)

    # Step 2: 转录
    transcript_path = job_dir / "transcript.json"
    if transcript_path.exists():
        print(f"\n[2/3] 已有转录结果，跳过")
        with open(transcript_path, encoding="utf-8") as f:
            segments = json.load(f)
        print(f"  ✓ 加载 {len(segments)} 段")
    else:
        duration = args.duration if args.duration > 0 else None
        segments = transcribe(audio_path, duration_limit=duration)
        # 保存
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(segments, f, ensure_ascii=False, indent=2)

    print(f"\n转录预览（前 3 段）：")
    for seg in segments[:3]:
        print(f"  [{seg.get('start', 0):.1f}s] {seg.get('text', '').strip()[:80]}")

    # Step 3: 翻译
    results = translate(segments, job_dir)

    # 输出
    out_md = save_bilingual(results, job_dir)

    print(f"\n{'='*50}")
    print(f"✓ 转录+翻译完成！处理了 {len(results)} 段")
    print(f"\n双语对照预览（前 3 段）：")
    for seg in results[:3]:
        mm, ss = divmod(int(seg.get("start") or 0), 60)
        print(f"\n  [{mm:02d}:{ss:02d}] EN: {seg['text_en'][:60]}")
        print(f"         ZH: {seg['text_zh'][:60]}")

    print(f"\n完整对照: {out_md}")

    # Step 4: TTS 合成 → MP3
    if args.no_tts:
        print(f"\n[跳过 TTS]（--no-tts）")
    else:
        print(f"\n{'='*50}")
        # 调用 tts_compose 模块
        tts_script = Path(__file__).parent / "tts_compose.py"
        result = subprocess.run(
            [sys.executable, str(tts_script), str(job_dir), "--voice", args.voice],
            text=True,
        )
        if result.returncode != 0:
            print("⚠️  TTS 合成失败，请手动运行：")
            print(f"   python tts_compose.py {job_dir}")


if __name__ == "__main__":
    main()
