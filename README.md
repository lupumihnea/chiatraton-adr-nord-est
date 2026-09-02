# ChIAtraton – ADR Nord-Est Monitoring Copilot

Acest branch integrează prototipul RAG/OpenRouter cu proiectul NiceGUI + repository/DAO și implementează fluxul complet de verificare a unui raport periodic.

AI-ul **nu ia decizia finală**. El identifică excepții verificabile; utilizatorul confirmă, corectează, respinge sau cere clarificări. Istoricul analizelor și al deciziilor este păstrat.

## Workflow implementat

1. Utilizatorul deschide proiectul și selectează un raport/task existent.
2. Aplicația încarcă proiectul, raportul, documentele asociate și rapoartele anterioare.
3. OpenRouter/Qwen decide ce criterii sunt aplicabile perioadei raportate.
4. Pentru fiecare criteriu compară raportul cu:
   - sursa exactă a criteriului (contract/anexă/cerere/plan etc.);
   - documentele relevante ale proiectului;
   - rapoartele periodice anterioare.
5. UI-ul afișează **numai**:
   - neconcordanțe;
   - informații lipsă;
   - valori/date diferite;
   - dovezi insuficiente;
   - contradicții între rapoarte;
   - cazuri care necesită analiză umană.
6. Pentru fiecare excepție sunt păstrate și afișate cele două pasaje-sursă și paginile, atunci când textul poate fi extras mecanic. Modelul returnează doar ID-uri de evidence; pasajele finale sunt luate local din documente, nu rescrise de model.
7. Utilizatorul confirmă, corectează, respinge sau solicită clarificări.
8. Aplicația generează o notă de verificare sau un draft de clarificare din constatările revizuite.
9. Rezultatul poate fi copiat sau exportat `.txt` pentru transfer în sistemul oficial.
10. `AnalysisJob`, reviziile validărilor, `UserDecision` și exporturile rămân în istoric.

## AI integrat

- Provider: **OpenRouter paid-only**.
- Model implicit: `qwen/qwen3-235b-a22b-2507`.
- Nu există fallback la modele `:free`.
- Embeddings: `intfloat/multilingual-e5-small`, local.
- Parsing/RAG: local.
- Obligațiile/criteriile și pasajele-sursă rămân exact textul românesc extras local.
- Cheia OpenRouter nu este salvată în repository.

## Instalare

În PowerShell, din rădăcina proiectului:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Configurați modelul:

```powershell
$env:OPENROUTER_API_KEY="CHEIA_TA"
$env:OPENROUTER_PAID_MODEL="qwen/qwen3-235b-a22b-2507"
```

### Refolosirea bazei din prototipul RAG existent

Dacă baza ta curentă este `adr_rag.db`, cel mai simplu este să o copiezi în rădăcina acestui proiect și să rulezi:

```powershell
$env:ADR_DB_PATH="adr_rag.db"
$env:DATABASE_URL="sqlite:///adr_rag.db"
python workflow_cli.py init-db
```

`init-db` **nu șterge** proiectele, documentele, criteriile sau referințele existente. Adaugă doar tabelele necesare workflow-ului de rapoarte și istoric.

Dacă nu setezi nimic, baza implicită este `documents.db`.

## Pornire UI

```powershell
python Interface\main.py
```

Apoi deschide `http://localhost:8080`.

UI-ul este organizat astfel:

`Proiect -> Raport/task -> Analiză -> Excepții -> Decizie umană -> Notă/Draft -> Istoric`

## CLI – flux minim

### 1. Inițializează extensiile DB

```powershell
python workflow_cli.py init-db
```

### 2. Leagă documentele proiectului

Pentru proiectul folosit în prototip:

```powershell
python workflow_cli.py link-documents `
  --project-id 123456 `
  --document-ids 1 3 4 5 6 7 8 9
```

Documentul raportului se înregistrează separat ca `Report`.

### 3. Opțional: re-extrage criteriile

