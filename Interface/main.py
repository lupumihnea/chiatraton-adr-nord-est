from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import ui

from API.monitoring_api import MonitoringAPI
from Interface import add_project  # noqa: F401 - registers /add_project


api = MonitoringAPI()

OUTCOME_LABELS = {
    "nonconcordance": "Neconcordanță",
    "missing_information": "Informații lipsă",
    "different_value_or_date": "Valoare/dată diferită",
    "insufficient_evidence": "Dovezi insuficiente",
    "cross_report_contradiction": "Contradicție între rapoarte",
    "human_review_required": "Necesită analiză umană",
}


def display_text(text: str) -> str:
    """Display-only whitespace normalization; never changes Romanian wording."""
    return re.sub(r"\s+", " ", text or "").strip()


def source_title(source: dict) -> str:
    role = {
        "criterion_source": "Sursa criteriului",
        "current_report": "Raport curent",
        "previous_report": "Raport anterior",
        "project_context": "Document proiect",
    }.get(source.get("role"), source.get("role", "Sursă"))
    return f"{role} · document {source.get('document_id')} · pagina {source.get('page', 'N/A')}"


@ui.page("/")
def home():
    with ui.column().classes("w-full items-center mt-10 gap-6"):
        logo = ROOT / "Interface" / "Assets" / "Logo-ADR.png"
        if logo.exists():
            ui.image(str(logo)).classes("w-56")
        ui.label("AI Monitoring Copilot").classes("text-3xl font-bold")
        ui.label("Selectează proiectul și apoi raportul/task-ul de verificat.").classes("text-gray-600")

        projects = api.list_projects()
        if not projects:
            ui.label("Nu există proiecte în baza de date.").classes("text-orange-700")
        else:
            search = ui.input(placeholder="Caută după cod sau nume").props("outlined clearable").classes("w-full max-w-2xl")
            container = ui.column().classes("w-full max-w-3xl gap-2")

            @ui.refreshable
            def project_list():
                container.clear()
                term = (search.value or "").lower().strip()
                with container:
                    for project in projects:
                        text = f"{project['id']} {project.get('name') or ''}".lower()
                        if term and term not in text:
                            continue
                        with ui.card().classes("w-full"):
                            with ui.row().classes("w-full items-center justify-between"):
                                with ui.column().classes("gap-0"):
                                    ui.label(project.get("name") or f"Proiect {project['id']}").classes("font-semibold text-lg")
                                    ui.label(f"Cod proiect: {project['id']}").classes("text-sm text-gray-600")
                                ui.button(
                                    "Accesează",
                                    on_click=lambda p=project: ui.navigate.to(f"/project/{p['id']}")
                                ).props("no-caps")
            search.on("update:model-value", lambda _: project_list.refresh())
            project_list()

        ui.button("Adaugă proiect", icon="add", on_click=lambda: ui.navigate.to("/add_project")).props("flat no-caps")


