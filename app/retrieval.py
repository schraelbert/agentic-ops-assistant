from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer


@dataclass
class RetrievedChunk:
    text: str
    score: float


class EmbeddingRetriever:
    def __init__(self, docs_path: str, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        raw = Path(docs_path).read_text(encoding="utf-8").strip()
        self.chunks = [c.strip() for c in raw.split("\n\n") if c.strip()]
        self.model = SentenceTransformer(model_name)
        emb = self.model.encode(self.chunks, normalize_embeddings=True)
        self.embeddings = np.asarray(emb, dtype=np.float32)

    def search(self, query: str, k: int = 3) -> List[RetrievedChunk]:
        q = self.model.encode([query], normalize_embeddings=True)
        qv = np.asarray(q[0], dtype=np.float32)
        scores = self.embeddings @ qv
        idx = np.argsort(scores)[::-1][:k]
        return [RetrievedChunk(self.chunks[i], float(scores[i])) for i in idx]
