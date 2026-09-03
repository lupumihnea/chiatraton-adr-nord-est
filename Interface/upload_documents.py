"""Document upload using Andrei's supplied dynamic-row design."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from uuid import uuid4

from nicegui import app, events, ui

from Interface.api_client import (
    APIProblemError,
    APITimeoutError,
    APIUnavailableError,
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


@ui.page("/upload/{project_id}")
async def upload_documents_page(project_id: str) -> None:
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
                header_label = ui.label(f"Încărcare documente - Proiect {project_id}").classes(
                    "text-2xl font-extrabold text-gray-800 break-all"
                )

            ui.separator().classes("opacity-50")
            uploads_container = ui.column().classes("w-full space-y-4")

            def add_upload_row() -> None:
                row_data: dict[str, Any] = {
                    "operation": f"upload-document:{uuid4()}",
                    "category": "altele",
                    "filename": None,
                    "content": None,
                    "status_label": None,
                    "completed": False,
                }
                upload_state.append(row_data)

                with uploads_container:
                    row = ui.row().classes(
                        "w-full items-center bg-gray-50 p-4 rounded-xl border "
                        "border-gray-200 shadow-sm transition-all gap-4 flex-nowrap"
                    )
                    with row:
                        category_select = ui.select(
                            CATEGORY_OPTIONS,
                            value="altele",
                            on_change=lambda event: row_data.update(
                                {"category": event.value}
                            ),
                        ).props(
                            "outlined rounded bg-white hide-bottom-space"
                        ).classes("w-1/3 min-w-[200px]")

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
                                upload_component.set_visibility(False)
                                category_select.disable()

                                with middle_container:
                                    with ui.row().classes(
                                        "w-full bg-green-50 border border-green-200 p-3 "
                                        "rounded-xl items-center justify-between shadow-inner"
                                    ):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.icon(
                                                "picture_as_pdf",
                                                size="sm",
                                            ).classes("text-red-500")
                                            ui.label(filename).classes(
                                                "text-base font-extrabold text-green-900"
                                            )

                                        with ui.row().classes("items-center gap-1"):
                                            ui.icon(
                                                "check_circle",
                                                size="sm",
                                            ).classes("text-green-600")
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
                            row.delete()

                        ui.button(icon="delete", on_click=delete_row).props(
                            "flat round color=negative size=md"
                        ).classes(
                            "bg-red-50 hover:bg-red-100 transition-colors"
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
                ui.label("Se trimit documentele...")
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

                    submit_button.disable()
                    back_button.disable()
                    loading.set_visibility(True)
                    error_label.set_visibility(False)
                    uploaded = 0
                    uploaded_document_ids: list[str] = []
                    try:
                        for row_data in pending:
                            filename = str(row_data["filename"])
                            content = bytes(row_data["content"])
                            display_name = CATEGORY_OPTIONS[str(row_data["category"])]
                            fingerprint = upload_fingerprint(
                                project_id=project_id,
                                filename=filename,
                                content_type="application/pdf",
                                content=content,
                                display_name=display_name,
                            )
                            idempotency_key = key_manager.key_for(
                                str(row_data["operation"]),
                                fingerprint,
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
                            except APIProblemError as error:
                                if error.problem.code == "document_duplicate":
                                    # Same file (identical content) already exists in
                                    # this project. Not a fatal error: skip it and keep
                                    # going with the rest of the batch, since re-running
                                    # extraction on an unchanged document is a common,
                                    # intentional thing to try (e.g. re-testing).
                                    row_data["completed"] = True
                                    status_label = row_data["status_label"]
                                    if status_label is not None:
                                        status_label.text = "Deja încărcat"
                                        status_label.classes(
                                            replace=(
                                                "text-xs font-bold text-yellow-700 "
                                                "uppercase tracking-wide"
                                            )
                                        )
                                    ui.notify(
                                        f"„{filename}” este deja încărcat în acest "
                                        "proiect; se sare peste el.",
                                        type="info",
                                        position="top",
                                    )
                                    continue
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
                                break
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
                                break

                            row_data["completed"] = True
                            document_id = uploaded_document.get("id")
                            if document_id:
                                row_data["document_id"] = str(document_id)
                                uploaded_document_ids.append(str(document_id))
                            key_manager.mark_succeeded(
                                str(row_data["operation"]),
                                fingerprint,
                            )
                            status_label = row_data["status_label"]
                            if status_label is not None:
                                status_label.text = "Încărcat"
                            uploaded += 1
                    finally:
                        loading.set_visibility(False)
                        submit_button.enable()
                        back_button.enable()

                    all_rows_settled = all(row["completed"] for row in pending)
                    if all_rows_settled:
                        if not uploaded_document_ids:
                            ui.notify(
                                "Toate documentele selectate erau deja încărcate în acest "
                                "proiect — nu e nimic nou de extras. Încarcă un document "
                                "diferit, sau vezi criteriile deja existente pe pagina "
                                "proiectului.",
                                type="warning",
                                position="top",
                                timeout=10000,
                            )
                            return
                        ui.notify(
                            f"{uploaded} document(e) nou(i) au fost încărcate. "
                            "Pornim extragerea obligațiilor...",
                            type="positive",
                            position="top",
                        )

                        extraction_payload = {
                            "projectId": project_id,
                            "documentIds": sorted(uploaded_document_ids),
                        }
                        extraction_fingerprint = json_fingerprint(extraction_payload)
                        extraction_operation = f"extract-criteria:{project_id}"
                        extraction_key = key_manager.key_for(
                            extraction_operation, extraction_fingerprint
                        )
                        job = None
                        last_error: Exception | None = None
                        # A lost/late response is ambiguous: the server may
                        # already have accepted the job. Retry with the SAME
                        # idempotency key instead of creating duplicates.
                        for attempt in range(3):
                            try:
                                job = await api_client.create_criterion_extraction_job(
                                    project_id,
                                    document_ids=uploaded_document_ids,
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
                                "Documentele sunt încărcate. Nu am primit confirmarea "
                                "job-ului de extracție după 3 încercări. "
                                + (api_error_message(last_error) if last_error else ""),
                                type="negative",
                                timeout=15000,
                            )
                            # Stay on the upload page: navigating immediately to
                            # /project while the backend is CPU-busy used to
                            # trigger NiceGUI's 3-second page-build timeout.
                            return

                        key_manager.mark_succeeded(
                            extraction_operation, extraction_fingerprint
                        )
                        job_id = job.get("id")
                        if not job_id:
                            ui.notify(
                                "Job-ul de extracție nu are ID.",
                                type="negative",
                            )
                            ui.navigate.to(f"/project/{project_id}")
                            return
                        pending_jobs = getattr(app, "pending_extraction_jobs", {})
                        pending_jobs[project_id] = job_id
                        app.pending_extraction_jobs = pending_jobs
                        ui.navigate.to(
                            f"/project/{project_id}/criteria-review/{job_id}"
                        )

                submit_button = ui.button(
                    "Trimite documentele",
                    icon="send",
                    on_click=submit_documents,
                ).props("push rounded size=md color=primary").classes(
                    "px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 "
                    "transition-transform duration-200 text-gray-900"
                )

        async def _show_smis_code() -> None:
            try:
                project = await api_client.get_project(project_id)
            except Exception:
                return
            if project and project.get("smisCode"):
                header_label.text = f"Încărcare documente - Proiect {project['smisCode']}"

        await ui.context.client.connected(timeout=10.0)
        await _show_smis_code()
