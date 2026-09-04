# Context Interfață (UI Guidelines) - ChIAtraton

Acest document conține standardele, convențiile și regulile de design stabilite pentru interfața proiectului ChIAtraton. Orice modificare sau dezvoltare de noi componente UI trebuie să respecte aceste linii directoare pentru a menține un design unitar și o experiență de utilizare coerentă.

## 1. Tehnologie și Framework
- Interfața este dezvoltată exclusiv în **Python** folosind framework-ul **NiceGUI** (bazat pe Vue.js și Quasar).
- Stilizarea se face folosind utilitare **Tailwind CSS** (prin metoda `.classes()`) și proprietăți specifice **Quasar** (prin metoda `.props()`).

## 2. Paleta de Culori (Color Scheme)
Tema generală a aplicației este construită în jurul culorii **Galben (Yellow)**, pentru a oferi un aspect prietenos și distinct. Culorile albastre implicite ale diverselor componente trebuie evitate/suprascrise.

- **Culoarea principală (Primary/Accent)**: `#ffcc00`. Se aplică global prin `ui.colors(primary="#ffcc00", accent="#ffcc00")`.
- **Fundaluri secțiuni (Cards/Containers)**: `bg-white`, `bg-gray-50/30`, sau `bg-yellow-50/70` pentru zone de accent (ex: secțiunea de încărcare documente).
- **Borduri**: `border-yellow-100` pentru cardurile principale, `border-gray-200` pentru carduri secundare, `border-green-100` pentru obligații confirmate cu succes.
- **Iconițe**: `text-yellow-600` pentru iconițele principale de secțiune.
- **Tipografie**: 
  - Titluri mari: `text-gray-800 font-extrabold`.
  - Subtitluri/Accente: `text-yellow-800` sau `text-yellow-900`.
  - Text principal (Body): `text-gray-800`.
  - Text secundar (Meta/Mici explicații): `text-gray-600` sau `text-gray-500`.

## 3. Butoane (Buttons)
Există un limbaj de design strict pentru butoane. **Foarte important:** toate butoanele trebuie să aibă proprietatea `no-caps` (adăugată prin `.props("no-caps")`) pentru a suprascrie comportamentul implicit Quasar de a transforma textul în majuscule (uppercase).

- **Butoane de Acțiune Principale (Primary - ex. "Analizează", "Salvează"):**
  - Props: `.props("push rounded size=md color=primary no-caps")`
  - Classes: `.classes("px-6 py-2 text-base font-extrabold shadow-lg hover:scale-105 transition-transform duration-200 text-gray-900")`
- **Butoane Secundare (Outline - ex. "Vezi progresul", "Corectează"):**
  - Props: `.props("outline rounded size=sm color=primary no-caps")`
  - Classes: `.classes("px-4 py-1 text-sm font-bold hover:bg-gray-50")`
- **Butoane Negative / Distructive (ex. "Respinge"):**
  - Props: `.props("flat rounded size=sm color=negative no-caps")`
  - Classes: `.classes("font-bold hover:bg-red-50 px-3")`
- **Butoane Simple (Flat - ex. "Înapoi", "Deschide document"):**
  - Props: `.props("flat no-caps dense color=primary")`

## 4. Prezentarea Datelor: Documente
Când se afișează un document sau un link către un document, prioritatea este **întotdeauna numele real al fișierului** (`originalFilename`), nu categoria acestuia (`displayName`). Categoria (ex: "Cerere de finanțare") poate fi afișată secundar, cu text mai mic, doar dacă este necesar.

## 5. Prezentarea Datelor: Obligații / Criterii
Pentru a nu confunda utilizatorul, **nu se afișează niciodată ID-uri interne sau UUID-uri** (câmpul `id` sau `code` autogenerat). 
Structura vizuală a unui card de obligație este:
1. Etichetă supra-titlu: "OBLIGAȚIE" (`font-extrabold text-green-700 uppercase tracking-wide text-xs`).
2. Descrierea completă a obligației (`font-bold text-lg`).
3. Termenul limită (`text-sm text-gray-600`).

## 6. Prezentarea Datelor: Dovezi (Source Anchors)
Orice pasaj extras din documente (dovezi pentru obligații sau rapoarte) este plasat într-o expansiune (acordeon). Formatul este standardizat:
- **Titlul expansiunii**: `[NumeleFișierului.pdf] · pagina [NumărPagina]`
- **Stilizare expansiune**: `.classes("w-full bg-gray-50 rounded-md border border-gray-100")`
- **Conținutul expansiunii**: 
  1. Un buton "Deschide documentul" care declanșează funcția de download/vizualizare.
  2. Pasajul de text propriu-zis (`whitespace-normal text-gray-700`).

## 7. Reguli de Flow & UX
- **Validarea dovezilor**: Orice propunere de obligațiune generată de AI care nu conține dovezi/ancore ("sourceAnchors") nu trebuie să prezinte butoane de confirmare manuală și trebuie să fie ignorată de butoanele globale de acțiune ("Confirmă toate"). Se afișează cu text roșu: "Fără pasaj sursă — nu poate fi confirmată."
- **Feedback vizual**: Operațiunile asincrone grele folosesc `ui.spinner()` și `ui.notify()` pentru succes (verde/positive) sau eroare (roșu/negative).
