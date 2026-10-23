#!/usr/bin/env python3
"""Append the approved copyright notice to every RSS item description."""

from __future__ import annotations

import argparse
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from notes_to_description import COPYRIGHT_NOTICE, append_copyright_notice

ITEM_RE = re.compile(r"<item>.*?</item>", re.S)
DESCRIPTION_RE = re.compile(r"(<description>)(.*?)(</description>)", re.S)


def update_feed_text(feed_text: str) -> tuple[str, int]:
    changed = 0

    def update_item(match: re.Match[str]) -> str:
        nonlocal changed
        item = match.group(0)
        description_match = DESCRIPTION_RE.search(item)
        if not description_match:
            raise ValueError("RSS item has no description")
        current = html.unescape(description_match.group(2))
        updated = append_copyright_notice(current)
        if updated == current.rstrip():
            return item
        changed += 1
        replacement = (
            description_match.group(1) + escape(updated) + description_match.group(3)
        )
        return item[: description_match.start()] + replacement + item[description_match.end() :]

    return ITEM_RE.sub(update_item, feed_text), changed


def update_feed(path: Path) -> tuple[int, int]:
    original = path.read_text(encoding="utf-8")
    updated, changed = update_feed_text(original)
    path.write_text(updated, encoding="utf-8")
    root = ET.parse(path).getroot()
    items = root.find("channel").findall("item")
    for item in items:
        description = item.findtext("description") or ""
        if description.count(COPYRIGHT_NOTICE) != 1:
            raise ValueError(f"{path}: copyright notice count is not 1")
    return changed, len(items)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feeds", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.feeds:
        changed, total = update_feed(path)
        print(f"✓ {path}: changed={changed}, items={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
