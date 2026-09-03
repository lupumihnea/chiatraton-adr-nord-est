from nicegui import ui

@ui.page('/add_project')
def add_project_page():
    # Setăm paleta de culori (quirky)
    ui.colors(primary='#ffcc00', accent='#ffcc00')
    
    # Container principal aerisit, aliniat central
    with ui.column().classes('w-full items-center mt-6 mb-6 min-h-[85vh]'):
        
        # Titlu prietenos
        with ui.row().classes('items-center mb-4 gap-3'):
            ui.icon('post_add', size='md').classes('text-yellow-600')
            ui.label('Adaugă un nou proiect').classes('text-2xl font-extrabold text-gray-800')

        # Formular principal (card rotunjit cu umbră)
        with ui.column().classes('w-full max-w-3xl bg-white shadow-2xl rounded-[2rem] p-6 space-y-3 border border-yellow-100'):
            
            # Cod SMIS
            with ui.column().classes('w-full space-y-1'):
                ui.label('Cod SMIS (6 cifre)').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2')
                project_code = ui.input(
                                        validation={'Trebuie exact 6 cifre': lambda v: len(v) == 6 if v else False}) \
                    .props('rounded outlined clearable hide-bottom-space mask="######" input-class="text-lg font-bold tracking-widest"') \
                    .classes('w-full text-lg bg-gray-50 rounded-xl')

            # Identificator al apelului
            with ui.column().classes('w-full space-y-1'):
                ui.label('Identificator al apelului (obligatoriu)').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2')
                call_identifier = ui.input(
                                        validation={'Trebuie să fie un număr întreg': lambda v: v is not None and v.strip().isdigit()}) \
                    .props('rounded outlined clearable hide-bottom-space input-class="text-base font-bold"') \
                    .classes('w-full text-base bg-gray-50 rounded-xl')

            # Nume proiect
            with ui.column().classes('w-full space-y-1'):
                ui.label('Nume proiect (opțional)').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2')
                project_name = ui.input() \
                    .props('rounded outlined clearable hide-bottom-space input-class="text-base font-bold"') \
                    .classes('w-full text-base bg-gray-50 rounded-xl')

            # Nume beneficiar
            with ui.column().classes('w-full space-y-1'):
                ui.label('Nume beneficiar (opțional)').classes('text-xs font-extrabold text-gray-500 uppercase tracking-wide ml-2')
                beneficiary_name = ui.input() \
                    .props('rounded outlined clearable hide-bottom-space input-class="text-base font-bold"') \
                    .classes('w-full text-base bg-gray-50 rounded-xl')

            ui.separator().classes('my-2 opacity-50')



            # Acțiuni finale (Înapoi și Salvare)
            with ui.row().classes('w-full items-center justify-between mt-2 pt-0'):
                ui.button('Înapoi la start', icon='arrow_back', on_click=lambda: ui.navigate.to('/')) \
                    .props('flat rounded no-caps text-gray-500 size="md"') \
                    .classes('hover:bg-gray-100 px-4 py-2 rounded-full font-bold')

                async def save_project():
                    if not project_code.value or len(project_code.value) != 6:
                        ui.notify('Te rugăm să completezi un cod SMIS valid de 6 cifre înainte de a salva.',
                                  type='negative', position='top', classes='font-bold')
                        return
                    
                    if call_identifier.value is None or not str(call_identifier.value).strip().isdigit():
                        ui.notify('Te rugăm să introduci un identificator de apel valid (număr întreg).',
                                  type='negative', position='top', classes='font-bold')
                        return
                    
                    # -------------------------------------------------------------------------
                    # TODO: [INTEGRARE BACKEND FastAPI]
                    # Aici se extrag datele introduse pentru a fi trimise la API.
                    # Colegul tău poate folosi httpx pentru a apela endpoint-ul de FastAPI.
                    # -------------------------------------------------------------------------
                    try:
                        # 1. Datele proiectului
                        smis_code = project_code.value
                        identifier = int(call_identifier.value)
                        p_name = project_name.value if project_name.value else ""
                        b_name = beneficiary_name.value if beneficiary_name.value else ""
                            
                        # --- EXEMPLU DE APEL HTTP CĂTRE FASTAPI ---
                        # import httpx
                        # async with httpx.AsyncClient() as client:
                        #     response = await client.post(
                        #         'http://localhost:8000/api/projects',
                        #         json={
                        #             'smis_code': smis_code,
                        #             'call_identifier': identifier,
                        #             'project_name': p_name,
                        #             'beneficiary_name': b_name
                        #         }
                        #     )
                        #     response.raise_for_status()
                        
                        # După răspunsul cu succes de la backend, redirecționăm către pagina de succes:
                        ui.navigate.to(f'/success/{project_code.value}')
                    
                    except Exception as e:
                        # În cazul în care backend-ul returnează o eroare
                        ui.notify(f'Eroare la salvare: {str(e)}', type='negative', position='top')
                        ui.navigate.to(f'/error/{project_code.value}')

                ui.button('Salvează Proiectul', icon='check_circle', on_click=save_project) \
                    .props('push rounded size="md" color="primary"') \
                    .classes('px-6 py-2 text-base font-extrabold shadow-xl hover:scale-105 transition-transform duration-200 text-gray-900')

