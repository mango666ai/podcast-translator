import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

DEFAULT_OPENAI_MODEL = "gpt-5.6-luna"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_CLAUDE_MODEL = "sonnet"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def _looks_like_real_key(api_key: str | None) -> bool:
    if not api_key:
        return False
    if any(ch.isspace() for ch in api_key):
        return False
    if any(ord(ch) > 127 for ch in api_key):
        return False
    return api_key.startswith(("sk-", "sess-"))


def call_claude_cli(prompt: str, *, json_mode: bool = False, timeout: float = 240) -> str:
    claude_bin = os.getenv("CLAUDE_BIN", str(Path.home() / ".local/bin/claude"))
    model = os.getenv("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
    if json_mode:
        prompt = prompt.rstrip() + "\n\n只输出合法 JSON，不要 Markdown 代码块，不要解释。"
    result = subprocess.run(
        [claude_bin, "-p", prompt, "--model", model],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        stderr = result.stderr.lower()
        if any(k in stderr for k in ["rate limit", "usage limit", "quota", "5-hour"]):
            print("⚠️ Claude CLI 配额耗尽，稍后重试即可续跑")
            sys.exit(0)
        raise RuntimeError(f"Claude CLI 失败: {result.stderr[:300]}")
    text = result.stdout.strip()
    if not text:
        raise RuntimeError("Claude CLI 返回为空")
    return text


def call_deepseek(prompt: str, *, json_mode: bool = False, timeout: float = 240) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, timeout=timeout)
    if json_mode:
        prompt = prompt.rstrip() + "\n\n只输出合法 JSON，不要 Markdown 代码块，不要解释。"

    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    text = response.choices[0].message.content or ""
    if not text.strip():
        raise RuntimeError("DeepSeek 返回为空")
    return text


def call_openai(prompt: str, *, json_mode: bool = False, timeout: float = 240) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    client = OpenAI(api_key=api_key, timeout=timeout)
    if json_mode:
        prompt = prompt.rstrip() + "\n\n只输出合法 JSON，不要 Markdown 代码块，不要解释。"

    response = client.responses.create(
        model=model,
        input=prompt,
    )
    text = getattr(response, "output_text", "") or ""
    if not text.strip():
        raise RuntimeError("OpenAI 返回为空")
    return text


def call_gpt(prompt: str, *, json_mode: bool = False, timeout: float = 240) -> str:
    """翻译/文本生成统一入口。优先级：DeepSeek > OpenAI > 本地 Claude CLI（兜底，已知脚本调用不稳定）。"""
    if _looks_like_real_key(os.getenv("DEEPSEEK_API_KEY")):
        return call_deepseek(prompt, json_mode=json_mode, timeout=timeout)
    if _looks_like_real_key(os.getenv("OPENAI_API_KEY")):
        return call_openai(prompt, json_mode=json_mode, timeout=timeout)
    return call_claude_cli(prompt, json_mode=json_mode, timeout=timeout)
