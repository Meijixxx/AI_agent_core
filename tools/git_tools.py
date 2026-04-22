"""Git ツール: status / diff / log（読み取り専用）"""

import subprocess

from tools.file_ops import _SANDBOX_ROOT

TIMEOUT = 15
MAX_OUTPUT_LINES = 200


def _get_cwd() -> str:
    # file_ops の _SANDBOX_ROOT を動的参照（set_sandbox_root 後の値を使う）
    from tools import file_ops
    return file_ops._SANDBOX_ROOT


def _run_git(args: list[str]) -> str:
    cwd = _get_cwd()
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except FileNotFoundError:
        return "[エラー] git コマンドが見つかりません"
    except subprocess.TimeoutExpired:
        return f"[タイムアウト] git コマンドが {TIMEOUT}秒 で終了しませんでした"
    except Exception as e:
        return f"[エラー] git 実行に失敗: {e}"

    output = result.stdout or ""
    if result.stderr:
        output += ("\n" if output else "") + "[stderr]\n" + result.stderr
    if result.returncode != 0:
        output += f"\n[終了コード: {result.returncode}]"

    if not output.strip():
        return "(出力なし)"

    lines = output.splitlines()
    if len(lines) > MAX_OUTPUT_LINES:
        output = "\n".join(lines[:MAX_OUTPUT_LINES]) + f"\n... ({len(lines) - MAX_OUTPUT_LINES}行省略)"
    return output


def git_status() -> str:
    """git status --short の結果を返す。"""
    return _run_git(["status", "--short"])


def git_diff(staged: bool = False, path: str = "") -> str:
    """git diff の結果を返す。staged=True でステージング済みを対象。"""
    args = ["diff"]
    if staged:
        args.append("--staged")
    if path:
        args.append("--")
        args.append(path)
    return _run_git(args)


def git_log(n: int = 10) -> str:
    """git log --oneline -n N の結果を返す。"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        n = 10
    n = max(1, min(n, 100))
    return _run_git(["log", "--oneline", "-n", str(n)])
