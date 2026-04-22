"""RAGベクトルストア: チャンクの保存・検索・管理"""

import json
from pathlib import Path
from typing import Any

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


class RAGStore:
    """チャンクとベクトルをJSONで永続化し、コサイン類似度で検索するストア。"""

    def __init__(self, store_dir: str) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.data_path = self.store_dir / "chunks.json"
        self.chunks: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.data_path.exists():
            try:
                self.chunks = json.loads(self.data_path.read_text(encoding="utf-8"))
            except Exception:
                self.chunks = []

    def save(self) -> None:
        self.data_path.write_text(
            json.dumps(self.chunks, ensure_ascii=False),
            encoding="utf-8",
        )

    def add(self, source: str, text: str, vector: list[float]) -> None:
        self.chunks.append({"source": source, "text": text, "vector": vector})

    def remove_source(self, source: str) -> int:
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["source"] != source]
        self.save()
        return before - len(self.chunks)

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        if _HAS_NUMPY:
            return self._search_numpy(query_vector, top_k)
        return self._search_pure(query_vector, top_k)

    def _search_numpy(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        vectors = np.array([c["vector"] for c in self.chunks], dtype=np.float32)
        qv = np.array(query_vector, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1) * np.linalg.norm(qv) + 1e-9
        sims = (vectors @ qv) / norms
        top_idx = np.argsort(-sims)[:top_k]
        return [
            {
                "source": self.chunks[i]["source"],
                "text": self.chunks[i]["text"],
                "score": float(sims[i]),
            }
            for i in top_idx
            if sims[i] > 0
        ]

    def _search_pure(self, query_vector: list[float], top_k: int) -> list[dict[str, Any]]:
        qnorm = sum(x * x for x in query_vector) ** 0.5
        results = []
        for chunk in self.chunks:
            cv = chunk["vector"]
            dot = sum(a * b for a, b in zip(query_vector, cv))
            cnorm = sum(x * x for x in cv) ** 0.5
            sim = dot / (qnorm * cnorm + 1e-9)
            results.append((sim, chunk))
        results.sort(key=lambda x: -x[0])
        return [
            {"source": r["source"], "text": r["text"], "score": round(sim, 4)}
            for sim, r in results[:top_k]
            if sim > 0
        ]

    def list_sources(self) -> list[str]:
        return sorted(set(c["source"] for c in self.chunks))

    def clear(self) -> int:
        count = len(self.chunks)
        self.chunks = []
        self.save()
        return count

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
