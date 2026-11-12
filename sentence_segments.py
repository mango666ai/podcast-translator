"""把转写/字幕事件重新切成「整句」翻译分段。

为什么：字幕事件按时间机械切开，约四成段落在半句处断开（《智能体时代的设计》479 段里
208 段）。DeepSeek 分批逐段翻译时，半句结尾的段落会诱导模型把下一段的内容提前译入，
下一段又照常译一遍，成品里同一句话念两遍。提示词约束 + 事后检测只能拦住一部分，
换说法的重复检测不全。

配音成品不跟原视频逐帧对齐（中文字幕按配音实际时长重新生成），所以分段不需要贴着
字幕事件走，可以只在句末切：
- 说话人切换（`>>`）一定切开，且 `>>` 留在新段开头，供说话人规则和声纹复核使用；
- 段落够长（soft_chars）且到了句末就收尾；
- 加上下一句会超过 max_chars 时，在上一句末尾收尾；
- 单句本身超过 max_chars（无标点的自动字幕、超长连句）才退回按逗号/词数硬切。

时间戳按词在原事件里的位置线性插值，只供定位参考。
"""
from __future__ import annotations

import re

_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "e.g.", "i.e.", "jr.", "sr.", "prof.", "inc.", "no."}
_END_RE = re.compile(r"[.?!][\"'”’)\]]*$")
_CLAUSE_RE = re.compile(r"[,;:—][\"'”’)\]]*$")


def _words(segs: list[dict]) -> list[tuple[str, float, float]]:
    out = []
    for seg in segs:
        toks = (seg.get("text") or "").split()
        if not toks:
            continue
        s, e = float(seg["start"]), float(seg["end"])
        step = (e - s) / len(toks)
        for k, w in enumerate(toks):
            out.append((w, s + step * k, s + step * (k + 1)))
    return out


def _is_sentence_end(word: str, nxt: str | None) -> bool:
    if not _END_RE.search(word) or word.lower() in _ABBREV:
        return False
    if nxt is None or nxt.startswith(">>"):
        return True
    # "U.S. and"、"5.5" 之类：下一个词小写开头就不算句末
    first = nxt.lstrip("\"'“‘([")[:1]
    return not first.islower()


def _sentences(words: list[tuple[str, float, float]]) -> list[list[tuple[str, float, float]]]:
    sents, cur = [], []
    for i, w in enumerate(words):
        if w[0].startswith(">>") and cur:
            sents.append(cur); cur = []
        cur.append(w)
        nxt = words[i + 1][0] if i + 1 < len(words) else None
        if _is_sentence_end(w[0], nxt):
            sents.append(cur); cur = []
    if cur:
        sents.append(cur)
    return sents


def _text(ws) -> str:
    return " ".join(w[0] for w in ws)


def _hard_split(sent, max_chars: int):
    """超长单句：优先在最靠后的逗号类标点处切，没有就按字数切。"""
    pieces, cur = [], []
    for w in sent:
        if cur and len(_text(cur)) + 1 + len(w[0]) > max_chars:
            cut = max((k for k, x in enumerate(cur) if _CLAUSE_RE.search(x[0])), default=None)
            if cut is not None and cut >= len(cur) // 3:
                pieces.append(cur[:cut + 1]); cur = cur[cut + 1:]
            else:
                pieces.append(cur); cur = []
        cur.append(w)
    if cur:
        pieces.append(cur)
    return pieces


def regroup_sentences(segs: list[dict], soft_chars: int = 150, max_chars: int = 260) -> list[dict]:
    units = []
    for sent in _sentences(_words(segs)):
        units.extend(_hard_split(sent, max_chars) if len(_text(sent)) > max_chars else [sent])

    chunks, cur = [], []
    for u in units:
        new_speaker = u[0][0].startswith(">>")
        if cur and (new_speaker or len(_text(cur)) + 1 + len(_text(u)) > max_chars):
            chunks.append(cur); cur = []
        cur = cur + u
        if len(_text(cur)) >= soft_chars:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    out, last = [], 0.0
    for c in chunks:
        # 原字幕事件时间互相重叠，插值后起点可能不晚于上一段。说话人规则按起点查找，
        # 两段起点相同就分不出谁说的，所以钳到严格递增
        start = round(c[0][1], 2) if not out else max(round(c[0][1], 2), round(last + 0.01, 2))
        out.append({"start": start, "end": max(round(c[-1][2], 2), start), "text": _text(c)})
        last = start
    return out


def mid_sentence_count(segs: list[dict]) -> int:
    return sum(1 for s in segs if not _END_RE.search((s.get("text") or "").strip()))


if __name__ == "__main__":
    import argparse, json
    from pathlib import Path
    ap = argparse.ArgumentParser(description="把转写分段重切成整句分段")
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--soft-chars", type=int, default=150)
    ap.add_argument("--max-chars", type=int, default=260)
    a = ap.parse_args()
    raw = json.loads(Path(a.inp).read_text(encoding="utf-8"))
    new = regroup_sentences(raw, a.soft_chars, a.max_chars)
    Path(a.out).write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(raw)} 段（半句断开 {mid_sentence_count(raw)}）→ {len(new)} 段（半句断开 {mid_sentence_count(new)}）")
