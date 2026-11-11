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


_SENTENCE_END = (".", "?", "!", '."', '?"', '!"')


def merge_segments(segs: list[dict], max_chars: int = 260, soft_chars: int = 150) -> list[dict]:
    """把字幕事件合并成翻译分段。

    max_chars 是硬上限；soft_chars 是软上限：当前段已经够长且刚好在句末（. ? !）时就
    收尾，让分段尽量落在句子边界。半句断开的段会诱导 DeepSeek 把下一段内容提前译入，
    造成成品里同一句话念两遍（见 youtube_dub.cross_segment_overlaps）。自动字幕本身没有
    标点时此规则不起作用，仍按 max_chars 切。
    """
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
        at_sentence_end = len(cur["text"]) >= soft_chars and cur["text"].rstrip().endswith(_SENTENCE_END)
        if close and room and not starts_new_speaker and not at_sentence_end:
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
    parser.add_argument("--soft-chars", type=int, default=150,
                        help="段落达到此长度且处于句末时就切开，尽量不在半句处断（0=关闭）")
    args = parser.parse_args()
    chunks = merge_segments(parse_json3(Path(args.json3)), max_chars=args.max_chars,
                            soft_chars=args.soft_chars or args.max_chars)
    Path(args.out).write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(chunks)} segments")


if __name__ == "__main__":
    main()
