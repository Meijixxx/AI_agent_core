"""Unified diff を適用する apply_patch ツール"""

import re
import subprocess
import tempfile

from tools.file_ops import _safe_path

TIMEOUT = 15


def _extract_targets(diff_text: str) -> list[str]:
    """diff 内の `+++ b/xxx` や `+++ xxx` からターゲットファイル一覧を抽出。"""
    targets: list[str] = []
    for line in diff_text.splitlines():
        m = re.match(r"^\+\+\+\s+(?:b/)?(.+?)(?:\t.*)?$", line)
        if m:
            path = m.group(1).strip()
            if path and path != "/dev/null":
                targets.append(path)
    return targets


def apply_patch(diff_text: str) -> str:
    """Unified diff を patch コマンドで適用する。

    1. diff から対象ファイルを抽出
    2. 各ファイルをサンドボックス検証
    3. patch --dry-run で事前検証
    4. OK なら本実行
    """
    if not diff_text or not diff_text.strip():
        return "[エラー] diff_text が空です"

    targets = _extract_targets(diff_text)
    if not targets:
        return "[エラー] diff から対象ファイルを検出できませんでした（`+++ b/path` 形式が必要）"

    # サンドボックス検証
    for t in targets:
        _, err = _safe_path(t)
        if err:
            return err

    # 一時ファイルに diff を書き出す
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False, encoding="utf-8") as f:
            f.write(diff_text)
            patch_file = f.name
    except Exception as e:
        return f"[エラー] 一時ファイル作成に失敗: {e}"

    try:
        # dry-run
        try:
            dry = subprocess.run(
                ["patch", "-p1", "--dry-run", "-i", patch_file],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except FileNotFoundError:
            return "[エラー] patch コマンドが見つかりません"
        except subprocess.TimeoutExpired:
            return "[タイムアウト] patch --dry-run が時間内に終了しませんでした"

        if dry.returncode != 0:
            return f"[エラー] patch --dry-run 失敗:\n{dry.stdout}\n{dry.stderr}"

        # 本実行
        try:
            real = subprocess.run(
                ["patch", "-p1", "-i", patch_file],
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return "[タイムアウト] patch 適用が時間内に終了しませんでした"

        if real.returncode != 0:
            return f"[エラー] patch 適用失敗:\n{real.stdout}\n{real.stderr}"

        applied_list = "\n".join(f"  - {t}" for t in targets)
        return f"patch を適用しました ({len(targets)}ファイル):\n{applied_list}\n{real.stdout.strip()}"
    finally:
        try:
            import os as _os
            _os.unlink(patch_file)
        except Exception:
            pass
