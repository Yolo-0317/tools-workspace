#!/usr/bin/env python3
"""将 QClaw daily_briefing 定时任务切换为东财 OpenCLI 战报脚本。"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

JOBS_FILE = Path.home() / ".qclaw" / "cron" / "jobs.json"
PUSH_SCRIPT = Path(__file__).resolve().parents[2] / "push_daily_briefing_wechat.sh"

SLOT_BY_NAME = {
    "daily_briefing_09:00": "09:00",
    "daily_briefing_12:00": "12:00",
    "daily_briefing_15:00": "15:00",
    "daily_briefing_20:00": "20:00",
}


def _build_message(slot: str) -> str:
    return (
        "执行每日战报并推送微信。\n\n"
        f"1. 仅运行：bash {PUSH_SCRIPT} {slot}\n"
        "2. 将脚本 stdout 原样作为回复（成功时含「已推送」，失败时含错误原因）。\n"
        "3. 禁止调用 message 工具，禁止回复 NO_REPLY 或 HEARTBEAT_OK。\n"
        "4. 禁止自行搜索新闻或改写战报逻辑；宏观财经已由东财 OpenCLI 脚本抓取。"
    )


def main() -> int:
    if not JOBS_FILE.exists():
        print(f"❌ 未找到 QClaw cron 配置: {JOBS_FILE}", file=sys.stderr)
        return 1
    if not PUSH_SCRIPT.exists():
        print(f"❌ 未找到战报脚本: {PUSH_SCRIPT}", file=sys.stderr)
        return 1

    backup = JOBS_FILE.with_suffix(".json.bak.macro-eastmoney")
    shutil.copy2(JOBS_FILE, backup)
    data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))

    updated = 0
    for job in data.get("jobs", []):
        name = job.get("name", "")
        slot = SLOT_BY_NAME.get(name)
        if not slot:
            continue
        job.setdefault("payload", {})["message"] = _build_message(slot)
        job["description"] = f"每日战报（{slot}，东财 OpenCLI + 大盘/持仓）"
        updated += 1

    if updated == 0:
        print("⚠️ 未找到 daily_briefing_09/12/15/20 任务，未修改", file=sys.stderr)
        return 1

    JOBS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 已更新 {updated} 个 daily_briefing 任务")
    print(f"备份: {backup}")
    print(f"战报脚本: {PUSH_SCRIPT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
