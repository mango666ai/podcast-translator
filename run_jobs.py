"""
播客任务队列轮询脚本
从飞书多维表格拉取「待处理」任务，逐个执行完整 pipeline，完成后回写状态。

用法：
    python run_jobs.py              # 处理一条待处理任务后退出
    python run_jobs.py --loop       # 持续轮询，每 5 分钟检查一次
    python run_jobs.py --dry-run    # 只打印任务，不实际处理

飞书表格：
    https://m0c4oiqy715.feishu.cn/base/OucDbcF7MaNObBs1WANcmEAQnke

设置 macOS 定时运行（每5分钟）：
    crontab -e
    */5 * * * * cd ~/Documents/CCtest/podcast-translator && source ../VideoLingo/.venv/bin/activate && python run_jobs.py >> logs/cron.log 2>&1
"""

import sys
import os
import json
import time
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# ── 飞书配置 ────────────────────────────────────────────
BASE_TOKEN   = "OucDbcF7MaNObBs1WANcmEAQnke"
TABLE_ID     = "tblVsPdsuqoX5RLf"
FEISHU_PROFILE = "cli_a92330864c785bde"

# 字段名
F_URL       = "播客URL"
F_TITLE     = "标题"
F_DURATION  = "时长限制(秒)"
F_STATUS    = "状态"
F_LINK      = "飞书文件链接"
F_ERROR     = "错误信息"
F_DONE_TIME = "完成时间"

# ── 项目路径 ─────────────────────────────────────────────
PROJECT_DIR = Path(__file__).parent
VENV_PYTHON = PROJECT_DIR.parent / "VideoLingo" / ".venv" / "bin" / "python3.11"
LOG_DIR     = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


# ── 飞书 lark-cli 封装 ────────────────────────────────────
def lark(args: list) -> dict:
    """调用 lark-cli，返回 JSON dict"""
    cmd = ["lark-cli"] + args + ["--profile", FEISHU_PROFILE, "--as", "user"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"ok": False, "error": {"message": result.stderr[:200]}}


def get_pending_task() -> dict | None:
    """从多维表格拉取第一条「待处理」任务"""
    data = lark([
        "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
        "--filter-json", json.dumps({
            "logic": "and",
            "conditions": [[F_STATUS, "intersects", ["待处理"]]]
        }),
        "--limit", "1",
        "--format", "json",
    ])

    if not data.get("ok"):
        log(f"⚠️  查询失败: {data.get('error', {}).get('message', '')}")
        return None

    inner = data.get("data", {})
    rows = inner.get("data", [])
    record_ids = inner.get("record_id_list", [])
    field_names = inner.get("fields", [])

    if not rows or not record_ids:
        return None

    # 列式 → dict: {field_name: value}
    raw_fields = dict(zip(field_names, rows[0]))
    # select 字段返回 list，取第一个值
    fields = {
        k: (v[0] if isinstance(v, list) and v else v)
        for k, v in raw_fields.items()
    }
    return {"record_id": record_ids[0], "fields": fields}


def update_record(record_id: str, fields: dict):
    """更新指定记录的字段"""
    # 过滤掉 None 值；select 字段传字符串即可
    cells = {k: v for k, v in fields.items() if v is not None}
    data = lark([
        "base", "+record-upsert",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
        "--record-id", record_id,
        "--json", json.dumps(cells),
    ])
    return data.get("ok", False)


def run_script(script_name: str, args: list) -> tuple[bool, str]:
    """用 venv python 运行项目脚本"""
    cmd = [str(VENV_PYTHON), str(PROJECT_DIR / script_name)] + args
    log_file = LOG_DIR / f"{script_name.replace('.py','')}.log"

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=7200,  # 最长 2 小时
        cwd=str(PROJECT_DIR),
    )

    # 追加日志
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'='*50}\n{datetime.now()}\n")
        f.write(result.stdout)
        if result.stderr:
            f.write("\nSTDERR:\n" + result.stderr)

    return result.returncode == 0, result.stdout + result.stderr


