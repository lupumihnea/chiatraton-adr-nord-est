from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from AI.ai_client import CriterionInput, EvidenceAnchor, ReportInput
from AI.openrouter_monitoring_client import OpenRouterMonitoringAI
from DAO.projects_DAO import ProjectDAO
from DataBase.db_schema import database_path, setup_database
from Repositories.document_repository import DocumentRepository
from Repositories.monitoring_repository import EXCEPTION_OUTCOMES, MonitoringRepository
from Repositories.obligation_repository import ObligationRepository
from Repositories.project_document_repository import ProjectDocumentRepository
from Repositories.project_repository import ProjectRepository
from Repositories.reference_repository import ReferenceRepository
from Repositories.report_repository import ReportRepository


VALID_DECISIONS = {"confirmed", "corrected", "rejected", "clarification_requested"}
VALID_OUTPUT_KINDS = {"verification_note", "clarification_draft"}


class MonitoringService:
    """Application service implementing the requested report-monitoring workflow."""

    def __init__(
        self,
        db_path: str | None = None,
        ai_factory: Callable[[], OpenRouterMonitoringAI] | None = None,
    ):
        self.db_path = db_path or database_path()
        self.ai_factory = ai_factory or OpenRouterMonitoringAI
        con = setup_database(self.db_path)
        con.close()

    def _con(self):
        return setup_database(self.db_path)

    # ------------------------------------------------------------------
    # Project / document / report setup
    # ------------------------------------------------------------------
    def list_projects(self) -> list[dict[str, Any]]:
        con = self._con()
        try:
            return [vars(x) for x in ProjectRepository.get_all_projects(con.cursor())]
        finally:
            con.close()

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        con = self._con()
        try:
            item = ProjectRepository.get_project_by_id(con.cursor(), project_id)
            return vars(item) if item else None
        finally:
            con.close()

    def upsert_project(self, project_id: int, call_id: int | None, time_ending: str | None, name: str | None) -> None:
        con = self._con()
        try:
            ProjectRepository.upsert(
                con.cursor(),
                ProjectDAO(id=project_id, call_id=call_id, time_ending=time_ending, name=name),
            )
            con.commit()
        finally:
            con.close()

    def list_documents(self) -> list[dict[str, Any]]:
        con = self._con()
        try:
            return [vars(x) for x in DocumentRepository.get_all(con.cursor())]
        finally:
            con.close()

    def add_document(self, type_: int, path: str, project_id: int | None = None, role: str = "project_document") -> int:
        if not Path(path).exists():
            raise FileNotFoundError(path)
        con = self._con()
        try:
            document_id = DocumentRepository.add(con.cursor(), type_, str(Path(path).resolve()))
            if project_id is not None:
                ProjectDocumentRepository.link(con.cursor(), project_id, document_id, role)
            con.commit()
            return document_id
        finally:
            con.close()

    def link_documents(self, project_id: int, document_ids: list[int], role: str = "project_document") -> None:
        con = self._con()
        try:
            cur = con.cursor()
            for document_id in document_ids:
                if DocumentRepository.get_document_by_id(cur, document_id) is None:
                    raise ValueError(f"Document {document_id} does not exist")
            ProjectDocumentRepository.link_many(cur, project_id, document_ids, role)
            con.commit()
        finally:
            con.close()

    def add_report(
        self,
        project_id: int,
        document_id: int,
        sequence_number: int,
        kind: str,
        period_start: str,
        period_end: str,
        submitted_at: str | None = None,
    ) -> int:
        con = self._con()
        try:
            cur = con.cursor()
            if ProjectRepository.get_project_by_id(cur, project_id) is None:
                raise ValueError(f"Project {project_id} does not exist")
            if DocumentRepository.get_document_by_id(cur, document_id) is None:
                raise ValueError(f"Document {document_id} does not exist")
            report_id = ReportRepository.add(
                cur, project_id, document_id, sequence_number, kind,
                period_start, period_end, submitted_at,
            )
            ProjectDocumentRepository.link(cur, project_id, document_id, "report")
            con.commit()
            return report_id
        finally:
            con.close()

    def list_reports(self, project_id: int) -> list[dict[str, Any]]:
        con = self._con()
        try:
            return [vars(x) for x in ReportRepository.get_all_by_project(con.cursor(), project_id)]
        finally:
            con.close()

    def get_report(self, report_id: int) -> dict[str, Any] | None:
        con = self._con()
        try:
            row = ReportRepository.get_by_id(con.cursor(), report_id)
            return vars(row) if row else None
        finally:
            con.close()

    def extract_criteria(self, project_id: int, document_ids: list[int] | None = None) -> list[dict[str, Any]]:
        """Run the integrated paid OpenRouter RAG extraction against project documents."""
        con = self._con()
        try:
            cur = con.cursor()
            history_count = cur.execute(
                """
                SELECT COUNT(*)
                FROM criterion_validations v
                JOIN obligation o ON o.id=v.obligation_id
                WHERE o.project_id=?
                """,
                (project_id,),
            ).fetchone()[0]
            if history_count:
                raise ValueError(
                    "Criteriile nu pot fi înlocuite după ce există istoric de validare. "
                    "Pentru o schimbare ulterioară este necesară o versiune nouă de criterii."
                )
            if document_ids is None:
                ProjectDocumentRepository.ensure_from_criterion_references(cur, project_id)
                linked = ProjectDocumentRepository.get_documents(cur, project_id, include_report_documents=False)
                document_ids = [d.id for d in linked]
            if not document_ids:
                raise ValueError("No project documents are linked for criterion extraction.")
            ProjectDocumentRepository.link_many(cur, project_id, document_ids, "project_document")
            con.commit()
        finally:
            con.close()

        # The RAG package uses the same SQLite database and the original four
        # tables, so extraction writes criteria + exact references directly into
        # the application's canonical storage.
        from adr_rag.db import SessionLocal, get_documents, get_project
        from adr_rag.pipeline import run_extraction

        with SessionLocal() as session:
            project = get_project(session, project_id)
            docs = get_documents(session, document_ids)
            saved = run_extraction(session, project, docs)

        return [
            {
                "id": o.id,
                "project_id": o.project_id,
                "description": o.description,
                "deadline": str(o.deadline) if o.deadline else None,
                "importance": o.importance,
                "references": [
                    {
                        "document_id": r.document_id,
                        "page": r.page,
                        "text": r.text,
                        "chapter": r.chapter,
                        "subchapter": r.subchapter,
                    }
                    for r in o.references
                ],
            }
            for o in saved
        ]

    def list_criteria(self, project_id: int) -> list[dict[str, Any]]:
        con = self._con()
        try:
            cur = con.cursor()
            result = []
            for o in ObligationRepository.get_all_by_project_id(cur, project_id):
                refs = ReferenceRepository.find_all_reference_by_obligation_id(cur, o.id)
                result.append({
                    **vars(o),
                    "references": [vars(r) for r in refs],
                })
            return result
        finally:
            con.close()

    # ------------------------------------------------------------------
    # AI report analysis
    # ------------------------------------------------------------------
    def _criterion_inputs(self, cur, project_id: int) -> list[CriterionInput]:
        items: list[CriterionInput] = []
        for o in ObligationRepository.get_all_by_project_id(cur, project_id):
            refs = ReferenceRepository.find_all_reference_by_obligation_id(cur, o.id)
            baseline = [
                EvidenceAnchor(
                    evidence_id=f"criterion-{o.id}-source-{r.id}",
                    role="criterion_source",
                    document_id=r.document_id,
                    page=r.page,
                    text=r.text or "",
                    chapter=r.chapter,
                    subchapter=r.subchapter,
                )
                for r in refs
                if r.text and str(r.text).strip()
            ]
            items.append(
                CriterionInput(
                    criterion_id=o.id,
                    description=o.description or "",
                    deadline=o.deadline,
                    importance=o.importance,
                    baseline_sources=baseline,
                )
            )
        return items

    @staticmethod
    def _report_input(report, document) -> ReportInput:
        return ReportInput(
            report_id=report.id,
            document_id=document.id,
            kind=report.kind,
            period_start=report.period_start,
            period_end=report.period_end,
            path=document.path or "",
        )

    @staticmethod
    def _report_file_marker(path: str) -> str:
        try:
            p = Path(path)
            stat = p.stat()
            return f"{stat.st_size}:{stat.st_mtime_ns}"
        except OSError:
            return path

    def analyze_report(self, report_id: int, force: bool = False) -> list[dict[str, Any]]:
        con = self._con()
        job_id: int | None = None
        try:
            cur = con.cursor()
            report = ReportRepository.get_by_id(cur, report_id)
            if report is None:
                raise ValueError(f"Report {report_id} does not exist")

            project = ProjectRepository.get_project_by_id(cur, report.project_id)
            if project is None:
                raise ValueError(f"Project {report.project_id} does not exist")

            report_doc = DocumentRepository.get_document_by_id(cur, report.document_id)
            if report_doc is None or not report_doc.path:
                raise ValueError("Report document is missing")

            criteria = self._criterion_inputs(cur, report.project_id)
            if not criteria:
                raise ValueError(
                    "Project has no extracted criteria/obligations. Run criterion extraction first."
                )

            # Existing RAG criteria already tell us which project documents are
            # authoritative. Backfill associations automatically for smooth
            # integration with older databases.
            ProjectDocumentRepository.ensure_from_criterion_references(cur, report.project_id)
            project_docs = ProjectDocumentRepository.get_documents(
                cur, report.project_id, include_report_documents=False
            )

            previous = ReportRepository.get_previous(cur, report)
            previous_inputs: list[ReportInput] = []
            for previous_report in previous:
                d = DocumentRepository.get_document_by_id(cur, previous_report.document_id)
                if d and d.path:
                    previous_inputs.append(self._report_input(previous_report, d))

            criteria_key = MonitoringRepository.criteria_fingerprint(
                [
                    {
                        "id": c.criterion_id,
                        "description": c.description,
                        "deadline": c.deadline,
                        "sources": [(s.document_id, s.page, s.text) for s in c.baseline_sources],
                    }
                    for c in criteria
                ]
            )
            base_key = (
                f"{report.project_id}:{report.id}:{criteria_key}:"
                f"{self._report_file_marker(report_doc.path)}"
            )

            if not force:
                old = MonitoringRepository.get_succeeded_job_by_key(cur, base_key)
                if old is not None:
                    return MonitoringRepository.latest_validations(cur, report_id, exceptions_only=True)

            job_revision = MonitoringRepository.next_job_revision(cur, report_id)
            key = base_key if not force else f"{base_key}:revision:{job_revision}"

            ai = self.ai_factory()
            job_id = MonitoringRepository.create_job(
                cur,
                project_id=report.project_id,
                report_id=report.id,
                idempotency_key=key,
                model_name=ai.model_name,
                revision=job_revision,
            )
            ReportRepository.set_status(cur, report.id, "analyzing")
            con.commit()

            proposals = ai.analyze_report(
                report=self._report_input(report, report_doc),
                criteria=criteria,
                project_documents=[(d.id, d.path or "") for d in project_docs if d.path],
                previous_reports=previous_inputs,
            )

            criterion_ids = {c.criterion_id for c in criteria}
            proposal_ids = {p.criterion_id for p in proposals}
            missing = criterion_ids - proposal_ids
            if missing:
                raise RuntimeError(f"AI contract mismatch; missing criteria: {sorted(missing)}")

            for proposal in proposals:
                revision = MonitoringRepository.next_validation_revision(
                    cur, report.id, proposal.criterion_id
                )
                validation_id = MonitoringRepository.add_validation(
                    cur,
                    report_id=report.id,
                    obligation_id=proposal.criterion_id,
                    revision=revision,
                    applicable=proposal.applicable,
                    outcome=proposal.outcome,
                    rationale=(
                        proposal.rationale
                        + (" Avertismente: " + " | ".join(proposal.warnings) if proposal.warnings else "")
                    ),
                    analysis_job_id=job_id,
                )
                for source in proposal.sources:
                    MonitoringRepository.add_source(
                        cur,
                        validation_id=validation_id,
                        role=source.role,
                        document_id=source.document_id,
                        page=source.page,
                        text=source.text,
                        chapter=source.chapter,
                        subchapter=source.subchapter,
                    )

            MonitoringRepository.finish_job(cur, job_id, "succeeded")
            ReportRepository.set_status(cur, report.id, "awaiting_user")
            con.commit()
            return MonitoringRepository.latest_validations(cur, report_id, exceptions_only=True)

        except Exception as exc:
            if job_id is not None:
                try:
                    MonitoringRepository.finish_job(cur, job_id, "failed", "analysis_failed")
                    ReportRepository.set_status(cur, report_id, "analysis_failed")
                    con.commit()
                except Exception:
                    con.rollback()
            raise
        finally:
            con.close()

    def list_findings(self, report_id: int) -> list[dict[str, Any]]:
        con = self._con()
        try:
            return MonitoringRepository.latest_validations(
                con.cursor(), report_id, exceptions_only=True
            )
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Human decisions and history
    # ------------------------------------------------------------------
    def decide(
        self,
        validation_id: int,
        action: str,
        final_outcome: str | None = None,
        corrected_text: str | None = None,
        comment: str | None = None,
        decided_by: str = "utilizator",
    ) -> int:
        if action not in VALID_DECISIONS:
            raise ValueError(f"Unknown decision action: {action}")
        con = self._con()
        try:
            decision_id = MonitoringRepository.add_decision(
                con.cursor(), validation_id, action, final_outcome,
                corrected_text, comment, decided_by,
            )
            con.commit()
            return decision_id
        finally:
            con.close()

    @staticmethod
    def _display_text(text: str) -> str:
        # Display/export formatting only: words, spelling, punctuation and
        # diacritics remain unchanged; PDF line-break whitespace is collapsed.
        return re.sub(r"\s+", " ", text or "").strip()

    def generate_output(self, report_id: int, kind: str) -> dict[str, Any]:
        if kind not in VALID_OUTPUT_KINDS:
            raise ValueError(f"Unknown output kind: {kind}")

        con = self._con()
        try:
            cur = con.cursor()
            report = ReportRepository.get_by_id(cur, report_id)
            if report is None:
                raise ValueError(f"Report {report_id} does not exist")
            project = ProjectRepository.get_project_by_id(cur, report.project_id)
            findings = MonitoringRepository.latest_validations(cur, report_id, exceptions_only=True)

            reviewed = [
                f for f in findings
                if f.get("decision") and f["decision"].get("action") != "rejected"
            ]
            if not reviewed:
                raise ValueError(
                    "Nu există constatări confirmate/corectate/trimise la clarificare pentru acest raport."
                )

            title = (
                "NOTĂ DE VERIFICARE - DRAFT"
                if kind == "verification_note"
                else "DRAFT SOLICITARE DE CLARIFICĂRI"
            )
            lines = [
                title,
                "",
                f"Proiect: {project.name or project.id}",
                f"Cod proiect: {project.id}",
                f"Raport: #{report.sequence_number} ({report.kind})",
                f"Perioadă: {report.period_start} - {report.period_end}",
                "",
            ]

            if kind == "clarification_draft":
                lines.extend([
                    "Vă rugăm să clarificați următoarele aspecte identificate în verificarea raportului:",
                    "",
                ])

            for idx, finding in enumerate(reviewed, start=1):
                decision = finding["decision"]
                final_outcome = decision.get("final_outcome") or finding["outcome"]
                corrected = decision.get("corrected_text")
                explanation = corrected or finding["rationale"]
                lines.append(f"{idx}. [{final_outcome}] {explanation}")
                lines.append(f"   Criteriu: {self._display_text(finding['criterion_text'])}")

                sources = finding.get("sources", [])[:2]
                for source_idx, source in enumerate(sources, start=1):
                    lines.append(
                        f"   Sursa {source_idx}: document {source['document_id']}, "
                        f"pagina {source['page'] if source['page'] is not None else 'N/A'}"
                    )
                    lines.append(f"   Pasaj: {self._display_text(source['text'])}")
                if decision.get("comment"):
                    lines.append(f"   Observație utilizator: {decision['comment']}")
                lines.append("")

            lines.append(
                "Document generat ca draft. Analiza și decizia finală aparțin utilizatorului."
            )
            content = "\n".join(lines)

            exports = Path("exports")
            exports.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"project_{project.id}_report_{report.id}_{kind}_{timestamp}.txt"
            path = exports / filename
            path.write_text(content, encoding="utf-8")

            output_id = MonitoringRepository.add_generated_output(
                cur, report_id, kind, content, str(path.resolve())
            )
            con.commit()
            return {
                "id": output_id,
                "kind": kind,
                "content": content,
                "path": str(path.resolve()),
            }
        finally:
            con.close()

    def history(self, report_id: int) -> dict[str, Any]:
        con = self._con()
        try:
            return MonitoringRepository.history(con.cursor(), report_id)
        finally:
            con.close()
