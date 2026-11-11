#!/usr/bin/env python3
"""用 pyannote 声纹分离复核/修正说话人规则（speaker_rules.json）。

背景（2026-11-11）：`build_speaker_rules.py` 只读字幕文字判断谁在说话，长段落里的一来一回
容易整体判反；pyannote 听声音，长段落很准，但会把夹在长段中间的两三秒短问句吞进旁边的人。
所以分工是：**长段落（默认 ≥5 秒、声纹纯度 ≥0.9）听 pyannote，问句和插话沿用文字规则**。
`P06RgnUKX_I` 用这套方法后，规则与 pyannote 在长段上的一致率从 77.6% 提到 93.1%。

模型：ModelScope 上 pyannote 官方组织发布的 `speaker-diarization-community-1`（免登录，
文件与 HuggingFace 官方逐字节一致），放在 MODEL_DIR。本机 torchcodec 不可用，所以音频先用
ffmpeg 转 16k 单声道 wav，再以内存波形传入。

用法（VideoLingo/.venv）：
  # 1. 跑分离（约为音频时长的 1/8），输出说话人轮次
  "$VENV_PY" diarize_pyannote.py run <video_id> --num-speakers 2
  # 2. 用确定无疑的时间段把聚类编号映射到 speaker 标签，并给出建议修改（不写文件）
  "$VENV_PY" diarize_pyannote.py apply <video_id> --ref host=2812.8-2856.5 --ref main=2857.2-2946
  # 3. 确认建议后加 --write 覆盖 speaker_rules.json（自动备份原文件）
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
TRANS_DIR = HERE / "youtube_transcripts"
OUT_ROOT = HERE / "youtube_dub"
MODEL_DIR = Path.home() / ".cache/modelscope/pyannote/speaker-diarization-community-1"
INTERJ = re.compile(r"^(>>\s*)?(\[laughter\]|\[笑声\]|mhm\.?|yeah\.?( yeah\.?)?|right\.?|yep\.?|uh-huh\.?)$", re.I)


def turns_path(video_id: str) -> Path:
    return OUT_ROOT / f"{video_id}__pyannote_community1.json"


def rules_path(video_id: str) -> Path:
    return OUT_ROOT / f"{video_id}__speaker_rules.json"


def run(video_id: str, num_speakers: int | None) -> None:
    import soundfile as sf
    import torch
    from pyannote.audio import Pipeline

    src = TRANS_DIR / "_audio" / f"{video_id}.mp3"
    if not MODEL_DIR.exists():
        raise SystemExit(f"✗ 模型不存在：{MODEL_DIR}（见 PROGRESS.md 2026-11-11 的下载说明）")
    pipe = Pipeline.from_pretrained(str(MODEL_DIR))
    if torch.backends.mps.is_available():
        pipe.to(torch.device("mps"))
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(wav)], check=True)
        y, sr = sf.read(wav, dtype="float32")
    kwargs = {"num_speakers": num_speakers} if num_speakers else {}
    res = pipe({"waveform": torch.from_numpy(y).unsqueeze(0), "sample_rate": sr}, **kwargs)
    ann = getattr(res, "exclusive_speaker_diarization", None) or getattr(res, "speaker_diarization", res)
    turns = [{"start": round(s.start, 3), "end": round(s.end, 3), "speaker": k}
             for s, _, k in ann.itertracks(yield_label=True)]
    turns_path(video_id).write_text(json.dumps(turns, ensure_ascii=False), encoding="utf-8")
    print(f"✓ {len(turns)} 段，聚类 {sorted({t['speaker'] for t in turns})} → {turns_path(video_id)}")


def _overlap_label(turns: list, a: float, b: float, mapping: dict) -> tuple[str | None, float]:
    acc: dict[str, float] = defaultdict(float)
    for t in turns:
        o = min(b, t["end"]) - max(a, t["start"])
        if o > 0 and t["speaker"] in mapping:
            acc[mapping[t["speaker"]]] += o
    if not acc:
        return None, 0.0
    lab, ov = max(acc.items(), key=lambda kv: kv[1])
    return lab, ov / sum(acc.values())


def apply(video_id: str, refs: list[str], min_dur: float, min_purity: float, write: bool) -> None:
    turns = json.loads(turns_path(video_id).read_text(encoding="utf-8"))
    segs = json.loads((TRANS_DIR / f"{video_id}.json").read_text(encoding="utf-8"))
    rules = json.loads(rules_path(video_id).read_text(encoding="utf-8"))
    spk = lambda t: next((r["speaker"] for r in rules if r["start"] <= t < r["end"]), rules[0]["speaker"])

    votes: dict[str, Counter] = defaultdict(Counter)
    for ref in refs:
        label, span = ref.split("=", 1)
        a, b = (float(x) for x in span.split("-"))
        for t in turns:
            o = min(b, t["end"]) - max(a, t["start"])
            if o > 0:
                votes[t["speaker"]][label] += o
    mapping = {c: v.most_common(1)[0][0] for c, v in votes.items()}
    if len(set(mapping.values())) < len(set(r.split("=")[0] for r in refs)):
        raise SystemExit(f"✗ 参照段无法区分聚类：{dict(votes)}；换更长、更确定的参照段")
    print("聚类映射：", mapping)

    labels = [spk(s["start"] + 0.001) for s in segs]
    agree = total = 0
    changes = []
    for i, s in enumerate(segs):
        lab, purity = _overlap_label(turns, s["start"], s["end"], mapping)
        if lab is None:
            continue
        text = s.get("text", "").strip()
        long_pure = (s["end"] - s["start"]) >= min_dur and purity >= min_purity
        if long_pure:
            total += 1
            agree += lab == labels[i]
        if long_pure and lab != labels[i] and not INTERJ.match(text) and not (text.startswith(">>") and text.endswith("?")):
            changes.append((i, labels[i], lab, purity, text))
    print(f"长段（≥{min_dur}s、纯度≥{min_purity}）与当前规则一致：{agree}/{total}")
    print(f"建议修改 {len(changes)} 段（已排除问句与插话，这两类 pyannote 不可靠）：")
    for i, a, b, p, t in changes:
        print(f"  #{i + 1} {segs[i]['start']:.1f}s {a}->{b} 纯度{p:.2f} | {t[:90]}")
    if not write:
        print("（预览模式，未写文件；人工看过上面每一条后再加 --write）")
        return
    for i, _, b, _, _ in changes:
        labels[i] = b
        # 紧跟其后、没有 >> 的半句是同一个人说完的
        j = i + 1
        while j < len(segs) and not segs[j].get("text", "").lstrip().startswith(">>"):
            labels[j] = b
            j += 1
    out = []
    for i, (s, lab) in enumerate(zip(segs, labels)):
        end = segs[i + 1]["start"] if i + 1 < len(segs) else s["end"]
        if out and out[-1]["speaker"] == lab:
            out[-1]["end"] = end
        else:
            out.append({"start": s["start"], "end": end, "speaker": lab})
    out[0]["start"] = 0.0
    backup = rules_path(video_id).with_suffix(f".before-pyannote-{datetime.now():%Y%m%d-%H%M%S}.json")
    shutil.copy2(rules_path(video_id), backup)
    rules_path(video_id).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 已写入 {rules_path(video_id)}（备份 {backup.name}）；重跑 youtube_multivoice_dub.py 只会重合成换了声线的段")


def main() -> None:
    ap = argparse.ArgumentParser(description="pyannote 声纹分离复核说话人规则")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("video_id")
    r.add_argument("--num-speakers", type=int)
    a = sub.add_parser("apply")
    a.add_argument("video_id")
    a.add_argument("--ref", action="append", required=True, help="label=开始秒-结束秒，用内容上确定无疑的段落，每人至少一段")
    a.add_argument("--min-dur", type=float, default=5.0)
    a.add_argument("--min-purity", type=float, default=0.9)
    a.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.cmd == "run":
        run(args.video_id, args.num_speakers)
    else:
        apply(args.video_id, args.ref, args.min_dur, args.min_purity, args.write)


if __name__ == "__main__":
    main()
