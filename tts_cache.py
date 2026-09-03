"""TTS 分段缓存的内容指纹。

为什么需要：两个配音脚本都用 `seg_{i:04d}.mp3` 当缓存键——只认序号（多声线还加 speaker），
不认文本内容。于是「改完译文重跑一遍、替换线上音频」这个操作会静默地复用上一轮的旧音频：
序号没变的段落根本不会重新合成。2026-08-11 修完翻译截断、2026-08-20 修完编号错位之后
各重跑过一次，`P3KDebPTUrw` 线上音频因此变成新旧两版译文混在一起——同一句话用两种措辞
先后念了两遍，而字幕里只有新的那一版。

做法：每个 seg mp3 旁边写一个同名 `.txt` 指纹，记 voice/speed/文本哈希。命中缓存前先比对，
对不上就重新合成。老的缓存目录没有 `.txt`，默认判为不可信（宁可重合成，也不要再混一次），
确实想省额度可以显式传 --trust-legacy-cache。
"""
import hashlib
from pathlib import Path


def _fingerprint(text: str, *, voice: str, speed: float) -> str:
    raw = f"{voice}|{speed:.3f}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _sidecar(mp3: Path) -> Path:
    return mp3.with_suffix(".txt")


def cache_hit(mp3: Path, text: str, *, voice: str, speed: float,
              trust_legacy: bool = False) -> tuple[bool, str]:
    """→ (能否复用, 不能复用的原因)。原因为空表示本来就没有这个文件，属正常首次合成。"""
    if not (mp3.exists() and mp3.stat().st_size > 0):
        return False, ""
    side = _sidecar(mp3)
    if not side.exists():
        if trust_legacy:
            return True, ""
        return False, "旧缓存没有指纹文件"
    want = _fingerprint(text, voice=voice, speed=speed)
    if side.read_text(encoding="utf-8").strip() == want:
        return True, ""
    return False, "译文或声音参数已变"


def mark_synthesized(mp3: Path, text: str, *, voice: str, speed: float) -> None:
    _sidecar(mp3).write_text(_fingerprint(text, voice=voice, speed=speed), encoding="utf-8")
