#!/usr/bin/env python3
"""从说话人规则里挑一段只含某个人声音的 20 秒样本，用于 CosyVoice 声音复刻。

为什么需要（2026-11-11）：早期样本是人工按时间段截的 90 秒，`P06RgnUKX_I` 的嘉宾样本里实际混进了
约 44 秒主持人的提问，复刻出的声线是两个人的混合。这里改为在声纹复核过的规则上自动挑：
同一个 speaker 连续发言、中间没有 `>>` 换人记号、Whisper 词级时间连续（停顿 < 1.5 秒）、不含音乐/掌声/赞助口播的最长一段，
从中间截 SAMPLE_SEC 秒。CosyVoice 要求样本 10–20 秒、含至少 5 秒连续清晰人声。

用法（VideoLingo/.venv）：
  "$VENV_PY" pick_voice_sample.py <video_id> --rules youtube_dub/<id>__speaker_rules.json --speaker host
输出：youtube_transcripts/_audio/<video_id>_<speaker>_cv20.mp3，并打印所选时间段与其原文，供人工核对。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from speaker_voice_check import OUT_ROOT, TRANS_DIR, _speaker_at, align_spans, find_audio

SAMPLE_SEC = 20.0
MAX_GAP = 1.5
# 垫了背景音乐或是赞助口播的段落不能当复刻样本（2026-11-11 zegYJ6dhIg4 曾挑到 Mercury 广告段）
UNSUITABLE = re.compile(r"\[(music|音乐|applause|laughter)\]|brought to you by|sponsor|this episode is", re.I)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--rules", type=Path, required=True)
    ap.add_argument("--speaker", required=True)
    ap.add_argument("--seconds", type=float, default=SAMPLE_SEC)
    args = ap.parse_args()
    segs = json.loads((TRANS_DIR / f"{args.video_id}.json").read_text(encoding="utf-8"))
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    words_path = OUT_ROOT / f"{args.video_id}__whisper_words.json"
    if not words_path.exists():
        raise SystemExit(f"✗ 缺少 {words_path}，先跑 speaker_voice_check.py")
    spans = align_spans(segs, json.loads(words_path.read_text(encoding="utf-8")))
    labels = [_speaker_at(rules, s["start"] + 0.001, rules[0]["speaker"]) for s in segs]

    best, cur = None, None
    for i, s in enumerate(segs):
        ok = labels[i] == args.speaker and spans[i] is not None and not UNSUITABLE.search(s.get("text", ""))
        new_turn = s.get("text", "").lstrip().startswith(">>")
        if ok and cur and not new_turn and spans[i][0] - cur["end"] < MAX_GAP:
            cur["end"] = spans[i][1]; cur["segs"].append(i)
        elif ok:
            cur = {"start": spans[i][0], "end": spans[i][1], "segs": [i]}
        else:
            cur = None
        if cur and (best is None or cur["end"] - cur["start"] > best["end"] - best["start"]):
            best = {"start": cur["start"], "end": cur["end"], "segs": list(cur["segs"])}
    if not best or best["end"] - best["start"] < 12:
        raise SystemExit(f"✗ 找不到 {args.speaker} 连续 ≥12 秒的发言")
    length = min(args.seconds, best["end"] - best["start"])
    mid = (best["start"] + best["end"]) / 2
    a = max(best["start"], mid - length / 2)
    out = TRANS_DIR / "_audio" / f"{args.video_id}_{args.speaker}_cv20.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.2f}", "-t", f"{length:.2f}",
                    "-i", str(find_audio(args.video_id)),
                    "-ac", "1", "-ar", "24000", "-b:a", "128k", str(out)], check=True)
    print(f"✓ {args.speaker}: 原音频 {a:.1f}–{a + length:.1f} 秒（所在连续发言 {best['start']:.1f}–{best['end']:.1f}，"
          f"{len(best['segs'])} 段） → {out}")
    for i in best["segs"][:3]:
        print(f"   #{i + 1} {segs[i]['text'][:100]}")


if __name__ == "__main__":
    main()
