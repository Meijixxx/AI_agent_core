#!/usr/bin/env python3
"""Local AI Agent — Ollama で動く CLI エージェント"""

import os
from datetime import datetime

from agent import Agent
from config import CFG
from logger import setup_logging
from tools.file_ops import set_sandbox_root


def print_banner() -> None:
    print("=" * 50)
    print("  Local AI Agent")
    print(f"  モデル: {CFG.model}")
    print(f"  コンテキスト: {CFG.num_ctx} トークン")
    print("=" * 50)
    print("  コマンド:")
    print("    /quit            - 終了")
    print("    /clear           - 履歴クリア")
    print("    /save [name]     - セッション保存")
    print("    /load <name>     - セッション復元")
    print("    /list-sessions   - セッション一覧")
    print("    /stats           - 統計表示")
    print("    /help            - このヘルプを表示")
    print()


def list_sessions() -> str:
    if not os.path.isdir(CFG.session_dir):
        return "(セッションディレクトリがありません)"
    files = sorted(
        f for f in os.listdir(CFG.session_dir)
        if f.endswith(".json")
    )
    if not files:
        return "(セッションなし)"
    lines = ["セッション一覧:"]
    for f in files:
        path = os.path.join(CFG.session_dir, f)
        size = os.path.getsize(path)
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        lines.append(f"  {f[:-5]:<30} {size:>8} bytes  {mtime}")
    return "\n".join(lines)


def session_path(name: str) -> str:
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_.")
    if not safe_name:
        safe_name = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(CFG.session_dir, f"{safe_name}.json")


def print_help() -> None:
    print("  /quit            - 終了")
    print("  /clear           - 会話履歴をクリア")
    print("  /save [name]     - 履歴を保存（name省略時は日時）")
    print("  /load <name>     - 履歴を復元")
    print("  /list-sessions   - 保存済みセッション一覧")
    print("  /stats           - セッション統計を表示")
    print("  /help            - このヘルプを表示")


def main() -> None:
    # ロガー初期化
    logger = setup_logging(CFG.log_dir, CFG.log_level)
    logger.info("=== AI Agent 起動 ===")

    print_banner()

    # 作業ディレクトリをサンドボックスに設定
    cwd = os.getcwd()
    set_sandbox_root(cwd)
    os.makedirs(CFG.session_dir, exist_ok=True)

    print(f"  作業ディレクトリ: {cwd}")
    print(f"  サンドボックス: この配下のみファイル操作可能")
    print(f"  ログ: {os.path.join(CFG.log_dir, 'agent.log')}")
    print()

    agent = Agent()

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            logger.info("=== AI Agent 終了 ===")
            break

        if not user_input:
            continue

        # 組み込みコマンド
        if user_input == "/quit":
            print("Bye!")
            logger.info("=== AI Agent 終了 ===")
            break

        if user_input == "/clear":
            agent = Agent()
            print("[履歴をクリアしました]")
            continue

        if user_input == "/help":
            print_help()
            continue

        if user_input == "/stats":
            print(agent.get_stats_display())
            continue

        if user_input == "/list-sessions":
            print(list_sessions())
            continue

        if user_input.startswith("/save"):
            parts = user_input.split(maxsplit=1)
            name = parts[1].strip() if len(parts) > 1 else datetime.now().strftime("%Y%m%d_%H%M%S")
            print(agent.save_session(session_path(name)))
            continue

        if user_input.startswith("/load"):
            parts = user_input.split(maxsplit=1)
            if len(parts) < 2:
                print("[ヒント] /load <name> で指定してください。候補:")
                print(list_sessions())
                continue
            name = parts[1].strip()
            print(agent.load_session(session_path(name)))
            continue

        if user_input.startswith("/"):
            print(f"[不明なコマンド] {user_input} (/help で一覧表示)")
            continue

        try:
            agent.run(user_input)
        except KeyboardInterrupt:
            print("\n[中断]")


if __name__ == "__main__":
    main()
