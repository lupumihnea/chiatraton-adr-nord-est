"""Dense multilingual retrieval with lexical/structured recall guards."""

from __future__ import annotations

import hashlib
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
    "angajarea a trei persoane dintre care o persoană defavorizată implementare",
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
    r"angajarea\s+a\s+\d+|defavorizat\w*|"
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
    kind: str = "text"
    # For structured representations, this is the canonical exact substring
    # from the original document. ``text`` may be richer/synthetic for semantic
    # retrieval, but provenance must never use that synthetic representation.
    source_text: str | None = None


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
        page_by_number = {page.page_number: page for page in document.pages}
        for page in document.pages:
            category = category_by_document.get(document.document_id, "document")

            # Structured blocks are complete table rows / explicitly selected
            # scoring options.  Keep them atomic so row-column relationships are
            # never destroyed by the generic character chunker.
            for block in page.blocks:
                block_text = block.text.strip()
                # A structured representation without a mechanically recoverable
                # canonical source would violate the grounding invariant. The raw
                # page is still chunked below (except selected-option pages, where
                # every accepted option has an exact source substring).
                source_page_number = block.source_page_number or page.page_number
                if block.kind in {"table_row", "selected_option"}:
                    canonical_page = page_by_number.get(source_page_number)
                    if (
                        not block.source_text
                        or canonical_page is None
                        or block.source_text not in canonical_page.text
                    ):
                        continue
                if block_text:
                    chunks.append(
                        Chunk(
                            document_id=document.document_id,
                            page_number=source_page_number,
                            start=0,
                            end=len(block_text),
                            text=block_text,
                            category=category,
                            kind=block.kind,
                            source_text=block.source_text,
                        )
                    )

            # On MySMIS ``Tip: OPTIUNI`` pages, raw text contains both selected
            # and explicitly unselected alternatives.  The parser already built
            # selected_option blocks, so suppress the raw page for extraction /
            # retrieval to prevent false obligations from re-entering downstream.
            if page.prefer_structured:
                continue

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
                            category=category,
                            kind="text",
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
        # Keep the embedding worker from monopolising every CPU core in the
        # same process as FastAPI. This improves API responsiveness during the
        # first extraction on Windows laptops.
        try:
            import torch
            torch.set_num_threads(
                max(1, int(os.getenv("LOCAL_EMBEDDING_THREADS", "4")))
            )
        except (ImportError, RuntimeError, ValueError):
            pass

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
        # Repeated report analyses reuse baseline documents. Caching exact text
        # embeddings avoids re-encoding unchanged chunks without changing any
        # retrieval score or candidate set. The adapter serializes retrieval,
        # so this small in-process cache needs no extra concurrency layer.
        self._passage_cache: dict[str, np.ndarray] = {}
        self._query_cache: dict[str, np.ndarray] = {}

    @staticmethod
    def _text_key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1), dtype=np.float32)
        keys = [self._text_key(text) for text in texts]
        missing_order: list[str] = []
        missing_texts: list[str] = []
        seen_missing: set[str] = set()
        for key, text in zip(keys, texts, strict=False):
            if key not in self._passage_cache and key not in seen_missing:
                seen_missing.add(key)
                missing_order.append(key)
                missing_texts.append(text)
        if missing_texts:
            vectors = self._model.encode(
                [f"passage: {text}" for text in missing_texts],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            if len(self._passage_cache) + len(missing_order) > 20_000:
                self._passage_cache.clear()
            for key, vector in zip(missing_order, vectors, strict=False):
                self._passage_cache[key] = np.asarray(vector, dtype=np.float32)
        return np.vstack([self._passage_cache[key] for key in keys]).astype(
            np.float32, copy=False
        )

    def encode_queries(self, queries: list[str]) -> np.ndarray:
        if not queries:
            return np.zeros((0, 1), dtype=np.float32)
        missing = [query for query in dict.fromkeys(queries) if query not in self._query_cache]
        if missing:
            vectors = self._model.encode(
                [f"query: {query}" for query in missing],
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            if len(self._query_cache) + len(missing) > 1024:
                self._query_cache.clear()
            for query, vector in zip(missing, vectors, strict=False):
                self._query_cache[query] = np.asarray(vector, dtype=np.float32)
        return np.vstack([self._query_cache[query] for query in queries]).astype(
            np.float32, copy=False
        )

    def encode_query(self, query: str) -> np.ndarray:
        return self.encode_queries([query])[0]


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
        max_per_document: int = 40,
        top_k_per_query: int = 8,
    ) -> list[Chunk]:
        by_doc: dict[UUID, dict[tuple[int, int, int, str], tuple[float, Chunk]]] = {}
        document_ids = {chunk.document_id for chunk in self.chunks}
        indices_by_doc = {
            document_id: [
                index
                for index, chunk in enumerate(self.chunks)
                if chunk.document_id == document_id
            ]
            for document_id in document_ids
        }

        encode_queries = getattr(self._embedder, "encode_queries", None)
        if callable(encode_queries):
            query_vectors = encode_queries(list(SEED_QUERIES))
        else:
            query_vectors = np.vstack(
                [self._embedder.encode_query(query) for query in SEED_QUERIES]
            )

        # Encode all seed queries in one batch when supported; the ranking itself
        # is identical to running them one-by-one.
        for vector in query_vectors:
            for document_id, indices in indices_by_doc.items():
                if not indices:
                    continue
                scores = self._matrix[indices] @ vector
                order = np.argsort(scores)[::-1][:top_k_per_query]
                bucket = by_doc.setdefault(document_id, {})
                for position in order:
                    index = indices[int(position)]
                    chunk = self.chunks[index]
                    key = (chunk.page_number, chunk.start, chunk.end, chunk.kind)
                    score = float(scores[int(position)])
                    current = bucket.get(key)
                    if current is None or score > current[0]:
                        bucket[key] = (score, chunk)

        mandatory_by_doc: dict[UUID, set[tuple[int, int, int, str]]] = {}
        for chunk in self.chunks:
            bucket = by_doc.setdefault(chunk.document_id, {})
            key = (chunk.page_number, chunk.start, chunk.end, chunk.kind)
            mandatory = mandatory_by_doc.setdefault(chunk.document_id, set())
            if chunk.kind == "selected_option":
                bucket[key] = (2.0, chunk)
                mandatory.add(key)
            elif chunk.kind == "table_row" and FORCE_SIGNALS.search(chunk.text):
                bucket[key] = (1.75, chunk)
                mandatory.add(key)
            elif FORCE_SIGNALS.search(chunk.text):
                bucket[key] = (max(bucket.get(key, (float("-inf"), chunk))[0], 1.5), chunk)
                mandatory.add(key)
            elif chunk.kind == "table_row" and LEXICAL_SIGNALS.search(chunk.text):
                bucket[key] = (max(bucket.get(key, (float("-inf"), chunk))[0], 0.9), chunk)
            elif LEXICAL_SIGNALS.search(chunk.text) and key not in bucket:
                bucket[key] = (0.62, chunk)

        selected: list[Chunk] = []
        for document_id in sorted(by_doc, key=str):
            ranked = sorted(by_doc[document_id].items(), key=lambda item: item[1][0], reverse=True)
            mandatory = mandatory_by_doc.get(document_id, set())
            required = [item for key, (_, item) in ranked if key in mandatory]
            optional = [item for key, (_, item) in ranked if key not in mandatory]
            # Structural commitments are never lost to the document cap. Fill the
            # remaining budget with the strongest semantic/lexical candidates.
            remaining = max(0, max_per_document - len(required))
            selected.extend(required)
            selected.extend(optional[:remaining])
        return selected

