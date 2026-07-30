"""
M4: 开场简介生成
流程：
  1. 读取 bilingual.json，提取节目主题和关键内容
  2. OpenAI GPT 生成中文开场旁白（~150字，女声朗读约60秒）
  3. MiniMax TTS 合成简介音频（无 key 时自动 fallback 到 edge-tts）
  4. ffmpeg 拼接：intro.mp3 + 主体 MP3 → final.mp3

用法：
    python intro_compose.py work/<job_id>
    python intro_compose.py work/<job_id> --tts edge        # 强制用 edge-tts
    python intro_compose.py work/<job_id> --voice Wise_Woman
    python intro_compose.py work/<job_id> --no-concat       # 只生成 intro，不拼接
"""

import os
import sys
import json
import time
import asyncio
import argparse
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv
from llm_openai import call_gpt

load_dotenv(Path(__file__).parent / ".env")

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_URL = "https://api.minimax.io/v1/t2a_v2"

DEFAULT_MINIMAX_VOICE = "Wise_Woman"
DEFAULT_EDGE_VOICE = "zh-CN-XiaoxiaoNeural"

# ─────────────────────────────────────────
# Step 1: 用 OpenAI GPT 生成简介文本
# ─────────────────────────────────────────
INTRO_PROMPT = """你是一位专业播客编辑，请根据以下节目内容片段，写一段中文开场旁白。

要求：
- 长度约 100-150 字（女声朗读约 40-60 秒）
- 语气温暖亲切，像在邀请听众
- 点出节目的核心话题和 2-3 个亮点
- 结尾用"让我们一起来听"收束
- 不要提"本期"、不要用"欢迎收听XXX播客"这种套话
- 直接输出旁白正文，不要任何前缀或解释

节目内容片段（前 {n} 段）：
{content}
"""


def generate_intro_text(segments: list) -> str:
    """调用 OpenAI GPT 生成开场旁白文本"""
    # 取前 20 段，足够了解节目主题
    sample = segments[:20]
    content_lines = []
    for seg in sample:
        zh = seg.get("text_zh", "").strip()
        en = seg.get("text_en", "").strip()
        if zh:
            content_lines.append(f"- {zh}")
        elif en:
            content_lines.append(f"- {en}")

    prompt = INTRO_PROMPT.format(
        n=len(sample),
        content="\n".join(content_lines),
    )

    print("  调用 OpenAI GPT 生成简介...", end="", flush=True)
    t0 = time.time()
    intro_text = call_gpt(prompt, timeout=60).strip()
    elapsed = time.time() - t0

    print(f" ✓ {elapsed:.1f}s，{len(intro_text)} 字")
    return intro_text