@ui.page('/success/{code}')
def success_page(code: str):
    ui.colors(primary='#ffcc00', accent='#ffcc00')
    
    with ui.column().classes('w-full items-center justify-center min-h-[85vh] p-4'):
        # Cardul de succes mai mic (max-w-lg, p-8)
        with ui.column().classes('items-center bg-white shadow-2xl rounded-[2rem] p-8 border border-yellow-100 transform transition-transform hover:scale-105 duration-300 text-center max-w-lg'):
            
            # Iconiță mare de succes (păstrată la fel)
            ui.icon('check_circle', size='120px').classes('text-green-500 mb-6 drop-shadow-md')
            
            # Textul Gata (păstrat la fel)
            ui.label('Gata!').classes('text-5xl font-extrabold text-gray-800 mb-4')
            
            # Text descriptiv (micșorat)
            with ui.row().classes('items-center justify-center gap-1 flex-wrap'):
                ui.label('Proiectul cu codul SMIS').classes('text-lg text-gray-600 font-medium')
                ui.label(code).classes('text-xl font-extrabold text-yellow-600 bg-yellow-50 px-3 py-1 rounded-xl shadow-inner border border-yellow-200 mx-1')
                ui.label('a fost adăugat cu succes.').classes('text-lg text-gray-600 font-medium')

            # Redirectare automată după 2.5 secunde către main
            ui.timer(2.5, lambda: ui.navigate.to('/'), once=True)


@ui.page('/error/{code}')
def error_page(code: str):
    ui.colors(primary='#ffcc00', accent='#ffcc00')
    
    with ui.column().classes('w-full items-center justify-center min-h-[85vh] p-4'):
        # Cardul de eroare similar ca structură, dar pe roșu
        with ui.column().classes('items-center bg-white shadow-2xl rounded-[2rem] p-8 border border-red-100 transform transition-transform hover:scale-105 duration-300 text-center max-w-lg'):
            
            ui.icon('error', size='120px').classes('text-red-500 mb-6 drop-shadow-md')
            
            ui.label('Eroare!').classes('text-5xl font-extrabold text-gray-800 mb-4')
            
            with ui.row().classes('items-center justify-center gap-1 flex-wrap'):
                ui.label('A apărut o problemă la adăugarea proiectului').classes('text-lg text-gray-600 font-medium')
                ui.label(code).classes('text-xl font-extrabold text-red-600 bg-red-50 px-3 py-1 rounded-xl shadow-inner border border-red-200 mx-1')
                
            # Redirectare automată după 5 secunde înapoi la add_project pentru a reîncerca
            ui.timer(5.0, lambda: ui.navigate.to('/add_project'), once=True)