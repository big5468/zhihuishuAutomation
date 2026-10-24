"""日志：控制台 + 文件，一处配置，全项目共用。

每个文件只管"领记录员"：logger = logging.getLogger(__name__)
喇叭装在哪（控制台/文件/格式/级别）是本文件的事，main.py 启动时调一次。

注：文件名 loging_setup 少了个 g（历史拼写），目录结构冻结，将错就错。
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def setup_logging(level: int = logging.INFO, log_dir: str = "logs") -> Path:
    """配置根 logger，返回日志文件路径。"""
    directory = ROOT / log_dir
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / f"{datetime.now():%Y%m%d-%H%M%S}.log"

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)
    return log_file
