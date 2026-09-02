# Model de date conceptual

Acest document descrie modelul țintă. Nu modifică schema SQLite existentă din `DataBase/` și nu reprezintă încă o migrare.

## 1. Relații

```mermaid
erDiagram
    Project ||--o{ Document : contains
    Project ||--o{ Criterion : defines
    Project ||--o{ AnalysisJob : starts
    Project ||--o{ Report : receives
    Report ||--|{ ReportDocument : groups
    Document ||--o{ ReportDocument : associated_as
    Report ||--o{ CriterionValidation : has
    Criterion ||--o{ CriterionValidation : checked_in
    CriterionValidation ||--|{ SourceAnchor : supported_by
    Document ||--o{ SourceAnchor : anchors
    CriterionValidation ||--o{ UserDecision : reviewed_by
    Report ||--o{ AnalysisJob : analyzed_by
    AnalysisJob ||--o{ CriterionProposal : produces
    CriterionProposal ||--o| CriterionProposalReview : reviewed_as
    CriterionProposalReview ||--o| Criterion : may_create
```

## 2. Entități

### Project

- `id`
- `name`
- `fundingCallId`
- `completionDate`
- `monitoringEndDate` - data contractuală explicită, egală cu sau ulterioară `completionDate`
- `status`
- `createdAt`, `updatedAt`

Un `Project` are documente, criterii și rapoarte. Data-limită trebuie validată față de contractul aplicabil înainte de utilizarea operațională.

### Document

- `id`
- `projectId`
- `kind`
- `originalFilename`
- `storageKey`
- `mediaType`
- `sha256`
- `pageCount`
- `createdAt`

Conținutul documentului nu se duplică în loguri sau metadate. `storageKey` este opac și nu expune căi locale.

### Criterion

- `id`
- `projectId`
- `version`
- `code`
- `description`
- `deadline`
- `severity`
- `activeFrom`, `activeTo`
- `sourceAnchorIds`

Un criteriu este versionat. Termenul canonic pentru contracte noi este `Criterion`; `obligation` rămâne doar denumire legacy până la o migrare separată.

### CriterionProposal

- `id`
- `analysisJobId`
- `projectId`
- `revision`
- `proposedCode`
- `proposedDescription`
- `proposedDeadline`, opțional
- `sourceAnchorIds` - cel puțin o ancoră completă
- `createdAt`

`CriterionProposal` este rezultatul auditabil al AI-ului și nu este
`Criterion`. O extracție nouă adaugă propuneri noi; nu șterge, nu înlocuiește
și nu dezactivează criteriile sau propunerile existente.

### CriterionProposalReview

- `id`
- `criterionProposalId`
- `proposalRevision`
- `action` - `accept`, `correct` sau `reject`
- `correction`, obligatorie pentru `correct`
- `comment`, obligatoriu pentru `correct` și `reject`
- `createdCriterionId`, prezent numai pentru `accept` și `correct`
- `reviewedBy`, `reviewedAt`

Review-ul este decizia utilizatorului asupra propunerii, nu un rezultat AI.
Este append-only și rămâne legat de versiunea exactă a propunerii. `accept` și
`correct` creează un criteriu nou; `reject` nu creează criteriu.

### Report

- `id`
- `projectId`
- `sequenceNumber`
- `reportType` - `implementation_progress`, `final_progress` sau `durability`
- `periodStart`, `periodEnd`
- `criterionSetVersion`
- `status` - stare internă controlată de ChIAtraton
- `externalSystem`, `externalId`, `externalUrl`, `externalStatus`, opționale
- `createdAt`, `finalizedAt`

`sequenceNumber` este unic în cadrul proiectului. Raportul capturează versiunea criteriilor folosită la analiză. `externalStatus` este text opac și nu produce tranziții ale statusului intern.

### ReportDocument

- `reportId`
- `documentId`
- `role` - `main_report`, `final_document`, `attachment` sau `clarification`

Asocierea este unică pentru perechea (`reportId`, `documentId`). Fiecare raport are exact un document primar: `main_report` sau `final_document`; celelalte documente sunt suport. Toate documentele asociate aparțin proiectului raportului.

### SourceAnchor

- `id`
- `documentId`
- `pageNumber`
- `passage`
- `chapter` și `section`, opțional
- `locatorVersion`

