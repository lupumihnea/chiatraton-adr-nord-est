# ChIAtraton - ADR Nord-Est

ChIAtraton este un AI verification workspace pentru raportul periodic selectat. Aplicația
organizează proiectele, documentele, obligațiile proiectului, rapoartele și dovezile. AI-ul
propune obligații din documentele-sursă și evaluează progresul raportat față de obligațiile
confirmate. Nu înlocuiește
MyADR/MySMIS și nu execută task-uri, autorizări ori clarificări oficiale.

Implementarea curentă oferă întregul workflow HTTP API v1 în modul
`development`: servicii de aplicație reale, repository-uri și stocare de documente în
memorie, joburi locale, adaptoare AI fake deterministe pentru teste și adaptorul real
Qwen/OpenRouter din `AI/`. Toate exemplele și fixture-urile sunt sintetice.

## Instalare

Este necesar Python 3.11 sau mai nou.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test,ui,ai]"
Copy-Item .env.example .env
```

În `.env`, înlocuiește valoarea sintetică `CHIATRATON_JWT_SECRET` cu un secret local
aleatoriu. Fișierul `.env` este ignorat de Git.

## Pornire în development/demo

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Documentația interactivă este la `http://127.0.0.1:8000/docs`, iar health check-ul public
la `http://127.0.0.1:8000/health`. Toate operațiile `/api/v1` cer Bearer JWT și toate
operațiile `POST` cer `Idempotency-Key`.

Generează un token cu durată scurtă numai pentru development/test:

```powershell
$token = python -m app.core.dev_token --subject synthetic-demo-user --minutes 60
```

Generatorul folosește configurația din `.env`, nu afișează secretul și refuză rularea
când `CHIATRATON_ENVIRONMENT=production`. Nu există endpoint de autentificare deoarece
acesta nu face parte din contractul API v1.

Într-un al doilea terminal, transmite tokenul către clientul UI și pornește NiceGUI:

```powershell
$token = python -m app.core.dev_token --subject synthetic-demo-user --minutes 60
$env:CHIATRATON_API_BASE_URL = "http://127.0.0.1:8000"
$env:CHIATRATON_UI_BEARER_TOKEN = $token
python -m Interface.main
```

Interfața este disponibilă implicit la `http://127.0.0.1:8081`. Portul poate fi schimbat
prin `CHIATRATON_UI_PORT`. UI-ul listează proiectele după nume și UUID, creează proiecte
cu exact câmpurile contractuale și încarcă documente prin API; nu accesează direct
repository-uri, DAO-uri sau baza de date.

Exemplu minimal:

```powershell
$headers = @{
  Authorization = "Bearer $token"
  "Idempotency-Key" = "synthetic-project-0001"
}
$body = @{
  name = "Synthetic monitoring project"
  completionDate = "2030-12-31"
  monitoringEndDate = "2033-12-31"
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/v1/projects `
  -Method Post -Headers $headers -ContentType application/json -Body $body
```

## Configurare

Variabilele au prefixul `CHIATRATON_`:

| Variabilă | Development/demo | Production |
|---|---|---|
| `ENVIRONMENT` | `development` sau `test` | `production` |
| `JWT_SECRET` | secret local | secret injectat la runtime |
| `IDEMPOTENCY_BACKEND` | `memory` | `external` |
| `REPOSITORY_BACKEND` | `memory` | `external` |
| `DOCUMENT_STORAGE_BACKEND` | `memory` | `external` |
| `CRITERION_EXTRACTOR_BACKEND` | `fake` sau `qwen` | `external` |
| `REPORT_ANALYZER_BACKEND` | `fake` sau `qwen` | `external` |
| `JOB_RUNNER_BACKEND` | `local` | `external` |
| `API_BASE_URL` | `http://127.0.0.1:8000` | URL-ul API injectat la runtime |
| `UI_BEARER_TOKEN` | token local cu durată scurtă | token injectat la runtime |
| `UI_HOST` / `UI_PORT` | `127.0.0.1` / `8081` | configurate la deployment |

Pornirea în production este refuzată dacă a rămas selectat oricare adaptor in-memory,
fake sau local. Compoziția production trebuie să injecteze explicit `ApplicationService`
și `IdempotencyStore` cu adaptoarele infrastructurii reale.


## Qwen/OpenRouter real

Implementarea AI reală este compatibilă cu contractele curente și nu introduce un
workflow paralel sau acces direct la DB. Instalează extra-ul AI:

```powershell
python -m pip install -e ".[ui,ai,test]"
```

Apoi configurează:

