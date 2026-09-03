"""NiceGUI entry point and project-selection page."""

import os
from pathlib import Path

from nicegui import app, ui

from Interface import add_project, project_details, upload_documents
from Interface.api_client import api_client, api_error_message

_REGISTERED_PAGE_MODULES = (add_project, project_details, upload_documents)
ASSETS_DIR = Path(__file__).with_name("Assets")

ui.add_head_html(
    """
    <style>
        body { font-family: Inter, ui-sans-serif, system-ui, sans-serif; background: #fffdf5; }
    </style>
    """,
    shared=True,
)
app.add_static_files("/Assets", str(ASSETS_DIR))
app.on_shutdown(api_client.close)


@ui.page("/")
async def home() -> None:
    """List projects through the HTTP API and navigate using their UUID."""

    ui.colors(primary="#ffcc00", accent="#ffcc00")
    with ui.column().classes("w-full items-center mt-8 gap-6 min-h-[85vh]"):
        ui.image("/Assets/Logo-ADR.png").classes(
            "w-64 transition-transform hover:scale-105 duration-300 drop-shadow-sm"
        )

        with ui.row().classes(
            "items-center bg-white px-4 py-2 rounded-full shadow-md "
            "border-2 border-yellow-200"
        ):
            ui.image("/Assets/ADRut.png").classes("w-12 h-12 rounded-full bg-yellow-50 p-1")
            ui.label("Haide să începem verificarea!").classes(
                "text-lg font-extrabold text-gray-700 mx-3"
            )

        with ui.column().classes("w-full max-w-2xl items-stretch gap-4"):
            ui.label("Selectează proiectul după nume și UUID").classes(
                "text-sm font-bold text-gray-600"
            )
            project_select = ui.select(
                options={},
                label="Proiect",
                with_input=True,
            ).props("outlined rounded clearable")
            project_select.disable()

            loading = ui.row().classes("items-center gap-2 text-gray-600")
            with loading:
                ui.spinner(size="md")
                ui.label("Se încarcă proiectele...")
            empty_label = ui.label("Nu există încă proiecte.").classes(
                "text-gray-500 italic"
            )
            empty_label.set_visibility(False)

            with ui.row().classes("w-full justify-between items-center gap-3"):
                ui.button(
                    "Adaugă un nou proiect",
                    icon="add",
                    on_click=lambda: ui.navigate.to("/add_project"),
                ).props("flat rounded no-caps").classes(
                    "text-yellow-700 font-bold bg-yellow-50 px-4 py-2"
                )

                def access_project() -> None:
                    if not project_select.value:
                        ui.notify("Selectează un proiect.", type="warning", position="top")
                        return
                    ui.navigate.to(f"/projects/{project_select.value}")

                access_button = ui.button(
                    "Accesează",
                    icon="arrow_forward",
                    on_click=access_project,
                ).props("push rounded color=primary").classes(
                    "px-8 py-2 font-extrabold text-gray-900"
                )
                access_button.disable()

        try:
            projects = await api_client.list_all_projects()
        except Exception as error:  # the client converts transport/API errors to safe messages
            ui.notify(api_error_message(error), type="negative", position="top", timeout=8000)
            empty_label.text = "Proiectele nu au putut fi încărcate."
            empty_label.set_visibility(True)
        else:
            project_select.options = {
                str(project["id"]): f'{project["name"]} — {project["id"]}'
                for project in projects
                if project.get("id") and project.get("name")
            }
            project_select.update()
            empty_label.set_visibility(not bool(project_select.options))
            if project_select.options:
                project_select.enable()
                access_button.enable()
        finally:
            loading.set_visibility(False)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="ChIAtraton",
        host=os.getenv("CHIATRATON_UI_HOST", "127.0.0.1"),
        port=int(os.getenv("CHIATRATON_UI_PORT", "8081")),
        reload=False,
    )
