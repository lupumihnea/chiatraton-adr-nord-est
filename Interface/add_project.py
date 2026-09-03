from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import ui

from API.monitoring_api import MonitoringAPI


api = MonitoringAPI()


@ui.page("/add_project")
def add_project_page():
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes(
        "w-full items-center mt-6 mb-6 min-h-[85vh]"
    ):
        with ui.row().classes("items-center mb-4 gap-3"):
            ui.icon("post_add", size="md").classes("text-yellow-600")
            ui.label("Adaugă un nou proiect").classes(
                "text-2xl font-extrabold text-gray-800"
            )

        with ui.column().classes(
            "w-full max-w-3xl bg-white shadow-2xl rounded-[2rem] "
            "p-6 space-y-3 border border-yellow-100"
        ):
            with ui.column().classes("w-full space-y-1"):
                ui.label("Cod SMIS (6 cifre)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase "
                    "tracking-wide ml-2"
                )
                project_code = ui.input(
                    validation={
                        "Trebuie exact 6 cifre":
                            lambda v: len(str(v or "")) == 6
                            and str(v).isdigit()
                    }
                ).props(
                    'rounded outlined clearable hide-bottom-space mask="######" '
                    'input-class="text-lg font-bold tracking-widest"'
                ).classes(
                    "w-full text-lg bg-gray-50 rounded-xl"
                )

            with ui.column().classes("w-full space-y-1"):
                ui.label(
                    "Identificator al apelului (obligatoriu)"
                ).classes(
                    "text-xs font-extrabold text-gray-500 uppercase "
                    "tracking-wide ml-2"
                )
                call_identifier = ui.input(
                    validation={
                        "Trebuie să fie un număr întreg":
                            lambda v: str(v or "").strip().isdigit()
                    }
                ).props(
                    'rounded outlined clearable hide-bottom-space '
                    'input-class="text-base font-bold"'
                ).classes(
                    "w-full text-base bg-gray-50 rounded-xl"
                )

            with ui.column().classes("w-full space-y-1"):
                ui.label("Nume proiect (opțional)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase "
                    "tracking-wide ml-2"
                )
                project_name = ui.input().props(
                    'rounded outlined clearable hide-bottom-space '
                    'input-class="text-base font-bold"'
                ).classes(
                    "w-full text-base bg-gray-50 rounded-xl"
                )

            with ui.column().classes("w-full space-y-1"):
                ui.label("Data finalizării (opțional)").classes(
                    "text-xs font-extrabold text-gray-500 uppercase "
                    "tracking-wide ml-2"
                )
                time_ending = ui.input(
                    placeholder="2025-07-23"
                ).props(
                    'rounded outlined clearable hide-bottom-space '
                    'input-class="text-base font-bold"'
                ).classes(
                    "w-full text-base bg-gray-50 rounded-xl"
                )

            # This field existed in the newer UI.  The current project table does
            # not have a beneficiary_name column, so we keep the field visible
            # without pretending it is persisted.
            with ui.column().classes("w-full space-y-1"):
                ui.label(
                    "Nume beneficiar (opțional, informativ)"
                ).classes(
                    "text-xs font-extrabold text-gray-500 uppercase "
                    "tracking-wide ml-2"
                )
                beneficiary_name = ui.input().props(
                    'rounded outlined clearable hide-bottom-space '
                    'input-class="text-base font-bold"'
                ).classes(
                    "w-full text-base bg-gray-50 rounded-xl"
                )
                ui.label(
                    "Schema actuală nu persistă încă numele beneficiarului."
                ).classes("text-xs text-gray-400 ml-2")

            ui.separator().classes("my-2 opacity-50")

            with ui.row().classes(
                "w-full items-center justify-between mt-2 pt-0"
            ):
                ui.button(
                    "Înapoi la start",
                    icon="arrow_back",
                    on_click=lambda: ui.navigate.to("/"),
                ).props(
                    'flat rounded no-caps text-gray-500 size="md"'
                ).classes(
                    "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
                )

                def save_project():
                    code = str(project_code.value or "").strip()
                    if len(code) != 6 or not code.isdigit():
                        ui.notify(
                            "Te rugăm să completezi un cod SMIS valid "
                            "de 6 cifre înainte de a salva.",
                            type="negative",
                            position="top",
                            classes="font-bold",
                        )
                        return

                    identifier_text = str(
                        call_identifier.value or ""
                    ).strip()
                    if not identifier_text.isdigit():
                        ui.notify(
                            "Te rugăm să introduci un identificator de apel "
                            "valid (număr întreg).",
                            type="negative",
                            position="top",
                            classes="font-bold",
                        )
                        return

                    try:
                        project_id = int(code)
                        identifier = int(identifier_text)
                        p_name = (
                            str(project_name.value).strip()
                            if project_name.value
                            else None
                        )
                        end_date = (
                            str(time_ending.value).strip()
                            if time_ending.value
                            else None
                        )

                        # Actual backend integration from the AI branch.
                        api.upsert_project(
                            project_id=project_id,
                            call_id=identifier,
                            time_ending=end_date,
                            name=p_name,
                        )

                        # beneficiary_name is intentionally not passed: the
                        # current DB/API schema has no corresponding field.
                        _ = beneficiary_name.value

                        ui.navigate.to(f"/success/{project_id}")
                    except Exception as exc:
                        ui.notify(
                            f"Eroare la salvare: {exc}",
                            type="negative",
                            position="top",
                        )
                        ui.navigate.to(f"/error/{code}")

                ui.button(
                    "Salvează Proiectul",
                    icon="check_circle",
                    on_click=save_project,
                ).props(
                    'push rounded size="md" color="primary"'
                ).classes(
                    "px-6 py-2 text-base font-extrabold shadow-xl "
                    "hover:scale-105 transition-transform duration-200 "
                    "text-gray-900"
                )


