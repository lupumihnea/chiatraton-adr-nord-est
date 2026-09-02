# ChIAtraton - ADR Nord-Est

ChIAtraton este un **AI Monitoring Copilot pentru ADR Nord-Est**. Aplicația ajută utilizatorul să monitorizeze proiecte finanțate, să compare fiecare raport periodic cu criteriile proiectului și să păstreze o urmă auditabilă a constatărilor.

AI-ul propune; utilizatorul ia decizia finală. Sistemul nu emite decizii juridice și nu înlocuiește verificarea umană.

## Principii de produs

- Există un singur actor de business: utilizatorul.
- Un `Project` are `Document` și `Criterion`.
- AI-ul extrage numai `CriterionProposal`; utilizatorul le acceptă, corectează
  sau respinge înainte ca un `Criterion` să fie creat.
- Extracția este append-only: nu șterge și nu înlocuiește criteriile existente,
  iar propunerile și review-urile rămân auditabile.
- Un `Project` primește `Report` periodice până la `monitoringEndDate`, data contractuală explicită.
- Fiecare `Criterion` este verificat separat pentru fiecare `Report`.
- O `CriterionValidation` aparține unui singur raport; validarea Raportului 2 nu o suprascrie pe cea a Raportului 1.
- Fiecare constatare AI include cel puțin un `SourceAnchor` cu document, pagină și pasaj.
- Orice rezultat AI devine final numai printr-o `UserDecision` explicită.
- Procesarea asincronă este reprezentată de `AnalysisJob`.

## Arhitectură și responsabilități

- Mihnea deține API-ul și contractele.
- Andrei deține UI/UX în NiceGUI.
- Emi deține AI-ul și integrarea Qwen.
- Dragoș deține SQLite și eventuala migrare la PostgreSQL.

UI-ul comunică numai prin API. API-ul accesează baza de date numai prin repository interfaces și accesează Qwen numai prin interfața `AIClient`. Numele modelului AI și adresa serviciului sunt configurabile; secretele nu intră în repository. ChIAtraton nu înlocuiește MyADR/MySMIS și nu execută task-uri, autorizări sau clarificări oficiale.

## Documentație

- [Specificația produsului](docs/product-spec.md)
- [Workflow](docs/workflow.md)
- [Modelul de date](docs/data-model.md)
- [Arhitectura](docs/architecture.md)
- [Indexul surselor și contradicțiilor](docs/source-index.md)
- [Contractul HTTP API v1](contracts/http-api.md)
- [OpenAPI 3.1](contracts/openapi.yaml)
- [Contractul AI](contracts/ai-contract.md)
- [Decizia pentru API v1](docs/decisions/ADR-api-v1.md)
- [Decizii de arhitectură](docs/decisions/)

## Starea implementării

`DAO/` și `DataBase/` reprezintă implementarea existentă. Ele nu sunt actualizate de acest set de documentație. Denumirile legacy precum `obligations` și `references` vor necesita ulterior o migrare controlată către terminologia `Criterion` și `SourceAnchor`, cu acordul responsabilului bazei de date.

## Confidențialitate

Documentele beneficiarului sunt surse locale de analiză și sunt excluse prin `.gitignore`. Nu se publică nume, adrese, identificatori, valori financiare, pasaje comerciale sau alte date sensibile. În produs, accesul la documente și la pasajele-sursă trebuie limitat la proiectul curent și auditat.
