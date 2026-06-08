"""
M5c: ID3 章节标记
向 MP3 文件写入 ID3v2 CHAP 章节，主流播客客户端（Overcast、Pocket Casts、Apple Podcasts）均支持。

策略：
  - 默认每 5 分钟一章（--interval 可调）
  - 也可以按段落数分组（--by-segments N）
  - 章节标题 = 该章首句中文翻译（截取 20 字）

用法：
    python add_chapters.py work/<job_id>
    python add_chapters.py work/<job_id> --interval 3        # 每 3 分钟一章
    python add_chapters.py work/<job_id> --by-segments 15    # 每 15 段一章
    python add_chapters.py work/<job_id> --mp3 final.mp3     # 指定 MP3 文件名
"""

import sys
import json
import argparse
from pathlib import Path

try:
    from mutagen.id3 import ID3, CHAP, CTOC, TIT2, ID3NoHeaderError
    from mutagen.mp3 import MP3
except ImportError:
    print("缺少 mutagen，请安装: pip install mutagen")
    sys.exit(1)


# ─────────────────────────────────────────
# 章节分组逻辑
# ─────────────────────────────────────────
def group_by_interval(segments: list, interval_seconds: int) -> list[dict]:
    """按时间间隔分组，每 interval_seconds 秒一章"""
    if not segments:
        return []

    chapters = []
    chap_start = segments[0].get("start") or 0.0
    chap_texts = []
    next_boundary = chap_start + interval_seconds

    for seg in segments:
        seg_start = seg.get("start") or 0.0
        text_zh = seg.get("text_zh", "").strip()

        if seg_start >= next_boundary and chap_texts:
            chapters.append({
                "start": chap_start,
                "end": seg_start,
                "title": _make_title(chap_texts[0], len(chapters) + 1),
            })
            chap_start = seg_start
            chap_texts = []
            next_boundary = seg_start + interval_seconds

        if text_zh:
            chap_texts.append(text_zh)

    # 最后一章
    if chap_texts:
        last_end = segments[-1].get("end") or (segments[-1].get("start") or 0) + 5
        chapters.append({
            "start": chap_start,
            "end": last_end,
            "title": _make_title(chap_texts[0], len(chapters) + 1),
        })

    return chapters


def group_by_segments(segments: list, n: int) -> list[dict]:
    """每 n 段一章"""
    if not segments:
        return []

    chapters = []
    for i in range(0, len(segments), n):
        chunk = segments[i: i + n]
        start = chunk[0].get("start") or 0.0
        end = chunk[-1].get("end") or (chunk[-1].get("start") or 0) + 5
        title_text = next((s.get("text_zh", "") for s in chunk if s.get("text_zh")), "")
        chapters.append({
            "start": start,
            "end": end,
            "title": _make_title(title_text, len(chapters) + 1),
        })

    return chapters


def _make_title(text: str, idx: int) -> str:
    """截取首句作为章节标题，最多 20 字"""
    text = text.strip()
    if not text:
        return f"第 {idx} 章"
    # 截到第一个句号/逗号/问号，或 20 字
    for end_char in "。，？！,.?!":
        pos = text.find(end_char)
        if 0 < pos <= 20:
            return text[:pos]
    return text[:20] if len(text) > 20 else text


# ─────────────────────────────────────────
# 写入 ID3 章节
# ─────────────────────────────────────────
def write_chapters(mp3_path: Path, chapters: list[dict]):
    """向 MP3 写入 CTOC + CHAP ID3 帧"""
    try:
        tags = ID3(str(mp3_path))
    except ID3NoHeaderError:
        tags = ID3()

    # 清除旧章节
    tags.delall("CHAP")
    tags.delall("CTOC")

    chap_ids = []
    for i, chap in enumerate(chapters):
        chap_id = f"chp{i}"
        chap_ids.append(chap_id)

        start_ms = int(chap["start"] * 1000)
        end_ms = int(chap["end"] * 1000)

        tags.add(CHAP(
            element_id=chap_id,
            start_time=start_ms,
            end_time=end_ms,
            start_offset=0xFFFFFFFF,
            end_offset=0xFFFFFFFF,
            sub_frames=[TIT2(text=[chap["title"]])],
        ))

    # 目录帧（CTOC），让播放器识别章节列表
    tags.add(CTOC(
        element_id="toc",
        flags=0x03,          # top-level + ordered
        child_element_ids=chap_ids,
        sub_frames=[TIT2(text=["Table of Contents"])],
    ))

    tags.save(str(mp3_path), v2_version=3)


# ─────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="M5c: 写入 ID3 章节标记")
    parser.add_argument("job_dir", help="work/<job_id> 目录")
    parser.add_argument("--mp3", default=None,
                        help="指定 MP3 文件名（默认优先 final.mp3 > output_zh_minimax.mp3 > output_zh.mp3）")
    parser.add_argument("--interval", type=int, default=300,
                        help="按时间间隔分章，单位秒（默认 300 = 5 分钟）")
    parser.add_argument("--by-segments", type=int, default=None, metavar="N",
                        help="每 N 段分一章（优先级高于 --interval）")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    bilingual_path = job_dir / "bilingual.json"

    if not bilingual_path.exists():
        print(f"✗ 找不到 bilingual.json: {bilingual_path}")
        sys.exit(1)

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    # 确定目标 MP3
    if args.mp3:
        mp3_path = job_dir / args.mp3
    else:
        candidates = ["final.mp3", "output_zh_minimax.mp3", "output_zh.mp3"]
        mp3_path = next((job_dir / c for c in candidates if (job_dir / c).exists()), None)

    if not mp3_path or not mp3_path.exists():
        print(f"✗ 找不到 MP3 文件（试过 final.mp3 / output_zh_minimax.mp3 / output_zh.mp3）")
        sys.exit(1)

    # 获取 MP3 时长（用于校验）
    audio = MP3(str(mp3_path))
    duration = audio.info.length
    print(f"目标文件：{mp3_path.name}（{duration:.1f}s，{mp3_path.stat().st_size // 1024}KB）")

    # 分组
    if args.by_segments:
        chapters = group_by_segments(segments, args.by_segments)
        mode = f"每 {args.by_segments} 段一章"
    else:
        chapters = group_by_interval(segments, args.interval)
        mode = f"每 {args.interval//60} 分钟一章"

    if not chapters:
        print("✗ 没有生成任何章节，请检查 bilingual.json 是否有时间戳")
        sys.exit(1)

    print(f"分组方式：{mode}，共 {len(chapters)} 章")
    print()

    # 打印章节列表
    for i, chap in enumerate(chapters, 1):
        mm, ss = divmod(int(chap["start"]), 60)
        print(f"  {i:2d}. [{mm:02d}:{ss:02d}] {chap['title']}")

    # 写入
    print(f"\n写入 ID3 章节标记...")
    write_chapters(mp3_path, chapters)
    print(f"✓ 完成：{mp3_path}")
    print(f"  {len(chapters)} 个章节已写入，播放器（Overcast / Pocket Casts / Apple Podcasts）可跳转")


if __name__ == "__main__":
    main()
