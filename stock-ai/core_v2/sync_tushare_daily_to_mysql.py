"""兼容入口 → scripts/sync/sync_tushare_daily_to_mysql"""
from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

from scripts.sync.sync_tushare_daily_to_mysql import *  # noqa: F403
