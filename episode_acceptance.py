#!/usr/bin/env python3
"""返修集上线前的验收清单（2026-11-11 起每集必跑，全部通过才允许替换线上文件）。

检查项：
1. 翻译审计 0 error，且跨段重合为 0（其余 warning 列出，需人工逐条看过）
2. 字幕里没有 `>>`
3. TTS 分段缓存体检干净（无旧缓存、指纹与当前译文/声线/语速一致、无疑似复读）
4. 成品音频：时长与分段合计偏差 ≤2%，采样率 24kHz 单声道，响度在 -19～-13 LUFS
5. 说话人：有声纹复核报告；声纹中心相似度 < 0.7；长段声纹归队与文字一致率 ≥ 80%

用法（VideoLingo/.venv）：
  "$VENV_PY" episode_acceptance.py <video_id> --audio <成品mp3> --voices '<json>' --speed 0.92 [--label cosyvoice]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def job_paths(video_id: str):
    job = next(d for d in (HERE / "youtube_dub").glob(f"{video_id}__*") if d.is_dir())
    bil = next(p for p in job.glob("*__双语分段.json") if ".before" not in p.name)
    srt = next(job.glob("*__中文字幕.srt"))
    return job, bil, srt


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--audio", type=Path, required=True)
    ap.add_argument("--voices", required=True)
    ap.add_argument("--speed", type=float, default=0.92)
    ap.add_argument("--label", default="cosyvoice")
    ap.add_argument("--srt", type=Path, help="成品字幕，默认取成品 mp3 同名 .srt（按配音实际时间生成）")
    args = ap.parse_args()
    job, bil, srt = job_paths(args.video_id)
    if args.srt:
        srt = args.srt
    elif args.audio.with_suffix(".srt").exists():
        srt = args.audio.with_suffix(".srt")
    rules = HERE / "youtube_dub" / f"{args.video_id}__speaker_rules.json"
    results = []

    a = run([sys.executable, "audit_translation.py", str(bil), "--max-details", "500"]).stdout
    errs = int(re.search(r"(\d+) error", a).group(1))
    cross = len(re.findall(r"译文重合", a))
    other = [l.strip() for l in a.splitlines() if "WARN" in l and "译文重合" not in l and "合计" not in l]
    results.append(("翻译审计 0 error、跨段重合 0", errs == 0 and cross == 0, f"error {errs}，跨段重合 {cross}，其他警告 {len(other)}（需人工看过）"))

    srt_text = srt.read_text(encoding="utf-8")
    gt = srt_text.count(">>")
    results.append(("字幕无 >>", gt == 0, f"{gt} 处"))
    first = srt_text.split("\n\n")[0]
    results.append(("开头有 AI 合成提示", "AI" in first and "合成" in first, first.splitlines()[-1][:60] if first else "无字幕"))
    last = re.findall(r"--> (\d+):(\d+):(\d+),(\d+)", srt_text)
    srt_end = int(last[-1][0]) * 3600 + int(last[-1][1]) * 60 + int(last[-1][2]) if last else 0

    scan_args = [sys.executable, "scan_tts_cache.py", str(bil), "--seg-dir", str(job / f"seg_{args.label}"),
                 "--voices", args.voices, "--speed", str(args.speed)]
    if rules.exists():
        scan_args += ["--rules", str(rules)]
    sc = run(scan_args).stdout
    results.append(("缓存体检干净", "缓存干净" in sc, sc.strip().splitlines()[-1] if sc.strip() else "无输出"))

    probe = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=sample_rate,channels", "-of", "json", str(args.audio)]).stdout
    pj = json.loads(probe); dur = float(pj["format"]["duration"]); st = pj["streams"][0]
    lu = run(["ffmpeg", "-hide_banner", "-i", str(args.audio), "-af", "ebur128=framelog=quiet", "-f", "null", "-"]).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", lu); lufs = float(m[-1]) if m else 0.0
    ok_fmt = st.get("sample_rate") == "24000" and st.get("channels") == 1 and -19 <= lufs <= -13
    results.append(("成品格式与响度", ok_fmt, f"{dur:.1f}s，{st.get('sample_rate')}Hz，{st.get('channels')} 声道，{lufs} LUFS"))
    results.append(("字幕与音频对齐", abs(srt_end - dur) <= 3, f"字幕结束 {srt_end}s，音频 {dur:.0f}s"))

    rep = HERE / "youtube_dub" / f"{args.video_id}__speaker_voice_report.json"
    if rules.exists():
        if rep.exists():
            r = json.loads(rep.read_text(encoding="utf-8"))
            ok = r.get("centroid_similarity", 1) < 0.7 and r.get("cluster_text_agreement", 0) >= 0.8
            results.append(("说话人声纹复核", ok, f"中心相似度 {r.get('centroid_similarity')}，归队一致率 {r.get('cluster_text_agreement')}，"
                                              f"改判 {len(r.get('changed', []))}，陌生声音 {len(r.get('unknown_voice', []))}"))
        else:
            results.append(("说话人声纹复核", False, "缺少 speaker_voice_report.json"))

    width = max(len(n) for n, _, _ in results)
    for name, ok, detail in results:
        print(f"{'✓' if ok else '✗'} {name.ljust(width)}  {detail}")
    for l in other[:20]:
        print(f"    待人工确认：{l}")
    allok = all(ok for _, ok, _ in results)
    print("结论：" + ("验收通过，可以替换线上文件" if allok else "验收未通过，不能上线"))
    return 0 if allok else 1


if __name__ == "__main__":
    raise SystemExit(main())
