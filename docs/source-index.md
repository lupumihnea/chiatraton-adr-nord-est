# Indexul surselor și registrul contradicțiilor

## 1. Politica surselor

Sursele beneficiarului sunt păstrate local și excluse din Git. Acest index reține numai tipul sursei, rolul ei în analiză și concluzii generale necesare produsului. Nu include nume, adrese, identificatori, valori financiare, date de contact ori pasaje comerciale.

Ordinea de autoritate folosită la analiză este:

1. documente oficiale ADR și contractul aplicabil proiectului;
2. decizii explicite confirmate de product owner și mentor;
3. specificația și workflow-ul produsului;
4. contractele tehnice;
5. implementarea legacy.

## 2. Surse analizate

| Sursă locală | Tip | Utilizare sigură în contextul produsului |
|---|---|---|
| Manualul beneficiarului, ediția/revizia 2026 | document oficial, 62 pagini | tipuri și cadențe de rapoarte; verificarea documentelor; indicatori de etapă; raportare post-implementare; vizite de monitorizare |
| Anexa 2 - Raport de progres | formular oficial Word, 5 pagini | perioadă și număr de raport; progres; indicatori; criteriu de validare; termen; documente/dovezi; recomandări anterioare |
| Anexa 16 - Plan de monitorizare, exemplar anonimizat | formular PDF, 2 pagini | relația dintre indicator/criteriu, termen și documentele care probează îndeplinirea |
| Cerere de finanțare, exemplar pseudonimizat | PDF, 60 pagini | structură de proiect, documente atașate, obiective, indicatori, activități, calendar și durabilitate |
| Plan de afaceri, exemplar pseudonimizat | PDF, 93 pagini | sursă narativă și tabelară pentru criterii, justificări, rezultate și sustenabilitate |
| Anexe la planul de afaceri, exemplar pseudonimizat | PDF, 7 pagini | dovezi și tabele suport care trebuie ancorate separat de documentul principal |
| Grafic de rambursare, exemplar pseudonimizat | PDF, 1 pagină | exemplu de document cu repere calendaristice și tranșe |
| Plan de achiziții, exemplar pseudonimizat | două fișiere XLSX identice, o foaie fiecare | exemplu de sursă tabelară; duplicatele binar-identice nu trebuie ingerate de două ori |
| Diagramă workflow | imagine | separarea utilizator/sistem, validarea bazei inițiale, ciclul raportării și prioritizarea excepțiilor |

Referințe de pagină relevante din manual: rapoarte trimestriale și indicatori de etapă la paginile 40-42; raport final și rapoarte de durabilitate la paginile 42-44; vizite și perioada de durabilitate la paginile 45-46.

## 3. Concluzii convergente

- Proiectul este susținut de mai multe tipuri de documente, nu de un singur fișier.
- Criteriile au termene și documente/dovezi asociate.
- Rapoartele sunt recurente, iar tipul și perioada lor contează.
- Verificarea trebuie să compare raportul curent cu baza de monitorizare și cu dovezile.
- Istoricul și recomandările anterioare sunt relevante pentru raportul curent, fără a fi suprascrise.
- Raportarea din implementare și raportarea post-implementare pot avea cadențe diferite.

## 4. Contradicții și rezoluții

| ID | Tensiune observată | Rezoluție pentru produs | Urmărire necesară |
|---|---|---|---|
| C-01 | Diagrama de workflow închide monitorizarea după 3 ani, dar durata nu este universală. | Rezolvat prin eliminare: API-ul nu mai păstrează o dată de închidere a monitorizării (`monitoringEndDate` a fost scoasă din contract pe 2026-09-03); utilizatorul decide manual când se închide monitorizarea. | — |
| C-02 | Diagrama spune că utilizatorul verifică numai excepțiile; principiul de guvernanță cere decizie finală umană. | UI-ul poate prioritiza excepțiile, dar AI-ul nu creează `UserDecision`, iar un raport nu este finalizat prin acceptare AI implicită. | Teste de acceptare pentru finalizare și bulk review controlat. |
| C-03 | Manualul descrie perioada post-implementare conform contractului și rapoarte anuale calculate de la plata finală, în timp ce proiectele pot folosi repere diferite. | Rezolvat prin eliminare: `completionDate` și `monitoringEndDate` au fost scoase din `Project` pe 2026-09-03; produsul nu mai urmărește aceste date contractuale. | — |
| C-04 | „Rapoarte periodice” este generic; manualul distinge progres trimestrial, raport final și durabilitate anuală. | `Report.reportType` și perioada/cadența sunt explicite. Același mecanism de validare se aplică fiecărui raport. | Catalogul final de tipuri se confirmă în contractul API. |
| C-05 | Implementarea legacy folosește `obligations` și `references`, iar terminologia cerută este `Criterion` și `SourceAnchor`; lipsesc rapoarte și validări istorice. | Documentația și contractele noi folosesc terminologia canonică. Implementarea rămâne neschimbată în acest branch. | Migrare DB separată, coordonată cu Dragoș și Mihnea. |
| C-06 | Instrucțiunile repository-ului menționează generic `Task`; cerința curentă cere `AnalysisJob`. | Pentru procesarea AI și contractele noi se folosește `AnalysisJob`. | Aliniere într-un change set separat dacă apare cod legacy cu `Task`. |
| C-07 | Planul de achiziții este prezent de două ori cu conținut binar identic. | Ingestia trebuie să detecteze duplicate prin hash și să ceară confirmare înainte de asocierea dublă. | Caz de test pentru deduplicare. |

## 5. Necunoscute controlate

- Taxonomia completă a rezultatelor de validare și pragurile de încredere AI necesită confirmare de produs și evaluare pe date anonimizate.
- Politica de retenție și ștergere a documentelor trebuie definită separat, cu cerințe juridice și de securitate.

## 6. Regula de nepublicare

Sursele locale, extragerile, capturile și fișierele intermediare nu se comit. Exemplele din repository folosesc numai date sintetice. Dacă este necesar un caz de test derivat dintr-un document real, acesta se reduce la structură și se rescrie cu valori fictive înainte de review.
