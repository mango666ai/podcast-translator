"""
阿里云百炼 CosyVoice TTS 合成模块（MiniMax 的低成本替代）

跟 tts_minimax.py 的 synthesize() 保持同样的函数签名，所以
youtube_dub.py / youtube_multivoice_dub.py 只要换个 provider 就能切过来。

成本对比（2026-09 实测/查证）：
  MiniMax：按次计费，额度用尽会直接中断
  CosyVoice：声音复刻**免费**（最多1000个音色/账号），合成 2元/万字符

文本清洗（剥掉 `>>`、`[音乐]` 这类不该念出来的标记）复用
tts_minimax.clean_for_tts()——那边注释里写明了它是所有 TTS 链路的唯一收口点，
换供应商不该让这条规则失效，所以这里直接 import 而不是另写一份。
"""

import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
from dotenv import load_dotenv

from tts_minimax import clean_for_tts

load_dotenv(Path(__file__).parent / ".env")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
# v3.5-plus 是 2026-09 实测里自然度最好的，而且 1.5元/万字符 反而比 v2 的 2元 更便宜。
# ⚠️ 换这个常量时，clone_cosyvoice_voice.py 的 TARGET_MODEL 必须同步改：
# 声音复刻时指定的 target_model 和合成时用的 model 必须一致，否则 voice_id 用不了。
MODEL = "cosyvoice-v3.5-plus"
# 单段合成的超时上限（秒）。正常一段 10-30 秒文本几秒就返回，给足冗余即可。
CALL_TIMEOUT = 120


def synthesize(text: str, out_path: Path, voice: str, speed: float = 0.82) -> bool:
    """合成单段音频存成 mp3。voice 传声音复刻返回的 voice_id
    （形如 `cosyvoice-v2-<prefix>-<hash>`，见 clone_cosyvoice_voice.py）。"""
    if not DASHSCOPE_API_KEY:
        raise ValueError("DASHSCOPE_API_KEY 未设置，请更新 .env 文件")

    text = clean_for_tts(text)
    if not text:
        raise ValueError("清洗后文本为空，调用方应改为写静音段")

    dashscope.api_key = DASHSCOPE_API_KEY
    synth = SpeechSynthesizer(
        model=MODEL,
        voice=voice,
        format=AudioFormat.MP3_24000HZ_MONO_256KBPS,
        speech_rate=speed,
    )
    # SDK 走 WebSocket 且没有超时参数，连接挂住时 call() 会无限阻塞——实测跑批量时
    # 卡死过一次（进程还活着但十几分钟不出新片段）。放到线程里加超时，超时就抛异常，
    # 交给调用方的 _synthesize_with_retry 重试。
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            audio = pool.submit(synth.call, text).result(timeout=CALL_TIMEOUT)
        except FuturesTimeout:
            raise RuntimeError(f"CosyVoice 合成超时（>{CALL_TIMEOUT}s，voice={voice}）")
    if not audio:
        raise RuntimeError(f"CosyVoice 未返回音频（voice={voice}）")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    return True
