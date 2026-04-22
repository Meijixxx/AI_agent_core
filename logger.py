"""ロガーセットアップ: logs/agent.log に RotatingFileHandler で出力"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOGGER_NAME = "ai_agent"
_initialized = False


def setup_logging(log_dir: str = "logs", level: str = "INFO") -> logging.Logger:
    """ロガーを初期化して返す。複数回呼んでも副作用なし。"""
    global _initialized
    logger = logging.getLogger(_LOGGER_NAME)

    if _initialized:
        return logger

    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "agent.log")

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1024 * 1024,  # 1MB
        backupCount=3,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False

    _initialized = True
    return logger


def get_logger() -> logging.Logger:
    """既にセットアップ済みのロガーを取得する（未初期化ならデフォルトで初期化）。"""
    if not _initialized:
        return setup_logging()
    return logging.getLogger(_LOGGER_NAME)
