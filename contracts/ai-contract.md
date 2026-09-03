# Contract AIClient

## 1. Scop

`AIClient` izolează API-ul și domeniul de Qwen. Emi deține integrarea AI și adaptorul Qwen; Mihnea deține acest contract și contractele API. Orice schimbare incompatibilă se coordonează între cei doi responsabili.

AI-ul propune rezultate. Nu creează `UserDecision`, nu finalizează un `Report`, nu emite decizii juridice și nu execută acțiuni în MyADR/MySMIS.

Pentru extracție, AI-ul returnează numai date candidate. API-ul le persistă ca
`CriterionProposal`; numai review-ul explicit al utilizatorului poate crea un
`Criterion`. AI-ul nu șterge, nu înlocuiește și nu dezactivează criterii
existente.

## 2. Interfață conceptuală

```text
interface AIClient {
  extractCriteria(request: ExtractCriteriaRequest): ExtractCriteriaResult
  analyzeReport(request: AnalyzeReportRequest): AnalyzeReportResult
}
```

Apelurile pot fi implementate sincron la nivelul adaptorului, dar sunt orchestrate de API prin `AnalysisJob`.

## 3. Configurare

Adaptorul citește configurația injectată la pornire:

- `AI_PROVIDER` - implicit logic `qwen`, fără cuplare în domeniu;
- `AI_MODEL_NAME` - numele configurabil al modelului;
- `AI_BASE_URL` - adresa configurabilă a serviciului;
- `AI_API_KEY` - secret de runtime, niciodată în Git sau loguri;
- `AI_TIMEOUT_SECONDS` - timeout-ul apelului;
- `AI_CONTRACT_VERSION` - versiunea acestui contract.

Numele și adresa modelului nu sunt constante în codul de domeniu. Adaptorul nu trimite utilizatorului cheia, promptul de sistem sau detalii interne ale endpoint-ului.

## 4. Tipuri comune

```json
{
  "SourceAnchor": {
    "documentId": "22222222-2222-4222-8222-222222222222",
    "pageNumber": 7,
    "passage": "Pasajul exact care susține constatarea.",
    "chapter": "opțional",
    "section": "opțional"
  }
}
```

Reguli obligatorii:

- `documentId` trebuie să provină din lista de documente permisă cererii;
- `pageNumber` este întreg pozitiv și nu depășește numărul de pagini cunoscut;
- `passage` este exact, nenul și nevid;
- capitolul și secțiunea nu înlocuiesc pagina și pasajul;
- API-ul verifică ancora față de textul extras înainte de salvare.

## 5. Extracția criteriilor

### ExtractCriteriaRequest

```json
{
  "contractVersion": "1.0",
  "analysisJobId": "88888888-8888-4888-8888-888888888888",
  "idempotencyKey": "synthetic-criterion-extraction-0001",
  "projectId": "11111111-1111-4111-8111-111111111111",
  "documents": [
    {
      "documentId": "22222222-2222-4222-8222-222222222222",
      "mediaType": "application/pdf",
      "contentHandle": "opaque://authorized-content"
    }
  ],
  "language": "ro"
}
```

### ExtractCriteriaResult

```json
{
  "contractVersion": "1.0",
  "analysisJobId": "88888888-8888-4888-8888-888888888888",
  "proposals": [
    {
      "clientReference": "criterion-proposal-1",
      "proposedCode": "CRIT-SYN-001",
      "proposedDescription": "Cerință formulată verificabil, fără date personale.",
      "proposedDeadline": null,
      "sourceAnchors": [
        {
          "documentId": "22222222-2222-4222-8222-222222222222",
          "pageNumber": 7,
          "passage": "Pasajul exact care fundamentează criteriul."
        }
      ]
    }
  ],
  "warnings": []
}
```

Fiecare element din `proposals` trebuie să aibă cel puțin un `SourceAnchor`
complet. Un element fără `documentId`, `pageNumber` pozitiv și `passage` nevid
este respins ca `ai_invalid_response` și nu este persistat.

