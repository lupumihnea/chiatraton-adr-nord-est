# AGENTS.md

## Produs

Construim un AI verification workspace pentru verificarea raportului periodic
selectat în cadrul proiectelor monitorizate de ADR Nord-Est.

ChIAtraton nu înlocuiește MyADR sau MySMIS. Sistemele externe gestionează în
continuare task-urile, prioritățile, distribuirea, validarea, autorizarea și
clarificările oficiale. ChIAtraton păstrează contextul intern al analizei și nu
declanșează acțiuni oficiale în aceste sisteme.

Sistemul nu ia decizii juridice. AI-ul propune constatări, iar utilizatorul le
confirmă, corectează sau respinge.

## Flux obligatoriu

1. Un apel de finanțare conține proiecte.
2. Un proiect conține documente și criterii de monitorizare.
3. Proiectul primește rapoarte periodice până la `monitoringEndDate`, data
   contractuală explicită.
4. Un raport are exact un document principal (`main_report` sau
   `final_document`) și poate avea documente suport (`attachment` sau
   `clarification`).
5. Raportul păstrează separat statusul intern și metadatele oficiale opționale:
   `externalSystem`, `externalId`, `externalUrl` și `externalStatus`.
6. Pentru fiecare raport, fiecare criteriu este verificat separat.
7. AI-ul compară raportul cu criteriile, documentele de proiect selectate și,
   opțional, rapoartele anterioare selectate explicit.
8. Validările rapoartelor și reviziilor anterioare nu sunt suprascrise.
9. Fiecare constatare AI trebuie să conțină `documentId`, `pageNumber` și
   `passage`.
10. Există un singur tip de actor de business: utilizatorul.

## Terminologie

Folosiți în cod denumirile:

- Project
- Document
- Criterion
- Report
- CriterionValidation
- AnalysisJob
- SourceAnchor
- UserDecision

Folosiți `criteria`, nu `obligations`, pentru noile contracte API.

## Responsabilități

- Mihnea: API, scheme Pydantic și contracte OpenAPI.
- Andrei: UI/UX în NiceGUI; consumă API-ul prin HTTP.
- Emi: integrarea AI folosind Qwen; respectă contracts/ai-contract.md.
- Dragoș: SQLite, DAO și eventual migrarea la PostgreSQL.

## Limite între componente

- UI-ul nu accesează direct baza de date sau DAO-urile.
- API-ul nu depinde direct de sqlite3.
- Accesul la DB se face prin interfețe repository.
- API-ul nu trebuie să cunoască implementarea internă Qwen.
- Modelul AI și URL-ul său sunt configurate prin variabile de mediu.
- Nu modifica schema bazei de date fără acordul responsabilului DB.
- Nu modifica openapi.yaml fără acordul responsabilului API.
- Pentru task-urile de contract nu modifica `Interface/`, `DAO/` sau
  `DataBase/`.

## Confidențialitate

- Nu folosi și nu publica fotografiile realizate la ADR.
- Nu introduce în repository date reale despre beneficiari, proiecte sau
  personal.
- Exemplele din contracte și teste trebuie să fie integral sintetice.
- Nu include secrete, URL-uri interne sau conținut real în loguri și erori.

## Autoritatea surselor

În cazul unui conflict, ordinea este:

1. Documentele oficiale ADR și contractul aplicabil proiectului.
2. Deciziile confirmate în urma vizitelor ADR, de PO și de mentor.
3. docs/product-spec.md și docs/workflow.md.
4. contracts/openapi.yaml.
5. Implementarea existentă.

Codul vechi nu este automat sursa adevărului.

## Verificare

Pentru orice modificare API:

- rulează testele;
- verifică validarea Pydantic;
- verifică OpenAPI;
- nu schimba comportamentul public fără actualizarea contractului.
- verifică faptul că `status` și `externalStatus` rămân independente;
- verifică faptul că toate operațiile POST implementează `Idempotency-Key`;
- verifică faptul că exemplele nu conțin date reale.
