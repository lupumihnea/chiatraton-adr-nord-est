# Implementarea AI Qwen — compatibilă cu API v1

Această implementare înlocuiește integrarea AI legacy care accesa direct SQLite/DAO.
Ea respectă limitele stabilite în `AGENTS.md`, `contracts/ai-contract.md` și
`contracts/openapi.yaml`.

## Limite de componentă

```text
NiceGUI -> HTTP API -> ApplicationService -> AIClient ports -> QwenAIAdapter -> OpenRouter
                         |                    |
                         |                    +-> parsing + semantic retrieval
                         +-> repositories/storage
```

- `Interface/` nu importă AI, DAO sau SQLite.
- `AI/` nu importă UI, DAO, repositories sau DB.
- API-ul cunoaște doar `CriterionExtractor` și `ReportAnalyzer` din
  `app/services/ports.py`.
- composition root-ul `app/main.py` injectează loader-ul pentru content handles.
- contractul HTTP/OpenAPI nu este modificat.

## Grounding

Modelul nu returnează pasajele care sunt persistate. Textul extras local este
împărțit în SOURCE UNITS cu offset-uri. Qwen returnează numai
`candidate_id + unit_start + unit_end`, iar adaptorul reconstruiește local
`SourceAnchor.passage` ca substring exact al textului extras de pe pagina indicată.

Nu se execută OCR în mod silențios. Paginile PDF fără text layer nu pot deveni
surse de constatări până când există o sursă text validă sau un pas OCR explicit,
separat și auditat.

## Retrieval

Retrieval-ul folosește `intfloat/multilingual-e5-small` local, per document și
cu garduri de recall pentru tabele/indicatori/termene. Nu există fallback
TF-IDF sau character n-gram.

La analiza raportului, contextul este separat în:

- `current_report`;
- `project_document`;
- `previous_report`.

Pentru fiecare criteriu se caută semantic dovezi în fiecare categorie, apoi Qwen
primește doar pasajele candidate. Raportul curent rămâne sursa principală de
conformitate; rapoartele anterioare sunt folosite pentru contradicții numai când
au fost selectate explicit prin API.

## Rezultate

Adaptorul respectă enum-ul API existent:

- `compliant`
- `non_compliant`
- `partially_compliant`
- `not_applicable`
- `insufficient_evidence`

Lipsa informației/dovezii devine `insufficient_evidence`; nu se inventează o
ancoră. API-ul creează câte o `CriterionValidation` pentru fiecare criteriu și
păstrează decizia utilizatorului separat.

## Configurare

Instalare pentru API + UI + AI:

```powershell
python -m pip install -e ".[ui,ai,test]"
```

Configurare runtime:

```powershell
$env:CHIATRATON_CRITERION_EXTRACTOR_BACKEND="qwen"
$env:CHIATRATON_REPORT_ANALYZER_BACKEND="qwen"
$env:AI_PROVIDER="qwen"
$env:AI_MODEL_NAME="qwen/qwen3-235b-a22b-2507"
$env:AI_BASE_URL="https://openrouter.ai/api/v1"
$env:AI_API_KEY="CHEIA_TA_NOUA"
$env:AI_TIMEOUT_SECONDS="180"
$env:AI_CONTRACT_VERSION="1.0"
```

Cheia nu se pune în Git. Variabilele legacy `OPENROUTER_PAID_MODEL`,
`OPENROUTER_BASE_URL` și `OPENROUTER_API_KEY` sunt acceptate și ele de Settings
pentru compatibilitate, dar `AI_*` este forma conformă cu contractul curent.

## Pornire

API:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

UI într-un al doilea terminal:

```powershell
python -m Interface.main
```

UI-ul continuă să consume exclusiv HTTP API-ul. Joburile de extracție și analiză
sunt endpoint-urile deja definite în `contracts/openapi.yaml`; adaptorul Qwen
este în spatele lor și nu introduce un al doilea workflow paralel.
