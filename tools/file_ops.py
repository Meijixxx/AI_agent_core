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
    """ファイルを読み取って内容を返す。.pdf/.docx は専用ライブラリで抽出。"""
    abs_path, err = _safe_path(path)
    if err:
        return err
    if not os.path.isfile(abs_path):
        return f"[エラー] ファイルが見つかりません: {abs_path}"

    ext = os.path.splitext(abs_path)[1].lower()
    try:
        if ext == ".pdf":
            try:
                from pdfminer.high_level import extract_text
            except ImportError:
                return "[エラー] PDF読み込みには pdfminer.six が必要です: pip install pdfminer.six"
            content = extract_text(abs_path) or ""
        elif ext == ".docx":
            try:
                import docx  # type: ignore
            except ImportError:
                return "[エラー] docx読み込みには python-docx が必要です: pip install python-docx"
            doc = docx.Document(abs_path)
            content = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
    except Exception as e:
        return f"[エラー] ファイル読み取り失敗: {e}"

    lines = content.splitlines()
    if len(lines) > 500:
        truncated = "\n".join(lines[:500])
        return f"{truncated}\n\n... ({len(lines)} 行中、先頭500行を表示)"
    return content


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


def append_file(path: str, content: str) -> str:
    """ファイル末尾に追記する（ファイルが無ければ新規作成）。

    大きなドキュメントをチャンク単位で書き出すときに使う。
    """
    abs_path, err = _safe_path(path)
    if err:
        return err
    try:
        parent = os.path.dirname(abs_path)
        if parent and not parent.startswith(_SANDBOX_ROOT):
            return f"[拒否] サンドボックス外にディレクトリは作成できません"
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(content)
        total = os.path.getsize(abs_path)
        return f"追記しました: {abs_path} (+{len(content)} bytes → {total:,} bytes)"
    except Exception as e:
        return f"[エラー] 追記失敗: {e}"


def get_pdf_info(path: str) -> str:
    """PDFのページ数などメタ情報を返す。"""
    abs_path, err = _safe_path(path)
    if err:
        return err
    if not os.path.isfile(abs_path):
        return f"[エラー] ファイルが見つかりません: {abs_path}"
    if os.path.splitext(abs_path)[1].lower() != ".pdf":
        return f"[エラー] PDFファイルではありません: {path}"
    try:
        from pdfminer.pdfpage import PDFPage  # type: ignore
    except ImportError:
        return "[エラー] pdfminer.six が必要です: pip install pdfminer.six"
    try:
        with open(abs_path, "rb") as f:
            count = sum(1 for _ in PDFPage.get_pages(f))
        size = os.path.getsize(abs_path)
        return f"PDF情報 [{os.path.basename(abs_path)}]\n  ページ数: {count}\n  サイズ: {size:,} bytes"
    except Exception as e:
        return f"[エラー] PDF解析失敗: {e}"


def read_pdf_pages(path: str, start_page: int = 1, end_page: int | None = None) -> str:
    """PDFの指定ページ範囲のテキストを返す（1始まり、truncateなし）。

    end_page 省略時は start_page のみ1ページ分を返す。
    50ページ級の大きなPDFを分割して処理する用途に使う。
    """
    abs_path, err = _safe_path(path)
    if err:
        return err
    if not os.path.isfile(abs_path):
        return f"[エラー] ファイルが見つかりません: {abs_path}"
    if os.path.splitext(abs_path)[1].lower() != ".pdf":
        return f"[エラー] PDFファイルではありません: {path}"
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except ImportError:
        return "[エラー] pdfminer.six が必要です: pip install pdfminer.six"

    if end_page is None:
        end_page = start_page
    if start_page < 1:
        start_page = 1
    if end_page < start_page:
        return f"[エラー] end_page ({end_page}) は start_page ({start_page}) 以上にしてください"

    # pdfminer の page_numbers は 0 始まり
    page_numbers = list(range(start_page - 1, end_page))
    try:
        content = extract_text(abs_path, page_numbers=page_numbers) or ""
    except Exception as e:
        return f"[エラー] PDF読み込み失敗: {e}"
    header = f"[PDF ページ {start_page}-{end_page}]\n"
    return header + content


