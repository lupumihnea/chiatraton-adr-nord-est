# ADR: Metadate Project pentru compatibilitatea UI

- Stare: Acceptată
- Data: 2026-09-03
- Owner: Mihnea - API și contracte

## Context

Ultimul UI NiceGUI furnizat de Andrei folosește codul SMIS, identificatorul
apelului de finanțare și numele beneficiarului. Contractul API v1 expunea doar
numele proiectului și datele contractuale, astfel încât interfața nu putea
trimite aceste valori fără a încălca OpenAPI.

## Decizie

`ProjectCreate` și `Project` primesc aditiv câmpurile opționale:

- `smisCode`: șir de exact șase cifre;
- `fundingCallId`: număr întreg pozitiv;
- `beneficiaryName`: șir de 1-200 caractere.

`name`, `completionDate` și `monitoringEndDate` rămân obligatorii. UUID-ul
`Project.id` rămâne identitatea publică și este folosit în rutele API; codul
SMIS este metadată externă și poate fi folosit numai pentru căutare și afișare.

Extensia nu adaugă acces UI la baza de date. NiceGUI continuă să comunice
exclusiv prin HTTP, cu JWT și `Idempotency-Key` pentru operațiile POST.

## Consecințe

- clienții existenți pot omite noile câmpuri;
- răspunsurile `Project` includ noile chei, cu `null` dacă lipsesc;
- UI-ul poate păstra fluxul vizual bazat pe cod SMIS fără `mock_db`;
- nu se implementează sincronizare sau acțiuni oficiale în MyADR/MySMIS;
- exemplele și testele folosesc exclusiv valori sintetice.
