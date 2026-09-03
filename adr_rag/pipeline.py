from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import re
from typing import Iterable

import numpy as np
from dateutil.parser import isoparse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import DOCUMENT_TYPES, settings
from .db import Document, Obligation, Project, Reference
from .local_models import ExtractedObligation, LocalEmbedder, LocalOllamaLLM
from .parsing import Passage, parse_document
from .rag import InMemoryRAG


@dataclass
class SourceUnit:
    unit_id: int
    start: int
    end: int
    text: str


@dataclass
class Candidate:
    description: str
    deadline: datetime | None
    importance: int
    refs: list[tuple[Passage, str]] = field(default_factory=list)
    origin: str = "llm"


# The document classes have different recall/cost policies.
PROJECT_SPECIFIC_TYPES = {1, 2, 3, 4, 5, 6, 10, 11, 12}
# Small/structured project documents are read in full rather than competing in RAG.
PROJECT_READ_ALL_TYPES = {3, 4, 10, 11, 12}
# These two have deterministic row extractors; no need to spend LLM quota on rows.
DETERMINISTIC_STRUCTURED_TYPES = {5, 6}
# Reporting template is small and useful enough to inspect in full, but its conditional
# clauses still need project applicability checking.
GENERIC_READ_ALL_TYPES = {7}
# Long generic sources use RAG.
GENERIC_RAG_TYPES = {8, 9}

PROFILE_QUERIES = [
    "categoria beneficiar microîntreprindere societate privată autoritate publică",
    "obiectul investiției echipamente utilaje teren clădire lucrări",
    "buget TVA eligibilă cheltuieli salariale contribuție proprie",
    "cerere prefinanțare cerere plată cerere rambursare grafic",
    "ajutor de stat ajutor de minimis",
    "achiziții beneficiar privat Ordinul 1284 Legea 98",
    "localizare proiect Botoșani punct de lucru contract de comodat",
    "locuri de muncă salariați defavorizați indicatori asumați",
    "plan monitorizare indicator etapă RCO01 RCO02 RCR02",
    "criteriu selecție punctaj selectată contribuția solicitantului",
]

DATE_DMY_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")
NUMBER_ANCHOR_RE = re.compile(
    r"(?<!\w)(?:RCO\d+|RCR\d+|\d{1,3}(?:[. ]\d{3})*(?:,\d+)?%?|\d{2}-\d{2}-\d{4})(?!\w)",
    re.IGNORECASE,
)
WORD_RE = re.compile(r"[\wĂÂÎȘȚăâîșț]+", re.UNICODE)