```powershell
$env:CHIATRATON_CRITERION_EXTRACTOR_BACKEND="qwen"
$env:CHIATRATON_REPORT_ANALYZER_BACKEND="qwen"
$env:AI_PROVIDER="qwen"
$env:AI_MODEL_NAME="qwen/qwen3-235b-a22b-2507"
# Opțional: un model separat, mai strict, pentru review și deduplicare.
$env:AI_REVIEWER_MODEL_NAME="provider/reviewer-model"
$env:AI_BASE_URL="https://openrouter.ai/api/v1"
$secureKey = Read-Host "OpenRouter API key" -AsSecureString
$env:AI_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
$env:AI_CONTRACT_VERSION="1.0"
```

La extracția baseline, modelul formulează un statement atomic pentru propunere și
returnează separat pointeri către source-units. Adaptorul reconstruiește local
pasajele exacte și pagina înainte ca API-ul să creeze `CriterionProposal`.
La analiza raportului, dovezile sunt reconstruite la fel pentru `CriterionValidation`.
Stratul intern `AI.claim_engine` modelează aceste rezultate ca afirmații
verificabile: statement formulat de AI, evidence exact din document, verificări
independente și decizie deterministă. Detalii în `docs/ai-implementation.md` și
`docs/verified-claim-engine.md`.

### Comportamentul AI pe categoriile existente

Categoriile din UI rămân neschimbate și nu necesită modificări de schemă:

| Categoria UI | Comportament AI |
|---|---|
| `Documente legate de apel` | propune obligații/reguli monitorizabile aplicabile proiectului |
| `Documente inițiale` | propune angajamente specifice proiectului: indicatori, ținte, termene, milestone-uri și angajamente de punctaj |
| `Rapoarte de progres` | nu creează obligații; creează `Report` și verifică progresul față de obligațiile confirmate |
| `Alte documente` | documente suport; nu generează automat obligații |

În UI, `Criterion` este prezentat drept **Obligație**, iar `CriterionValidation` drept
progres/verificare a obligației. Contractele și schema backend rămân neschimbate.

### PDF-uri și tabele

Parserul local păstrează structura tabelară înainte de LLM:

1. `OpenDataLoader PDF` este încercat primul în modul implicit `auto`;
2. opțional, OpenDataLoader poate fi rulat în modul Hybrid (`docling-fast`) pentru
   pagini/tabele complexe, cu backend local;
3. dacă OpenDataLoader/Java/backend-ul local nu este disponibil, se folosește
   `PyMuPDF find_tables()`;
4. secțiunile MySMIS `Tip: OPTIUNI` sunt tratate separat și numai variantele explicit
   `Selectată: Da` pot ajunge în pool-ul pentru extracția obligațiilor, împreună
   cu markerul exact al selecției;
5. alternativele `Selectată: Nu` sunt excluse structural; datele izolate și
   metricile istorice sunt clasificate de reviewer, fără reguli de conținut hardcodate;
6. reprezentarea semantică a unui rând (`Header: valoare | ...`) este separată de pasajul canonic: numai un substring exact recuperat din textul PyMuPDF poate deveni `SourceAnchor`;
7. dacă un rând structurat nu poate fi mapat mecanic la textul canonic, acel rând sintetic nu ajunge la Qwen, iar pagina brută rămâne fallback;
8. propunerile duplicate sunt grupate fără pierderea `SourceAnchor`-urilor și fără
   ca etapa de compactare să poată rescrie sau elimina claim-uri acceptate.

Extracția obligațiilor nu mai folosește un singur apel global peste tot textul.
Adaptorul rulează discovery cu ledger complet pentru fiecare source candidate,
review semantic strict în batch-uri de cel mult 16 claim-uri și, la final, o
compactare globală care numai grupează duplicatele. Fiecare claim trebuie să
primească exact un verdict; răspunsurile incomplete sunt reîncercate și apoi
respinse, nu publicate parțial.

OpenDataLoader necesită Java 11+ și este inclus în extra-ul `ai`. Configurația implicită este:

```powershell
$env:CHIATRATON_PDF_TABLE_BACKEND="auto"
```

Poți forța `opendataloader` sau `pymupdf`. Detalii în `docs/pdf-parsing.md`.
Pentru experimentul Hybrid local:

```powershell
opendataloader-pdf-hybrid --port 5002
$env:CHIATRATON_PDF_OPENDATALOADER_HYBRID="docling-fast"
$env:CHIATRATON_PDF_OPENDATALOADER_HYBRID_MODE="auto"
```

## Matrice endpoint-uri

