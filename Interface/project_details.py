from nicegui import ui

@ui.page('/project/{code}')
def project_details_page(code: str):
    ui.colors(primary='#fcc300', accent='#fcc300')
    ui.label('Under construction')