#!/usr/bin/env python3
"""Local AI Agent — Ollama + Qwen3.5-9B で動く CLI エージェント"""

import os
import sys

from agent import Agent
from tools.file_ops import set_sandbox_root


def print_banner() -> None:
    print("=" * 50)
    print("  Local AI Agent (Qwen3.5-9B)")
    print("  ファイル操作・コード検索・シェル実行")
    print("=" * 50)
    print("  コマンド: /quit 終了 | /clear 履歴クリア")
    print()


def main() -> None:
    print_banner()

    # 作業ディレクトリをサンドボックスに設定
    cwd = os.getcwd()
    set_sandbox_root(cwd)
    print(f"  作業ディレクトリ: {cwd}")
    print(f"  サンドボックス: この配下のみファイル操作可能\n")

    agent = Agent()

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue

        # 組み込みコマンド
        if user_input == "/quit":
            print("Bye!")
            break
        elif user_input == "/clear":
            agent = Agent()  # 履歴リセット
            print("[履歴をクリアしました]")
            continue
        elif user_input == "/help":
            print("  /quit   - 終了")
            print("  /clear  - 会話履歴をクリア")
            print("  /help   - このヘルプを表示")
            continue

        agent.run(user_input)


if __name__ == "__main__":
    main()