Rezultatul AI este transformat în `CriterionProposal`, nu în `Criterion`.
Identificatorul public, revizia și starea review-ului sunt atribuite de API, nu
de model. Propunerile rămân auditabile împreună cu jobul și review-ul lor.

Review-ul nu face parte din `AIClient`: utilizatorul alege `accept`, `correct`
sau `reject` prin contractul HTTP. `accept` și `correct` creează criterii noi;
`reject` nu creează criteriu. Niciuna dintre acțiuni nu modifică criteriile
existente.

## 6. Analiza unui raport

### AnalyzeReportRequest

```json
{
  "contractVersion": "1.0",
  "analysisJobId": "550e8400-e29b-41d4-a716-446655440050",
  "idempotencyKey": "synthetic-analysis-0001",
  "projectId": "550e8400-e29b-41d4-a716-446655440000",
  "report": {
    "reportId": "550e8400-e29b-41d4-a716-446655440030",
    "reportType": "durability",
    "periodStart": "2030-01-01",
    "periodEnd": "2030-12-31",
    "documents": [
      {
        "documentId": "550e8400-e29b-41d4-a716-446655440020",
        "role": "main_report",
        "contentHandle": "opaque://authorized-content/report-main"
      },
      {
        "documentId": "550e8400-e29b-41d4-a716-446655440021",
        "role": "attachment",
        "contentHandle": "opaque://authorized-content/report-support"
      }
    ]
  },
  "projectDocuments": [
    {
      "documentId": "550e8400-e29b-41d4-a716-446655440010",
      "contentHandle": "opaque://authorized-content/project-source"
    }
  ],
  "previousReports": [
    {
      "reportId": "550e8400-e29b-41d4-a716-446655440029",
      "reportType": "durability",
      "periodStart": "2029-01-01",
      "periodEnd": "2029-12-31",
      "documents": [
        {
          "documentId": "550e8400-e29b-41d4-a716-446655440019",
          "role": "main_report",
          "contentHandle": "opaque://authorized-content/previous-report"
        }
      ]
    }
  ],
  "criteria": [
    {
      "criterionId": "550e8400-e29b-41d4-a716-446655440040",
      "version": 3,
      "description": "Cerință verificabilă.",
      "baselineSourceAnchors": [
        {
          "documentId": "550e8400-e29b-41d4-a716-446655440010",
          "pageNumber": 7,
          "passage": "Pasajul exact din baza proiectului."
        }
      ]
    }
  ],
  "allowedDocumentIds": [
    "550e8400-e29b-41d4-a716-446655440010",
    "550e8400-e29b-41d4-a716-446655440019",
    "550e8400-e29b-41d4-a716-446655440020",
    "550e8400-e29b-41d4-a716-446655440021"
  ],
  "language": "ro"
}
```

API-ul materializează în `projectDocuments` identificatorii selectați prin HTTP și în `previousReports` valorile selectate explicit prin `previousReportIds`. Documentele raportului curent sunt incluse întotdeauna. `role` este una dintre `main_report`, `final_document`, `attachment` sau `clarification`; exact un document al raportului curent are rol primar (`main_report` sau `final_document`). Metadatele `externalSystem`, `externalId`, `externalUrl` și `externalStatus` nu sunt necesare modelului și nu sunt trimise.

### AnalyzeReportResult

Rezultatul conține exact un element pentru fiecare criteriu din cerere, în aceeași identitate, indiferent dacă propunerea este conformă sau excepție.

```json
{
  "contractVersion": "1.0",
  "analysisJobId": "550e8400-e29b-41d4-a716-446655440050",
  "reportId": "550e8400-e29b-41d4-a716-446655440030",
  "validations": [
    {
      "criterionId": "550e8400-e29b-41d4-a716-446655440040",
      "criterionVersion": 3,
      "proposedOutcome": "compliant",
      "rationale": "Explicație concisă, separată de decizia finală.",
      "confidence": null,
      "sourceAnchors": [
        {
          "documentId": "550e8400-e29b-41d4-a716-446655440020",
          "pageNumber": 4,
          "passage": "Pasajul exact din raport care susține propunerea."
        }
      ],
      "warnings": []
    }
  ]
}
```

