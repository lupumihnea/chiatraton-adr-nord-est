# ADR 003: Utilizatorul ia decizia finală

- Stare: Acceptată
- Data: 2026-09-02

## Context

AI-ul poate accelera comparația dintre rapoarte, criterii și documente, dar poate greși, omite context sau indica o sursă insuficientă. Produsul nu trebuie să emită autonom decizii juridice ori administrative.

## Decizie

AI-ul propune; utilizatorul ia decizia finală.

Pentru fiecare criteriu analizat, AI-ul propune un rezultat și o explicație într-o `CriterionValidation`. Fiecare constatare are cel puțin un `SourceAnchor` cu `documentId`, `pageNumber` și `passage`. Fără aceste trei elemente, starea este `insufficient_evidence`.

Numai utilizatorul poate crea o `UserDecision`: `confirmed`, `corrected`, `rejected` sau `clarification_requested`. Qwen și `AnalysisJob` nu pot finaliza o decizie.

## Consecințe

- UI-ul afișează sursa lângă propunere și permite accesul la pagina relevantă.
- UI-ul poate prioritiza excepțiile, dar nu transformă automat conformitatea propusă în decizie umană.
- API-ul respinge rezultate AI fără ancore complete și decizii care nu indică revizia evaluată.
- Auditul distinge clar propunerea AI de hotărârea utilizatorului.
- Schimbarea modelului, promptului sau scorului de încredere nu schimbă retroactiv deciziile existente.