@ui.page("/success/{code}")
def success_page(code: str):
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes(
        "w-full items-center justify-center min-h-[85vh] p-4"
    ):
        with ui.column().classes(
            "items-center bg-white shadow-2xl rounded-[2rem] p-8 "
            "border border-yellow-100 transform transition-transform "
            "hover:scale-105 duration-300 text-center max-w-lg"
        ):
            ui.icon(
                "check_circle",
                size="120px",
            ).classes("text-green-500 mb-6 drop-shadow-md")

            ui.label("Gata!").classes(
                "text-5xl font-extrabold text-gray-800 mb-4"
            )

            with ui.row().classes(
                "items-center justify-center gap-1 flex-wrap"
            ):
                ui.label("Proiectul cu codul SMIS").classes(
                    "text-lg text-gray-600 font-medium"
                )
                ui.label(code).classes(
                    "text-xl font-extrabold text-yellow-600 "
                    "bg-yellow-50 px-3 py-1 rounded-xl shadow-inner "
                    "border border-yellow-200 mx-1"
                )
                ui.label("a fost adăugat cu succes.").classes(
                    "text-lg text-gray-600 font-medium"
                )

            with ui.row().classes("gap-2 mt-5"):
                ui.button(
                    "Detalii proiect",
                    on_click=lambda: ui.navigate.to(f"/project/{code}"),
                ).props("outline no-caps")
                ui.button(
                    "Monitorizare AI",
                    icon="smart_toy",
                    on_click=lambda: ui.navigate.to(
                        f"/monitoring/project/{code}"
                    ),
                ).props("no-caps")

            ui.timer(5.0, lambda: ui.navigate.to("/"), once=True)


@ui.page("/error/{code}")
def error_page(code: str):
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes(
        "w-full items-center justify-center min-h-[85vh] p-4"
    ):
        with ui.column().classes(
            "items-center bg-white shadow-2xl rounded-[2rem] p-8 "
            "border border-red-100 transform transition-transform "
            "hover:scale-105 duration-300 text-center max-w-lg"
        ):
            ui.icon(
                "error",
                size="120px",
            ).classes("text-red-500 mb-6 drop-shadow-md")

            ui.label("Eroare!").classes(
                "text-5xl font-extrabold text-gray-800 mb-4"
            )

            with ui.row().classes(
                "items-center justify-center gap-1 flex-wrap"
            ):
                ui.label(
                    "A apărut o problemă la adăugarea proiectului"
                ).classes("text-lg text-gray-600 font-medium")
                ui.label(code).classes(
                    "text-xl font-extrabold text-red-600 bg-red-50 "
                    "px-3 py-1 rounded-xl shadow-inner border "
                    "border-red-200 mx-1"
                )

            ui.timer(
                5.0,
                lambda: ui.navigate.to("/add_project"),
                once=True,
            )
