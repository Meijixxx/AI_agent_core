"""Ollama embeddings API 呼び出し"""

import requests

from rag._settings import EMBEDDING_MODEL, OLLAMA_URL


def embed(text: str) -> list[float]:
    """テキストのembeddingベクトルをOllamaから取得する。"""
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]
