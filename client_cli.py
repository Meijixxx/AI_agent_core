"""LAN 内の他PCから server.py に接続する CLI クライアント

使い方:
    python client_cli.py --url http://<サーバーIP>:8000 --api-key <キー>

環境変数でも可:
    AGENT_SERVER_URL=http://192.168.1.10:8000
    AGENT_API_KEY=your-key
    python client_cli.py
"""

import argparse
import os
import sys

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Agent Server client")
    parser.add_argument(
        "--url",
        default=os.environ.get("AGENT_SERVER_URL", "http://localhost:8000"),
        help="サーバーURL (default: http://localhost:8000)",
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
    args = parser.parse_args()

    if not args.api_key:
        print("[エラー] --api-key または環境変数 AGENT_API_KEY を指定してください")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    headers = {"X-API-Key": args.api_key}

    # ヘルスチェック
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
        info = r.json()
        print(f"[接続OK] モデル: {info.get('model')}, ctx: {info.get('num_ctx')}")
    except Exception as e:
        print(f"[エラー] サーバーに接続できません: {e}")
        sys.exit(1)

    # セッション取得/作成
    session_id = args.session
    if not session_id:
        try:
            r = requests.post(f"{base_url}/sessions", headers=headers, timeout=5)
            r.raise_for_status()
            session_id = r.json()["session_id"]
            print(f"[セッション作成] {session_id}")
        except requests.HTTPError as e:
            print(f"[エラー] セッション作成失敗: {e.response.status_code} {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"[エラー] セッション作成失敗: {e}")
            sys.exit(1)
    else:
        print(f"[セッション継続] {session_id}")

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
                r = requests.get(f"{base_url}/sessions/{session_id}/stats", headers=headers, timeout=5)
                r.raise_for_status()
                print(r.json().get("display", ""))
            except Exception as e:
                print(f"[エラー] {e}")
            continue

        if user_input == "/end":
            try:
                requests.delete(f"{base_url}/sessions/{session_id}", headers=headers, timeout=5)
                print(f"[セッション削除] {session_id}")
            except Exception as e:
                print(f"[エラー] {e}")
            break

        # chat リクエスト
        try:
            r = requests.post(
                f"{base_url}/sessions/{session_id}/chat",
                headers=headers,
                json={"message": user_input},
                timeout=600,
            )
            r.raise_for_status()
            data = r.json()
        except requests.HTTPError as e:
            print(f"[エラー] {e.response.status_code} {e.response.text}")
            continue
        except Exception as e:
            print(f"[エラー] {e}")
            continue

        # サーバー側の print 出力（ツール呼び出しログ等）を表示
        out = data.get("output", "")
        if out:
            print(out, end="" if out.endswith("\n") else "\n")

        # assistant 応答
        assistant = data.get("assistant", "")
        if assistant:
            print(f"\n{assistant}")


if __name__ == "__main__":
    main()
