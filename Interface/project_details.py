"""Project details with obligations and progress reports.

Backend contract names remain Criterion/Report. The UI deliberately presents
criteria as obligations and reports as progress against those obligations.
"""

from __future__ import annotations

from typing import Any

from nicegui import app, ui

from Interface.api_client import (
    IdempotencyKeyManager,
    api_client,
    api_error_message,
    json_fingerprint,
)
from Interface.document_viewer import open_document_at_anchor
from Interface.obligation_progress import latest_analyzed_report, obligation_progress

REPORT_STATUS_LABELS = {
    "created": "Pregătit pentru analiză",
    "analysis_queued": "Analiză în așteptare",
    "analysis_in_progress": "Analiză în curs",
    "awaiting_user_decision": "Progres analizat",
    "completed": "Finalizat",
    "analysis_failed": "Analiza a eșuat",
}

PROGRESS_STYLES = {
    "unknown": {
        "icon": "help_outline",
        "card": "border-sky-200 border-l-sky-500",
        "panel": "bg-sky-50 border-sky-200",
        "summary": "bg-sky-50 border-sky-200 text-sky-800",
        "text": "text-sky-800",
    },
    "no_progress": {
        "icon": "radio_button_unchecked",
        "card": "border-gray-200 border-l-gray-400",
        "panel": "bg-gray-50 border-gray-200",
        "summary": "bg-gray-50 border-gray-200 text-gray-700",
        "text": "text-gray-700",
    },
    "partial": {
        "icon": "timelapse",
        "card": "border-amber-200 border-l-amber-500",
        "panel": "bg-amber-50 border-amber-200",
        "summary": "bg-amber-50 border-amber-200 text-amber-800",
        "text": "text-amber-800",
    },
    "completed": {
        "icon": "check_circle",
        "card": "border-emerald-200 border-l-emerald-500",
        "panel": "bg-emerald-50 border-emerald-200",
        "summary": "bg-emerald-50 border-emerald-200 text-emerald-800",
        "text": "text-emerald-800",
    },
}


