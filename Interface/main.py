import os
from nicegui import app, ui
import add_project
import project_details

assets_dir = os.path.join(os.path.dirname(__file__), 'Assets')
app.add_static_files('/Assets', assets_dir)

@ui.page('/')
def home():
    ui.colors(primary='#fcc300', accent='#fcc300')
    # Setăm înălțimea minimă la 75vh pentru a aduce butonul mai sus
    with ui.column().classes('w-full items-center mt-16 space-y-8 min-h-[75vh]'):

        # Logo mai mare (w-64 = 256px)
        ui.image('Assets/Logo-ADR.png').classes('w-64')

        # Container pentru bara de căutare (mai lat: max-w-xl)
        with ui.column().classes('w-full max-w-xl items-start space-y-2'):
            
            # Search Bar mai mare (text-lg)
            search_bar = ui.input(placeholder='Caută proiectul pe care dorești să îl monitorizezi după codul SMIS') \
                .props('rounded outlined clearable mask="######" input-class="text-lg"') \
                .classes('w-full text-lg')
                
            # Add New Project Button mai mare (size="lg")
            add_button = ui.button('Adaugă un nou proiect', icon='add', on_click=lambda: ui.navigate.to('/add_project')) \
                .props('flat no-caps size="lg"') \
                .classes('p-0 text-primary')

        # ui.space() ocupă tot spațiul liber rămas, împingând elementele de mai jos spre finalul paginii
        ui.chat_message("Haide să începem munca!", name='ADRuț',avatar='/Assets/ADRut.png')
        ui.space()



        def access_project():
            code = search_bar.value
            if not code or len(code) != 6:
                ui.notify('Cod invalid', type='warning')
                return
                
            # Bază de date simulată (mock) pentru showcase
            mock_db = ['123456', '111111', '999999']

            exists = code in mock_db

            if exists:
                ui.navigate.to(f'/project/{code}')
            else:
                ui.notify(f'Proiectul cu codul SMIS {code} nu a fost găsit în baza de date.', type='negative')

        # Access Button la baza paginii, dar mutat mai sus prin reducerea înălțimii minime și creșterea marginii de jos (mb-16)
        access_button = ui.button('Accesează', color='primary', on_click=access_project) \
            .props('size="lg"') \
            .classes('w-64 py-3 mb-16 text-xl font-bold')


ui.run()