| Metodă | Rută | Implementare curentă |
|---|---|---|
| GET | `/health` | funcțional, public |
| POST | `/api/v1/projects` | funcțional, in-memory |
| GET | `/api/v1/projects` | funcțional, cursor opac |
| POST | `/api/v1/projects/{projectId}/documents` | funcțional, conținut in-memory separat |
| POST | `/api/v1/projects/{projectId}/criteria` | funcțional, cod unic și ancore validate |
| GET | `/api/v1/projects/{projectId}/criteria` | funcțional, cursor opac |
| POST | `/api/v1/projects/{projectId}/criterion-extraction-jobs` | funcțional, `202` + job local |
| GET | `/api/v1/analysis-jobs/{jobId}` | funcțional pentru ambele tipuri de job |
| GET | `/api/v1/criterion-extraction-jobs/{jobId}/proposals` | funcțional, auditabil |
| POST | `/api/v1/criterion-extraction-jobs/{jobId}/proposal-reviews` | funcțional, batch atomic |
| POST | `/api/v1/projects/{projectId}/reports` | funcțional, document primar unic |
| GET | `/api/v1/projects/{projectId}/reports` | funcțional, cursor opac |
| POST | `/api/v1/reports/{reportId}/analysis-jobs` | funcțional, `202` + snapshot criterii |
| GET | `/api/v1/reports/{reportId}/validations` | funcțional, istoric opțional |
| POST | `/api/v1/validations/{validationId}/decisions` | funcțional, control optimist al reviziei |

Rutele FastAPI depind numai de interfața `ApplicationService`. Serviciul concret depinde
de porturile `UnitOfWork`, `DocumentStorage`, `CriterionExtractor`, `ReportAnalyzer` și
`JobRunner`; nu importă SQLite, Qwen, OpenRouter sau NiceGUI.

## Reguli importante

- În UI, AI-ul propune **obligații**. Intern creează `CriterionProposal`, nu `Criterion`; numai
  review-ul utilizatorului poate crea obligația confirmată (`Criterion`).
- Review-ul batch este atomic. `accept` și `correct` creează obligații confirmate, `reject` nu creează.
- `Rapoarte de progres` nu intră în extractorul de obligații; ele sunt analizate prin `ReportAnalyzer`.
- La analiza unui raport, listele goale de context sunt rezolvate automat la documentele baseline relevante și la rapoartele anterioare proiectului; nu este necesar un agent sau un contract API nou.
- UI-ul de analiză arată implicit excepțiile acționabile (`partially_compliant`, `non_compliant`, `insufficient_evidence`) și permite afișarea tuturor obligațiilor.
- Fiecare propunere și fiecare constatare factuală are `SourceAnchor` cu document, pagină
  și pasaj.
- O reanalizare adaugă o nouă revizie de `CriterionValidation`; istoricul și deciziile
  vechi rămân disponibile.
- `Report.status` este independent de `externalStatus`.
- Repetarea unui `POST` cu aceeași cheie și același payload returnează răspunsul inițial;
  aceeași cheie cu alt payload produce `409 idempotency_conflict`.
- Conținutul documentelor nu este inclus în loguri sau erori.

## Teste și verificări

```powershell
python -m pytest
python -m ruff check app tests Interface
python -m compileall -q app tests Interface
```

Testele validează și contractul OpenAPI 3.1, exemplele JSON, JWT, ProblemDetails,
idempotency și întregul workflow Project → Document → CriterionProposal → Criterion →
Report → AnalysisJob → CriterionValidation → UserDecision. În UI, același flux este prezentat
ca Documente-sursă → Obligații → Raport de progres → Progres față de obligații.

## Limitări și următoarele adaptoare

Starea, cursoarele, fișierele și joburile locale se pierd la restart și nu sunt potrivite
pentru mai multe procese. Modul `fake` rămâne disponibil pentru testele structurale. Pentru analiza reală,
setează backends la `qwen`; adaptorul din `AI/` parsează documentele, face retrieval
semantic multilingual E5 și apelează Qwen prin OpenRouter paid-only.

- Dragoș poate înlocui `InMemoryUnitOfWorkFactory` și `InMemoryDocumentStorage` cu
  adaptoarele SQLite, apoi PostgreSQL, fără a schimba rutele.
- Adaptorul Qwen este implementat în `AI/qwen_adapter.py` și este injectat numai
  prin porturile `CriterionExtractor` / `ReportAnalyzer`; modul fake rămâne pentru teste.
- Un runner durabil și un `IdempotencyStore` extern trebuie injectate înainte de
  production.
- Adaptorul real separă reprezentarea semantică de evidența canonică și construiește
  `SourceAnchor` numai din text local exact. Pentru reanalizări, parsing-ul documentelor
  și embedding-urile textelor/query-urilor sunt cache-uite in-process după identitatea
  imuabilă / hash-ul conținutului, fără schimbarea scorurilor de retrieval.

## Documentație

- [Contractul HTTP API v1](contracts/http-api.md)
- [OpenAPI 3.1](contracts/openapi.yaml)
- [Contractul AI](contracts/ai-contract.md)
- [Specificația produsului](docs/product-spec.md)
- [Workflow](docs/workflow.md)
- [Modelul de date](docs/data-model.md)
- [Arhitectura](docs/architecture.md)
- [Verified Claim Engine](docs/verified-claim-engine.md)

Nu se publică fotografii realizate la ADR, date reale despre beneficiari, URL-uri interne
sau alte informații sensibile.
