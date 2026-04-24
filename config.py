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
    num_predict: int = -1          # -1 = 無制限（モデル/コンテキスト次第で停止）
    max_retries: int = 2
    timeout: int = 120

    max_tool_loops: int = 10
    max_history_messages: int = 40
    token_budget_warn_ratio: float = 0.8

    session_dir: str = "sessions"
    log_dir: str = "logs"
    rag_dir: str = "rag_store"

    embedding_model: str = "nomic-embed-text"
    rag_chunk_size: int = 500
    rag_chunk_overlap: int = 50
    rag_top_k: int = 5

    log_level: str = "INFO"

    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_api_key: str = "change-me-to-random-string"
    server_cors_origins: list[str] = field(default_factory=lambda: ["*"])
    server_auto_confirm: bool = True


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
    cfg.num_predict = _get(data, "llm", "num_predict", cfg.num_predict)
    cfg.max_retries = _get(data, "llm", "max_retries", cfg.max_retries)
    cfg.timeout = _get(data, "llm", "timeout", cfg.timeout)

    cfg.max_tool_loops = _get(data, "agent", "max_tool_loops", cfg.max_tool_loops)
    cfg.max_history_messages = _get(data, "agent", "max_history_messages", cfg.max_history_messages)
    cfg.token_budget_warn_ratio = _get(data, "agent", "token_budget_warn_ratio", cfg.token_budget_warn_ratio)

    cfg.session_dir = _get(data, "paths", "session_dir", cfg.session_dir)
    cfg.log_dir = _get(data, "paths", "log_dir", cfg.log_dir)
    cfg.rag_dir = _get(data, "paths", "rag_dir", cfg.rag_dir)

    cfg.embedding_model = _get(data, "rag", "embedding_model", cfg.embedding_model)
    cfg.rag_chunk_size = _get(data, "rag", "chunk_size", cfg.rag_chunk_size)
    cfg.rag_chunk_overlap = _get(data, "rag", "chunk_overlap", cfg.rag_chunk_overlap)
    cfg.rag_top_k = _get(data, "rag", "top_k", cfg.rag_top_k)

    cfg.log_level = _get(data, "log", "level", cfg.log_level)

    cfg.server_host = _get(data, "server", "host", cfg.server_host)
    cfg.server_port = _get(data, "server", "port", cfg.server_port)
    cfg.server_api_key = _get(data, "server", "api_key", cfg.server_api_key)
    cfg.server_cors_origins = _get(data, "server", "cors_origins", cfg.server_cors_origins)
    cfg.server_auto_confirm = _get(data, "server", "auto_confirm", cfg.server_auto_confirm)

    return cfg


CFG = load_config()
