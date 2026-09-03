"""Progress-report analysis page.

The public API still uses Criterion/CriterionValidation internally.  The UI presents
those domain objects as project obligations and progress against obligations.
"""

from __future__ import annotations

import asyncio
from typing import Any

from nicegui import ui

from Interface.api_client import api_client, api_error_message

TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled"}
OUTCOME_LABELS = {
    "compliant": "Îndeplinită",
    "partially_compliant": "Parțial îndeplinită",
    "non_compliant": "Neîndeplinită / neconformă",
    "insufficient_evidence": "Dovezi insuficiente",
    "not_applicable": "Neaplicabilă perioadei",
}
OUTCOME_CLASSES = {
    "compliant": "text-green-700",
    "partially_compliant": "text-orange-700",
    "non_compliant": "text-red-700",
    "insufficient_evidence": "text-gray-700",
    "not_applicable": "text-blue-700",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


@ui.page("/project/{project_id}/report-analysis/{report_id}/{job_id}")
async def report_analysis_page(project_id: str, report_id: str, job_id: str) -> None:
    ui.colors(primary="#ffcc00", accent="#ffcc00")

    with ui.column().classes("w-full items-center min-h-[85vh] bg-gray-50/30 p-4 gap-4"):
        with ui.row().classes("w-full max-w-6xl"):
            ui.button(
                "Înapoi la proiect",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(f"/project/{project_id}"),
            ).props("flat rounded no-caps size=md text-color=grey-8").classes(
                "hover:bg-gray-100 px-4 py-2 rounded-full font-bold"
            )

        with ui.column().classes(
            "w-full max-w-6xl bg-white shadow-xl rounded-[1.5rem] p-6 "
            "border border-yellow-100 gap-3"
        ):
            with ui.row().classes("items-center gap-2"):
                ui.icon("timeline", size="sm").classes("text-yellow-600")
                ui.label("Progres raportat față de obligațiile proiectului").classes(
                    "text-2xl font-extrabold text-gray-800"
                )

            ui.label(
                "Raportul de progres nu creează obligații noi. AI-ul verifică doar starea "
                "obligațiilor deja confirmate și citează pasajele folosite ca dovezi."
            ).classes("text-gray-600")

            ui.separator().classes("opacity-50")

            with ui.row().classes("items-center gap-2") as status_row:
                spinner = ui.spinner(size="sm")
                status_label = ui.label("Se pregătește analiza...").classes(
                    "font-bold text-gray-700"
                )

        results_container = ui.column().classes("w-full max-w-6xl gap-3")

        async def render_results() -> None:
            results_container.clear()
            try:
                criteria = await api_client.list_all_project_criteria(project_id)
                validations = await api_client.list_all_report_validations(report_id)
            except Exception as error:
                with results_container:
                    ui.label(api_error_message(error)).classes("text-red-700 font-bold")
                return

            criterion_by_id = {
                str(item.get("id")): item
                for item in criteria
                if isinstance(item, dict) and item.get("id")
            }

            with results_container:
                if not validations:
                    ui.label(
                        "Analiza s-a încheiat, dar nu există încă rezultate de progres."
                    ).classes("text-gray-600")
                    return

                ui.label(f"{len(validations)} obligații verificate").classes(
                    "text-xl font-extrabold text-gray-800"
                )

                for validation in validations:
                    criterion = criterion_by_id.get(str(validation.get("criterionId")), {})
                    outcome = str(validation.get("aiOutcome", ""))
                    outcome_text = OUTCOME_LABELS.get(outcome, outcome or "Necunoscut")
                    outcome_class = OUTCOME_CLASSES.get(outcome, "text-gray-700")

                    with ui.card().classes(
                        "w-full shadow-sm rounded-xl border border-yellow-100"
                    ):
                        ui.label(_clean(criterion.get("code")) or "Obligație").classes(
                            "font-extrabold text-gray-800"
                        )
                        ui.label(_clean(criterion.get("description"))).classes(
                            "text-gray-800"
                        )
                        deadline = criterion.get("deadline") or "Fără termen explicit"
                        ui.label(f"Termen obligație: {deadline}").classes(
                            "text-sm text-gray-600"
                        )

                        ui.separator().classes("my-2 opacity-50")
                        ui.label(f"Status în raport: {outcome_text}").classes(
                            f"font-extrabold {outcome_class}"
                        )
                        ui.label(_clean(validation.get("aiRationale"))).classes(
                            "text-gray-700"
                        )

                        anchors = validation.get("sourceAnchors") or []
                        if anchors:
                            ui.label("Dovezi din raport").classes("font-bold mt-2")
                            for index, anchor in enumerate(anchors, start=1):
                                with ui.expansion(
                                    f"Pasaj {index} · pagina {anchor.get('pageNumber', '?')}",
                                    icon="article",
                                ).classes("w-full"):
                                    ui.label(_clean(anchor.get("passage"))).classes(
                                        "whitespace-normal text-gray-800"
                                    )
                        elif outcome == "insufficient_evidence":
                            ui.label(
                                "Raportul nu conține suficiente dovezi pentru o "
                                "concluzie factuală."
                            ).classes("text-gray-600 italic")

        async def load_after_connect() -> None:
            if job_id != "results":
                job: dict[str, Any] | None = None
                try:
                    for _ in range(180):  # up to ~6 minutes
                        job = await api_client.get_analysis_job(job_id)
                        status = str(job.get("status", ""))
                        if status in TERMINAL_JOB_STATUSES:
                            break
                        status_label.text = f"Analiză progres în curs: {status}..."
                        await asyncio.sleep(2)
                except Exception as error:
                    spinner.set_visibility(False)
                    status_label.text = "Nu am putut citi starea analizei."
                    ui.notify(api_error_message(error), type="negative", timeout=10000)
                    return

                if job is None or str(job.get("status")) not in TERMINAL_JOB_STATUSES:
                    spinner.set_visibility(False)
                    status_label.text = "Analiza durează mai mult decât intervalul de așteptare."
                    return

                if str(job.get("status")) != "succeeded":
                    spinner.set_visibility(False)
                    error = job.get("error") or {}
                    status_label.text = "Analiza a eșuat: " + _clean(
                        error.get("message") or job.get("status")
                    )
                    status_label.classes(replace="font-bold text-red-700")
                    return

            spinner.set_visibility(False)
            status_label.text = "Analiza progresului este finalizată."
            status_label.classes(replace="font-bold text-green-700")
            await render_results()

        await ui.context.client.connected(timeout=10.0)
        await load_after_connect()
