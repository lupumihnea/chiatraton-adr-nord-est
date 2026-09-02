# Contract HTTP API v1

## 1. Scop și limite

API-ul v1 oferă vertical slice-ul necesar unui AI verification workspace:

`Project -> Document -> Criterion -> Report -> AnalysisJob -> CriterionValidation -> UserDecision`

ChIAtraton nu înlocuiește MyADR/MySMIS. API-ul nu distribuie task-uri, nu schimbă priorități oficiale, nu autorizează rapoarte și nu trimite clarificări. Metadatele externe sunt păstrate exclusiv pentru trasabilitate.

Contractul normativ machine-readable este `contracts/openapi.yaml`. Acest document explică semantica pe care schema singură nu o poate reda suficient.

## 2. Convenții

- Base path: `/api/v1`; `GET /health` rămâne în afara versiunii și este public.
- Media type JSON: `application/json`.
- Erori: `application/problem+json`, conform RFC 9457.
- Autentificare: Bearer JWT pe toate operațiile `/api/v1`.
- ID-uri publice: UUID strings. ID-urile SQLite nu sunt expuse.
- Date calendaristice: `YYYY-MM-DD`.
- Timestamps: RFC 3339 în UTC.
- Câmpurile necunoscute din request sunt respinse.
- Listele sunt paginate prin cursor opac: `limit` implicit 50, maxim 100.
- URL-urile externe acceptă numai `https` sau `http`; API-ul nu le accesează automat.

## 3. Autentificare

Clientul trimite:

```http
Authorization: Bearer <token>
```

Emiterea și reînnoirea tokenului nu fac parte din acest vertical slice. Tokenul identifică utilizatorul tehnic pentru audit, fără a introduce roluri de business suplimentare.

`GET /health` nu cere autentificare și nu expune informații despre DB, modelul AI, secrete sau documente.

## 4. Idempotency

Toate operațiile POST cer headerul `Idempotency-Key`, cu 1-255 caractere. Cheia este evaluată în domeniul utilizatorului autentificat, metodei și rutei.

- Aceeași cheie și același payload semantic returnează statusul și corpul răspunsului inițial.
- Replay-ul adaugă `Idempotency-Replayed: true`.
- Aceeași cheie cu alt payload produce `409 idempotency_conflict`.
- Pentru upload, fingerprint-ul include metadatele și hash-ul conținutului fișierului.
- O cheie nouă la pornirea analizei poate crea o revizie nouă; nu suprascrie validările anterioare.

## 5. Paginare

Endpoint-urile de listare acceptă:

- `limit`: integer între 1 și 100, implicit 50;
- `cursor`: string opac primit din răspunsul anterior.

Răspunsul comun este:

```json
{
  "items": [],
  "nextCursor": null
}
```

Clienții nu parsează și nu construiesc cursorul.

## 6. Endpoint-uri

| Metodă | Rută | Succes | Rol |
|---|---|---:|---|
| GET | `/health` | 200 | verificare publică minimală |
| POST | `/api/v1/projects` | 201 | creare proiect |
| GET | `/api/v1/projects` | 200 | listare proiecte |
| POST | `/api/v1/projects/{projectId}/documents` | 201 | upload document |
| POST | `/api/v1/projects/{projectId}/criteria` | 201 | creare criteriu |
| GET | `/api/v1/projects/{projectId}/criteria` | 200 | listare criterii |
| POST | `/api/v1/projects/{projectId}/reports` | 201 | creare raport și asociere documente |
| GET | `/api/v1/projects/{projectId}/reports` | 200 | listare rapoarte |
| POST | `/api/v1/reports/{reportId}/analysis-jobs` | 202 | pornire analiză asincronă |
| GET | `/api/v1/analysis-jobs/{jobId}` | 200 | citire stare analiză |
| GET | `/api/v1/reports/{reportId}/validations` | 200 | citire validări și decizii |
| POST | `/api/v1/validations/{validationId}/decisions` | 201 | salvare decizie umană |

Răspunsurile de creare includ `Location` spre resursa creată.

## 7. Project

### ProjectCreate

- `name`: 1-200 caractere;
- `completionDate`: data finalizării proiectului;
- `monitoringEndDate`: data contractuală explicită până la care pot exista rapoarte, egală cu sau ulterioară `completionDate`.

