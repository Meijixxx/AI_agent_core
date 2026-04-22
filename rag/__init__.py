"""RAGパッケージ: ベクトル検索によるドキュメント参照"""

import os

from rag._settings import RAG_DIR
from rag.store import RAGStore

_store: RAGStore | None = None


def get_store() -> RAGStore:
    """シングルトンのRAGストアを返す。"""
    global _store
    if _store is None:
        store_dir = RAG_DIR if os.path.isabs(RAG_DIR) else os.path.join(os.getcwd(), RAG_DIR)
        _store = RAGStore(store_dir)
    return _store
