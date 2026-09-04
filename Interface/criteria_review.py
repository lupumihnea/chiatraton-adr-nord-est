"""Human review page for AI-extracted project obligations."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from nicegui import app, ui

from Interface.api_client import (
    IdempotencyKeyManager,
    api_client,
    api_error_message,
    json_fingerprint,
)

TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled"}


def _clean(text: object) -> str:
    return " ".join(str(text or "").split())


def _deadline_text(value: object) -> str:
    return str(value) if value else "Fără termen explicit"


@ui.page("/project/{project_id}/criteria-review/{job_id}")
async def criteria_review_page(project_id: str, job_id: str) -> None:
    """Show extraction proposals, their exact sources, and review actions."""

    ui.colors(primary="#ffcc00", accent="#ffcc00")
    key_manager = IdempotencyKeyManager()

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30 p-4"):
        with ui.row().classes("w-full max-w-6xl items-center justify-between mb-2"):
            ui.button(
                "Înapoi la proiect",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
            ).props("flat rounded no-caps size=md text-color=grey-8").classes(
                "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
            )
            ui.label("Extragere obligații").classes(
                "text-2xl font-extrabold text-gray-800"
            )

        with ui.card().classes(
            "w-full max-w-6xl rounded-[1.5rem] shadow-xl border border-yellow-100"
        ):
            ui.label(
                "AI-ul propune obligațiile, dar acestea devin obligații confirmate numai după "
                "confirmarea utilizatorului. Pasajele afișate sunt recuperate din sursa locală."
            ).classes("text-gray-700")

            status_row = ui.row().classes("items-center gap-3")
            with status_row:
                spinner = ui.spinner(size="md")
                status_label = ui.label("Se verifică starea extracției...").classes("font-bold")

        proposals_container = ui.column().classes("w-full max-w-6xl gap-4")
        criteria_container = ui.column().classes("w-full max-w-6xl gap-3")

        async def load_proposals() -> list[dict[str, Any]]:
            return await api_client.list_all_criterion_extraction_proposals(job_id)

        async def load_criteria() -> list[dict[str, Any]]:
            return await api_client.list_all_project_criteria(project_id)
            
        async def open_document(document_id: str, fallback_name: str) -> None:
            try:
                content_bytes, filename = await api_client.get_document_content(document_id)
            except Exception as error:
                ui.notify(api_error_message(error), type="negative", timeout=8000)
                return
            ui.download(content_bytes, filename=filename or fallback_name)

        async def load_documents() -> list[dict[str, Any]]:
            return await api_client.list_project_documents(project_id)

        @ui.refreshable
        async def criteria_view() -> None:
            criteria_container.clear()
            with criteria_container:
                try:
                    criteria = await load_criteria()
                except Exception as error:
                    ui.label(api_error_message(error)).classes("text-red-700")
                    return
                ui.label(f"Obligații confirmate: {len(criteria)}").classes(
                    "text-xl font-extrabold text-gray-800"
                )
                if not criteria:
                    ui.label(
                        "Încă nu există obligații confirmate. Confirmă cel puțin "
                        "o propunere de mai jos."
                    ).classes("text-gray-500")
                    return
                for criterion in criteria:
                    with ui.card().classes(
                        "w-full shadow-sm border border-green-100 p-4"
                    ):
                        ui.label(_clean(criterion.get("description"))).classes(
                            "text-gray-800 text-lg font-medium"
                        )
                        ui.label(
                            f"Termen: {_deadline_text(criterion.get('deadline'))}"
                        ).classes("text-sm text-gray-600")

        async def review_one(
            proposal: dict[str, Any],
            *,
            action: str,
            correction: dict[str, Any] | None = None,
            comment: str | None = None,
        ) -> None:
            review: dict[str, Any] = {
                "proposalId": proposal["id"],
                "proposalRevision": proposal["revision"],
                "action": action,
            }
            if correction is not None:
                review["correction"] = correction
            if comment:
                review["comment"] = comment
            payload = {"reviews": [review]}
            fingerprint = json_fingerprint(payload)
            operation = f"criterion-review:{job_id}:{proposal['id']}"
            key = key_manager.key_for(operation, fingerprint)
            try:
                await api_client.review_criterion_proposals(
                    job_id,
                    reviews=payload["reviews"],
                    idempotency_key=key,
                )
            except Exception as error:
                ui.notify(api_error_message(error), type="negative", timeout=10000)
                return
            key_manager.mark_succeeded(operation, fingerprint)
            ui.notify("Decizia a fost salvată.", type="positive")
            await proposals_view.refresh()
            await criteria_view.refresh()

        def correction_dialog(proposal: dict[str, Any]) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-3xl"):
                ui.label("Corectează obligația propusă").classes("text-xl font-extrabold")
                code = ui.input("Cod", value=proposal.get("proposedCode") or "").classes("w-full")
                description = ui.textarea(
                    "Descriere",
                    value=proposal.get("proposedDescription") or "",
                ).props("autogrow").classes("w-full")
                deadline = ui.input(
                    "Termen (YYYY-MM-DD, opțional)",
                    value=proposal.get("proposedDeadline") or "",
                ).classes("w-full")
                comment = ui.textarea("Motivul corecției").props("autogrow").classes("w-full")

                async def save() -> None:
                    if (
                        not str(code.value or "").strip()
                        or not str(description.value or "").strip()
                    ):
                        ui.notify("Codul și descrierea sunt obligatorii.", type="warning")
                        return
                    if not str(comment.value or "").strip():
                        ui.notify("Adaugă motivul corecției.", type="warning")
                        return
                    raw_deadline = str(deadline.value or "").strip()
                    if raw_deadline:
                        try:
                            date.fromisoformat(raw_deadline)
                        except ValueError:
                            ui.notify("Termenul trebuie să fie YYYY-MM-DD.", type="warning")
                            return
                    correction = {
                        "code": str(code.value).strip(),
                        "description": str(description.value).strip(),
                        "deadline": raw_deadline or None,
                        "sourceAnchors": proposal.get("sourceAnchors") or [],
                    }
                    dialog.close()
                    await review_one(
                        proposal,
                        action="correct",
                        correction=correction,
                        comment=str(comment.value).strip(),
                    )

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Anulează", on_click=dialog.close).props(
                        "flat rounded no-caps text-color=grey-8 size=sm"
                    ).classes("hover:bg-gray-100 font-bold")
                    ui.button("Salvează corecția", on_click=save).props(
                        "push rounded size=sm color=primary no-caps"
                    ).classes(
                        "px-4 py-1 text-gray-900 font-bold shadow-md hover:scale-105 "
                        "transition-transform duration-200"
                    )
            dialog.open()

        def reject_dialog(proposal: dict[str, Any]) -> None:
            with ui.dialog() as dialog, ui.card().classes("w-full max-w-xl"):
                ui.label("Respinge propunerea").classes("text-xl font-extrabold")
                comment = ui.textarea("Motivul respingerii").props("autogrow").classes("w-full")

                async def reject() -> None:
                    value = str(comment.value or "").strip()
                    if not value:
                        ui.notify("Motivul respingerii este obligatoriu.", type="warning")
                        return
                    dialog.close()
                    await review_one(proposal, action="reject", comment=value)

                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Anulează", on_click=dialog.close).props(
                        "flat rounded no-caps text-color=grey-8 size=sm"
                    ).classes("hover:bg-gray-100 font-bold")
                    ui.button("Respinge", on_click=reject).props(
                        "push rounded size=sm color=negative no-caps"
                    ).classes(
                        "px-4 py-1 font-bold shadow-md hover:scale-105 "
                        "transition-transform duration-200"
                    )
            dialog.open()

        @ui.refreshable
        async def proposals_view() -> None:
            proposals_container.clear()
            with proposals_container:
                try:
                    proposals = await load_proposals()
                    documents = await load_documents()
                except Exception as error:
                    ui.label(api_error_message(error)).classes("text-red-700")
                    return

                unreviewed = [
                    p for p in proposals 
                    if p.get("review") is None and p.get("sourceAnchors")
                ]
                ui.label(
                    f"Propuneri AI: {len(proposals)} · de verificat: {len(unreviewed)}"
                ).classes("text-xl font-extrabold text-gray-800")

                if not unreviewed:
                    pending_jobs = getattr(app, "pending_extraction_jobs", {})
                    if pending_jobs.pop(project_id, None) is not None:
                        app.pending_extraction_jobs = pending_jobs

                if not proposals:
                    ui.label(
                        "Extragerea s-a terminat, dar AI-ul nu a găsit obligații susținute de "
                        "pasaje exacte în documentele selectate."
                    ).classes("text-orange-700")
                    return

                async def accept_all() -> None:
                    current = [
                        item for item in proposals 
                        if item.get("review") is None and item.get("sourceAnchors")
                    ]
                    if not current:
                        return
                    reviews = [
                        {
                            "proposalId": item["id"],
                            "proposalRevision": item["revision"],
                            "action": "accept",
                        }
                        for item in current
                    ]
                    payload = {"reviews": reviews}
                    fingerprint = json_fingerprint(payload)
                    operation = f"criterion-review-all:{job_id}"
                    key = key_manager.key_for(operation, fingerprint)
                    try:
                        await api_client.review_criterion_proposals(
                            job_id,
                            reviews=reviews,
                            idempotency_key=key,
                        )
                    except Exception as error:
                        ui.notify(api_error_message(error), type="negative", timeout=10000)
                        return
                    key_manager.mark_succeeded(operation, fingerprint)
                    ui.notify(f"Au fost confirmate {len(current)} obligații.", type="positive")
                    await proposals_view.refresh()
                    await criteria_view.refresh()

                if unreviewed:
                    ui.button(
                        f"Confirmă toate ({len(unreviewed)})",
                        icon="done_all",
                        on_click=accept_all,
                    ).props("push rounded size=md color=primary no-caps").classes(
                        "px-4 py-2 text-sm font-extrabold shadow-lg hover:scale-105 "
                        "transition-transform duration-200 text-gray-900 self-start"
                    )


                for proposal in proposals:
                    review = proposal.get("review")
                    with ui.card().classes(
                        "w-full shadow-md rounded-xl border border-yellow-100"
                    ):
                        with ui.row().classes("w-full items-start justify-between gap-3"):
                            with ui.column().classes("gap-1 flex-grow"):
                                ui.label(_clean(proposal.get("proposedDescription"))).classes(
                                    "text-gray-800 text-lg font-medium"
                                )
                                ui.label(
                                    f"Termen: {_deadline_text(proposal.get('proposedDeadline'))}"
                                ).classes("text-sm text-gray-600")
                            if review:
                                ui.badge(f"Revizuit: {review.get('action')}").props("outline")

                        anchors = proposal.get("sourceAnchors") or []
                        if anchors:
                            ui.separator().classes("my-2 opacity-50")
                            for anchor in anchors:
                                page_number = anchor.get("pageNumber", "?")
                                doc_id = anchor.get("documentId")
                                doc_name = "document.pdf"
                                if doc_id:
                                    for d in documents:
                                        if d.get("id") == doc_id:
                                            doc_name = d.get("originalFilename") or "document.pdf"
                                            break

                                with ui.expansion(
                                    f"{doc_name} · pagina {page_number}",
                                    icon="article",
                                ).classes("w-full bg-gray-50 rounded-md border border-gray-100"):
                                    if doc_id:
                                        ui.button(
                                            f"Deschide documentul",
                                            on_click=lambda did=doc_id, name=doc_name: open_document(
                                                did, name
                                            ),
                                        ).props(
                                            "flat no-caps dense color=primary"
                                        ).classes("text-sm mb-2 self-start px-0")
                                    ui.label(
                                        " ".join(str(anchor.get("passage", "")).split())
                                    ).classes("whitespace-normal text-gray-700")
                        else:
                            ui.label("Fără pasaj sursă — nu poate fi confirmată.").classes(
                                "text-red-700"
                            )
    

                        if review is None and anchors:
                            with ui.row().classes("gap-2 mt-2"):
                                ui.button(
                                    "Confirmă",
                                    icon="check",
                                    on_click=lambda p=proposal: review_one(p, action="accept"),
                                ).props("push rounded size=sm color=primary no-caps").classes(
                                    "font-extrabold shadow-sm hover:scale-105 text-gray-900 "
                                    "transition-transform duration-200 px-3"
                                )
                                ui.button(
                                    "Corectează",
                                    icon="edit",
                                    on_click=lambda p=proposal: correction_dialog(p),
                                ).props("outline rounded size=sm no-caps").classes(
                                    "font-bold text-gray-800 hover:bg-gray-50 px-3"
                                )
                                ui.button(
                                    "Respinge",
                                    icon="close",
                                    on_click=lambda p=proposal: reject_dialog(p),
                                ).props("flat rounded size=sm color=negative no-caps").classes(
                                    "font-bold hover:bg-red-50 px-3"
                                )

        async def poll_job_after_connect() -> None:
            """Poll after the initial page has already been sent to the browser."""

            job: dict[str, Any] | None = None
            try:
                for _ in range(180):  # up to ~6 minutes
                    job = await api_client.get_analysis_job(job_id)
                    status = str(job.get("status", ""))
                    if status in TERMINAL_JOB_STATUSES:
                        break
                    status_label.text = f"Extragere în curs: {status}..."
                    await asyncio.sleep(2)
            except Exception as error:
                spinner.set_visibility(False)
                status_label.text = "Nu am putut citi starea extracției."
                ui.notify(api_error_message(error), type="negative", timeout=10000)
                return

            if job is None or str(job.get("status")) not in TERMINAL_JOB_STATUSES:
                spinner.set_visibility(False)
                status_label.text = (
                    "Extragerea durează mai mult decât intervalul de așteptare."
                )
                ui.button(
                    "Reîncarcă pagina",
                    on_click=lambda: ui.navigate.to(
                        f"/project/{project_id}/criteria-review/{job_id}"
                    ),
                ).props("push rounded size=md color=primary no-caps").classes(
                    "px-4 py-2 text-sm font-extrabold shadow-lg hover:scale-105 "
                    "transition-transform duration-200 text-gray-900"
                )
                return

            spinner.set_visibility(False)
            status = str(job.get("status"))
            if status != "succeeded":
                error = job.get("error") or {}
                status_label.text = (
                    "Extragerea a eșuat: "
                    + _clean(error.get("message") or status)
                )
                status_label.classes(replace="font-bold text-red-700")
                return

            status_label.text = (
                f"Extragere finalizată · {job.get('proposalCount', 0)} propuneri găsite"
            )
            status_label.classes(replace="font-bold text-green-700")
            await criteria_view()
            await proposals_view()

        # This is the NiceGUI-supported pattern for long-running page setup:
        # everything built above is sent immediately as the initial HTTP response;
        # only after the browser/websocket is connected do we start polling.
        #
        # Using ui.timer here looked asynchronous, but on some NiceGUI versions
        # the timer could still participate in page setup and hit the default
        # 3-second response_timeout. Explicitly awaiting connected() is the
        # documented lifecycle boundary.
        await ui.context.client.connected(timeout=10.0)
        await poll_job_after_connect()