def _parse_deadline(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return isoparse(value)
    except (ValueError, TypeError):
        try:
            return datetime.strptime(value, "%d-%m-%Y")
        except (ValueError, TypeError):
            return None


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _split_long_line(
    text: str, start: int, end: int, max_chars: int = 450
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = start
    for m in re.finditer(r"[.!?;:](?:\s+|$)", text[start:end]):
        boundary = start + m.end()
        if boundary - cursor >= 70:
            s, e = _trim_span(text, cursor, boundary)
            if s < e:
                spans.append((s, e))
            cursor = boundary
    if cursor < end:
        s, e = _trim_span(text, cursor, end)
        if s < e:
            spans.append((s, e))

    final: list[tuple[int, int]] = []
    for s, e in spans or [(start, end)]:
        while e - s > max_chars:
            cut = min(s + max_chars, e)
            while cut > s + max_chars // 2 and not text[cut - 1].isspace():
                cut -= 1
            if cut <= s:
                cut = min(s + max_chars, e)
            ss, ee = _trim_span(text, s, cut)
            if ss < ee:
                final.append((ss, ee))
            s = cut
        ss, ee = _trim_span(text, s, e)
        if ss < ee:
            final.append((ss, ee))
    return final


def _source_units(text: str) -> list[SourceUnit]:
    """Number local source units while retaining exact source offsets."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for raw_line in text.splitlines(keepends=True):
        line_start = pos
        line_end = pos + len(raw_line)
        pos = line_end
        s, e = _trim_span(text, line_start, line_end)
        if s >= e:
            continue
        if e - s <= 450:
            spans.append((s, e))
        else:
            spans.extend(_split_long_line(text, s, e))

    if not spans and text.strip():
        s = len(text) - len(text.lstrip())
        e = len(text.rstrip())
        spans.extend(_split_long_line(text, s, e))

    return [SourceUnit(i, s, e, text[s:e]) for i, (s, e) in enumerate(spans)]


def _exact_section_from_units(
    passage: Passage,
    units: list[SourceUnit],
    unit_start: int,
    unit_end: int,
) -> str | None:
    if not units:
        return None
    if unit_start < 0 or unit_end < unit_start or unit_end >= len(units):
        return None
    exact = passage.text[units[unit_start].start : units[unit_end].end]
    return exact if exact.strip() else None


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().casefold()


def _document_text_fingerprint(passages: list[Passage]) -> str:
    body = "\n".join(_normalized_text(p.text) for p in passages)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _remove_duplicate_document_content(
    parsed_by_doc: dict[int, list[Passage]],
    document_by_id: dict[int, Document],
) -> dict[int, list[Passage]]:
    """Skip duplicate copies of the same textual document to protect RAG quota."""
    seen: dict[tuple[int, str], int] = {}
    result: dict[int, list[Passage]] = {}
    for doc_id, passages in parsed_by_doc.items():
        doc_type = document_by_id[doc_id].type
        if not passages:
            result[doc_id] = []
            continue
        fp = _document_text_fingerprint(passages)
        key = (doc_type, fp)
        if key in seen:
            print(
                f"Duplicate textual document detected: document {doc_id} "
                f"duplicates document {seen[key]}; skipping duplicate for extraction."
            )
            result[doc_id] = []
        else:
            seen[key] = doc_id
            result[doc_id] = passages
    return result


def _deterministic_project_profile(
    parsed_by_doc: dict[int, list[Passage]],
    document_by_id: dict[int, Document],
    project_end: str | None,
) -> dict:
    project_passages = [
        p
        for doc_id, passages in parsed_by_doc.items()
        if document_by_id[doc_id].type in PROJECT_SPECIFIC_TYPES
        for p in passages
    ]
    text = "\n".join(p.text for p in project_passages)
    folded = _normalized_text(text)

    profile: dict = {
        "beneficiary_kind": "unknown",
        "enterprise_size": "unknown",
        "has_land_acquisition": "unknown",
        "has_building_acquisition": "unknown",
        "has_construction_works": "unknown",
        "has_equipment_acquisition": "unknown",
        "has_salary_costs": "unknown",
        "has_eligible_vat": "unknown",
        "uses_prefinancing": "unknown",
        "uses_payment_requests": "unknown",
        "uses_reimbursement_requests": "unknown",
        "state_aid": "unknown",
        "de_minimis": "unknown",
        "procurement_regime": "unknown",
        "project_location": "unknown",
        "project_end": project_end or "unknown",
        "facts": [],
    }

    if any(x in folded for x in ["microîntreprindere", "microintreprindere", "entitate comerciala", "societate cu raspundere limitata"]):
        profile["beneficiary_kind"] = "private_company"
        profile["enterprise_size"] = "micro" if "micro" in folded else "unknown"
        profile["procurement_regime"] = "private_beneficiary"
        profile["facts"].append("Beneficiarul este o întreprindere privată/microîntreprindere.")

    # Presence of the project-specific procurement plan is a very strong fact.
    procurement_docs = [
        parsed_by_doc.get(doc_id, [])
        for doc_id, doc in document_by_id.items()
        if doc.type == 5
    ]
    procurement_text = "\n".join(p.text for group in procurement_docs for p in group)
    if procurement_text.strip():
        pnorm = _normalized_text(procurement_text)
        profile["has_equipment_acquisition"] = True
        profile["facts"].append("Planul de achiziții conține achiziții de furnizare/echipamente.")
        if "teren" not in pnorm:
            profile["has_land_acquisition"] = False
        if "clădire" not in pnorm and "cladire" not in pnorm and "imobil" not in pnorm:
            profile["has_building_acquisition"] = False
        # Current project plan containing only Furnizare is evidence that the
        # financed investment itself is not a works-procurement project.
        lines = [x for x in procurement_text.splitlines() if "|" in x][1:]
        if lines and all("furnizare" in _normalized_text(x) for x in lines):
            profile["has_construction_works"] = False

    payment_docs = [
        parsed_by_doc.get(doc_id, [])
        for doc_id, doc in document_by_id.items()
        if doc.type == 6
    ]
    payment_text = "\n".join(p.text for group in payment_docs for p in group)
    if payment_text:
        pnorm = _normalized_text(payment_text)
        profile["uses_payment_requests"] = "cerere de plată" in pnorm
        profile["uses_reimbursement_requests"] = "cerere de rambursare" in pnorm
        profile["uses_prefinancing"] = "cerere de prefinanțare" in pnorm
        if not profile["uses_prefinancing"]:
            profile["uses_prefinancing"] = False

    if re.search(r"sprijinul public va constitui ajutor de stat\s*:\s*da", folded, re.I):
        profile["state_aid"] = True
    if re.search(r"sprijinul public va constitui ajutor de minimis\s*:\s*da", folded, re.I):
        profile["de_minimis"] = True

    # Existing use-right / point of work is useful negative evidence against
    # generic land-purchase rules for this dossier.
    if (
        profile["has_land_acquisition"] == "unknown"
        and "contract de comodat" in folded
        and "achiziție teren" not in folded
        and "achizitie teren" not in folded
    ):
        profile["has_land_acquisition"] = False

    if "municipiul botosani" in folded or "municipiul botoșani" in folded:
        profile["project_location"] = "Municipiul Botoșani, județul Botoșani"

    return profile


def _project_profile_context(
    parsed_by_doc: dict[int, list[Passage]],
    document_by_id: dict[int, Document],
    embedder: LocalEmbedder,
) -> list[dict]:
    project_passages = [
        p
        for doc_id, passages in parsed_by_doc.items()
        if document_by_id[doc_id].type in PROJECT_SPECIFIC_TYPES
        for p in passages
    ]
    if not project_passages:
        return []

    rag = InMemoryRAG(embedder)
    rag.build(project_passages)
    chosen: dict[tuple[int, int | None, str], tuple[Passage, float]] = {}
    for query in PROFILE_QUERIES:
        for hit in rag._dense(query, top_k=settings.profile_top_k_per_query):
            key = (hit.passage.document_id, hit.passage.page, hit.passage.text)
            old = chosen.get(key)
            if old is None or hit.score > old[1]:
                chosen[key] = (hit.passage, hit.score)

    ranked = sorted(chosen.values(), key=lambda x: x[1], reverse=True)[
        : settings.profile_max_passages
    ]
    return [
        {
            "document_type": DOCUMENT_TYPES.get(
                document_by_id[p.document_id].type,
                f"type_{document_by_id[p.document_id].type}",
            ),
            "text": p.text,
        }
        for p, _ in ranked
    ]


def _payment_schedule_candidates(passages: list[Passage]) -> list[Candidate]:
    """Extract every payment/reimbursement schedule row deterministically."""
    out: list[Candidate] = []
    for passage in passages:
        lines = passage.text.splitlines()
        i = 0
        while i < len(lines):
            label = lines[i].strip()
            if not label.startswith("Cerere de "):
                i += 1
                continue

            # Expected export layout: type, request number, date, amount.
            if i + 3 >= len(lines):
                i += 1
                continue
            number = lines[i + 1].strip()
            date_text = lines[i + 2].strip()
            amount = lines[i + 3].strip()
            if not DATE_DMY_RE.match(date_text) or not number:
                i += 1
                continue

            exact = "\n".join(lines[i : i + 4]).strip()
            out.append(
                Candidate(
                    description=exact,
                    deadline=_parse_deadline(date_text),
                    importance=2,
                    refs=[(passage, exact)],
                    origin="payment_schedule_row",
                )
            )
            i += 4
    return out


def _procurement_plan_candidates(passages: list[Passage]) -> list[Candidate]:
    """Every non-header procurement row is a monitorable planned commitment."""
    out: list[Candidate] = []
    for passage in passages:
        for line in passage.text.splitlines():
            exact = line.strip()
            if "|" not in exact:
                continue
            norm = _normalized_text(exact)
            if norm.startswith("lider/partener |"):
                continue
            # The MySMIS export rows contain procurement title, procedure and period.
            if "achiz" not in norm and "furnizare" not in norm:
                continue
            out.append(
                Candidate(
                    description=exact,
                    # Month ranges do not map honestly to one timestamp; do not invent a day.
                    deadline=None,
                    importance=2,
                    refs=[(passage, exact)],
                    origin="procurement_plan_row",
                )
            )
    return out


def _numeric_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    for m in NUMBER_ANCHOR_RE.finditer(text or ""):
        v = m.group(0).casefold().replace(" ", "")
        anchors.add(v)
    return anchors


def _content_tokens(text: str) -> set[str]:
    stop = {
        "de", "a", "la", "în", "in", "si", "și", "cu", "din", "pentru", "prin",
        "se", "sau", "ale", "al", "ai", "un", "o", "este", "sunt", "va", "vor",
        "beneficiar", "beneficiarul", "proiect", "proiectului",
    }
    return {
        x.casefold()
        for x in WORD_RE.findall(text or "")
        if len(x) >= 3 and x.casefold() not in stop
    }


def _deadlines_compatible(a: datetime | None, b: datetime | None) -> bool:
    # CRITICAL FIX: None + explicit date are NOT compatible.  The old code
    # merged them and could transfer a deadline to the wrong obligation.
    if (a is None) != (b is None):
        return False
    if a is None and b is None:
        return True
    return a.date() == b.date()


def _can_semantically_merge(a: Candidate, b: Candidate, similarity: float) -> bool:
    if not _deadlines_compatible(a.deadline, b.deadline):
        return False
    if similarity < settings.dedup_similarity:
        return False

    aa = _numeric_anchors(a.description)
    bb = _numeric_anchors(b.description)
    # Different numeric/date/indicator anchors are strong evidence these are
    # distinct obligations (e.g. different request dates or different targets).
    if aa and bb and aa != bb:
        return False

    ta = _content_tokens(a.description)
    tb = _content_tokens(b.description)
    if not ta or not tb:
        return False
    jaccard = len(ta & tb) / len(ta | tb)
    return jaccard >= settings.dedup_token_jaccard


def _deduplicate(
    candidates: list[Candidate], embedder: LocalEmbedder
) -> tuple[list[Candidate], int]:
    if len(candidates) < 2:
        return candidates, 0

    # Exact normalized duplicates first; only merge if deadlines agree.
    exact_groups: dict[tuple[str, str | None], Candidate] = {}
    exact_unique: list[Candidate] = []
    exact_merged = 0
    for c in candidates:
        deadline_key = c.deadline.date().isoformat() if c.deadline else None
        key = (_normalized_text(c.description), deadline_key)
        target = exact_groups.get(key)
        if target is None:
            exact_groups[key] = c
            exact_unique.append(c)
        else:
            target.importance = max(target.importance, c.importance)
            target.refs.extend(c.refs)
            exact_merged += 1

    if len(exact_unique) < 2:
        return exact_unique, exact_merged

    embeddings = embedder.encode([c.description for c in exact_unique])
    merged: list[Candidate] = []
    merged_embeddings: list[np.ndarray] = []
    semantic_merged = 0

    for idx, c in enumerate(exact_unique):
        best_i = None
        best_score = -1.0
        for j, existing in enumerate(merged):
            score = float(embeddings[idx] @ merged_embeddings[j])
            if score > best_score and _can_semantically_merge(c, existing, score):
                best_score = score
                best_i = j

        if best_i is None:
            merged.append(c)
            merged_embeddings.append(embeddings[idx])
            continue

        target = merged[best_i]
        target.importance = max(target.importance, c.importance)
        target.refs.extend(c.refs)
        # NEVER inherit/change deadline here; compatibility already required it
        # to be identical (or both absent).
        semantic_merged += 1

    return merged, exact_merged + semantic_merged


def _batched(items: list, size: int):
    size = max(1, size)
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _select_project_passages(
    parsed_by_doc: dict[int, list[Passage]],
    document_by_id: dict[int, Document],
    embedder: LocalEmbedder,
) -> list[Passage]:
    selected: list[Passage] = []

    for doc_id, passages in parsed_by_doc.items():
        doc = document_by_id[doc_id]
        doc_type = doc.type
        if not passages or doc_type in DETERMINISTIC_STRUCTURED_TYPES:
            continue
        if doc_type not in PROJECT_SPECIFIC_TYPES:
            continue

        if doc_type in PROJECT_READ_ALL_TYPES or len(passages) <= 12:
            picked = passages
        else:
            rag = InMemoryRAG(embedder)
            rag.build(passages)
            picked = rag.candidate_passages(
                max_chunks=settings.project_max_chunks_per_document,
                top_k_per_query=settings.project_top_k_per_query,
            )

        print(
            f"document {doc_id} ({DOCUMENT_TYPES.get(doc_type, doc_type)}): "
            f"parsed {len(passages)} -> selected {len(picked)} project passage(s)"
        )
        selected.extend(picked)

    return selected


def _select_generic_passages(
    parsed_by_doc: dict[int, list[Passage]],
    document_by_id: dict[int, Document],
    embedder: LocalEmbedder,
) -> list[Passage]:
    selected: list[Passage] = []

    for doc_id, passages in parsed_by_doc.items():
        doc_type = document_by_id[doc_id].type
        if doc_type in GENERIC_READ_ALL_TYPES:
            print(
                f"document {doc_id} ({DOCUMENT_TYPES.get(doc_type, doc_type)}): "
                f"reading all {len(passages)} reporting-template passage(s)"
            )
            selected.extend(passages)

    long_generic = [
        p
        for doc_id, passages in parsed_by_doc.items()
        if document_by_id[doc_id].type in GENERIC_RAG_TYPES
        for p in passages
    ]
    if long_generic:
        rag = InMemoryRAG(embedder)
        rag.build(long_generic)
        picked = rag.candidate_passages(
            max_chunks=settings.generic_max_candidate_chunks,
            top_k_per_query=settings.generic_top_k_per_query,
        )
        print(
            f"generic manual/guide pool: parsed {len(long_generic)} -> "
            f"selected {len(picked)} passage(s)"
        )
        selected.extend(picked)

    return selected


def _extract_llm_group(
    *,
    group_name: str,
    group_passages: list[Passage],
    document_by_id: dict[int, Document],
    llm: LocalOllamaLLM,
    project_end: str | None,
    project_profile: dict,
    strict_applicability: bool,
    project_specific: bool,
    start_global_index: int,
) -> tuple[list[Candidate], list[tuple[Candidate, str]], int, int]:
    candidates: list[Candidate] = []
    pending: list[tuple[Candidate, str]] = []
    rejected = 0
    global_index = start_global_index
    batch_size = settings.groq_batch_size
    batch_count = (len(group_passages) + batch_size - 1) // batch_size

    if not group_passages:
        return candidates, pending, rejected, global_index

    print(
        f"{group_name}: {len(group_passages)} passage(s) -> "
        f"{batch_count} OpenRouter batch(es)."
    )

    for batch_no, batch in enumerate(_batched(group_passages, batch_size), start=1):
        indexed_passages: dict[int, Passage] = {}
        units_by_passage_id: dict[int, list[SourceUnit]] = {}
        payload_passages: list[dict] = []

        for passage in batch:
            pid = global_index
            global_index += 1
            indexed_passages[pid] = passage
            units = _source_units(passage.text)
            units_by_passage_id[pid] = units
            doc = document_by_id[passage.document_id]
            payload_passages.append(
                {
                    "passage_id": pid,
                    "document_type": DOCUMENT_TYPES.get(doc.type, f"type_{doc.type}"),
                    "units": [{"unit_id": u.unit_id, "text": u.text} for u in units],
                }
            )

        print(f"Groq {group_name} batch {batch_no}/{batch_count}: {len(batch)} passages")
        extracted = llm.extract_obligations_batch(
            payload_passages,
            project_end,
            project_profile=project_profile if strict_applicability else None,
            strict_applicability=strict_applicability,
            project_specific=project_specific,
        )

        for item in extracted:
            passage = indexed_passages.get(item.passage_id)
            units = units_by_passage_id.get(item.passage_id, [])
            if passage is None:
                continue
            exact_source = _exact_section_from_units(
                passage, units, item.unit_start, item.unit_end
            )
            if exact_source is None:
                continue

            c = Candidate(
                description=exact_source,
                deadline=_parse_deadline(item.deadline),
                importance=item.importance,
                refs=[(passage, exact_source)],
                origin=group_name,
            )

            if item.applicability == "not_applicable":
                rejected += 1
                continue
            if item.applicability == "needs_check":
                pending.append((c, item.applicability_query or exact_source[:240]))
            else:
                candidates.append(c)

    return candidates, pending, rejected, global_index


def _resolve_pending_applicability(
    pending: list[tuple[Candidate, str]],
    project_passages: list[Passage],
    embedder: LocalEmbedder,
    llm: LocalOllamaLLM,
    project_profile: dict,
) -> tuple[list[Candidate], int, int]:
    if not pending:
        return [], 0, 0

    project_rag = InMemoryRAG(embedder)
    project_rag.build(project_passages)

    prepared: list[dict] = []
    for cid, (candidate, query) in enumerate(pending):
        # Targeted evidence only: enough to decide one applicability condition,
        # while keeping OpenRouter requests small and quota-efficient.
        hits = project_rag._dense(query, top_k=3) if project_passages else []
        evidence = [hit.passage.text[:900] for hit in hits]
        prepared.append(
            {
                "candidate_id": cid,
                "rule_text": candidate.description,
                "query": query,
                "project_evidence": evidence,
            }
        )

    kept: list[Candidate] = []
    rejected = 0
    uncertain = 0
    for batch in _batched(prepared, settings.applicability_batch_size):
        decisions = llm.resolve_applicability_batch(batch, project_profile)
        for item in batch:
            cid = item["candidate_id"]
            decision = decisions.get(cid, "uncertain")
            candidate = pending[cid][0]
            if decision == "not_applicable":
                rejected += 1
                continue
            if decision == "uncertain":
                # Recall-first fallback: after two applicability stages, do not
                # silently delete an otherwise real duty merely because the dossier
                # evidence is incomplete.  Lower its importance unless already normal.
                uncertain += 1
                candidate.importance = min(candidate.importance, 1)
            kept.append(candidate)

    return kept, rejected, uncertain


def _replace_existing_project_results(session: Session, project_id: int) -> int:
    old_ids = list(
        session.scalars(select(Obligation.id).where(Obligation.project_id == project_id))
    )
    if not old_ids:
        return 0
    session.execute(delete(Reference).where(Reference.obligation_id.in_(old_ids)))
    session.execute(delete(Obligation).where(Obligation.id.in_(old_ids)))
    session.flush()
    return len(old_ids)


def run_extraction(
    session: Session,
    project: Project,
    documents: list[Document],
    embedder: LocalEmbedder | None = None,
    llm: LocalOllamaLLM | None = None,
) -> list[Obligation]:
    embedder = embedder or LocalEmbedder()
    llm = llm or LocalOllamaLLM()
    document_by_id = {d.id: d for d in documents}

    # Parse per document so retrieval budgets cannot be stolen by another file.
    parsed_by_doc_raw: dict[int, list[Passage]] = {}
    for doc in documents:
        passages = parse_document(doc.id, doc.path)
        parsed_by_doc_raw[doc.id] = passages
        print(
            f"Parsed document {doc.id} ({DOCUMENT_TYPES.get(doc.type, doc.type)}): "
            f"{len(passages)} passage(s)"
        )

    parsed_by_doc = _remove_duplicate_document_content(
        parsed_by_doc_raw, document_by_id
    )
    project_end = project.time_ending.date().isoformat() if project.time_ending else None

    # Deterministic structured rows are guaranteed candidates; no semantic
    # retrieval or LLM can accidentally hide them.
    candidates: list[Candidate] = []
    payment_count = procurement_count = 0
    for doc_id, passages in parsed_by_doc.items():
        doc_type = document_by_id[doc_id].type
        if doc_type == 6:
            rows = _payment_schedule_candidates(passages)
            candidates.extend(rows)
            payment_count += len(rows)
        elif doc_type == 5:
            rows = _procurement_plan_candidates(passages)
            candidates.extend(rows)
            procurement_count += len(rows)

    print(
        f"Deterministic structured extraction: {payment_count} payment/reimbursement "
        f"row(s), {procurement_count} procurement row(s)."
    )

    project_passages_all = [
        p
        for doc_id, passages in parsed_by_doc.items()
        if document_by_id[doc_id].type in PROJECT_SPECIFIC_TYPES
        for p in passages
    ]

    # Build the applicability profile LOCALLY from the complete parsed dossier.
    #
    # Previous versions sent many project passages to OpenRouter in one profile request,
    # which can exceed Groq's request-size limit (HTTP 413). We do not need that
    # large request: deterministic dossier facts are enough for the first pass,
    # while genuinely unknown conditions are resolved later with targeted
    # retrieval against only a few project passages.
    project_profile = _deterministic_project_profile(
        parsed_by_doc, document_by_id, project_end
    )
    print(
        "Built local project applicability profile (no large OpenRouter profile request). "
        f"beneficiary={project_profile.get('beneficiary_kind')}, "
        f"land={project_profile.get('has_land_acquisition')}, "
        f"works={project_profile.get('has_construction_works')}, "
        f"equipment={project_profile.get('has_equipment_acquisition')}, "
        f"payment_requests={project_profile.get('uses_payment_requests')}, "
        f"reimbursements={project_profile.get('uses_reimbursement_requests')}"
    )

    project_selected = _select_project_passages(
        parsed_by_doc, document_by_id, embedder
    )
    generic_selected = _select_generic_passages(
        parsed_by_doc, document_by_id, embedder
    )

    global_index = 0
    project_llm, _, _, global_index = _extract_llm_group(
        group_name="project-specific",
        group_passages=project_selected,
        document_by_id=document_by_id,
        llm=llm,
        project_end=project_end,
        project_profile=project_profile,
        strict_applicability=False,
        project_specific=True,
        start_global_index=global_index,
    )
    candidates.extend(project_llm)

    generic_llm, pending, rejected_stage1, global_index = _extract_llm_group(
        group_name="generic/applicability",
        group_passages=generic_selected,
        document_by_id=document_by_id,
        llm=llm,
        project_end=project_end,
        project_profile=project_profile,
        strict_applicability=True,
        project_specific=False,
        start_global_index=global_index,
    )
    candidates.extend(generic_llm)

    resolved, rejected_stage2, uncertain = _resolve_pending_applicability(
        pending,
        project_passages_all,
        embedder,
        llm,
        project_profile,
    )
    candidates.extend(resolved)

    before_dedup = len(candidates)
    candidates, merged_count = _deduplicate(candidates, embedder)

    print(
        "Extraction diagnostics: "
        f"pre-dedup={before_dedup}, dedup_merged={merged_count}, "
        f"generic_rejected={rejected_stage1 + rejected_stage2}, "
        f"generic_uncertain_kept={uncertain}, final={len(candidates)}"
    )

    if hasattr(llm, "request_count"):
        print(
            "OpenRouter run summary: "
            f"{llm.request_count} request(s), "
            f"{llm.prompt_tokens} input tokens, "
            f"{llm.completion_tokens} output tokens, "
            f"{llm.total_tokens} total tokens."
        )

    # Replace only after successful extraction; if anything above fails, old DB
    # results remain untouched.
    replaced = _replace_existing_project_results(session, project.id)
    if replaced:
        print(
            f"Replacing {replaced} previously extracted obligation(s) "
            f"for project {project.id}."
        )

    saved: list[Obligation] = []
    for c in candidates:
        valid_refs: list[tuple[Passage, str]] = []
        seen_refs = set()
        for passage, evidence in c.refs:
            if not evidence or not evidence.strip():
                continue
            key = (passage.document_id, passage.page, evidence)
            if key in seen_refs:
                continue
            seen_refs.add(key)
            valid_refs.append((passage, evidence))

        if not valid_refs:
            continue

        source_texts = [evidence for _, evidence in valid_refs]
        exact_description = (
            c.description if c.description in source_texts else source_texts[0]
        )

        obligation = Obligation(
            project_id=project.id,
            description=exact_description,
            deadline=c.deadline,
            importance=c.importance,
        )
        session.add(obligation)
        session.flush()

        for passage, evidence in valid_refs:
            session.add(
                Reference(
                    obligation_id=obligation.id,
                    document_id=passage.document_id,
                    page=passage.page,
                    text=evidence,
                    chapter=passage.chapter,
                    subchapter=passage.subchapter,
                )
            )
        saved.append(obligation)

    session.flush()
    saved_ids = [o.id for o in saved]
    if saved_ids:
        orphan_ids = list(
            session.scalars(
                select(Obligation.id)
                .outerjoin(Reference, Reference.obligation_id == Obligation.id)
                .where(Obligation.id.in_(saved_ids))
                .group_by(Obligation.id)
                .having(func.count(Reference.id) == 0)
            )
        )
        if orphan_ids:
            session.rollback()
            raise RuntimeError(
                "Reference invariant violated. Orphan obligation ids: " + str(orphan_ids)
            )

        invalid_description_ids = list(
            session.scalars(
                select(Obligation.id)
                .outerjoin(
                    Reference,
                    (Reference.obligation_id == Obligation.id)
                    & (Reference.text == Obligation.description),
                )
                .where(Obligation.id.in_(saved_ids))
                .group_by(Obligation.id)
                .having(func.count(Reference.id) == 0)
            )
        )
        if invalid_description_ids:
            session.rollback()
            raise RuntimeError(
                "Source-language invariant violated. Invalid obligation ids: "
                + str(invalid_description_ids)
            )

    session.commit()
    return saved
