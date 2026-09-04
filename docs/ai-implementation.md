# Implementarea AI Qwen — compatibilă cu API v1

Această implementare înlocuiește integrarea AI legacy care accesa direct SQLite/DAO.
Ea respectă limitele stabilite în `AGENTS.md`, `contracts/ai-contract.md` și
`contracts/openapi.yaml`.

## Limite de componentă

```text
NiceGUI -> HTTP API -> ApplicationService -> AIClient ports -> QwenAIAdapter -> OpenRouter
                         |                    |
                         |                    +-> parsing + discovery/review/global selection
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
împărțit în SOURCE UNITS cu offset-uri. Qwen returnează pentru dovezi numai
`candidate_id + unit_start + unit_end`, iar adaptorul reconstruiește local
`SourceAnchor.passage` ca substring exact al textului extras de pe pagina indicată.

Pentru extracția baseline, `proposedDescription` este un statement atomic formulat
de AI pe baza dovezilor, nu un citat. Pasajele exacte rămân în `sourceAnchors` și
sunt afișate separat pentru review-ul utilizatorului.

Nu se execută OCR în mod silențios. Paginile PDF fără text layer nu pot deveni
surse de constatări până când există o sursă text validă sau un pas OCR explicit,
separat și auditat.

Primitivele interne pentru afirmații verificabile sunt în `AI.claim_engine`.
Acest strat este provider-agnostic: claim-ul, evidence-ul, rezultatele
verifierilor și decizia finală sunt modelate separat de Qwen/OpenRouter.
Detaliile de design sunt în `docs/verified-claim-engine.md`.

## Parsing PDF și tabele

Pentru PDF-uri, PyMuPDF rămâne sursa canonică locală pentru pagină/text. Pentru
structura tabelelor se încearcă OpenDataLoader PDF (`table_method=cluster`,
`reading_order=xycut`), cu fallback deterministic la `PyMuPDF find_tables()`.
Secțiunile MySMIS `Tip: OPTIUNI` sunt parsate separat: numai variantele explicit
`Selectată: Da` pot ajunge la extractor, iar sursa exactă include markerul de
selecție. Alternativele `Nu` nu intră în extracție. Detalii în
`docs/pdf-parsing.md`.

## Extracție Baseline

Extractorul baseline folosește trei roluri conceptuale mici:

```text
toate candidate-urile parserului
  -> discovery batch-uri + coverage ledger, orientate pe recall
  -> review semantic strict în batch-uri, orientat pe precision
  -> compactare globală numai pentru duplicatele acceptate
  -> validare locală a provenance-ului și SourceAnchor exact
```

Discovery emite claim-uri atomice cu statement + evidence pointers și trebuie să
contabilizeze fiecare source candidate exact o dată în coverage ledger. Reviewer-ul
emite exact un verdict pentru fiecare claim, împreună cu o clasificare abstractă și
un test concret de monitorizare. Numai claim-urile `keep` cu evidence suficient trec
prin `AI.claim_engine`; compactarea ulterioară poate numai grupa ID-uri duplicate și
folosește statement-ul deja verificat al claim-ului reprezentativ.

Codul local nu folosește regex-uri semantice ca să decidă ce este obligație. El
verifică forma JSON, exhaustivitatea ledger-elor, relațiile dintre claim-uri și
evidence și faptul că fiecare dovadă există exact pe pagina declarată. Un răspuns
care omite ID-uri, citează pointeri necunoscuți sau pierde claim-uri la compactare
este reîncercat o dată, apoi respins integral.

Conceptual, acest extractor este prima specializare a `GroundedClaimEngine`:
întrebarea internă este exhaustivă, nu conversațională, iar răspunsul acceptat
este o listă de claim-uri monitorizabile independent. Aceeași fundație poate
servi ulterior întrebări punctuale, rezumate sau QA, dar acele fluxuri pot folosi
retrieval normal în loc de map/reduce peste toate candidate-urile.

## Retrieval

Retrieval-ul folosește `intfloat/multilingual-e5-small` local pentru analiza
rapoartelor, per document și cu garduri de recall pentru tabele/indicatori/termene.
Nu există fallback TF-IDF sau character n-gram. Extracția baseline nu selectează
semantic înainte de LLM: fiecare chunk/candidate parser valid intră într-un batch
de discovery.

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
# Opțional; în lipsă se reutilizează AI_MODEL_NAME.
$env:AI_REVIEWER_MODEL_NAME="provider/reviewer-model"
$env:AI_BASE_URL="https://openrouter.ai/api/v1"
$secureKey = Read-Host "OpenRouter API key" -AsSecureString
$env:AI_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password
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
