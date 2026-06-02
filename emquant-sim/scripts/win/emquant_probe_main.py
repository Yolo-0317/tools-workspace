#!/usr/bin/env python3
# 复制到量化终端「策略目录」下的某策略文件夹，文件名须与 run(filename=...) 一致。
# 在终端：量化研究 → 我的策略 → 设置 → 关联仿真账户 → 点「运行」

from gm.api import *


def init(context):
    print("=== probe init ===")
    print("account_id:", getattr(context, "account_id", None))
    try:
        print("cash:", get_cash())
        print("positions:", get_position())
    except Exception as exc:
        print("query error:", exc)


def on_schedule(context):
    pass


if __name__ == "__main__":
    # 仅本地调试；在终端里运行时由终端注入 token/strategy_id，勿手写 token
    run(
        strategy_id="REPLACE_STRATEGY_ID",
        filename="emquant_probe_main.py",
        mode=MODE_LIVE,
        token="REPLACE_TOKEN",
    )
