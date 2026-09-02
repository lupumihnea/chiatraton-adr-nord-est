from nicegui import ui
import add_project

@ui.page('/')
def home():
    # Setăm înălțimea minimă la 75vh pentru a aduce butonul mai sus
    with ui.column().classes('w-full items-center mt-16 space-y-8 min-h-[75vh]'):

        # Logo mai mare (w-64 = 256px)
        ui.image('Assets/Logo-ADR.png').classes('w-64')

        # Container pentru bara de căutare (mai lat: max-w-xl)
        with ui.column().classes('w-full max-w-xl items-start space-y-2'):
            
            # Search Bar mai mare (text-lg)
            search_bar = ui.input(placeholder='Caută proiectul pe care dorești să îl monitorizezi') \
                .props('rounded outlined clearable input-class="text-lg"') \
                .classes('w-full text-lg')
                
            # Add New Project Button mai mare (size="lg")
            add_button = ui.button('Adaugă un nou proiect', icon='add', on_click=lambda: ui.navigate.to('/add_project')) \
                .props('flat no-caps size="lg"') \
                .classes('p-0 text-blue-600')

        # ui.space() ocupă tot spațiul liber rămas, împingând elementele de mai jos spre finalul paginii
        ui.space()



        # Access Button la baza paginii, dar mutat mai sus prin reducerea înălțimii minime și creșterea marginii de jos (mb-16)
        access_button = ui.button('Accesează', color='primary', on_click=lambda: ui.notify('Se accesează proiectul...')) \
            .props('size="lg"') \
            .classes('w-full max-w-md py-3 mb-16 text-xl font-bold')


ui.run()
