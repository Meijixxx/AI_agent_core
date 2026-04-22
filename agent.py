"""エージェントコア: tool-use ループ"""

import difflib
import json
import os
import sys
from datetime import datetime
from typing import Any, Callable

import llm
from config import CFG
from logger import get_logger
from tools import TOOL_DEFINITIONS, DANGEROUS_TOOLS, execute_tool
from tools.file_ops import _safe_path

SYSTEM_PROMPT = """あなたはローカルで動作するAIコーディングアシスタントです。
ユーザーの指示に従い、ファイルの読み書き・編集・検索・シェルコマンド実行・git操作・URL取得・パッチ適用を行います。

## 重要ルール
- ファイルを編集する前に、必ず read_file で最新内容を確認すること
- edit_file の old_text には、read_file で見た内容を一字一句正確にコピーすること（空白・インデント含む）
- ツール実行で [エラー] が返った場合は、エラー内容を分析して原因を特定し、修正案を日本語で提示してから再試行すること
- 日本語で応答すること
- 簡潔に、結論から伝えること"""

# ANSI カラー（TTY のみ）
_COLOR_RED = "\033[31m"
_COLOR_GREEN = "\033[32m"
_COLOR_RESET = "\033[0m"


class Agent:
    def __init__(
        self,
        auto_confirm: bool = False,
        tool_executor: Callable[[str, dict[str, Any]], str] | None = None,
        progress_callback: Callable[[float], None] | None = None,
    ) -> None:
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self.stats: dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "tool_calls": 0,
            "gen_time_ms": 0,
            "start_time": datetime.now(),
        }
        # auto_confirm=True で危険ツールと編集を無確認で実行（サーバーモード用）
        self.auto_confirm = auto_confirm
        # tool_executor を差し替えることでリモート実行（クライアントで実行）に対応
        self.tool_executor: Callable[[str, dict[str, Any]], str] = tool_executor or execute_tool
        # progress_callback: LLM生成中の経過秒数を通知（サーバ→クライアント転送用）
        self.progress_callback = progress_callback
        self.logger = get_logger()
        self.logger.info(f"新規セッション開始 (auto_confirm={auto_confirm}, remote={tool_executor is not None})")

    def run(self, user_input: str) -> None:
        """ユーザー入力を処理し、tool-useループを実行する。"""
        self.logger.info(f"user: {user_input}")
        self.messages.append({"role": "user", "content": user_input})
        self._trim_history()
        self._check_token_budget()

        for loop_count in range(CFG.max_tool_loops):
            try:
                response = llm.chat(
                    messages=self.messages,
                    tools=TOOL_DEFINITIONS,
                    progress_callback=self.progress_callback,
                )
            except Exception as e:
                self.logger.error(f"LLM 呼び出しエラー: {e}")
                return

            if response is None:
                # Ctrl+C で中断
                self.logger.info("ユーザーによる中断")
                return

            assistant_msg = response.get("message", {})
            # 統計情報
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            total_ns = response.get("total_duration", 0)
            eval_ns = response.get("eval_duration", 0)
            eval_ms = eval_ns / 1_000_000
            total_ms = total_ns / 1_000_000

            self.stats["prompt_tokens"] += prompt_tokens
            self.stats["completion_tokens"] += completion_tokens
            self.stats["gen_time_ms"] += eval_ms

            print(f"[トークン数] prompt: {prompt_tokens}, completion: {completion_tokens}")
            print(f"[生成時間] {eval_ms:.0f}ms (全体: {total_ms:.0f}ms)")
            self.logger.info(
                f"llm stats: prompt={prompt_tokens} completion={completion_tokens} "
                f"eval_ms={eval_ms:.0f} total_ms={total_ms:.0f}"
            )

            self.messages.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls")

            if not tool_calls:
                content = assistant_msg.get("content", "")
                if content:
                    print(f"\n{content}")
                self.logger.info(f"assistant: {content[:200]}")
                return

            # ツール実行
            for tool_call in tool_calls:
                func = tool_call.get("function", {})
                name = func.get("name", "unknown")
                arguments = func.get("arguments", {})

                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                self.stats["tool_calls"] += 1
                self.logger.info(f"tool call: {name} args={self._truncate(str(arguments), 200)}")

                # edit_file は diff プレビュー（auto_confirm 時はスキップして自動実行）
                if name == "edit_file" and not self.auto_confirm:
                    if not self._preview_edit_diff(arguments):
                        self.messages.append({
                            "role": "tool",
                            "content": "[スキップ] ユーザーが編集を拒否しました",
                        })
                        self.logger.info("edit_file skipped by user")
                        continue

                # 危険なツールはユーザー確認（auto_confirm 時はスキップ）
                if name in DANGEROUS_TOOLS and name != "edit_file" and not self.auto_confirm:
                    if not self._confirm_tool(name, arguments):
                        self.messages.append({
                            "role": "tool",
                            "content": "[スキップ] ユーザーが実行を拒否しました",
                        })
                        self.logger.info(f"{name} skipped by user")
                        continue

                self._print_tool_call(name, arguments)

                result = self.tool_executor(name, arguments)
                print(f"  → {self._truncate(result, 200)}")
                self.logger.info(f"tool result: {self._truncate(result, 500)}")

                self.messages.append({
                    "role": "tool",
                    "content": result,
                })

        print("\n[警告] ツール実行ループが上限に達しました。")
        self.logger.warning(f"tool loop limit reached: {CFG.max_tool_loops}")

    def _preview_edit_diff(self, arguments: dict[str, Any]) -> bool:
        """edit_file 実行前に diff を表示してユーザー確認を取る。"""
        path = arguments.get("path", "")
        old_text = arguments.get("old_text", "")
        new_text = arguments.get("new_text", "")

        print(f"\n  [edit_file] {path}")

        # ファイル全体のコンテキストで diff を生成
        abs_path, err = _safe_path(path)
        if err:
            print(f"    {err}")
            return False

        if os.path.isfile(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                    current = f.read()
            except Exception as e:
                print(f"    [エラー] ファイル読み込み失敗: {e}")
                return False
            if old_text not in current:
                preview_old = old_text
                preview_new = new_text
            else:
                preview_old = current
                preview_new = current.replace(old_text, new_text, 1)
        else:
            preview_old = old_text
            preview_new = new_text

        diff = difflib.unified_diff(
            preview_old.splitlines(keepends=True),
            preview_new.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
            n=3,
        )

        is_tty = sys.stdout.isatty()
        printed_any = False
        print("  --- diff ---")
        for line in diff:
            printed_any = True
            out = line.rstrip("\n")
            if is_tty:
                if out.startswith("+") and not out.startswith("+++"):
                    out = f"{_COLOR_GREEN}{out}{_COLOR_RESET}"
                elif out.startswith("-") and not out.startswith("---"):
                    out = f"{_COLOR_RED}{out}{_COLOR_RESET}"
            print(f"  {out}")

        if not printed_any:
            print("  (差分なし)")

        try:
            answer = input("  この編集を適用する？ (y/N): ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

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
        if len(self.messages) > CFG.max_history_messages:
            system = self.messages[0]
            self.messages = [system] + self.messages[-(CFG.max_history_messages - 1):]

    def _check_token_budget(self) -> None:
        """履歴のトークン数見積もりが閾値を超えたら警告する。"""
        estimated = self._estimate_tokens(self.messages)
        threshold = int(CFG.num_ctx * CFG.token_budget_warn_ratio)
        if estimated > threshold:
            msg = f"[警告] 推定トークン数 {estimated} が上限の{int(CFG.token_budget_warn_ratio * 100)}% ({threshold}) を超えています"
            print(msg)
            self.logger.warning(msg)

    @staticmethod
    def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
        """メッセージ履歴のトークン数を粗く見積もる（1トークン≈4文字）。"""
        total = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total += len(content)
        return total // 4

    def get_stats_display(self) -> str:
        """累積統計を人間可読な文字列で返す。"""
        duration = datetime.now() - self.stats["start_time"]
        duration_sec = duration.total_seconds()
        lines = [
            "=== セッション統計 ===",
            f"  経過時間: {duration_sec:.0f}秒",
            f"  累積プロンプトトークン: {self.stats['prompt_tokens']}",
            f"  累積生成トークン: {self.stats['completion_tokens']}",
            f"  累積生成時間: {self.stats['gen_time_ms'] / 1000:.1f}秒",
            f"  ツール呼び出し数: {self.stats['tool_calls']}",
            f"  履歴メッセージ数: {len(self.messages)}",
            f"  推定トークン数: {self._estimate_tokens(self.messages)}",
        ]
        return "\n".join(lines)

    def save_session(self, path: str) -> str:
        """メッセージ履歴を JSON で保存する。"""
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            data = {
                "created": datetime.now().isoformat(timespec="seconds"),
                "messages": self.messages,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"session saved: {path}")
            return f"セッションを保存しました: {path}"
        except Exception as e:
            self.logger.error(f"session save failed: {e}")
            return f"[エラー] 保存失敗: {e}"

    def load_session(self, path: str) -> str:
        """メッセージ履歴を JSON から復元する。"""
        if not os.path.isfile(path):
            return f"[エラー] セッションファイルが見つかりません: {path}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data.get("messages")
            if not isinstance(messages, list) or not messages:
                return "[エラー] セッションファイルが不正です"
            self.messages = messages
            self.logger.info(f"session loaded: {path} ({len(messages)} messages)")
            return f"セッションを読み込みました: {path} ({len(messages)}メッセージ)"
        except Exception as e:
            self.logger.error(f"session load failed: {e}")
            return f"[エラー] 読み込み失敗: {e}"

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """テキストを切り詰める。"""
        text = text.replace("\n", " ")
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
