#!/usr/bin/env python3
"""修「换说法的跨段重复」：前段把后段的内容提前译了，后段又换个说法译一遍。

只重写前段（#i）的译文：给模型看 #i 的英文和前后文，后段译文 #j 原样保留、明确告诉模型
不要再说一遍。改完重新算首尾相似度，仍然重复就重试。只有 #i 一段需要重新配音。

用法：
  python3 fix_dup_pairs.py <双语分段.json> --pair 194 [--pair 287 ...] [--dry-run]

改前自动备份 <json>.before-dupfix-<时间>.json。哪些对是真重复需要先人工确认
（audit_translation.py 的「首尾相似」警告会有误报：原话本身重复、并列句式）。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from llm_openai import call_gpt
from youtube_dub import extract_json


def _cjk(t: str) -> str:
    return re.sub(r"[^㐀-鿿]", "", t)


def _bg(t: str) -> set:
    return {t[k:k + 2] for k in range(len(t) - 1)}


def head_cover(prev_zh: str, next_zh: str) -> float:
    """后段开头至多 40 个汉字的二元组落在前段末尾窗口里的比例（同 audit_translation 的口径）。"""
    head = _cjk(next_zh)[:40]
    if len(head) < 10:
        return 0.0
    H = _bg(head)
    return len(_bg(_cjk(prev_zh)[-int(len(head) * 1.5):]) & H) / max(1, len(H))


def fix_one(segs: list, i: int) -> str:
    """i 为 0 起下标，返回新的 segs[i]['text_zh']。"""
    prev_en = segs[i - 1]["text"] if i > 0 else ""
    prev_zh = segs[i - 1]["text_zh"] if i > 0 else ""
    en, old = segs[i]["text"], segs[i]["text_zh"]
    next_en, next_zh = segs[i + 1]["text"], segs[i + 1]["text_zh"]
    prompt = (
        "你在修一份英译中配音稿。英文是一段连续讲话被机械切开的片段，很多片段在半句处开始或结束。"
        "下面【本段】的旧译文把【下一段】的内容提前译了进去，而【下一段】自己的译文又把那部分说了一遍，"
        "配音时同一个意思会念两遍。\n"
        "请重写【本段】的中文译文：\n"
        "1. 完整、准确地译出【本段英文】的全部内容，不漏信息，口语化、适合朗读；\n"
        "2. 不要包含【下一段英文】的内容——那部分已经由【下一段译文】负责，不要改它；\n"
        "3. 本段英文在半句处结束，译文也可以停在半句，让下一段接着说，衔接要自然；\n"
        "4. 不要重复【上一段译文】已经说过的内容。\n"
        '只返回 JSON：{"zh":"新的本段译文"}\n\n'
        f"【上一段英文】{prev_en}\n【上一段译文】{prev_zh}\n\n"
        f"【本段英文】{en}\n【本段旧译文】{old}\n\n"
        f"【下一段英文】{next_en}\n【下一段译文（不改）】{next_zh}\n"
    )
    last = None
    for attempt in range(1, 4):
        new = str(extract_json(call_gpt(prompt, json_mode=True)).get("zh", "")).strip()
        if old.lstrip().startswith(">>") and not new.startswith(">>"):
            new = ">> " + new
        cover = head_cover(new, next_zh)
        ratio = len(_cjk(new)) / max(1, len(en))
        last = new
        if new and cover < 0.35 and 0.15 <= ratio <= 0.9:
            return new
        print(f"    第{attempt}次结果仍可疑（首尾相似 {cover:.2f}，汉字/英文字符 {ratio:.2f}），重试")
    print("    ⚠️ 3 次都没达标，保留最后一次结果，请人工看")
    return last


def main() -> None:
    ap = argparse.ArgumentParser(description="重写提前译入下一段内容的译文")
    ap.add_argument("bilingual_json", type=Path)
    ap.add_argument("--pair", type=int, action="append", required=True, help="前段编号（从 1 开始），可重复")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    segs = json.loads(a.bilingual_json.read_text(encoding="utf-8"))
    for n in a.pair:
        i = n - 1
        old = segs[i]["text_zh"]
        print(f"#{n}→#{n + 1}  改前首尾相似 {head_cover(old, segs[i + 1]['text_zh']):.2f}")
        new = fix_one(segs, i)
        print(f"  旧：{old}\n  新：{new}\n  下：{segs[i + 1]['text_zh']}\n  改后首尾相似 {head_cover(new, segs[i + 1]['text_zh']):.2f}")
        segs[i]["text_zh"] = new
    if a.dry_run:
        print("（--dry-run：未写入）"); return
    bak = a.bilingual_json.with_name(a.bilingual_json.stem + f".before-dupfix-{datetime.now():%Y%m%d-%H%M%S}.json")
    shutil.copy2(a.bilingual_json, bak)
    a.bilingual_json.write_text(json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ 已写入（备份 {bak.name}）")


if __name__ == "__main__":
    main()
