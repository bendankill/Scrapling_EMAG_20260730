"""
eMAG 爬虫 - 日志模块
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from config import LOGS_DIR


def setup_logger(name: str = "emag_crawler") -> logging.Logger:
    """创建双输出日志器：控制台 + 文件"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---- 控制台：INFO 及以上 ----
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # ---- 主日志文件：DEBUG 及以上，10MB 轮转 ----
    main_log = RotatingFileHandler(
        os.path.join(LOGS_DIR, "crawl.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    main_log.setLevel(logging.DEBUG)
    main_log.setFormatter(formatter)
    logger.addHandler(main_log)

    # ---- 错误日志文件 ----
    error_log = RotatingFileHandler(
        os.path.join(LOGS_DIR, "error.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    error_log.setLevel(logging.WARNING)
    error_log.setFormatter(formatter)
    logger.addHandler(error_log)

    return logger


# 全局单例
logger = setup_logger()
