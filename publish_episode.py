"""
发布一集播客到 GitHub Releases + GitHub Pages RSS

流程：
  1. 上传 MP3 到 GitHub Releases（公网直链）
  2. 上传文稿到 GitHub Pages（transcript/<job_id>.txt）
  3. 更新 feed.xml
  4. git commit + push → GitHub Pages 自动更新

用法：
    python publish_episode.py work/<job_id> --title "How I AI EP01"
    python publish_episode.py work/<job_id> --title "标题" --dry-run
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

PROJECT_DIR  = Path(__file__).parent
REPO         = "mango666ai/podcast-translator"
PAGES_URL    = "https://mango666ai.github.io/podcast-translator"

# RSS 元数据
PODCAST_TITLE  = "Dove的学习记录"
PODCAST_AUTHOR = "DoveInBeta"
PODCAST_DESC   = "英文播客 AI 翻译中文版，声音克隆自原主持人。"
PODCAST_LANG   = "zh-cn"
FEED_PATH      = PROJECT_DIR / "feed.xml"
TRANSCRIPT_DIR = PROJECT_DIR / "transcripts"


def log(msg):
    print(f"  {msg}", flush=True)


# ─────────────────────────────────────────
# Step 1: 上传 MP3 到 GitHub Releases
# ─────────────────────────────────────────
def upload_to_github_releases(mp3_path: Path, tag: str, title: str, dry_run=False) -> str:
    """上传 MP3 到 GitHub Releases，返回公网下载 URL。"""
    log(f"上传 {mp3_path.name} → GitHub Releases ({tag})...")

    if dry_run:
        url = f"https://github.com/{REPO}/releases/download/{tag}/{mp3_path.name}"
        log(f"[dry-run] URL: {url}")
        return url

    # 检查 release 是否已存在
    check = subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO],
        capture_output=True, text=True
    )
    if check.returncode != 0:
        # 创建新 release
        subprocess.run([
            "gh", "release", "create", tag,
            "--repo", REPO,
            "--title", title,
            "--notes", f"播客自动发布：{title}",
        ], check=True)
        log(f"✓ 创建 Release: {tag}")

    # 上传文件
    subprocess.run([
        "gh", "release", "upload", tag,
        str(mp3_path),
        "--repo", REPO,
        "--clobber",  # 覆盖同名文件
    ], check=True)

    url = f"https://github.com/{REPO}/releases/download/{tag}/{mp3_path.name}"
    log(f"✓ 上传完成: {url}")
    return url


# ─────────────────────────────────────────
# Step 2: 上传文稿到 transcripts/
# ─────────────────────────────────────────
def prepare_transcript(job_dir: Path, job_id: str) -> str:
    """把双语文稿写到 transcripts/<job_id>.txt，返回公网 URL。"""
    TRANSCRIPT_DIR.mkdir(exist_ok=True)

    bilingual_path = job_dir / "bilingual.json"
    if not bilingual_path.exists():
        return ""

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    lines = []
    for seg in segments:
        start = seg.get("start") or 0
        mm, ss = divmod(int(start), 60)
        lines.append(f"[{mm:02d}:{ss:02d}]")
        lines.append(seg.get("text_zh", ""))
        lines.append("")

    out = TRANSCRIPT_DIR / f"{job_id}.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    log(f"✓ 文稿: {out.name}")
    return f"{PAGES_URL}/transcripts/{job_id}.txt"


# ─────────────────────────────────────────
# Step 3: 更新 feed.xml
# ─────────────────────────────────────────
def get_audio_duration(mp3_path: Path) -> int:
    """返回音频时长（秒）。"""
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(mp3_path)],
        capture_output=True, text=True
    )
    try:
        return int(float(r.stdout.strip()))
    except Exception:
        return 0


def _item_xml(ep: dict) -> str:
    transcript_tag = ""
    if ep.get("transcript_url"):
        transcript_tag = f'\n    <podcast:transcript url="{ep["transcript_url"]}" type="text/plain" />'
    return f"""  <item>
    <title>{ep["title"]}</title>
    <description>{ep.get("description", ep["title"])}</description>
    <link>{ep["guid"]}</link>
    <guid>{ep["guid"]}</guid>
    <pubDate>{ep["pub_date"]}</pubDate>
    <itunes:duration>{ep["duration"]}</itunes:duration>
    <enclosure url="{ep["mp3_url"]}" length="{ep["file_size"]}" type="audio/mpeg" />{transcript_tag}
  </item>"""


COVER_URL = f"{PAGES_URL}/cover.png"

def _build_feed(items_xml: list) -> str:
    items = "\n".join(items_xml)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:podcast="https://podcastindex.org/namespace/1.0">
  <channel>
    <title>{PODCAST_TITLE}</title>
    <description>{PODCAST_DESC}</description>
    <language>{PODCAST_LANG}</language>
    <link>{PAGES_URL}</link>
    <itunes:author>{PODCAST_AUTHOR}</itunes:author>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{COVER_URL}" />
    <itunes:category text="Education" />
{items}
  </channel>
</rss>"""


