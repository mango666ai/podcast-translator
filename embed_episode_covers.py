#!/usr/bin/env python3
"""Embed cover-v2.png into formal-feed MP3s without re-encoding audio."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
DEFAULT_FEED = HERE / "feed.xml"
DEFAULT_COVER = HERE / "cover-v2.png"


def _run(command: list[str], *, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=text, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pcm_hash(path: Path) -> str:
    result = _run(
        [
            "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
            "-f", "hash", "-hash", "sha256", "-",
        ]
    )
    match = re.search(r"SHA256=([0-9a-f]{64})", result.stdout)
    if not match:
        raise RuntimeError(f"could not calculate PCM hash for {path}")
    return match.group(1)


def _duration(path: Path) -> float:
    result = _run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ]
    )
    return float(result.stdout.strip())


def _attached_pictures(path: Path) -> int:
    result = _run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)]
    )
    streams = json.loads(result.stdout).get("streams", [])
    return sum(
        1
        for stream in streams
        if stream.get("codec_type") == "video"
        and stream.get("disposition", {}).get("attached_pic") == 1
    )


def _extract_cover_hash(mp3: Path, directory: Path) -> str:
    extracted = directory / "embedded-cover.png"
    _run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-map", "0:v:0",
            "-c", "copy", str(extracted),
        ]
    )
    return _sha256(extracted)


def formal_episodes(feed: Path) -> dict[str, tuple[Path, str]]:
    root = ET.parse(feed).getroot()
    result: dict[str, tuple[Path, str]] = {}
    for item in root.find("channel").findall("item"):
        guid = (item.findtext("guid") or "").strip()
        video_id = guid.rstrip("/").rsplit("/", 1)[-1]
        enclosure = item.find("enclosure")
        if enclosure is None:
            raise ValueError(f"{video_id}: missing enclosure")
        url = enclosure.get("url", "")
        filename = Path(urlparse(url).path).name
        path = feed.parent / "episodes" / filename
        if not path.exists():
            raise FileNotFoundError(path)
        if video_id in result:
            raise ValueError(f"duplicate video id in feed: {video_id}")
        result[video_id] = (path, url)
    return result


def update_enclosure_length(feed: Path, url: str, size: int) -> None:
    content = feed.read_text(encoding="utf-8")
    pattern = re.compile(
        r'(<enclosure\b(?=[^>]*\burl="' + re.escape(url) + r'")[^>]*\blength=")\d+("[^>]*>)'
    )
    updated, count = pattern.subn(rf"\g<1>{size}\g<2>", content)
    if count != 1:
        raise ValueError(f"expected one enclosure for {url}, found {count}")
    feed.write_text(updated, encoding="utf-8")
    ET.parse(feed)


def embed_cover(mp3: Path, cover: Path) -> dict[str, object]:
    before_pcm = _pcm_hash(mp3)
    before_duration = _duration(mp3)

    with tempfile.TemporaryDirectory(prefix="podcast-cover-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        output = temp_dir / mp3.name
        _run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-i", str(cover),
                "-map", "0:a:0", "-map", "1:v:0", "-map_metadata", "0",
                "-map_chapters", "0", "-c:a", "copy", "-c:v", "copy",
                "-id3v2_version", "3", "-metadata:s:v", "title=Album cover",
                "-metadata:s:v", "comment=Cover (front)", "-disposition:v:0", "attached_pic",
                str(output),
            ]
        )

        after_pcm = _pcm_hash(output)
        after_duration = _duration(output)
        if before_pcm != after_pcm:
            raise RuntimeError(f"{mp3}: decoded PCM changed")
        if abs(before_duration - after_duration) > 0.01:
            raise RuntimeError(
                f"{mp3}: duration changed {before_duration:.6f} -> {after_duration:.6f}"
            )
        if _attached_pictures(output) != 1:
            raise RuntimeError(f"{mp3}: expected exactly one attached picture")
        if _extract_cover_hash(output, temp_dir) != _sha256(cover):
            raise RuntimeError(f"{mp3}: embedded cover differs from {cover}")

        os.replace(output, mp3)

    return {
        "path": str(mp3),
        "duration": before_duration,
        "pcmSha256": before_pcm,
        "coverSha256": _sha256(cover),
        "size": mp3.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, default=DEFAULT_FEED)
    parser.add_argument("--cover", type=Path, default=DEFAULT_COVER)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--video-id")
    group.add_argument("--all", action="store_true")
    args = parser.parse_args()

    episodes = formal_episodes(args.feed)
    selected = episodes if args.all else {args.video_id: episodes[args.video_id]}
    for video_id, (mp3, url) in selected.items():
        report = embed_cover(mp3, args.cover)
        update_enclosure_length(args.feed, url, int(report["size"]))
        print(json.dumps({"videoId": video_id, **report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
