"""RAGパッケージ: ベクトル検索によるドキュメント参照"""

import os

from rag.store import RAGStore

_store: RAGStore | None = None


def get_store() -> RAGStore:
    """シングルトンのRAGストアを返す。"""
    global _store
    if _store is None:
        from config import CFG
        store_dir = (
            CFG.rag_dir
            if os.path.isabs(CFG.rag_dir)
            else os.path.join(os.getcwd(), CFG.rag_dir)
        )
        _store = RAGStore(store_dir)
    return _store
