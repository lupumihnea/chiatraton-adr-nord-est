"""Project-details page using the public UUID and HTTP API data."""

from nicegui import ui

from Interface.api_client import api_client, api_error_message


@ui.page("/projects/{project_id}")
async def project_details_page(project_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30"):
        with ui.row().classes("w-full max-w-6xl p-4"):
            ui.button(
                "Înapoi la start",
                icon="home",
                on_click=lambda: ui.navigate.to("/"),
            ).props("flat rounded no-caps text-color=grey-8")

        loading = ui.row().classes("items-center gap-2 text-gray-600 mt-8")
        with loading:
            ui.spinner(size="lg")
            ui.label("Se încarcă proiectul...")

        content = ui.column().classes("w-full max-w-6xl px-4 gap-6")
        content.set_visibility(False)
        try:
            project = await api_client.get_project(project_id)
        except Exception as error:
            ui.notify(api_error_message(error), type="negative", position="top", timeout=8000)
            project = None
        finally:
            loading.set_visibility(False)

        with content:
            if project is None:
                with ui.column().classes(
                    "w-full items-center bg-white shadow-xl rounded-[1.5rem] p-8"
                ):
                    ui.icon("search_off", size="xl").classes("text-gray-400")
                    ui.label("Proiectul nu a fost găsit.").classes(
                        "text-xl font-bold text-gray-700"
                    )
            else:
                with ui.row().classes("w-full gap-6 flex-wrap lg:flex-nowrap items-stretch"):
                    with ui.column().classes(
                        "grow bg-white shadow-xl rounded-[1.5rem] p-6 "
                        "border border-yellow-100"
                    ):
                        with ui.row().classes("items-center mb-2 gap-2"):
                            ui.icon("info", size="sm").classes("text-yellow-600")
                            ui.label("Detalii proiect").classes(
                                "text-2xl font-extrabold text-gray-800"
                            )
                        ui.separator()
                        details = (
                            ("Nume", project["name"]),
                            ("Project ID", project["id"]),
                            ("Data finalizării", project["completionDate"]),
                            ("Sfârșitul monitorizării", project["monitoringEndDate"]),
                        )
                        with ui.grid(columns=2).classes("w-full gap-4 mt-4"):
                            for label, value in details:
                                with ui.column().classes("gap-1"):
                                    ui.label(label).classes(
                                        "text-xs font-extrabold text-gray-500 uppercase"
                                    )
                                    ui.label(str(value)).classes(
                                        "text-base font-bold text-gray-800 bg-gray-50 "
                                        "px-3 py-2 rounded-xl border border-gray-100 w-full"
                                    )

                    with ui.column().classes(
                        "w-full lg:w-72 items-center justify-center bg-yellow-50 shadow-xl "
                        "rounded-[1.5rem] p-6 border-2 border-yellow-200"
                    ):
                        ui.icon("cloud_upload", size="50px").classes("text-yellow-600 mb-4")
                        ui.button(
                            "Încarcă documente",
                            icon="upload_file",
                            on_click=lambda: ui.navigate.to(
                                f"/projects/{project_id}/documents"
                            ),
                        ).props("push rounded color=primary").classes(
                            "px-4 py-2 font-extrabold text-gray-900 w-full"
                        )
        content.set_visibility(True)
