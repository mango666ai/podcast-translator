import argparse
import json
import re
from pathlib import Path

from json3_to_segments import clean_text, event_text, parse_json3


def _speaker_turns(en_events: list[dict]) -> list[tuple[float, str]]:
    turns = []
    speaker = "andrew"
    last_turn = -999.0
    for event in en_events:
        text = event["text"]
        start = event["start"]
        if not text.startswith(">>"):
            continue
        if turns and start - last_turn < 2.0:
            continue
        speaker = "andrew" if speaker == "host" else "host"
        turns.append((start, speaker))
        last_turn = start
    # Known structure: after intro, host welcomes Andrew, Andrew answers, then host asks.
    turns.extend([(0.0, "host"), (12.5, "andrew"), (24.8, "host"), (28.8, "andrew"), (31.4, "host"), (35.9, "andrew"), (82.0, "host"), (153.0, "host"), (157.0, "andrew"), (162.0, "host"), (195.0, "andrew")])
    turns = sorted(turns, key=lambda x: x[0])
    # Remove near-duplicates after adding anchors.
    deduped = []
    for start, speaker in turns:
        if deduped and abs(start - deduped[-1][0]) < 1.0:
            deduped[-1] = (start, speaker)
        else:
            deduped.append((start, speaker))
    return deduped


def _speaker_at(start: float, turns: list[tuple[float, str]]) -> str:
    speaker = "host"
    for turn_start, turn_speaker in turns:
        if turn_start <= start:
            speaker = turn_speaker
        else:
            break
    return speaker


def _strip_noise(text: str) -> str:
    text = text.replace("Opening Eye", "OpenAI")
    text = text.replace("Codeex", "Codex").replace("CodeX", "Codex")
    text = text.replace("OpenI", "OpenAI")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build(zh_json3: Path, en_json3: Path, max_chars: int) -> list[dict]:
    zh_events = parse_json3(zh_json3)
    en_events = parse_json3(en_json3)
    turns = _speaker_turns(en_events)
    out = []
    cur = None
    for event in zh_events:
        text = _strip_noise(clean_text(event["text"]))
        if not text:
            continue
        speaker = _speaker_at(event["start"], turns)
        if cur and cur["speaker"] == speaker and event["start"] - cur["end"] < 1.4 and len(cur["text_zh"]) + len(text) < max_chars:
            cur["text_zh"] = clean_text(cur["text_zh"] + " " + text)
            cur["end"] = event["end"]
        else:
            if cur:
                out.append(cur)
            cur = {
                "start": event["start"],
                "end": event["end"],
                "speaker": speaker,
                "text_zh": text,
            }
    if cur:
        out.append(cur)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zh-json3", required=True)
    parser.add_argument("--en-json3", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--max-chars", type=int, default=220)
    args = parser.parse_args()
    segments = build(Path(args.zh_json3), Path(args.en_json3), args.max_chars)
    Path(args.out).write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for seg in segments:
        counts[seg["speaker"]] = counts.get(seg["speaker"], 0) + 1
    print(f"wrote {len(segments)} segments {counts}")


if __name__ == "__main__":
    main()
