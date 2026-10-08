"""
把一集从 staging（待审核）转到正式播客，对应 播客工作循环.md §3.9-B。

手工做这步漏过东西：p1 转正时只改了 link/guid，忘了把 enclosure 和
podcast:transcript 的 URL 从 staging/ 路径换成正式路径，结果正式 feed 里
指向的还是 staging 目录下的文件。这里把整套替换固化下来。

用法：
  "$VENV_PY" publish_from_staging.py <video_id> --pub-date "Fri, 12 Sep 2026 09:00:00 +0000"
  # 多声线的集数加 --multivoice，状态会记成 published_multivoice
"""

import argparse
import csv
import io
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).parent
STAGING = HERE / "staging"
STATUS_CSV = HERE / "podcast_status.csv"
PAGES_BASE = "https://mango666ai.github.io/podcast-translator"


def extract_item(feed_text: str, video_id: str):
    """从 staging feed 里摘出该集的 <item>，返回 (item文本, 剩余feed文本)。"""
    marker = f"{PAGES_BASE}/staging/ep/{video_id}<"
    idx = feed_text.find(marker)
    if idx == -1:
        raise SystemExit(f"✗ staging feed 里找不到 {video_id}")
    start = feed_text.rfind("    <item>", 0, idx)
    end = feed_text.find("</item>", idx) + len("</item>\n")
    return feed_text[start:end], feed_text[:start] + feed_text[end:]


def slug_from_item(item: str) -> str:
    """从 enclosure URL 反推 slug，避免调用方再传一遍、传错。"""
    import re
    m = re.search(r"/staging/episodes/([^\"]+)\.mp3", item)
    if not m:
        raise SystemExit("✗ 解析不出 slug，enclosure URL 格式不符合预期")
    return m.group(1)


def updated_status_text(video_id: str, multivoice: bool) -> str:
    rows = list(csv.reader(STATUS_CSV.open(encoding="utf-8")))
    header, body = rows[0], rows[1:]
    col = {h: i for i, h in enumerate(header)}
    found = False
    for r in body:
        if r[col["video_id"]] == video_id:
            found = True
            r[col["status"]] = "published_multivoice" if multivoice else "published"
            r[col["published"]] = "yes"
            r[col["next_action"]] = "已正式发布到RSS"
    if not found:
        raise SystemExit(f"✗ podcast_status.csv 里找不到 {video_id}")
    output = io.StringIO(newline="")
    csv.writer(output).writerows([header] + body)
    return output.getvalue()


def parse_xml(text: str, label: str) -> None:
    try:
        ET.fromstring(text)
    except ET.ParseError as exc:
        raise SystemExit(f"✗ {label} XML 无效：{exc}") from exc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--pub-date", required=True)
    ap.add_argument("--multivoice", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="只做全部预检，不复制或改写文件")
    args = ap.parse_args()

    staging_feed = STAGING / "feed.xml"
    staging_text = staging_feed.read_text(encoding="utf-8")
    item, remaining = extract_item(staging_text, args.video_id)
    slug = slug_from_item(item)

    assets = []
    for sub, ext in (("episodes", "mp3"), ("transcripts", "srt")):
        src = STAGING / sub / f"{slug}.{ext}"
        dst = HERE / sub / f"{slug}.{ext}"
        if not src.exists() or src.stat().st_size == 0:
            raise SystemExit(f"✗ staging 产物不存在或为空：{src}")
        assets.append((src, dst))

    # 三处 URL 全部要从 staging 换成正式，漏一处就会指回 staging 目录
    item = (item
            .replace(f"/staging/ep/{args.video_id}", f"/ep/{args.video_id}")
            .replace("/staging/episodes/", "/episodes/")
            .replace("/staging/transcripts/", "/transcripts/"))
    import re
    item = re.sub(r"<pubDate>[^<]*</pubDate>", f"<pubDate>{args.pub_date}</pubDate>", item)

    feed = HERE / "feed.xml"
    formal_text = feed.read_text(encoding="utf-8")
    if f"/ep/{args.video_id}<" in formal_text:
        raise SystemExit(f"✗ {args.video_id} 已经在正式 feed 中")
    updated_feed = formal_text.replace("    <item>", item + "    <item>", 1)
    status_text = updated_status_text(args.video_id, args.multivoice)

    if "/staging/" in item:
        raise SystemExit("✗ 转正后的 item 里仍残留 staging 路径，请检查")
    parse_xml(updated_feed, "正式 feed")
    parse_xml(remaining, "staging feed")

    if args.dry_run:
        print(f"✓ 预检通过：{args.video_id} 可转正式（slug={slug}），未修改文件")
        return

    for src, dst in assets:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    staging_feed.write_text(remaining, encoding="utf-8")
    feed.write_text(updated_feed, encoding="utf-8")
    STATUS_CSV.write_text(status_text, encoding="utf-8")

    print(f"✓ {args.video_id} 已转正式发布（slug={slug}）")


if __name__ == "__main__":
    main()
