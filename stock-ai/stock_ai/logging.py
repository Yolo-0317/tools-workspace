"""统一日志配置。"""

import inspect
import logging
from datetime import datetime
from pathlib import Path


def setup_logging(
    name: str = "stock_monitor",
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    console_level: int = logging.INFO,
    log_format: str = "%(asctime)s - %(levelname)s - %(message)s",
    date_format: str = "%Y-%m-%d %H:%M:%S",
) -> logging.Logger:
    caller_file = Path(inspect.stack()[1].filename)
    log_path = caller_file.parent / log_dir
    log_path.mkdir(exist_ok=True)

    log_file = log_path / f"{name}_{datetime.now().strftime('%Y%m%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


def get_logger(name: str = "stock_monitor") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger


def setup_monitor_logging() -> logging.Logger:
    return setup_logging(name="monitor", log_dir="logs")


def setup_ingest_logging() -> logging.Logger:
    return setup_logging(name="ingest", log_dir="logs")


def setup_debug_logging() -> logging.Logger:
    return setup_logging(
        name="debug",
        log_dir="logs",
        log_level=logging.DEBUG,
        console_level=logging.DEBUG,
    )
