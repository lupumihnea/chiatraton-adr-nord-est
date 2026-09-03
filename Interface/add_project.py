"""Project creation using Andrei's supplied card design and the HTTP API."""

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
            "space-y-3 border border-yellow-100"
        ):
            with ui.column().classes("w-full space-y-1"):
                ui.label("Cod SMIS (6 cifre)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2"
                )
                smis_code = ui.input(
                    validation={
                        "Trebuie exact 6 cifre": lambda value: (
                            len(str(value or "")) == 6
                            and str(value or "").isdigit()
                        )
                    }
                ).props(
                    'rounded outlined clearable hide-bottom-space mask="######" '
                    'input-class="text-lg font-bold tracking-widest"'
                ).classes("w-full text-lg bg-gray-50 rounded-xl")

            with ui.column().classes("w-full space-y-1"):
                ui.label("Identificator al apelului (obligatoriu)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2"
                )
                funding_call_id = ui.input(
                    validation={
                        "Trebuie să fie un număr întreg pozitiv": lambda value: (
                            str(value or "").isdigit() and int(str(value)) > 0
                        )
                    }
                ).props(
                    "rounded outlined clearable hide-bottom-space "
                    'input-class="text-base font-bold"'
                ).classes("w-full text-base bg-gray-50 rounded-xl")

            with ui.column().classes("w-full space-y-1"):
                ui.label("Nume proiect (obligatoriu)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2"
                )
                project_name = ui.input(
                    validation={
                        "Numele este obligatoriu": lambda value: bool(
                            str(value or "").strip()
                        )
                    }
                ).props(
                    "rounded outlined clearable hide-bottom-space maxlength=200 "
                    'input-class="text-lg font-bold"'
                ).classes("w-full text-lg bg-gray-50 rounded-xl")

            with ui.column().classes("w-full space-y-1"):
                ui.label("Nume beneficiar (opțional)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2"
                )
                beneficiary_name = ui.input().props(
                    "rounded outlined clearable hide-bottom-space maxlength=200 "
                    'input-class="text-base font-bold"'
                ).classes("w-full text-base bg-gray-50 rounded-xl")

            with ui.column().classes("w-full space-y-1"):
                ui.label("Data finalizării (obligatoriu)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2"
                )
                completion_date = ui.input().props(
                    "rounded outlined hide-bottom-space type=date "
                    'input-class="text-base font-bold"'
                ).classes("w-full text-base bg-gray-50 rounded-xl")

            with ui.column().classes("w-full space-y-1"):
                ui.label("Sfârșitul monitorizării (obligatoriu)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2"
                )
                monitoring_end_date = ui.input().props(
                    "rounded outlined hide-bottom-space type=date "
                    'input-class="text-base font-bold"'
                ).classes("w-full text-base bg-gray-50 rounded-xl")

            ui.separator().classes("my-2 opacity-50")

            error_label = ui.label().classes(
                "w-full text-sm font-bold text-red-700 bg-red-50 p-3 rounded-xl"
            )
            error_label.set_visibility(False)

            loading = ui.row().classes("items-center gap-2 text-gray-600")
            with loading:
                ui.spinner(size="sm")
                ui.label("Se salvează proiectul...")
            loading.set_visibility(False)

            with ui.row().classes("w-full items-center justify-between mt-2 pt-0"):
                back_button = ui.button(
                    "Înapoi la start",
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/"),
                ).props("flat rounded no-caps text-color=grey-7 size=md").classes(
                    "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
                )

                async def save_project() -> None:
                    smis = str(smis_code.value or "").strip()
                    funding_call = str(funding_call_id.value or "").strip()
                    name = str(project_name.value or "").strip()
                    beneficiary = str(beneficiary_name.value or "").strip()
                    completed = str(completion_date.value or "").strip()
                    monitored_until = str(monitoring_end_date.value or "").strip()
                    error_label.set_visibility(False)

                    if len(smis) != 6 or not smis.isdigit():
                        ui.notify(
                            "Completează un cod SMIS valid de șase cifre.",
                            type="negative",
                            position="top",
                            classes="font-bold",
                        )
                        return
                    if not funding_call.isdigit() or int(funding_call) < 1:
                        ui.notify(
                            "Completează un identificator de apel pozitiv.",
                            type="negative",
                            position="top",
                            classes="font-bold",
                        )
                        return
                    if not name or not completed or not monitored_until:
                        ui.notify(
                            "Completează numele și ambele date.",
                            type="negative",
                            position="top",
                            classes="font-bold",
                        )
                        return
                    if monitored_until < completed:
                        ui.notify(
                            "Sfârșitul monitorizării nu poate preceda data finalizării.",
                            type="negative",
                            position="top",
                            classes="font-bold",
                        )
                        return

                    payload = {
                        "name": name,
                        "smisCode": smis,
                        "fundingCallId": int(funding_call),
                        "beneficiaryName": beneficiary or None,
                        "completionDate": completed,
                        "monitoringEndDate": monitored_until,
                    }
                    fingerprint = json_fingerprint(payload)
                    idempotency_key = key_manager.key_for(operation, fingerprint)
                    save_button.disable()
                    back_button.disable()
                    loading.set_visibility(True)
                    try:
                        project = await api_client.create_project(
                            payload,
                            idempotency_key=idempotency_key,
                        )
                    except Exception as error:
                        message = api_error_message(error)
                        error_label.text = message
                        error_label.set_visibility(True)
                        ui.notify(
                            message,
                            type="negative",
                            position="top",
                            timeout=8000,
                        )
                    else:
                        key_manager.mark_succeeded(operation, fingerprint)
                        ui.navigate.to(f'/success/{project["id"]}/{smis}')
                    finally:
                        loading.set_visibility(False)
                        save_button.enable()
                        back_button.enable()

                save_button = ui.button(
                    "Salvează Proiectul",
                    icon="check_circle",
                    on_click=save_project,
                ).props("push rounded size=md color=primary").classes(
                    "px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 "
                    "transition-transform duration-200 text-gray-900"
                )


@ui.page("/success/{project_id}/{smis_code}")
def success_page(project_id: str, smis_code: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes(
        "w-full items-center justify-center min-h-[85vh] p-4"
    ):
        with ui.column().classes(
            "items-center bg-white shadow-2xl rounded-[2rem] p-8 border "
            "border-yellow-100 transform transition-transform hover:scale-105 "
            "duration-300 text-center max-w-lg"
        ):
            ui.icon("check_circle", size="120px").classes(
                "text-green-500 mb-6 drop-shadow-md"
            )
            ui.label("Gata!").classes("text-5xl font-extrabold text-gray-800 mb-4")

            with ui.row().classes("items-center justify-center gap-1 flex-wrap"):
                ui.label("Proiectul cu codul SMIS").classes(
                    "text-lg text-gray-600 font-medium"
                )
                ui.label(smis_code).classes(
                    "text-xl font-extrabold text-yellow-600 bg-yellow-50 px-3 py-1 "
                    "rounded-xl shadow-inner border border-yellow-200 mx-1"
                )
                ui.label("a fost adăugat cu succes.").classes(
                    "text-lg text-gray-600 font-medium"
                )

            ui.timer(2.5, lambda: ui.navigate.to("/"), once=True)
