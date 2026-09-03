"""NiceGUI entry point preserving Andrei's current visual design."""

import os
from pathlib import Path

from nicegui import app, ui

from Interface import add_project, project_details, upload_documents
from Interface.api_client import api_client, api_error_message

_REGISTERED_PAGE_MODULES = (add_project, project_details, upload_documents)
ASSETS_DIR = Path(__file__).with_name("Assets")

ui.add_head_html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;700;800"
          rel="stylesheet">
    <style>
        body {
            font-family: 'Quicksand', ui-sans-serif, system-ui, sans-serif;
            background-color: #fffdf5;
        }
    </style>
    """,
    shared=True,
)
app.add_static_files("/Assets", str(ASSETS_DIR))
app.on_shutdown(api_client.close)


@ui.page("/")
async def home() -> None:
    """List projects through the API in Andrei's current landing-page design."""

    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full items-center mt-8 gap-6 min-h-[85vh]"):
        ui.image("/Assets/Logo-ADR.png").classes(
            "w-64 transition-transform hover:scale-105 duration-300 drop-shadow-sm"
        )

        with ui.row().classes(
            "items-center bg-white px-4 py-2 rounded-full shadow-md "
            "border-2 border-yellow-200 mb-2 hover:-translate-y-1 transition-transform"
        ):
            ui.image("/Assets/ADRut.png").classes(
                "w-12 h-12 rounded-full bg-yellow-50 p-1"
            )
            ui.label("Haide să începem analiza!").classes(
                "text-lg font-extrabold text-gray-700 mx-3"
            )

        with ui.column().classes("w-full max-w-xl items-start gap-4"):
            project_select = ui.select(
                options={},
                label="Selectează proiectul după nume și UUID",
                with_input=True,
            ).props(
                "rounded outlined clearable options-dense "
                'input-class="text-lg font-bold"'
            ).classes("w-full text-lg bg-white shadow-xl rounded-full border-0")
            project_select.disable()

            ui.button(
                "Adaugă un nou proiect",
                icon="add",
                on_click=lambda: ui.navigate.to("/add_project"),
            ).props("flat rounded no-caps size=md").classes(
                "text-yellow-600 font-bold bg-yellow-50 hover:bg-yellow-100 "
                "transition-colors rounded-full px-4 py-1 text-sm"
            )

        loading = ui.row().classes("items-center gap-2 text-gray-600")
        with loading:
            ui.spinner(size="md")
            ui.label("Se încarcă proiectele...")

        status_label = ui.label().classes("text-sm text-gray-500")
        status_label.set_visibility(False)

        def access_project() -> None:
            if not project_select.value:
                ui.notify("Selectează un proiect.", type="warning", position="top")
                return
            ui.navigate.to(f"/projects/{project_select.value}")

        access_button = ui.button(
            "Accesează",
            on_click=access_project,
        ).props("push rounded size=xl color=primary").classes(
            "w-64 py-4 mt-4 text-2xl font-extrabold shadow-xl hover:scale-105 "
            "transition-transform duration-200 text-gray-900"
        )
        access_button.disable()
        ui.space()

        try:
            projects = await api_client.list_all_projects()
        except Exception as error:
            status_label.text = "Proiectele nu au putut fi încărcate."
            status_label.classes(replace="text-sm font-bold text-red-700")
            status_label.set_visibility(True)
            ui.notify(api_error_message(error), type="negative", position="top", timeout=8000)
        else:
            project_select.options = {
                str(project["id"]): f'{project["name"]} — {project["id"]}'
                for project in projects
                if project.get("id") and project.get("name")
            }
            project_select.update()
            if project_select.options:
                project_select.enable()
                access_button.enable()
            else:
                status_label.text = "Nu există încă proiecte."
                status_label.set_visibility(True)
        finally:
            loading.set_visibility(False)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="ChIAtraton",
        host=os.getenv("CHIATRATON_UI_HOST", "127.0.0.1"),
        port=int(os.getenv("CHIATRATON_UI_PORT", "8081")),
        reload=False,
    )
