"""
Multi-voice Chinese dubbing for already translated YouTube episodes.

This keeps the existing translation/SRT workflow intact, but lets one episode
route different time ranges to different voices.

--provider 选 TTS 供应商：minimax（默认，历史集数都是它生成的）或 cosyvoice
（阿里云百炼，声音复刻免费+合成2元/万字符，成本低得多）。两家的 voice_id 格式和
克隆流程都不一样，**同一集不要混用**，否则一集里前后声音会不一致。
"""
import argparse
import json
import time
from pathlib import Path

from tts_minimax import synthesize as synthesize_minimax
from tts_minimax import _concat, _make_silence, clean_for_tts
from tts_cache import cache_hit, mark_synthesized


def _get_synthesize(provider: str):
    if provider == "minimax":
        return synthesize_minimax
    if provider == "cosyvoice":
        from tts_cosyvoice import synthesize as synthesize_cosyvoice  # 延迟导入，没装 dashscope 也能跑 minimax
        return synthesize_cosyvoice
    raise SystemExit(f"✗ 未知 provider：{provider}")


HERE = Path(__file__).parent
OUT_ROOT = HERE / "youtube_dub"


def _synthesize_with_retry(synthesize, text: str, out: Path, *, voice: str, speed: float, attempts: int = 3):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            synthesize(text, out, voice=voice, speed=speed)
            return
        except Exception as e:
            last_error = e
            if out.exists() and out.stat().st_size < 5000:
                out.unlink()
            if attempt < attempts:
                wait = attempt * 5
                print(f"  TTS retry {attempt}/{attempts - 1}: {e}; wait {wait}s")
                time.sleep(wait)
    raise last_error


def _speaker_for(start: float, rules: list[dict], default_speaker: str) -> str:
    for rule in rules:
        if rule["start"] <= start < rule["end"]:
            return rule["speaker"]
    return default_speaker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bilingual_json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--voices", required=True,
                     help='JSON object mapping speaker label -> voice_id, '
                          'e.g. \'{"host":"...","main":"..."}\'; supports any number of speakers')
    ap.add_argument("--rules", required=True, help="JSON list of {start,end,speaker}")
    ap.add_argument("--label", default="multivoice")
    ap.add_argument("--provider", default="minimax", choices=["minimax", "cosyvoice"],
                    help="TTS 供应商；同一集不要中途换，会导致前后声音不一致")
    ap.add_argument("--limit-seconds", type=float, default=0,
                    help="只合成到原视频这个时间点为止（做试听小样用，0=全片）")
    ap.add_argument("--ai-notice", default="",
                    help="开头的 AI 合成语音提示文本（《人工智能生成合成内容标识办法》要求音频含语音提示）")
    ap.add_argument("--notice-voice", default="longanwen_v3", help="AI 提示所用音色（与节目里的声音区分开）")
    ap.add_argument("--trust-legacy-cache", action="store_true",
                    help="没有 .txt 指纹的旧缓存也直接复用（默认不复用，会重新合成）")
    args = ap.parse_args()

    bilingual_path = Path(args.bilingual_json)
    segments = json.loads(bilingual_path.read_text(encoding="utf-8"))
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))
    voices = json.loads(args.voices)
    if not voices:
        raise SystemExit("✗ --voices 不能为空")
    default_speaker = next(iter(voices))
    synthesize = _get_synthesize(args.provider)

    if args.limit_seconds:
        segments = [s for s in segments if float(s.get("start", 0)) < args.limit_seconds]
        print(f"⚠️ 试听模式：只合成前 {args.limit_seconds:.0f} 秒（{len(segments)} 段）")

    seg_dir = bilingual_path.parent / f"seg_{args.label}"
    seg_dir.mkdir(exist_ok=True)

    paths = []
    for i, seg in enumerate(segments):
        speaker = _speaker_for(float(seg.get("start", 0)), rules, default_speaker)
        voice = voices.get(speaker, voices[default_speaker])
        out = seg_dir / f"{bilingual_path.stem}__{args.label}__{speaker}__seg_{i:04d}.mp3"
        paths.append(out)

        text = clean_for_tts(seg.get("text_zh", ""))
        hit, why = cache_hit(out, text, voice=voice, speed=args.speed,
                             trust_legacy=args.trust_legacy_cache)
        if hit:
            print(f"  [{i + 1}/{len(segments)}] cached {speaker}/{voice}")
            continue
        if why:
            print(f"  [{i + 1}/{len(segments)}] 缓存失效（{why}），重新合成")

        if not text:
            _make_silence(out)
            mark_synthesized(out, text, voice=voice, speed=args.speed)
            print(f"  [{i + 1}/{len(segments)}] silence")
            continue

        _synthesize_with_retry(synthesize, text, out, voice=voice, speed=args.speed)
        mark_synthesized(out, text, voice=voice, speed=args.speed)
        print(f"  [{i + 1}/{len(segments)}] {speaker}/{voice}")

    lead = []
    if args.ai_notice:
        nsyn = _get_synthesize("cosyvoice") if args.provider != "minimax" else synthesize
        nout = seg_dir / f"{bilingual_path.stem}__{args.label}__ai_notice.mp3"
        hit, _ = cache_hit(nout, args.ai_notice, voice=args.notice_voice, speed=1.0)
        if not hit:
            _synthesize_with_retry(nsyn, args.ai_notice, nout, voice=args.notice_voice, speed=1.0)
            mark_synthesized(nout, args.ai_notice, voice=args.notice_voice, speed=1.0)
        gap = seg_dir / "_gap_0.8s.mp3"
        if not gap.exists():
            import subprocess
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                            "-t", "0.8", "-acodec", "libmp3lame", "-q:a", "2", str(gap)], check=True)
        lead = [nout, gap]
        print(f"  AI 提示：{args.ai_notice}")

    _concat(lead + paths, Path(args.out))
    _write_dubbed_srt(lead, paths, segments, Path(args.out), args.ai_notice)
    print(f"done: {args.out}")


def _write_dubbed_srt(lead, paths, segments, out_mp3: Path, notice: str):
    """按成品音频的真实时间写中文字幕。

    旧做法 write_srt() 用的是英文原视频的时间轴，中文配音长短不同，越往后偏得越多
    （P06RgnUKX_I：字幕最后一条在 55:48，音频却有 67:54）。这里用每个分段文件的实测时长
    累加，并按成品总时长线性校正 MP3 帧填充带来的累计误差。
    """
    from tts_minimax import _probe_duration
    files = list(lead) + list(paths)
    durs = [_probe_duration(p) for p in files]
    total = _probe_duration(out_mp3)
    scale = total / sum(durs) if sum(durs) else 1.0
    def fmt(t):
        ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s_, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s_:02d},{ms:03d}"
    cues, t = [], 0.0
    texts = ([notice, None] if lead else []) + [clean_for_tts(s.get("text_zh", "")) for s in segments]
    for text, d in zip(texts, durs):
        d *= scale
        if text:
            cues.append((t, t + d, text))
        t += d
    lines = []
    for i, (a, b, text) in enumerate(cues, 1):
        lines += [str(i), f"{fmt(a)} --> {fmt(b)}", text, ""]
    srt = out_mp3.with_suffix(".srt")
    srt.write_text("\n".join(lines), encoding="utf-8")
    print(f"字幕（按配音实际时间）：{srt}，{len(cues)} 条，校正系数 {scale:.4f}")


if __name__ == "__main__":
    main()
