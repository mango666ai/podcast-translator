"""
修复翻译批次截断导致的空段问题，不重跑整集。

背景：youtube_dub.py 的 translate() 一批处理 25 段，DeepSeek 偶尔在批次接近
token 上限时被截断，旧代码没做数量校验，截断后缺的段落被静默当成空翻译，
最终配音时用静音顶替。这里只重新翻译含空段的批次，其余批次原样保留。

用法（用 VideoLingo/.venv 的 python3.11 跑）：
  "$VENV_PY" repair_translation.py <video_id>
"""
import argparse
import json

from youtube_dub import (
    TRANS_DIR, OUT_ROOT, BATCH,
    translate, write_srt, write_bilingual_transcript,
    display_title, _source_from_status, _safe_name,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    args = ap.parse_args()

    title = display_title(args.video_id)
    source = _source_from_status(args.video_id)
    safe_title = _safe_name(title)
    prefix = f"{args.video_id}__{safe_title}"
    job = OUT_ROOT / prefix

    bilp = job / f"{prefix}__双语分段.json"
    bil = json.loads(bilp.read_text(encoding="utf-8"))
    segs = json.loads((TRANS_DIR / f"{args.video_id}.json").read_text(encoding="utf-8"))

    empty_idx = [i for i, s in enumerate(bil) if not s.get("text_zh", "").strip()]
    if not empty_idx:
        print("没有发现空翻译段落，无需修复")
        return

    affected_batches = sorted({i // BATCH for i in empty_idx})
    print(f"发现 {len(empty_idx)} 个空段，分布在 {len(affected_batches)} 个批次：{affected_batches}")

    changed = []
    for b in affected_batches:
        start = b * BATCH
        end = min(start + BATCH, len(segs))
        batch_segs = segs[start:end]
        print(f"  重新翻译批次 {b}（段 {start}-{end - 1}）…")
        fixed = translate(batch_segs, title, source)
        for j, seg in enumerate(fixed):
            idx = start + j
            old_zh = bil[idx].get("text_zh", "")
            bil[idx] = {**bil[idx], **seg}
            if not old_zh.strip() and bil[idx].get("text_zh", "").strip():
                changed.append(idx)

    bilp.write_text(json.dumps(bil, ensure_ascii=False, indent=2), encoding="utf-8")
    write_srt(bil, job / f"{prefix}__中文字幕.srt")
    write_bilingual_transcript(bil, title, job / f"{prefix}__双语对照.md")

    still_empty = [i for i, s in enumerate(bil) if not s.get("text_zh", "").strip()]
    print(f"✓ 修复完成：{len(changed)} 段找回内容，仍为空的段落: {still_empty}")
    out_idx_file = job / f"{prefix}__修复段落下标.json"
    out_idx_file.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
    print(f"变化的段落下标已写入 {out_idx_file}，用于后续只重新TTS这些段落")


if __name__ == "__main__":
    main()
