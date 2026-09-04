"""Document upload with category-aware AI behavior.

The four existing UI categories stay unchanged. Their meaning is operational:
- call/initial documents can propose project obligations;
- progress reports are analyzed against already confirmed obligations;
- other documents are stored without automatically creating obligations.

No database/API schema change is required: the selected category continues to be
persisted through the existing Document.displayName field.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

from nicegui import events, ui

from Interface.api_client import (
    APIUnavailableError,
    APITimeoutError,
    IdempotencyKeyManager,
    api_client,
    api_error_message,
    json_fingerprint,
    upload_fingerprint,
)

MAX_PDF_BYTES = 26_214_400
CATEGORY_OPTIONS = {
    "apel": "Documente legate de apel",
    "initiale": "Documente inițiale",
    "rapoarte": "Rapoarte de progres",
    "altele": "Alte documente",
}
OBLIGATION_SOURCE_CATEGORIES = {"apel", "initiale"}
PROGRESS_REPORT_CATEGORY = "rapoarte"
CONTEXT_ONLY_CATEGORY = "altele"


async def _read_pdf(event: events.UploadEventArguments) -> tuple[str, bytes]:
    filename = Path(event.file.name).name
    if Path(filename).suffix.lower() != ".pdf":
        raise ValueError("Te rugăm să alegi un fișier PDF.")
    content = await event.file.read()
    if not content:
        raise ValueError("Fișierul selectat este gol.")
    if len(content) > MAX_PDF_BYTES:
        raise ValueError("Fișierul PDF depășește limita de 25 MiB.")
    return filename, content


def _selected_category(row: dict[str, Any]) -> str | None:
    """Return the explicitly selected category, or ``None``.

    There is intentionally no default category. A missing selection must stop
    submission instead of silently routing a project document to ``altele``.
    """
    category_select = row.get("category_select")
    selected = getattr(category_select, "value", None)
    if selected in CATEGORY_OPTIONS:
        return str(selected)

    stored = row.get("category")
    if stored in CATEGORY_OPTIONS:
        return str(stored)

    return None


def _valid_report_period(row: dict[str, Any]) -> str | None:
    if row.get("category") != PROGRESS_REPORT_CATEGORY:
        return None
    start = str(row.get("period_start") or "").strip()
    end = str(row.get("period_end") or "").strip()
    if not start or not end:
        return "Completează perioada pentru fiecare raport de progres."
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return "Perioada raportului de progres nu conține date valide."
    if end_date < start_date:
        return "Data de sfârșit a raportului trebuie să fie după data de început."
    return None


@ui.page("/upload/{project_id}")
def upload_documents_page(project_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    upload_state: list[dict[str, Any]] = []
    key_manager = IdempotencyKeyManager()

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30 p-4"):
        with ui.row().classes("w-full max-w-4xl mb-4"):
            back_button = ui.button(
                "Înapoi la proiect",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
            ).props("flat rounded no-caps size=md text-color=grey-8").classes(
                "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
            )

        with ui.column().classes(
            "w-full max-w-4xl bg-white shadow-2xl rounded-[2rem] p-6 "
            "space-y-4 border border-yellow-100"
        ):
            with ui.row().classes("items-center gap-3 mb-2"):
                ui.icon("cloud_upload", size="md").classes("text-yellow-600")
                ui.label(f"Încărcare documente - Proiect {project_id}").classes(
                    "text-2xl font-extrabold text-gray-800 break-all"
                )

            ui.label(
                "Ordinea este obligatorie: încarcă mai întâi documentele inițiale, "
                "confirmă obligațiile propuse și abia apoi încarcă rapoarte de progres. "
                "Fiecare raport este verificat față de toate obligațiile confirmate."
            ).classes("text-sm text-gray-600")

            ui.separator().classes("opacity-50")
            uploads_container = ui.column().classes("w-full space-y-4")

            def add_upload_row() -> None:
                row_data: dict[str, Any] = {
                    "operation": f"upload-document:{uuid4()}",
                    "category": None,
                    "category_select": None,
                    "filename": None,
                    "content": None,
                    "status_label": None,
                    "completed": False,
                    "document_id": None,
                    "period_start": None,
                    "period_end": None,
                }
                upload_state.append(row_data)

                with uploads_container:
                    outer = ui.column().classes(
                        "w-full bg-gray-50 p-4 rounded-xl border border-gray-200 "
                        "shadow-sm transition-all gap-3"
                    )
                    with outer:
                        controls = ui.row().classes(
                            "w-full items-center gap-4 flex-nowrap"
                        )
                        with controls:
                            category_select = ui.select(
                                CATEGORY_OPTIONS,
                                value=None,
                                label="Alege categoria documentului",
                            ).props(
                                "outlined rounded bg-white hide-bottom-space"
                            ).classes("w-1/3 min-w-[240px]")
                            row_data["category_select"] = category_select

                            middle_container = ui.row().classes("flex-grow items-center")

                            with middle_container:
                                async def on_file_uploaded(
                                    event: events.UploadEventArguments,
                                ) -> None:
                                    try:
                                        filename, content = await _read_pdf(event)
                                    except ValueError as error:
                                        ui.notify(
                                            str(error),
                                            type="negative",
                                            position="top",
                                            classes="font-bold",
                                        )
                                        return

                                    row_data["filename"] = filename
                                    row_data["content"] = content
                                    row_data["completed"] = False
                                    # Keep the selector editable until Submit.
                                    row_data["category"] = _selected_category(row_data)
                                    upload_component.set_visibility(False)

                                    with middle_container:
                                        with ui.row().classes(
                                            "w-full bg-green-50 border border-green-200 p-3 "
                                            "rounded-xl items-center justify-between shadow-inner"
                                        ):
                                            with ui.row().classes("items-center gap-2"):
                                                ui.icon("picture_as_pdf", size="sm").classes(
                                                    "text-red-500"
                                                )
                                                ui.label(filename).classes(
                                                    "text-base font-extrabold text-green-900"
                                                )

                                            with ui.row().classes("items-center gap-1"):
                                                ui.icon("check_circle", size="sm").classes(
                                                    "text-green-600"
                                                )
                                                row_data["status_label"] = ui.label(
                                                    "Pregătit"
                                                ).classes(
                                                    "text-xs font-bold text-green-700 "
                                                    "uppercase tracking-wide"
                                                )

                                    ui.notify(
                                        "Fișier atașat local cu succes!",
                                        type="info",
                                        position="top",
                                    )

                                upload_component = ui.upload(
                                    multiple=False,
                                    auto_upload=True,
                                    on_upload=on_file_uploaded,
                                    max_file_size=MAX_PDF_BYTES,
                                    on_rejected=lambda: ui.notify(
                                        "Alege un singur fișier PDF de maximum 25 MiB.",
                                        type="negative",
                                        position="top",
                                        classes="font-bold",
                                    ),
                                ).props(
                                    'accept=".pdf" max-files=1 '
                                    'label="Trage fișierul PDF aici" flat bordered '
                                    'color=white text-color=grey-9 hide-upload-btn'
                                ).classes("w-full shadow-sm bg-white")

                            def delete_row() -> None:
                                upload_state.remove(row_data)
                                outer.delete()

                            ui.button(icon="delete", on_click=delete_row).props(
                                "flat round color=negative size=md"
                            ).classes(
                                "bg-red-50 hover:bg-red-100 transition-colors"
                            )

                        report_period = ui.row().classes(
                            "w-full items-center gap-3 bg-blue-50/70 border border-blue-100 "
                            "rounded-xl p-3"
                        )
                        with report_period:
                            ui.icon("date_range").classes("text-blue-600")
                            ui.label("Perioada raportată").classes(
                                "font-bold text-blue-900"
                            )
                            start_input = ui.input("De la").props(
                                "type=date outlined dense"
                            ).classes("w-48")
                            end_input = ui.input("Până la").props(
                                "type=date outlined dense"
                            ).classes("w-48")
                            ui.label(
                                "Este folosită numai pentru analiza progresului."
                            ).classes("text-xs text-blue-800")
                        report_period.set_visibility(False)

                        def category_changed(event: Any) -> None:
                            value = event.value
                            category = str(value) if value in CATEGORY_OPTIONS else None
                            row_data["category"] = category
                            print(
                                f"[UI] category changed: {category!r}",
                                flush=True,
                            )
                            report_period.set_visibility(
                                category == PROGRESS_REPORT_CATEGORY
                            )

                        category_select.on_value_change(category_changed)
                        start_input.on_value_change(
                            lambda event: row_data.update({"period_start": event.value})
                        )
                        end_input.on_value_change(
                            lambda event: row_data.update({"period_end": event.value})
                        )

            add_upload_row()

            ui.button(
                "+ Adaugă altă categorie de document",
                on_click=add_upload_row,
            ).props("flat rounded no-caps size=md").classes(
                "text-yellow-700 font-bold bg-yellow-50 hover:bg-yellow-100 "
                "transition-colors rounded-full px-6 py-2 mt-2 self-start"
            )

            ui.separator().classes("my-2 opacity-50")

            error_label = ui.label().classes(
                "w-full text-sm font-bold text-red-700 bg-red-50 p-3 rounded-xl"
            )
            error_label.set_visibility(False)

            loading = ui.row().classes("items-center gap-2 text-gray-600")
            with loading:
                ui.spinner(size="sm")
                loading_text = ui.label("Se trimit documentele...")
            loading.set_visibility(False)

            with ui.row().classes("w-full justify-end mt-2 pt-2"):
                async def submit_documents() -> None:
                    pending = [
                        row
                        for row in upload_state
                        if row["filename"]
                        and row["content"]
                        and not row["completed"]
                    ]
                    if not pending:
                        ui.notify(
                            "Nu ai selectat niciun document pentru trimitere.",
                            type="warning",
                            position="top",
                        )
                        return

                    # The UI control is the source of truth immediately before routing.
                    for row in pending:
                        category = _selected_category(row)
                        if category is None:
                            filename = str(row.get("filename") or "document")
                            ui.notify(
                                f"Alege categoria pentru {filename} înainte de trimitere.",
                                type="warning",
                                position="top",
                                timeout=8000,
                            )
                            return
                        row["category"] = category
                        period_error = _valid_report_period(row)
                        if period_error:
                            ui.notify(period_error, type="warning", position="top")
                            return

                    progress_rows = [
                        row for row in pending if row["category"] == PROGRESS_REPORT_CATEGORY
                    ]
                    baseline_rows = [
                        row
                        for row in pending
                        if row["category"] in OBLIGATION_SOURCE_CATEGORIES
                    ]
                    if progress_rows and baseline_rows:
                        ui.notify(
                            "Încarcă documentele inițiale și rapoartele de progres în etape "
                            "separate: mai întâi baseline-ul și confirmarea obligațiilor, apoi raportul.",
                            type="warning",
                            position="top",
                            timeout=10000,
                        )
                        return
                    if len(progress_rows) > 1:
                        ui.notify(
                            "Încarcă rapoartele de progres pe rând. Analizează raportul curent "
                            "înainte de a încărca următorul, pentru a păstra istoricul schimbărilor.",
                            type="warning",
                            position="top",
                            timeout=10000,
                        )
                        return
                    if progress_rows:
                        try:
                            confirmed = await api_client.list_all_project_criteria(project_id)
                        except Exception as error:
                            ui.notify(api_error_message(error), type="negative", timeout=10000)
                            return
                        if not confirmed:
                            ui.notify(
                                "Confirmă mai întâi obligațiile extrase din documentele inițiale. "
                                "Raportul de progres nu poate fi primit înainte de baseline.",
                                type="warning",
                                position="top",
                                timeout=10000,
                            )
                            return

                    submit_button.disable()
                    back_button.disable()
                    loading.set_visibility(True)
                    error_label.set_visibility(False)
                    uploaded = 0

                    try:
                        for row_data in pending:
                            filename = str(row_data["filename"])
                            content = bytes(row_data["content"])
                            category = _selected_category(row_data)
                            if category is None:
                                raise RuntimeError(
                                    f"Categoria documentului {filename!r} nu este selectată."
                                )
                            row_data["category"] = category
                            display_name = CATEGORY_OPTIONS[category]
                            print(
                                f"[UI] submit document: {filename!r}, category={category!r}",
                                flush=True,
                            )
                            fingerprint = upload_fingerprint(
                                project_id=project_id,
                                filename=filename,
                                content_type="application/pdf",
                                content=content,
                                display_name=display_name,
                            )
                            idempotency_key = key_manager.key_for(
                                str(row_data["operation"]), fingerprint
                            )
                            try:
                                uploaded_document = await api_client.upload_document(
                                    project_id,
                                    filename=filename,
                                    content=content,
                                    content_type="application/pdf",
                                    display_name=display_name,
                                    idempotency_key=idempotency_key,
                                )
                            except Exception as error:
                                message = api_error_message(error)
                                error_label.text = message
                                error_label.set_visibility(True)
                                status_label = row_data["status_label"]
                                if status_label is not None:
                                    status_label.text = "Eroare"
                                    status_label.classes(
                                        replace=(
                                            "text-xs font-bold text-red-700 "
                                            "uppercase tracking-wide"
                                        )
                                    )
                                ui.notify(
                                    message,
                                    type="negative",
                                    position="top",
                                    timeout=8000,
                                )
                                return

                            row_data["completed"] = True
                            document_id = uploaded_document.get("id")
                            if document_id:
                                row_data["document_id"] = str(document_id)
                            key_manager.mark_succeeded(
                                str(row_data["operation"]), fingerprint
                            )
                            status_label = row_data["status_label"]
                            if status_label is not None:
                                status_label.text = "Încărcat"
                            uploaded += 1

                        report_rows = [
                            row
                            for row in pending
                            if row["category"] == PROGRESS_REPORT_CATEGORY
                            and row.get("document_id")
                        ]
                        obligation_rows = [
                            row
                            for row in pending
                            if row["category"] in OBLIGATION_SOURCE_CATEGORIES
                            and row.get("document_id")
                        ]
                        other_rows = [
                            row
                            for row in pending
                            if row["category"] == CONTEXT_ONLY_CATEGORY
                            and row.get("document_id")
                        ]

                        # Progress reports become Report resources and never enter
                        # the obligation-extraction job.
                        created_reports: list[dict[str, Any]] = []
                        for row in report_rows:
                            payload = {
                                "projectId": project_id,
                                "documentId": row["document_id"],
                                "periodStart": row["period_start"],
                                "periodEnd": row["period_end"],
                                "reportType": "implementation_progress",
                            }
                            fingerprint = json_fingerprint(payload)
                            operation = f"create-progress-report:{row['document_id']}"
                            key = key_manager.key_for(operation, fingerprint)
                            report = await api_client.create_project_report(
                                project_id,
                                period_start=str(row["period_start"]),
                                period_end=str(row["period_end"]),
                                document_id=str(row["document_id"]),
                                idempotency_key=key,
                            )
                            key_manager.mark_succeeded(operation, fingerprint)
                            created_reports.append(report)

                        if other_rows:
                            ui.notify(
                                f"{len(other_rows)} document(e) suport au fost păstrate fără "
                                "a genera automat obligații.",
                                type="info",
                                timeout=7000,
                            )

                        # Project-source documents propose obligations first. If reports
                        # are uploaded in the same batch, they remain saved until review.
                        obligation_document_ids = [
                            str(row["document_id"]) for row in obligation_rows
                        ]
                        if obligation_document_ids:
                            loading_text.text = "Pornim extragerea obligațiilor..."
                            extraction_payload = {
                                "projectId": project_id,
                                "documentIds": sorted(obligation_document_ids),
                            }
                            extraction_fingerprint = json_fingerprint(extraction_payload)
                            extraction_operation = f"extract-obligations:{project_id}"
                            extraction_key = key_manager.key_for(
                                extraction_operation, extraction_fingerprint
                            )
                            job = None
                            last_error: Exception | None = None
                            for attempt in range(3):
                                try:
                                    job = await api_client.create_criterion_extraction_job(
                                        project_id,
                                        document_ids=obligation_document_ids,
                                        idempotency_key=extraction_key,
                                    )
                                    break
                                except (APITimeoutError, APIUnavailableError) as error:
                                    last_error = error
                                    if attempt < 2:
                                        ui.notify(
                                            "API-ul este ocupat cu inițializarea AI; "
                                            f"reîncercăm pornirea extracției ({attempt + 2}/3)...",
                                            type="warning",
                                            timeout=5000,
                                        )
                                        await asyncio.sleep(2.0 * (attempt + 1))
                                        continue
                                    break
                                except Exception as error:
                                    last_error = error
                                    break

                            if job is None:
                                ui.notify(
                                    "Documentele sunt încărcate, dar nu am primit confirmarea "
                                    "job-ului de extragere a obligațiilor. "
                                    + (api_error_message(last_error) if last_error else ""),
                                    type="negative",
                                    timeout=15000,
                                )
                                return

                            key_manager.mark_succeeded(
                                extraction_operation, extraction_fingerprint
                            )
                            job_id = job.get("id")
                            if not job_id:
                                ui.notify("Job-ul de extracție nu are ID.", type="negative")
                                ui.navigate.to(f"/project/{project_id}")
                                return

                            if created_reports:
                                ui.notify(
                                    "Raportul/rapoartele de progres au fost salvate. "
                                    "Analiza lor se pornește după confirmarea obligațiilor.",
                                    type="info",
                                    timeout=9000,
                                )
                            ui.navigate.to(
                                f"/project/{project_id}/criteria-review/{job_id}"
                            )
                            return

                        # Progress reports are accepted one at a time and every accepted
                        # report is analyzed immediately against all confirmed obligations.
                        if created_reports:
                            criteria = await api_client.list_all_project_criteria(project_id)
                            if not criteria:
                                ui.notify(
                                    "Raportul a fost salvat, dar analiza progresului nu poate "
                                    "porni până nu există obligații confirmate.",
                                    type="warning",
                                    timeout=10000,
                                )
                                ui.navigate.to(f"/project/{project_id}")
                                return

                            if len(created_reports) > 1:
                                ui.notify(
                                    "Rapoartele au fost salvate. Pentru a evita mai multe analize "
                                    "Qwen simultane, pornește analiza fiecărui raport din pagina proiectului.",
                                    type="info",
                                    timeout=9000,
                                )
                                ui.navigate.to(f"/project/{project_id}")
                                return

                            report_id = str(created_reports[0].get("id") or "")
                            if not report_id:
                                ui.navigate.to(f"/project/{project_id}")
                                return
                            payload = {
                                "reportId": report_id,
                                "projectDocumentIds": [],
                                "previousReportIds": [],
                            }
                            fingerprint = json_fingerprint(payload)
                            operation = f"analyze-progress:{report_id}"
                            key = key_manager.key_for(operation, fingerprint)
                            job = await api_client.create_report_analysis_job(
                                report_id,
                                idempotency_key=key,
                            )
                            key_manager.mark_succeeded(operation, fingerprint)
                            job_id = str(job.get("id") or "")
                            if not job_id:
                                ui.notify("Job-ul de analiză nu are ID.", type="negative")
                                ui.navigate.to(f"/project/{project_id}")
                                return
                            ui.navigate.to(
                                f"/project/{project_id}/report-analysis/{report_id}/{job_id}"
                            )
                            return

                        ui.notify(
                            f"{uploaded} document(e) au fost încărcate.",
                            type="positive",
                            position="top",
                        )
                        ui.navigate.to(f"/project/{project_id}")
                    except Exception as error:
                        message = api_error_message(error)
                        error_label.text = message
                        error_label.set_visibility(True)
                        ui.notify(message, type="negative", timeout=10000)
                    finally:
                        loading.set_visibility(False)
                        submit_button.enable()
                        back_button.enable()

                submit_button = ui.button(
                    "Trimite documentele",
                    icon="send",
                    on_click=submit_documents,
                ).props("push rounded size=md color=primary").classes(
                    "px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 "
                    "transition-transform duration-200 text-gray-900"
                )
