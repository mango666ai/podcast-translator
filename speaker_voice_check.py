#!/usr/bin/env python3
"""用声纹逐段复核说话人规则（build_speaker_rules.py 默认最后一步调用）。

为什么需要：`build_speaker_rules.py` 只读字幕文字判断谁在说话，一来一回的长对话容易整段判反
（2026-11-11 `P06RgnUKX_I` 实测 9 月规则 94/479 段声线错配）。pyannote 整集分离在长段上准，
却会把夹在长段中间两三秒的短问句并进旁边的人。这里换一种做法，逐段直接听声音：

1. faster-whisper（本机缓存的 small 模型）重新转写原音频，拿到每个词的精确时间；把 YouTube
   字幕分段对齐到这些词上，得到每段真实的说话时间窗。YouTube 字幕段的时间互相重叠、
   偏前偏后，直接拿来截音频会混进别人的声音。
2. pyannote community-1 自带的声纹模型（WeSpeaker ResNet34）给每段时间窗提一个声纹向量。
3. 用文字规则当起点算每个人的声纹中心：先按文字标签对长段（≥3 秒）声纹取平均，再反复
   "按声纹重新归队 → 重算平均"直到稳定（文字规则只要大体正确，起点就偏不远）。不需要人工挑
   参照段。最早试过盲目层次聚类，会把 327 段分成一组、2 段离群值分成另一组，完全没按人分。
4. 每段与各中心比相似度：领先第二名足够多（margin）就采用声纹结论，否则保留文字判断。
5. 一两个词的插话（Mhm/Yeah）时间窗太短，声纹判断不了。两人对话时，字幕里以 `>>` 开头
   就表示换了人说话，所以这类段定为"和相邻有把握段相反的那个人"：优先看上一段（插话通常
   是在回应上一句），上一段没把握或是陌生声音时才看下一段（下一段也须以 `>>` 开头）。
   比让 LLM 猜稳定，LLM 每次跑结果都不一样（P06 两次运行在 25 个插话上互相矛盾）。
   注意 YouTube 的 `>>` 本身约有 9% 标错（停顿处误插），所以有声纹的段一律以声纹为准，
   换人规则只用于声纹判断不了的短插话。
6. 和所有人声纹都不像的段（如 YC 招生口播，相似度只有 0.06/0.14）标为"陌生声音"写进报告，
   声线保留文字判断，也不拿它当插话的参照。

模型：`~/.cache/modelscope/pyannote/speaker-diarization-community-1`（ModelScope 免登录下载，
见 PROGRESS.md 2026-11-11）。本机 torchcodec 不可用，音频以内存波形传入。

独立用法（VideoLingo/.venv）：
  "$VENV_PY" speaker_voice_check.py <video_id> --rules youtube_dub/<id>__speaker_rules.json [--write]
不加 --write 只出报告。
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).parent
TRANS_DIR = HERE / "youtube_transcripts"
OUT_ROOT = HERE / "youtube_dub"
EMB_MODEL = Path.home() / ".cache/modelscope/pyannote/speaker-diarization-community-1/embedding"
MIN_SPAN = 0.8      # 秒；对齐后的时间窗短于此不做声纹判断
LONG_SPAN = 3.0     # 秒；用于聚类/算中心的长段
MARGIN = 0.15       # 余弦相似度领先第二名至少这么多才推翻文字判断
UNKNOWN_SIM = 0.3   # 和所有人都低于此相似度：不是这几个人（如节目里插播的口播广告），保留文字判断并报出来


def _norm_tokens(text: str) -> list[str]:
    text = re.sub(r"\[[^\]]*\]", " ", text.replace(">>", " "))
    return re.findall(r"[a-z0-9']+", text.lower())


def _speaker_at(rules: list[dict], t: float, default: str) -> str:
    for r in rules:
        if r["start"] <= t < r["end"]:
            return r["speaker"]
    return default


def find_audio(video_id: str) -> Path:
    """原音频：新集在 youtube_transcripts/_audio/，2026-08 前的早期集在 youtube_demo/_audio/。"""
    for d in (TRANS_DIR / "_audio", HERE / "youtube_demo" / "_audio"):
        for ext in (".mp3", ".m4a", ".webm", ".wav"):
            if (d / f"{video_id}{ext}").exists():
                return d / f"{video_id}{ext}"
    return TRANS_DIR / "_audio" / f"{video_id}.mp3"


def load_audio(audio: Path):
    import soundfile as sf
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "a.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio), "-ac", "1", "-ar", "16000", str(wav)], check=True)
        y, sr = sf.read(wav, dtype="float32")
    return y, sr


def whisper_words(video_id: str, y, sr) -> list[dict]:
    cache = OUT_ROOT / f"{video_id}__whisper_words.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    from faster_whisper import WhisperModel
    print("  转写词级时间（faster-whisper small，约为音频时长的 1/6）…")
    model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
    segs, _ = model.transcribe(y, language="en", word_timestamps=True, vad_filter=True, beam_size=1)
    words = [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in (s.words or [])]
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
    return words


def align_spans(segments: list[dict], words: list[dict]) -> list[tuple[float, float] | None]:
    """把字幕分段对齐到 whisper 词序列，返回每段真实说话的 (开始, 结束)；对不上的段为 None。"""
    seg_tok, owner = [], []
    for i, s in enumerate(segments):
        for t in _norm_tokens(s.get("text", "")):
            seg_tok.append(t)
            owner.append(i)
    w_tok, w_idx = [], []
    for j, w in enumerate(words):
        for t in _norm_tokens(w["w"]):
            w_tok.append(t)
            w_idx.append(j)
    spans: list[list[float] | None] = [None] * len(segments)
    sm = SequenceMatcher(None, seg_tok, w_tok, autojunk=False)
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            i, w = owner[a + k], words[w_idx[b + k]]
            if spans[i] is None:
                spans[i] = [w["s"], w["e"]]
            else:
                spans[i][0] = min(spans[i][0], w["s"])
                spans[i][1] = max(spans[i][1], w["e"])
    return [tuple(s) if s else None for s in spans]


def embed_spans(spans, y, sr):
    import numpy as np
    import torch
    from pyannote.audio import Inference, Model
    model = Model.from_pretrained(str(EMB_MODEL))
    inf = Inference(model, window="whole")
    out = []
    for sp in spans:
        if not sp or sp[1] - sp[0] < MIN_SPAN:
            out.append(None)
            continue
        x = torch.from_numpy(y[int(sp[0] * sr):int(sp[1] * sr)]).unsqueeze(0)
        v = np.asarray(inf({"waveform": x, "sample_rate": sr}), dtype="float64").ravel()
        out.append(v / (np.linalg.norm(v) + 1e-9))
    return out


def voice_check(video_id: str, rules: list[dict], *, segments: list[dict] | None = None,
                audio: Path | None = None) -> tuple[list[dict], dict]:
    """→ (声纹修正后的规则, 报告)。规则按字幕分段重新生成，每段一个起点，相邻同人合并。"""
    import numpy as np

    segments = segments or json.loads((TRANS_DIR / f"{video_id}.json").read_text(encoding="utf-8"))
    audio = audio or find_audio(video_id)
    if not EMB_MODEL.exists():
        raise FileNotFoundError(f"声纹模型不存在：{EMB_MODEL}")
    if not audio.exists():
        raise FileNotFoundError(f"原音频不存在：{audio}")
    labels_all = sorted({r["speaker"] for r in rules})
    default = rules[0]["speaker"]
    text_lab = [_speaker_at(rules, s["start"] + 0.001, default) for s in segments]

    y, sr = load_audio(audio)
    words = whisper_words(video_id, y, sr)
    spans = align_spans(segments, words)
    embs = embed_spans(spans, y, sr)

    long_idx = [i for i, e in enumerate(embs) if e is not None and spans[i][1] - spans[i][0] >= LONG_SPAN]
    if len(long_idx) < 10 * len(labels_all):
        raise RuntimeError(f"可用长段太少（{len(long_idx)}），无法可靠估计声纹中心")
    X = np.stack([embs[i] for i in long_idx])

    def _centroids(assign: list[str]) -> dict:
        out = {}
        for lab in labels_all:
            members = [x for x, a in zip(X, assign) if a == lab]
            if len(members) < 3:
                raise RuntimeError(f"{lab} 的长段不足 3 段，无法估计声纹中心")
            c = np.mean(members, axis=0)
            out[lab] = c / np.linalg.norm(c)
        return out

    assign = [text_lab[i] for i in long_idx]
    for _ in range(20):
        centroids = _centroids(assign)
        new_assign = [max(labels_all, key=lambda lab: float(x @ centroids[lab])) for x in X]
        if new_assign == assign:
            break
        assign = new_assign
    centroids = _centroids(assign)
    agreement = sum(1 for a, i in zip(assign, long_idx) if a == text_lab[i]) / len(long_idx)
    centroid_sim = min(float(centroids[a] @ centroids[b]) for a, b in itertools.combinations(labels_all, 2))

    final, changes, uncertain, unknown = list(text_lab), [], [], []
    confident = [False] * len(segments)
    for i, e in enumerate(embs):
        if e is None:
            continue
        sims = sorted(((float(e @ c), lab) for lab, c in centroids.items()), reverse=True)
        margin = sims[0][0] - sims[1][0]
        voice = sims[0][1]
        if sims[0][0] < UNKNOWN_SIM:
            unknown.append({"seg": i + 1, "start": segments[i]["start"], "best_sim": round(sims[0][0], 3),
                            "kept": text_lab[i], "text": segments[i].get("text", "")[:120]})
            continue
        confident[i] = margin >= MARGIN
        if voice != text_lab[i]:
            if margin >= MARGIN:
                final[i] = voice
                changes.append({"seg": i + 1, "start": segments[i]["start"], "from": text_lab[i], "to": voice,
                                "margin": round(margin, 3), "text": segments[i].get("text", "")[:120]})
            else:
                uncertain.append({"seg": i + 1, "start": segments[i]["start"], "text_label": text_lab[i],
                                  "voice": voice, "margin": round(margin, 3), "text": segments[i].get("text", "")[:120]})

    by_turn = []
    if len(labels_all) == 2:
        other = {labels_all[0]: labels_all[1], labels_all[1]: labels_all[0]}
        starts_turn = [s.get("text", "").lstrip().startswith(">>") for s in segments]
        for i in range(1, len(segments)):
            if embs[i] is not None or not starts_turn[i]:
                continue
            if confident[i - 1]:
                want = other[final[i - 1]]
            elif i + 1 < len(segments) and starts_turn[i + 1] and confident[i + 1]:
                want = other[final[i + 1]]
            else:
                continue
            if final[i] != want:
                by_turn.append(i + 1)
            final[i] = want

    new_rules = []
    for i, (s, lab) in enumerate(zip(segments, final)):
        end = segments[i + 1]["start"] if i + 1 < len(segments) else s["end"]
        if new_rules and new_rules[-1]["speaker"] == lab:
            new_rules[-1]["end"] = end
        else:
            new_rules.append({"start": s["start"], "end": end, "speaker": lab})
    new_rules[0]["start"] = 0.0
    judged = sum(1 for e in embs if e is not None)
    report = {
        "video_id": video_id, "segments": len(segments), "voice_judged": judged,
        "long_segments": len(long_idx),
        "cluster_text_agreement": round(agreement, 3),
        "centroid_similarity": round(centroid_sim, 3),
        "changed": changes, "uncertain": uncertain, "interjections_by_turn": by_turn, "unknown_voice": unknown,
        "unaligned": [i + 1 for i, sp in enumerate(spans) if sp is None],
    }
    return new_rules, report


def print_report(report: dict) -> None:
    print(f"  声纹复核：{report['segments']} 段，{report['voice_judged']} 段可做声纹判断；"
          f"长段声纹归队与文字规则一致率 {report['cluster_text_agreement']:.1%}；"
          f"两人声纹中心相似度 {report['centroid_similarity']:.2f}（越低越好区分）")
    print(f"  按声纹改判 {len(report['changed'])} 段，声纹与文字不一致但把握不足 {len(report['uncertain'])} 段（保留文字判断）")
    print(f"  无法做声纹判断的 >> 插话按换人规则定声线 {len(report['interjections_by_turn'])} 段")
    if report["unknown_voice"]:
        print(f"  ⚠️ 和所有说话人都不像的段 {len(report['unknown_voice'])} 个（可能是插播口播/第三人），保留文字判断，请人工确认：")
        for u in report["unknown_voice"]:
            print(f"    #{u['seg']} {u['start']:.1f}s 最高相似度{u['best_sim']:.2f} 暂定{u['kept']} | {u['text'][:70]}")
    for c in report["changed"][:40]:
        print(f"    #{c['seg']} {c['start']:.1f}s {c['from']}->{c['to']} (领先{c['margin']:.2f}) | {c['text'][:80]}")
    if report["cluster_text_agreement"] < 0.6:
        print("  ⚠️ 声纹归队与文字规则一致率很低：可能说话人数不对，或文字规则整体判反，请人工抽查")
    if report["centroid_similarity"] > 0.7:
        print("  ⚠️ 两人声纹中心太接近，声纹区分不可靠，请人工抽查")


def main() -> None:
    ap = argparse.ArgumentParser(description="用声纹逐段复核说话人规则")
    ap.add_argument("video_id")
    ap.add_argument("--rules", type=Path, required=True)
    ap.add_argument("--segments", type=Path, help="字幕分段 JSON，默认 youtube_transcripts/<id>.json")
    ap.add_argument("--audio", type=Path, help="原音频，默认 youtube_transcripts/_audio/<id>.mp3")
    ap.add_argument("--write", action="store_true", help="用修正结果覆盖 --rules（自动备份）")
    args = ap.parse_args()
    rules = json.loads(args.rules.read_text(encoding="utf-8"))
    segments = json.loads(args.segments.read_text(encoding="utf-8")) if args.segments else None
    new_rules, report = voice_check(args.video_id, rules, segments=segments, audio=args.audio)
    print_report(report)
    rep_path = args.rules.with_name(f"{args.video_id}__speaker_voice_report.json")
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  报告 → {rep_path}")
    if args.write:
        backup = args.rules.with_suffix(f".before-voice-{datetime.now():%Y%m%d-%H%M%S}.json")
        shutil.copy2(args.rules, backup)
        args.rules.write_text(json.dumps(new_rules, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ 已写入 {args.rules}（备份 {backup.name}）")


if __name__ == "__main__":
    main()
