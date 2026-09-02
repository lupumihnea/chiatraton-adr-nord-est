from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nicegui import ui
from API.monitoring_api import MonitoringAPI

api = MonitoringAPI()


@ui.page('/add_project')
def add_project_page():
    with ui.column().classes('w-full max-w-3xl mx-auto mt-8 gap-5 p-6'):
        ui.label('Adaugă / actualizează proiect').classes('text-3xl font-bold')
        project_code = ui.number('Codul proiectului (6 cifre)', min=100000, max=999999).classes('w-full')
        call_id = ui.number('Call ID').classes('w-full')
        time_ending = ui.input('Data finalizării', placeholder='2025-07-23').classes('w-full')
        name = ui.input('Nume proiect').classes('w-full')

        def save_project():
            try:
                api.upsert_project(
                    project_id=int(project_code.value),
                    call_id=int(call_id.value) if call_id.value is not None else None,
                    time_ending=time_ending.value or None,
                    name=name.value or None,
                )
                ui.notify('Proiect salvat.', type='positive')
                ui.navigate.to(f'/project/{int(project_code.value)}')
            except Exception as exc:
                ui.notify(str(exc), type='negative')

        ui.button('Salvează proiect', on_click=save_project).classes('w-full').props('no-caps')
        ui.button('Înapoi', on_click=lambda: ui.navigate.to('/')).props('flat no-caps').classes('w-full')
