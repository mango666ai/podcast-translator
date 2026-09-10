"""
把一集做好的音频放进 staging（待审核）播客，替代手工拼 feed.xml。

之前每集都是手工复制文件 + 手写 <item> + 手算 duration/size，重复且容易漏
（漏过单集封面、漏过把 description 用 notes_to_description 生成、漏过改 enclosure 路径）。
这里按 播客工作循环.md §3.9-A 固化成一条命令。

用法：
  "$VENV_PY" stage_episode.py <video_id> \
      --audio <完整音频.mp3> \
      --srt <中文字幕.srt> \
      --notes <简介与亮点.md> \
      --slug <英文短名，不带扩展名> \
      --title "单集标题" \
      --pub-date "Wed, 10 Sep 2026 09:00:00 +0000"
"""

import argparse
import csv
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from notes_to_description import notes_md_to_description

HERE = Path(__file__).parent
STAGING = HERE / "staging"
STATUS_CSV = HERE / "podcast_status.csv"
COVER = "https://mango666ai.github.io/podcast-translator/cover-v2.png"
RAW_BASE = "https://raw.githubusercontent.com/mango666ai/podcast-translator/main"
PAGES_BASE = "https://mango666ai.github.io/podcast-translator"


def audio_duration(path: Path) -> int:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    return int(round(float(r.stdout.strip())))


def update_status(video_id: str):
    rows = list(csv.reader(STATUS_CSV.open(encoding="utf-8")))
    header, body = rows[0], rows[1:]
    col = {h: i for i, h in enumerate(header)}
    for r in body:
        if r[col["video_id"]] == video_id:
            for k in ("downloaded", "transcribed", "translated", "notes", "full_tts"):
                r[col[k]] = "yes"
            r[col["tts_sample"]] = "no"
            r[col["status"]] = "staging"
            r[col["published"]] = "staging"
            r[col["next_action"]] = "已生成完整音频并放入staging待用户试听确认"
    with STATUS_CSV.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows([header] + body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--srt", required=True)
    ap.add_argument("--notes", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--pub-date", required=True)
    args = ap.parse_args()

    audio_src, srt_src = Path(args.audio), Path(args.srt)
    audio_dst = STAGING / "episodes" / f"{args.slug}.mp3"
    srt_dst = STAGING / "transcripts" / f"{args.slug}.srt"
    audio_dst.parent.mkdir(parents=True, exist_ok=True)
    srt_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(audio_src, audio_dst)
    shutil.copy2(srt_src, srt_dst)

    dur = audio_duration(audio_dst)
    size = audio_dst.stat().st_size
    desc = escape(notes_md_to_description(Path(args.notes).read_text(encoding="utf-8")))
    ep_url = f"{PAGES_BASE}/staging/ep/{args.video_id}"

    item = (
        f"    <item>\n"
        f"      <title>{escape(args.title)}</title>\n"
        f"      <description>{desc}</description>\n"
        f"      <link>{ep_url}</link>\n"
        f"      <guid>{ep_url}</guid>\n"
        f"      <pubDate>{args.pub_date}</pubDate>\n"
        f"      <itunes:duration>{dur}</itunes:duration>\n"
        f'      <itunes:image href="{COVER}" />\n'
        f'      <enclosure url="{RAW_BASE}/staging/episodes/{args.slug}.mp3" length="{size}" type="audio/mpeg" />\n'
        f'      <podcast:transcript url="{PAGES_BASE}/staging/transcripts/{args.slug}.srt" type="text/srt" />\n'
        f"    </item>\n"
    )

    feed = STAGING / "feed.xml"
    content = feed.read_text(encoding="utf-8")
    if ep_url in content:
        raise SystemExit(f"✗ {args.video_id} 已经在 staging feed 里了，先手动移除再跑")
    feed.write_text(content.replace("  </channel>\n", item + "  </channel>\n", 1), encoding="utf-8")

    ET.parse(feed)  # 校验 XML 合法，不合法直接抛异常
    update_status(args.video_id)
    print(f"✓ {args.video_id} 已入 staging：{dur}s / {size} bytes / slug={args.slug}")


if __name__ == "__main__":
    main()
