"""
用 LLM 做多人对话的说话人轮次标注（文本判断，不碰音频，不需要任何音频模型/HF token）。

背景：youtube_multivoice_dub.py 只需要「时间段 → speaker 标签」就能合成多声线音频，
不需要真的分析原始音频声纹。字幕里 YouTube 自动生成的 `>>` 就是说话人切换的边界，
把它切成一轮一轮的发言，丢给 DeepSeek 按对话内容判断这轮是谁在说即可。支持任意人数
（2人对话、3人以上的圆桌/访谈都用同一套逻辑）。

用法（用 VideoLingo/.venv 的 python3.11 跑）：
  "$VENV_PY" build_speaker_rules.py <video_id> \
      --speakers '[{"label":"host","name":"Lenny（主持人）"},{"label":"main","name":"Andrew Ambrosino（嘉宾）"}]' \
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


def _preview(text: str, head: int = 300, tail: int = 300) -> str:
    # 长发言轮次（如主持人一段开场白里混了自我介绍+读广告+串场）只看开头
    # 200字很容易漏掉后面才出现的身份线索（"我是主持人XXX"）；开头+结尾各取一段
    # 大幅降低这种漏判概率。
    if len(text) <= head + tail:
        return text
    if tail <= 0:
        return f"{text[:head]}…"
    return f"{text[:head]} …(中间省略)… {text[-tail:]}"


BATCH = 50


def _label_batch(turns: list, speakers: list, offset: int, context: list) -> dict:
    """标注单批（<=BATCH 轮）。3 次仍解析失败就对半拆开递归重试，缩小单次输出量——
    和 youtube_dub._translate_batch 同一套路数。context 是上一批末尾几轮的
    「轮次→speaker」结论，只读，用来保持对话线索不断。"""
    labels = [s["label"] for s in speakers]
    default_label = labels[-1]
    roster = "\n".join(f"- {s['label']}：{s['name']}" for s in speakers)
    lines = "\n".join(f"[{i}] {_preview(t['text'])}" for i, t in enumerate(turns))
    ctx = ""
    if context:
        ctx = "已经判定好的上文（只作参考，不要重复标注）：\n" + "\n".join(
            f"（{spk}）{_preview(txt, 120, 0)}" for spk, txt in context
        ) + "\n\n"
    prompt = (
        f"下面是一段播客对话按发言轮次切分的文本，说话人一共 {len(speakers)} 位：\n{roster}\n"
        f"请按顺序判断每一轮是谁在说话，只看对话内容和上下文逻辑（谁在提问、谁在讲自己的经历/工作、"
        f"被别人怎么称呼/提到）。\n"
        f"本批共 {len(turns)} 轮，序号 0 到 {len(turns) - 1}，必须每一轮都给出结论。\n"
        f"按序号一一对应，**只**返回 JSON（无其他文字）：\n"
        f'```json\n{{"turns":[{{"i":0,"speaker":"{labels[0]}"}}]}}\n```\n'
        f"speaker 只能是这些取值之一：{', '.join(labels)}。\n\n"
        f"{ctx}对话：\n{lines}"
    )
    for attempt in range(1, 4):
        try:
            text = call_gpt(prompt, json_mode=True)
            m_start = text.find("{")
            m_end = text.rfind("}")
            if m_start < 0 or m_end < 0:
                raise ValueError("返回里找不到 JSON（多半是输出被截断）")
            data = json.loads(text[m_start:m_end + 1])
            local = {}
            for k, d in enumerate(data.get("turns", [])):
                try:
                    idx = int(d.get("i", k))
                except (TypeError, ValueError):
                    idx = k
                speaker = d.get("speaker", default_label)
                local[idx] = speaker if speaker in labels else default_label
            missing = [i for i in range(len(turns)) if i not in local]
            if missing:
                raise ValueError(f"缺少轮次 {missing[:8]}{'…' if len(missing) > 8 else ''}")
            return {offset + i: local[i] for i in range(len(turns))}
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            if attempt < 3:
                print(f"  ⚠️ 说话人标注解析失败(第{attempt}次)：{e}，重试")
                continue
            if len(turns) > 1:
                mid = len(turns) // 2
                print(f"  ⚠️ 批次({len(turns)}轮)连续3次失败：{e}，拆成两半分别重试")
                left = _label_batch(turns[:mid], speakers, offset, context)
                right_ctx = [(left[offset + mid - 1], turns[mid - 1]["text"])]
                return {**left, **_label_batch(turns[mid:], speakers, offset + mid, right_ctx)}
            # 单轮还失败：不让整集崩掉，沿用上一轮的说话人并记账
            fallback = context[-1][0] if context else default_label
            print(f"  ⚠️ 第 {offset} 轮标注失败({e})，沿用上一轮 speaker={fallback}")
            FALLBACK_TURNS.append(offset)
            return {offset: fallback}


FALLBACK_TURNS: list = []


def label_turns(turns: list, speakers: list) -> dict:
    """分批标注。原来是把全部轮次塞进一个 prompt——DHH 那集 1008 轮直接把
    DeepSeek 的输出撑到截断，JSON 连续解析失败后整集崩溃退出。"""
    FALLBACK_TURNS.clear()
    result = {}
    context: list = []
    for i in range(0, len(turns), BATCH):
        batch = turns[i:i + BATCH]
        result.update(_label_batch(batch, speakers, i, context))
        context = [(result[j], turns[j]["text"]) for j in range(max(i, i + len(batch) - 3), i + len(batch))]
        print(f"  标注 {min(i + BATCH, len(turns))}/{len(turns)} 轮")
    if FALLBACK_TURNS:
        print(f"  ⚠️ 有 {len(FALLBACK_TURNS)} 轮是兜底沿用上一轮的：{FALLBACK_TURNS[:20]}")
    return result


def merge_rules(turns: list, labels: dict, default_label: str) -> list:
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
        speaker = labels.get(i, default_label)
        if rules and rules[-1]["speaker"] == speaker and t["start"] - rules[-1]["end"] < 2.0:
            rules[-1]["end"] = t["end"]
        else:
            rules.append({"start": t["start"], "end": t["end"], "speaker": speaker})
    return rules


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id")
    ap.add_argument("--speakers", required=True,
                     help='JSON list: [{"label":"host","name":"人名/身份说明"}, ...]，至少2人')
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    speakers = json.loads(args.speakers)
    if len(speakers) < 2:
        raise SystemExit("✗ --speakers 至少需要 2 位说话人")

    tj = TRANS_DIR / f"{args.video_id}.json"
    segs = json.loads(tj.read_text(encoding="utf-8"))
    turns = group_turns(segs)
    print(f"共 {len(turns)} 轮发言，{len(speakers)} 位说话人，标注中…")
    labels = label_turns(turns, speakers)
    rules = merge_rules(turns, labels, speakers[-1]["label"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {len(rules)} 条规则 → {out}")
    for r in rules[:10]:
        print(f"  [{r['start']:.1f}-{r['end']:.1f}] {r['speaker']}")


if __name__ == "__main__":
    main()
