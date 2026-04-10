"""シェルコマンド実行ツール（セキュリティ強化版）"""

import shlex
import subprocess
import sys

# 明確に危険なコマンドパターン（小文字で比較）
BLOCKED_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "rm -rf .",
    "format c:",
    "format d:",
    "mkfs",
    ":(){:|:&};:",  # fork bomb
    "dd if=/dev/zero",
    "dd if=/dev/random",
    "> /dev/sd",
    "chmod -r 777 /",
    "shutdown",
    "reboot",
    "init 0",
    "init 6",
]

# シェルメタ文字の警告対象
SHELL_META_CHARS = set(";&|`$(){}!")

TIMEOUT_SECONDS = 30


def run_command(command: str) -> str:
    """シェルコマンドを実行して結果を返す。

    セキュリティ対策:
    - 危険パターンのブロックリスト
    - シェルメタ文字を含む場合は警告表示
    - タイムアウト強制
    - 出力サイズ制限
    """
    cmd_stripped = command.strip()
    if not cmd_stripped:
        return "[エラー] 空のコマンドです"

    # 危険パターンチェック
    cmd_lower = cmd_stripped.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return f"[ブロック] 危険なコマンドのため実行を拒否しました: {command}"

    # シェルメタ文字の検出・警告（agent.pyの確認プロンプトで表示される）
    meta_found = SHELL_META_CHARS.intersection(set(cmd_stripped))
    warning = ""
    if meta_found:
        warning = f"[注意] シェルメタ文字を含みます: {' '.join(sorted(meta_found))}\n"

    try:
        # Windows / Unix 両対応
        if sys.platform == "win32":
            result = subprocess.run(
                cmd_stripped,
                shell=True,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
            )
        else:
            # Unix: shlex.split でトークン化し、shell=False で実行（安全）
            # パイプ等のシェル機能が必要な場合のみ shell=True にフォールバック
            if meta_found:
                result = subprocess.run(
                    cmd_stripped,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS,
                )
            else:
                try:
                    args = shlex.split(cmd_stripped)
                    result = subprocess.run(
                        args,
                        shell=False,
                        capture_output=True,
                        text=True,
                        timeout=TIMEOUT_SECONDS,
                    )
                except ValueError:
                    # shlex.splitに失敗した場合はshellで実行
                    result = subprocess.run(
                        cmd_stripped,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=TIMEOUT_SECONDS,
                    )

        output = warning
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += f"[stderr]\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n[終了コード: {result.returncode}]"

        if not output.strip():
            output = "(出力なし)"

        # 出力サイズ制限
        lines = output.splitlines()
        if len(lines) > 200:
            output = "\n".join(lines[:200]) + f"\n\n... ({len(lines)} 行中、200行を表示)"

        return output
    except subprocess.TimeoutExpired:
        return f"[タイムアウト] コマンドが {TIMEOUT_SECONDS} 秒以内に完了しませんでした"
    except Exception as e:
        return f"[エラー] コマンド実行失敗: {e}"