```powershell
python workflow_cli.py extract-criteria `
  --project-id 123456 `
  --document-ids 1 3 4 5 6 7 8 9
```

Aceasta folosește pipeline-ul RAG recall-oriented deja dezvoltat și salvează `obligation + references` în aceeași bază. Din motive de audit, setul nu poate fi înlocuit după ce există validări istorice; o versiune ulterioară de criterii trebuie tratată explicit.

### 4. Înregistrează raportul existent

Presupunând că PDF-ul raportului este deja în tabela `document` cu `id=10`:

```powershell
python workflow_cli.py add-report `
  --project-id 123456 `
  --document-id 10 `
  --sequence 1 `
  --kind implementation_progress `
  --period-start 2025-01-01 `
  --period-end 2025-03-31
```

### 5. Analizează raportul

```powershell
python workflow_cli.py analyze-report --report-id 1
```

CLI-ul și UI-ul afișează numai excepțiile. Intern, baza păstrează și criteriile evaluate ca `ok/not_applicable`, astfel încât analiza să fie auditabilă.

### 6. Decizie umană

```powershell
python workflow_cli.py decide `
  --validation-id 12 `
  --action confirmed
```

Acțiuni disponibile: `confirmed`, `corrected`, `rejected`, `clarification_requested`.

### 7. Generează rezultat

```powershell
python workflow_cli.py generate --report-id 1 --kind verification_note
```

sau:

```powershell
python workflow_cli.py generate --report-id 1 --kind clarification_draft
```

Fișierul este scris în `exports/` și înregistrat în istoric.

## Baza de date

Cele patru entități existente din RAG rămân:

- `project`
- `document`
- `obligation` – conceptul legacy folosit ca `Criterion`
- `references` – sursa exactă a criteriului

Extensia workflow adaugă:

- `project_documents`
- `reports`
- `analysis_jobs`
- `criterion_validations`
- `validation_sources`
- `user_decisions`
- `generated_outputs`

Schema veche cu denumiri plural (`projects`, `documents`, `obligations`, `referinte`) este importată best-effort dacă este găsită într-o bază veche goală pe partea canonică.

## Reguli de auditabilitate

- Fiecare criteriu extras de RAG trebuie să aibă o referință exactă.
- Pentru o constatare, modelul selectează doar evidence IDs; textul și pagina sunt recuperate local.
- UI-ul normalizează doar whitespace-ul pentru afișare; nu schimbă cuvintele, punctuația sau diacriticele pasajelor.
- Analiza unui raport nu suprascrie raportul anterior.
- Reanalizarea cu `--force` creează revizii noi.
- Deciziile umane sunt append-only.
- Un retry cu aceeași stare a raportului și criteriilor este idempotent.
- Dacă un document nu are strat text, aplicația nu inventează un pasaj; cazul este tratat ca `insufficient_evidence`/analiză umană.

## Structură

- `Interface/` – NiceGUI
- `API/monitoring_api.py` – boundary consumat de UI/CLI
- `Services/monitoring_service.py` – orchestrarea workflow-ului
- `AI/openrouter_monitoring_client.py` – comparația raport-criteriu
- `adr_rag/` – parsing, embeddings, retrieval și extracția criteriilor
- `Repositories/` – acces DB
- `DAO/` – obiecte de transfer legacy
- `DataBase/db_schema.py` – schema SQLite integrată, aditivă
- `workflow_cli.py` – flux end-to-end fără UI

## Teste

```powershell
pytest -q
```

Testele incluse verifică fluxul analiză -> două surse -> decizie -> export -> istoric și idempotency, fără apel real către OpenRouter.

## Confidențialitate

`exports/`, bazele de date, `.env` și sursele beneficiarului trebuie să rămână locale. Nu introduce cheia OpenRouter în cod sau Git. Documentele și pasajele sunt trimise către furnizor numai în contextul analizei curente; politica de retenție a furnizorului trebuie verificată înainte de folosirea datelor neanonimizate.
