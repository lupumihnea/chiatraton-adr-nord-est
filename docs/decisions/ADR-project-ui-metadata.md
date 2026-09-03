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

`name` rămâne singurul câmp obligatoriu. UUID-ul `Project.id` rămâne
identitatea publică și este folosit în rutele API; codul SMIS este metadată
externă și poate fi folosit numai pentru căutare și afișare.

Extensia nu adaugă acces UI la baza de date. NiceGUI continuă să comunice
exclusiv prin HTTP, cu JWT și `Idempotency-Key` pentru operațiile POST.

## Consecințe

- clienții existenți pot omite noile câmpuri;
- răspunsurile `Project` includ noile chei, cu `null` dacă lipsesc;
- UI-ul poate păstra fluxul vizual bazat pe cod SMIS fără `mock_db`;
- nu se implementează sincronizare sau acțiuni oficiale în MyADR/MySMIS;
- exemplele și testele folosesc exclusiv valori sintetice.

## Amendament (2026-09-03): eliminarea `completionDate` și `monitoringEndDate`

Câmpurile `completionDate` și `monitoringEndDate`, obligatorii inițial pe
`ProjectCreate`/`Project`, sunt eliminate complet din contract la cererea
owner-ului. Nu aduceau valoare pentru fluxul curent al UI-ului și complicau
formularul de creare a proiectului.

Consecință directă: regula de business care respingea rapoartele cu
`periodEnd` ulterior lui `monitoringEndDate` (`app/services/default.py`,
`create_project_report`) este eliminată — perioada unui raport nu mai este
limitată de o dată de monitorizare la nivel de proiect. Dacă va fi nevoie de
o astfel de limită pe viitor, va necesita o decizie de contract separată.
