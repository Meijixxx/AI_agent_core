"""Ollama API クライアント（タイマー・中断対応）"""

import json
import sys
import threading
import time
from typing import Any

import requests

from config import CFG

MAX_RETRIES = CFG.max_retries

# モジュールレベルで Session を保持（中断時に close() できるようにするため）
_session: requests.Session | None = None
_session_lock = threading.Lock()


def _get_session() -> requests.Session:
    global _session
    with _session_lock:
        if _session is None:
            _session = requests.Session()
        return _session


def _reset_session() -> None:
    """中断時に接続を強制切断してセッションを作り直す。"""
    global _session
    with _session_lock:
        if _session is not None:
            try:
                _session.close()
            except Exception:
                pass
            _session = None


def _chat_impl(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    model: str,
    stream: bool,
    first_token_event: threading.Event | None = None,
) -> dict[str, Any]:
    """実際の Ollama /api/chat 呼び出し。"""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "options": {"num_ctx": CFG.num_ctx},
        "think": True,
    }
    if tools:
        payload["tools"] = tools
        stream = False

    payload["stream"] = stream

    session = _get_session()
    resp = session.post(
        f"{CFG.ollama_url}/api/chat",
        json=payload,
        stream=stream,
        timeout=CFG.timeout,
    )
    resp.raise_for_status()

    if not stream:
        if first_token_event is not None:
            first_token_event.set()
        return resp.json()

    full_content = ""
    final_response: dict[str, Any] = {}
    for line in resp.iter_lines():
        if not line:
            continue
        chunk = json.loads(line)
        if chunk.get("message", {}).get("content"):
            text = chunk["message"]["content"]
            if first_token_event is not None and not first_token_event.is_set():
                # 最初のトークン受信時にタイマーを止める
                first_token_event.set()
            full_content += text
            sys.stdout.write(text)
            sys.stdout.flush()
        if chunk.get("done"):
            final_response = chunk

    if full_content:
        print()

    final_response["message"] = {
        "role": "assistant",
        "content": full_content,
    }
    return final_response


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str = None,  # type: ignore
    stream: bool = False,
) -> dict[str, Any] | None:
    """Ollama /api/chat を呼び出す。タイマー表示 + Ctrl+C 中断対応。

    中断された場合は None を返す。
    """
    if model is None:
        model = CFG.model

    cancel_event = threading.Event()
    first_token_event = threading.Event()
    result_container: list[Any] = [None]
    error_container: list[Any] = [None]

    def timer_worker() -> None:
        start = time.time()
        # 最初のトークン受信 or 完了まで表示
        while not first_token_event.is_set() and not cancel_event.is_set():
            elapsed = time.time() - start
            msg = f"\r[生成中... {elapsed:.1f}s]"
            try:
                sys.stderr.write(msg)
                sys.stderr.flush()
            except Exception:
                return
            time.sleep(0.1)
        # 行クリア
        try:
            sys.stderr.write("\r" + " " * 40 + "\r")
            sys.stderr.flush()
        except Exception:
            pass

    def llm_worker() -> None:
        for attempt in range(MAX_RETRIES + 1):
            if cancel_event.is_set():
                return
            try:
                result_container[0] = _chat_impl(
                    messages, tools, model, stream, first_token_event
                )
                return
            except requests.ConnectionError as e:
                if cancel_event.is_set():
                    return
                if attempt < MAX_RETRIES:
                    print(f"\n[接続エラー] リトライ中... ({attempt + 1}/{MAX_RETRIES})")
                    continue
                error_container[0] = e
                return
            except requests.Timeout as e:
                if cancel_event.is_set():
                    return
                if attempt < MAX_RETRIES:
                    print(f"\n[タイムアウト] リトライ中... ({attempt + 1}/{MAX_RETRIES})")
                    continue
                error_container[0] = e
                return
            except Exception as e:
                error_container[0] = e
                return

    timer_thread = threading.Thread(target=timer_worker, daemon=True)
    llm_thread = threading.Thread(target=llm_worker, daemon=True)

    timer_thread.start()
    llm_thread.start()

    try:
        while llm_thread.is_alive():
            llm_thread.join(timeout=0.2)
    except KeyboardInterrupt:
        cancel_event.set()
        first_token_event.set()  # タイマー停止
        _reset_session()  # 接続切断
        print("\n[中断] 生成を中断しました")
        return None
    finally:
        first_token_event.set()  # タイマー確実に停止
        timer_thread.join(timeout=0.5)

    if error_container[0] is not None:
        err = error_container[0]
        if isinstance(err, requests.ConnectionError):
            print("[エラー] Ollama に接続できません。`ollama serve` が起動しているか確認してください。")
        elif isinstance(err, requests.Timeout):
            print("[エラー] Ollama からの応答がタイムアウトしました。")
        else:
            print(f"[エラー] LLM 呼び出しに失敗しました: {err}")
        raise err

    return result_container[0]
