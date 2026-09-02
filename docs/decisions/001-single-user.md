# ADR 001: Un singur actor de business

- Stare: Acceptată
- Data: 2026-09-02

## Context

Produsul are nevoie de un model de interacțiune clar pentru prima versiune. Introducerea prematură a rolurilor de beneficiar, evaluator, administrator sau aprobator ar multiplica permisiunile și fluxurile fără o cerință confirmată.

## Decizie

Există un singur actor de business: **utilizatorul**. Sistemul, API-ul și Qwen sunt componente tehnice, nu actori de business.

Utilizatorul configurează `Project`, gestionează `Document` și `Criterion`, încarcă `Report`, inspectează `CriterionValidation` și emite `UserDecision`.

Această decizie descrie rolul de business. Versiunea curentă nu introduce RBAC sau fluxuri de aprobare între roluri. Dacă vor exista mai multe conturi tehnice, ele nu dobândesc automat roluri de business diferite.

## Consecințe

- UI-ul poate avea un flux unic și o navigație simplă.
- Auditul păstrează identitatea tehnică din `decidedBy`, chiar dacă rolul de business este unic.
- Nu există auto-aprobare din partea AI-ului.
- Adăugarea viitoare a rolurilor sau aprobării în patru ochi necesită un ADR nou și o analiză de migrare.
