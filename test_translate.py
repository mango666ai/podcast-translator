"""
翻译验证脚本 — 测试 Claude Code headless 的翻译质量和 JSON 解析稳定性

用法：
    python test_translate.py

不需要任何 API key，走本地 claude CLI（Max 订阅）
"""

import subprocess
import json
import re
import sys
import time

# 测试用的英文片段（模拟双人访谈播客，约 3 分钟内容）
TEST_SEGMENTS = [
    {
        "speaker": "SPEAKER_00",
        "text": "Welcome to the Lex Fridman podcast. My guest today is Sam Altman, CEO of OpenAI. Sam, great to have you here."
    },
    {
        "speaker": "SPEAKER_01",
        "text": "Thanks Lex, it's great to be here. I've been looking forward to this conversation for a while."
    },
    {
        "speaker": "SPEAKER_00",
        "text": "Let's start with a big question. What does AGI actually mean to you, and do you think we're close to achieving it?"
    },
    {
        "speaker": "SPEAKER_01",
        "text": "That's a really hard question to answer precisely. I think of AGI as a system that can do basically any cognitive task that a human can do. Are we close? I think we're closer than most people expected even two years ago, but I'm genuinely uncertain about the timeline. It could be years, it could be longer."
    },
    {
        "speaker": "SPEAKER_00",
        "text": "That uncertainty is interesting. Do you think about the risks? The downside scenarios?"
    },
    {
        "speaker": "SPEAKER_01",
        "text": "All the time. I think about it constantly. The thing that worries me most is not the sci-fi robot uprising scenario. It's more subtle things — systems that are misaligned in ways we don't fully understand, or that are used by small groups of people to gain outsized power. Those feel more realistic to me."
    },
]


TRANSLATE_PROMPT = """你是专业播客翻译，请将以下英文播客片段翻译成中文。

要求：
- 意译为主，保留所有信息点
- 说人话，不要逐词直译
- 保留说话人的语气特征（主持人vs嘉宾）
- 适合朗读，自然流畅

上文背景：这是 Lex Fridman 与 Sam Altman（OpenAI CEO）的访谈。

原文片段：
{segments_text}

请严格按以下 JSON 格式返回，不要有其他内容：
```json
{{
  "segments": [
    {{"speaker": "SPEAKER_ID", "text_zh": "中文翻译"}}
  ]
}}
```"""


def call_claude_headless(prompt: str) -> str:
    """调用 claude -p，返回 stdout 文本"""
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        stderr = result.stderr.lower()
        if any(k in stderr for k in ["rate limit", "usage limit", "quota", "5-hour"]):
            print("⚠️  Claude Code 配额耗尽，请稍后重试")
            sys.exit(0)
        raise RuntimeError(f"claude 调用失败: {result.stderr[:200]}")
    return result.stdout


def extract_json(text: str) -> dict:
    """从 claude 输出中提取 JSON，兜底用正则"""
    # 优先提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        return json.loads(match.group(1))
    # 兜底：找第一个 { ... }
    match = re.search(r"\{[\s\S]+\}", text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"无法从输出中提取 JSON:\n{text[:300]}")


def format_segments_for_prompt(segments: list) -> str:
    lines = []
    for i, seg in enumerate(segments):
        lines.append(f"[{i+1}] {seg['speaker']}: {seg['text']}")
    return "\n".join(lines)


def main():
    print("=" * 60)
    print("翻译验证测试")
    print("=" * 60)
    print(f"测试片段数：{len(TEST_SEGMENTS)}")
    print()

    # 构建 prompt
    segments_text = format_segments_for_prompt(TEST_SEGMENTS)
    prompt = TRANSLATE_PROMPT.format(segments_text=segments_text)

    print("▶ 正在调用 claude headless...")
    t0 = time.time()

    try:
        raw_output = call_claude_headless(prompt)
    except subprocess.TimeoutExpired:
        print("✗ 超时（120s）")
        sys.exit(1)
    except RuntimeError as e:
        print(f"✗ {e}")
        sys.exit(1)

    elapsed = time.time() - t0
    print(f"✓ 调用完成，耗时 {elapsed:.1f}s")
    print()

    # 解析 JSON
    try:
        result = extract_json(raw_output)
        segments_zh = result["segments"]
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"✗ JSON 解析失败: {e}")
        print("--- 原始输出 ---")
        print(raw_output[:500])
        sys.exit(1)

    print("✓ JSON 解析成功")
    print()

    # 展示双语对照
    print("=" * 60)
    print("双语对照")
    print("=" * 60)
    for orig, trans in zip(TEST_SEGMENTS, segments_zh):
        print(f"\n[{orig['speaker']}]")
        print(f"  EN: {orig['text']}")
        print(f"  ZH: {trans.get('text_zh', '(缺失)')}")

    print()
    print("=" * 60)
    print(f"✓ 验证完成：{len(segments_zh)}/{len(TEST_SEGMENTS)} 段翻译成功")

    # 检查完整性
    missing = [i for i, s in enumerate(segments_zh) if not s.get("text_zh")]
    if missing:
        print(f"⚠️  以下片段翻译为空：{missing}")
    else:
        print("✓ 所有片段翻译完整")


if __name__ == "__main__":
    main()
