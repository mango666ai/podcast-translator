import argparse
import json
import re
from pathlib import Path


def _sec(text: str) -> float:
    h, m, s = text.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_vtt(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(?P<s>\d\d:\d\d:\d\d\.\d\d\d) --> (?P<e>\d\d:\d\d:\d\d\.\d\d\d).*?\n(?P<t>.*?)(?=\n\n|\Z)",
        re.S,
    )
    cues = []
    last = ""
    for match in pattern.finditer(raw):
        text = " ".join(match.group("t").splitlines())
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&gt;&gt;", ">>")
        text = re.sub(r"\s+", " ", text).strip()
        if not text or text == last:
            continue
        last = text
        cues.append({"start": _sec(match.group("s")), "end": _sec(match.group("e")), "text": text})
    return cues


def merge_cues(cues: list[dict], max_chars: int = 420) -> list[dict]:
    chunks = []
    cur = None
    for cue in cues:
        text = cue["text"]
        starts_new_speaker = text.startswith(">>")
        if cur is None:
            cur = {**cue}
            continue
        close = cue["start"] - cur["end"] < 1.2
        room = len(cur["text"]) + len(text) < max_chars
        if close and room and not starts_new_speaker:
            add = text
            if add.startswith(cur["text"]):
                add = add[len(cur["text"]):].strip()
            if add and add not in cur["text"][-120:]:
                cur["text"] = (cur["text"] + " " + add).strip()
            cur["end"] = cue["end"]
        else:
            chunks.append(cur)
            cur = {**cue}
    if cur:
        chunks.append(cur)
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("vtt")
    parser.add_argument("out")
    args = parser.parse_args()
    chunks = merge_cues(parse_vtt(Path(args.vtt)))
    Path(args.out).write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(chunks)} segments")


if __name__ == "__main__":
    main()
