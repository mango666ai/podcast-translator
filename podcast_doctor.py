#!/usr/bin/env python3
"""检查 RSS、状态表和公开产物是否彼此一致。"""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
NS = {"podcast": "https://podcastindex.org/namespace/1.0"}


def local_path(url: str) -> Path | None:
    path = urlparse(url).path.lstrip("/")
    marker = "podcast-translator/"
    if marker in path:
        path = path.split(marker, 1)[1]
    if path.startswith("main/"):
        path = path[len("main/"):]
    if path.startswith(("episodes/", "transcripts/", "staging/")):
        return HERE / path
    return None


def feed_items(feed_path: Path, errors: list[str], warnings: list[str], *, staging_feed: bool) -> dict[str, dict[str, Path]]:
    root = ET.parse(feed_path).getroot()
    result: dict[str, dict[str, Path]] = {}
    for item in root.find("channel").findall("item"):
        guid = (item.findtext("guid") or "").strip()
        match = re.search(r"/ep/([^/?#]+)$", guid)
        if not match:
            match = re.search(r"/staging/ep/([^/?#]+)$", guid)
        if not match:
            errors.append(f"{feed_path}: 无法从 guid 解析 video_id: {guid}")
            continue
        video_id = match.group(1)
        if video_id in result:
            errors.append(f"{feed_path}: video_id 重复: {video_id}")
        enclosure = item.find("enclosure")
        transcript = item.find("podcast:transcript", NS)
        assets: dict[str, Path] = {}
        for kind, node in (("audio", enclosure), ("transcript", transcript)):
            url = node.get("url", "") if node is not None else ""
            path = local_path(url)
            if path is None or not path.exists():
                errors.append(f"{feed_path}: {video_id} 的 {kind} 不存在: {url}")
            elif path:
                assets[kind] = path
                is_staging_asset = path.relative_to(HERE).parts[0] == "staging"
                if staging_feed != is_staging_asset:
                    expected = "staging" if staging_feed else "正式"
                    warnings.append(f"{feed_path}: {video_id} 的 {kind} 没有指向{expected}目录")
        if enclosure is not None and "audio" in assets:
            declared = enclosure.get("length", "")
            if declared.isdigit() and int(declared) != assets["audio"].stat().st_size:
                errors.append(f"{feed_path}: {video_id} enclosure length 与文件大小不符")
        result[video_id] = assets
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="检查播客发布状态")
    parser.add_argument("--strict", action="store_true", help="公开目录有孤立文件时也返回非零")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    formal = feed_items(HERE / "feed.xml", errors, warnings, staging_feed=False)
    staging = feed_items(HERE / "staging/feed.xml", errors, warnings, staging_feed=True)
    overlap = set(formal) & set(staging)
    if overlap:
        errors.append(f"正式与 staging feed 重复: {', '.join(sorted(overlap))}")

    with (HERE / "podcast_status.csv").open(encoding="utf-8", newline="") as handle:
        rows = {row["video_id"]: row for row in csv.DictReader(handle)}
    for video_id in formal:
        row = rows.get(video_id)
        if not row or row["published"] != "yes":
            errors.append(f"{video_id}: 在正式 feed，但状态表 published 不是 yes")
    for video_id in staging:
        row = rows.get(video_id)
        if not row or row["published"] != "staging":
            errors.append(f"{video_id}: 在 staging feed，但状态表 published 不是 staging")
    for video_id, row in rows.items():
        if row["status"] == "abandoned" and row["published"] != "no":
            errors.append(f"{video_id}: abandoned 但 published={row['published']}")
        if row["published"] == "yes" and video_id not in formal:
            errors.append(f"{video_id}: 状态表已发布，但不在正式 feed")
        if row["published"] == "staging" and video_id not in staging:
            errors.append(f"{video_id}: 状态表为 staging，但不在 staging feed")

    referenced = {path.resolve() for assets in (*formal.values(), *staging.values()) for path in assets.values()}
    for directory in ("episodes", "transcripts", "staging/episodes", "staging/transcripts"):
        for path in (HERE / directory).iterdir():
            if path.is_file() and path.resolve() not in referenced:
                warnings.append(f"未被 feed 引用: {path.relative_to(HERE)}")

    print(f"formal={len(formal)} staging={len(staging)} errors={len(errors)} warnings={len(warnings)}")
    for message in errors:
        print(f"ERROR {message}")
    for message in warnings:
        print(f"WARN  {message}")
    return 1 if errors or (args.strict and warnings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
