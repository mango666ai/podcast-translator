#!/usr/bin/env python3
"""把返修后的成品替换到正式发布位置：MP3 / SRT 覆盖到 feed 引用的同名文件，嵌入封面，
同步 RSS 的 enclosure length 与 itunes:duration，最后跑 podcast_doctor。URL 不变，订阅端无需改动。

先跑 episode_acceptance.py，通过后再用本脚本。用法：
  "$VENV_PY" replace_published.py <video_id> --audio <成品mp3> --srt <中文字幕.srt>
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
FEED = HERE / "feed.xml"
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "podcast": "https://podcastindex.org/namespace/1.0"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--srt", type=Path, required=True)
    args = ap.parse_args()
    root = ET.parse(FEED).getroot()
    item = next((it for it in root.find("channel").findall("item")
                 if (it.findtext("guid") or "").rstrip("/").endswith(f"/{args.video_id}")), None)
    if item is None:
        raise SystemExit(f"✗ 正式 feed 里没有 {args.video_id}")
    mp3 = HERE / "episodes" / Path(urlparse(item.find("enclosure").get("url")).path).name
    tr = item.find("podcast:transcript", NS)
    srt = HERE / "transcripts" / Path(urlparse(tr.get("url")).path).name if tr is not None else None
    if srt is not None and args.srt.read_text(encoding="utf-8").count(">>"):
        raise SystemExit("✗ 字幕里还有 >>，先修")
    shutil.copy2(args.audio, mp3)
    if srt is not None:
        shutil.copy2(args.srt, srt)
    out = subprocess.run([sys.executable, "embed_episode_covers.py", "--video-id", args.video_id],
                         capture_output=True, text=True, cwd=HERE)
    if out.returncode != 0:
        raise SystemExit(f"✗ 嵌封面失败：{out.stderr[-500:]}")
    # 隐式标识：ID3 元数据写入 AIGC 字段（《人工智能生成合成内容标识办法》要求元数据含生成合成属性）
    import json as _json, tempfile as _tf
    aigc = _json.dumps({"Label": "1", "ContentProducer": "Alibaba Cloud Model Studio (CosyVoice TTS)",
                        "ProduceID": args.video_id, "ContentPropagator": "mango666ai/podcast-translator",
                        "PropagateID": mp3.name}, ensure_ascii=False)
    with _tf.TemporaryDirectory() as td:
        tmp = Path(td) / mp3.name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3), "-map", "0", "-c", "copy", "-id3v2_version", "3",
                        "-metadata", f"AIGC={aigc}", "-metadata", "comment=AI生成合成内容：中文译制与全部人声均由 AI 合成",
                        str(tmp)], check=True)
        shutil.copy2(tmp, mp3)
    size = mp3.stat().st_size
    feed_text = FEED.read_text(encoding="utf-8")
    url = item.find("enclosure").get("url")
    feed_text = re.sub(r'(<enclosure\b(?=[^>]*\burl="' + re.escape(url) + r'")[^>]*\blength=")\d+("[^>]*>)',
                       rf"\g<1>{size}\g<2>", feed_text)
    FEED.write_text(feed_text, encoding="utf-8")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                               capture_output=True, text=True).stdout)
    text = FEED.read_text(encoding="utf-8")
    m = re.search(r"<item>(?:(?!</item>).)*?/ep/" + re.escape(args.video_id) + r"</guid>(?:(?!</item>).)*?</item>", text, re.S)
    new_item = re.sub(r"<itunes:duration>\d+</itunes:duration>", f"<itunes:duration>{round(dur)}</itunes:duration>", m.group(0))
    # 简介里旧的"声音克隆自原视频/主持人"说明同步改为标准音色说明（2026-11-11 起公开节目不再克隆真人声音）
    new_item, n_voice = re.subn(r"声音克隆自[^。]*。", "所有声音均为AI合成的标准音色，并非原节目主持人和嘉宾本人。", new_item)
    if n_voice:
        print(f"  简介声音说明已更新 {n_voice} 处")
    FEED.write_text(text.replace(m.group(0), new_item), encoding="utf-8")
    ET.parse(FEED)
    doc = subprocess.run([sys.executable, "podcast_doctor.py"], capture_output=True, text=True, cwd=HERE).stdout
    print(f"✓ 已替换 {mp3.name}（{dur:.1f}s，{mp3.stat().st_size} bytes）" + (f" 与 {srt.name}" if srt else ""))
    print("  " + doc.strip().splitlines()[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
