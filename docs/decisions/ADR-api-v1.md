# ADR API v1: Contract-first verification workspace

- Stare: Acceptată
- Data: 2026-09-02
- Owner: Mihnea - API și contracte

## Context

Vizita la ADR a confirmat că MyADR/MySMIS gestionează deja task-urile, prioritățile, distribuirea, validarea, autorizarea și clarificările oficiale. ChIAtraton trebuie să ajute utilizatorul să verifice un raport periodic selectat, nu să dubleze aceste sisteme.

Faza curentă definește numai contractele. Implementarea FastAPI și integrările cu SQLite, Qwen și NiceGUI sunt decizii și task-uri ulterioare.

## Decizie

### Limita produsului

API-ul v1 reprezintă fluxul:

`Project -> Document -> Criterion -> Report -> AnalysisJob -> CriterionValidation -> UserDecision`

Metadatele MyADR/MySMIS sunt read-only din perspectiva workflow-ului ChIAtraton. API-ul nu include endpoint-uri de sincronizare, autorizare, distribuire sau clarificare oficială.

### Identitate și securitate

- Resursele publice folosesc UUID strings, independent de ID-urile bazei de date.
- Toate endpoint-urile `/api/v1` folosesc Bearer JWT.
- `/health` este public și returnează numai starea minimală a serviciului.
- Emiterea tokenului rămâne în afara vertical slice-ului.

### Perioada de monitorizare

`Project.monitoringEndDate` este data contractuală explicită și trebuie să fie egală cu sau ulterioară `completionDate`. API-ul nu deduce data dintr-un număr implicit sau configurabil de ani.

### Raport și documente

Un `Report` poate asocia mai multe `Document`. Exact unul are rol primar, `main_report` sau `final_document`; celelalte pot avea rol `attachment` sau `clarification`.

Statusul intern `status` este un enum controlat de ChIAtraton. `externalStatus` este text opac și nu produce tranziții interne. `externalSystem`, `externalId` și `externalUrl` sunt metadate opționale pentru trasabilitate.

### Analiză și decizie

- Pornirea unui `AnalysisJob` răspunde cu `202 Accepted`.
- Toate criteriile active sunt capturate într-un snapshot.
- Documentele proiectului și rapoartele anterioare sunt selectate explicit.
- AI-ul produce câte o `CriterionValidation` per criteriu și revizie.
- Orice constatare factuală are `SourceAnchor` cu document, pagină și pasaj.
- `aiOutcome` și `UserDecision` sunt reprezentări distincte.
- Utilizatorul poate confirma, corecta sau respinge; comentariul nu pornește o clarificare oficială.

### Fiabilitate HTTP

- Toate operațiile POST cer `Idempotency-Key`.
- Replay-ul aceluiași request returnează răspunsul inițial.
- Refolosirea cheii cu alt payload produce `409`.
- Erorile folosesc RFC 9457 `application/problem+json`.
- Listele folosesc paginare cu cursor opac.

## Consecințe

- NiceGUI va consuma un contract stabil și nu va accesa direct DB sau Qwen.
- SQLite și viitorul PostgreSQL pot folosi ID-uri interne diferite de UUID-urile publice.
- Qwen rămâne ascuns în spatele `AIClient`.
- ChIAtraton nu poate crea impresia că statusul intern este o validare sau autorizare oficială.
- Istoricul rapoartelor, analizelor și deciziilor rămâne auditabil și nu este suprascris.
- Uploadurile v1 sunt limitate la PDF și formate Microsoft Word/Excel, maximum 50 MiB per fișier; fotografiile nu fac parte din acest slice.

## Alternative respinse

- Reutilizarea task-urilor MyADR/MySMIS: ar dubla un sistem existent și ar confunda autoritatea oficială.
- ID-uri publice întregi: ar cupla API-ul la schema SQLite legacy.
- Calcul automat `completionDate + X`: poate contrazice data contractuală aplicabilă proiectului.
- Includerea automată a tuturor rapoartelor anterioare: reduce reproductibilitatea și controlul asupra datelor trimise AI-ului.
- `clarification_requested` ca decizie ChIAtraton: ar putea fi interpretată ca inițiere a unui flux oficial.
- Idempotency numai pentru analiză: nu protejează uniform uploadurile, rapoartele și deciziile la retry.

## Criterii de acceptare

- OpenAPI 3.1 și documentația narativă descriu aceleași endpoint-uri și enum-uri.
- Exemplele sunt sintetice și valide față de scheme.
- Nicio modificare de contract nu atinge `Interface/`, `DAO/` sau `DataBase/`.
- Nu este introdus cod FastAPI și nu este implementată nicio integrare externă.
