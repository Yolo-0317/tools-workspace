#!/usr/bin/env python3
"""探测东财掘金终端连通性（读 .env.emquant，不打印 Token 明文）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts._bootstrap import ensure_paths

ensure_paths()

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.emquant"


def load_emquant_env() -> None:
    if not ENV_FILE.is_file():
        print(f"❌ 未找到 {ENV_FILE}", file=sys.stderr)
        print("  cp config/emquant.env.example .env.emquant 后填写", file=sys.stderr)
        raise SystemExit(1)
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def mask(s: str, show: int = 4) -> str:
    s = (s or "").strip()
    if len(s) <= show * 2:
        return "***"
    return f"{s[:show]}...{s[-show:]}"


def check_tcp(serv_addr: str) -> bool:
    host, _, port_s = serv_addr.partition(":")
    port = int(port_s or "7001")
    import socket

    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError as exc:
        print(f"❌ TCP {serv_addr} 不通: {exc}", file=sys.stderr)
        return False


def main() -> int:
    load_emquant_env()
    token = os.environ.get("EMQUANT_TOKEN", "")
    strategy_id = os.environ.get("EMQUANT_STRATEGY_ID", "")
    serv = os.environ.get("EMQUANT_SERV_ADDR", "")
    account = os.environ.get("EMQUANT_ACCOUNT_ID", "")
    mode = os.environ.get("EMQUANT_RUN_MODE", "simulation")

    print("配置检查:")
    print(f"  EMQUANT_TOKEN        {'(已填)' if token else '(空 — 请在 .env.emquant 填写)'}")
    if token:
        print(f"                       {mask(token)}")
    print(f"  EMQUANT_STRATEGY_ID  {'(已填)' if strategy_id else '(空)'}")
    if strategy_id:
        print(f"                       {mask(strategy_id)}")
    print(f"  EMQUANT_SERV_ADDR    {serv or '(空，本机终端可省略)'}")
    print(f"  EMQUANT_ACCOUNT_ID   {account or '(空)'}")
    print(f"  EMQUANT_RUN_MODE     {mode}")

    enabled = os.environ.get("EMQUANT_ENABLED", "0").strip()
    print(f"  EMQUANT_ENABLED      {enabled}")
    if enabled != "1":
        print("\n⚠️ 量化已下线（EMQUANT_ENABLED≠1）。见 emquant-sim/OFFLINE.md", file=sys.stderr)
        return 0

    if not token or not strategy_id:
        print("\n请先在 Win11 量化终端复制 Token / 策略 ID，写入 .env.emquant", file=sys.stderr)
        return 2

    if serv and not check_tcp(serv):
        print("提示: 确认 Win11 量化终端已登录且 Parallels 虚拟机 IP 正确", file=sys.stderr)
        return 3

    if serv:
        print(f"\n✅ 网络可达 {serv}")

    try:
        from gm.api import MODE_LIVE, run, set_token  # type: ignore
    except ImportError:
        import platform

        print("\n⚠️ 本机无法 import gm。", file=sys.stderr)
        if platform.system() == "Darwin":
            print(
                "  掘金 gm 官方 wheel 仅支持 Windows / Linux x86_64，"
                "M 系 Mac 上不能 pip 安装。",
                file=sys.stderr,
            )
            print(
                "  请在 Win11 虚拟机内：量化终端 → SDK 下载 → 安装 Python+gm，"
                "在终端运行策略验证。",
                file=sys.stderr,
            )
            print(
                f"  网络层已通时，.env.emquant 中的 EMQUANT_SERV_ADDR 供 Win 本机脚本使用；"
                f"Mac 仅做配置与端口探测。",
                file=sys.stderr,
            )
        else:
            print(
                "  pip install gm -i https://pypi.tuna.tsinghua.edu.cn/simple",
                file=sys.stderr,
            )
        return 4

    set_token(token)
    kwargs: dict = {
        "strategy_id": strategy_id,
        "filename": __file__,
        "mode": MODE_LIVE,
        "token": token,
    }
    if serv:
        kwargs["serv_addr"] = serv

    print("\n尝试连接终端（需终端已开、策略已在界面关联仿真账户）…")
    print("若长时间无输出，请在终端「我的策略」点运行后再试。")

    def init(context):
        from gm.api import get_cash, get_position  # type: ignore

        print("account_id:", getattr(context, "account_id", None))
        print("cash:", get_cash())
        print("positions:", get_position())

    # gm run 会阻塞；探测只做配置+TCP，完整 run 由用户在 Win11 或自行脚本触发
    print("\n配置与端口检查完成。完整策略请用终端运行或在 Win11 执行 run()。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