def process_task(task: dict, dry_run: bool = False) -> bool:
    """执行一条任务的完整 pipeline"""
    record_id = task.get("record_id")
    fields    = task.get("fields", {})

    url      = fields.get(F_URL, "")
    title    = fields.get(F_TITLE, "") or ""
    duration = int(fields.get(F_DURATION) or 0)

    if not url:
        log(f"  ⚠️  记录 {record_id} 没有 URL，跳过")
        update_record(record_id, {F_STATUS: "失败", F_ERROR: "URL 为空"})
        return False

    log(f"\n{'='*55}")
    log(f"▶ 开始处理: {url[:60]}")
    log(f"  标题: {title or '(未填)'} | 时长限制: {duration or '全集'}秒")

    if dry_run:
        log("  [dry-run] 跳过实际处理")
        return True

    # 标记为处理中
    update_record(record_id, {F_STATUS: "处理中"})

    # ── Step 1: 转录 + 翻译 ────────────────────────────
    log("\n[1/5] 转录 + 翻译...")
    pipeline_args = [url, "--no-tts"]
    if duration > 0:
        pipeline_args += ["--duration", str(duration)]

    ok, output = run_script("test_pipeline.py", pipeline_args)
    if not ok:
        log(f"  ❌ 转录/翻译失败")
        update_record(record_id, {F_STATUS: "失败", F_ERROR: output[-300:]})
        return False

    # 从输出中提取 job_id / job 目录
    job_dir = None
    for line in output.splitlines():
        if "Job 目录:" in line:
            job_dir = line.split("Job 目录:")[-1].strip()
            break

    if not job_dir:
        log("  ❌ 无法获取 job 目录")
        update_record(record_id, {F_STATUS: "失败", F_ERROR: "无法获取 job 目录"})
        return False

    log(f"  ✓ job 目录: {job_dir}")

    # ── Step 2: MiniMax TTS ───────────────────────────
    log("\n[2/5] MiniMax TTS 合成...")
    ok, output = run_script("tts_minimax.py", [job_dir])
    if not ok:
        log("  ⚠️  MiniMax TTS 失败，fallback edge-tts")
        ok, output = run_script("tts_compose.py", [job_dir])
        if not ok:
            update_record(record_id, {F_STATUS: "失败", F_ERROR: "TTS 失败: " + output[-200:]})
            return False
    log("  ✓ TTS 完成")

    # ── Step 3: 开场简介 ──────────────────────────────
    log("\n[3/5] 生成开场简介...")
    ok, _ = run_script("intro_compose.py", [job_dir])
    if not ok:
        log("  ⚠️  简介生成失败，跳过（继续后续步骤）")

    # ── Step 4: SRT 字幕 + ID3 章节 ──────────────────
    log("\n[4/5] 生成字幕 + 章节标记...")
    run_script("generate_srt.py", [job_dir])
    run_script("add_chapters.py", [job_dir])
    log("  ✓ 字幕和章节完成")

    # ── Step 5: 上传飞书云盘 ──────────────────────────
    log("\n[5/5] 上传飞书云盘...")
    upload_args = [job_dir]
    if title:
        upload_args += ["--title", title]

    ok, output = run_script("upload_feishu.py", upload_args)
    feishu_url = ""
    if ok:
        # 从上传记录读取飞书链接
        upload_record = Path(job_dir) / "feishu_upload.json"
        if upload_record.exists():
            with open(upload_record, encoding="utf-8") as f:
                udata = json.load(f)
            feishu_url = udata.get("folder_url", "")
            # 优先用 final.mp3 的链接
            for finfo in udata.get("files", []):
                if "final" in finfo.get("local", "") and finfo.get("url"):
                    feishu_url = finfo["url"]
                    break
        log(f"  ✓ 上传完成")
    else:
        log("  ⚠️  上传失败，但本地文件已生成")

    # ── 回写飞书状态 ───────────────────────────────────
    done_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    update_record(record_id, {
        F_STATUS:    "已完成",
        F_LINK:      feishu_url,
        F_DONE_TIME: done_time,
        F_ERROR:     "",
    })

    log(f"\n✅ 任务完成！")
    log(f"   飞书链接: {feishu_url or '(上传失败)'}")
    return True


# ── 主入口 ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="播客任务队列轮询脚本")
    parser.add_argument("--loop",    action="store_true", help="持续轮询（每5分钟）")
    parser.add_argument("--dry-run", action="store_true", help="只打印任务，不实际处理")
    parser.add_argument("--interval", type=int, default=300, help="轮询间隔秒数（默认300）")
    args = parser.parse_args()

    log("🎙  播客任务队列启动")
    log(f"   模式: {'持续轮询' if args.loop else '单次运行'} | {'dry-run' if args.dry_run else '正式处理'}")

    while True:
        log("\n⟳  检查待处理任务...")
        task = get_pending_task()

        if task:
            process_task(task, dry_run=args.dry_run)
        else:
            log("   没有待处理任务")

        if not args.loop:
            break

        log(f"\n⏸  等待 {args.interval} 秒后再次检查（Ctrl+C 退出）...")
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            log("\n👋 已退出")
            break


if __name__ == "__main__":
    main()
