"""
M5a: SRT 字幕生成
从 bilingual.json 生成两份字幕：
  - output_zh.srt          中文字幕
  - output_bilingual.srt   双语字幕（中文上，英文下）

用法：
    python generate_srt.py work/<job_id>

示例：
    python generate_srt.py work/abc12345
"""

import sys
import json
from pathlib import Path


def seconds_to_srt_time(seconds: float) -> str:
    """把秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    if seconds is None or seconds < 0:
        seconds = 0
    total_ms = int(seconds * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt_block(idx: int, start: float, end: float, lines: list[str]) -> str:
    """生成一个 SRT 字幕块"""
    # 保证 end > start，至少显示 1 秒
    if end is None or end <= start:
        end = start + 1.0
    time_line = f"{seconds_to_srt_time(start)} --> {seconds_to_srt_time(end)}"
    text = "\n".join(line for line in lines if line.strip())
    return f"{idx}\n{time_line}\n{text}\n"


def generate_srt(work_dir: Path):
    bilingual_path = work_dir / "bilingual.json"
    if not bilingual_path.exists():
        print(f"✗ 找不到 bilingual.json: {bilingual_path}")
        print("  请先运行 test_pipeline.py 完成转录和翻译")
        sys.exit(1)

    with open(bilingual_path, encoding="utf-8") as f:
        segments = json.load(f)

    print(f"加载 {len(segments)} 段，生成字幕...")

    zh_blocks = []
    bilingual_blocks = []

    for i, seg in enumerate(segments, start=1):
        start = seg.get("start") or 0.0
        end = seg.get("end")
        text_zh = seg.get("text_zh", "").strip()
        text_en = seg.get("text_en", "").strip()

        if not text_zh and not text_en:
            continue

        # 中文字幕
        if text_zh:
            zh_blocks.append(build_srt_block(len(zh_blocks) + 1, start, end, [text_zh]))

        # 双语字幕（中文在上，英文在下）
        if text_zh or text_en:
            bilingual_blocks.append(
                build_srt_block(len(bilingual_blocks) + 1, start, end, [text_zh, text_en])
            )

    # 写出文件
    out_zh = work_dir / "output_zh.srt"
    out_bilingual = work_dir / "output_bilingual.srt"

    out_zh.write_text("\n".join(zh_blocks), encoding="utf-8")
    out_bilingual.write_text("\n".join(bilingual_blocks), encoding="utf-8")

    print(f"  ✓ 中文字幕:   {out_zh}")
    print(f"  ✓ 双语字幕:   {out_bilingual}")
    print(f"  共 {len(zh_blocks)} 条字幕")

    # 预览前 3 条
    print("\n预览（前 3 条）：")
    for block in zh_blocks[:3]:
        print("  " + block.replace("\n", "\n  ").rstrip())


def main():
    if len(sys.argv) < 2:
        print("用法: python generate_srt.py work/<job_id>")
        sys.exit(1)

    work_dir = Path(sys.argv[1])
    generate_srt(work_dir)


if __name__ == "__main__":
    main()
