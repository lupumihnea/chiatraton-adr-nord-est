"""Project details using Andrei's supplied 3/4 + 1/4 layout."""

from nicegui import ui

from Interface.api_client import api_client, api_error_message


@ui.page("/project/{project_id}")
async def project_details_page(project_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30"):
        with ui.row().classes("w-full max-w-6xl p-4"):
            ui.button(
                "Înapoi la start",
                icon="home",
                on_click=lambda: ui.navigate.to("/"),
            ).props("flat rounded no-caps size=md text-color=grey-8").classes(
                "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
            )

        loading = ui.row().classes("items-center gap-2 text-gray-600 mt-8")
        with loading:
            ui.spinner(size="lg")
            ui.label("Se încarcă proiectul...")

        try:
            project = await api_client.get_project(project_id)
        except Exception as error:
            ui.notify(
                api_error_message(error),
                type="negative",
                position="top",
                timeout=8000,
            )
            project = None
        finally:
            loading.set_visibility(False)

        if project is None:
            with ui.column().classes(
                "w-full max-w-6xl items-center bg-white shadow-xl "
                "rounded-[1.5rem] p-8"
            ):
                ui.icon("search_off", size="xl").classes("text-gray-400")
                ui.label("Proiectul nu a fost găsit.").classes(
                    "text-xl font-bold text-gray-700"
                )
            return

        with ui.row().classes(
            "w-full max-w-6xl px-4 gap-6 flex-nowrap items-stretch"
        ):
            with ui.column().classes(
                "w-3/4 bg-white shadow-xl rounded-[1.5rem] p-6 "
                "border border-yellow-100"
            ):
                with ui.row().classes("items-center mb-2 gap-2"):
                    ui.icon("info", size="sm").classes("text-yellow-600")
                    ui.label("Detalii Proiect").classes(
                        "text-2xl font-extrabold text-gray-800"
                    )

                ui.separator().classes("mb-4 opacity-50")

                details = (
                    ("Project ID", project["id"]),
                    ("Data finalizării", project["completionDate"]),
                    ("Nume Proiect", project["name"]),
                    ("Sfârșitul monitorizării", project["monitoringEndDate"]),
                )
                with ui.grid(columns=2).classes("w-full gap-4"):
                    for label, value in details:
                        with ui.column().classes("space-y-1"):
                            ui.label(label).classes(
                                "text-xs font-extrabold text-gray-500 uppercase "
                                "tracking-wide"
                            )
                            ui.label(str(value)).classes(
                                "text-base font-bold text-gray-800 bg-gray-50 px-3 "
                                "py-1 rounded-xl border border-gray-100 w-full break-all"
                            )

            with ui.column().classes(
                "w-1/4 items-center justify-center bg-yellow-50 shadow-xl "
                "rounded-[1.5rem] p-6 border-2 border-yellow-200 transition-all "
                "hover:bg-yellow-100/80"
            ):
                ui.icon("cloud_upload", size="50px").classes(
                    "text-yellow-600 mb-4"
                )
                ui.button(
                    "Încarcă Documente",
                    icon="upload_file",
                    on_click=lambda: ui.navigate.to(f"/upload/{project_id}"),
                ).props("push rounded size=md color=primary").classes(
                    "px-4 py-2 text-sm font-extrabold shadow-lg hover:scale-105 "
                    "transition-transform duration-200 text-gray-900 w-full"
                )

        with ui.column().classes(
            "w-full max-w-6xl mt-6 bg-white shadow-xl rounded-[1.5rem] p-6 "
            "border border-yellow-100"
        ):
            with ui.row().classes("w-full items-center justify-between gap-3"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("fact_check", size="sm").classes("text-yellow-600")
                    ui.label("Obligații / criterii active").classes(
                        "text-2xl font-extrabold text-gray-800"
                    )
                ui.button(
                    "Încarcă documente și extrage din nou",
                    icon="document_scanner",
                    on_click=lambda: ui.navigate.to(f"/upload/{project_id}"),
                ).props("outline rounded no-caps")

            ui.separator().classes("my-3 opacity-50")
            try:
                criteria = await api_client.list_all_project_criteria(project_id)
            except Exception as error:
                ui.label(api_error_message(error)).classes("text-red-700")
                criteria = []

            if not criteria:
                ui.label(
                    "Nu există încă obligații confirmate. După upload, extragerea AI pornește "
                    "automat și vei fi dus la pagina unde confirmi/corectezi/respingi propunerile."
                ).classes("text-gray-600")
            else:
                ui.label(f"{len(criteria)} obligații confirmate").classes(
                    "font-bold text-green-700 mb-2"
                )
                for criterion in criteria:
                    with ui.card().classes(
                        "w-full shadow-sm rounded-xl border border-green-100"
                    ):
                        ui.label(str(criterion.get("code", ""))).classes(
                            "font-extrabold text-green-800"
                        )
                        ui.label(
                            " ".join(str(criterion.get("description", "")).split())
                        ).classes("text-gray-800")
                        deadline = criterion.get("deadline") or "Fără termen explicit"
                        ui.label(f"Termen: {deadline}").classes("text-sm text-gray-600")
                        for anchor in criterion.get("sourceAnchors") or []:
                            with ui.expansion(
                                f"Sursă · pagina {anchor.get('pageNumber', '?')}",
                                icon="article",
                            ).classes("w-full"):
                                ui.label(
                                    " ".join(str(anchor.get("passage", "")).split())
                                ).classes("whitespace-normal")

