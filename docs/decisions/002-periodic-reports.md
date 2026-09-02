# ADR 002: Rapoarte periodice și istoric independent

- Stare: Acceptată
- Data: 2026-09-02

## Context

Un proiect este urmărit în timp prin rapoarte de implementare, un raport final și rapoarte post-implementare. Sursele indică cadențe diferite, iar diagrama existentă folosește o durată fixă de 3 ani care nu este universală.

## Decizie

Un `Project` primește `Report` periodice până la `monitoringEndDate`, data contractuală explicită. API-ul nu deduce această dată dintr-o valoare `X`. Tipul, perioada și cadența unui raport sunt explicite.

Pentru fiecare `Report`, fiecare `Criterion` activ în snapshot este verificat separat și produce o `CriterionValidation`. Validarea Raportului 2 nu suprascrie validarea Raportului 1. Reanalizările creează revizii noi, iar deciziile rămân legate de revizia evaluată.

## Consecințe

- Modelul de date trebuie să includă `Report`, `CriterionValidation` și versiuni/snapshot-uri.
- Interogările pot reconstrui situația oricărui raport la momentul deciziei.
- Costul de stocare crește controlat în schimbul auditabilității.
- Contractul individual este sursa pentru durata și reperul calendaristic aplicabile; data rezultată este păstrată explicit.
- Migrarea schemei existente se face separat și numai cu acordul responsabilului DB.
