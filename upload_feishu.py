"""
上传播客产物到飞书云盘 → 播客翻译 文件夹

上传内容（存在则上传）：
  - final.mp3               完整播客（intro + 正文 + 章节）
  - output_zh_minimax.mp3   MiniMax 正文（无 intro）
  - output_zh.srt           中文字幕
  - output_bilingual.srt    双语字幕

用法：
    python upload_feishu.py work/<job_id>
    python upload_feishu.py work/<job_id> --title "Lex x Sam Altman"
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# 飞书云盘 - 播客翻译 文件夹
# 本仓库是 public，标识不写死在代码里，改从 .env 读（.env 已 gitignore）。
# 具体值记在私有笔记仓库 aicoding-notes/project5_podcast/PROJECT_MAP.md。
load_dotenv(Path(__file__).parent / ".env")

FOLDER_TOKEN   = os.getenv("FEISHU_FOLDER_TOKEN", "")
FEISHU_PROFILE = os.getenv("FEISHU_PROFILE", "")
FEISHU_DOMAIN  = os.getenv("FEISHU_DOMAIN", "")

# 要上传的文件（优先级顺序）
UPLOAD_TARGETS = [
    "final.mp3",
    "output_zh_minimax.mp3",
    "output_zh.srt",
    "output_bilingual.srt",
    "bilingual.md",
]


def upload_file(local_path: Path, remote_name: str) -> dict | None:
    """调用 lark-cli 上传单个文件，返回结果 dict"""
    print(f"  上传 {local_path.name} → {remote_name} ...", end="", flush=True)

    result = subprocess.run(
        [
            "lark-cli", "drive", "+upload",
            "--file", str(local_path),
            "--name", remote_name,
            "--folder-token", FOLDER_TOKEN,
            "--profile", FEISHU_PROFILE,
            "--as", "user",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f" ✗\n  原始输出: {result.stdout[:200]}")
        return None

    if not data.get("ok"):
        err = data.get("error", {})
        print(f" ✗ {err.get('message', '未知错误')}")
        return None

    file_data = data.get("data", {})
    url = file_data.get("url", "")
    print(f" ✓")
    if url:
        print(f"    {url}")
    return file_data


def main():
    parser = argparse.ArgumentParser(description="上传播客产物到飞书云盘")
    parser.add_argument("job_dir", help="work/<job_id> 目录")
    parser.add_argument("--title", default=None,
                        help="播客标题，用于文件命名（默认用 job_id）")
    args = parser.parse_args()

    job_dir = Path(args.job_dir)
    if not job_dir.exists():
        print(f"✗ 目录不存在: {job_dir}")
        sys.exit(1)

    # 标题前缀（用于文件命名）
    title_prefix = args.title or job_dir.name

    print(f"\n[飞书云盘] 上传播客产物")
    print(f"  来源目录: {job_dir}")
    print(f"  目标文件夹: 播客翻译 / {title_prefix}")
    print()

    uploaded = []
    skipped = []

    for filename in UPLOAD_TARGETS:
        local = job_dir / filename
        if not local.exists():
            skipped.append(filename)
            continue

        # 重命名为 "标题_原文件名"
        suffix = local.suffix
        stem = local.stem
        remote_name = f"{title_prefix}_{stem}{suffix}"

        result = upload_file(local, remote_name)
        if result:
            uploaded.append({
                "local": filename,
                "remote": remote_name,
                "url": result.get("url", ""),
                "token": result.get("file_token", ""),
            })

    # 汇总
    print(f"\n{'='*50}")
    print(f"✓ 上传完成：{len(uploaded)} 个文件")

    if uploaded:
        print(f"\n飞书云盘文件夹：")
        print(f"  https://{FEISHU_DOMAIN}/drive/folder/{FOLDER_TOKEN}")
        print(f"\n已上传文件：")
        for f in uploaded:
            print(f"  ✓ {f['remote']}")
            if f["url"]:
                print(f"    {f['url']}")

    if skipped:
        print(f"\n跳过（文件不存在）: {', '.join(skipped)}")

    # 保存上传记录
    record_path = job_dir / "feishu_upload.json"
    with open(record_path, "w", encoding="utf-8") as f:
        json.dump({
            "folder_token": FOLDER_TOKEN,
            "folder_url": f"https://{FEISHU_DOMAIN}/drive/folder/{FOLDER_TOKEN}",
            "title": title_prefix,
            "files": uploaded,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n上传记录已保存: {record_path}")


if __name__ == "__main__":
    main()
