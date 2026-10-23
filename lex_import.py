#!/usr/bin/env python3
"""Import one Lex Fridman episode from joeseesun/lexfridman-cn.

The upstream repository is used only as a structured index.  The English
transcript is fetched from the official Lex Fridman transcript URL.  Raw
transcripts and generated work files belong under ``lex_work/`` (gitignored).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

UPSTREAM_REPO = "https://github.com/joeseesun/lexfridman-cn"
RAW_BASE = "https://raw.githubusercontent.com/joeseesun/lexfridman-cn"
DEFAULT_REF = "main"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
SPAN_RE = re.compile(
    r'<span class="ts-name">(.*?)</span>\s*'
    r'<span class="ts-timestamp">(.*?)</span>\s*'
    r'<span class="ts-text">(.*?)</span>',
    re.S,
)
TIMESTAMP_RE = re.compile(r"\((\d{1,2}):(\d{2}):(\d{2})\)")


def _download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "replace")


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(html.unescape(value).split())


def _timestamp_seconds(value: str) -> float:
    match = TIMESTAMP_RE.search(value)
    if not match:
        raise ValueError(f"missing HH:MM:SS timestamp: {value!r}")
    hours, minutes, seconds = (int(part) for part in match.groups())
    return float(hours * 3600 + minutes * 60 + seconds)


def parse_official_transcript(page: str) -> list[dict[str, Any]]:
    """Convert Lex's official transcript HTML into source segments."""
    raw = SPAN_RE.findall(page)
    if not raw:
        raise ValueError("official transcript contains no ts-name/ts-timestamp/ts-text rows")

    rows: list[dict[str, Any]] = []
    last_speaker = ""
    for name_html, timestamp_html, text_html in raw:
        speaker = _clean_html(name_html) or last_speaker
        text = _clean_html(text_html)
        if not speaker:
            raise ValueError("first transcript row has no speaker")
        if not text:
            continue
        start = _timestamp_seconds(timestamp_html)
        rows.append(
            {"start": start, "source_start": start, "speaker": speaker, "text": text}
        )
        last_speaker = speaker

    for previous, current in zip(rows, rows[1:]):
        if current["start"] < previous["start"]:
            raise ValueError(
                f"timestamps must increase: {previous['start']} -> {current['start']}"
            )

    # The official timestamps have one-second precision, so a short response
    # and the next speaker can legitimately share the same timestamp.  Split
    # that interval by estimated reading time while retaining source_start.
    index = 0
    while index < len(rows):
        group_end = index + 1
        while group_end < len(rows) and rows[group_end]["source_start"] == rows[index]["source_start"]:
            group_end += 1
        group = rows[index:group_end]
        if len(group) > 1:
            base = group[0]["source_start"]
            next_start = (
                rows[group_end]["source_start"]
                if group_end < len(rows)
                else base + sum(max(1.0, len(row["text"].split()) / 2.5) for row in group)
            )
            available = max(0.01 * len(group), next_start - base)
            weights = [max(1.0, min(30.0, len(row["text"].split()) / 2.5)) for row in group]
            total = sum(weights)
            elapsed = 0.0
            for row, weight in zip(group, weights):
                row["start"] = round(base + available * elapsed / total, 3)
                elapsed += weight
        index = group_end

    for index, row in enumerate(rows):
        if index + 1 < len(rows):
            row["end"] = rows[index + 1]["start"]
        else:
            # The official transcript has no end time for its last row.  Use a
            # conservative reading-time tail instead of stretching it across
            # unrelated outro/advertising audio.
            estimated = len(row["text"].split()) / 2.5
            row["end"] = row["start"] + min(30.0, max(2.0, estimated))
        row["text_zh"] = ""

    return rows


def clip_segments(
    segments: list[dict[str, Any]], start: float | None, end: float | None
) -> list[dict[str, Any]]:
    if start is None and end is None:
        return segments
    lower = 0.0 if start is None else start
    upper = float("inf") if end is None else end
    if upper <= lower:
        raise ValueError("clip end must be greater than clip start")
    return [row for row in segments if row["start"] < upper and row["end"] > lower]


