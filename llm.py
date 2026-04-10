"""Ollama API クライアント"""

import json
import sys
from typing import Any

import requests

OLLAMA_BASE_URL = "http://localhost:11434"
# DEFAULT_MODEL = "qwen3.5:9b"
DEFAULT_MODEL = "gemma4-agent"
DEFAULT_NUM_CTX = 8192
MAX_RETRIES = 2


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str = DEFAULT_MODEL,
    stream: bool = False,
) -> dict[str, Any]:
    """Ollama /api/chat を呼び出す。

    stream=True の場合、テキストをリアルタイム出力し、最終レスポンスを返す。
    tool_calls がある場合は stream=False にフォールバック（tool calls はストリーム非対応のため）。
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "options": {"num_ctx": DEFAULT_NUM_CTX},
        "think": True,  # thinking モード有効化（Qwen3.5 は安全）
    }
    if tools:
        payload["tools"] = tools
        # tool 定義がある場合、ストリームを無効化（tool calls の完全な JSON が必要）
        stream = False

    payload["stream"] = stream

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json=payload,
                stream=stream,
                timeout=120,
            )
            resp.raise_for_status()

            if not stream:
                return resp.json()

            # ストリーミング: チャンクを逐次出力
            full_content = ""
            final_response = {}
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("message", {}).get("content"):
                    text = chunk["message"]["content"]
                    full_content += text
                    sys.stdout.write(text)
                    sys.stdout.flush()
                if chunk.get("done"):
                    final_response = chunk

            if full_content:
                print()  # 改行

            # 最終レスポンスを構築
            # final_response = chunk (done=true) に既にOllamaの統計フィールド
            # (prompt_eval_count, eval_count, total_duration等) が含まれている
            final_response["message"] = {
                "role": "assistant",
                "content": full_content,
            }
            return final_response

        except requests.ConnectionError:
            if attempt < MAX_RETRIES:
                print(f"[接続エラー] リトライ中... ({attempt + 1}/{MAX_RETRIES})")
                continue
            print("[エラー] Ollama に接続できません。`ollama serve` が起動しているか確認してください。")
            raise
        except requests.Timeout:
            if attempt < MAX_RETRIES:
                print(f"[タイムアウト] リトライ中... ({attempt + 1}/{MAX_RETRIES})")
                continue
            print("[エラー] Ollama からの応答がタイムアウトしました。")
            raise

    # ここには到達しないが型安全のため
    return {}