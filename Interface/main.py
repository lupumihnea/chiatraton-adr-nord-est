import os
from nicegui import app, ui
import add_project
import project_details
import upload_documents

# Includem un font prietenos ("Quicksand") și stilizăm fundalul
ui.add_head_html('''
    <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@500;700;800&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Quicksand', sans-serif;
            background-color: #fffdf5; /* un alb-gălbui cald */
        }
    </style>
''', shared=True)

assets_dir = os.path.join(os.path.dirname(__file__), 'Assets')
app.add_static_files('/Assets', assets_dir)

@ui.page('/')
def home():
    # Setăm nuanțele noastre calde
    ui.colors(primary='#ffcc00', accent='#ffcc00')

    # Container principal aerisit
    with ui.column().classes('w-full items-center mt-8 space-y-6 min-h-[85vh]'):
        
        # Logo cu un efect subtil de creștere când treci cu mouse-ul
        ui.image('/Assets/Logo-ADR.png') \
            .classes('w-64 transition-transform hover:scale-105 duration-300 drop-shadow-sm')

        # Mesajul de chat reinterpretat sub forma unui "card" prietenos
        with ui.row().classes('items-center bg-white px-4 py-2 rounded-full shadow-md border-2 border-yellow-200 mb-2 hover:-translate-y-1 transition-transform'):
            ui.image('/Assets/ADRut.png').classes('w-12 h-12 rounded-full bg-yellow-50 p-1')
            ui.label("Haide să începem analiza!").classes('text-lg font-extrabold text-gray-700 mx-3')

        # Containerul de Search mult mai "bubbly"
        with ui.column().classes('w-full max-w-xl items-start space-y-4'):
            
            # Bară de căutare rotunjită complet (rounded-full) și text centrat
            search_bar = ui.input(placeholder='Introdu codul SMIS...') \
                .props('rounded outlined clearable mask="######" input-class="text-2xl font-bold text-center"') \
                .classes('w-full text-2xl bg-white shadow-xl rounded-full border-0')
            
            # Butonul de adăugare ca un "pill" (capsulă) cu iconiță
            add_button = ui.button('Adaugă un nou proiect', icon='add', on_click=lambda: ui.navigate.to('/add_project')) \
                .props('flat rounded no-caps size="md"') \
                .classes('text-yellow-600 font-bold bg-yellow-50 hover:bg-yellow-100 transition-colors rounded-full px-4 py-1 text-sm')

        #aici e end-point pentru verificare dacă există proiectul cu codul respectiv în aplicație
        def access_project():
            code = search_bar.value
            if not code or len(code) != 6:
                ui.notify('Cod invalid', type='warning')
                return
                
            # Bază de date simulată (mock) pentru showcase
            mock_db = ['123456', '111111', '999999']
            #TO DO: verificarea reală în bază dacă există
            exists = code in mock_db

            if exists:
                ui.navigate.to(f'/project/{code}')
            else:
                ui.notify(f'Proiectul cu codul SMIS {code} nu a fost găsit în baza de date.', type='negative')

        # Buton de access jucăuș cu proprietatea "push" din Quasar (aspect 3D)
        access_button = ui.button('Accesează', on_click=access_project) \
            .props('push rounded size="xl" color="primary"') \
            .classes('w-64 py-4 mt-4 text-2xl font-extrabold shadow-xl hover:scale-105 transition-transform duration-200 text-gray-900')

        ui.space()


ui.run(title="ADR Analizator")

