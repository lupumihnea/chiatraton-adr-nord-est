from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import app, ui

from API.monitoring_api import MonitoringAPI

# Keep the newer UI modules registered.  In particular, project_details owns
# /project/{code}; the AI workflow therefore uses /monitoring/project/{id}
# instead of registering a second route with the same path.
from Interface import add_project  # noqa: F401
try:
    from Interface import project_details  # noqa: F401
except ImportError:
    project_details = None
try:
    from Interface import upload_documents  # noqa: F401
except ImportError:
    upload_documents = None


api = MonitoringAPI()

OUTCOME_LABELS = {
    "nonconcordance": "Neconcordanță",
    "missing_information": "Informații lipsă",
    "different_value_or_date": "Valoare/dată diferită",
    "insufficient_evidence": "Dovezi insuficiente",
    "cross_report_contradiction": "Contradicție între rapoarte",
    "human_review_required": "Necesită analiză umană",
}


# Preserve the visual work from the newer main branch.
ui.add_head_html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;700;800&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Quicksand', sans-serif;
            background-color: #fffdf5;
        }
    </style>
    """,
    shared=True,
)

assets_dir = ROOT / "Interface" / "Assets"
if assets_dir.is_dir():
    app.add_static_files("/Assets", str(assets_dir))


def display_text(text: str) -> str:
    """Display-only whitespace normalization; source wording in DB is untouched."""
    return re.sub(r"\s+", " ", text or "").strip()


def source_title(source: dict) -> str:
    role = {
        "criterion_source": "Sursa criteriului",
        "current_report": "Raport curent",
        "previous_report": "Raport anterior",
        "project_context": "Document proiect",
    }.get(source.get("role"), source.get("role", "Sursă"))
    return (
        f"{role} · document {source.get('document_id')} · "
        f"pagina {source.get('page', 'N/A')}"
    )


def _parse_project_code(value: object) -> int | None:
    text = str(value or "").strip()
    if len(text) != 6 or not text.isdigit():
        return None
    return int(text)


def _project_exists(project_id: int) -> bool:
    try:
        return api.get_project(project_id) is not None
    except Exception as exc:
        ui.notify(f"Eroare la verificarea proiectului: {exc}", type="negative")
        return False


@ui.page("/")
def home():
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes(
        "w-full items-center mt-8 space-y-6 min-h-[85vh]"
    ):
        logo = assets_dir / "Logo-ADR.png"
        if logo.exists():
            ui.image("/Assets/Logo-ADR.png").classes(
                "w-64 transition-transform hover:scale-105 duration-300 drop-shadow-sm"
            )

        mascot = assets_dir / "ADRut.png"
        with ui.row().classes(
            "items-center bg-white px-4 py-2 rounded-full shadow-md "
            "border-2 border-yellow-200 mb-2 hover:-translate-y-1 transition-transform"
        ):
            if mascot.exists():
                ui.image("/Assets/ADRut.png").classes(
                    "w-12 h-12 rounded-full bg-yellow-50 p-1"
                )
            ui.label("Haide să începem analiza!").classes(
                "text-lg font-extrabold text-gray-700 mx-3"
            )

        ui.label(
            "Selectează proiectul, apoi raportul/task-ul pe care vrei să îl verifici."
        ).classes("text-gray-600")

        with ui.column().classes("w-full max-w-xl items-start space-y-4"):
            search_bar = (
                ui.input(placeholder="Introdu codul SMIS...")
                .props(
                    'rounded outlined clearable mask="######" '
                    'input-class="text-2xl font-bold text-center"'
                )
                .classes(
                    "w-full text-2xl bg-white shadow-xl rounded-full border-0"
                )
            )

            ui.button(
                "Adaugă un nou proiect",
                icon="add",
                on_click=lambda: ui.navigate.to("/add_project"),
            ).props("flat rounded no-caps size=\"md\"").classes(
                "text-yellow-600 font-bold bg-yellow-50 hover:bg-yellow-100 "
                "transition-colors rounded-full px-4 py-1 text-sm"
            )

        def selected_project_id() -> int | None:
            project_id = _parse_project_code(search_bar.value)
            if project_id is None:
                ui.notify(
                    "Cod invalid. Introdu exact 6 cifre.",
                    type="warning",
                )
                return None
            if not _project_exists(project_id):
                ui.notify(
                    f"Proiectul cu codul SMIS {project_id} nu a fost găsit în baza de date.",
                    type="negative",
                )
                return None
            return project_id

        def access_project():
            project_id = selected_project_id()
            if project_id is not None:
                # Preserve the newer branch's project-details workflow.
                ui.navigate.to(f"/project/{project_id}")

        def access_ai_monitoring():
            project_id = selected_project_id()
            if project_id is not None:
                ui.navigate.to(f"/monitoring/project/{project_id}")

        with ui.row().classes("items-center gap-3 mt-4"):
            ui.button(
                "Accesează proiectul",
                on_click=access_project,
            ).props('push rounded size="lg" color="primary"').classes(
                "px-6 py-3 text-lg font-extrabold shadow-xl "
                "hover:scale-105 transition-transform duration-200 text-gray-900"
            )

            ui.button(
                "Monitorizare AI",
                icon="smart_toy",
                on_click=access_ai_monitoring,
            ).props("outline rounded no-caps size=\"lg\"").classes(
                "px-6 py-3 text-lg font-bold bg-white"
            )

        # Also expose the projects already present in the real DB; this replaces
        # the old hard-coded mock list without discarding the newer visual design.
        try:
            projects = api.list_projects()
        except Exception as exc:
            projects = []
            ui.notify(f"Nu s-au putut încărca proiectele: {exc}", type="negative")

        if projects:
            with ui.expansion(
                f"Proiecte disponibile ({len(projects)})",
                icon="folder_open",
            ).classes("w-full max-w-2xl bg-white rounded-xl shadow"):
                for project in projects:
                    project_id = int(project["id"])
                    with ui.row().classes(
                        "w-full items-center justify-between py-1"
                    ):
                        with ui.column().classes("gap-0"):
                            ui.label(
                                project.get("name") or f"Proiect {project_id}"
                            ).classes("font-bold")
                            ui.label(f"Cod SMIS: {project_id}").classes(
                                "text-xs text-gray-500"
                            )
                        with ui.row().classes("gap-1"):
                            ui.button(
                                "Detalii",
                                on_click=lambda pid=project_id: ui.navigate.to(
                                    f"/project/{pid}"
                                ),
                            ).props("flat no-caps")
                            ui.button(
                                "AI",
                                icon="smart_toy",
                                on_click=lambda pid=project_id: ui.navigate.to(
                                    f"/monitoring/project/{pid}"
                                ),
                            ).props("flat no-caps")

        ui.space()


@ui.page("/monitoring/project/{project_id}")
def monitoring_project_page(project_id: int):
    project = api.get_project(project_id)
    if not project:
        ui.label("Proiect inexistent")
        return

    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full max-w-6xl mx-auto p-6 gap-5"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(
                    project.get("name") or f"Proiect {project_id}"
                ).classes("text-3xl font-extrabold")
                ui.label(
                    f"Cod proiect: {project_id} · Monitorizare AI"
                ).classes("text-gray-600")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Detalii proiect",
                    on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
                ).props("flat no-caps")
                ui.button(
                    "Înapoi",
                    on_click=lambda: ui.navigate.to("/"),
                ).props("flat no-caps")

        criteria = api.list_criteria(project_id)
        reports = api.list_reports(project_id)
        ui.label(
            f"Criterii extrase: {len(criteria)} · "
            f"Rapoarte/task-uri: {len(reports)}"
        ).classes("font-medium")

        with ui.expansion(
            "Documente și criterii",
            icon="folder",
        ).classes("w-full bg-white rounded-xl shadow-sm"):
            ui.label(
                "Leagă documente existente de proiect "
                "(ID-uri separate prin virgulă):"
            )
            with ui.row().classes("w-full items-end"):
                doc_ids = ui.input(
                    "Document IDs",
                    placeholder="1,3,4,5,6,7,9",
                ).classes("flex-grow")
                role = ui.input(
                    "Rol",
                    value="project_document",
                ).classes("w-52")

                def link_docs():
                    try:
                        ids = [
                            int(x.strip())
                            for x in (doc_ids.value or "").split(",")
                            if x.strip()
                        ]
                        if not ids:
                            raise ValueError("Introdu cel puțin un document ID.")
                        api.link_documents(
                            project_id,
                            ids,
                            role.value or "project_document",
                        )
                        ui.notify(
                            f"Legate {len(ids)} documente",
                            type="positive",
                        )
                    except Exception as exc:
                        ui.notify(str(exc), type="negative")

                ui.button("Leagă", on_click=link_docs).props("no-caps")

            ui.separator()
            ui.label(
                "Re-extrage criteriile cu OpenRouter paid-only. "
                "Atenție: înlocuiește setul curent de criterii."
            )
            extract_ids = ui.input(
                "Document IDs pentru extracție",
                placeholder="1,3,4,5,6,7,9",
            ).classes("w-full")

            async def extract_criteria():
                try:
                    ids = [
                        int(x.strip())
                        for x in (extract_ids.value or "").split(",")
                        if x.strip()
                    ]
                    if not ids:
                        raise ValueError(
                            "Introdu ID-urile documentelor proiectului."
                        )
                    ui.notify("Extracția criteriilor a pornit...")
                    result = await asyncio.to_thread(
                        api.extract_criteria,
                        project_id,
                        ids,
                    )
                    ui.notify(
                        f"Au fost salvate {len(result)} criterii.",
                        type="positive",
                    )
                except Exception as exc:
                    ui.notify(
                        str(exc),
                        type="negative",
                        timeout=10000,
                    )

            ui.button(
                "Extrage criterii",
                icon="psychology",
                on_click=extract_criteria,
            ).props("no-caps")

        ui.label(
            "1. Selectează un raport din task-urile existente"
        ).classes("text-xl font-semibold")

        if not reports:
            ui.label(
                "Nu există încă rapoarte înregistrate pentru proiect."
            ).classes("text-orange-700")
        else:
            for report in reports:
                with ui.card().classes(
                    "w-full rounded-xl shadow-sm border border-yellow-100"
                ):
                    with ui.row().classes(
                        "w-full items-center justify-between"
                    ):
                        with ui.column().classes("gap-0"):
                            ui.label(
                                f"Raport #{report['sequence_number']} · "
                                f"{report['kind']}"
                            ).classes("font-semibold")
                            ui.label(
                                f"Perioadă: {report['period_start']} — "
                                f"{report['period_end']}"
                            ).classes("text-sm text-gray-600")
                            ui.label(
                                f"Status: {report['status']}"
                            ).classes("text-sm")
                        ui.button(
                            "Deschide task-ul",
                            on_click=lambda r=report: ui.navigate.to(
                                f"/report/{r['id']}"
                            ),
                        ).props("no-caps")

        with ui.expansion(
            "Înregistrează un raport existent",
            icon="description",
        ).classes("w-full bg-white rounded-xl shadow-sm"):
            ui.label(
                "Raportul trebuie să existe deja în tabela document și "
                "să aibă un fișier local asociat."
            )
            with ui.grid(columns=3).classes("w-full gap-3"):
                report_document_id = ui.number("Document ID", min=1)
                sequence = ui.number("Număr raport", min=1)
                kind = ui.select(
                    [
                        "implementation_progress",
                        "final_progress",
                        "durability",
                    ],
                    value="implementation_progress",
                    label="Tip raport",
                )
                period_start = ui.input(
                    "Început perioadă",
                    placeholder="2025-01-01",
                )
                period_end = ui.input(
                    "Sfârșit perioadă",
                    placeholder="2025-03-31",
                )

            def add_report():
                try:
                    if report_document_id.value is None or sequence.value is None:
                        raise ValueError(
                            "Document ID și numărul raportului sunt obligatorii."
                        )
                    rid = api.add_report(
                        project_id=project_id,
                        document_id=int(report_document_id.value),
                        sequence_number=int(sequence.value),
                        kind=kind.value,
                        period_start=period_start.value,
                        period_end=period_end.value,
                    )
                    ui.notify(
                        f"Raport înregistrat cu id {rid}",
                        type="positive",
                    )
                    ui.navigate.to(f"/report/{rid}")
                except Exception as exc:
                    ui.notify(str(exc), type="negative")

            ui.button(
                "Înregistrează raport",
                on_click=add_report,
            ).props("no-caps")


@ui.page("/report/{report_id}")
def report_page(report_id: int):
    report = api.get_report(report_id)
    if not report:
        ui.label("Raport inexistent")
        return

    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-5"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.column().classes("gap-0"):
                ui.label(
                    f"Raport #{report['sequence_number']} · {report['kind']}"
                ).classes("text-3xl font-extrabold")
                ui.label(
                    f"Perioadă: {report['period_start']} — "
                    f"{report['period_end']}"
                ).classes("text-gray-600")
            ui.button(
                "Înapoi la proiect",
                on_click=lambda: ui.navigate.to(
                    f"/monitoring/project/{report['project_id']}"
                ),
            ).props("flat no-caps")

        ui.label(
            "AI-ul compară raportul cu criteriile, contractul și anexele, "
            "documentele relevante și rapoartele periodice anterioare. "
            "Interfața afișează numai excepțiile; decizia rămâne la utilizator."
        ).classes("text-gray-700")

        findings_container = ui.column().classes("w-full gap-4")
        output_area = ui.column().classes("w-full")

        def decision_dialog(finding: dict):
            with ui.dialog() as dialog, ui.card().classes(
                "w-full max-w-2xl"
            ):
                ui.label("Corectează constatarea").classes(
                    "text-xl font-semibold"
                )
                final_outcome = ui.select(
                    list(OUTCOME_LABELS.keys()),
                    value=finding["outcome"],
                    label="Rezultat final",
                ).classes("w-full")
                corrected_text = ui.textarea(
                    "Corecție / formulare utilizator",
                    value=finding["rationale"],
                ).classes("w-full")
                comment = ui.textarea(
                    "Comentariu opțional"
                ).classes("w-full")

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
                    ui.notify(
                        "Corecția a fost salvată.",
                        type="positive",
                    )

                with ui.row().classes("justify-end w-full"):
                    ui.button(
                        "Anulează",
                        on_click=dialog.close,
                    ).props("flat")
                    ui.button("Salvează", on_click=save)
            dialog.open()

        def simple_decision(finding: dict, action: str):
            try:
                api.decide(
                    finding["id"],
                    action,
                    final_outcome=finding["outcome"],
                )
                findings_view.refresh()
                ui.notify(
                    "Decizia a fost păstrată în istoric.",
                    type="positive",
                )
            except Exception as exc:
                ui.notify(str(exc), type="negative")

        @ui.refreshable
        def findings_view():
            findings_container.clear()
            findings = api.list_findings(report_id)
            with findings_container:
                ui.label(
                    f"5. Excepții identificate: {len(findings)}"
                ).classes("text-xl font-semibold")
                if not findings:
                    ui.label(
                        "Nu există excepții salvate. Rulează analiza sau "
                        "raportul nu are constatări de afișat."
                    ).classes("text-gray-600")
                    return

                for finding in findings:
                    with ui.card().classes(
                        "w-full rounded-xl shadow-sm border border-yellow-100"
                    ):
                        with ui.row().classes(
                            "w-full items-start justify-between gap-4"
                        ):
                            with ui.column().classes("gap-1 flex-grow"):
                                ui.label(
                                    OUTCOME_LABELS.get(
                                        finding["outcome"],
                                        finding["outcome"],
                                    )
                                ).classes("font-bold text-lg")
                                ui.label(
                                    finding["rationale"]
                                ).classes("text-gray-800")
                                ui.label(
                                    f"Criteriu #{finding['criterion_id']} · "
                                    f"importanță {finding['importance']}"
                                ).classes("text-xs text-gray-500")
                            if finding.get("decision"):
                                ui.badge(
                                    f"Decizie: "
                                    f"{finding['decision']['action']}"
                                ).props("outline")

                        ui.separator()
                        ui.label(
                            "6. Cele două pasaje pentru verificare"
                        ).classes("font-semibold")
                        sources = finding.get("sources", [])
                        if len(sources) < 2:
                            ui.label(
                                "Nu există două pasaje textuale suficiente; "
                                "cazul necesită analiză umană."
                            ).classes("text-red-700")
                        for source in sources[:2]:
                            with ui.expansion(
                                source_title(source),
                                icon="article",
                            ).classes("w-full"):
                                ui.label(
                                    display_text(source.get("text", ""))
                                ).classes("whitespace-normal")
                                chapter = (
                                    source.get("chapter")
                                    or source.get("subchapter")
                                )
                                if chapter:
                                    ui.label(
                                        f"Secțiune: {chapter}"
                                    ).classes("text-xs text-gray-500")

                        with ui.row().classes("w-full gap-2 mt-2"):
                            ui.button(
                                "Confirmă",
                                on_click=lambda f=finding: simple_decision(
                                    f,
                                    "confirmed",
                                ),
                            ).props("no-caps")
                            ui.button(
                                "Corectează",
                                on_click=lambda f=finding: decision_dialog(f),
                            ).props("outline no-caps")
                            ui.button(
                                "Respinge",
                                on_click=lambda f=finding: simple_decision(
                                    f,
                                    "rejected",
                                ),
                            ).props("flat no-caps color=negative")
                            ui.button(
                                "Solicită clarificări",
                                on_click=lambda f=finding: simple_decision(
                                    f,
                                    "clarification_requested",
                                ),
                            ).props("flat no-caps")

        findings_view()

        async def analyze(force: bool):
            try:
                ui.notify(
                    "Analiza a pornit. Poate dura câteva minute..."
                )
                await asyncio.to_thread(
                    api.analyze_report,
                    report_id,
                    force,
                )
                findings_view.refresh()
                history_view.refresh()
                ui.notify(
                    "Analiza a fost finalizată.",
                    type="positive",
                )
            except Exception as exc:
                ui.notify(
                    str(exc),
                    type="negative",
                    timeout=15000,
                )

        with ui.row().classes("gap-3"):
            ui.button(
                "Analizează raportul",
                icon="smart_toy",
                on_click=lambda: analyze(False),
            ).props("no-caps")
            ui.button(
                "Reanalizează (revizie nouă)",
                on_click=lambda: analyze(True),
            ).props("outline no-caps")

        ui.separator()
        ui.label(
            "8–9. Generează nota/draftul și exportă"
        ).classes("text-xl font-semibold")

        async def generate(kind: str):
            try:
                result = await asyncio.to_thread(
                    api.generate_output,
                    report_id,
                    kind,
                )
                output_area.clear()
                with output_area:
                    ui.textarea(
                        value=result["content"]
                    ).props("readonly autogrow").classes(
                        "w-full font-mono"
                    )
                    with ui.row().classes("gap-2"):
                        ui.button(
                            "Copiază",
                            on_click=lambda content=result["content"]:
                                ui.run_javascript(
                                    "navigator.clipboard.writeText("
                                    f"{json.dumps(content)})"
                                ),
                        ).props("no-caps")
                        ui.button(
                            "Descarcă .txt",
                            on_click=lambda path=result["path"]:
                                ui.download(path),
                        ).props("outline no-caps")
                history_view.refresh()
            except Exception as exc:
                ui.notify(
                    str(exc),
                    type="negative",
                    timeout=10000,
                )

        with ui.row().classes("gap-3"):
            ui.button(
                "Generează notă de verificare",
                on_click=lambda: generate("verification_note"),
            ).props("no-caps")
            ui.button(
                "Generează draft clarificare",
                on_click=lambda: generate("clarification_draft"),
            ).props("outline no-caps")

        @ui.refreshable
        def history_view():
            history = api.history(report_id)
            with ui.expansion(
                "10. Istoric analiză și decizii",
                icon="history",
            ).classes("w-full"):
                ui.label(
                    f"Analize: {len(history['jobs'])} · "
                    f"Decizii: {len(history['decisions'])} · "
                    f"Exporturi: {len(history['outputs'])}"
                )
                for job in history["jobs"][:10]:
                    ui.label(
                        f"Analiză revizia {job['revision']} · "
                        f"{job['status']} · {job['model_name']} · "
                        f"{job['started_at']}"
                    ).classes("text-sm")
                for decision in history["decisions"][:20]:
                    ui.label(
                        f"Decizie #{decision['id']} · "
                        f"validare {decision['validation_id']} · "
                        f"{decision['action']} · "
                        f"{decision['decided_at']}"
                    ).classes("text-sm")

        history_view()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="ADR Analizator", reload=False)
