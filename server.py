"""FastAPI サーバー: LAN 内の他PCからエージェントを利用できるようにする

起動方法:
    python server.py

API:
    POST   /sessions                 新規セッション作成 (returns {session_id})
    GET    /sessions                 セッション一覧
    DELETE /sessions/{id}            セッション削除
    POST   /sessions/{id}/chat       メッセージ送信 (body: {message: "..."}) -> 応答
    GET    /sessions/{id}/stats      統計取得
    GET    /health                   疎通確認

認証:
    X-API-Key ヘッダーに config.toml の server.api_key を指定
"""

import io
import os
import uuid
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import Agent
from config import CFG
from logger import setup_logging
from tools.file_ops import set_sandbox_root

# --- 初期化 ---
logger = setup_logging(CFG.log_dir, CFG.log_level)
logger.info("=== AI Agent Server 起動 ===")

# サンドボックス: 作業ディレクトリを起点
set_sandbox_root(os.getcwd())

app = FastAPI(title="AI Agent Core Server", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CFG.server_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# セッション管理（メモリ内）
_sessions: dict[str, Agent] = {}


# --- 認証 ---
def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key != CFG.server_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


# --- リクエスト/レスポンスモデル ---
class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    session_id: str
    assistant: str
    output: str
    stderr: str


class SessionInfo(BaseModel):
    session_id: str
    messages: int
    prompt_tokens: int
    completion_tokens: int
    tool_calls: int


# --- エンドポイント ---
@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": CFG.model,
        "num_ctx": CFG.num_ctx,
        "sessions": len(_sessions),
    }


@app.post("/sessions", dependencies=[Depends(require_api_key)])
def create_session() -> dict[str, str]:
    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = Agent(auto_confirm=CFG.server_auto_confirm)
    logger.info(f"session created: {session_id}")
    return {"session_id": session_id}


@app.get("/sessions", dependencies=[Depends(require_api_key)])
def list_sessions() -> list[SessionInfo]:
    result = []
    for sid, agent in _sessions.items():
        result.append(
            SessionInfo(
                session_id=sid,
                messages=len(agent.messages),
                prompt_tokens=agent.stats["prompt_tokens"],
                completion_tokens=agent.stats["completion_tokens"],
                tool_calls=agent.stats["tool_calls"],
            )
        )
    return result


@app.delete("/sessions/{session_id}", dependencies=[Depends(require_api_key)])
def delete_session(session_id: str) -> dict[str, str]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="session not found")
    del _sessions[session_id]
    logger.info(f"session deleted: {session_id}")
    return {"status": "deleted"}


@app.post("/sessions/{session_id}/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
def chat(session_id: str, req: ChatRequest) -> ChatResponse:
    agent = _sessions.get(session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="session not found")

    buf_out = io.StringIO()
    buf_err = io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            agent.run(req.message)
    except Exception as e:
        logger.exception(f"chat failed for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"agent run failed: {e}")

    # 最新の assistant メッセージを抽出
    assistant_text = ""
    for m in reversed(agent.messages):
        if m.get("role") == "assistant":
            assistant_text = m.get("content", "") or ""
            break

    return ChatResponse(
        session_id=session_id,
        assistant=assistant_text,
        output=buf_out.getvalue(),
        stderr=buf_err.getvalue(),
    )


@app.get("/sessions/{session_id}/stats", dependencies=[Depends(require_api_key)])
def stats(session_id: str) -> dict[str, Any]:
    agent = _sessions.get(session_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {
        "session_id": session_id,
        "stats": {
            "prompt_tokens": agent.stats["prompt_tokens"],
            "completion_tokens": agent.stats["completion_tokens"],
            "tool_calls": agent.stats["tool_calls"],
            "gen_time_ms": agent.stats["gen_time_ms"],
            "start_time": agent.stats["start_time"].isoformat(),
            "messages": len(agent.messages),
        },
        "display": agent.get_stats_display(),
    }


# --- エントリポイント ---
if __name__ == "__main__":
    import uvicorn

    print("=" * 50)
    print("  AI Agent Server")
    print(f"  モデル: {CFG.model}")
    print(f"  ホスト: {CFG.server_host}:{CFG.server_port}")
    print(f"  作業ディレクトリ: {os.getcwd()}")
    print(f"  API キー: {'(未設定)' if not CFG.server_api_key else '(設定済み)'}")
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