@ui.page("/project/{project_id}")
async def project_details_page(project_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")
    key_manager = IdempotencyKeyManager()

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

        content = ui.column().classes("w-full items-center gap-6 pb-8")

        async def load_after_connect() -> None:
            try:
                project = await api_client.get_project(project_id)
            except Exception as error:
                loading.set_visibility(False)
                with content:
                    ui.label(api_error_message(error)).classes("text-red-700 font-bold")
                    ui.button(
                        "Reîncearcă",
                        on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
                    ).props("push rounded size=md color=primary no-caps").classes(
                        "px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 "
                        "transition-transform duration-200 text-gray-900"
                    )
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

            loading_label.text = "Se încarcă documentele, obligațiile și rapoartele..."
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

            try:
                reports = await api_client.list_all_project_reports(project_id)
            except Exception as error:
                reports = []
                reports_error = api_error_message(error)
            else:
                reports_error = None

            latest_progress_report = latest_analyzed_report(reports)
            progress_validations: list[dict[str, Any]] = []
            progress_error: str | None = None
            if latest_progress_report is not None:
                try:
                    progress_validations = await api_client.list_all_report_validations(
                        str(latest_progress_report.get("id") or "")
                    )
                except Exception as error:
                    progress_error = api_error_message(error)

            validation_by_criterion = {
                str(validation.get("criterionId")): validation
                for validation in progress_validations
                if validation.get("criterionId")
            }
            progress_by_criterion = {
                str(criterion.get("id")): obligation_progress(
                    validation_by_criterion.get(str(criterion.get("id")))
                )
                for criterion in criteria
                if criterion.get("id")
            }
            document_by_id = {
                str(document.get("id")): document
                for document in documents
                if document.get("id")
            }

            loading.set_visibility(False)
            content.clear()

            async def start_report_analysis(report: dict[str, Any]) -> None:
                report_id = str(report.get("id") or "")
                if not report_id:
                    ui.notify("Raportul nu are ID.", type="negative")
                    return
                if not criteria:
                    ui.notify(
                        "Confirmă mai întâi cel puțin o obligație a proiectului.",
                        type="warning",
                    )
                    return
                payload = {
                    "reportId": report_id,
                    "projectDocumentIds": [],
                    "previousReportIds": [],
                }
                fingerprint = json_fingerprint(payload)
                operation = f"analyze-progress:{report_id}"
                key = key_manager.key_for(operation, fingerprint)
                try:
                    job = await api_client.create_report_analysis_job(
                        report_id,
                        idempotency_key=key,
                    )
                except Exception as error:
                    ui.notify(api_error_message(error), type="negative", timeout=10000)
                    return
                key_manager.mark_succeeded(operation, fingerprint)
                job_id = str(job.get("id") or "")
                if not job_id:
                    ui.notify("Job-ul de analiză nu are ID.", type="negative")
                    return
                ui.navigate.to(
                    f"/project/{project_id}/report-analysis/{report_id}/{job_id}"
                )

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
                                            original_filename
                                        ).classes("font-bold text-gray-800 break-all")
                                    if doc.get("displayName"):
                                        ui.label(doc.get("displayName")).classes(
                                            "text-xs text-gray-500 break-all"
                                        )
                                    ui.button(
                                        "Deschide",
                                        on_click=lambda did=doc_id, name=original_filename: (
                                            open_document_at_anchor(did, name)
                                        ),
                                    ).props("flat no-caps dense color=primary").classes(
                                        "text-sm mt-1 self-start px-0"
                                    )

                qa_messages: list[dict[str, Any]] = []
                with ui.column().classes(
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-yellow-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("forum", size="sm").classes("text-yellow-600")
                        ui.label("Întreabă documentele").classes(
                            "text-2xl font-extrabold text-gray-800"
                        )
                    ui.separator().classes("my-3 opacity-50")
                    qa_results = ui.column().classes("w-full gap-3")

                    def render_qa_messages() -> None:
                        qa_results.clear()
                        with qa_results:
                            for message in qa_messages:
                                is_user = message.get("role") == "user"
                                with ui.row().classes(
                                    "w-full justify-end" if is_user else "w-full justify-start"
                                ):
                                    with ui.column().classes(
                                        (
                                            "max-w-3xl bg-yellow-50 border border-yellow-200 "
                                            if is_user
                                            else "max-w-4xl bg-gray-50 border border-gray-200 "
                                        )
                                        + "rounded-lg px-4 py-3 gap-2"
                                    ):
                                        ui.label(str(message.get("text", ""))).classes(
                                            "text-gray-800 whitespace-normal"
                                        )
                                        for match in message.get("matches") or []:
                                            anchor = match.get("sourceAnchor") or {}
                                            doc_id = str(anchor.get("documentId") or "")
                                            page = int(anchor.get("pageNumber") or 1)
                                            passage = str(anchor.get("passage") or "")
                                            document = document_by_id.get(doc_id, {})
                                            name = str(
                                                document.get("originalFilename")
                                                or "document.pdf"
                                            )
                                            ui.button(
                                                f"{name} · pagina {page}",
                                                icon="article",
                                                on_click=lambda did=doc_id, filename=name,
                                                page_number=page, text=passage: (
                                                    open_document_at_anchor(
                                                        did,
                                                        filename,
                                                        page_number=page_number,
                                                        passage=text,
                                                    )
                                                ),
                                            ).props(
                                                "flat dense no-caps color=primary"
                                            ).classes("self-start px-0")
                                            ui.label(" ".join(passage.split())).classes(
                                                "text-sm text-gray-600 whitespace-normal"
                                            )

                    with ui.row().classes("w-full items-center gap-2"):
                        question_input = ui.input(
                            placeholder="Ex.: Care este valoarea contribuției proprii?"
                        ).props("outlined dense").classes("flex-grow")

                        async def ask_documents() -> None:
                            question = str(question_input.value or "").strip()
                            if len(question) < 3:
                                ui.notify("Scrie o întrebare factuală.", type="warning")
                                return
                            qa_messages.append({"role": "user", "text": question})
                            render_qa_messages()
                            question_input.disable()
                            send_button.disable()
                            payload = {
                                "question": question,
                                "documentIds": list(document_by_id),
                            }
                            fingerprint = json_fingerprint(payload)
                            operation = f"document-question:{project_id}"
                            key = key_manager.key_for(operation, fingerprint)
                            try:
                                answer = await api_client.ask_project_documents(
                                    project_id,
                                    question=question,
                                    document_ids=list(document_by_id),
                                    idempotency_key=key,
                                )
                            except Exception as error:
                                ui.notify(
                                    api_error_message(error), type="negative", timeout=10000
                                )
                            else:
                                key_manager.mark_succeeded(operation, fingerprint)
                                qa_messages.append(
                                    {
                                        "role": "assistant",
                                        "text": str(answer.get("answer") or ""),
                                        "matches": answer.get("matches") or [],
                                    }
                                )
                                question_input.value = ""
                                render_qa_messages()
                            finally:
                                question_input.enable()
                                send_button.enable()

                        send_button = ui.button(icon="send", on_click=ask_documents).props(
                            "round color=primary"
                        )
                        send_button.tooltip("Trimite întrebarea")

                with ui.column().classes(
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-yellow-100"
                ):
                    with ui.row().classes("w-full items-center justify-between gap-3"):
                        with ui.row().classes("items-center gap-2"):
                            ui.icon("fact_check", size="sm").classes("text-yellow-600")
                            ui.label("Obligații confirmate").classes(
                                "text-2xl font-extrabold text-gray-800"
                            )

                    ui.label(
                        "Obligațiile confirmate și starea lor conform celui mai recent "
                        "raport de progres analizat."
                    ).classes("text-sm text-gray-600")
                    ui.separator().classes("my-3 opacity-50")

                    if criteria_error:
                        ui.label(criteria_error).classes("text-red-700")

                    if not criteria:
                        ui.label(
                            "Nu există încă obligații confirmate. Încarcă documentele-sursă, "
                            "apoi confirmă/corectează/respinge propunerile AI."
                        ).classes("text-gray-600")
                    else:
                        if latest_progress_report is None:
                            with ui.row().classes(
                                "w-full items-center gap-2 p-3 rounded-lg border "
                                "border-gray-200 bg-gray-50 text-gray-700 mb-2"
                            ):
                                ui.icon("history_toggle_off", size="sm")
                                ui.label(
                                    "Nu există încă un raport de progres analizat."
                                ).classes("font-bold")
                        else:
                            period_start = latest_progress_report.get("periodStart", "?")
                            period_end = latest_progress_report.get("periodEnd", "?")
                            with ui.row().classes(
                                "w-full items-center justify-between gap-3 flex-wrap mb-2"
                            ):
                                with ui.column().classes("gap-0"):
                                    ui.label("Stare la cel mai recent raport analizat").classes(
                                        "font-extrabold text-gray-800"
                                    )
                                    ui.label(
                                        f"Perioadă: {period_start} → {period_end}"
                                    ).classes("text-sm text-gray-600")
                                if latest_progress_report.get("status") == (
                                    "awaiting_user_decision"
                                ):
                                    ui.badge("Evaluare AI de verificat", color="warning").props(
                                        "outline"
                                    )

                            if progress_error:
                                ui.label(progress_error).classes("text-red-700 font-bold")
                            else:
                                progress_counts = {
                                    "unknown": 0,
                                    "no_progress": 0,
                                    "partial": 0,
                                    "completed": 0,
                                }
                                for progress in progress_by_criterion.values():
                                    progress_counts[progress.state] += 1

                                with ui.row().classes("w-full gap-2 flex-wrap mb-2"):
                                    for state, summary_label in (
                                        ("unknown", "necunoscute"),
                                        ("no_progress", "fără progres"),
                                        ("partial", "în progres"),
                                        ("completed", "finalizate"),
                                    ):
                                        style = PROGRESS_STYLES[state]
                                        with ui.row().classes(
                                            "items-center gap-2 px-3 py-2 rounded-lg border "
                                            f"{style['summary']}"
                                        ):
                                            ui.icon(style["icon"], size="xs")
                                            ui.label(
                                                f"{progress_counts[state]} {summary_label}"
                                            ).classes("text-sm font-bold")

                        for criterion in criteria:
                            criterion_id = str(criterion.get("id") or "")
                            progress = progress_by_criterion.get(
                                criterion_id, obligation_progress(None)
                            )
                            progress_style = PROGRESS_STYLES[progress.state]
                            with ui.card().classes(
                                "w-full shadow-sm rounded-lg border border-l-4 "
                                f"{progress_style['card']}"
                            ):
                                with ui.row().classes(
                                    "w-full items-start justify-between gap-3 flex-wrap"
                                ):
                                    ui.label("Obligație").classes(
                                        "font-extrabold text-gray-500 uppercase tracking-wide "
                                        "text-xs"
                                    )
                                    with ui.row().classes(
                                        f"items-center gap-1 {progress_style['text']}"
                                    ):
                                        ui.icon(progress_style["icon"], size="xs")
                                        ui.label(progress.label).classes(
                                            "font-extrabold text-sm"
                                        )
                                ui.label(
                                    " ".join(str(criterion.get("description", "")).split())
                                ).classes("text-gray-800 font-bold text-lg")
                                deadline = criterion.get("deadline") or "Fără termen explicit"
                                ui.label(f"Termen: {deadline}").classes(
                                    "text-sm text-gray-600 mb-2"
                                )

                                if progress_error:
                                    ui.label(
                                        "Starea din raport nu a putut fi încărcată."
                                    ).classes("text-sm text-red-700 font-bold")
                                else:
                                    with ui.column().classes(
                                        "w-full gap-1 p-3 rounded-lg border "
                                        f"{progress_style['panel']}"
                                    ):
                                        with ui.row().classes(
                                            "w-full items-center justify-between gap-2 flex-wrap"
                                        ):
                                            ui.label("Progres raportat").classes(
                                                f"text-sm font-extrabold {progress_style['text']}"
                                            )
                                            if progress.pending_review:
                                                ui.badge(
                                                    "De verificat", color="warning"
                                                ).props("outline")
                                        progress_detail = progress.detail
                                        if latest_progress_report is None:
                                            progress_detail = (
                                                "Starea va fi actualizată după analiza primului "
                                                "raport de progres."
                                            )
                                        ui.label(progress_detail).classes(
                                            "text-sm text-gray-700 whitespace-normal"
                                        )

                                        for index, anchor in enumerate(
                                            progress.source_anchors, start=1
                                        ):
                                            doc_id = str(anchor.get("documentId") or "")
                                            document = document_by_id.get(doc_id, {})
                                            doc_name = str(
                                                document.get("originalFilename")
                                                or "document.pdf"
                                            )
                                            page_number = int(
                                                anchor.get("pageNumber") or 1
                                            )
                                            passage = str(anchor.get("passage") or "")
                                            if doc_id:
                                                ui.button(
                                                    f"Dovadă progres {index} · pagina "
                                                    f"{page_number}",
                                                    icon="open_in_new",
                                                    on_click=lambda did=doc_id, name=doc_name,
                                                    page=page_number,
                                                    text=passage: open_document_at_anchor(
                                                        did,
                                                        name,
                                                        page_number=page,
                                                        passage=text,
                                                    ),
                                                ).props(
                                                    "flat dense no-caps color=primary"
                                                ).classes("self-start px-0 text-sm")

                                source_anchors = criterion.get("sourceAnchors") or []
                                if source_anchors:
                                    ui.label("Sursa obligației").classes(
                                        "text-xs font-bold text-gray-500 uppercase mt-1"
                                    )
                                for anchor in source_anchors:
                                    page_number = anchor.get("pageNumber", "?")
                                    doc_id = anchor.get("documentId")
                                    passage = str(anchor.get("passage", ""))
                                    doc_name = "document.pdf"
                                    if doc_id:
                                        document = document_by_id.get(str(doc_id), {})
                                        doc_name = (
                                            document.get("originalFilename") or "document.pdf"
                                        )

                                    with ui.expansion(
                                        f"{doc_name} · pagina {page_number}",
                                        icon="article",
                                    ).classes(
                                        "w-full bg-gray-50 rounded-md border border-gray-100"
                                    ):
                                        if doc_id:
                                            ui.button(
                                                "Deschide documentul",
                                                on_click=lambda did=doc_id, name=doc_name,
                                                page=page_number,
                                                text=passage: (
                                                    open_document_at_anchor(
                                                        did,
                                                        name,
                                                        page_number=int(page),
                                                        passage=text,
                                                    )
                                                ),
                                            ).props(
                                                "flat no-caps dense color=primary"
                                            ).classes("text-sm mb-2 self-start px-0")
                                        ui.label(
                                            " ".join(
                                                str(anchor.get("passage", "")).split()
                                            )
                                        ).classes("whitespace-normal text-gray-700")

                with ui.column().classes(
                    "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
                    "border border-yellow-100"
                ):
                    with ui.row().classes("items-center gap-2"):
                        ui.icon("timeline", size="sm").classes("text-yellow-600")
                        ui.label("Rapoarte de progres").classes(
                            "text-2xl font-extrabold text-gray-800"
                        )
                    ui.label(
                        "Rapoartele nu adaugă obligații. AI-ul le compară cu obligațiile "
                        "confirmate și produce numai starea/progresul fiecărei obligații."
                    ).classes("text-sm text-gray-600")
                    ui.separator().classes("my-3 opacity-50")

                    if reports_error:
                        ui.label(reports_error).classes("text-red-700")

                    if not reports:
                        ui.label(
                            "Nu există încă rapoarte de progres încărcate."
                        ).classes("text-gray-600")
                    else:
                        for report in reports:
                            status = str(report.get("status", "created"))
                            with ui.card().classes(
                                "w-full shadow-sm rounded-xl border border-yellow-100"
                            ):
                                with ui.row().classes(
                                    "w-full items-center justify-between gap-3"
                                ):
                                    with ui.column().classes("gap-1"):
                                        ui.label("Raport de progres").classes(
                                            "font-extrabold text-yellow-800"
                                        )
                                        ui.label(
                                            f"Perioadă: {report.get('periodStart', '?')} → "
                                            f"{report.get('periodEnd', '?')}"
                                        ).classes("text-gray-700")
                                        ui.label(
                                            f"Status: {REPORT_STATUS_LABELS.get(status, status)}"
                                        ).classes("text-sm font-bold text-gray-600")

                                    if status in {"created", "analysis_failed"}:
                                        button = ui.button(
                                            "Analizează progresul",
                                            icon="psychology",
                                            on_click=lambda r=report: start_report_analysis(r),
                                        ).props(
                                            "push rounded size=md color=primary no-caps"
                                        ).classes(
                                            "px-6 py-2 text-base font-extrabold shadow-lg "
                                            "hover:scale-105 transition-transform duration-200 "
                                            "text-gray-900"
                                        )
                                        if not criteria:
                                            button.disable()
                                    elif status in {"awaiting_user_decision", "completed"}:
                                        ui.button(
                                            "Vezi progresul",
                                            icon="visibility",
                                            on_click=lambda r=report: ui.navigate.to(
                                                f"/project/{project_id}/report-analysis/"
                                                f"{r.get('id')}/results"
                                            ),
                                        ).props(
                                            "outline rounded size=sm color=primary no-caps"
                                        ).classes(
                                            "px-4 py-1 text-sm font-bold hover:bg-gray-50"
                                        )
                                    else:
                                        ui.label(
                                            "Analiza rulează în fundal; reîncarcă pagina "
                                            "pentru status."
                                        ).classes("text-sm text-yellow-700")

        await ui.context.client.connected(timeout=10.0)
        await load_after_connect()
