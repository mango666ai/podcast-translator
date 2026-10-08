#!/usr/bin/env python3
"""重译一个完整翻译批次，并保留可回滚备份。

批次编号从 1 开始；默认批大小沿用 youtube_dub.BATCH（当前为 25）。
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime

from youtube_dub import (
    BATCH,
    OUT_ROOT,
    TRANS_DIR,
    _safe_name,
    _source_from_status,
    display_title,
    translate,
    write_bilingual_transcript,
    write_srt,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="重译指定的完整翻译批次")
    parser.add_argument("video_id")
    parser.add_argument("--batch", type=int, required=True, help="从 1 开始的批次编号")
    args = parser.parse_args()
    if args.batch < 1:
        raise SystemExit("✗ --batch 必须从 1 开始")

    title = display_title(args.video_id)
    source = _source_from_status(args.video_id)
    prefix = f"{args.video_id}__{_safe_name(title)}"
    job = OUT_ROOT / prefix
    bilingual_path = job / f"{prefix}__双语分段.json"
    bilingual = json.loads(bilingual_path.read_text(encoding="utf-8"))
    source_segments = json.loads((TRANS_DIR / f"{args.video_id}.json").read_text(encoding="utf-8"))
    if len(bilingual) != len(source_segments):
        raise SystemExit(f"✗ 双语分段 {len(bilingual)} 条，与原文 {len(source_segments)} 条不一致")

    start = (args.batch - 1) * BATCH
    end = min(start + BATCH, len(source_segments))
    if start >= len(source_segments):
        raise SystemExit(f"✗ 第 {args.batch} 批超出范围，共 {len(source_segments)} 段")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = bilingual_path.with_name(f"{bilingual_path.stem}.before-batch-{args.batch:02d}.{stamp}.json")
    shutil.copy2(bilingual_path, backup)
    print(f"备份：{backup}")
    print(f"重译第 {args.batch} 批：#{start + 1}–#{end}")
    fixed = translate(source_segments[start:end], title, source)
    if len(fixed) != end - start:
        raise SystemExit(f"✗ 重译返回 {len(fixed)} 段，预期 {end - start} 段；未覆盖原文件")

    bilingual[start:end] = fixed
    bilingual_path.write_text(json.dumps(bilingual, ensure_ascii=False, indent=2), encoding="utf-8")
    write_srt(bilingual, job / f"{prefix}__中文字幕.srt")
    write_bilingual_transcript(bilingual, title, job / f"{prefix}__双语对照.md")
    print(f"✓ 已更新 #{start + 1}–#{end}，请先审计和人工对照，再启动 TTS")


if __name__ == "__main__":
    main()
