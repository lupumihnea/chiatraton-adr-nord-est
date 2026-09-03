from nicegui import ui

@ui.page('/project/{code}')
def project_details_page(code: str):
    # Păstrăm paleta de culori cu galben
    ui.colors(primary='#ffcc00', accent='#ffcc00')
    
    # Container principal aerisit
    with ui.column().classes('w-full items-center min-h-[85vh] bg-gray-50/30'):
        
        # Partea de sus: Butonul de Home (aliniat la stânga)
        with ui.row().classes('w-full max-w-6xl p-4'):
            ui.button('Înapoi la start', icon='home', on_click=lambda: ui.navigate.to('/')) \
                .props('flat rounded no-caps size="md" text-color="grey-8"') \
                .classes('hover:bg-gray-100 px-4 py-2 rounded-full font-bold')
                
        # Secțiunea principală împărțită 3/4 și 1/4
        with ui.row().classes('w-full max-w-6xl px-4 gap-6 flex-nowrap items-stretch'):
            
            # Partea stângă (3/4) - Detalii Proiect
            with ui.column().classes('w-3/4 bg-white shadow-xl rounded-[1.5rem] p-6 border border-yellow-100'):
                with ui.row().classes('items-center mb-2 gap-2'):
                    ui.icon('info', size='sm').classes('text-yellow-600')
                    ui.label('Detalii Proiect').classes('text-2xl font-extrabold text-gray-800')
                
                ui.separator().classes('mb-4 opacity-50')
                
                # Afișarea detaliilor într-un grid pentru a arăta aerisit
                with ui.grid(columns=2).classes('w-full gap-4'):
                    # Cod SMIS
                    with ui.column().classes('space-y-1'):
                        ui.label('Cod SMIS').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide')
                        ui.label(code).classes('text-lg font-bold text-gray-800 bg-gray-50 px-3 py-1 rounded-xl border border-gray-100 w-full')

                    # Identificator Apel (Mockup data)
                    with ui.column().classes('space-y-1'):
                        ui.label('Identificator Apel').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide')
                        ui.label('Se încarcă...').classes('text-base font-bold text-gray-600 bg-gray-50 px-3 py-1 rounded-xl border border-gray-100 w-full')

                    # Nume Proiect (Mockup data)
                    with ui.column().classes('space-y-1'):
                        ui.label('Nume Proiect').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide')
                        ui.label('Se încarcă...').classes('text-base font-bold text-gray-600 bg-gray-50 px-3 py-1 rounded-xl border border-gray-100 w-full')

                    # Nume Beneficiar (Mockup data)
                    with ui.column().classes('space-y-1'):
                        ui.label('Nume Beneficiar').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide')
                        ui.label('Se încarcă...').classes('text-base font-bold text-gray-600 bg-gray-50 px-3 py-1 rounded-xl border border-gray-100 w-full')

            # Partea dreaptă (1/4) - Buton Upload
            with ui.column().classes('w-1/4 items-center justify-center bg-yellow-50 shadow-xl rounded-[1.5rem] p-6 border-2 border-yellow-200 transition-all hover:bg-yellow-100/80'):
                ui.icon('cloud_upload', size='50px').classes('text-yellow-600 mb-4')
                
                # Navigare către viitoarea pagină de upload (de ex. /upload/123456)
                ui.button('Încarcă Documente', icon='upload_file', on_click=lambda: ui.navigate.to(f'/upload/{code}')) \
                    .props('push rounded size="md" color="primary"') \
                    .classes('px-4 py-2 text-sm font-extrabold shadow-lg hover:scale-105 transition-transform duration-200 text-gray-900 w-full')