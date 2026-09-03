from uuid import uuid4

import numpy as np

from AI.retrieval import Chunk, ChunkIndex


class FlatEmbedder:
    def encode_passages(self, texts: list[str]):
        return np.ones((len(texts), 3), dtype=np.float32)

    def encode_query(self, query: str):
        return np.ones(3, dtype=np.float32)

    def encode_queries(self, queries: list[str]):
        return np.ones((len(queries), 3), dtype=np.float32)


def test_critical_recall_guards_survive_document_cap() -> None:
    document_id = uuid4()
    noise = [
        Chunk(document_id, page, 0, 50, f"Text generic {page} despre proiect")
        for page in range(1, 60)
    ]
    critical = [
        Chunk(
            document_id,
            70,
            0,
            80,
            "angajarea a 3 pers din care 1 defavorizat, in cele 12 luni de implementare",
        ),
        Chunk(
            document_id,
            71,
            0,
            80,
            "RCR02 realizarea raportului de progres final si anexele acestuia",
        ),
        Chunk(
            document_id,
            72,
            0,
            80,
            "Contribuția solicitantului la valoarea cheltuielilor eligibile 20%",
            kind="selected_option",
            source_text="Contribuția solicitantului la valoarea cheltuielilor eligibile 20%",
        ),
    ]
    index = ChunkIndex(tuple(noise + critical), FlatEmbedder())

    selected = index.extraction_candidates(max_per_document=2, top_k_per_query=1)
    texts = {chunk.text for chunk in selected}

    assert critical[0].text in texts
    assert critical[1].text in texts
    assert critical[2].text in texts
