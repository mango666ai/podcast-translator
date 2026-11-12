#!/usr/bin/env python3
"""对双语分段做发布前静态审计。

它能抓空译文、时间轴异常、相邻重复、跨段重合（同一句话在相邻两段各译一遍）、
异常扩写和待清理标记；不能证明语义一定对齐，所以通过审计仍不等于可以跳过抽听。
"""

from __future__ import annotations

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


def compact(text: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]", "", text.lower())


def chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u3400-\u9fff]", text))


def cross_segment_overlap(a: str, b: str) -> str:
    """两段译文（已 compact）的最长公共子串。"""
    if not a or not b:
        return ""
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return a[m.a:m.a + m.size]


def audit(path: Path, *, cross_min_chars: int = 12, cross_min_cjk: int = 8) -> tuple[list[str], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return ["顶层必须是分段数组"], []

    errors: list[str] = []
    warnings: list[str] = []
    previous_start = -1.0
    previous_zh = ""
    for index, segment in enumerate(data, 1):
        en = str(segment.get("text", "")).strip()
        zh = str(segment.get("text_zh", "")).strip()
        try:
            start = float(segment["start"])
            end = float(segment["end"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"#{index}: start/end 缺失或不是数字")
            continue
        if end <= start:
            errors.append(f"#{index}: end ({end}) 不大于 start ({start})")
        if start < previous_start:
            errors.append(f"#{index}: start 倒退 ({start} < {previous_start})")
        previous_start = start
        if en and not zh:
            errors.append(f"#{index}: 原文非空但译文为空")
        if zh and compact(zh) == previous_zh and len(compact(zh)) >= 8:
            warnings.append(f"#{index}: 与上一段译文完全重复")
        previous_zh = compact(zh)
        if re.search(r"[A-Za-z0-9-]+\.(com|ai|io|org|net|co|app|dev)\b", zh):
            warnings.append(f"#{index}: 译文含网址，TTS 会逐字母念出（自动字幕常把网址听错），改成口语说法")
        en_letters = len(re.findall(r"[A-Za-z]", en))
        ratio = chinese_chars(zh) / max(en_letters, 1)
        if en_letters >= 12 and ratio > 0.85:
            warnings.append(f"#{index}: 中英长度比异常 ({ratio:.2f})，可能把半句扩写成整段")

    # 跨段重合：DeepSeek 翻译半句时把下一段内容提前译入，下一段再译一遍，成品连念两遍。
    # 相邻完全相同的检查抓不到它（只是大段重合而非整段相同）。阈值比翻译阶段的自动重试
    # （youtube_dub.cross_segment_overlaps，15 字/10 汉字）更松，宁可多报让人看。
    compacted = [compact(str(seg.get("text_zh", ""))) for seg in data]
    total_dup = 0
    for i in range(len(compacted)):
        for k in (i + 1, i + 2):
            if k >= len(compacted):
                break
            shared = cross_segment_overlap(compacted[i], compacted[k])
            if len(shared) >= cross_min_chars and chinese_chars(shared) >= cross_min_cjk:
                total_dup += len(shared)
                warnings.append(f"#{i + 1}↔#{k + 1}: 译文重合 {len(shared)} 字「{shared[:20]}…」，疑似同一句话译了两遍")
    # 换说法的重复：模型把下一段的意思提前译进本段，下一段又换个说法再译一遍，两段字面不同，
    # 跨段重合（最长公共子串）抓不到。比较前段结尾与后段开头各 14 个汉字的二元组 Jaccard 相似度。
    # 2026-11-11 在 zegYJ6dhIg4、tivaWTTVRhY、87DyyMV0kCY、DHH 等集各找到 1–2 处；也会误报（原话本身重复、
    # 并列句式），所以只报警，由人工逐条确认后登记到 <id>__audit_reviewed.json。
    def _bg(t):
        return {t[i:i + 2] for i in range(len(t) - 1)}
    zh_cjk = [re.sub(r"[^\u3400-\u9fff]", "", str(seg.get("text_zh", ""))) for seg in data]
    # 2026-11-12 加宽：提前译入的内容常常不在前段最末尾 14 字，而是前段后半截整句（例：《智能体时代
    # 的设计》#194 把 #195 的「调轻字重、只用三种字号」先说了一遍）。再比一次：后段开头至多 40 个汉字
    # 的二元组，有多少落在前段末尾 1.5 倍长度的窗口里（覆盖率 ≥0.35）。
    for i in range(len(zh_cjk) - 1):
        a, b = zh_cjk[i][-14:], zh_cjk[i + 1][:14]
        sim = 0.0
        if len(a) >= 8 and len(b) >= 8:
            A, B = _bg(a), _bg(b)
            sim = len(A & B) / max(1, len(A | B))
        head = zh_cjk[i + 1][:40]
        cover = 0.0
        if len(head) >= 10:
            H = _bg(head)
            cover = len(_bg(zh_cjk[i][-int(len(head) * 1.5):]) & H) / max(1, len(H))
        if sim >= 0.4 or cover >= 0.35:
            tail = zh_cjk[i][-int(max(len(head), 14) * 1.5):]
            warnings.append(f"#{i + 1}→#{i + 2}: 首尾相似 {max(sim, cover):.2f}「…{tail[-24:]}」/「{head[:24]}…」，疑似换说法把同一句译了两遍")
    if total_dup:
        warnings.append(f"跨段重合合计约 {total_dup} 字（按 4 字/秒估算约 {total_dup / 4 / 60:.1f} 分钟重复朗读）")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="审计双语分段 JSON")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true", help="有警告也返回非零")
    parser.add_argument("--max-details", type=int, default=40, help="每个文件最多显示多少条详情")
    args = parser.parse_args()
    failed = False
    for path in args.paths:
        errors, warnings = audit(path)
        print(f"{path}: {len(errors)} error(s), {len(warnings)} warning(s)")
        for message in errors[:args.max_details]:
            print(f"  ERROR {message}")
        for message in warnings[:args.max_details]:
            print(f"  WARN  {message}")
        hidden = len(errors) + len(warnings) - min(len(errors), args.max_details) - min(len(warnings), args.max_details)
        if hidden:
            print(f"  ... 另有 {hidden} 条未显示（用 --max-details 调整）")
        failed = failed or bool(errors) or (args.strict and bool(warnings))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