API-ul nu calculează `monitoringEndDate` dintr-un număr de ani. O dată contractuală schimbată ulterior va necesita un endpoint și o decizie de contract separate.

### Project

Adaugă `id`, `createdAt` și `updatedAt`.

## 8. Document

Uploadul folosește `multipart/form-data` cu:

- `file`: obligatoriu;
- `displayName`: opțional, maximum 255 caractere.

Tipuri acceptate:

- `application/pdf`;
- `application/msword`;
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`;
- `application/vnd.ms-excel`;
- `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.

Dimensiunea maximă este 50 MiB (52.428.800 bytes) per fișier. Depășirea limitei produce `413 payload_too_large`; un tip neacceptat produce `415 unsupported_media_type`.

Răspunsul `Document` conține `id`, `projectId`, `displayName`, `originalFilename`, `mediaType`, `sizeBytes`, `sha256`, `pageCount` nullable și `createdAt`. Rolul documentului într-un raport nu aparține resursei `Document`; el este stabilit pe asocierea `ReportDocument`.

## 9. Criterion

### CriterionCreate

- `code`: 1-100 caractere, unic în proiect;
- `description`: 1-4000 caractere;
- `deadline`: dată opțională;
- `sourceAnchors`: listă opțională de ancore către documente ale aceluiași proiect.

### Criterion

Adaugă `id`, `projectId`, `version`, `active`, `createdAt` și `updatedAt`. Crearea produce versiunea 1. Actualizarea și dezactivarea criteriilor nu fac parte din vertical slice.

## 10. Report

### ReportCreate

- `reportType`: `implementation_progress`, `final_progress` sau `durability`;
- `periodStart`, `periodEnd`, cu `periodEnd >= periodStart`;
- `documents`: listă nevidă de asocieri `documentId` + `role`;
- `externalSystem`: opțional, `myadr`, `mysmis` sau `other`;
- `externalId`, `externalUrl`, `externalStatus`: opționale și permise numai împreună cu `externalSystem`.

Rolurile documentelor sunt:

- `main_report`;
- `final_document`;
- `attachment`;
- `clarification`.

Fiecare raport are exact un document primar: un singur `main_report` sau un singur `final_document`. Celelalte documente sunt suport. Același `documentId` nu poate apărea de două ori și toate documentele trebuie să aparțină proiectului raportului.

Perechea (`externalSystem`, `externalId`) este unică în proiect când ambele valori există. `externalStatus` este text opac și nu schimbă automat `status`.

### Status intern

- `created`: raportul a fost înregistrat;
- `analysis_queued`: există un job în coadă;
- `analysis_in_progress`: analiza rulează;
- `awaiting_user_decision`: analiza s-a încheiat și există validări de revizuit;
- `completed`: toate validările cerute au o decizie finală;
- `analysis_failed`: ultimul job a eșuat; raportul poate fi reanalizat.

## 11. AnalysisJob

### AnalysisJobCreate

- `projectDocumentIds`: listă de documente de context ale aceluiași proiect, implicit goală;
- `previousReportIds`: listă de rapoarte anterioare ale aceluiași proiect, implicit goală.

Documentele asociate raportului curent sunt incluse întotdeauna. Serverul capturează snapshot-ul tuturor criteriilor active în momentul creării jobului. Rapoartele anterioare nu sunt incluse implicit și trebuie selectate explicit pentru reproductibilitate.

Crearea răspunde cu `202 Accepted`, `Location: /api/v1/analysis-jobs/{jobId}` și un `AnalysisJob` în starea `queued`.

### AnalysisJob

Stările sunt `queued`, `running`, `succeeded`, `failed` și `cancelled`. Resursa conține `id`, `reportId`, selecțiile de context, `criteriaSnapshotVersion`, timestamps și, pentru eșec, o eroare sigură cu `code` și `message`. Mesajul nu include răspunsul brut al furnizorului, prompturi sau conținut din documente.

Un job este respins cu `409 invalid_report_state` dacă raportul nu poate fi analizat sau cu `409 no_active_criteria` dacă proiectul nu are criterii active.

## 12. CriterionValidation și SourceAnchor

Lista validărilor returnează implicit ultima revizie pentru fiecare criteriu. `includeHistory=true` include toate reviziile în ordine descrescătoare.

`CriterionValidation` conține:

