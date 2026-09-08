"""
Multi-voice Chinese dubbing for already translated YouTube episodes.

This keeps the existing translation/SRT workflow intact, but lets one episode
route different time ranges to different voices.

--provider 选 TTS 供应商：minimax（默认，历史集数都是它生成的）或 cosyvoice
（阿里云百炼，声音复刻免费+合成2元/万字符，成本低得多）。两家的 voice_id 格式和
克隆流程都不一样，**同一集不要混用**，否则一集里前后声音会不一致。
"""
import argparse
import json
import time
from pathlib import Path

from tts_minimax import synthesize as synthesize_minimax
from tts_minimax import _concat, _make_silence, clean_for_tts
from tts_cache import cache_hit, mark_synthesized


def _get_synthesize(provider: str):
    if provider == "minimax":
        return synthesize_minimax
    if provider == "cosyvoice":
        from tts_cosyvoice import synthesize as synthesize_cosyvoice  # 延迟导入，没装 dashscope 也能跑 minimax
        return synthesize_cosyvoice
    raise SystemExit(f"✗ 未知 provider：{provider}")


HERE = Path(__file__).parent
OUT_ROOT = HERE / "youtube_dub"


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
                print(f"  TTS retry {attempt}/{attempts - 1}: {e}; wait {wait}s")
                time.sleep(wait)
    raise last_error


def _speaker_for(start: float, rules: list[dict], default_speaker: str) -> str:
    for rule in rules:
        if rule["start"] <= start < rule["end"]:
            return rule["speaker"]
    return default_speaker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bilingual_json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--voices", required=True,
                     help='JSON object mapping speaker label -> voice_id, '
                          'e.g. \'{"host":"...","main":"..."}\'; supports any number of speakers')
    ap.add_argument("--rules", required=True, help="JSON list of {start,end,speaker}")
    ap.add_argument("--label", default="multivoice")
    ap.add_argument("--provider", default="minimax", choices=["minimax", "cosyvoice"],
                    help="TTS 供应商；同一集不要中途换，会导致前后声音不一致")
    ap.add_argument("--limit-seconds", type=float, default=0,
                    help="只合成到原视频这个时间点为止（做试听小样用，0=全片）")
    ap.add_argument("--trust-legacy-cache", action="store_true",
                    help="没有 .txt 指纹的旧缓存也直接复用（默认不复用，会重新合成）")
    args = ap.parse_args()

    bilingual_path = Path(args.bilingual_json)
    segments = json.loads(bilingual_path.read_text(encoding="utf-8"))
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    voices = json.loads(args.voices)
    if not voices:
        raise SystemExit("✗ --voices 不能为空")
    default_speaker = next(iter(voices))
    synthesize = _get_synthesize(args.provider)

    if args.limit_seconds:
        segments = [s for s in segments if float(s.get("start", 0)) < args.limit_seconds]
        print(f"⚠️ 试听模式：只合成前 {args.limit_seconds:.0f} 秒（{len(segments)} 段）")

    seg_dir = bilingual_path.parent / f"seg_{args.label}"
    seg_dir.mkdir(exist_ok=True)

    paths = []
    for i, seg in enumerate(segments):
        speaker = _speaker_for(float(seg.get("start", 0)), rules, default_speaker)
        voice = voices.get(speaker, voices[default_speaker])
        out = seg_dir / f"{bilingual_path.stem}__{args.label}__{speaker}__seg_{i:04d}.mp3"
        paths.append(out)

        text = clean_for_tts(seg.get("text_zh", ""))
        hit, why = cache_hit(out, text, voice=voice, speed=args.speed,
                             trust_legacy=args.trust_legacy_cache)
        if hit:
            print(f"  [{i + 1}/{len(segments)}] cached {speaker}/{voice}")
            continue
        if why:
            print(f"  [{i + 1}/{len(segments)}] 缓存失效（{why}），重新合成")

        if not text:
            _make_silence(out)
            mark_synthesized(out, text, voice=voice, speed=args.speed)
            print(f"  [{i + 1}/{len(segments)}] silence")
            continue

        _synthesize_with_retry(synthesize, text, out, voice=voice, speed=args.speed)
        mark_synthesized(out, text, voice=voice, speed=args.speed)
        print(f"  [{i + 1}/{len(segments)}] {speaker}/{voice}")

    _concat(paths, Path(args.out))
    print(f"done: {args.out}")


if __name__ == "__main__":
    main()
