"""Document-upload page using multipart/form-data through the HTTP API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from nicegui import events, ui

from Interface.api_client import (
    IdempotencyKeyManager,
    api_client,
    api_error_message,
    upload_fingerprint,
)

MAX_FILE_BYTES = 52_428_800
SUPPORTED_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@dataclass(slots=True)
class PendingUpload:
    operation: str = field(default_factory=lambda: f"upload-document:{uuid4()}")
    filename: str | None = None
    content: bytes | None = None
    content_type: str | None = None
    completed: bool = False
    display_name_input: Any = None
    status_label: Any = None


async def _read_upload(event: events.UploadEventArguments) -> tuple[str, bytes, str]:
    filename = Path(event.file.name).name
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_TYPES:
        raise ValueError("Tipul fișierului nu este acceptat de contractul API.")
    content = await event.file.read()
    if not content:
        raise ValueError("Fișierul selectat este gol.")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError("Fișierul depășește limita de 50 MiB.")
    return filename, content, SUPPORTED_TYPES[extension]


@ui.page("/projects/{project_id}/documents")
def upload_documents_page(project_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")
    key_manager = IdempotencyKeyManager()
    rows: list[PendingUpload] = []

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30 p-4"):
        with ui.row().classes("w-full max-w-4xl mb-4"):
            back_button = ui.button(
                "Înapoi la proiect",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/projects/{project_id}"),
            ).props("flat rounded no-caps text-color=grey-8")

        with ui.column().classes(
            "w-full max-w-4xl bg-white shadow-2xl rounded-[2rem] p-6 "
            "gap-4 border border-yellow-100"
        ):
            with ui.row().classes("items-center gap-3"):
                ui.icon("cloud_upload", size="md").classes("text-yellow-600")
                ui.label("Încărcare documente").classes(
                    "text-2xl font-extrabold text-gray-800"
                )
            ui.label(f"Project ID: {project_id}").classes("text-sm text-gray-500")
            ui.separator()

            uploads_container = ui.column().classes("w-full gap-4")

            def add_upload_row() -> None:
                state = PendingUpload()
                rows.append(state)
                with uploads_container:
                    row = ui.column().classes(
                        "w-full bg-gray-50 p-4 rounded-xl border border-gray-200 gap-3"
                    )
                    with row:
                        state.display_name_input = ui.input("Nume afișat (opțional)").props(
                            "outlined maxlength=255"
                        ).classes("w-full")
                        state.status_label = ui.label("Selectează un fișier.").classes(
                            "text-sm text-gray-600"
                        )

                        async def on_file_uploaded(event: events.UploadEventArguments) -> None:
                            try:
                                filename, content, content_type = await _read_upload(event)
                            except ValueError as error:
                                state.filename = None
                                state.content = None
                                state.content_type = None
                                state.status_label.text = str(error)
                                state.status_label.classes(replace="text-sm text-red-700")
                                ui.notify(str(error), type="negative", position="top")
                                return
                            state.filename = filename
                            state.content = content
                            state.content_type = content_type
                            state.completed = False
                            state.status_label.text = f"Pregătit: {filename}"
                            state.status_label.classes(
                                replace="text-sm font-bold text-green-700"
                            )

                        ui.upload(
                            multiple=False,
                            auto_upload=True,
                            on_upload=on_file_uploaded,
                            max_file_size=MAX_FILE_BYTES,
                            on_rejected=lambda: ui.notify(
                                "Fișier respins: verifică tipul și limita de 50 MiB.",
                                type="negative",
                                position="top",
                            ),
                        ).props(
                            'accept=".pdf,.doc,.docx,.xls,.xlsx" max-files=1 '
                            'label="Selectează documentul" flat bordered hide-upload-btn'
                        ).classes("w-full bg-white")

                        def delete_row() -> None:
                            rows.remove(state)
                            row.delete()

                        ui.button("Elimină", icon="delete", on_click=delete_row).props(
                            "flat color=negative"
                        )

            add_upload_row()
            ui.button(
                "Adaugă alt document",
                icon="add",
                on_click=add_upload_row,
            ).props("flat rounded no-caps").classes(
                "text-yellow-700 font-bold bg-yellow-50 px-6 py-2"
            )

            loading = ui.row().classes("items-center gap-2 text-gray-600")
            with loading:
                ui.spinner(size="sm")
                ui.label("Se încarcă documentele...")
            loading.set_visibility(False)

            async def submit_documents() -> None:
                pending = [
                    row
                    for row in rows
                    if not row.completed and row.filename and row.content and row.content_type
                ]
                if not pending:
                    ui.notify(
                        "Nu există documente noi pregătite pentru upload.",
                        type="warning",
                        position="top",
                    )
                    return
                submit_button.disable()
                back_button.disable()
                loading.set_visibility(True)
                uploaded = 0
                try:
                    for state in pending:
                        assert state.filename is not None
                        assert state.content is not None
                        assert state.content_type is not None
                        display_name = (
                            str(state.display_name_input.value or "").strip() or None
                        )
                        fingerprint = upload_fingerprint(
                            project_id=project_id,
                            filename=state.filename,
                            content_type=state.content_type,
                            content=state.content,
                            display_name=display_name,
                        )
                        key = key_manager.key_for(state.operation, fingerprint)
                        try:
                            await api_client.upload_document(
                                project_id,
                                filename=state.filename,
                                content=state.content,
                                content_type=state.content_type,
                                display_name=display_name,
                                idempotency_key=key,
                            )
                        except Exception as error:
                            state.status_label.text = api_error_message(error)
                            state.status_label.classes(replace="text-sm text-red-700")
                            ui.notify(
                                api_error_message(error),
                                type="negative",
                                position="top",
                                timeout=8000,
                            )
                            break
                        state.completed = True
                        key_manager.mark_succeeded(state.operation, fingerprint)
                        state.display_name_input.disable()
                        state.status_label.text = f"Încărcat: {state.filename}"
                        state.status_label.classes(
                            replace="text-sm font-bold text-green-700"
                        )
                        uploaded += 1
                finally:
                    loading.set_visibility(False)
                    submit_button.enable()
                    back_button.enable()
                if uploaded:
                    ui.notify(
                        f"{uploaded} document(e) încărcat(e).",
                        type="positive",
                        position="top",
                    )

            submit_button = ui.button(
                "Încarcă documentele",
                icon="send",
                on_click=submit_documents,
            ).props("push rounded color=primary").classes(
                "self-end px-6 py-2 font-extrabold text-gray-900"
            )
