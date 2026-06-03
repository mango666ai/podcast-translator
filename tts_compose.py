"""
M1: TTS 合成 + MP3 拼接
从 bilingual.json 读取中文翻译，用 edge-tts 合成每段音频，最终拼接成一个完整 MP3。

用法：
    python tts_compose.py <work_dir> [--voice zh-CN-XiaoxiaoNeural]

示例：
    python tts_compose.py work/abc12345
    python tts_compose.py work/abc12345 --voice zh-CN-YunxiNeural

可用中文声音：
    zh-CN-XiaoxiaoNeural   女声（默认，自然亲切）
    zh-CN-YunxiNeural      男声（活泼）
    zh-CN-YunjianNeural    男声（沉稳）
    zh-CN-XiaoyiNeural     女声（活泼）
"""

import sys
import json
import asyncio
import argparse
import subprocess
import time
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("缺少 edge-tts，请安装: pip install edge-tts")
    sys.exit(1)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


# ─────────────────────────────────────────
# Step 1: 逐段 TTS 合成
# ─────────────────────────────────────────
async def synthesize_segment(text: str, out_path: Path, voice: str):
    """合成单段，输出 mp3"""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


async def synthesize_all(segments: list, tts_dir: Path, voice: str) -> list[Path]:
    """
    逐段合成（顺序执行，避免 edge-tts 并发限流）。
    已存在的缓存文件直接复用，支持断点续跑。
    返回所有段的输出路径列表（顺序与 segments 对应）。
    """
    out_paths = []
    total = len(segments)

    for i, seg in enumerate(segments):
        out_path = tts_dir / f"seg_{i:04d}.mp3"
        out_paths.append(out_path)

        if out_path.exists() and out_path.stat().st_size > 0:
            print(f"  [{i+1}/{total}] ✓ (cached) {seg.get('text_zh', '')[:30]}")
            continue

        text = seg.get("text_zh", "").strip()

        if not text:
            # 空段落 → 500ms 静音占位
            _make_silence(out_path, duration=0.5)
            print(f"  [{i+1}/{total}] ≈ (silence, empty segment)")
            continue

        t0 = time.time()
        await synthesize_segment(text, out_path, voice)
        elapsed = time.time() - t0
        print(f"  [{i+1}/{total}] ✓ {elapsed:.1f}s  {text[:40]}")

    return out_paths


def _make_silence(out_path: Path, duration: float = 0.5):
    """用 ffmpeg 生成静音 mp3"""
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=24000:cl=mono",
        "-t", str(duration),
        "-acodec", "libmp3lame",
        "-q:a", "4",
        str(out_path),
    ], capture_output=True)


# ─────────────────────────────────────────
# Step 2: 拼接所有段落
# ─────────────────────────────────────────
def concat_mp3(audio_paths: list[Path], output_path: Path):
    """用 ffmpeg concat demuxer 拼接 MP3，无重新编码损耗"""
    list_file = output_path.parent / "_concat_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in audio_paths:
            if p.exists() and p.stat().st_size > 0:
                f.write(f"file '{p.absolute()}'\n")

    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-acodec", "libmp3lame",
        "-q:a", "2",      # VBR 质量 2，约 190kbps，对播客足够
        str(output_path),
    ], capture_output=True, text=True)

    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 拼接失败:\n{result.stderr[-500:]}")


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="M1: TTS 合成 → MP3 输出")
    parser.add_argument("work_dir", help="pipeline 产物目录，需含 bilingual.json")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="edge-tts 声音名称")
    parser.add_argument("--output", default=None, help="输出 MP3 路径（默认 work_dir/output_zh.mp3）")
    args = parser.parse_args()

    work_dir = Path(args.work_dir)
    bilingual_path = work_dir / "bilingual.json"

    if not bilingual_path.exists():
        print(f"✗ 找不到 bilingual.json: {bilingual_path}")
        print("  请先运行 test_pipeline.py 完成转录和翻译")
        sys.exit(1)

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    print(f"加载翻译：{len(segments)} 段，声音：{args.voice}")

    # TTS 中间文件目录
    tts_dir = work_dir / "tts_segments"
    tts_dir.mkdir(exist_ok=True)

    # Step 4: TTS 合成
    print(f"\n[4/5] TTS 合成...")
    t0 = time.time()
    out_paths = asyncio.run(synthesize_all(segments, tts_dir, args.voice))
    elapsed = time.time() - t0
    print(f"  ✓ 合成完成，耗时 {elapsed:.1f}s")

    # Step 5: 拼接
    output_mp3 = Path(args.output) if args.output else work_dir / "output_zh.mp3"
    print(f"\n[5/5] 拼接 MP3 → {output_mp3.name} ...")
    t0 = time.time()
    concat_mp3(out_paths, output_mp3)
    elapsed = time.time() - t0

    size_kb = output_mp3.stat().st_size // 1024
    duration_est = size_kb / 24  # 粗估秒数（190kbps ≈ 24KB/s）
    print(f"  ✓ 拼接完成，耗时 {elapsed:.1f}s")
    print(f"\n{'='*50}")
    print(f"✓ 中文 MP3 输出完成")
    print(f"  文件: {output_mp3}")
    print(f"  大小: {size_kb} KB（约 {duration_est:.0f} 秒）")
    print(f"  声音: {args.voice}")
    print(f"\n播放: open \"{output_mp3}\"")


if __name__ == "__main__":
    main()
