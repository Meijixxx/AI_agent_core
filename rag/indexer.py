"""ファイル読み込みとテキストチャンキング"""

import re
from pathlib import Path


def read_text(path: str) -> str:
    """ファイルをテキストとして読む。.pdf/.docx は追加ライブラリが必要。"""
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in {".txt", ".md", ".py", ".csv", ".json", ".toml", ".yaml", ".yml",
                  ".rst", ".html", ".xml", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rb"}:
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[エラー] ファイル読み込み失敗: {e}"

    if suffix == ".pdf":
        try:
            from pdfminer.high_level import extract_text  # type: ignore
            return extract_text(str(p)) or ""
        except ImportError:
            return "[エラー] PDF読み込みには pdfminer.six が必要です: pip install pdfminer.six"
        except Exception as e:
            return f"[エラー] PDF読み込み失敗: {e}"

    if suffix == ".docx":
        try:
            import docx  # type: ignore
            doc = docx.Document(str(p))
            return "\n".join(para.text for para in doc.paragraphs if para.text.strip())
        except ImportError:
            return "[エラー] docx読み込みには python-docx が必要です: pip install python-docx"
        except Exception as e:
            return f"[エラー] docx読み込み失敗: {e}"

    # フォールバック: UTF-8テキストとして読む
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"[エラー] ファイル読み込み失敗: {e}"


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """テキストを重複ありでチャンクに分割する。"""
    # 段落単位で区切ってからマージ
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            # 段落自体が大きい場合は強制分割
            if len(para) > chunk_size:
                for i in range(0, len(para), chunk_size - overlap):
                    piece = para[i : i + chunk_size]
                    if piece.strip():
                        chunks.append(piece.strip())
                current = ""
            else:
                current = para

    if current:
        chunks.append(current)

    # 極端に短いチャンクは除外
    return [c for c in chunks if len(c) >= 20]
