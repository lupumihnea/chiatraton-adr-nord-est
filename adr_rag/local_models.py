from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import requests

from .config import settings


class LocalEmbedder:
    """Local multilingual embeddings; downloads once if missing."""

    def __init__(self, model_name_or_path: str | None = None):
        self.model_name = model_name_or_path or settings.embedding_model
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name, local_files_only=True)
        except OSError:
            print(
                f"Embedding model '{self.model_name}' was not found locally. "
                "Downloading it once from Hugging Face..."
            )
            os.environ.pop("HF_HUB_OFFLINE", None)
            os.environ.pop("TRANSFORMERS_OFFLINE", None)
            self.model = SentenceTransformer(self.model_name)
            print(
                f"Embedding model '{self.model_name}' downloaded and cached. "
                "Future runs can use it locally."
            )

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


@dataclass
class ExtractedObligation:
    deadline: str | None
    importance: int
    passage_id: int
    unit_start: int
    unit_end: int
    applicability: str = "applies"  # applies | not_applicable | needs_check
    applicability_query: str | None = None


class OpenRouterLLM:
    """OpenRouter paid-only; exact persisted wording stays local."""

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        # PAID-ONLY OpenRouter routing.
        #
        # OPENROUTER_PAID_MODEL has highest priority because this project is
        # intentionally configured to never call a :free endpoint.
        self.model = (
            model
            or os.environ.get("OPENROUTER_PAID_MODEL")
            or os.environ.get("OPENROUTER_MODEL")
            or "qwen/qwen3-235b-a22b-2507"
        )

        # Safety guard: even if an old shell variable still points at a :free
        # route, refuse to use it. This prevents the previous HTTP 404 failure
        # from silently returning.
        if self.model.endswith(":free"):
            raise RuntimeError(
                "This build is paid-only, but the configured OpenRouter model "
                f"is a free route: '{self.model}'. "
                "Set OPENROUTER_PAID_MODEL=qwen/qwen3-235b-a22b-2507 "
                "or unset the old OPENROUTER_MODEL/OPENROUTER_FREE_MODEL variables."
            )

        self.base_url = (
            base_url
            or os.environ.get("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set.\n"
                "PowerShell:\n"
                '  $env:OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"\n'
            )

        # Optional OpenRouter attribution headers. They are not required.
        self.app_url = os.environ.get("OPENROUTER_APP_URL")
        self.app_name = os.environ.get("OPENROUTER_APP_NAME", "ADR Local RAG")

        self.request_count = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    @staticmethod
    def _system_prompt() -> str:
        return """You identify MONITORING OBLIGATIONS and MONITORABLE PROJECT COMMITMENTS in Romanian/EU-funding documents.

Use ONLY the supplied source units. Do not add outside legal knowledge or assumptions.

IMPORTANT FOR THIS TASK:
A monitorable obligation is not limited to sentences containing "trebuie" or "obligația".
In PROJECT-SPECIFIC documents, also extract:
- formal indicators and target values;
- monitoring-plan milestones and evidence requirements;
- rows of payment/reimbursement/procurement schedules;
- explicit project commitments and promised outputs;
- SELECTED scoring/selection options that the project committed to satisfy or maintain;
- durability/maintenance commitments;
- explicit conditions whose continued observance affects eligibility/funding.

Do NOT extract:
- generic market analysis;
- merely descriptive historical facts;
- speculative commercial forecasts with no formal project commitment;
- recommendations;
- risks;
- rights/options/remedies (for example "poate", "are posibilitatea") unless the text also contains a separate mandatory duty.

A planned target CAN be an obligation when it appears in a formal project schedule, monitoring plan, selected scoring criterion, formal indicator, or explicit commitment of the funded project.

IMPORTANCE:
3 = critical: formal indicator/deadline, scored commitment, funding/eligibility condition, mandatory procurement/compliance condition, or omission can plausibly affect funding.
2 = important: mandatory reporting/procedural/monitoring obligation or formal schedule item.
1 = normal: explicit lower-impact operational monitoring duty.

SOURCE POINTER RULE:
Each passage is divided locally into numbered SOURCE UNITS. NEVER translate, rewrite, fix spelling, or paraphrase the obligation. Return only the contiguous source-unit range. The application itself copies the original Romanian characters from that range.

Return JSON only:
{
  "obligations": [
    {
      "passage_id": 0,
      "unit_start": 2,
      "unit_end": 4,
      "deadline": "YYYY-MM-DD or null",
      "importance": 3,
      "applicability": "applies",
      "applicability_query": null
    }
  ]
}

Rules:
- Select the SMALLEST CONTIGUOUS range containing the complete duty/commitment and its local condition/target.
- Do not merge different passages in this extraction step.
- Use an absolute deadline only when explicit in the source or directly resolvable from PROJECT_END_ISO.
- If a deadline depends on an unavailable event (e.g. final payment), use null; preserve the relative condition by selecting the units containing it.
- For project-specific passages, applicability must be "applies".
- If there are no obligations, return {"obligations": []}.
"""

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.app_url:
            headers["HTTP-Referer"] = self.app_url
        if self.app_name:
            headers["X-Title"] = self.app_name

        # Always override any model value embedded in a caller payload.
        request_payload = dict(payload)
        request_payload["model"] = self.model

        for attempt in range(8):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=request_payload,
                    timeout=(10, 180),
                )
            except requests.Timeout as exc:
                if attempt == 7:
                    raise RuntimeError(
                        f"OpenRouter paid-model request timed out for "
                        f"'{self.model}'. Original error: {exc}"
                    ) from exc
                wait = min(2 ** min(attempt, 4), 20)
                print(
                    f"OpenRouter timeout on paid model '{self.model}'; "
                    f"retrying in {wait}s..."
                )
                time.sleep(wait)
                continue
            except requests.RequestException as exc:
                if attempt == 7:
                    raise RuntimeError(
                        f"Could not communicate with OpenRouter using paid model "
                        f"'{self.model}'. Original error: {exc}"
                    ) from exc
                wait = min(2 ** min(attempt, 4), 20)
                print(
                    f"OpenRouter network error on paid model '{self.model}'; "
                    f"retrying in {wait}s..."
                )
                time.sleep(wait)
                continue

            if response.status_code == 401:
                raise RuntimeError("OpenRouter rejected OPENROUTER_API_KEY.")

            if response.status_code == 402:
                raise RuntimeError(
                    "OpenRouter returned HTTP 402. This build uses only a paid "
                    "model, so the account/API key needs sufficient OpenRouter credits."
                )

            if response.status_code == 403:
                raise RuntimeError(
                    "OpenRouter returned HTTP 403. Check API-key permissions and "
                    "provider/privacy settings on the OpenRouter account."
                )

            if response.status_code == 404:
                raise RuntimeError(
                    f"OpenRouter could not find paid model '{self.model}' (HTTP 404). "
                    "The expected model slug is "
                    "'qwen/qwen3-235b-a22b-2507'."
                )

            if response.status_code == 413:
                raise RuntimeError(
                    "OpenRouter rejected this request as too large (HTTP 413). "
                    "This is a request-size problem, not a billing/model-selection "
                    "problem. Reduce extraction/applicability batch sizes if they "
                    "were manually increased."
                )

            if response.status_code == 429:
                if attempt == 7:
                    raise RuntimeError(
                        "OpenRouter paid model is rate-limited after retries. "
                        f"Model: {self.model}. Response: {response.text[:500]}"
                    )
                retry_after = response.headers.get("retry-after")
                try:
                    wait = float(retry_after) if retry_after else min(
                        2 ** min(attempt + 1, 5), 30
                    )
                except ValueError:
                    wait = min(2 ** min(attempt + 1, 5), 30)
                wait = max(1.0, min(wait, 90.0))
                print(
                    f"OpenRouter paid model rate-limited (429); "
                    f"waiting {wait:.1f}s before retry..."
                )
                time.sleep(wait)
                continue

            if 500 <= response.status_code < 600:
                if attempt == 7:
                    raise RuntimeError(
                        "OpenRouter paid provider/server error after retries. "
                        f"Model: {self.model}. Response: {response.text[:500]}"
                    )
                wait = min(2 ** min(attempt, 4), 20)
                print(
                    f"OpenRouter provider/server busy ({response.status_code}) "
                    f"for '{self.model}'; retrying in {wait}s..."
                )
                time.sleep(wait)
                continue

            response.raise_for_status()

            try:
                body = response.json()
                content = body["choices"][0]["message"]["content"]

                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict)
                    )

                content = str(content).strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
                    content = re.sub(r"\s*```$", "", content)

                parsed = json.loads(content)
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                raise RuntimeError(
                    "OpenRouter returned invalid JSON for the expected schema. "
                    f"Model: {self.model}. Raw response: {response.text[:1000]}"
                ) from exc

            usage = body.get("usage", {}) or {}
            self.request_count += 1
            self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
            self.total_tokens += int(usage.get("total_tokens", 0) or 0)

            print(
                "OpenRouter usage: "
                f"route=PAID, model={self.model}, "
                f"request={self.request_count}, "
                f"this={usage.get('total_tokens', '?')} tokens, "
                f"run_total={self.total_tokens} tokens"
            )
            return parsed

        raise RuntimeError("Unexpected OpenRouter paid-only retry loop exit.")

    def build_project_profile(
        self,
        context_passages: list[dict[str, Any]],
        project_end_iso: str | None,
        seed_profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not context_passages:
            result = dict(seed_profile or {})
            result.setdefault("project_end", project_end_iso or "unknown")
            result.setdefault("facts", [])
            return result

        blocks: list[str] = []
        for i, p in enumerate(context_passages):
            blocks.append(
                f"--- PROJECT EXCERPT {i} ---\n"
                f"DOCUMENT_TYPE: {p['document_type']}\n"
                f"TEXT:\n{p['text']}\n"
                f"--- END PROJECT EXCERPT {i} ---"
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._project_profile_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"PROJECT_END_ISO: {project_end_iso or 'unknown'}\n"
                        f"SEED_PROFILE: {json.dumps(seed_profile or {}, ensure_ascii=False)}\n\n"
                        + "\n\n".join(blocks)
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 850,
            "response_format": {"type": "json_object"},
        }
        data = self._post(payload)
        profile = data.get("project_profile", {})
        if not isinstance(profile, dict):
            profile = dict(seed_profile or {})
        profile.setdefault("project_end", project_end_iso or "unknown")
        profile.setdefault("facts", [])
        return profile

    def extract_obligations_batch(
        self,
        passages: list[dict[str, Any]],
        project_end_iso: str | None,
        project_profile: dict[str, Any] | None = None,
        strict_applicability: bool = False,
        project_specific: bool = False,
    ) -> list[ExtractedObligation]:
        if not passages:
            return []

        blocks: list[str] = []
        valid: dict[int, dict[str, Any]] = {}
        for p in passages:
            pid = int(p["passage_id"])
            valid[pid] = p
            unit_lines = "\n".join(
                f"[U{u['unit_id']}] {u['text']}" for u in p.get("units", [])
            )
            blocks.append(
                f"--- PASSAGE {pid} ---\n"
                f"DOCUMENT_TYPE: {p['document_type']}\n"
                f"SOURCE_UNITS:\n{unit_lines}\n"
                f"--- END PASSAGE {pid} ---"
            )

        mode_block = ""
        if project_specific:
            mode_block += (
                "PROJECT_SPECIFIC_MODE: true\n"
                "These are this project's own documents. Treat formal schedules, "
                "monitoring rows, explicit project targets, and selected scoring "
                "commitments as monitorable even if they are not written as imperatives.\n"
            )

        if strict_applicability:
            mode_block += (
                "GENERIC_APPLICABILITY_MODE: true\n"
                "These passages come from a generic manual/guide. For each real duty:\n"
                "- applicability=applies if universal or PROJECT_PROFILE supports its condition;\n"
                "- applicability=not_applicable only if PROJECT_PROFILE explicitly contradicts it;\n"
                "- applicability=needs_check when the condition is genuinely unknown. DO NOT omit "
                "a duty merely because the profile is incomplete.\n"
                "For needs_check, provide applicability_query: a short Romanian query describing "
                "the missing project fact needed to decide applicability.\n"
                "Do not extract rights/options/remedies as duties.\n"
                f"PROJECT_PROFILE: {json.dumps(project_profile or {}, ensure_ascii=False)}\n"
            )

        user_prompt = (
            f"PROJECT_END_ISO: {project_end_iso or 'unknown'}\n\n"
            + mode_block
            + "\n"
            + "\n\n".join(blocks)
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "max_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        data = self._post(payload)
        result: list[ExtractedObligation] = []

        for item in data.get("obligations", []):
            try:
                pid = int(item.get("passage_id"))
                unit_start = int(item.get("unit_start"))
                unit_end = int(item.get("unit_end"))
                importance = int(item.get("importance", 1))
            except (TypeError, ValueError):
                continue

            p = valid.get(pid)
            if p is None:
                continue
            unit_count = len(p.get("units", []))
            if unit_start < 0 or unit_end < unit_start or unit_end >= unit_count:
                continue

            importance = min(3, max(1, importance))
            deadline = item.get("deadline")
            if deadline in ("", "null", "None", None):
                deadline = None
            else:
                deadline = str(deadline).strip()

            applicability = str(item.get("applicability", "applies")).strip().lower()
            if applicability not in {"applies", "not_applicable", "needs_check"}:
                applicability = "needs_check" if strict_applicability else "applies"
            if not strict_applicability:
                applicability = "applies"

            query = item.get("applicability_query")
            query = str(query).strip() if query not in (None, "", "null") else None

            result.append(
                ExtractedObligation(
                    deadline=deadline,
                    importance=importance,
                    passage_id=pid,
                    unit_start=unit_start,
                    unit_end=unit_end,
                    applicability=applicability,
                    applicability_query=query,
                )
            )

        return result

    @staticmethod
    def _applicability_resolver_prompt() -> str:
        return """Decide whether generic beneficiary duties apply to one already-funded project.

Use ONLY the supplied project profile and retrieved PROJECT EVIDENCE.
A rule may be rejected only when evidence shows its condition is false/not applicable.
If evidence positively supports the condition, apply it.
If evidence remains genuinely unknown, choose "uncertain" rather than inventing facts.
Rights/options are not duties, but the candidate rules here were already screened as duties.

Return JSON only:
{
  "decisions": [
    {"candidate_id": 0, "decision": "applies | not_applicable | uncertain"}
  ]
}
"""

    def resolve_applicability_batch(
        self,
        items: list[dict[str, Any]],
        project_profile: dict[str, Any],
    ) -> dict[int, str]:
        if not items:
            return {}

        blocks: list[str] = []
        for item in items:
            evidence = "\n".join(
                f"- {x}" for x in item.get("project_evidence", [])
            ) or "- no retrieved project evidence"
            blocks.append(
                f"--- CANDIDATE {item['candidate_id']} ---\n"
                f"GENERIC_RULE: {item['rule_text']}\n"
                f"MISSING_FACT_QUERY: {item.get('query') or 'unspecified'}\n"
                f"PROJECT_EVIDENCE:\n{evidence}\n"
                f"--- END CANDIDATE {item['candidate_id']} ---"
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._applicability_resolver_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"PROJECT_PROFILE: {json.dumps(project_profile, ensure_ascii=False)}\n\n"
                        + "\n\n".join(blocks)
                    ),
                },
            ],
            "temperature": 0,
            "max_tokens": 700,
            "response_format": {"type": "json_object"},
        }
        data = self._post(payload)
        decisions: dict[int, str] = {}
        valid_ids = {int(x["candidate_id"]) for x in items}
        for row in data.get("decisions", []):
            try:
                cid = int(row.get("candidate_id"))
            except (TypeError, ValueError):
                continue
            if cid not in valid_ids:
                continue
            decision = str(row.get("decision", "uncertain")).strip().lower()
            if decision not in {"applies", "not_applicable", "uncertain"}:
                decision = "uncertain"
            decisions[cid] = decision
        return decisions

    def extract_obligations(
        self,
        passage: str,
        project_end_iso: str | None,
        document_type: str,
    ) -> list[ExtractedObligation]:
        return self.extract_obligations_batch(
            [
                {
                    "passage_id": 0,
                    "document_type": document_type,
                    "units": [{"unit_id": 0, "text": passage}],
                }
            ],
            project_end_iso,
            project_specific=True,
        )


# Keep old imports working without touching CLI/API surface.
# Backwards compatibility: pipeline.py can keep importing LocalOllamaLLM.
# GroqLLM is retained as a legacy alias so older local code does not break.
GroqLLM = OpenRouterLLM
LocalOllamaLLM = OpenRouterLLM
