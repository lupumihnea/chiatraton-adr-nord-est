# Workflow implementat în MVP

Maparea cerinței operaționale la cod:

| Pas | Implementare |
|---|---|
| 1. Selectare raport/task | `Interface/main.py` – pagina proiectului |
| 2. Proiect + raport + documente | `MonitoringService.analyze_report` + repositories |
| 3. Criterii aplicabile perioadei | `OpenRouterMonitoringAI` (`applicable_to_period`) |
| 4. Comparație surse | criterion source + project docs + current report + previous reports |
| 5. Numai excepții | `MonitoringRepository.latest_validations(..., exceptions_only=True)` |
| 6. Două pasaje/pagini | `validation_sources`; modelul returnează evidence IDs, nu text inventat |
| 7. Confirm/correct/reject | `user_decisions` append-only |
| 8. Notă/draft | `MonitoringService.generate_output` |
| 9. Copy/export | NiceGUI clipboard + `.txt` în `exports/` |
| 10. Istoric | `analysis_jobs`, validation revisions, decisions, generated outputs |

## Taxonomia excepțiilor

- `nonconcordance`
- `missing_information`
- `different_value_or_date`
- `insufficient_evidence`
- `cross_report_contradiction`
- `human_review_required`

`ok` și `not_applicable` se păstrează în DB pentru audit, dar nu sunt afișate în lista principală de constatări.