@ui.page("/project/{project_id}")
def project_page(project_id: int):
    project = api.get_project(project_id)
    if not project:
        ui.label("Proiect inexistent")
        return

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-5"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(project.get("name") or f"Proiect {project_id}").classes("text-3xl font-bold")
                ui.label(f"Cod proiect: {project_id}").classes("text-gray-600")
            ui.button("Înapoi", on_click=lambda: ui.navigate.to("/")).props("flat")

        criteria = api.list_criteria(project_id)
        reports = api.list_reports(project_id)
        ui.label(f"Criterii extrase: {len(criteria)} · Rapoarte/task-uri: {len(reports)}").classes("font-medium")

        with ui.expansion("Documente și criterii", icon="folder").classes("w-full"):
            docs = api.list_documents()
            ui.label("Leagă documente existente de proiect (ID-uri separate prin virgulă):")
            with ui.row().classes("w-full items-end"):
                doc_ids = ui.input("Document IDs", placeholder="1,3,4,5,6,7,9").classes("flex-grow")
                role = ui.input("Rol", value="project_document").classes("w-52")

                def link_docs():
                    try:
                        ids = [int(x.strip()) for x in (doc_ids.value or "").split(",") if x.strip()]
                        api.link_documents(project_id, ids, role.value or "project_document")
                        ui.notify(f"Legate {len(ids)} documente")
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                ui.button("Leagă", on_click=link_docs)

            ui.separator()
            ui.label("Re-extrage criteriile cu OpenRouter paid-only. Atenție: înlocuiește setul curent de criterii.")
            extract_ids = ui.input("Document IDs pentru extracție", placeholder="1,3,4,5,6,7,9").classes("w-full")

            async def extract_criteria():
                try:
                    ids = [int(x.strip()) for x in (extract_ids.value or "").split(",") if x.strip()]
                    if not ids:
                        raise ValueError("Introdu ID-urile documentelor proiectului.")
                    ui.notify("Extracția criteriilor a pornit...")
                    result = await asyncio.to_thread(api.extract_criteria, project_id, ids)
                    ui.notify(f"Au fost salvate {len(result)} criterii.", type="positive")
                except Exception as exc:
                    ui.notify(str(exc), type="negative", timeout=10000)

            ui.button("Extrage criterii", on_click=extract_criteria).props("no-caps")

        ui.label("1. Selectează un raport din task-urile existente").classes("text-xl font-semibold")

        if not reports:
            ui.label("Nu există încă rapoarte înregistrate pentru proiect.").classes("text-orange-700")
        else:
            for report in reports:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"Raport #{report['sequence_number']} · {report['kind']}").classes("font-semibold")
                            ui.label(f"Perioadă: {report['period_start']} — {report['period_end']}").classes("text-sm text-gray-600")
                            ui.label(f"Status: {report['status']}").classes("text-sm")
                        ui.button(
                            "Deschide task-ul",
                            on_click=lambda r=report: ui.navigate.to(f"/report/{r['id']}")
                        ).props("no-caps")

        with ui.expansion("Înregistrează un raport existent", icon="description").classes("w-full"):
            ui.label("Raportul trebuie să existe deja în tabela document și să aibă un fișier local asociat.")
            with ui.grid(columns=3).classes("w-full gap-3"):
                report_document_id = ui.number("Document ID", min=1)
                sequence = ui.number("Număr raport", min=1)
                kind = ui.select(
                    ["implementation_progress", "final_progress", "durability"],
                    value="implementation_progress",
                    label="Tip raport",
                )
                period_start = ui.input("Început perioadă", placeholder="2025-01-01")
                period_end = ui.input("Sfârșit perioadă", placeholder="2025-03-31")

            def add_report():
                try:
                    rid = api.add_report(
                        project_id=project_id,
                        document_id=int(report_document_id.value),
                        sequence_number=int(sequence.value),
                        kind=kind.value,
                        period_start=period_start.value,
                        period_end=period_end.value,
                    )
                    ui.notify(f"Raport înregistrat cu id {rid}", type="positive")
                    ui.navigate.to(f"/report/{rid}")
                except Exception as exc:
                    ui.notify(str(exc), type="negative")

            ui.button("Înregistrează raport", on_click=add_report).props("no-caps")


