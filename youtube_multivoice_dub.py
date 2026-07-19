"""
Multi-voice Chinese dubbing for already translated YouTube episodes.

This keeps the existing translation/SRT workflow intact, but lets one episode
route different time ranges to different MiniMax voices.
"""
import argparse
import json
import time
from pathlib import Path

from tts_minimax import synthesize, _concat, _make_silence


HERE = Path(__file__).parent
OUT_ROOT = HERE / "youtube_dub"


def _synthesize_with_retry(text: str, out: Path, *, voice: str, speed: float, attempts: int = 3):
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


def _speaker_for(start: float, rules: list[dict]) -> str:
    for rule in rules:
        if rule["start"] <= start < rule["end"]:
            return rule["speaker"]
    return "main"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bilingual_json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--main-voice", required=True)
    ap.add_argument("--host-voice", default="Elegant_Man")
    ap.add_argument("--clip-voice", default="Calm_Woman")
    ap.add_argument("--rules", required=True, help="JSON list of {start,end,speaker}")
    ap.add_argument("--label", default="multivoice")
    args = ap.parse_args()

    bilingual_path = Path(args.bilingual_json)
    segments = json.loads(bilingual_path.read_text(encoding="utf-8"))
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    voices = {
        "main": args.main_voice,
        "host": args.host_voice,
        "clip": args.clip_voice,
    }

    seg_dir = bilingual_path.parent / f"seg_{args.label}"
    seg_dir.mkdir(exist_ok=True)

    paths = []
    for i, seg in enumerate(segments):
        speaker = _speaker_for(float(seg.get("start", 0)), rules)
        voice = voices.get(speaker, args.main_voice)
        out = seg_dir / f"{bilingual_path.stem}__{args.label}__{speaker}__seg_{i:04d}.mp3"
        paths.append(out)
        if out.exists() and out.stat().st_size > 0:
            print(f"  [{i + 1}/{len(segments)}] cached {speaker}/{voice}")
            continue

        text = seg.get("text_zh", "").strip()
        if not text:
            _make_silence(out)
            print(f"  [{i + 1}/{len(segments)}] silence")
            continue

        _synthesize_with_retry(text, out, voice=voice, speed=args.speed)
        print(f"  [{i + 1}/{len(segments)}] {speaker}/{voice}")

    _concat(paths, Path(args.out))
    print(f"done: {args.out}")


if __name__ == "__main__":
    main()
