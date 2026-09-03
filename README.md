# ChIAtraton - ADR Nord-Est

ChIAtraton este un AI verification workspace pentru raportul periodic selectat. Aplicația
organizează proiectele, documentele, criteriile, rapoartele și dovezile, iar AI-ul propune
constatări pe care utilizatorul le confirmă, corectează sau respinge. Nu înlocuiește
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
$env:AI_BASE_URL="https://openrouter.ai/api/v1"
$env:AI_API_KEY="CHEIA_TA_NOUA"
$env:AI_CONTRACT_VERSION="1.0"
```

Modelul nu furnizează direct pasajele persistate. El returnează pointeri către
source-units, iar adaptorul reconstruiește local pasajul exact și pagina înainte ca
API-ul să creeze `CriterionProposal` sau `CriterionValidation`. Detalii în
`docs/ai-implementation.md`.

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

- AI-ul creează `CriterionProposal`, nu `Criterion`; numai review-ul utilizatorului poate
  crea criterii.
- Review-ul batch este atomic. `accept` și `correct` creează criterii, `reject` nu creează.
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
Report → AnalysisJob → CriterionValidation → UserDecision.

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
- Validarea faptului că pasajul AI există textual în document va fi realizată de fluxul
  real de extracție a conținutului; adaptorul fake validează doar forma și apartenența
  ancorei.

## Documentație

- [Contractul HTTP API v1](contracts/http-api.md)
- [OpenAPI 3.1](contracts/openapi.yaml)
- [Contractul AI](contracts/ai-contract.md)
- [Specificația produsului](docs/product-spec.md)
- [Workflow](docs/workflow.md)
- [Modelul de date](docs/data-model.md)
- [Arhitectura](docs/architecture.md)

Nu se publică fotografii realizate la ADR, date reale despre beneficiari, URL-uri interne
sau alte informații sensibile.
