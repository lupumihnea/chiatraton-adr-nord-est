"""Project details with obligations and progress reports.

Backend contract names remain Criterion/Report.  The UI deliberately presents
criteria as obligations and reports as progress against those obligations.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from Interface.api_client import (
    IdempotencyKeyManager,
    api_client,
    api_error_message,
    json_fingerprint,
)

REPORT_STATUS_LABELS = {
    "created": "Pregătit pentru analiză",
    "analysis_queued": "Analiză în așteptare",
    "analysis_in_progress": "Analiză în curs",
    "awaiting_user_decision": "Progres analizat",
    "completed": "Finalizat",
    "analysis_failed": "Analiza a eșuat",
}


@ui.page("/project/{project_id}")
async def project_details_page(project_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")
    key_manager = IdempotencyKeyManager()

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30"):
        with ui.row().classes("w-full max-w-6xl p-4"):
            ui.button(
                "Înapoi la start",
                icon="home",
                on_click=lambda: ui.navigate.to("/"),
            ).props("flat rounded no-caps size=md text-color=grey-8").classes(
                "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
            )

        loading = ui.row().classes("items-center gap-2 text-gray-600 mt-8")
        with loading:
            ui.spinner(size="lg")
            loading_label = ui.label("Se încarcă proiectul...")

        content = ui.column().classes("w-full items-center gap-6 pb-8")

        async def load_after_connect() -> None:
            try:
                project = await api_client.get_project(project_id)
            except Exception as error:
                loading.set_visibility(False)
                with content:
                    ui.label(api_error_message(error)).classes("text-red-700 font-bold")
                    ui.button(
                        "Reîncearcă",
                        on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
                    ).props("no-caps")
                return

            if project is None:
                loading.set_visibility(False)
                with content:
                    with ui.column().classes(
                        "w-full max-w-6xl items-center bg-white shadow-xl "
                        "rounded-[1.5rem] p-8"
                    ):
                        ui.icon("search_off", size="xl").classes("text-gray-400")
                        ui.label("Proiectul nu a fost găsit.").classes(
                            "text-xl font-bold text-gray-700"
                        )
                return

            loading_label.text = "Se încarcă obligațiile și rapoartele..."
            try:
                criteria = await api_client.list_all_project_criteria(project_id)
            except Exception as error:
                criteria = []
                criteria_error = api_error_message(error)
            else:
                criteria_error = None

            try:
                reports = await api_client.list_all_project_reports(project_id)
            except Exception as error:
                reports = []
                reports_error = api_error_message(error)
            else:
                reports_error = None

            loading.set_visibility(False)
            content.clear()

            async def start_report_analysis(report: dict[str, Any]) -> None:
                report_id = str(report.get("id") or "")
                if not report_id:
                    ui.notify("Raportul nu are ID.", type="negative")
                    return
                if not criteria:
                    ui.notify(
                        "Confirmă mai întâi cel puțin o obligație a proiectului.",
                        type="warning",
                    )
                    return
                payload = {
                    "reportId": report_id,
                    "projectDocumentIds": [],
                    "previousReportIds": [],
                }
                fingerprint = json_fingerprint(payload)
                operation = f"analyze-progress:{report_id}"
                key = key_manager.key_for(operation, fingerprint)
                try:
                    job = await api_client.create_report_analysis_job(
                        report_id,
                        idempotency_key=key,
                    )
                except Exception as error:
                    ui.notify(api_error_message(error), type="negative", timeout=10000)
                    return
                key_manager.mark_succeeded(operation, fingerprint)
                job_id = str(job.get("id") or "")
                if not job_id:
                    ui.notify("Job-ul de analiză nu are ID.", type="negative")
                    return
                ui.navigate.to(
                    f"/project/{project_id}/report-analysis/{report_id}/{job_id}"
                )

            with content:
                with ui.row().classes(
                    "w-full max-w-6xl px-4 gap-6 flex-nowrap items-stretch"
                ):
                    with ui.column().classes(
                        "w-3/4 bg-white shadow-xl rounded-[1.5rem] p-6 "
                        "border border-yellow-100"
                    ):
                        with ui.row().classes("items-center mb-2 gap-2"):
                            ui.icon("info", size="sm").classes("text-yellow-600")
                            ui.label("Detalii Proiect").classes(
                                "text-2xl font-extrabold text-gray-800"
                            )

                        ui.separator().classes("mb-4 opacity-50")

                        details = (
                            ("Project ID", project["id"]),
                            ("Data finalizării", project["completionDate"]),
                            ("Nume Proiect", project["name"]),
                            ("Sfârșitul monitorizării", project["monitoringEndDate"]),
                        )
                        with ui.grid(columns=2).classes("w-full gap-4"):
                            for label, value in details:
                                with ui.column().classes("space-y-1"):
                                    ui.label(label).classes(
                                        "text-xs font-extrabold text-gray-500 uppercase "
                                        "tracking-wide"
                                    )
                                    ui.label(str(value)).classes(
                                        "text-base font-bold text-gray-800 bg-gray-50 px-3 "
                                        "py-1 rounded-xl border border-gray-100 w-full break-all"
                                    )

                    with ui.column().classes(
                        "w-1/4 items-center justify-center bg-yellow-50 shadow-xl "
                        "rounded-[1.5rem] p-6 border-2 border-yellow-200 transition-all "
                        "hover:bg-yellow-100/80"
                    ):
                        ui.icon("cloud_upload", size="50px").classes(
                            "text-yellow-600 mb-4"
                        )
                        ui.button(
                            "Încarcă Documente",
                            icon="upload_file",
                            on_click=lambda: ui.navigate.to(f"/upload/{project_id}"),
                        ).props("push rounded size=md color=primary").classes(
                            "px-4 py-2 text-sm font-extrabold shadow-lg hover:scale-105 "
                            "transition-transform duration-200 text-gray-900 w-full"
                        )

                with ui.column().classes(
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-yellow-100"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("fact_check", size="sm").classes("text-yellow-600")
                            ui.label("Obligații confirmate").classes(
                                "text-2xl font-extrabold text-gray-800"
                            )
                        ui.button(
                            "Încarcă documente și extrage obligații",
                            icon="document_scanner",
                            on_click=lambda: ui.navigate.to(f"/upload/{project_id}"),
                        ).props("outline rounded no-caps")

                    ui.label(
                        "Obligațiile provin din documentele legate de apel și din "
                        "documentele inițiale ale proiectului."
                    ).classes("text-sm text-gray-600")
                    ui.separator().classes("my-3 opacity-50")

                    if criteria_error:
                        ui.label(criteria_error).classes("text-red-700")

                    if not criteria:
                        ui.label(
                            "Nu există încă obligații confirmate. Încarcă "
                            "documentele-sursă, "
                            "apoi confirmă/corectează/respinge propunerile AI."
                        ).classes("text-gray-600")
                    else:
                        ui.label(f"{len(criteria)} obligații confirmate").classes(
                            "font-bold text-green-700 mb-2"
                        )
                        for criterion in criteria:
                            with ui.card().classes(
                                "w-full shadow-sm rounded-xl border border-green-100"
                            ):
                                ui.label(str(criterion.get("code", ""))).classes(
                                    "font-extrabold text-green-800"
                                )
                                ui.label(
                                    " ".join(str(criterion.get("description", "")).split())
                                ).classes("text-gray-800")
                                deadline = criterion.get("deadline") or "Fără termen explicit"
                                ui.label(f"Termen: {deadline}").classes(
                                    "text-sm text-gray-600"
                                )
                                for anchor in criterion.get("sourceAnchors") or []:
                                    with ui.expansion(
                                        "Sursa obligației · pagina "
                                        f"{anchor.get('pageNumber', '?')}",
                                        icon="article",
                                    ).classes("w-full"):
                                        ui.label(
                                            " ".join(
                                                str(anchor.get("passage", "")).split()
                                            )
                                        ).classes("whitespace-normal")

                with ui.column().classes(
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-blue-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("timeline", size="sm").classes("text-blue-600")
                        ui.label("Rapoarte de progres").classes(
                            "text-2xl font-extrabold text-gray-800"
                        )
                    ui.label(
                        "Rapoartele nu adaugă obligații. AI-ul le compară cu obligațiile "
                        "confirmate și produce numai starea/progresul fiecărei obligații."
                    ).classes("text-sm text-gray-600")
                    ui.separator().classes("my-3 opacity-50")

                    if reports_error:
                        ui.label(reports_error).classes("text-red-700")

                    if not reports:
                        ui.label(
                            "Nu există încă rapoarte de progres încărcate."
                        ).classes("text-gray-600")
                    else:
                        for report in reports:
                            status = str(report.get("status", "created"))
                            with ui.card().classes(
                                "w-full shadow-sm rounded-xl border border-blue-100"
                            ):
                                with ui.row().classes(
                                    "w-full items-center justify-between gap-3"
                                ):
                                    with ui.column().classes("gap-1"):
                                        ui.label("Raport de progres").classes(
                                            "font-extrabold text-blue-800"
                                        )
                                        ui.label(
                                            f"Perioadă: {report.get('periodStart', '?')} → "
                                            f"{report.get('periodEnd', '?')}"
                                        ).classes("text-gray-700")
                                        ui.label(
                                            f"Status: {REPORT_STATUS_LABELS.get(status, status)}"
                                        ).classes("text-sm font-bold text-gray-600")

                                    if status in {"created", "analysis_failed"}:
                                        button = ui.button(
                                            "Analizează progresul",
                                            icon="psychology",
                                            on_click=lambda r=report: start_report_analysis(r),
                                        ).props("no-caps")
                                        if not criteria:
                                            button.disable()
                                    elif status in {"awaiting_user_decision", "completed"}:
                                        ui.button(
                                            "Vezi progresul",
                                            icon="visibility",
                                            on_click=lambda r=report: ui.navigate.to(
                                                f"/project/{project_id}/report-analysis/"
                                                f"{r.get('id')}/results"
                                            ),
                                        ).props("outline no-caps")
                                    else:
                                        ui.label(
                                            "Analiza rulează în fundal; reîncarcă pagina "
                                            "pentru status."
                                        ).classes("text-sm text-blue-700")

        await ui.context.client.connected(timeout=10.0)
        await load_after_connect()