def update_feed(episode: dict, dry_run=False):
    """把新集追加到 feed.xml（若不存在则新建）。"""
    import re

    # 检查是否已存在
    guid = episode["guid"]
    if FEED_PATH.exists():
        content = FEED_PATH.read_text(encoding="utf-8")
        if guid in content:
            log(f"⚠️  集 {guid} 已在 feed.xml 中，跳过")
            return
        # 把新 item 插到第一个 <item> 前面（最新集在最上面）
        new_item = _item_xml(episode)
        # 补充旧 feed 里缺失的 channel 标签
        if "<itunes:image" not in content:
            content = content.replace("<itunes:explicit>false</itunes:explicit>",
                f'<itunes:explicit>false</itunes:explicit>\n    <itunes:image href="{COVER_URL}" />\n    <itunes:category text="Education" />')
        if "<item>" in content:
            content = content.replace("<item>", new_item + "\n  <item>", 1)
        else:
            content = content.replace("  </channel>", new_item + "\n  </channel>")
    else:
        content = _build_feed([_item_xml(episode)])

    if not dry_run:
        FEED_PATH.write_text(content, encoding="utf-8")
        log(f"✓ feed.xml 已更新（{FEED_PATH}）")
    else:
        log(f"[dry-run] feed.xml 会新增: {episode['title']}")


# ─────────────────────────────────────────
# Step 4: git commit + push
# ─────────────────────────────────────────
def git_push(title: str, dry_run=False):
    if dry_run:
        log("[dry-run] 跳过 git push")
        return

    subprocess.run(["git", "-C", str(PROJECT_DIR), "add",
                    "feed.xml", "transcripts/"], check=True)
    subprocess.run(["git", "-C", str(PROJECT_DIR), "commit",
                    "-m", f"发布播客: {title}"], check=True)
    subprocess.run(["git", "-C", str(PROJECT_DIR), "push"], check=True)
    log(f"✓ GitHub Pages 已更新: {PAGES_URL}/feed.xml")


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────
def publish(job_dir: Path, title: str, dry_run=False) -> str:
    job_id = job_dir.name

    print(f"\n{'='*55}")
    print(f"发布播客集: {title}")
    print(f"{'='*55}")

    # 找 MP3（优先克隆版）
    mp3_candidates = ["output_zh_clone.mp3", "final.mp3", "output_zh_minimax.mp3"]
    mp3_path = next((job_dir / f for f in mp3_candidates if (job_dir / f).exists()), None)
    if not mp3_path:
        raise FileNotFoundError(f"找不到 MP3 文件（{job_dir}）")
    log(f"使用: {mp3_path.name}")

    # Step 1: 上传 MP3
    tag = f"ep-{job_id}"
    mp3_url = upload_to_github_releases(mp3_path, tag, title, dry_run)

    # Step 2: 文稿
    transcript_url = prepare_transcript(job_dir, job_id)

    # Step 3: 更新 RSS
    duration  = get_audio_duration(mp3_path)
    file_size = mp3_path.stat().st_size
    pub_date  = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    update_feed({
        "title":          title,
        "description":    title,
        "guid":           f"{PAGES_URL}/ep/{job_id}",
        "pub_date":       pub_date,
        "duration":       duration,
        "mp3_url":        mp3_url,
        "file_size":      file_size,
        "transcript_url": transcript_url,
    }, dry_run)

    # Step 4: 推送
    git_push(title, dry_run)

    feed_url = f"{PAGES_URL}/feed.xml"
    print(f"\n✅ 发布完成！")
    print(f"   RSS: {feed_url}")
    print(f"   在小宇宙里订阅这个地址即可")
    return feed_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_dir", help="work/<job_id> 目录")
    parser.add_argument("--title", required=True, help="本集标题")
    parser.add_argument("--dry-run", action="store_true", help="演习，不实际上传/推送")
    args = parser.parse_args()

    publish(Path(args.job_dir), args.title, args.dry_run)


if __name__ == "__main__":
    main()
