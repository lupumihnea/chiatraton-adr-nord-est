"""Dense multilingual retrieval with lexical/structured recall guards."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from uuid import UUID

import numpy as np

from AI.document_parser import ParsedDocument


SEED_QUERIES = (
    "obligații asumate de beneficiar termene monitorizare proiect",
    "indicator de etapă criteriu de validare termen documente dovezi",
    "plan de monitorizare indicator realizare rezultat țintă",
    "angajament criteriu selecție punctaj selectat",
    "locuri de muncă salariați lucrători defavorizați menținere",
    "contribuția proprie solicitant procent cheltuieli eligibile",
    "achiziție contract furnizare recepție punere în funcțiune termen",
    "cerere de plată rambursare prefinanțare dată depunere",
    "raport progres raport final termen transmitere",
    "durabilitate vizibilitate publicitate DNSH conflict de interese",
)

FORCE_SIGNALS = re.compile(
    r"(Punctaj\s*:\s*Selectat|Selectat[ăa]\s*:|Plan de monitorizare|"
    r"indicator de etapă|RCO0[12]|RCR02|Contribuția solicitantului|"
    r"numărului mediu de salariați|lucrătorilor defavorizați|"
    r"locuri de muncă|Graficul cererilor|Dată depunere\s*estimat|"
    r"Cerere de plată|Cerere de rambursare|Plan de achiziții|"
    r"Raportul de progres final|raport de durabilitate)",
    re.IGNORECASE,
)

LEXICAL_SIGNALS = re.compile(
    r"\b(oblig\w*|trebuie|se angajeaz\w*|asum\w*|mențin\w*|termen\w*|"
    r"până la|indicator\w*|criteri\w*|transmit\w*|depun\w*|realiz\w*|"
    r"respect\w*|doved\w*|raport\w*|achizi\w*|ramburs\w*|prefinanț\w*|"
    r"plată|salariaț\w*|defavorizat\w*|contribuți\w*|punctaj|DNSH|"
    r"durabil\w*|vizibilitate|publicitate|de minimis)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Chunk:
    document_id: UUID
    page_number: int
    start: int
    end: int
    text: str
    category: str = "document"


def chunk_documents(
    documents: tuple[ParsedDocument, ...],
    *,
    category_by_document: dict[UUID, str] | None = None,
    max_chars: int = 1600,
    overlap: int = 180,
) -> tuple[Chunk, ...]:
    chunks: list[Chunk] = []
    category_by_document = category_by_document or {}
    for document in documents:
        for page in document.pages:
            text = page.text
            start = 0
            while start < len(text):
                end = min(start + max_chars, len(text))
                if end < len(text):
                    boundary = max(
                        text.rfind("\n", start + max_chars // 2, end),
                        text.rfind(". ", start + max_chars // 2, end),
                    )
                    if boundary > start:
                        end = boundary + 1
                raw = text[start:end]
                left = len(raw) - len(raw.lstrip())
                right = len(raw.rstrip())
                actual_start = start + left
                actual_end = start + right
                if actual_end > actual_start:
                    chunks.append(
                        Chunk(
                            document_id=document.document_id,
                            page_number=page.page_number,
                            start=actual_start,
                            end=actual_end,
                            text=text[actual_start:actual_end],
                            category=category_by_document.get(document.document_id, "document"),
                        )
                    )
                if end >= len(text):
                    break
                start = max(end - overlap, start + 1)
    return tuple(chunks)


class MultilingualDenseRetriever:
    """Sentence-transformer retrieval; no TF-IDF/character-ngram fallback."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or os.getenv(
            "LOCAL_EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
        )
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional AI extra
            raise RuntimeError(
                "Install the 'ai' extra: sentence-transformers is required for semantic retrieval"
            ) from exc
        try:
            self._model = SentenceTransformer(self.model_name, local_files_only=True)
        except OSError:
            self._model = SentenceTransformer(self.model_name)

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(
            [f"passage: {text}" for text in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_query(self, query: str) -> np.ndarray:
        vector = self._model.encode(
            [f"query: {query}"],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]
        return np.asarray(vector, dtype=np.float32)


class ChunkIndex:
    def __init__(self, chunks: tuple[Chunk, ...], embedder: MultilingualDenseRetriever) -> None:
        self.chunks = chunks
        self._embedder = embedder
        self._matrix = (
            embedder.encode_passages([chunk.text for chunk in chunks])
            if chunks
            else np.zeros((0, 1), dtype=np.float32)
        )

    def top(self, query: str, *, k: int, category: str | None = None) -> list[Chunk]:
        if not self.chunks or k <= 0:
            return []
        indices = [
            index
            for index, chunk in enumerate(self.chunks)
            if category is None or chunk.category == category
        ]
        if not indices:
            return []
        query_vector = self._embedder.encode_query(query)
        scores = self._matrix[indices] @ query_vector
        order = np.argsort(scores)[::-1][:k]
        return [self.chunks[indices[int(position)]] for position in order]

    def extraction_candidates(
        self,
        *,
        max_per_document: int = 32,
        top_k_per_query: int = 8,
    ) -> list[Chunk]:
        by_doc: dict[UUID, dict[tuple[int, int, int], tuple[float, Chunk]]] = {}
        for query in SEED_QUERIES:
            vector = self._embedder.encode_query(query)
            for document_id in {chunk.document_id for chunk in self.chunks}:
                indices = [
                    index
                    for index, chunk in enumerate(self.chunks)
                    if chunk.document_id == document_id
                ]
                if not indices:
                    continue
                scores = self._matrix[indices] @ vector
                order = np.argsort(scores)[::-1][:top_k_per_query]
                bucket = by_doc.setdefault(document_id, {})
                for position in order:
                    index = indices[int(position)]
                    chunk = self.chunks[index]
                    key = (chunk.page_number, chunk.start, chunk.end)
                    score = float(scores[int(position)])
                    current = bucket.get(key)
                    if current is None or score > current[0]:
                        bucket[key] = (score, chunk)

        for chunk in self.chunks:
            bucket = by_doc.setdefault(chunk.document_id, {})
            key = (chunk.page_number, chunk.start, chunk.end)
            if FORCE_SIGNALS.search(chunk.text):
                bucket[key] = (1.5, chunk)
            elif LEXICAL_SIGNALS.search(chunk.text) and key not in bucket:
                bucket[key] = (0.62, chunk)

        selected: list[Chunk] = []
        for document_id in sorted(by_doc, key=str):
            ranked = sorted(by_doc[document_id].values(), key=lambda item: item[0], reverse=True)
            selected.extend(chunk for _, chunk in ranked[:max_per_document])
        return selected
