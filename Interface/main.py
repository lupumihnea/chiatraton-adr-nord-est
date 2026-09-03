"""NiceGUI entry point based directly on Andrei's supplied interface."""

import os
from dotenv import load_dotenv

load_dotenv()

from nicegui import app, ui

from Interface import add_project, criteria_review, project_details, upload_documents
from Interface.api_client import api_client, api_error_message

_REGISTERED_PAGE_MODULES = (add_project, criteria_review, project_details, upload_documents)

# Includem fontul și fundalul definite în interfața furnizată de Andrei.
ui.add_head_html(
    """
    <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;700;800&display=swap"
          rel="stylesheet">
    <style>
        body {
            font-family: 'Quicksand', sans-serif;
            background-color: #fffdf5;
        }
    </style>
    """,
    shared=True,
)

assets_dir = os.path.join(os.path.dirname(__file__), "Assets")
app.add_static_files("/Assets", assets_dir)
app.on_shutdown(api_client.close)


@ui.page("/")
async def home() -> None:
    """Render immediately; load projects only after the browser is connected."""

    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full items-center mt-8 space-y-6 min-h-[85vh]"):
        with ui.row().classes("absolute top-6 right-6 items-center gap-3 bg-white px-4 py-2 rounded-full shadow-sm"):
            ui.label("Bine ai venit, expert în monitorizare!").classes("text-gray-700 font-bold text-sm")
            ui.icon("account_circle", size="2rem").classes("text-gray-400")

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

        with ui.column().classes("w-full max-w-xl items-start space-y-4"):
            search_bar = ui.input(placeholder="Introdu codul SMIS...").props(
                'rounded outlined clearable mask="######" '
                'input-class="text-2xl font-bold text-center"'
            ).classes("w-full text-2xl bg-white shadow-xl rounded-full border-0")
            search_bar.disable()

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

        projects: list[dict[str, object]] = []

        def access_project() -> None:
            smis_code = str(search_bar.value or "").strip()
            if len(smis_code) != 6 or not smis_code.isdigit():
                ui.notify(
                    "Introdu un cod SMIS valid de șase cifre.",
                    type="warning",
                    position="top",
                )
                return

            project_id = next(
                (
                    str(project["id"])
                    for project in projects
                    if str(project.get("smisCode", "")) == smis_code
                ),
                None,
            )

            if project_id is None:
                ui.notify(
                    f"Proiectul cu codul SMIS {smis_code} nu a fost găsit.",
                    type="negative",
                    position="top",
                )
                return
            ui.navigate.to(f"/project/{project_id}")

        ui.button("Accesează", on_click=access_project).props(
            "push rounded size=xl color=primary"
        ).classes(
            "w-64 py-4 mt-4 text-2xl font-extrabold shadow-xl hover:scale-105 "
            "transition-transform duration-200 text-gray-900"
        )
        
        recent_container = ui.column().classes(
            "absolute left-4 top-32 w-72 p-4 items-start space-y-3 hidden lg:flex"
        )
        recent_container.set_visibility(False)

        ui.space()

        async def load_projects_after_connect() -> None:
            try:
                fetched = await api_client.list_all_projects()
            except Exception as error:
                ui.notify(
                    api_error_message(error),
                    type="negative",
                    position="top",
                    timeout=8000,
                )
            else:
                projects.extend(fetched)
                
                recent = getattr(app, "recent_projects", [])
                if recent:
                    recent_container.set_visibility(True)
                    with recent_container:
                        with ui.row().classes("items-center gap-2 mb-2"):
                            ui.icon("history", size="sm").classes("text-yellow-600")
                            ui.label("Proiecte recente").classes(
                                "text-lg font-extrabold text-gray-700 uppercase tracking-wide"
                            )
                        with ui.column().classes("w-full gap-3"):
                            for r_proj in recent:
                                btn_text = f"{r_proj.get('smisCode', '')} - {r_proj.get('name', 'Proiect')}"
                                if len(btn_text) > 35:
                                    btn_text = btn_text[:32] + "..."
                                ui.button(
                                    btn_text,
                                    on_click=lambda pid=r_proj["id"]: ui.navigate.to(f"/project/{pid}")
                                ).props("push rounded size=md color=primary no-caps").classes(
                                    "w-full justify-start text-left text-gray-900 font-bold shadow-md "
                                    "hover:scale-105 transition-transform duration-200 px-4 py-3"
                                )

            finally:
                loading.set_visibility(False)
                search_bar.enable()

        # Send the visible page first, then load projects over the websocket.
        # NiceGUI's default 3-second page-build timeout can otherwise fire
        # while a busy AI backend is still starting up.
        await ui.context.client.connected(timeout=10.0)
        await load_projects_after_connect()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="ADR Analizator",
        favicon=os.path.join(assets_dir, "favicon.png"),
        host=os.getenv("CHIATRATON_UI_HOST", "127.0.0.1"),
        port=int(os.getenv("CHIATRATON_UI_PORT", "8081")),
        reload=False,
    )
