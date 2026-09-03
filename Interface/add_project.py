"""Project-creation page backed exclusively by the HTTP API."""

from uuid import uuid4

from nicegui import ui

from Interface.api_client import (
    IdempotencyKeyManager,
    api_client,
    api_error_message,
    json_fingerprint,
)


@ui.page("/add_project")
def add_project_page() -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")
    key_manager = IdempotencyKeyManager()
    operation = f"create-project:{uuid4()}"

    with ui.column().classes("w-full items-center mt-6 mb-6 min-h-[85vh]"):
        with ui.row().classes("items-center mb-4 gap-3"):
            ui.icon("post_add", size="md").classes("text-yellow-600")
            ui.label("Adaugă un nou proiect").classes(
                "text-2xl font-extrabold text-gray-800"
            )

        with ui.column().classes(
            "w-full max-w-3xl bg-white shadow-2xl rounded-[2rem] p-6 "
            "gap-4 border border-yellow-100"
        ):
            project_name = ui.input("Nume proiect").props(
                "rounded outlined clearable maxlength=200"
            ).classes("w-full")
            completion_date = ui.input("Data finalizării").props("outlined type=date").classes(
                "w-full"
            )
            monitoring_end_date = ui.input("Sfârșitul monitorizării").props(
                "outlined type=date"
            ).classes("w-full")

            ui.label(
                "Contractul API acceptă exclusiv numele și cele două date; "
                "codul SMIS și datele beneficiarului nu sunt trimise."
            ).classes("text-sm text-gray-500")

            loading = ui.row().classes("items-center gap-2 text-gray-600")
            with loading:
                ui.spinner(size="sm")
                ui.label("Se salvează proiectul...")
            loading.set_visibility(False)

            with ui.row().classes("w-full items-center justify-between mt-2"):
                back_button = ui.button(
                    "Înapoi la start",
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/"),
                ).props("flat rounded no-caps")

                async def save_project() -> None:
                    name = str(project_name.value or "").strip()
                    completed = str(completion_date.value or "").strip()
                    monitored_until = str(monitoring_end_date.value or "").strip()
                    if not name or not completed or not monitored_until:
                        ui.notify(
                            "Completează numele și ambele date.",
                            type="warning",
                            position="top",
                        )
                        return
                    if monitored_until < completed:
                        ui.notify(
                            "Sfârșitul monitorizării nu poate preceda data finalizării.",
                            type="warning",
                            position="top",
                        )
                        return

                    payload = {
                        "name": name,
                        "completionDate": completed,
                        "monitoringEndDate": monitored_until,
                    }
                    fingerprint = json_fingerprint(payload)
                    key = key_manager.key_for(operation, fingerprint)
                    save_button.disable()
                    back_button.disable()
                    loading.set_visibility(True)
                    try:
                        project = await api_client.create_project(payload, idempotency_key=key)
                    except Exception as error:
                        ui.notify(
                            api_error_message(error),
                            type="negative",
                            position="top",
                            timeout=8000,
                        )
                    else:
                        key_manager.mark_succeeded(operation, fingerprint)
                        ui.notify("Proiectul a fost creat.", type="positive", position="top")
                        ui.navigate.to(f'/projects/{project["id"]}')
                    finally:
                        loading.set_visibility(False)
                        save_button.enable()
                        back_button.enable()

                save_button = ui.button(
                    "Salvează proiectul",
                    icon="check_circle",
                    on_click=save_project,
                ).props("push rounded color=primary").classes(
                    "px-6 py-2 font-extrabold text-gray-900"
                )
