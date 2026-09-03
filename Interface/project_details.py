"""Project details using Andrei's supplied 3/4 + 1/4 layout.

The page shell is rendered immediately. API reads happen only after the
NiceGUI browser connection exists, so a busy AI backend cannot trigger
NiceGUI's default 3-second page-build timeout.
"""

from nicegui import app, ui

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
            loading_label = ui.label("Se încarcă proiectul...")

        content = ui.column().classes("w-full items-center gap-6")

        async def open_document(document_id: str, fallback_name: str) -> None:
            # A plain <a href> to the API would ship without the bearer
            # token, so the content is fetched here (authenticated) and
            # handed to the browser as a download instead.
            try:
                content_bytes, filename = await api_client.get_document_content(document_id)
            except Exception as error:
                ui.notify(api_error_message(error), type="negative", timeout=8000)
                return
            ui.download(content_bytes, filename=filename or fallback_name)

        async def load_after_connect() -> None:
            try:
                project = await api_client.get_project(project_id)
            except Exception as error:
                loading.set_visibility(False)
                with content:
                    ui.label(api_error_message(error)).classes(
                        "text-red-700 font-bold"
                    )
                    ui.button(
                        "Reîncearcă",
                        on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
                    ).props("no-caps")
                return

            if project is None:
                loading.set_visibility(False)
                with content:
                    with ui.column().classes(
                        "w-full max-w-6xl items-center bg-white shadow-xl "
                        "rounded-[1.5rem] p-8"
                    ):
                        ui.icon("search_off", size="xl").classes("text-gray-400")
                        ui.label("Proiectul nu a fost găsit.").classes(
                            "text-xl font-bold text-gray-700"
                        )
                return

            recent = getattr(app, "recent_projects", [])
            recent = [p for p in recent if p["id"] != project_id]
            recent.insert(
                0,
                {
                    "id": project["id"],
                    "smisCode": project.get("smisCode", ""),
                    "name": project["name"],
                },
            )
            app.recent_projects = recent[:5]

            loading_label.text = "Se încarcă documentele și obligațiile..."
            try:
                documents = await api_client.list_all_project_documents(project_id)
            except Exception as error:
                documents = []
                documents_error = api_error_message(error)
            else:
                documents_error = None

            try:
                criteria = await api_client.list_all_project_criteria(project_id)
            except Exception as error:
                criteria = []
                criteria_error = api_error_message(error)
            else:
                criteria_error = None

            loading.set_visibility(False)
            content.clear()

            with content:
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
                            ("Cod SMIS", project.get("smisCode") or "—"),
                            ("Identificator Apel", project.get("fundingCallId") or "—"),
                            ("Nume Proiect", project["name"]),
                            ("Nume Beneficiar", project.get("beneficiaryName") or "—"),
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
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-yellow-100"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-3 mb-2"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("folder_open", size="sm").classes("text-yellow-600")
                            ui.label("Documente încărcate").classes(
                                "text-2xl font-extrabold text-gray-800"
                            )

                        pending_jobs = getattr(app, "pending_extraction_jobs", {})
                        pending_job_id = pending_jobs.get(project_id)
                        if pending_job_id:
                            ui.button(
                                "Vezi rezultatele extracției",
                                icon="visibility",
                                on_click=lambda pid=pending_job_id: ui.navigate.to(
                                    f"/project/{project_id}/criteria-review/{pid}"
                                ),
                            ).props("outline rounded no-caps size=sm color=primary")
                    ui.separator().classes("mb-4 opacity-50")
                    if documents_error:
                        ui.label(documents_error).classes("text-red-700")
                    elif not documents:
                        ui.label(
                            "Niciun document încărcat în proiect momentan."
                        ).classes("text-gray-600")
                    else:
                        with ui.row().classes("w-full gap-4"):
                            for doc in documents:
                                original_filename = (
                                    doc.get("originalFilename") or "document.pdf"
                                )
                                doc_id = doc.get("id")
                                with ui.card().classes(
                                    "w-72 shadow-sm rounded-xl border border-gray-200 "
                                    "bg-gray-50 flex-col gap-1"
                                ):
                                    with ui.row().classes("items-center gap-2 w-full"):
                                        ui.icon("description", size="sm").classes(
                                            "text-gray-500"
                                        )
                                        ui.label(
                                            doc.get("displayName") or original_filename
                                        ).classes("font-bold text-gray-800 break-all")
                                    if doc.get("displayName"):
                                        ui.label(original_filename).classes(
                                            "text-xs text-gray-500 break-all"
                                        )
                                    ui.button(
                                        "Deschide",
                                        on_click=lambda did=doc_id, name=original_filename: (
                                            open_document(did, name)
                                        ),
                                    ).props("flat no-caps dense color=primary").classes(
                                        "text-sm mt-1 self-start px-0"
                                    )

                with ui.column().classes(
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-yellow-100"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("fact_check", size="sm").classes("text-yellow-600")
                            ui.label("Obligații / criterii active").classes(
                                "text-2xl font-extrabold text-gray-800"
                            )

                    ui.separator().classes("my-3 opacity-50")

                    if criteria_error:
                        ui.label(criteria_error).classes("text-red-700")

                    if not criteria:
                        ui.label(
                            "Nu există încă obligații confirmate. După upload, extragerea AI "
                            "pornește automat și vei fi dus la pagina unde confirmi/corectezi/"
                            "respingi propunerile."
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
                                ui.label(f"Termen: {deadline}").classes(
                                    "text-sm text-gray-600"
                                )
                                for anchor in criterion.get("sourceAnchors") or []:
                                    with ui.expansion(
                                        f"Sursă · pagina {anchor.get('pageNumber', '?')}",
                                        icon="article",
                                    ).classes("w-full"):
                                        doc_id = anchor.get("documentId")
                                        if doc_id:
                                            ui.button(
                                                "Deschide documentul",
                                                on_click=lambda did=doc_id: open_document(
                                                    did, "document.pdf"
                                                ),
                                            ).props(
                                                "flat no-caps dense color=primary"
                                            ).classes("text-sm mb-2 self-start px-0")
                                        ui.label(
                                            " ".join(
                                                str(anchor.get("passage", "")).split()
                                            )
                                        ).classes("whitespace-normal")

        # Explicitly flush the page shell to the browser before any API request.
        # NiceGUI treats connected() as the boundary after which long-running
        # async work is safe and updates are delivered over the websocket.
        await ui.context.client.connected(timeout=10.0)
        await load_after_connect()
