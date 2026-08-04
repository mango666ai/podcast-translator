"""
用 LLM 做双人对话的说话人轮次标注（文本判断，不碰音频，不需要任何音频模型/HF token）。

背景：youtube_multivoice_dub.py 只需要「时间段 → speaker 标签」就能合成多声线音频，
不需要真的分析原始音频声纹。字幕里 YouTube 自动生成的 `>>` 就是说话人切换的边界，
把它切成一轮一轮的发言，丢给 DeepSeek 按对话内容判断这轮是主持人还是嘉宾即可。

用法（用 VideoLingo/.venv 的 python3.11 跑）：
  "$VENV_PY" build_speaker_rules.py <video_id> \
      --host-name "Lenny" --guest-name "Andrew Ambrosino" \
      --host-label host --guest-label main \
      --out youtube_dub/<prefix>/<video_id>__speaker_rules.json
"""
import argparse
import json
from pathlib import Path

from llm_openai import call_gpt

HERE = Path(__file__).parent
TRANS_DIR = HERE / "youtube_transcripts"


def group_turns(segs: list) -> list:
    turns = []
    cur = None
    for s in segs:
        text = s.get("text", "")
        is_new = text.startswith(">>") or cur is None
        if is_new:
            if cur:
                turns.append(cur)
            cur = {"start": s["start"], "end": s["end"], "text": text.lstrip(">").strip()}
        else:
            cur["text"] = (cur["text"] + " " + text).strip()
            cur["end"] = s["end"]
    if cur:
        turns.append(cur)
    return turns


def label_turns(turns: list, host_name: str, guest_name: str) -> dict:
    lines = "\n".join(f"[{i}] {t['text'][:200]}" for i, t in enumerate(turns))
    prompt = (
        f"下面是一段播客对话按发言轮次切分的文本，主持人是 {host_name}，嘉宾是 {guest_name}。\n"
        f"请按顺序判断每一轮是谁在说话，只看对话内容和上下文逻辑（谁在提问、谁在讲自己的经历/工作）。\n"
        f"按序号一一对应，**只**返回 JSON（无其他文字）：\n"
        f'```json\n{{"turns":[{{"i":0,"speaker":"host"}}]}}\n```\n'
        f"speaker 只能是 \"host\" 或 \"guest\" 两种取值。\n\n"
        f"对话：\n{lines}"
    )
    for attempt in range(1, 4):
        try:
            text = call_gpt(prompt, json_mode=True)
            m_start = text.find("{")
            m_end = text.rfind("}")
            data = json.loads(text[m_start:m_end + 1])
            result = {}
            for k, d in enumerate(data.get("turns", [])):
                try:
                    idx = int(d.get("i", k))
                except (TypeError, ValueError):
                    idx = k
                result[idx] = d.get("speaker", "guest")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == 3:
                raise
            print(f"  ⚠️ 说话人标注解析失败(第{attempt}次)：{e}，重试")


def merge_rules(turns: list, labels: dict, host_label: str, guest_label: str) -> list:
    # 相邻轮次原始时间戳可能重叠（YouTube 滚动字幕特性），裁掉重叠部分避免
    # _speaker_for 按时间点查找规则时命中错误的说话人。
    capped = []
    for i, t in enumerate(turns):
        end = t["end"]
        if i + 1 < len(turns):
            end = min(end, turns[i + 1]["start"])
        capped.append({**t, "end": end})

    rules = []
    for i, t in enumerate(capped):
        speaker = host_label if labels.get(i, "guest") == "host" else guest_label
        if rules and rules[-1]["speaker"] == speaker and t["start"] - rules[-1]["end"] < 2.0:
            rules[-1]["end"] = t["end"]
        else:
            rules.append({"start": t["start"], "end": t["end"], "speaker": speaker})
    return rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--host-name", required=True)
    ap.add_argument("--guest-name", required=True)
    ap.add_argument("--host-label", default="host")
    ap.add_argument("--guest-label", default="main")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    tj = TRANS_DIR / f"{args.video_id}.json"
    segs = json.loads(tj.read_text(encoding="utf-8"))
    turns = group_turns(segs)
    print(f"共 {len(turns)} 轮发言，标注中…")
    labels = label_turns(turns, args.host_name, args.guest_name)
    rules = merge_rules(turns, labels, args.host_label, args.guest_label)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {len(rules)} 条规则 → {out}")
    for r in rules[:10]:
        print(f"  [{r['start']:.1f}-{r['end']:.1f}] {r['speaker']}")


if __name__ == "__main__":
    main()
