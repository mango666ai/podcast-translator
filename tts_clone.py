"""
M3: F5-TTS 声音克隆模块
用播客原声克隆主持人声音，合成中文翻译音频。

流程：
  1. 从原始音频提取前10秒作为 reference（或指定片段）
  2. F5-TTS 用 reference 声音合成每段中文翻译
  3. ffmpeg 拼接 → output_zh_clone.mp3

用法：
    python tts_clone.py work/<job_id>
    python tts_clone.py work/<job_id> --ref-start 5 --ref-duration 12   # 自定义参考片段
    python tts_clone.py work/<job_id> --device mps                       # Apple Silicon GPU
    python tts_clone.py work/<job_id> --test                             # 只合成第1段验证效果

依赖：
    pip install f5-tts accelerate
    HF_ENDPOINT=https://hf-mirror.com  （国内需设置）
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

# 优先走系统代理访问 HuggingFace；若无代理则 fallback 镜像
if not os.environ.get("HTTPS_PROXY") and not os.environ.get("https_proxy"):
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

PROJECT_DIR = Path(__file__).parent
WORK_DIR = PROJECT_DIR / "work"

# ffmpeg 路径（Homebrew 安装在 /opt/homebrew/bin，不一定在 Python subprocess PATH 里）
import shutil
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

# 参考音频默认取前10秒（可调，越干净越好）
DEFAULT_REF_START    = 0
DEFAULT_REF_DURATION = 10


# ─────────────────────────────────────────
# Step 1: 提取参考音频
# ─────────────────────────────────────────
def extract_ref_audio(audio_path: Path, out_path: Path,
                      start: float = 0, duration: float = 10) -> Path:
    """从原始音频截取一段作为 voice reference，转成 16kHz mono wav。"""
    if out_path.exists():
        print(f"  ✓ 已有参考音频: {out_path.name}")
        return out_path

    cmd = [
        FFMPEG, "-y",
        "-i", str(audio_path),
        "-ss", str(start),
        "-t", str(duration),
        "-ar", "16000",
        "-ac", "1",
        str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取参考音频失败: {result.stderr.decode()[:200]}")
    print(f"  ✓ 参考音频: {out_path.name} ({start}s ~ {start+duration}s)")
    return out_path


# ─────────────────────────────────────────
# Step 2: 获取参考音频对应的原文
# ─────────────────────────────────────────
def get_ref_text(transcript_path: Path, ref_start: float, ref_duration: float) -> str:
    """从 transcript.json 提取参考片段对应的英文原文。"""
    with open(transcript_path, encoding="utf-8") as f:
        segments = json.load(f)

    ref_end = ref_start + ref_duration
    words = []
    for seg in segments:
        seg_start = seg.get("start", 0)
        seg_end   = seg.get("end", 0)
        # 有交集就取
        if seg_start < ref_end and seg_end > ref_start:
            words.append(seg.get("text", "").strip())

    ref_text = " ".join(words)
    # 截到合理长度（F5-TTS 建议参考文本不超过参考音频实际内容）
    ref_text = ref_text[:300]
    print(f"  参考文本({len(ref_text)}字符): {ref_text[:80]}...")
    return ref_text


# ─────────────────────────────────────────
# Step 3: F5-TTS 逐段合成
# ─────────────────────────────────────────
def synthesize_clone(bilingual_path: Path, job_dir: Path,
                     ref_audio: Path, ref_text: str,
                     device: str = "cpu",
                     speed: float = 0.85,
                     test_only: bool = False) -> list:
    """用 F5-TTS 逐段合成，返回各段输出路径列表。"""
    from f5_tts.api import F5TTS

    print(f"\n  初始化 F5TTS（device={device}）...")
    t0 = time.time()
    tts = F5TTS(device=device)
    print(f"  ✓ 模型加载完成 ({time.time()-t0:.1f}s)")

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    if test_only:
        segments = segments[:1]
        print(f"  [test 模式] 只合成第1段")

    clone_dir = job_dir / "tts_clone_segments"
    clone_dir.mkdir(exist_ok=True)

    seg_paths = []
    for i, seg in enumerate(segments):
        out_wav = clone_dir / f"seg_{i:04d}.wav"
        seg_paths.append(out_wav)

        if out_wav.exists() and out_wav.stat().st_size > 0:
            print(f"  [{i+1}/{len(segments)}] ✓ (cached)")
            continue

        zh_text = seg.get("text_zh", "").strip()
        if not zh_text:
            _make_silence_wav(out_wav)
            print(f"  [{i+1}/{len(segments)}] ≈ (silence)")
            continue

        t0 = time.time()
        try:
            tts.infer(
                ref_file=str(ref_audio),
                ref_text=ref_text,
                gen_text=zh_text,
                file_wave=str(out_wav),
                speed=speed,
            )
            size_kb = out_wav.stat().st_size // 1024
            print(f"  [{i+1}/{len(segments)}] ✓ {time.time()-t0:.1f}s  {zh_text[:40]}  ({size_kb}KB)")
        except Exception as e:
            print(f"  [{i+1}/{len(segments)}] ✗ {e}")
            _make_silence_wav(out_wav)

    return seg_paths


def _make_silence_wav(out_path: Path, duration: float = 0.5):
    subprocess.run([
        FFMPEG, "-y", "-f", "lavfi",
        "-i", f"anullsrc=r=16000:cl=mono",
        "-t", str(duration),
        str(out_path),
    ], capture_output=True)


# ─────────────────────────────────────────
# Step 4: 拼接为 MP3
# ─────────────────────────────────────────
def concat_to_mp3(seg_paths: list, output_mp3: Path):
    print(f"\n  拼接 {len(seg_paths)} 段 → {output_mp3.name} ...")
    list_file = output_mp3.parent / "concat_clone.txt"
    with open(list_file, "w") as f:
        for p in seg_paths:
            f.write(f"file '{p.resolve()}'\n")

    subprocess.run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-acodec", "libmp3lame", "-q:a", "2",
        str(output_mp3),
    ], capture_output=True)
    list_file.unlink(missing_ok=True)

    size_kb = output_mp3.stat().st_size // 1024
    print(f"  ✓ 输出: {output_mp3.name} ({size_kb} KB)")


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", help="work/<job_id> 目录")
    parser.add_argument("--ref-start",    type=float, default=DEFAULT_REF_START,
                        help="参考音频起始秒（默认0）")
    parser.add_argument("--ref-duration", type=float, default=DEFAULT_REF_DURATION,
                        help="参考音频时长秒（默认10）")
    parser.add_argument("--device", default="cpu",
                        choices=["cpu", "mps", "cuda"],
                        help="推理设备（Mac 可用 mps，默认 cpu）")
    parser.add_argument("--speed", type=float, default=0.85,
                        help="语速（默认0.85，1.0为原速，越小越慢）")
    parser.add_argument("--test", action="store_true",
                        help="只合成第1段，快速验证效果")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    if not job_dir.exists():
        print(f"✗ 找不到 job 目录: {job_dir}")
        sys.exit(1)

    bilingual_path = job_dir / "bilingual.json"
    transcript_path = job_dir / "transcript.json"
    if not bilingual_path.exists():
        print("✗ 找不到 bilingual.json，请先跑 test_pipeline.py")
        sys.exit(1)

    print("=" * 55)
    print("M3: F5-TTS 声音克隆")
    print("=" * 55)

    # 找原始音频
    audio_path = next(
        (job_dir / f for f in ["audio_clip_120s.mp3", "audio.mp3", "audio.wav"]
         if (job_dir / f).exists()),
        None
    )
    if not audio_path:
        print("✗ 找不到原始音频文件")
        sys.exit(1)
    print(f"  原始音频: {audio_path.name}")

    # Step 1: 提取参考音频
    print("\n[1/4] 提取参考音频...")
    ref_audio = job_dir / "ref_voice.wav"
    extract_ref_audio(audio_path, ref_audio,
                      start=args.ref_start, duration=args.ref_duration)

    # Step 2: 获取参考文本
    print("\n[2/4] 获取参考文本...")
    if transcript_path.exists():
        ref_text = get_ref_text(transcript_path, args.ref_start, args.ref_duration)
    else:
        ref_text = ""
        print("  ⚠️  无 transcript.json，参考文本为空（效果可能稍差）")

    # Step 3: F5-TTS 合成
    print(f"\n[3/4] F5-TTS 合成（device={args.device}）...")
    seg_paths = synthesize_clone(
        bilingual_path, job_dir,
        ref_audio, ref_text,
        device=args.device,
        speed=args.speed,
        test_only=args.test,
    )

    # Step 4: 拼接
    print("\n[4/4] 拼接音频...")
    output_mp3 = job_dir / ("clone_test.mp3" if args.test else "output_zh_clone.mp3")
    concat_to_mp3(seg_paths, output_mp3)

    print("\n" + "=" * 55)
    print(f"✅ 声音克隆完成: {output_mp3}")
    print(f"   播放: open \"{output_mp3}\"")

    subprocess.run(["open", str(output_mp3)], check=False)


if __name__ == "__main__":
    main()
