"""Embedding API 呼び出し

環境変数 AGENT_EMBED_SERVER_URL が設定されていれば、そのURLの /embed を叩く
（サーバ経由。クライアントPCにOllamaが無い環境向け）。
未設定ならローカルの Ollama /api/embeddings を直接呼ぶ。
"""

import os

import requests


def embed(text: str) -> list[float]:
    """テキストのembeddingベクトルを取得する。"""
    # 環境変数は呼び出し時に読む（client_cli.py で引数パース後に設定されるため）
    remote_url = os.environ.get("AGENT_EMBED_SERVER_URL", "").rstrip("/")
    if remote_url:
        api_key = os.environ.get("AGENT_EMBED_SERVER_API_KEY", "")
        headers = {"X-API-Key": api_key} if api_key else {}
        resp = requests.post(
            f"{remote_url}/embed",
            headers=headers,
            json={"text": text},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embedding"]

    # ローカル Ollama 直接
    from rag._settings import EMBEDDING_MODEL, OLLAMA_URL
    resp = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]
