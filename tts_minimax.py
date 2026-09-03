"""
MiniMax TTS 合成模块（替换 edge-tts，音质更自然）

用法：
    # 试听不同声音（推荐先跑这个）
    python tts_minimax.py --preview

    # 替换 tts_compose.py 中的 TTS 引擎，处理某个 job
    python tts_minimax.py work/<job_id> --voice Podcast_female

可用声音（中文，按场景推荐）：
    Podcast_female     播客女声，自然亲切（推荐通勤听）
    Podcast_male       播客男声，沉稳
    female-shaonv      少女音，活泼
    female-yujie       御姐音，成熟
    presenter_male     男主持，正式
    audiobook_female_2 有声书女声，情感丰富
"""

import os
import sys
import json
import time
import argparse
import subprocess
import asyncio
import requests
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_URL = "https://api.minimax.io/v1/t2a_v2"  # 国际版，无需 GroupId

# 每次请求最大字符数（官方限制 10000 字符）
MAX_CHARS = 5000

VOICES = {
    "Wise_Woman":         "睿智女声（推荐）",
    "Calm_Woman":         "沉稳女声",
    "Gentle_Woman":       "温柔女声",
    "Lively_Girl":        "活泼少女",
    "Elegant_Man":        "优雅男声",
    "Deep_Voice_Man":     "低沉男声",
}

PREVIEW_TEXT = "欢迎收听今天的播客节目。我们今天要讨论的是人工智能的未来发展方向，以及它将如何改变我们的工作和生活方式。这是一个非常值得深入探讨的话题。"


# ─────────────────────────────────────────
# 核心合成函数
# ─────────────────────────────────────────
def synthesize(text: str, out_path: Path, voice: str = "Wise_Woman", speed: float = 0.95) -> bool:
    """
    调用 MiniMax T2A v2 合成单段音频，保存为 mp3。
    speed=0.95 略慢，配合 1.2x 播放器倍速刚好。
    返回是否成功。
    """
    if not MINIMAX_API_KEY or MINIMAX_API_KEY == "换成你重新生成的新key":
        raise ValueError("MINIMAX_API_KEY 未设置，请更新 .env 文件")

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "speech-02-hd",
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": voice,
            "speed": speed,
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
        },
    }

    resp = requests.post(MINIMAX_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # 检查业务状态码
    base = data.get("base_resp", {})
    if base.get("status_code", -1) != 0:
        raise RuntimeError(f"MiniMax 返回错误: {base.get('status_msg')}")

    # 解码 hex 音频数据
    audio_hex = data.get("data", {}).get("audio", "")
    if not audio_hex:
        raise RuntimeError("返回数据中没有 audio 字段")

    audio_bytes = bytes.fromhex(audio_hex)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio_bytes)
    return True


# ─────────────────────────────────────────
# 试听模式：生成所有声音的样本
# ─────────────────────────────────────────
def run_preview():
    print("=" * 55)
    print("MiniMax TTS 声音试听")
    print("=" * 55)
    print(f"试听文本：{PREVIEW_TEXT[:30]}...\n")

    preview_dir = Path(__file__).parent / "work" / "voice_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for voice_id, desc in VOICES.items():
        out = preview_dir / f"{voice_id}.mp3"
        if out.exists():
            print(f"  ✓ {voice_id}（{desc}）— 已缓存")
            results.append(out)
            continue

        print(f"  合成 {voice_id}（{desc}）...", end="", flush=True)
        t0 = time.time()
        try:
            synthesize(PREVIEW_TEXT, out, voice=voice_id)
            print(f" ✓ {time.time()-t0:.1f}s")
            results.append(out)
        except Exception as e:
            print(f" ✗ {e}")

    print(f"\n所有样本保存在：{preview_dir}")
    print("\n逐个播放：")
    for out in results:
        voice_id = out.stem
        desc = VOICES.get(voice_id, "")
        print(f"  open \"{out}\"   # {voice_id}（{desc}）")

    # 自动播放第一个
    if results:
        print(f"\n正在播放第一个（{results[0].stem}）...")
        subprocess.run(["open", str(results[0])], check=False)


# ─────────────────────────────────────────
# 处理 job：替换 tts_compose.py 的 TTS 引擎
# ─────────────────────────────────────────
def run_job(job_dir: Path, voice: str):
    bilingual_path = job_dir / "bilingual.json"
    if not bilingual_path.exists():
        print(f"✗ 找不到 {bilingual_path}，请先跑 test_pipeline.py")
        sys.exit(1)

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    tts_dir = job_dir / "tts_minimax_segments"
    tts_dir.mkdir(exist_ok=True)

    print(f"共 {len(segments)} 段，声音：{voice}（{VOICES.get(voice, '')}）")
    print()

    seg_paths = []
    for i, seg in enumerate(segments):
        out = tts_dir / f"seg_{i:04d}.mp3"
        seg_paths.append(out)

        if out.exists() and out.stat().st_size > 0:
            print(f"  [{i+1}/{len(segments)}] ✓ (cached)")
            continue

        text = seg.get("text_zh", "").strip()
        if not text:
            _make_silence(out)
            print(f"  [{i+1}/{len(segments)}] ≈ (silence)")
            continue

        t0 = time.time()
        try:
            synthesize(text, out, voice=voice)
            print(f"  [{i+1}/{len(segments)}] ✓ {time.time()-t0:.1f}s  {text[:35]}")
        except Exception as e:
            print(f"  [{i+1}/{len(segments)}] ✗ {e}，用静音替代")
            _make_silence(out)

    # ffmpeg 拼接
    output_mp3 = job_dir / "output_zh_minimax.mp3"
    _concat(seg_paths, output_mp3)

    size_kb = output_mp3.stat().st_size // 1024
    print(f"\n✓ 输出：{output_mp3}（{size_kb} KB）")
    subprocess.run(["open", str(output_mp3)], check=False)


def _make_silence(out_path: Path, duration: float = 0.3):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r=32000:cl=mono",
        "-t", str(duration), "-q:a", "9",
        str(out_path),
    ], capture_output=True)


def _concat(seg_paths: list, output: Path):
    print(f"\n拼接 {len(seg_paths)} 段 → {output.name} ...")
    list_file = output.parent / "concat_minimax.txt"
    with open(list_file, "w") as f:
        for p in seg_paths:
            f.write(f"file '{p.resolve()}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-acodec", "libmp3lame", "-q:a", "2",
        str(output),
    ], capture_output=True)
    list_file.unlink(missing_ok=True)


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", nargs="?", help="work/<job_id> 目录")
    parser.add_argument("--voice", default="Wise_Woman", choices=list(VOICES.keys()))
    parser.add_argument("--preview", action="store_true", help="生成所有声音的试听样本")
    args = parser.parse_args()

    if args.preview or not args.job_dir:
        run_preview()
    else:
        run_job(Path(args.job_dir), args.voice)


if __name__ == "__main__":
    main()
