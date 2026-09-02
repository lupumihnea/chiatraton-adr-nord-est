from nicegui import ui

@ui.page('/add_project')
def add_project_page():
    with ui.column().classes('w-full items-center mt-8 space-y-8 min-h-[75vh]'):
        ui.label('Adaugă un nou proiect').classes('text-3xl font-bold')

        with ui.column().classes('w-full max-w-2xl space-y-4'):
            project_code = ui.input('Codul proiectului').props('outlined').classes('w-full')

            ui.label('Fișiere obligatorii').classes('text-xl font-semibold mt-4')
            
            with ui.row().classes('w-full items-center gap-4'):
                ui.label('Ghid al apelului:').classes('w-1/3')
                ui.upload(label='Încărcați Ghid al apelului (PDF)', multiple=False, auto_upload=True).props('accept=".pdf"').classes('flex-grow')

            with ui.row().classes('w-full items-center gap-4'):
                ui.label('Contract de finanțare:').classes('w-1/3')
                ui.upload(label='Încărcați Contract de finanțare (PDF)', multiple=False, auto_upload=True).props('accept=".pdf"').classes('flex-grow')

            ui.label('Alte fișiere PDF').classes('text-xl font-semibold mt-4')
            
            uploads_container = ui.column().classes('w-full space-y-4')
            
            def add_upload():
                with uploads_container:
                    row = ui.row().classes('w-full items-center gap-4')
                    with row:
                        file_type = ui.input('Nume/Tip fișier').props('outlined').classes('w-1/3')
                        upload = ui.upload(label='Încărcați fișier (PDF)', multiple=False, auto_upload=True).props('accept=".pdf"').classes('flex-grow')
                        ui.button(icon='delete', on_click=lambda r=row: r.delete()).props('flat color="negative"')

            ui.button('Adaugă fișier suplimentar', icon='add', on_click=add_upload).props('flat')

            ui.button('Salvează Proiect', color='primary', on_click=lambda: ui.notify('Proiect salvat!')).classes('w-full mt-8')
            
            ui.button('Înapoi', on_click=lambda: ui.navigate.to('/')).props('flat').classes('w-full mt-2')
