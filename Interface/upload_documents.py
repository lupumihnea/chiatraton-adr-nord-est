"""Document upload in Andrei's current NiceGUI design."""

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
CATEGORY_OPTIONS = {
    "apel": "Documente legate de apel",
    "initiale": "Documente inițiale",
    "rapoarte": "Rapoarte de progres",
    "altele": "Alte documente",
}


@dataclass(slots=True)
class PendingUpload:
    operation: str = field(default_factory=lambda: f"upload-document:{uuid4()}")
    category: str = "altele"
    filename: str | None = None
    content: bytes | None = None
    content_type: str | None = None
    completed: bool = False
    category_select: Any = None
    upload_component: Any = None
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
    """Upload documents through the contract-defined multipart endpoint."""

    ui.colors(primary="#ffcc00", accent="#ffcc00")
    key_manager = IdempotencyKeyManager()
    rows: list[PendingUpload] = []

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30 p-4"):
        with ui.row().classes("w-full max-w-4xl mb-4"):
            back_button = ui.button(
                "Înapoi la proiect",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/projects/{project_id}"),
            ).props("flat rounded no-caps size=md text-color=grey-8").classes(
                "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
            )

        with ui.column().classes(
            "w-full max-w-4xl bg-white shadow-2xl rounded-[2rem] p-6 gap-4 "
            "border border-yellow-100"
        ):
            with ui.row().classes("items-center gap-3 mb-2"):
                ui.icon("cloud_upload", size="md").classes("text-yellow-600")
                ui.label("Încărcare documente").classes(
                    "text-2xl font-extrabold text-gray-800"
                )
            ui.label(f"Project ID: {project_id}").classes(
                "text-xs font-bold text-gray-500 break-all"
            )
            ui.separator().classes("opacity-50")

            uploads_container = ui.column().classes("w-full gap-4")

            def add_upload_row() -> None:
                state = PendingUpload()
                rows.append(state)

                with uploads_container:
                    row = ui.row().classes(
                        "w-full items-center bg-gray-50 p-4 rounded-xl border "
                        "border-gray-200 shadow-sm transition-all gap-4 flex-nowrap"
                    )
                    with row:
                        def update_category(event: events.ValueChangeEventArguments) -> None:
                            state.category = str(event.value)

                        state.category_select = ui.select(
                            CATEGORY_OPTIONS,
                            value=state.category,
                            on_change=update_category,
                        ).props(
                            "outlined rounded bg-white hide-bottom-space"
                        ).classes("w-1/3 min-w-[200px]")

                        middle_container = ui.row().classes("flex-grow items-center")
                        with middle_container:
                            async def on_file_uploaded(
                                event: events.UploadEventArguments,
                            ) -> None:
                                try:
                                    filename, content, content_type = await _read_upload(event)
                                except ValueError as error:
                                    state.filename = None
                                    state.content = None
                                    state.content_type = None
                                    ui.notify(str(error), type="negative", position="top")
                                    return

                                state.filename = filename
                                state.content = content
                                state.content_type = content_type
                                state.completed = False
                                state.upload_component.set_visibility(False)
                                state.category_select.disable()

                                with middle_container:
                                    with ui.row().classes(
                                        "w-full bg-green-50 border border-green-200 p-3 "
                                        "rounded-xl items-center justify-between shadow-inner"
                                    ):
                                        with ui.row().classes("items-center gap-2"):
                                            ui.icon("description", size="sm").classes(
                                                "text-yellow-700"
                                            )
                                            ui.label(filename).classes(
                                                "text-base font-extrabold text-green-900"
                                            )
                                        with ui.row().classes("items-center gap-1"):
                                            ui.icon("check_circle", size="sm").classes(
                                                "text-green-600"
                                            )
                                            state.status_label = ui.label("Pregătit").classes(
                                                "text-xs font-bold text-green-700 "
                                                "uppercase tracking-wide"
                                            )
                                ui.notify(
                                    "Fișier atașat local.",
                                    type="info",
                                    position="top",
                                )

                            state.upload_component = ui.upload(
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
                                'label="Trage documentul aici" flat bordered color=white '
                                'text-color=grey-9 hide-upload-btn'
                            ).classes("w-full shadow-sm bg-white")

                        def delete_row() -> None:
                            rows.remove(state)
                            row.delete()

                        ui.button(icon="delete", on_click=delete_row).props(
                            "flat round color=negative size=md"
                        ).classes("bg-red-50 hover:bg-red-100 transition-colors")

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
                ui.label("Se încarcă documentele...")
            loading.set_visibility(False)

            with ui.row().classes("w-full justify-end mt-2 pt-2"):
                async def submit_documents() -> None:
                    pending = [
                        state
                        for state in rows
                        if not state.completed
                        and state.filename is not None
                        and state.content is not None
                        and state.content_type is not None
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
                    error_label.set_visibility(False)
                    uploaded = 0
                    try:
                        for state in pending:
                            assert state.filename is not None
                            assert state.content is not None
                            assert state.content_type is not None
                            display_name = CATEGORY_OPTIONS[state.category]
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
                                message = api_error_message(error)
                                error_label.text = message
                                error_label.set_visibility(True)
                                if state.status_label is not None:
                                    state.status_label.text = "Eroare"
                                    state.status_label.classes(
                                        replace="text-xs font-bold text-red-700 uppercase"
                                    )
                                ui.notify(
                                    message,
                                    type="negative",
                                    position="top",
                                    timeout=8000,
                                )
                                break

                            state.completed = True
                            key_manager.mark_succeeded(state.operation, fingerprint)
                            if state.status_label is not None:
                                state.status_label.text = "Încărcat"
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
                ).props("push rounded size=md color=primary").classes(
                    "px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 "
                    "transition-transform duration-200 text-gray-900"
                )
