"""RAGツール: ドキュメントのインデックス化・検索・管理"""

import os
from pathlib import Path

from rag import get_store
from rag._settings import CHUNK_OVERLAP, CHUNK_SIZE
from rag.embedder import embed
from rag.indexer import chunk_text, read_text
from tools.file_ops import _safe_path

_INDEXABLE_SUFFIXES = {
    ".txt", ".md", ".py", ".csv", ".json", ".toml", ".yaml", ".yml",
    ".rst", ".html", ".js", ".ts", ".java", ".c", ".cpp", ".go", ".rb",
    ".pdf", ".docx",
}


def rag_index(path: str) -> str:
    """ファイルまたはディレクトリをRAGインデックスに追加する。"""
    abs_path, err = _safe_path(path)
    if err:
        return f"[エラー] {err}"

    store = get_store()

    if os.path.isfile(abs_path):
        return _index_file(abs_path, store)

    if os.path.isdir(abs_path):
        results = []
        count = 0
        for p in sorted(Path(abs_path).rglob("*")):
            if p.is_file() and p.suffix.lower() in _INDEXABLE_SUFFIXES:
                msg = _index_file(str(p), store)
                results.append(f"  {p.name}: {msg}")
                count += 1
        if count == 0:
            return f"[警告] インデックス可能なファイルが見つかりません: {path}"
        return f"{count}ファイルを処理しました\n" + "\n".join(results)

    return f"[エラー] ファイルまたはディレクトリが見つかりません: {path}"


def _index_file(abs_path: str, store) -> str:
    """単一ファイルをインデックス化する（内部用）。"""
    text = read_text(abs_path)
    if text.startswith("[エラー]"):
        return text
    if not text.strip():
        return "スキップ（空ファイル）"

    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        return "スキップ（テキスト抽出失敗）"

    removed = store.remove_source(abs_path)

    for chunk in chunks:
        try:
            vector = embed(chunk)
        except Exception as e:
            return f"[エラー] embedding失敗: {e}"
        store.add(abs_path, chunk, vector)

    store.save()
    suffix = f"（既存{removed}チャンク置き換え）" if removed else ""
    return f"{len(chunks)}チャンク追加{suffix}"


def rag_search(query: str, top_k: int = 5) -> str:
    """クエリに関連するドキュメントチャンクを検索して返す。"""
    store = get_store()
    if store.chunk_count == 0:
        return "[情報] インデックスが空です。rag_index でファイルを登録してください。"

    try:
        query_vector = embed(query)
    except Exception as e:
        return f"[エラー] クエリのembedding失敗: {e}"

    results = store.search(query_vector, top_k=min(top_k, 10))
    if not results:
        return "関連するドキュメントが見つかりませんでした。"

    lines = [f"検索結果 ({len(results)}件):"]
    for i, r in enumerate(results, 1):
        source = os.path.basename(r["source"])
        score = r["score"]
        text = r["text"][:500].replace("\n", " ")
        lines.append(f"\n[{i}] {source} (スコア: {score:.3f})\n{text}")

    return "\n".join(lines)


def rag_list() -> str:
    """インデックス済みドキュメントの一覧とチャンク数を返す。"""
    store = get_store()
    sources = store.list_sources()
    if not sources:
        return "インデックスにドキュメントがありません。"

    count_by_src: dict[str, int] = {}
    for chunk in store.chunks:
        src = chunk["source"]
        count_by_src[src] = count_by_src.get(src, 0) + 1

    lines = [f"インデックス済みドキュメント ({len(sources)}件 / 計{store.chunk_count}チャンク):"]
    for src in sources:
        name = os.path.basename(src)
        lines.append(f"  {name}: {count_by_src[src]}チャンク  [{src}]")

    return "\n".join(lines)


def rag_remove(path: str) -> str:
    """指定ファイルのチャンクをインデックスから削除する。"""
    abs_path, err = _safe_path(path)
    if err:
        return f"[エラー] {err}"
    store = get_store()
    removed = store.remove_source(abs_path)
    if removed == 0:
        return f"[情報] インデックスに登録されていません: {path}"
    return f"{removed}チャンクを削除しました: {os.path.basename(abs_path)}"


def rag_clear() -> str:
    """RAGインデックスを全て削除する。"""
    store = get_store()
    count = store.clear()
    return f"インデックスをクリアしました（{count}チャンク削除）"
