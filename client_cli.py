"""LAN 内の別PC (サーバ) に接続して、このPCのローカルフォルダで作業するクライアント

アーキテクチャ:
  このPC (cwd で作業)  <--HTTP-->  サーバPC (Ollama + LLM)

  1. ユーザーがメッセージを入力
  2. サーバに送信 → LLMが考える
  3. LLMが「read_file 実行したい」と判断
  4. サーバから「このツール実行して」のリクエストが飛んでくる
  5. クライアント (このPC) が自分のローカルフォルダで実行
  6. 結果をサーバに返す
  7. LLMが続行 → 最終回答を取得

使い方:
    # このPCのサンドボックス（作業フォルダ）に cd してから実行
    cd C:\\Users\\me\\Documents\\target_folder
    python client_cli.py --url http://<サーバIP>:8000 --api-key <キー>

環境変数でも設定可能:
    AGENT_SERVER_URL=http://192.168.1.10:8000
    AGENT_API_KEY=your-key
"""

import argparse
import json
import os
import sys

import requests

# クライアント側でローカル実行するツール群（server と同じ tools/ を流用）
from tools import DANGEROUS_TOOLS, execute_tool
from tools.file_ops import set_sandbox_root


def format_args(arguments: dict) -> str:
    """ツール引数を短く整形する。"""
    parts = []
    for k, v in arguments.items():
        s = str(v).replace("\n", " ")
        if len(s) > 60:
            s = s[:60] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)


def run_local_tool(name: str, arguments: dict, auto_confirm: bool) -> str:
    """クライアント側でツールを実行する。危険ツールは確認プロンプト。"""
    print(f"\n  > {name}({format_args(arguments)})")

    if not auto_confirm and name in DANGEROUS_TOOLS:
        try:
            answer = input("    実行する？ (y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            return "[スキップ] ユーザーが実行を拒否しました"

    try:
        result = execute_tool(name, arguments)
    except Exception as e:
        result = f"[エラー] {name} の実行に失敗: {e}"

    # 短く表示
    display = result.replace("\n", " ")
    if len(display) > 200:
        display = display[:200] + "..."
    print(f"    → {display}")
    return result


def chat_once(base_url: str, headers: dict, sid: str, message: str, auto_confirm: bool) -> None:
    """1ターン分のやりとりを処理する。"""
    # chat 開始
    try:
        r = requests.post(
            f"{base_url}/sessions/{sid}/chat",
            headers=headers,
            json={"message": message},
            timeout=10,
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        print(f"[エラー] {e.response.status_code} {e.response.text}")
        return
    except Exception as e:
        print(f"[エラー] chat 開始失敗: {e}")
        return

    # イベントループ
    showing_progress = False

    def clear_progress_line() -> None:
        nonlocal showing_progress
        if showing_progress:
            sys.stderr.write("\r" + " " * 40 + "\r")
            sys.stderr.flush()
            showing_progress = False

    while True:
        try:
            r = requests.get(
                f"{base_url}/sessions/{sid}/next",
                headers=headers,
                timeout=40,
            )
            r.raise_for_status()
            event = r.json()
        except requests.Timeout:
            # heartbeat 相当。継続
            continue
        except Exception as e:
            clear_progress_line()
            print(f"[エラー] イベント取得失敗: {e}")
            return

        etype = event.get("type")

        if etype == "heartbeat":
            continue

        if etype == "progress":
            elapsed = event.get("elapsed", 0)
            sys.stderr.write(f"\r[生成中... {elapsed:.1f}s]")
            sys.stderr.flush()
            showing_progress = True
            continue

        # progress 以外のイベントが来たら表示行をクリア
        clear_progress_line()

        if etype == "tool_call":
            call_id = event["call_id"]
            name = event["name"]
            arguments = event.get("arguments") or {}
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            result = run_local_tool(name, arguments, auto_confirm)
            # 結果を返す
            try:
                requests.post(
                    f"{base_url}/sessions/{sid}/tool_result",
                    headers=headers,
                    json={"call_id": call_id, "content": result},
                    timeout=10,
                )
            except Exception as e:
                print(f"[エラー] ツール結果送信失敗: {e}")
                return
            continue

        if etype == "done":
            out = event.get("output", "")
            if out:
                sys.stdout.write(out)
                if not out.endswith("\n"):
                    sys.stdout.write("\n")
            assistant = event.get("assistant", "")
            if assistant:
                print(f"\n{assistant}")
            return

        if etype == "error":
            print(f"[エラー] サーバ側失敗: {event.get('message')}")
            return

        print(f"[警告] 不明なイベント: {event}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Agent Server client (remote-tool mode)")
    parser.add_argument(
        "--url",
        default=os.environ.get("AGENT_SERVER_URL", "http://localhost:8000"),
        help="サーバURL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AGENT_API_KEY", ""),
        help="API キー (環境変数 AGENT_API_KEY でも可)",
    )
    parser.add_argument(
        "--session",
        default="",
        help="既存セッションID (省略時は新規作成)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="危険ツール実行時の確認をスキップ（注意）",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("[エラー] --api-key または環境変数 AGENT_API_KEY を指定してください")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    headers = {"X-API-Key": args.api_key}

    # クライアント側のサンドボックスを現在の作業ディレクトリに設定
    cwd = os.getcwd()
    set_sandbox_root(cwd)

    # ヘルスチェック
    try:
        r = requests.get(f"{base_url}/health", timeout=10)
        r.raise_for_status()
        info = r.json()
        print("=" * 50)
        print("  AI Agent Client (remote-tool mode)")
        print(f"  サーバ: {base_url}")
        print(f"  モデル: {info.get('model')} (ctx: {info.get('num_ctx')})")
        print(f"  作業フォルダ: {cwd}")
        print("  ※ ツール実行はこのPCのこのフォルダで行われます")
        print("=" * 50)
    except Exception as e:
        print(f"[エラー] サーバに接続できません: {e}")
        sys.exit(1)

    # セッション取得/作成
    session_id = args.session
    if not session_id:
        try:
            r = requests.post(f"{base_url}/sessions", headers=headers, timeout=10)
            r.raise_for_status()
            session_id = r.json()["session_id"]
            print(f"  セッション: {session_id} (新規)")
        except requests.HTTPError as e:
            print(f"[エラー] セッション作成失敗: {e.response.status_code} {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"[エラー] セッション作成失敗: {e}")
            sys.exit(1)
    else:
        print(f"  セッション: {session_id} (継続)")

    print("  コマンド: /quit 終了 | /stats 統計 | /end セッション削除")
    print()

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("Bye!")
            break

        if user_input == "/stats":
            try:
                r = requests.get(f"{base_url}/sessions/{session_id}/stats", headers=headers, timeout=10)
                r.raise_for_status()
                print(r.json().get("display", ""))
            except Exception as e:
                print(f"[エラー] {e}")
            continue

        if user_input == "/end":
            try:
                requests.delete(f"{base_url}/sessions/{session_id}", headers=headers, timeout=10)
                print(f"[セッション削除] {session_id}")
            except Exception as e:
                print(f"[エラー] {e}")
            break

        chat_once(base_url, headers, session_id, user_input, auto_confirm=args.yes)


if __name__ == "__main__":
    main()