`pageNumber` este pozitiv, iar `passage` este nenul și nevid. Un hash al pasajului poate ajuta la detectarea modificării documentului, dar nu înlocuiește pasajul auditabil.

### CriterionValidation

- `id`
- `reportId`
- `criterionId`
- `criterionVersion`
- `revision`
- `aiOutcome`
- `aiConfidence`, opțional și calibrat
- `aiRationale`
- `status`
- `sourceAnchorIds`
- `analysisJobId`
- `createdAt`

Identitatea logică este (`reportId`, `criterionId`, `revision`). O validare nu se mută între rapoarte. Reviziile noi se adaugă; cele vechi rămân accesibile.

### UserDecision

- `id`
- `criterionValidationId`
- `action`
- `finalOutcome`, obligatoriu numai când acțiunea este `correct`
- `comment`, obligatoriu pentru `correct` și `reject`
- `decidedBy`
- `decidedAt`

Decizia aparține unei revizii precise de `CriterionValidation`. Acțiunea este `confirm`, `correct` sau `reject`. AI-ul nu poate crea `UserDecision`, iar decizia nu pornește o clarificare oficială în MyADR/MySMIS.

### AnalysisJob

- `id`
- `projectId`
- `reportId`, opțional pentru extracția inițială de criterii
- `kind` - `extract_criteria` sau `analyze_report`
- `documentIds` - documentele selectate pentru extracție
- `proposalCount`, relevant pentru extracție
- `status`
- `idempotencyKey`
- `modelName`
- `modelEndpointLabel` - etichetă neconfidențială, nu secret
- `promptVersion`, `contractVersion`
- `startedAt`, `completedAt`
- `errorCode`, fără conținut sensibil

## 3. Constrângeri

1. Toate entitățile operaționale sunt limitate la același `projectId`.
2. Pentru fiecare `Report` și fiecare `Criterion` din snapshot există cel puțin o `CriterionValidation` înainte de finalizare.
3. Fiecare constatare dintr-o validare are unul sau mai multe `SourceAnchor` complete.
4. Un `SourceAnchor.documentId` trebuie să indice un document al aceluiași proiect.
5. O `UserDecision` nu poate indica o validare ștearsă sau o altă revizie decât cea afișată utilizatorului.
6. Validările și deciziile finalizate sunt append-only; corecțiile creează înregistrări noi legate de cele anterioare.
7. Un `AnalysisJob.idempotencyKey` este unic în domeniul operației sale.
8. Statusul intern al raportului este independent de `externalStatus`.
9. Fiecare `CriterionProposal` are cel puțin un `SourceAnchor` complet din documentele jobului său.
10. Un job de extracție și review-urile sale nu fac update sau delete asupra criteriilor existente.
11. O propunere are un singur review final; replay-ul idempotent returnează același rezultat.

## 4. Păstrarea istoricului

Raportul 1 și Raportul 2 au identificatori diferiți și seturi diferite de validări. Un `UPDATE` asupra validării Raportului 1 nu este mecanismul de salvare a rezultatului Raportului 2. Același principiu se aplică reanalizărilor și deciziilor corective.

Același principiu append-only se aplică extracției: joburile,
`CriterionProposal` și `CriterionProposalReview` rămân disponibile pentru audit
după acceptare, corectare sau respingere.

## 5. Mapare legacy, fără implementare în acest branch

| Implementare existentă | Concept țintă | Observație |
|---|---|---|
| `projects` / `ProjectDAO` | `Project` | Lipsește `monitoringEndDate` contractual explicit și istoricul rapoartelor. |
| `documents` / `DocumentDAO` | `Document` | Relația cu `Project` trebuie proiectată într-o migrare ulterioară. |
| `obligations` / `ObligationDAO` | `Criterion` | Pentru contracte noi se folosește `criteria`. |
| `references` / `ReferenceDAO` | `SourceAnchor` | Câmpurile pagină și text oferă o bază, dar constrângerile obligatorii trebuie întărite ulterior. |
| fără echivalent | `Report`, `CriterionProposal`, `CriterionProposalReview`, `CriterionValidation`, `UserDecision`, `AnalysisJob` | Necesită design DB și migrare aprobate de responsabilul DB. |
