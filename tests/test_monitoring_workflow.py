from __future__ import annotations

from pathlib import Path

from AI.ai_client import EvidenceAnchor, ValidationProposal
from DataBase.db_schema import setup_database
from Services.monitoring_service import MonitoringService


class FakeAI:
    model_name = "fake-paid-model"

    def analyze_report(self, report, criteria, project_documents, previous_reports):
        out = []
        for c in criteria:
            baseline = c.baseline_sources[0]
            report_source = EvidenceAnchor(
                evidence_id=f"report-{c.criterion_id}",
                role="current_report",
                document_id=report.document_id,
                page=1,
                text="Raportul declară o valoare diferită de valoarea asumată.",
            )
            out.append(
                ValidationProposal(
                    criterion_id=c.criterion_id,
                    applicable=True,
                    outcome="different_value_or_date",
                    rationale="Valoarea raportată diferă de criteriul proiectului.",
                    sources=[baseline, report_source],
                )
            )
        return out


def _seed(tmp_path: Path):
    db = tmp_path / "test.db"
    baseline = tmp_path / "contract.txt"
    report_file = tmp_path / "report.txt"
    baseline.write_text("Beneficiarul va crea 3 noi locuri de muncă.", encoding="utf-8")
    report_file.write_text("Raportul declară o valoare diferită de valoarea asumată.", encoding="utf-8")

    con = setup_database(str(db))
    cur = con.cursor()
    cur.execute("INSERT INTO project(id, call_id, time_ending, name) VALUES (123456, 1, '2025-07-23', 'Test')")
    cur.execute("INSERT INTO document(type, path) VALUES (10, ?)", (str(baseline),))
    baseline_id = cur.lastrowid
    cur.execute("INSERT INTO document(type, path) VALUES (7, ?)", (str(report_file),))
    report_doc_id = cur.lastrowid
    cur.execute(
        "INSERT INTO obligation(project_id, description, deadline, importance) VALUES (123456, ?, '2025-07-23', 3)",
        ("Beneficiarul va crea 3 noi locuri de muncă.",),
    )
    criterion_id = cur.lastrowid
    cur.execute(
        'INSERT INTO "references"(obligation_id, document_id, page, text) VALUES (?, ?, 1, ?)',
        (criterion_id, baseline_id, "Beneficiarul va crea 3 noi locuri de muncă."),
    )
    cur.execute(
        "INSERT INTO project_documents(project_id, document_id, role) VALUES (123456, ?, 'contract')",
        (baseline_id,),
    )
    cur.execute(
        """
        INSERT INTO reports(project_id, document_id, sequence_number, kind, period_start, period_end)
        VALUES (123456, ?, 1, 'implementation_progress', '2025-01-01', '2025-03-31')
        """,
        (report_doc_id,),
    )
    report_id = cur.lastrowid
    cur.execute(
        "INSERT INTO project_documents(project_id, document_id, role) VALUES (123456, ?, 'report')",
        (report_doc_id,),
    )
    con.commit()
    con.close()
    return db, report_id


def test_full_human_review_history_and_export(tmp_path, monkeypatch):
    db, report_id = _seed(tmp_path)
    monkeypatch.chdir(tmp_path)
    service = MonitoringService(db_path=str(db), ai_factory=FakeAI)

    findings = service.analyze_report(report_id)
    assert len(findings) == 1
    finding = findings[0]
    assert finding["outcome"] == "different_value_or_date"
    assert len(finding["sources"]) == 2
    assert finding["sources"][0]["text"] == "Beneficiarul va crea 3 noi locuri de muncă."

    service.decide(finding["id"], "confirmed", final_outcome=finding["outcome"])
    output = service.generate_output(report_id, "verification_note")
    assert "NOTĂ DE VERIFICARE" in output["content"]
    assert Path(output["path"]).exists()

    history = service.history(report_id)
    assert len(history["jobs"]) == 1
    assert len(history["decisions"]) == 1
    assert len(history["outputs"]) == 1


def test_idempotent_analysis_does_not_duplicate_revision(tmp_path):
    db, report_id = _seed(tmp_path)
    service = MonitoringService(db_path=str(db), ai_factory=FakeAI)
    first = service.analyze_report(report_id)
    second = service.analyze_report(report_id)
    assert first[0]["id"] == second[0]["id"]
    assert len(service.history(report_id)["jobs"]) == 1
