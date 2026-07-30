import argparse
import json
import re
from pathlib import Path


def clean_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = text.replace("&gt;&gt;", ">>")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def event_text(event: dict) -> str:
    segs = event.get("segs") or []
    return clean_text("".join(seg.get("utf8", "") for seg in segs))


def parse_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for event in data.get("events", []):
        text = event_text(event)
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000
        dur = event.get("dDurationMs", 0) / 1000
        out.append({"start": start, "end": start + dur, "text": text})
    return out


def dedupe_words(text: str) -> str:
    words = text.split()
    if len(words) < 8:
        return text
    # Remove exact adjacent phrase duplication caused by rolling captions.
    changed = True
    while changed:
        changed = False
        n = len(words)
        for size in range(min(24, n // 2), 2, -1):
            i = 0
            while i + size * 2 <= len(words):
                if words[i:i + size] == words[i + size:i + size * 2]:
                    del words[i + size:i + size * 2]
                    changed = True
                else:
                    i += 1
    return " ".join(words)


def merge_segments(segs: list[dict], max_chars: int = 260) -> list[dict]:
    chunks = []
    cur = None
    for seg in segs:
        text = dedupe_words(seg["text"])
        starts_new_speaker = text.startswith(">>")
        if cur is None:
            cur = {"start": seg["start"], "end": seg["end"], "text": text}
            continue
        close = seg["start"] - cur["end"] < 1.5
        room = len(cur["text"]) + len(text) < max_chars
        if close and room and not starts_new_speaker:
            cur["text"] = clean_text(cur["text"] + " " + text)
            cur["text"] = dedupe_words(cur["text"])
            cur["end"] = seg["end"]
        else:
            chunks.append(cur)
            cur = {"start": seg["start"], "end": seg["end"], "text": text}
    if cur:
        chunks.append(cur)
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("json3")
    parser.add_argument("out")
    parser.add_argument("--max-chars", type=int, default=260)
    args = parser.parse_args()
    chunks = merge_segments(parse_json3(Path(args.json3)), max_chars=args.max_chars)
    Path(args.out).write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(chunks)} segments")


if __name__ == "__main__":
    main()
