# ADR: CriterionExtractor/ReportAnalyzer peste OpenRouter

- Stare: **Suprascrisă** (vezi Amendament) — implementarea nu a fost păstrată
- Data: 2026-09-03
- Owner: Mihnea - API și contracte (decizie confirmată cu Emi)

## Context

`app/services/ports.py` definește `CriterionExtractor` și `ReportAnalyzer` ca
interfețe async, satisfăcute până acum numai de adaptoarele deterministe din
`app/services/fake_ai.py`. Exista în paralel un stack legacy
(`AI/`, `adr_rag/`) cu integrare reală OpenRouter, dar cuplat la SQLite și
la propriul model de date, incompatibil cu contractul `app/`.

Decizia (confirmată cu Emi): se implementează adaptoare noi peste
`app/services/ports.py`, folosind OpenRouter ca furnizor, în loc de a
conecta UI-ul la stack-ul legacy.

## Decizie

`app/services/openrouter_ai.py` adaugă `OpenRouterCriterionExtractor` și
`OpenRouterReportAnalyzer`. Ambele:

- extrag textul documentelor PDF local (`pymupdf`), pagină cu pagină;
- ating fiecare pasaj un `evidence_id` local și trimit modelului numai
  blocuri `EVIDENCE` cu acel id — modelul nu reproduce niciodată text, ci
  doar referă `evidenceIds` (regula din `contracts/ai-contract.md` secțiunea 12);
- rezolvă `evidenceIds` înapoi la `SourceAnchor` folosind exclusiv textul
  extras local, deci un citat inventat este structural imposibil;
- `OpenRouterReportAnalyzer` garantează exact un `ValidationCandidate` per
  criteriu cerut, completând cu `insufficient_evidence` orice criteriu pe
  care modelul nu l-a acoperit valid.

`app/core/config.py` capătă `CHIATRATON_CRITERION_EXTRACTOR_BACKEND` și
`CHIATRATON_REPORT_ANALYZER_BACKEND` cu o a treia valoare, `openrouter`,
alături de `fake`/`external`. Configurația OpenRouter
(`CHIATRATON_OPENROUTER_API_KEY`/`_MODEL`/`_BASE_URL`/`_TIMEOUT_SECONDS`)
e validată la pornire: dacă vreun backend e `openrouter`, cheia API e
obligatorie.

`app/main.py` instanțiază adaptorul doar când e selectat, cu un singur
`httpx.AsyncClient` partajat, închis la shutdown prin noul parametru
`extra_shutdown_hooks` din `DefaultApplicationService`.

## Consecințe

- fluxul rămâne 100% compatibil cu contractul HTTP existent; niciun schema
  change în `contracts/openapi.yaml`;
- nu se face nicio retrieval semantică (RAG/embeddings) — se trimite tot
  textul paginilor documentelor autorizate, limitat la un plafon de
  evidențe per cerere (`_MAX_EVIDENCE_ITEMS_PER_REQUEST`); pentru documente
  foarte mari acest plafon poate omite pasaje relevante — o îmbunătățire
  ulterioară;
- taxonomia de excepții rămâne cea din `AIOutcome` (5 valori), nu cea
  extinsă din `contracts/ai-contract.md` secțiunea 12 (8 valori) — acea
  mapare la taxonomia UI extinsă nu a fost implementată în acest pas;
- `app/services/default.py` distinge în continuare doar 2 coduri de eroare
  (`ai_invalid_response`, `ai_unavailable`), nu cele 7 din contract — adaptorul
  e scris să se încadreze în această distincție existentă, nu o extinde;
- stack-ul legacy (`AI/`, `adr_rag/`, `Services/monitoring_service.py`) rămâne
  neschimbat și neconectat la `app/`/`Interface/`.

## Amendament (2026-09-03): înlocuit cu `AI/qwen_adapter.py` de pe `main`

La integrarea `ui/api-integration-v1` în `main`, s-a descoperit că `main`
avea deja un adaptor echivalent, mai complet: `AI/qwen_adapter.py`, cu
retrieval semantic real (`AI/retrieval.py`, embeddings dense) în loc de
trimiterea textului complet per pagină, plus un flux UI deja cablat
(`Interface/criteria_review.py`, navigare automată din
`Interface/upload_documents.py` după upload).

`app/services/openrouter_ai.py` și testele lui au fost șterse; backend-ul
`openrouter` din `CHIATRATON_CRITERION_EXTRACTOR_BACKEND`/
`CHIATRATON_REPORT_ANALYZER_BACKEND` a fost înlocuit cu `qwen`, care rămâne
adaptorul canonic. Acest ADR se păstrează doar ca istoric al deciziei
inițiale.
