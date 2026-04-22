"""RAG設定: 環境変数 → config.py（任意）→ デフォルト値の優先順で取得。

クライアント側で config.py が無くても動くように設計。
- AGENT_OLLAMA_URL          (default: http://localhost:11434)
- AGENT_EMBEDDING_MODEL     (default: nomic-embed-text)
- AGENT_RAG_DIR             (default: rag_store)
- AGENT_RAG_CHUNK_SIZE      (default: 500)
- AGENT_RAG_CHUNK_OVERLAP   (default: 50)
"""

import os

# デフォルト値
OLLAMA_URL: str = "http://localhost:11434"
EMBEDDING_MODEL: str = "nomic-embed-text"
RAG_DIR: str = "rag_store"
CHUNK_SIZE: int = 500
CHUNK_OVERLAP: int = 50

# config.py が利用可能なら上書き（サーバー側 / ローカル main.py 用）
try:
    from config import CFG  # type: ignore
    OLLAMA_URL = getattr(CFG, "ollama_url", OLLAMA_URL)
    EMBEDDING_MODEL = getattr(CFG, "embedding_model", EMBEDDING_MODEL)
    RAG_DIR = getattr(CFG, "rag_dir", RAG_DIR)
    CHUNK_SIZE = getattr(CFG, "rag_chunk_size", CHUNK_SIZE)
    CHUNK_OVERLAP = getattr(CFG, "rag_chunk_overlap", CHUNK_OVERLAP)
except Exception:
    pass

# 環境変数が最優先
OLLAMA_URL = os.environ.get("AGENT_OLLAMA_URL", OLLAMA_URL)
EMBEDDING_MODEL = os.environ.get("AGENT_EMBEDDING_MODEL", EMBEDDING_MODEL)
RAG_DIR = os.environ.get("AGENT_RAG_DIR", RAG_DIR)
CHUNK_SIZE = int(os.environ.get("AGENT_RAG_CHUNK_SIZE", str(CHUNK_SIZE)))
CHUNK_OVERLAP = int(os.environ.get("AGENT_RAG_CHUNK_OVERLAP", str(CHUNK_OVERLAP)))
