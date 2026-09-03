from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{os.getenv('ADR_DB_PATH', 'documents.db')}")

    # Kept for backwards compatibility; OpenRouter is the active LLM backend.
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    llm_model: str = os.getenv("LOCAL_LLM_MODEL", "qwen3:4b")

    embedding_model: str = os.getenv(
        "LOCAL_EMBEDDING_MODEL", "intfloat/multilingual-e5-small"
    )

    # Retrieval is now budgeted PER project document, not globally.  This is
    # intentionally recall-oriented because missing a project commitment is
    # worse than showing the LLM a few extra passages.
    project_top_k_per_query: int = int(os.getenv("PROJECT_TOP_K_PER_QUERY", "8"))
    project_max_chunks_per_document: int = int(
        os.getenv("PROJECT_MAX_CHUNKS_PER_DOCUMENT", "32")
    )

    # Generic manuals/guides still use RAG because reading every manual page on
    # every run would waste tokens and latency.
    generic_top_k_per_query: int = int(os.getenv("GENERIC_TOP_K_PER_QUERY", "8"))
    generic_max_candidate_chunks: int = int(
        os.getenv("GENERIC_MAX_CANDIDATE_CHUNKS", "40")
    )

    # A richer profile reduces false applicability rejections.
    profile_top_k_per_query: int = int(os.getenv("PROFILE_TOP_K_PER_QUERY", "3"))
    profile_max_passages: int = int(os.getenv("PROFILE_MAX_PASSAGES", "24"))

    # Batch size 4 keeps request payloads conservative.
    groq_batch_size: int = int(os.getenv("GROQ_BATCH_SIZE", "4"))
    applicability_batch_size: int = int(os.getenv("APPLICABILITY_BATCH_SIZE", "3"))

    # Deduplication is deliberately conservative.  Similar obligations are
    # preferable to accidentally fusing different duties/deadlines.
    dedup_similarity: float = float(os.getenv("DEDUP_SIMILARITY", "0.965"))
    dedup_token_jaccard: float = float(os.getenv("DEDUP_TOKEN_JACCARD", "0.62"))


settings = Settings()

# Intentionally kept in Python, not as a DB enum.
DOCUMENT_TYPES = {
    1: "financing_application",
    2: "business_plan",
    3: "business_plan_annex",
    4: "monitoring_plan",
    5: "procurement_plan",
    6: "payment_schedule",
    7: "progress_report",
    8: "beneficiary_manual",
    9: "funding_guide",
    10: "contract",
    11: "addendum",
    12: "declaration",
    99: "other",
}

IMPORTANCE = {
    1: "normal",
    2: "important",
    3: "critical",
}
