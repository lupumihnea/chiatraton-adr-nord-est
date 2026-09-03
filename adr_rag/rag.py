from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from .local_models import LocalEmbedder
from .parsing import Passage


# Dense retrieval queries target not only imperative language, but also the
# structured commitments that matter in this ADR challenge: selected scoring
# options, monitoring indicators, schedules and durability commitments.
SEED_QUERIES = [
    "obligații asumate de beneficiar termene monitorizare proiect",
    "beneficiarul trebuie să transmită depună respecte mențină realizeze",
    "indicator de etapă criteriu de validare termen documente dovezi",
    "plan de monitorizare RCO01 RCO02 RCR02 indicator realizare rezultat",
    "angajament care a adus punctaj criteriu de selecție selectată da",
    "creșterea numărului mediu de salariați menținerea 3 ani plata finală",
    "locuri de muncă angajare persoane lucrători defavorizați",
    "contribuția proprie solicitant cheltuieli eligibile procent punctaj",
    "achiziție contract furnizare recepție punere în funcțiune termen",
    "plan achiziții perioadă achiziție directă achiziție competitivă",
    "grafic cereri de plată rambursare prefinanțare dată depunere estimată",
    "raport progres trimestrial raport final termen transmitere",
    "locația investiției punct de lucru Botoșani menținere investiție",
    "DNSH vizibilitate publicitate durabilitate principii orizontale",
    "ajutor de stat de minimis eligibilitate conflict de interese arhivare",
    "obiective specifice proiect indicator țintă rezultat asumat",
]

# These are not necessarily obligations by themselves, but are strong evidence
# that a passage deserves review by the extraction model.
LEXICAL_SIGNALS = re.compile(
    r"\b(oblig\w*|trebuie|va trebui|se angajeaz\w*|asum\w*|mențin\w*|"
    r"termen\w*|până la|indicator\w*|criteri\w*|transmit\w*|depun\w*|"
    r"realiz\w*|respect\w*|doved\w*|raport\w*|achizi\w*|ramburs\w*|"
    r"prefinanț\w*|plată|locuri? de muncă|salariaț\w*|defavorizat\w*|"
    r"contribuți\w*|punctaj|selectat\w*|conflict de interese|vizibilitate|"
    r"publicitate|DNSH|durabil\w*|ajutor de stat|de minimis)\b",
    re.IGNORECASE,
)

# Passages matching these signals should survive truncation even when dense
# similarity is mediocre (common for tables exported from MySMIS/Excel).
FORCE_SIGNALS = re.compile(
    r"(Punctaj\s*:\s*Selectat|Selectat[ăa]\s*:|"
    r"Descriere subcriteriu|Plan de monitorizare|indicator de etapă|"
    r"RCO0[12]|RCR02|Contribuția solicitantului|numărului mediu de salariați|"
    r"lucrătorilor defavorizați|3 noi locuri de muncă|"
    r"Graficul cererilor|Dată depunere\s*estimat|Cerere de plată|"
    r"Cerere de rambursare|Plan de achiziții|Perioada\s*\||"
    r"Raportul de progres final|raport de durabilitate)",
    re.IGNORECASE,
)


@dataclass
class RankedPassage:
    passage: Passage
    score: float


class InMemoryRAG:
    def __init__(self, embedder: LocalEmbedder):
        self.embedder = embedder
        self.passages: list[Passage] = []
        self.matrix: np.ndarray | None = None

    def build(self, passages: list[Passage]) -> None:
        self.passages = passages
        if not passages:
            self.matrix = np.zeros((0, 1), dtype=np.float32)
            return
        self.matrix = self.embedder.encode([p.text for p in passages])

    def _dense(self, query: str, top_k: int) -> list[RankedPassage]:
        if self.matrix is None or len(self.passages) == 0:
            return []
        q = self.embedder.encode([query])[0]
        scores = self.matrix @ q
        top = np.argsort(scores)[::-1][:top_k]
        return [RankedPassage(self.passages[i], float(scores[i])) for i in top]

    def candidate_passages(
        self,
        *,
        max_chunks: int,
        top_k_per_query: int,
        seed_queries: list[str] | None = None,
    ) -> list[Passage]:
        """High-recall union of dense, lexical and forced structured hits."""
        chosen: dict[tuple[int, int | None, str], tuple[Passage, float]] = {}

        for query in seed_queries or SEED_QUERIES:
            for hit in self._dense(query, top_k_per_query):
                key = (hit.passage.document_id, hit.passage.page, hit.passage.text)
                old = chosen.get(key)
                if old is None or hit.score > old[1]:
                    chosen[key] = (hit.passage, hit.score)

        for p in self.passages:
            key = (p.document_id, p.page, p.text)
            if FORCE_SIGNALS.search(p.text):
                old = chosen.get(key)
                score = 1.50  # force above normal dense scores
                if old is None or score > old[1]:
                    chosen[key] = (p, score)
            elif LEXICAL_SIGNALS.search(p.text):
                old = chosen.get(key)
                score = 0.62
                if old is None or score > old[1]:
                    chosen[key] = (p, score)

        ranked = sorted(chosen.values(), key=lambda x: x[1], reverse=True)
        return [p for p, _ in ranked[:max_chunks]]
