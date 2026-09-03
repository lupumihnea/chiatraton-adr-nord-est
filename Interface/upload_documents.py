from nicegui import ui

@ui.page('/upload/{code}')
def upload_documents_page(code: str):
    ui.colors(primary='#ffcc00', accent='#ffcc00')
    
    # Stocăm datele într-o listă de dicționare, fiecare dict reprezentând un rând (categorie + fișiere)
    upload_state = []
    
    options = {
        'apel': 'Documente legate de apel',
        'initiale': 'Documente inițiale',
        'rapoarte': 'Rapoarte de progres',
        'altele': 'Alte documente'
    }
    
    with ui.column().classes('w-full items-center min-h-[85vh] bg-gray-50/30 p-4'):
        
        # Buton înapoi
        with ui.row().classes('w-full max-w-4xl mb-4'):
            ui.button('Înapoi la proiect', icon='arrow_back', on_click=lambda: ui.navigate.to(f'/project/{code}')) \
                .props('flat rounded no-caps size="md" text-color="grey-8"') \
                .classes('hover:bg-gray-100 px-4 py-2 rounded-full font-bold')
        
        with ui.column().classes('w-full max-w-4xl bg-white shadow-2xl rounded-[2rem] p-6 space-y-4 border border-yellow-100'):
            
            with ui.row().classes('items-center gap-3 mb-2'):
                ui.icon('cloud_upload', size='md').classes('text-yellow-600')
                ui.label(f'Încărcare documente - Proiect {code}').classes('text-2xl font-extrabold text-gray-800')

            ui.separator().classes('opacity-50')

            # Containerul unde vor fi adăugate rândurile dinamice
            uploads_container = ui.column().classes('w-full space-y-4')

            def add_upload_row():
                # Legăm starea acestui rând
                row_data = {'category': 'altele', 'events': []}
                upload_state.append(row_data)
                
                with uploads_container:
                    row = ui.row().classes('w-full items-center bg-gray-50 p-4 rounded-xl border border-gray-200 shadow-sm transition-all gap-4 flex-nowrap')
                    with row:
                        # Dropdown-ul pentru categoria documentului
                        category_select = ui.select(options, value='altele', on_change=lambda e: row_data.update({'category': e.value})) \
                            .props('outlined rounded bg-white hide-bottom-space') \
                            .classes('w-1/3 min-w-[200px]')
                        
                        # Zona centrală care va găzdui fie boxa de upload, fie mesajul de succes
                        middle_container = ui.row().classes('flex-grow items-center')
                        
                        with middle_container:
                            async def on_file_uploaded(e):
                                category = row_data['category']
                                row_data['events'].append(e)
                                
                                # După selectare, ascundem componenta de upload și blocăm dropdown-ul
                                upload_component.set_visibility(False)
                                category_select.disable()
                                
                                # Adăugăm un feedback vizual tip "fișier atașat"
                                with middle_container:
                                    with ui.row().classes('w-full bg-green-50 border border-green-200 p-3 rounded-xl items-center justify-between shadow-inner'):
                                        with ui.row().classes('items-center gap-2'):
                                            ui.icon('picture_as_pdf', size='sm').classes('text-red-500')
                                            ui.label(e.file.name).classes('text-base font-extrabold text-green-900')
                                        
                                        with ui.row().classes('items-center gap-1'):
                                            ui.icon('check_circle', size='sm').classes('text-green-600')
                                            ui.label('Pregătit').classes('text-xs font-bold text-green-700 uppercase tracking-wide')
                                
                                ui.notify('Fișier atașat local cu succes!', type='info', position='top')

                            # Componenta de upload (restricționată la 1 fișier PDF, max 25MB)
                            upload_component = ui.upload(multiple=False, auto_upload=True, on_upload=on_file_uploaded, max_file_size=26214400, on_rejected=lambda: ui.notify('Te rugăm să alegi un singur fișier PDF de maxim 25MB!', type='negative', position='top', classes='font-bold')) \
                                .props('accept=".pdf" max-files="1" label="Trage fișierul PDF aici" flat bordered color="white" text-color="grey-9" hide-upload-btn') \
                                .classes('w-full shadow-sm bg-white')
                        
                        # Ștergerea rândului
                        def delete_row():
                            upload_state.remove(row_data)
                            row.delete()
                            
                        ui.button(icon='delete', on_click=delete_row) \
                            .props('flat round color="negative" size="md"') \
                            .classes('bg-red-50 hover:bg-red-100 transition-colors')

            # Adăugăm primul rând by default
            add_upload_row()
            
            # Butonul pentru a adăuga mai multe rânduri
            ui.button('+ Adaugă altă categorie de document', on_click=add_upload_row) \
                .props('flat rounded no-caps size="md"') \
                .classes('text-yellow-700 font-bold bg-yellow-50 hover:bg-yellow-100 transition-colors rounded-full px-6 py-2 mt-2 self-start')

            ui.separator().classes('my-2 opacity-50')
            
            # Acțiuni finale (Trimitere spre analiză în bloc)
            with ui.row().classes('w-full justify-end mt-2 pt-2'):
                async def submit_documents():
                    # -------------------------------------------------------------------------
                    # TODO: [INTEGRARE BACKEND FastAPI]
                    # Parcurge lista `upload_state`.
                    # Pentru fiecare `row` în `upload_state`:
                    #   categorie = row['category'] # (ex: 'apel', 'initiale' etc)
                    #   fisiere = row['events'] # (lista de obiecte `e`, unde e.file.read() are biții)
                    # -------------------------------------------------------------------------
                    
                    total_files = sum(len(row['events']) for row in upload_state)
                    if total_files == 0:
                        ui.notify('Nu ai selectat niciun document pentru trimitere.', type='warning', position='top')
                        return
                    
                    ui.notify(f'{total_files} document(e) au fost trimise spre analiză cu succes!', type='positive', position='top')
                    ui.navigate.to(f'/project/{code}')

                ui.button('Trimite documentele', icon='send', on_click=submit_documents) \
                    .props('push rounded size="md" color="primary"') \
                    .classes('px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 transition-transform duration-200 text-gray-900')
