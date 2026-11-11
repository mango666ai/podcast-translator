#!/usr/bin/env python3
"""体检一集的 TTS 分段缓存：哪些段是没指纹的旧缓存、哪些段会把 `>>`/[笑声] 念出来、
哪些段音频时长与文本长度明显不匹配（疑似复读或拖长）。

背景（2026-11-11）：《智能体时代的设计》9 月 21 日续跑时信任了 9 月 2 日的旧缓存，
而 `>>` 不念出来的修复是 9 月 3 日才合入的，于是 43 段把 `>>` 念成了「大于大于」。
缓存目录里 mp3 数远大于 .txt 指纹数，就是这种情况的信号。

用法：
  python3 scan_tts_cache.py youtube_dub/<job>/<prefix>__双语分段.json \\
      --seg-dir youtube_dub/<job>/seg_full --rules youtube_dub/<video_id>__speaker_rules.json \\
      --voices '{"host":"<voice_id>","main":"<voice_id>"}' --speed 0.82 [--label full]

不传 --voices 时只做旧缓存/标记/时长检查，不校验指纹是否与当前译文一致。
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
from pathlib import Path

from tts_cache import _fingerprint
from tts_minimax import clean_for_tts


def _duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _speaker_for(start: float, rules: list[dict], default: str) -> str:
    for rule in rules:
        if rule["start"] <= start < rule["end"]:
            return rule["speaker"]
    return default


def _ranges(idx: list[int]) -> str:
    out: list[list[int]] = []
    for x in idx:
        if out and x == out[-1][1] + 1:
            out[-1][1] = x
        else:
            out.append([x, x])
    return ", ".join(f"#{a}" if a == b else f"#{a}–#{b}" for a, b in out)


def main() -> int:
    ap = argparse.ArgumentParser(description="体检 TTS 分段缓存")
    ap.add_argument("bilingual_json", type=Path)
    ap.add_argument("--seg-dir", type=Path, required=True)
    ap.add_argument("--rules", type=Path, help="speaker_rules.json；单声线可不传")
    ap.add_argument("--voices", help='JSON：speaker -> voice_id；传了才校验指纹')
    ap.add_argument("--speed", type=float, default=0.82)
    ap.add_argument("--label", default=None, help="seg 文件名里的 label；默认从目录名 seg_<label> 推断")
    ap.add_argument("--slow-rate", type=float, default=2.0, help="汉字/秒低于此值视为疑似复读或拖长")
    args = ap.parse_args()

    segs = json.loads(args.bilingual_json.read_text(encoding="utf-8"))
    rules = json.loads(args.rules.read_text(encoding="utf-8")) if args.rules else []
    voices = json.loads(args.voices) if args.voices else {}
    default_speaker = next(iter(voices)) if voices else (rules[0]["speaker"] if rules else "")
    label = args.label or args.seg_dir.name.removeprefix("seg_")
    stem = args.bilingual_json.stem

    legacy, marks_spoken, slow, mismatch, missing = [], [], [], [], []
    rates = []
    for i, seg in enumerate(segs):
        speaker = _speaker_for(float(seg.get("start", 0)), rules, default_speaker)
        mp3 = args.seg_dir / f"{stem}__{label}__{speaker}__seg_{i:04d}.mp3"
        if not mp3.exists():
            cands = list(args.seg_dir.glob(f"*seg_{i:04d}.mp3"))
            if not cands:
                missing.append(i + 1)
                continue
            mp3 = cands[0]
        side = mp3.with_suffix(".txt")
        raw = seg.get("text_zh", "")
        cleaned = clean_for_tts(raw)
        is_legacy = not side.exists()
        if is_legacy:
            legacy.append(i + 1)
            if re.sub(r"\s+", " ", raw).strip() != cleaned:
                marks_spoken.append(i + 1)  # 旧缓存生成时还没有 clean_for_tts，标记被念出
        elif voices:
            voice = voices.get(speaker, voices[default_speaker])
            if side.read_text(encoding="utf-8").strip() != _fingerprint(cleaned, voice=voice, speed=args.speed):
                mismatch.append(i + 1)
        n_cjk = len(re.findall(r"[㐀-鿿]", cleaned))
        dur = _duration(mp3)
        if n_cjk >= 10 and dur > 0:
            rate = n_cjk / dur
            rates.append(rate)
            if n_cjk >= 6 and dur > 4 and rate < args.slow_rate:
                slow.append((i + 1, dur, n_cjk, raw[:40]))

    print(f"分段 {len(segs)}，缓存目录 {args.seg_dir}")
    print(f"- 缺失音频：{len(missing)}" + (f" → {_ranges(missing)}" if missing else ""))
    print(f"- 无指纹旧缓存：{len(legacy)}" + (f" → {_ranges(legacy)}" if legacy else ""))
    print(f"- 旧缓存中会把 >>/[笑声] 等标记念出来的段：{len(marks_spoken)}"
          + (f" → {_ranges(marks_spoken)}" if marks_spoken else ""))
    if voices:
        print(f"- 指纹与当前译文/声线/语速不符：{len(mismatch)}" + (f" → {_ranges(mismatch)}" if mismatch else ""))
    if rates:
        print(f"- 汉字/秒：中位 {statistics.median(rates):.2f}")
    print(f"- 疑似复读/拖长（<{args.slow_rate} 字/秒）：{len(slow)}")
    for i, dur, n, text in slow[:30]:
        print(f"    #{i} {dur:.1f}s/{n}字  {text}")
    problem = bool(missing or legacy or mismatch or slow)
    print("结论：" + ("需要处理，不能直接拼接/发布" if problem else "缓存干净"))
    return 1 if problem else 0


if __name__ == "__main__":
    raise SystemExit(main())
