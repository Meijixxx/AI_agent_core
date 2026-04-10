"""エージェントコア: tool-use ループ"""

import json
import sys
from typing import Any

import llm
from tools import TOOL_DEFINITIONS, DANGEROUS_TOOLS, execute_tool

MAX_TOOL_LOOPS = 10
MAX_HISTORY_MESSAGES = 40  # これを超えたら古いメッセージを削除

SYSTEM_PROMPT = """あなたはローカルで動作するAIコーディングアシスタントです。
ユーザーの指示に従い、ファイルの読み書き・編集・検索・シェルコマンド実行を行います。

## 重要ルール
- ファイルを編集する前に、必ず read_file で最新内容を確認すること
- edit_file の old_text には、read_file で見た内容を一字一句正確にコピーすること（空白・インデント含む）
- 日本語で応答すること
- 簡潔に、結論から伝えること"""


class Agent:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

    def run(self, user_input: str) -> None:
        """ユーザー入力を処理し、tool-useループを実行する。"""
        self.messages.append({"role": "user", "content": user_input})
        self._trim_history()

        for loop_count in range(MAX_TOOL_LOOPS):
            response = llm.chat(
                messages=self.messages,
                tools=TOOL_DEFINITIONS,
            )

            assistant_msg = response.get("message", {})
            # Ollama統計情報の出力
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            total_ns = response.get("total_duration", 0)
            eval_ns = response.get("eval_duration", 0)
            print(f"[トークン数] prompt: {prompt_tokens}, completion: {completion_tokens}")
            print(f"[生成時間] {eval_ns / 1_000_000:.0f}ms (全体: {total_ns / 1_000_000:.0f}ms)")
            # メッセージ履歴に追加
            self.messages.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls")

            if not tool_calls:
                # テキスト応答 → 表示して終了
                content = assistant_msg.get("content", "")
                if content:
                    print(f"\n{content}")
                return

            # ツール実行
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                name = func.get("name", "unknown")
                arguments = func.get("arguments", {})

                # 引数が文字列の場合はJSONとしてパース
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                # 危険なツールはユーザー確認
                if name in DANGEROUS_TOOLS:
                    if not self._confirm_tool(name, arguments):
                        self.messages.append({
                            "role": "tool",
                            "content": "[スキップ] ユーザーが実行を拒否しました",
                        })
                        continue

                # ツール名と引数を表示
                self._print_tool_call(name, arguments)

                # 実行
                result = execute_tool(name, arguments)
                print(f"  → {self._truncate(result, 200)}")

                self.messages.append({
                    "role": "tool",
                    "content": result,
                })

        print("\n[警告] ツール実行ループが上限に達しました。")

    def _confirm_tool(self, name: str, arguments: dict[str, Any]) -> bool:
        """危険なツールの実行前にユーザー確認を取る。"""
        print(f"\n  [{name}] を実行しますか？")
        for k, v in arguments.items():
            display = self._truncate(str(v), 100)
            print(f"    {k}: {display}")
        try:
            answer = input("  実行する？ (y/N): ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _print_tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        """ツール呼び出しを表示する。"""
        args_summary = ", ".join(
            f"{k}={self._truncate(str(v), 50)}" for k, v in arguments.items()
        )
        print(f"\n  > {name}({args_summary})")

    def _trim_history(self) -> None:
        """メッセージ履歴が長くなりすぎたら古いものを削除（systemは保持）。"""
        if len(self.messages) > MAX_HISTORY_MESSAGES:
            # system + 最新の MAX_HISTORY_MESSAGES - 1 件を保持
            system = self.messages[0]
            self.messages = [system] + self.messages[-(MAX_HISTORY_MESSAGES - 1):]

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """テキストを切り詰める。"""
        text = text.replace("\n", " ")
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