def _compute_chunks(text: str, max_chars: int) -> list[tuple[int, int, str]]:
    """テキストを整形しやすい境界で分割する。

    境界判定:
      - 段落境界（空行）で分割
      - コードブロック（``` で囲まれた範囲）内では分割しない
      - 表（連続する | で始まる行）内では分割しない

    Returns: [(start_line_1idx, end_line_1idx, content), ...]
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    chunks: list[tuple[int, int, str]] = []
    start = 0
    size = 0
    in_code = False

    i = 0
    while i < len(lines):
        line = lines[i]
        size += len(line)
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code

        is_blank = stripped == ""
        # 表の途中かどうか: 前後の非空行が `|` で始まるかで判定
        in_table = False
        if is_blank and not in_code:
            # 前後の非空行がともに | で始まるなら表の途中の空行と見なす（通常は無いが念のため）
            prev = next((lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()), "")
            nxt = next((lines[j].strip() for j in range(i + 1, len(lines)) if lines[j].strip()), "")
            if prev.startswith("|") and nxt.startswith("|"):
                in_table = True

        can_split = is_blank and not in_code and not in_table and size >= max_chars

        if can_split:
            content = "".join(lines[start : i + 1])
            chunks.append((start + 1, i + 1, content))
            start = i + 1
            size = 0

        i += 1

    if start < len(lines):
        content = "".join(lines[start:])
        chunks.append((start + 1, len(lines), content))

    return chunks


def read_file_chunk(path: str, chunk_index: int = 0, max_chars: int = 5000) -> str:
    """ファイルを段落/コードブロック境界で分割し、N番目のチャンクを返す（0始まり）。

    大きなmdやテキストファイルをLLMで整形する際、ページ単位ではなく
    構造を壊さない境界で区切って処理するために使う。
    デフォルト max_chars=5000（約1.2K tokens相当）。入力は大きく取れても
    出力トークン上限で整形結果が途切れやすいので、チャンクは小さめ推奨。
    最後のチャンクより後を指定すると [EOF] を返す。
    """
    abs_path, err = _safe_path(path)
    if err:
        return err
    if not os.path.isfile(abs_path):
        return f"[エラー] ファイルが見つかりません: {abs_path}"

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return f"[エラー] 読み取り失敗: {e}"

    chunks = _compute_chunks(text, max_chars)
    total = len(chunks)

    if total == 0:
        return "[EOF] ファイルが空です"
    if chunk_index < 0:
        return f"[エラー] chunk_index は 0 以上を指定してください（0..{total-1}）"
    if chunk_index >= total:
        return f"[EOF] 全{total}チャンク完了（chunk_index={chunk_index} は範囲外）"

    start, end, content = chunks[chunk_index]
    header = f"[チャンク {chunk_index + 1}/{total}] 行 {start}-{end} ({len(content):,} chars)\n"
    return header + content


def pdf_to_markdown(pdf_path: str, output_path: str) -> str:
    """PDFの全テキストを抽出してファイルに書き出す（LLMを経由しない）。

    大きなPDFを.mdに変換する用途では、LLMに繰り返し転記させると
    要約やハルシネーションが発生する。このツールはpdfminerが抽出した
    テキストをそのままファイルに書き込むため、内容の改変が起きない。

    出力は「元文書そのまま」。見出しや表の美しい整形は行われない。
    整形が必要な場合は、生成後に特定セクションだけLLMに頼むとよい。
    """
    abs_pdf, err = _safe_path(pdf_path)
    if err:
        return err
    if not os.path.isfile(abs_pdf):
        return f"[エラー] ファイルが見つかりません: {abs_pdf}"
    if os.path.splitext(abs_pdf)[1].lower() != ".pdf":
        return f"[エラー] PDFファイルではありません: {pdf_path}"

    abs_out, err = _safe_path(output_path)
    if err:
        return err

    try:
        from pdfminer.high_level import extract_text  # type: ignore
        from pdfminer.pdfpage import PDFPage  # type: ignore
    except ImportError:
        return "[エラー] pdfminer.six が必要です: pip install pdfminer.six"

    try:
        with open(abs_pdf, "rb") as f:
            page_count = sum(1 for _ in PDFPage.get_pages(f))
    except Exception as e:
        return f"[エラー] PDF解析失敗: {e}"

    try:
        text = extract_text(abs_pdf) or ""
    except Exception as e:
        return f"[エラー] PDFテキスト抽出失敗: {e}"

    try:
        parent = os.path.dirname(abs_out)
        if parent and not parent.startswith(_SANDBOX_ROOT):
            return "[拒否] サンドボックス外への書き込みです"
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(abs_out, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:
        return f"[エラー] 書き込み失敗: {e}"

    size = os.path.getsize(abs_out)
    return f"PDF→テキスト変換完了: {abs_out} ({page_count}ページ, {size:,} bytes)"


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
