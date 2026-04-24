"""FastAPI サーバー: LAN 内の他PCからエージェントを利用できるようにする

アーキテクチャ:
  [クライアントPC] --chat-->  [サーバPC(このPC): LLM]
                  <--tool--             ↑ LLM制御
                  <--tool_call--        ツール実行はクライアント側で！
                  -->tool_result-->
                  <--done--

起動方法:
    python server.py

API:
    POST   /sessions                       新規セッション作成
    DELETE /sessions/{id}                  セッション削除
    POST   /sessions/{id}/chat             メッセージ送信（非同期開始）
    GET    /sessions/{id}/next             次のイベントをロングポール取得
    POST   /sessions/{id}/tool_result      ツール実行結果をサーバに返す
    GET    /sessions/{id}/stats            統計取得
    GET    /health                         疎通確認

認証:
    X-API-Key ヘッダーに config.toml の server.api_key を指定
"""

import io
import os
import queue
import threading
import uuid
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import Agent
from config import CFG
from logger import setup_logging

# --- 初期化 ---
logger = setup_logging(CFG.log_dir, CFG.log_level)
logger.info("=== AI Agent Server 起動 ===")

app = FastAPI(title="AI Agent Core Server", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CFG.server_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- セッション状態 ---
class SessionState:
    """1セッションの状態（Agent + イベントキュー + スレッド）"""

    def __init__(self) -> None:
        # 生成中タイマーはクライアント側で表示するため、サーバ側は no-op で抑制
        self.agent: Agent = Agent(
            auto_confirm=CFG.server_auto_confirm,
            tool_executor=self._remote_tool,
            progress_callback=lambda _elapsed: None,
        )
        self.event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.tool_result_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.running_thread: threading.Thread | None = None
        self.lock = threading.Lock()

    def _remote_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Agent スレッドから呼ばれる。クライアントにツール要求を投げて結果を待つ。"""
        call_id = uuid.uuid4().hex[:8]
        self.event_queue.put({
            "type": "tool_call",
            "call_id": call_id,
            "name": name,
            "arguments": arguments,
        })
        # 該当 call_id の結果を待つ（他の call_id が混ざっていたら元に戻す）
        while True:
            try:
                result = self.tool_result_queue.get(timeout=600)
            except queue.Empty:
                logger.warning(f"tool_result timeout for {call_id}")
                return "[エラー] クライアントからのツール結果がタイムアウトしました"
            if result.get("call_id") == call_id:
                return result.get("content", "")
            # call_id 不一致は戻して再取得
            self.tool_result_queue.put(result)

    def start_chat(self, message: str) -> None:
        """メッセージ処理をバックグラウンドスレッドで開始する。"""
        with self.lock:
            if self.running_thread is not None and self.running_thread.is_alive():
                raise HTTPException(status_code=409, detail="previous chat still running")

            def run() -> None:
                buf_out = io.StringIO()
                buf_err = io.StringIO()
                try:
                    with redirect_stdout(buf_out), redirect_stderr(buf_err):
                        self.agent.run(message)
                except Exception as e:
                    logger.exception(f"agent.run failed: {e}")
                    self.event_queue.put({"type": "error", "message": str(e)})
                    return
                # 最終応答は output（agent の print 出力）に含まれるため、
                # assistant フィールドは冗長なので送らない
                self.event_queue.put({
                    "type": "done",
                    "output": buf_out.getvalue(),
                    "stderr": buf_err.getvalue(),
                })

            self.running_thread = threading.Thread(target=run, daemon=True)
            self.running_thread.start()

    def next_event(self, timeout: int = 30) -> dict[str, Any]:
        """次のイベントをロングポールで取得する。タイムアウト時は heartbeat を返す。"""
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return {"type": "heartbeat"}

    def submit_tool_result(self, call_id: str, content: str) -> None:
        self.tool_result_queue.put({"call_id": call_id, "content": content})


_sessions: dict[str, SessionState] = {}


# --- 認証 ---
def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != CFG.server_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


# --- リクエストモデル ---
class ChatRequest(BaseModel):
    message: str


class ToolResultRequest(BaseModel):
    call_id: str
    content: str


class EmbedRequest(BaseModel):
    text: str


class SaveRequest(BaseModel):
    name: str = ""


class LoadRequest(BaseModel):
    name: str


# --- エンドポイント ---
@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": CFG.model,
        "num_ctx": CFG.num_ctx,
        "sessions": len(_sessions),
    }


@app.post("/embed", dependencies=[Depends(require_api_key)])
def embed_endpoint(req: EmbedRequest) -> dict[str, Any]:
    """サーバー側の Ollama に embedding 生成を委譲する。
    クライアントPCからOllamaが見えない環境向け。
    """
    import requests as _requests
    try:
        resp = _requests.post(
            f"{CFG.ollama_url}/api/embeddings",
            json={"model": CFG.embedding_model, "prompt": req.text},
            timeout=60,
        )
        resp.raise_for_status()
        return {"embedding": resp.json()["embedding"]}
    except Exception as e:
        logger.error(f"embed failed: {e}")
        raise HTTPException(status_code=500, detail=f"embedding failed: {e}")


@app.post("/sessions", dependencies=[Depends(require_api_key)])
def create_session() -> dict[str, str]:
    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = SessionState()
    logger.info(f"session created: {session_id}")
    return {"session_id": session_id}


@app.delete("/sessions/{session_id}", dependencies=[Depends(require_api_key)])
def delete_session(session_id: str) -> dict[str, str]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="session not found")
    del _sessions[session_id]
    logger.info(f"session deleted: {session_id}")
    return {"status": "deleted"}


@app.post("/sessions/{session_id}/chat", dependencies=[Depends(require_api_key)])
def chat(session_id: str, req: ChatRequest) -> dict[str, str]:
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    state.start_chat(req.message)
    logger.info(f"chat started: {session_id} msg={req.message[:100]}")
    return {"status": "started"}


@app.get("/sessions/{session_id}/next", dependencies=[Depends(require_api_key)])
def next_event(session_id: str) -> dict[str, Any]:
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return state.next_event(timeout=30)


@app.post("/sessions/{session_id}/tool_result", dependencies=[Depends(require_api_key)])
def tool_result(session_id: str, req: ToolResultRequest) -> dict[str, str]:
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    state.submit_tool_result(req.call_id, req.content)
    return {"status": "ok"}


@app.get("/sessions/{session_id}/stats", dependencies=[Depends(require_api_key)])
def stats(session_id: str) -> dict[str, Any]:
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "display": state.agent.get_stats_display(),
    }


def _session_path(name: str) -> str:
    """セッションファイル名をサニタイズして絶対パスを返す。"""
    import re
    safe = re.sub(r"[^A-Za-z0-9._-]", "", name)
    if not safe:
        safe = uuid.uuid4().hex[:8]
    os.makedirs(CFG.session_dir, exist_ok=True)
    return os.path.join(CFG.session_dir, f"{safe}.json")


@app.post("/sessions/{session_id}/save", dependencies=[Depends(require_api_key)])
def save_session(session_id: str, req: SaveRequest) -> dict[str, str]:
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    from datetime import datetime
    name = req.name.strip() or datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _session_path(name)
    msg = state.agent.save_session(path)
    return {"status": "ok", "message": msg}


@app.post("/sessions/{session_id}/load", dependencies=[Depends(require_api_key)])
def load_session(session_id: str, req: LoadRequest) -> dict[str, str]:
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    path = _session_path(req.name)
    msg = state.agent.load_session(path)
    return {"status": "ok", "message": msg}


@app.get("/saved-sessions", dependencies=[Depends(require_api_key)])
def list_saved_sessions() -> dict[str, Any]:
    if not os.path.isdir(CFG.session_dir):
        return {"sessions": []}
    files = sorted(f for f in os.listdir(CFG.session_dir) if f.endswith(".json"))
    items = []
    for f in files:
        path = os.path.join(CFG.session_dir, f)
        items.append({
            "name": f[:-5],
            "size": os.path.getsize(path),
            "mtime": int(os.path.getmtime(path)),
        })
    return {"sessions": items}


@app.post("/sessions/{session_id}/clear", dependencies=[Depends(require_api_key)])
def clear_session(session_id: str) -> dict[str, str]:
    """会話履歴をクリアする（system promptは残す）。"""
    state = _sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    state.agent.messages = state.agent.messages[:1]
    return {"status": "ok", "message": "履歴をクリアしました"}


# --- エントリポイント ---
if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("  AI Agent Server (remote-tool mode)")
    print(f"  モデル: {CFG.model}")
    print(f"  ホスト: {CFG.server_host}:{CFG.server_port}")
    print(f"  API キー: {'(未設定)' if not CFG.server_api_key else '(設定済み)'}")
    print("  ※ ツール実行はクライアント側で行われます")
    print("=" * 50)
    if CFG.server_api_key == "change-me-to-random-string":
        print("[警告] API キーがデフォルト値のままです。config.toml で変更してください。")
    print()

    uvicorn.run(
        "server:app",
        host=CFG.server_host,
        port=CFG.server_port,
        log_level=CFG.log_level.lower(),
    )