# ─────────────────────────────────────────
# Step 2a: MiniMax TTS 合成
# ─────────────────────────────────────────
def synthesize_minimax(text: str, out_path: Path, voice: str) -> bool:
    if not MINIMAX_API_KEY:
        return False

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
            "speed": 0.92,   # 略慢，开场旁白节奏感更好
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": 32000,
            "bitrate": 128000,
            "format": "mp3",
        },
    }

    try:
        resp = requests.post(MINIMAX_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        base = data.get("base_resp", {})
        if base.get("status_code", -1) != 0:
            print(f"\n  ⚠️  MiniMax 错误: {base.get('status_msg')}，fallback 到 edge-tts")
            return False

        audio_hex = data.get("data", {}).get("audio", "")
        if not audio_hex:
            return False

        out_path.write_bytes(bytes.fromhex(audio_hex))
        return True

    except Exception as e:
        print(f"\n  ⚠️  MiniMax 请求失败: {e}，fallback 到 edge-tts")
        return False


# ─────────────────────────────────────────
# Step 2b: edge-tts fallback
# ─────────────────────────────────────────
async def synthesize_edge(text: str, out_path: Path, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


# ─────────────────────────────────────────
# Step 3: ffmpeg 拼接 intro + 主体
# ─────────────────────────────────────────
def prepend_intro(intro_path: Path, body_path: Path, output_path: Path):
    """把 intro 拼到主体 MP3 前面"""
    list_file = output_path.parent / "_intro_concat.txt"
    with open(list_file, "w") as f:
        f.write(f"file '{intro_path.resolve()}'\n")
        f.write(f"file '{body_path.resolve()}'\n")

    result = subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-acodec", "libmp3lame", "-q:a", "2",
        str(output_path),
    ], capture_output=True, text=True)

    list_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 拼接失败:\n{result.stderr[-300:]}")


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="M4: 生成开场简介并拼接到 MP3")
    parser.add_argument("job_dir", help="work/<job_id> 目录")
    parser.add_argument("--tts", choices=["minimax", "edge", "auto"], default="auto",
                        help="TTS 引擎（默认 auto：有 MiniMax key 用 MiniMax，否则 edge-tts）")
    parser.add_argument("--voice", default=None,
                        help="声音 ID（MiniMax 默认 Wise_Woman，edge 默认 zh-CN-XiaoxiaoNeural）")
    parser.add_argument("--no-concat", action="store_true",
                        help="只生成 intro.mp3，不与主体拼接")
    parser.add_argument("--regen", action="store_true",
                        help="重新生成简介（忽略缓存）")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    bilingual_path = job_dir / "bilingual.json"

    if not bilingual_path.exists():
        print(f"✗ 找不到 bilingual.json: {bilingual_path}")
        sys.exit(1)

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    print(f"\n[M4] 开场简介生成（共 {len(segments)} 段节目内容）")
    print("=" * 50)

    # Step 1: 生成简介文本（有缓存跳过）
    intro_text_path = job_dir / "intro_text.txt"
    if intro_text_path.exists() and not args.regen:
        intro_text = intro_text_path.read_text(encoding="utf-8").strip()
        print(f"  ✓ 使用缓存简介文本（{len(intro_text)} 字）")
    else:
        intro_text = generate_intro_text(segments)
        intro_text_path.write_text(intro_text, encoding="utf-8")

    print(f"\n  简介预览：\n  {intro_text[:100]}{'...' if len(intro_text) > 100 else ''}")

    # Step 2: TTS 合成简介
    intro_mp3 = job_dir / "intro.mp3"
    use_minimax = (args.tts == "minimax") or (args.tts == "auto" and bool(MINIMAX_API_KEY))
    use_edge = (args.tts == "edge") or not use_minimax

    # 确定声音
    if args.voice:
        voice = args.voice
    elif use_minimax:
        voice = DEFAULT_MINIMAX_VOICE
    else:
        voice = DEFAULT_EDGE_VOICE

    print(f"\n[TTS] 合成简介音频（{'MiniMax' if use_minimax else 'edge-tts'}，{voice}）...")

    if not intro_mp3.exists() or args.regen:
        t0 = time.time()

        if use_minimax:
            ok = synthesize_minimax(intro_text, intro_mp3, voice)
            if not ok:
                # fallback
                use_edge = True
                voice = DEFAULT_EDGE_VOICE
                use_minimax = False

        if use_edge:
            asyncio.run(synthesize_edge(intro_text, intro_mp3, voice))

        elapsed = time.time() - t0
        size_kb = intro_mp3.stat().st_size // 1024
        print(f"  ✓ intro.mp3 生成完成（{size_kb}KB，{elapsed:.1f}s）")
    else:
        print(f"  ✓ 使用缓存 intro.mp3")

    if args.no_concat:
        print(f"\n✓ 简介音频：{intro_mp3}")
        print("  （--no-concat 模式，未拼接主体）")
        return

    # Step 3: 拼接
    # 自动检测主体 MP3（优先 minimax 版）
    body_candidates = [
        job_dir / "output_zh_minimax.mp3",
        job_dir / "output_zh.mp3",
    ]
    body_mp3 = next((p for p in body_candidates if p.exists()), None)

    if not body_mp3:
        print(f"\n⚠️  找不到主体 MP3（output_zh_minimax.mp3 或 output_zh.mp3）")
        print("  请先运行 tts_compose.py 或 tts_minimax.py 生成主体音频")
        print(f"  intro.mp3 已保存：{intro_mp3}")
        return

    final_mp3 = job_dir / "final.mp3"
    print(f"\n[ffmpeg] 拼接：intro + {body_mp3.name} → final.mp3 ...")
    t0 = time.time()
    prepend_intro(intro_mp3, body_mp3, final_mp3)
    elapsed = time.time() - t0

    size_kb = final_mp3.stat().st_size // 1024
    print(f"  ✓ final.mp3 完成（{size_kb}KB，{elapsed:.1f}s）")
    print(f"\n{'='*50}")
    print(f"✓ 完整播客 MP3 输出：{final_mp3}")
    print(f"  播放：open \"{final_mp3}\"")


if __name__ == "__main__":
    main()
