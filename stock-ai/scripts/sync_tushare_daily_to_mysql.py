"""兼容入口 → scripts/sync/sync_tushare_daily_to_mysql.py"""
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
runpy.run_module("scripts.sync.sync_tushare_daily_to_mysql", run_name="__main__")
