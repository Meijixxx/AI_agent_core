"""設定ファイル (config.toml) の読み込みとデフォルト値"""

import os
from dataclasses import dataclass, field
from typing import Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # type: ignore


@dataclass
class Config:
    ollama_url: str = "http://localhost:11434"
    model: str = "gemma4-agent"
    num_ctx: int = 8192
    max_retries: int = 2
    timeout: int = 120

    max_tool_loops: int = 10
    max_history_messages: int = 40
    token_budget_warn_ratio: float = 0.8

    session_dir: str = "sessions"
    log_dir: str = "logs"

    log_level: str = "INFO"


def _get(d: dict[str, Any], section: str, key: str, default: Any) -> Any:
    return d.get(section, {}).get(key, default)


def load_config(path: str = "config.toml") -> Config:
    """config.toml を読み込む。ファイルがなければデフォルト値を返す。"""
    cfg = Config()
    if not os.path.isfile(path):
        return cfg

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        print(f"[警告] config.toml の読み込みに失敗しました: {e}")
        return cfg

    cfg.ollama_url = _get(data, "llm", "ollama_url", cfg.ollama_url)
    cfg.model = _get(data, "llm", "model", cfg.model)
    cfg.num_ctx = _get(data, "llm", "num_ctx", cfg.num_ctx)
    cfg.max_retries = _get(data, "llm", "max_retries", cfg.max_retries)
    cfg.timeout = _get(data, "llm", "timeout", cfg.timeout)

    cfg.max_tool_loops = _get(data, "agent", "max_tool_loops", cfg.max_tool_loops)
    cfg.max_history_messages = _get(data, "agent", "max_history_messages", cfg.max_history_messages)
    cfg.token_budget_warn_ratio = _get(data, "agent", "token_budget_warn_ratio", cfg.token_budget_warn_ratio)

    cfg.session_dir = _get(data, "paths", "session_dir", cfg.session_dir)
    cfg.log_dir = _get(data, "paths", "log_dir", cfg.log_dir)

    cfg.log_level = _get(data, "log", "level", cfg.log_level)

    return cfg


CFG = load_config()
