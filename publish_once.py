#!/usr/bin/env python3
"""一次性、可重试地把一集从 staging 发布到正式 feed。

供本机 launchd 调用。成功标记写在 `.scheduled_publish/<video_id>.done`；之后即使
调度器再次唤醒也只会退出，不会重复发布。
"""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path

from publish_from_staging import STAGING, extract_item, slug_from_item

HERE = Path(__file__).parent
STATE = HERE / ".scheduled_publish"


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=HERE, check=True)


def in_feed(path: Path, video_id: str, *, staging: bool) -> bool:
    prefix = "/staging/ep/" if staging else "/ep/"
    return f"{prefix}{video_id}<" in path.read_text(encoding="utf-8")


def finish_once(marker: Path, message: str, *, label: str, plist: Path) -> None:
    """先留下成功凭据，再移走配置并卸载自己，使任务真正只运行一次。"""
    marker.write_text(f"{message} {datetime.now().astimezone().isoformat()}\n", encoding="utf-8")
    if plist.exists():
        plist.rename(plist.with_suffix(".plist.completed"))
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{label}"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument("--pub-date", required=True)
    parser.add_argument("--expected-date", required=True, help="Asia/Shanghai 的 YYYY-MM-DD")
    parser.add_argument("--not-before", required=True, help="含时区的 ISO 时间，早于此时只退出")
    parser.add_argument("--launchd-label", required=True)
    parser.add_argument("--launchd-plist", required=True, type=Path)
    parser.add_argument("--multivoice", action="store_true")
    args = parser.parse_args()

    STATE.mkdir(exist_ok=True)
    marker = STATE / f"{args.video_id}.done"
    lock = STATE / f"{args.video_id}.lock"
    if marker.exists():
        print(f"✓ {args.video_id} 已完成，跳过", flush=True)
        return
    now = datetime.now().astimezone()
    if now.strftime("%Y-%m-%d") != args.expected_date:
        print(f"跳过：今天不是预定日期 {args.expected_date}", flush=True)
        return
    not_before = datetime.fromisoformat(args.not_before)
    if now < not_before:
        print(f"跳过：尚未到发布时间 {not_before.isoformat()}", flush=True)
        return
    try:
        lock.mkdir()
    except FileExistsError:
        print("另一实例正在执行，跳过", flush=True)
        return

    try:
        run("git", "pull", "--ff-only")
        if in_feed(HERE / "feed.xml", args.video_id, staging=False):
            run("python3", "podcast_doctor.py")
            run("git", "push", "origin", "main")
            finish_once(marker, "already-published", label=args.launchd_label, plist=args.launchd_plist)
            print(f"✓ {args.video_id} 已在正式 feed，确认 push 后标记完成", flush=True)
            return
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=HERE, check=True, capture_output=True, text=True
        ).stdout.strip()
        if dirty:
            raise SystemExit(f"工作树不干净，拒绝自动发布：\n{dirty}")
        if not in_feed(STAGING / "feed.xml", args.video_id, staging=True):
            raise SystemExit(f"{args.video_id} 既不在正式 feed，也不在 staging feed")

        staging_text = (STAGING / "feed.xml").read_text(encoding="utf-8")
        item, _ = extract_item(staging_text, args.video_id)
        slug = slug_from_item(item)
        run("python3", "podcast_doctor.py")
        command = [
            "python3", "publish_from_staging.py", args.video_id,
            "--pub-date", args.pub_date,
        ]
        if args.multivoice:
            command.append("--multivoice")
        run(*command)
        run("python3", "podcast_doctor.py")
        run(
            "git", "add", "feed.xml", "staging/feed.xml", "podcast_status.csv",
            f"episodes/{slug}.mp3", f"transcripts/{slug}.srt",
        )
        run("git", "commit", "-m", f"publish: {args.video_id} 转正式")
        run("git", "push", "origin", "main")
        finish_once(marker, "published", label=args.launchd_label, plist=args.launchd_plist)
        print(f"✓ {args.video_id} 一次性发布完成", flush=True)
    finally:
        lock.rmdir()


if __name__ == "__main__":
    main()