@ui.page("/report/{report_id}")
def report_page(report_id: int):
    report = api.get_report(report_id)
    if not report:
        ui.label("Raport inexistent")
        return

    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-5"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(f"Raport #{report['sequence_number']} · {report['kind']}").classes("text-3xl font-bold")
                ui.label(f"Perioadă: {report['period_start']} — {report['period_end']}").classes("text-gray-600")
            ui.button("Înapoi la proiect", on_click=lambda: ui.navigate.to(f"/project/{report['project_id']}")).props("flat")

        ui.label(
            "AI-ul compară raportul cu criteriile, documentele proiectului și rapoartele anterioare. "
            "Interfața afișează numai excepțiile; decizia rămâne la utilizator."
        ).classes("text-gray-700")

        findings_container = ui.column().classes("w-full gap-4")
        output_area = ui.column().classes("w-full")

        def decision_dialog(finding: dict):
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-2xl"):
                ui.label("Corectează constatarea").classes("text-xl font-semibold")
                final_outcome = ui.select(
                    list(OUTCOME_LABELS.keys()),
                    value=finding["outcome"],
                    label="Rezultat final",
                ).classes("w-full")
                corrected_text = ui.textarea("Corecție / formulare utilizator", value=finding["rationale"]).classes("w-full")
                comment = ui.textarea("Comentariu opțional").classes("w-full")

                def save():
                    api.decide(
                        finding["id"],
                        "corrected",
                        final_outcome=final_outcome.value,
                        corrected_text=corrected_text.value,
                        comment=comment.value,
                    )
                    dialog.close()
                    findings_view.refresh()
                    ui.notify("Corecția a fost salvată.", type="positive")

                with ui.row().classes("justify-end w-full"):
                    ui.button("Anulează", on_click=dialog.close).props("flat")
                    ui.button("Salvează", on_click=save)
            dialog.open()

        def simple_decision(finding: dict, action: str):
            try:
                api.decide(finding["id"], action, final_outcome=finding["outcome"])
                findings_view.refresh()
                ui.notify("Decizia a fost păstrată în istoric.", type="positive")
            except Exception as exc:
                ui.notify(str(exc), type="negative")

        @ui.refreshable
        def findings_view():
            findings_container.clear()
            findings = api.list_findings(report_id)
            with findings_container:
                ui.label(f"5. Excepții identificate: {len(findings)}").classes("text-xl font-semibold")
                if not findings:
                    ui.label("Nu există excepții salvate. Rulează analiza sau raportul nu are constatări de afișat.").classes("text-gray-600")
                    return

                for finding in findings:
                    with ui.card().classes("w-full"):
                        with ui.row().classes("w-full items-start justify-between gap-4"):
                            with ui.column().classes("gap-1 flex-grow"):
                                ui.label(OUTCOME_LABELS.get(finding["outcome"], finding["outcome"])).classes("font-bold text-lg")
                                ui.label(finding["rationale"]).classes("text-gray-800")
                                ui.label(f"Criteriu #{finding['criterion_id']} · importanță {finding['importance']}").classes("text-xs text-gray-500")
                            if finding.get("decision"):
                                ui.badge(f"Decizie: {finding['decision']['action']}").props("outline")

                        ui.separator()
                        ui.label("6. Cele două pasaje pentru verificare").classes("font-semibold")
                        sources = finding.get("sources", [])
                        if len(sources) < 2:
                            ui.label("Nu există două pasaje textuale suficiente; cazul necesită analiză umană.").classes("text-red-700")
                        for source in sources[:2]:
                            with ui.expansion(source_title(source), icon="article").classes("w-full"):
                                ui.label(display_text(source.get("text", ""))).classes("whitespace-normal")
                                chapter = source.get("chapter") or source.get("subchapter")
                                if chapter:
                                    ui.label(f"Secțiune: {chapter}").classes("text-xs text-gray-500")

                        with ui.row().classes("w-full gap-2 mt-2"):
                            ui.button("Confirmă", on_click=lambda f=finding: simple_decision(f, "confirmed")).props("no-caps")
                            ui.button("Corectează", on_click=lambda f=finding: decision_dialog(f)).props("outline no-caps")
                            ui.button("Respinge", on_click=lambda f=finding: simple_decision(f, "rejected")).props("flat no-caps color=negative")
                            ui.button("Solicită clarificări", on_click=lambda f=finding: simple_decision(f, "clarification_requested")).props("flat no-caps")

        findings_view()

        async def analyze(force: bool):
            try:
                ui.notify("Analiza a pornit. Poate dura câteva minute...")
                await asyncio.to_thread(api.analyze_report, report_id, force)
                findings_view.refresh()
                history_view.refresh()
                ui.notify("Analiza a fost finalizată.", type="positive")
            except Exception as exc:
                ui.notify(str(exc), type="negative", timeout=15000)

        with ui.row().classes("gap-3"):
            ui.button("Analizează raportul", icon="smart_toy", on_click=lambda: analyze(False)).props("no-caps")
            ui.button("Reanalizează (revizie nouă)", on_click=lambda: analyze(True)).props("outline no-caps")

        ui.separator()
        ui.label("8–9. Generează nota/draftul și exportă").classes("text-xl font-semibold")

        async def generate(kind: str):
            try:
                result = await asyncio.to_thread(api.generate_output, report_id, kind)
                output_area.clear()
                with output_area:
                    ui.textarea(value=result["content"]).props("readonly autogrow").classes("w-full font-mono")
                    with ui.row().classes("gap-2"):
                        ui.button(
                            "Copiază",
                            on_click=lambda content=result["content"]: ui.run_javascript(
                                f"navigator.clipboard.writeText({json.dumps(content)})"
                            ),
                        ).props("no-caps")
                        ui.button("Descarcă .txt", on_click=lambda path=result["path"]: ui.download(path)).props("outline no-caps")
                history_view.refresh()
            except Exception as exc:
                ui.notify(str(exc), type="negative", timeout=10000)

        with ui.row().classes("gap-3"):
            ui.button("Generează notă de verificare", on_click=lambda: generate("verification_note")).props("no-caps")
            ui.button("Generează draft clarificare", on_click=lambda: generate("clarification_draft")).props("outline no-caps")

        @ui.refreshable
        def history_view():
            history = api.history(report_id)
            with ui.expansion("10. Istoric analiză și decizii", icon="history").classes("w-full"):
                ui.label(f"Analize: {len(history['jobs'])} · Decizii: {len(history['decisions'])} · Exporturi: {len(history['outputs'])}")
                for job in history["jobs"][:10]:
                    ui.label(
                        f"Analiză revizia {job['revision']} · {job['status']} · {job['model_name']} · "
                        f"{job['started_at']}"
                    ).classes("text-sm")
                for decision in history["decisions"][:20]:
                    ui.label(
                        f"Decizie #{decision['id']} · validare {decision['validation_id']} · "
                        f"{decision['action']} · {decision['decided_at']}"
                    ).classes("text-sm")
        history_view()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="ADR Monitoring Copilot", reload=False)
