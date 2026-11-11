#!/usr/bin/env python3
"""人工改判个别段落的说话人，并按字幕分段重建规则（自动备份）。

用于声纹判断不了、换人规则也会判错的短句，例如课堂里主讲人说的 "Go ahead." / "Last question."
（点学生发言时学生并没出声，字幕却标了 >>）。用法：
  python3 set_speaker.py <video_id> --set 31=instructor --set 79=instructor
段号从 1 开始，与审计/报告里的 #编号一致。
"""
import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--set", action="append", required=True, help="段号=speaker")
    args = ap.parse_args()
    segs = json.loads((HERE / "youtube_transcripts" / f"{args.video_id}.json").read_text(encoding="utf-8"))
    rp = HERE / "youtube_dub" / f"{args.video_id}__speaker_rules.json"
    rules = json.loads(rp.read_text(encoding="utf-8"))
    spk = lambda t: next((r["speaker"] for r in rules if r["start"] <= t < r["end"]), rules[0]["speaker"])
    labels = [spk(s["start"] + 0.001) for s in segs]
    for item in args.set:
        n, who = item.split("=")
        print(f"#{n}: {labels[int(n) - 1]} -> {who} | {segs[int(n) - 1]['text'][:70]}")
        labels[int(n) - 1] = who
    out = []
    for i, (s, lab) in enumerate(zip(segs, labels)):
        end = segs[i + 1]["start"] if i + 1 < len(segs) else s["end"]
        if out and out[-1]["speaker"] == lab:
            out[-1]["end"] = end
        else:
            out.append({"start": s["start"], "end": end, "speaker": lab})
    out[0]["start"] = 0.0
    shutil.copy2(rp, rp.with_suffix(f".before-manual-{datetime.now():%Y%m%d-%H%M%S}.json"))
    rp.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {len(out)} 条规则 → {rp}")


if __name__ == "__main__":
    main()
