from nicegui import ui


@ui.page('/add_project')
def add_project_page():
    ui.colors(primary='#fcc300', accent='#fcc300')
    with ui.column().classes('w-full items-center mt-8 space-y-8 min-h-[75vh]'):
        ui.label('Adaugă un nou proiect').classes('text-3xl font-bold')

        with ui.column().classes('w-full max-w-2xl space-y-4'):
            project_code = ui.input('Codul SMIS al proiectului',
                                    validation={'Sunt necesare 6 cifre': lambda v: len(v) == 6 if v else False}) \
                .props('outlined mask="######"').classes('w-full')

            ui.label('Fișiere obligatorii (format .PDF)').classes('text-xl font-semibold mt-4')

            with ui.row().classes('w-full items-center gap-4'):
                ui.label('Ghidul apelului(anexele se atașează la alte documente):').classes('w-1/3')
                ui.upload(multiple=False, auto_upload=True).props('accept=".pdf"').classes('flex-grow')

            with ui.row().classes('w-full items-center gap-4'):
                ui.label('Contractul de finanțare:').classes('w-1/3')
                ui.upload(multiple=False, auto_upload=True).props('accept=".pdf"').classes('flex-grow')

            ui.label('Alte fișiere PDF').classes('text-xl font-semibold mt-4')

            uploads_container = ui.column().classes('w-full space-y-4')

            def add_upload():
                with uploads_container:
                    row = ui.row().classes('w-full items-center gap-4')
                    with row:
                        file_type = ui.input('Nume/Tip fișier').props('outlined').classes('w-1/3')
                        upload = ui.upload(multiple=False, auto_upload=True).props('accept=".pdf"').classes('flex-grow')
                        ui.button(icon='delete', on_click=lambda r=row: r.delete()).props('flat color="negative"')

            ui.button('Adaugă fișier suplimentar', icon='add', on_click=add_upload).props('flat')

            def save_project():
                if not project_code.value or len(project_code.value) != 6:
                    ui.notify('Te rugăm să completezi un cod SMIS valid de 6 cifre înainte de a salva.',
                              type='negative')
                    return
                ui.notify('Proiect salvat cu succes!', type='positive')

            ui.button('Salvează Proiect', color='primary', on_click=save_project).classes('w-full mt-8')

            ui.button('Înapoi', on_click=lambda: ui.navigate.to('/')).props('flat').classes('w-full mt-2')