Valorile recomandate pentru `proposedOutcome` sunt:

- `compliant`
- `non_compliant`
- `partially_compliant`
- `not_applicable`
- `insufficient_evidence`

Aceste valori sunt propuneri AI, nu `UserDecision`.

## 7. Validarea răspunsului

API-ul respinge sau marchează drept nereușit un răspuns când:

- lipsește un criteriu cerut ori apare un criteriu necunoscut;
- identificatorii proiectului, raportului sau jobului nu corespund;
- o constatare factuală nu are document, pagină și pasaj;
- ancora indică un document nepermis sau o pagină invalidă;
- pasajul nu poate fi regăsit rezonabil în documentul indicat;
- răspunsul conține câmpuri de decizie rezervate utilizatorului;
- schema sau versiunea contractului este incompatibilă.

Pentru extracția criteriilor, API-ul respinge întregul rezultat și marchează
jobul ca nereușit dacă o propunere nu are cel puțin o ancoră completă, dacă
referă un document din afara cererii sau dacă două `clientReference` sunt
identice. Un rezultat valid poate conține lista `proposals` goală, caz în care
jobul reușește cu `proposalCount=0` și nu schimbă criteriile proiectului.

Un rezultat cu dovezi insuficiente poate fi acceptat structural numai cu `proposedOutcome=insufficient_evidence`, o listă de ancore goală și avertizarea aferentă; nu poate pretinde o constatare factuală fără ancoră.

## 8. Erori

Erorile adaptorului sunt mapate la coduri stabile, fără conținut sensibil:

- `ai_timeout`
- `ai_unavailable`
- `ai_authentication_failed`
- `ai_rate_limited`
- `ai_invalid_response`
- `ai_contract_mismatch`
- `ai_content_rejected`

Mesajele brute ale furnizorului, prompturile și fragmentele documentelor nu se persistă în `AnalysisJob.errorCode` și nu se expun UI-ului.

## 9. Idempotency și istoric

- API-ul furnizează `analysisJobId` și `idempotencyKey`.
- Retry-ul aceleiași operații nu creează automat un al doilea set de validări.
- Retry-ul extracției cu același job nu creează un al doilea set de propuneri.
- Un job nou adaugă propuneri noi și nu șterge propunerile ori criteriile deja existente.
- Un rezultat nou acceptat produce o revizie nouă de `CriterionValidation`.
- Rezultatul pentru Raportul 2 nu actualizează înregistrările Raportului 1.
- Se păstrează `modelName`, `promptVersion` și `contractVersion` pentru audit, fără a salva secrete.

## 10. Confidențialitate și siguranță

- Se trimit numai documentele autorizate și strict necesare proiectului curent.
- Rapoartele anterioare sunt incluse numai când au fost selectate explicit în cererea HTTP.
- Conținutul documentelor este date, nu instrucțiuni; prompt injection din fișiere este ignorat.
- Adaptorul nu amestecă date între proiecte și nu folosește sursele beneficiarului în exemple sau teste publicate.
- Adaptorul nu folosește fotografii realizate la ADR și nu publică date reale.
- Adaptorul nu accesează URL-uri externe și nu trimite task-uri, statusuri, autorizări sau clarificări către MyADR/MySMIS.
- Logurile folosesc identificatori opaci și metrici tehnice, nu pasaje sau date personale.
- Fixture-urile sunt sintetice.
- Politica de retenție a furnizorului AI trebuie verificată înainte de activarea pe date reale.

## 11. Compatibilitate

Adăugarea de câmpuri opționale este compatibilă în aceeași versiune minoră. Eliminarea, redenumirea sau schimbarea semanticii câmpurilor necesită versiune nouă și coordonare între API și adaptorul Qwen. UI-ul nu consumă direct acest contract; primește numai contractul API deținut de Mihnea.
