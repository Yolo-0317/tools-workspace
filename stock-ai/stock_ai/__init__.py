"""stock-ai 共享库：路径引导、日志、通知、标的配置。"""

from stock_ai.bootstrap import ensure_repo_root_on_path
from stock_ai.logging import (
    get_logger,
    setup_debug_logging,
    setup_ingest_logging,
    setup_logging,
    setup_monitor_logging,
)
from stock_ai.notify import send_to_lark
from stock_ai.symbols import CODE_NAMES, CODES, code_label

__all__ = [
    "ensure_repo_root_on_path",
    "get_logger",
    "setup_debug_logging",
    "setup_ingest_logging",
    "setup_logging",
    "setup_monitor_logging",
    "send_to_lark",
    "CODE_NAMES",
    "CODES",
    "code_label",
]
