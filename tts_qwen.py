"""Qwen-Audio TTS with official, non-impersonating system voices."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer
from dotenv import load_dotenv

from tts_minimax import clean_for_tts

load_dotenv(Path(__file__).parent / ".env")

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
MODEL = "qwen-audio-3.0-tts-plus"
CALL_TIMEOUT = 120
SYSTEM_VOICES = {
    "longanlufeng": "龙安鲁风（明亮开朗男声）",
    "longanlingxin": "龙安灵心（知心温暖女声）",
}


def synthesize(text: str, out_path: Path, voice: str, speed: float = 1.0) -> bool:
    if voice not in SYSTEM_VOICES:
        raise ValueError(f"Qwen 试播只允许已核对的官方系统音色: {voice}")
    text = clean_for_tts(text)
    if not text:
        raise ValueError("清洗后文本为空，调用方应写静音段")
    if not DASHSCOPE_API_KEY:
        raise ValueError("DASHSCOPE_API_KEY 未设置")

    dashscope.api_key = DASHSCOPE_API_KEY

    def call() -> bytes:
        synthesizer = SpeechSynthesizer(
            model=MODEL,
            voice=voice,
            format=AudioFormat.MP3_24000HZ_MONO_256KBPS,
            speech_rate=speed,
        )
        return synthesizer.call(text)

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            audio = pool.submit(call).result(timeout=CALL_TIMEOUT)
        except FuturesTimeout as error:
            raise RuntimeError(f"Qwen TTS 超时（>{CALL_TIMEOUT}s，voice={voice}）") from error
    if not audio:
        raise RuntimeError(f"Qwen TTS 未返回音频（voice={voice}）")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(audio)
    return True
