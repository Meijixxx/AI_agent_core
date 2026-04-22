"""Ollama embeddings API 呼び出し"""

import requests
from config import CFG


def embed(text: str) -> list[float]:
    """テキストのembeddingベクトルをOllamaから取得する。"""
    resp = requests.post(
        f"{CFG.ollama_url}/api/embeddings",
        json={"model": CFG.embedding_model, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]