- `id`, `reportId`, `criterionId`, `criterionVersion`;
- `analysisJobId` și `revision`;
- `status`: `awaiting_user_decision`, `decided`, `insufficient_evidence` sau `analysis_failed`;
- `aiOutcome` și `aiRationale`;
- `sourceAnchors`;
- `userDecision`, nullable.

`aiOutcome` este una dintre:

- `compliant`;
- `non_compliant`;
- `partially_compliant`;
- `not_applicable`;
- `insufficient_evidence`.

AI outcome și decizia utilizatorului sunt câmpuri diferite. Orice outcome factual are cel puțin un `SourceAnchor` cu:

- `documentId` din contextul jobului;
- `pageNumber` întreg pozitiv;
- `passage` exact și nevid.

`insufficient_evidence` poate avea o listă goală de ancore, deoarece nu afirmă o constatare factuală.

## 13. UserDecision

### UserDecisionCreate

- `action`: `confirm`, `correct` sau `reject`;
- `validationRevision`: revizia pe care utilizatorul a văzut-o;
- `finalOutcome`: obligatoriu numai pentru `correct` și interzis pentru `confirm` sau `reject`;
- `comment`: obligatoriu și nevid pentru `correct` și `reject`, opțional pentru `confirm`.

La `confirm`, rezultatul final este outcome-ul AI. La `correct`, rezultatul final este `finalOutcome`. La `reject`, nu există un outcome final acceptat.

O revizie modificată între citire și decizie produce `409 stale_validation_revision`. În v1 există o singură decizie curentă per revizie; o a doua decizie pe aceeași revizie produce `409 decision_already_exists`.

Decizia nu creează task, autorizare sau clarificare externă. Comentariul poate recomanda utilizatorului un follow-up în MyADR/MySMIS, fără efect automat.

## 14. Format comun de eroare

Toate erorile folosesc `application/problem+json`:

```json
{
  "type": "https://chiatraton.example/problems/validation-error",
  "title": "Request validation failed",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "instance": "/api/v1/projects",
  "code": "validation_error",
  "requestId": "req_01J00000000000000000000000",
  "errors": [
    {
      "field": "monitoringEndDate",
      "code": "date_order",
      "message": "monitoringEndDate must be on or after completionDate."
    }
  ]
}
```

Coduri comune:

- `authentication_required` - 401;
- `rate_limited` - 429;
- `resource_not_found` - 404;
- `idempotency_conflict` - 409;
- `invalid_report_state` - 409;
- `no_active_criteria` - 409;
- `stale_validation_revision` - 409;
- `decision_already_exists` - 409;
- `payload_too_large` - 413;
- `unsupported_media_type` - 415;
- `validation_error` - 422;
- `internal_error` - 500;
- `ai_unavailable` - 503.

## 15. Exemple sintetice

Fișierele din `contracts/examples/` sunt exemple normative de payload, fără date ADR reale:

| Fișier | Schemă OpenAPI |
|---|---|
| `project-create.request.json` | `ProjectCreate` |
| `project-create.response.json` | `Project` |
| `document-upload.response.json` | `Document` |
| `criterion-create.request.json` | `CriterionCreate` |
| `criterion-create.response.json` | `Criterion` |
| `report-create.request.json` | `ReportCreate` |
| `report-create.response.json` | `Report` |
| `analysis-job-create.request.json` | `AnalysisJobCreate` |
| `analysis-job.accepted.json` | `AnalysisJob` în starea `queued` |
| `analysis-job.succeeded.json` | `AnalysisJob` în starea `succeeded` |
| `validations-list.response.json` | `PaginatedValidations` |
| `user-decision-create.request.json` | `UserDecisionCreate` |
| `user-decision.response.json` | `UserDecision` |
| `problem.response.json` | `ProblemDetails` |

Uploadul este `multipart/form-data`; de aceea este reprezentat numai răspunsul JSON, nu conținutul binar al requestului.

## 16. Confidențialitate

- Exemplele API sunt integral sintetice.
- Fotografii realizate la ADR și date reale nu sunt încărcate, copiate sau publicate.
- Numele originale pot exista în resursa autorizată `Document`, dar nu apar în loguri ori erori.
- `externalUrl` este metadată; serverul nu o accesează și nu transmite automat date către sistemul extern.
- `SourceAnchor.passage` este returnat numai utilizatorului autentificat în contextul proiectului.
