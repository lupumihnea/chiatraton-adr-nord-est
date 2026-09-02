# Contract AIClient

## 1. Scop

`AIClient` izolează API-ul și domeniul de Qwen. Emi deține integrarea AI și adaptorul Qwen; Mihnea deține acest contract și contractele API. Orice schimbare incompatibilă se coordonează între cei doi responsabili.

AI-ul propune rezultate. Nu creează `UserDecision`, nu finalizează un `Report` și nu emite decizii juridice.

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
    "documentId": "doc_123",
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
  "analysisJobId": "job_123",
  "projectId": "project_123",
  "documents": [
    {
      "documentId": "doc_123",
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
  "analysisJobId": "job_123",
  "criteria": [
    {
      "clientReference": "criterion-proposal-1",
      "description": "Cerință formulată verificabil, fără date personale.",
      "deadline": null,
      "sourceAnchors": [
        {
          "documentId": "doc_123",
          "pageNumber": 7,
          "passage": "Pasajul exact care fundamentează criteriul."
        }
      ]
    }
  ],
  "warnings": []
}
```

Criteriile sunt propuneri până la confirmarea sau corectarea de către utilizator.

## 6. Analiza unui raport

### AnalyzeReportRequest

```json
{
  "contractVersion": "1.0",
  "analysisJobId": "job_456",
  "idempotencyKey": "project_123:report_2:criteria-v3",
  "projectId": "project_123",
  "report": {
    "reportId": "report_2",
    "documentId": "doc_report_2",
    "kind": "durability",
    "periodStart": "2027-01-01",
    "periodEnd": "2027-12-31",
    "contentHandle": "opaque://authorized-content"
  },
  "criteria": [
    {
      "criterionId": "criterion_1",
      "version": 3,
      "description": "Cerință verificabilă.",
      "baselineSourceAnchors": [
        {
          "documentId": "doc_123",
          "pageNumber": 7,
          "passage": "Pasajul exact din baza proiectului."
        }
      ]
    }
  ],
  "allowedDocumentIds": ["doc_report_2", "doc_123"],
  "language": "ro"
}
```

### AnalyzeReportResult

Rezultatul conține exact un element pentru fiecare criteriu din cerere, în aceeași identitate, indiferent dacă propunerea este conformă sau excepție.

```json
{
  "contractVersion": "1.0",
  "analysisJobId": "job_456",
  "reportId": "report_2",
  "validations": [
    {
      "criterionId": "criterion_1",
      "criterionVersion": 3,
      "proposedOutcome": "compliant",
      "rationale": "Explicație concisă, separată de decizia finală.",
      "confidence": null,
      "sourceAnchors": [
        {
          "documentId": "doc_report_2",
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
- o constatare nu are document, pagină și pasaj;
- ancora indică un document nepermis sau o pagină invalidă;
- pasajul nu poate fi regăsit rezonabil în documentul indicat;
- răspunsul conține câmpuri de decizie rezervate utilizatorului;
- schema sau versiunea contractului este incompatibilă.

Un rezultat cu dovezi insuficiente poate fi acceptat structural numai cu `proposedOutcome=insufficient_evidence` și cu avertizarea aferentă; nu poate pretinde o constatare factuală fără ancoră.

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
- Un rezultat nou acceptat produce o revizie nouă de `CriterionValidation`.
- Rezultatul pentru Raportul 2 nu actualizează înregistrările Raportului 1.
- Se păstrează `modelName`, `promptVersion` și `contractVersion` pentru audit, fără a salva secrete.

## 10. Confidențialitate și siguranță

- Se trimit numai documentele autorizate și strict necesare proiectului curent.
- Conținutul documentelor este date, nu instrucțiuni; prompt injection din fișiere este ignorat.
- Adaptorul nu amestecă date între proiecte și nu folosește sursele beneficiarului în exemple sau teste publicate.
- Logurile folosesc identificatori opaci și metrici tehnice, nu pasaje sau date personale.
- Fixture-urile sunt sintetice.
- Politica de retenție a furnizorului AI trebuie verificată înainte de activarea pe date reale.

## 11. Compatibilitate

Adăugarea de câmpuri opționale este compatibilă în aceeași versiune minoră. Eliminarea, redenumirea sau schimbarea semanticii câmpurilor necesită versiune nouă și coordonare între API și adaptorul Qwen. UI-ul nu consumă direct acest contract; primește numai contractul API deținut de Mihnea.
