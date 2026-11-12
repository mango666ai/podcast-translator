#!/usr/bin/env python3
"""把返修后的成品替换到正式发布位置：MP3 / SRT 换成带版本号的新文件名（旧文件删除），嵌入封面，
同步 RSS 的 enclosure url/length、字幕 url 与 itunes:duration，最后跑 podcast_doctor。guid 不变，仍是同一集。

为什么要换文件名：2026-11-12 用户在小宇宙听《智能体时代的设计》，原 URL 覆盖后小宇宙仍显示旧版时长
（76 分钟），前半段还是旧音频。客户端/平台按 URL 缓存，同 URL 覆盖不可靠，所以每次替换都换新 URL。

先跑 episode_acceptance.py，通过后再用本脚本。用法：
  "$VENV_PY" replace_published.py <video_id> --audio <成品mp3> --srt <中文字幕.srt>
  "$VENV_PY" replace_published.py <video_id> --rename-only   # 只把已替换过的文件挪到新版本号 URL
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
FEED = HERE / "feed.xml"
NS = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd", "podcast": "https://podcastindex.org/namespace/1.0"}


def versioned(name: str, tag: str) -> str:
    """<slug>.mp3 / <slug>-v202611121530.mp3 → <slug>-v<tag>.mp3"""
    stem, ext = name.rsplit(".", 1)
    base = re.sub(r"-v\d{8,12}$", "", stem)
    return f"{base}-v{tag}.{ext}"


def move_to_new_version(item, tag: str) -> tuple[Path, Path | None]:
    """把这一集的 MP3（和字幕）改成新版本号文件名，并改写 feed 里对应的 URL。返回新路径。"""
    feed_text = FEED.read_text(encoding="utf-8")
    moved = []
    for el, attr, sub in ((item.find("enclosure"), "url", "episodes"),
                          (item.find("podcast:transcript", NS), "url", "transcripts")):
        if el is None:
            moved.append(None)
            continue
        old_url = el.get(attr)
        old_name = Path(urlparse(old_url).path).name
        new_name = versioned(old_name, tag)
        new_url = old_url[: -len(old_name)] + new_name
        if feed_text.count(f'"{old_url}"') != 1:
            raise SystemExit(f"✗ feed 里 {old_url} 出现次数不是 1，停下人工看")
        old_path, new_path = HERE / sub / old_name, HERE / sub / new_name
        if old_path != new_path:
            old_path.rename(new_path)
            feed_text = feed_text.replace(f'"{old_url}"', f'"{new_url}"')
            el.set(attr, new_url)
        moved.append(new_path)
    FEED.write_text(feed_text, encoding="utf-8")
    ET.parse(FEED)
    return moved[0], moved[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--audio", type=Path)
    ap.add_argument("--srt", type=Path)
    ap.add_argument("--rename-only", action="store_true", help="不换内容，只挪到新版本号文件名")
    args = ap.parse_args()
    if not args.rename_only and not (args.audio and args.srt):
        ap.error("需要 --audio 和 --srt（或用 --rename-only）")
    tag = datetime.now().strftime("%Y%m%d%H%M")
    root = ET.parse(FEED).getroot()
    item = next((it for it in root.find("channel").findall("item")
                 if (it.findtext("guid") or "").rstrip("/").endswith(f"/{args.video_id}")), None)
    if item is None:
        raise SystemExit(f"✗ 正式 feed 里没有 {args.video_id}")
    mp3 = HERE / "episodes" / Path(urlparse(item.find("enclosure").get("url")).path).name
    tr = item.find("podcast:transcript", NS)
    srt = HERE / "transcripts" / Path(urlparse(tr.get("url")).path).name if tr is not None else None
    if not args.rename_only:
        # 和入 staging 同一道检查：字幕要和配音时长对齐、不能有 >>
        from stage_episode import audio_duration, check_srt
        check_srt(args.srt, audio_duration(args.audio))
    if args.rename_only:
        mp3, srt = move_to_new_version(item, tag)
        print(f"✓ 已改名 {mp3.name}" + (f" 与 {srt.name}" if srt else ""))
        return 0
    shutil.copy2(args.audio, mp3)
    if srt is not None:
        shutil.copy2(args.srt, srt)
    mp3, srt = move_to_new_version(item, tag)
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
    new_item, n2 = re.subn(r"克隆声线", "标准音色", new_item)
    new_item, n3 = re.subn(r"克隆技术", "语音合成技术", new_item)
    new_item, n4 = re.subn(r"(翻译)(和|与)克隆", r"\1\2语音合成", new_item)
    n3 += n4
    n2 += n3
    n_voice += n2
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
