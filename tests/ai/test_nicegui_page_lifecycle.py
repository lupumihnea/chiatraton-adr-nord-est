from pathlib import Path


def test_long_running_pages_flush_before_network_work() -> None:
    root = Path(__file__).resolve().parents[2]
    criteria = (root / "Interface" / "criteria_review.py").read_text(encoding="utf-8")
    project = (root / "Interface" / "project_details.py").read_text(encoding="utf-8")
    main = (root / "Interface" / "main.py").read_text(encoding="utf-8")
    report = (root / "Interface" / "report_analysis.py").read_text(encoding="utf-8")

    assert "async def criteria_review_page" in criteria
    assert "await ui.context.client.connected(timeout=10.0)" in criteria
    assert "ui.timer(0.1, poll_job_after_connect" not in criteria
    assert "return await api_client.list_all_project_documents(project_id)" in criteria

    assert "async def project_details_page" in project
    assert "await ui.context.client.connected(timeout=10.0)" in project

    assert "async def home" in main
    assert "await ui.context.client.connected(timeout=10.0)" in main

    assert "async def report_analysis_page" in report
    assert "await ui.context.client.connected(timeout=10.0)" in report
    assert 'EXCEPTION_OUTCOMES = {' in report
    assert '"partially_compliant"' in report
    assert '"non_compliant"' in report
    assert '"insufficient_evidence"' in report
    assert '"Arată toate obligațiile"' in report


def test_report_analysis_keeps_human_review_controls() -> None:
    root = Path(__file__).resolve().parents[2]
    report = (root / "Interface" / "report_analysis.py").read_text(encoding="utf-8")

    assert "create_validation_decision" in report
    assert 'action="confirm"' in report
    assert 'action="correct"' in report
    assert 'action="reject"' in report
    assert '"Confirmă constatarea"' in report