def build_speaker_rules(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for row in segments:
        if rules and rules[-1]["speaker"] == row["speaker"]:
            rules[-1]["end"] = row["end"]
        else:
            rules.append(
                {"start": row["start"], "end": row["end"], "speaker": row["speaker"]}
            )
    return rules


def _read_json(source_dir: Path | None, name: str, ref: str) -> Any:
    if source_dir:
        return json.loads((source_dir / "tools" / name).read_text(encoding="utf-8"))
    return json.loads(_download_text(f"{RAW_BASE}/{ref}/tools/{name}"))


def _upstream_commit(source_dir: Path | None, ref: str) -> str:
    if not source_dir:
        return ref
    result = subprocess.run(
        ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def load_episode(number: int, source_dir: Path | None, ref: str) -> dict[str, Any]:
    master = _read_json(source_dir, "lex-master.json", ref)
    episode = next((item for item in master if int(item.get("num", -1)) == number), None)
    if episode is None:
        raise ValueError(f"episode #{number} not found in lex-master.json")
    if not episode.get("officialTranscript"):
        raise ValueError(f"episode #{number} has no official transcript")

    feed_audio = _read_json(source_dir, "feed_audio.json", ref)
    translations = _read_json(source_dir, "translations.json", ref)
    result = dict(episode)
    result["audioUrl"] = feed_audio.get("by_num", {}).get(str(number))
    result["zhMetadata"] = translations.get(episode["slug"], {})
    return result


def write_import(
    *,
    episode: dict[str, Any],
    transcript_html: str,
    output_dir: Path,
    upstream_commit: str,
    clip_start: float | None = None,
    clip_end: float | None = None,
) -> dict[str, Any]:
    all_segments = parse_official_transcript(transcript_html)
    segments = clip_segments(all_segments, clip_start, clip_end)
    if not segments:
        raise ValueError("selected clip contains no transcript segments")
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "episodeNumber": episode["num"],
        "title": episode["title"],
        "date": episode["date"],
        "slug": episode["slug"],
        "youtubeId": episode["ytId"],
        "youtubeUrl": f"https://www.youtube.com/watch?v={episode['ytId']}",
        "officialEpisodeUrl": episode["lexUrl"],
        "officialTranscriptUrl": episode["officialTranscript"],
        "officialAudioUrl": episode.get("audioUrl"),
        "zhMetadata": episode.get("zhMetadata", {}),
        "upstreamRepository": UPSTREAM_REPO,
        "upstreamCommit": upstream_commit,
        "fullTranscriptSegmentCount": len(all_segments),
        "selectedSegmentCount": len(segments),
        "selectedStart": segments[0]["start"],
        "selectedEnd": segments[-1]["end"],
        "speakers": sorted({row["speaker"] for row in segments}),
        "transcriptSha256": hashlib.sha256(transcript_html.encode()).hexdigest(),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "source_segments.json").write_text(
        json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "speaker_rules.json").write_text(
        json.dumps(build_speaker_rules(segments), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Import one official Lex transcript")
    parser.add_argument("episode", type=int, help="Lex episode number, e.g. 398")
    parser.add_argument("--upstream-dir", type=Path, help="local lexfridman-cn checkout")
    parser.add_argument("--upstream-ref", default=DEFAULT_REF)
    parser.add_argument("--transcript-html", type=Path, help="already downloaded official HTML")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--clip-start", type=float)
    parser.add_argument("--clip-end", type=float)
    args = parser.parse_args()

    episode = load_episode(args.episode, args.upstream_dir, args.upstream_ref)
    transcript_html = (
        args.transcript_html.read_text(encoding="utf-8")
        if args.transcript_html
        else _download_text(episode["officialTranscript"])
    )
    output_dir = args.output_dir or Path("lex_work") / f"{episode['num']}-{episode['slug']}"
    metadata = write_import(
        episode=episode,
        transcript_html=transcript_html,
        output_dir=output_dir,
        upstream_commit=_upstream_commit(args.upstream_dir, args.upstream_ref),
        clip_start=args.clip_start,
        clip_end=args.clip_end,
    )
    print(
        f"✓ Lex #{metadata['episodeNumber']}: {metadata['selectedSegmentCount']} segments, "
        f"{len(metadata['speakers'])} speakers -> {output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
