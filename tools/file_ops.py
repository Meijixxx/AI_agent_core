"""ファイル操作ツール（サンドボックス付き）"""

import glob as glob_mod
import os
import re

# サンドボックス: 作業ディレクトリ配下のみ操作可能
_SANDBOX_ROOT: str = os.path.abspath(".")


def set_sandbox_root(path: str) -> None:
    """サンドボックスのルートディレクトリを設定する。"""
    global _SANDBOX_ROOT
    _SANDBOX_ROOT = os.path.abspath(path)


def _safe_path(path: str) -> tuple[str, str | None]:
    """パスを正規化し、サンドボックス内であることを検証する。

    Returns:
        (正規化パス, エラーメッセージ or None)
    """
    path = os.path.expanduser(path)
    abs_path = os.path.abspath(path)

    # サンドボックス外へのアクセスを拒否
    if not abs_path.startswith(_SANDBOX_ROOT + os.sep) and abs_path != _SANDBOX_ROOT:
        return abs_path, f"[拒否] サンドボックス外のパスです: {abs_path} (許可範囲: {_SANDBOX_ROOT})"

    return abs_path, None


def read_file(path: str) -> str:
    """ファイルを読み取って内容を返す。"""
    abs_path, err = _safe_path(path)
    if err:
        return err
    if not os.path.isfile(abs_path):
        return f"[エラー] ファイルが見つかりません: {abs_path}"
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        lines = content.splitlines()
        if len(lines) > 500:
            truncated = "\n".join(lines[:500])
            return f"{truncated}\n\n... ({len(lines)} 行中、先頭500行を表示)"
        return content
    except Exception as e:
        return f"[エラー] ファイル読み取り失敗: {e}"


def write_file(path: str, content: str) -> str:
    """ファイルを作成または上書きする。"""
    abs_path, err = _safe_path(path)
    if err:
        return err
    try:
        parent = os.path.dirname(abs_path)
        # 親ディレクトリもサンドボックス内か確認
        if not parent.startswith(_SANDBOX_ROOT):
            return f"[拒否] サンドボックス外にディレクトリは作成できません"
        os.makedirs(parent, exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"ファイルを書き込みました: {abs_path} ({len(content)} bytes)"
    except Exception as e:
        return f"[エラー] ファイル書き込み失敗: {e}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    """ファイル内のテキストを置換する。

    完全一致 → 正規化マッチ（空白揺れ吸収） → 部分行マッチの順で試行する。
    """
    abs_path, err = _safe_path(path)
    if err:
        return err
    if not os.path.isfile(abs_path):
        return f"[エラー] ファイルが見つかりません: {abs_path}"
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()

        # --- Phase 1: 完全一致 ---
        if old_text in content:
            count = content.count(old_text)
            new_content = content.replace(old_text, new_text, 1)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            msg = f"ファイルを編集しました: {abs_path}"
            if count > 1:
                msg += f" (一致 {count} 箇所中、最初の1箇所を置換)"
            return msg

        # --- Phase 2: 正規化マッチ（前後空白・連続空白を正規化して比較） ---
        def normalize(s: str) -> str:
            return re.sub(r'[ \t]+', ' ', s).strip()

        old_lines = old_text.splitlines()
        content_lines = content.splitlines()

        if len(old_lines) >= 1:
            old_normalized = [normalize(l) for l in old_lines]
            for start_idx in range(len(content_lines) - len(old_lines) + 1):
                window = content_lines[start_idx:start_idx + len(old_lines)]
                window_normalized = [normalize(l) for l in window]
                if old_normalized == window_normalized:
                    # 正規化で一致 → 元の行を置換
                    new_lines = new_text.splitlines()
                    result_lines = content_lines[:start_idx] + new_lines + content_lines[start_idx + len(old_lines):]
                    new_content = "\n".join(result_lines)
                    if content.endswith("\n"):
                        new_content += "\n"
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    return f"ファイルを編集しました（空白正規化マッチ）: {abs_path}"

        # --- Phase 3: 失敗時の診断情報 ---
        # old_text の最初の行に最も近い行を探して表示する
        first_old_line = normalize(old_lines[0]) if old_lines else ""
        candidates: list[str] = []
        for i, line in enumerate(content_lines):
            if first_old_line and _similarity(normalize(line), first_old_line) > 0.6:
                candidates.append(f"  L{i+1}: {line.rstrip()}")

        diag = "[エラー] 置換対象のテキストが見つかりません\n"
        diag += f"  検索テキスト(1行目): '{old_lines[0].rstrip()}'\n" if old_lines else ""
        if candidates:
            diag += "  類似行:\n" + "\n".join(candidates[:5])
        else:
            diag += "  類似行: なし（read_fileで最新の内容を確認してください）"
        return diag
    except Exception as e:
        return f"[エラー] ファイル編集失敗: {e}"



def _similarity(a: str, b: str) -> float:
    """2つの文字列の類似度を返す（0.0～1.0）。簡易Jaccard係数。"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    set_a = set(a.split())
    set_b = set(b.split())
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


def list_files(directory: str = ".", pattern: str = "*") -> str:
    """ディレクトリ内のファイルをglob検索する。"""
    abs_dir, err = _safe_path(directory)
    if err:
        return err
    if not os.path.isdir(abs_dir):
        return f"[エラー] ディレクトリが見つかりません: {abs_dir}"

    full_pattern = os.path.join(abs_dir, pattern)
    matches = sorted(glob_mod.glob(full_pattern, recursive=True))

    # サンドボックス外の結果をフィルタリング
    matches = [m for m in matches if os.path.abspath(m).startswith(_SANDBOX_ROOT)]

    if not matches:
        return f"パターン '{pattern}' に一致するファイルはありません"

    if len(matches) > 100:
        result = "\n".join(matches[:100])
        return f"{result}\n\n... (全 {len(matches)} 件中、100件を表示)"
    return "\n".join(matches)


def search_files(pattern: str, directory: str = ".") -> str:
    """ファイル内容をパターン検索する（簡易grep）。"""
    abs_dir, err = _safe_path(directory)
    if err:
        return err
    if not os.path.isdir(abs_dir):
        return f"[エラー] ディレクトリが見つかりません: {abs_dir}"

    results: list[str] = []
    max_results = 50
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"[エラー] 正規表現が不正です: {e}"

    for root, _dirs, files in os.walk(abs_dir):
        # サンドボックス外をスキップ
        if not os.path.abspath(root).startswith(_SANDBOX_ROOT):
            continue
        _dirs[:] = [
            d for d in _dirs
            if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".venv", "venv")
        ]
        for fname in files:
            if fname.startswith("."):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append(f"{fpath}:{i}: {line.rstrip()}")
                            if len(results) >= max_results:
                                return "\n".join(results) + f"\n\n... ({max_results}件で打ち切り)"
            except (OSError, UnicodeDecodeError):
                continue

    if not results:
        return f"パターン '{pattern}' に一致する行はありません"
    return "\n".join(results)
