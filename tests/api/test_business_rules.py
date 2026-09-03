from fastapi.testclient import TestClient

from app.main import create_app
from app.services.fake_ai import (
    DeterministicFakeCriterionExtractor,
    DeterministicFakeReportAnalyzer,
)
from tests.api.test_complete_workflow import (
    _create_project,
    _extract,
    _post,
    _upload,
    _wait_for_job,
)


def test_project_ui_metadata_round_trips_without_breaking_legacy_projects(
    client, auth_headers
):
    response = _post(
        client,
        auth_headers,
        "/api/v1/projects",
        "project-ui-metadata",
        expected=201,
        json={
            "name": "Proiect sintetic UI",
            "smisCode": "654321",
            "fundingCallId": 42,
            "beneficiaryName": "Organizație Sintetică Delta",
            "completionDate": "2030-12-31",
            "monitoringEndDate": "2033-12-31",
        },
    )
    project = response.json()
    assert project["smisCode"] == "654321"
    assert project["fundingCallId"] == 42
    assert project["beneficiaryName"] == "Organizație Sintetică Delta"

    listed = client.get("/api/v1/projects", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["items"] == [project]

    legacy = _create_project(
        client,
        auth_headers,
        "project-without-ui-metadata",
        "Proiect sintetic compatibil",
    )
    assert legacy["smisCode"] is None
    assert legacy["fundingCallId"] is None
    assert legacy["beneficiaryName"] is None


def test_documents_criteria_and_report_project_boundaries(client, auth_headers):
    project_a = _create_project(client, auth_headers, "project-a", "Synthetic A")
    project_b = _create_project(client, auth_headers, "project-b", "Synthetic B")
    document_a = _upload(client, auth_headers, project_a["id"], "doc-a", "a.pdf", b"synthetic-a")
    document_b = _upload(client, auth_headers, project_b["id"], "doc-b", "b.pdf", b"synthetic-b")

    duplicate = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/documents",
        "doc-a-duplicate",
        expected=409,
        files={"file": ("copy.pdf", b"synthetic-a", "application/pdf")},
    )
    assert duplicate.json()["code"] == "document_duplicate"

    missing_page = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/criteria",
        "criterion-missing-page",
        expected=422,
        json={
            "code": "SYN-001",
            "description": "Synthetic criterion.",
            "sourceAnchors": [{"documentId": document_a["id"], "passage": "Evidence"}],
        },
    )
    assert missing_page.json()["code"] == "validation_error"

    cross_project_anchor = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/criteria",
        "criterion-cross-anchor",
        expected=422,
        json={
            "code": "SYN-001",
            "description": "Synthetic criterion.",
            "sourceAnchors": [
                {"documentId": document_b["id"], "pageNumber": 1, "passage": "Evidence"}
            ],
        },
    )
    assert cross_project_anchor.json()["code"] == "validation_error"

    created = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/criteria",
        "criterion-created",
        expected=201,
        json={"code": "SYN-001", "description": "Synthetic criterion."},
    )
    assert created.json()["version"] == 1
    duplicate_code = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/criteria",
        "criterion-duplicate",
        expected=409,
        json={"code": "syn-001", "description": "Duplicate synthetic criterion."},
    )
    assert duplicate_code.json()["code"] == "criterion_code_conflict"

    cross_project_extraction = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/criterion-extraction-jobs",
        "cross-project-extraction",
        expected=422,
        json={"documentIds": [document_b["id"]]},
    )
    assert cross_project_extraction.json()["code"] == "validation_error"

    cross_project_report = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/reports",
        "cross-project-report",
        expected=422,
        json={
            "reportType": "durability",
            "periodStart": "2031-01-01",
            "periodEnd": "2031-12-31",
            "documents": [{"documentId": document_b["id"], "role": "main_report"}],
        },
    )
    assert cross_project_report.json()["code"] == "validation_error"


def test_report_primary_and_monitoring_period_rules(client, auth_headers):
    project = _create_project(client, auth_headers)
    first = _upload(client, auth_headers, project["id"], "doc-1", "one.pdf", b"one")
    second = _upload(client, auth_headers, project["id"], "doc-2", "two.pdf", b"two")

    two_primaries = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project['id']}/reports",
        "two-primaries",
        expected=422,
        json={
            "reportType": "durability",
            "periodStart": "2031-01-01",
            "periodEnd": "2031-12-31",
            "documents": [
                {"documentId": first["id"], "role": "main_report"},
                {"documentId": second["id"], "role": "final_document"},
            ],
        },
    )
    assert two_primaries.json()["code"] == "validation_error"

    after_monitoring = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project['id']}/reports",
        "after-monitoring",
        expected=422,
        json={
            "reportType": "durability",
            "periodStart": "2033-01-01",
            "periodEnd": "2034-01-01",
            "documents": [{"documentId": first["id"], "role": "main_report"}],
        },
    )
    assert after_monitoring.json()["code"] == "validation_error"


def test_proposal_review_batch_is_atomic_and_stale_revision_conflicts(client, auth_headers):
    project = _create_project(client, auth_headers)
    document = _upload(client, auth_headers, project["id"], "source", "source.pdf", b"synthetic")
    job, proposals = _extract(client, auth_headers, project["id"], document["id"])

    partially_invalid = _post(
        client,
        auth_headers,
        f"/api/v1/criterion-extraction-jobs/{job['id']}/proposal-reviews",
        "atomic-invalid-batch",
        expected=409,
        json={
            "reviews": [
                {
                    "proposalId": proposals[0]["id"],
                    "proposalRevision": proposals[0]["revision"],
                    "action": "accept",
                },
                {
                    "proposalId": proposals[1]["id"],
                    "proposalRevision": proposals[1]["revision"] + 1,
                    "action": "accept",
                },
            ]
        },
    )
    assert partially_invalid.json()["code"] == "stale_proposal_revision"
    criteria = client.get(
        f"/api/v1/projects/{project['id']}/criteria", headers=auth_headers
    ).json()["items"]
    assert criteria == []
    audited = client.get(
        f"/api/v1/criterion-extraction-jobs/{job['id']}/proposals",
        headers=auth_headers,
    ).json()["items"]
    assert all(item["review"] is None for item in audited)

    stale_only = _post(
        client,
        auth_headers,
        f"/api/v1/criterion-extraction-jobs/{job['id']}/proposal-reviews",
        "stale-only",
        expected=409,
        json={
            "reviews": [
                {
                    "proposalId": proposals[0]["id"],
                    "proposalRevision": 999,
                    "action": "accept",
                }
            ]
        },
    )
    assert stale_only.json()["code"] == "stale_proposal_revision"


def test_cross_project_analysis_context_is_rejected(client, auth_headers):
    project_a = _create_project(client, auth_headers, "analysis-project-a", "Synthetic A")
    project_b = _create_project(client, auth_headers, "analysis-project-b", "Synthetic B")
    report_document = _upload(
        client, auth_headers, project_a["id"], "analysis-report", "report.pdf", b"report"
    )
    foreign_document = _upload(
        client, auth_headers, project_b["id"], "analysis-foreign", "foreign.pdf", b"foreign"
    )
    _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/criteria",
        "analysis-criterion",
        expected=201,
        json={"code": "SYN-ANALYSIS", "description": "Synthetic analysis criterion."},
    )
    report = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_a['id']}/reports",
        "analysis-report-create",
        expected=201,
        json={
            "reportType": "durability",
            "periodStart": "2031-01-01",
            "periodEnd": "2031-12-31",
            "documents": [{"documentId": report_document["id"], "role": "main_report"}],
        },
    ).json()
    response = _post(
        client,
        auth_headers,
        f"/api/v1/reports/{report['id']}/analysis-jobs",
        "foreign-analysis-context",
        expected=422,
        json={"projectDocumentIds": [foreign_document["id"]], "previousReportIds": []},
    )
    assert response.json()["code"] == "validation_error"


def test_invalid_fake_extraction_response_fails_job_without_proposals(settings, auth_headers):
    app = create_app(
        settings,
        criterion_extractor=DeterministicFakeCriterionExtractor(invalid_response=True),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        project = _create_project(client, auth_headers)
        document = _upload(
            client, auth_headers, project["id"], "invalid-source", "source.pdf", b"synthetic"
        )
        response = _post(
            client,
            auth_headers,
            f"/api/v1/projects/{project['id']}/criterion-extraction-jobs",
            "invalid-extraction",
            expected=202,
            json={"documentIds": [document["id"]]},
        )
        job = _wait_for_job(client, auth_headers, response.json()["id"])
        assert job["status"] == "failed"
        assert job["error"]["code"] == "ai_invalid_response"
        proposals = client.get(
            f"/api/v1/criterion-extraction-jobs/{job['id']}/proposals",
            headers=auth_headers,
        )
        assert proposals.status_code == 409
        assert proposals.json()["code"] == "analysis_job_not_succeeded"


def test_invalid_fake_analysis_response_fails_job_and_report(settings, auth_headers):
    app = create_app(
        settings,
        report_analyzer=DeterministicFakeReportAnalyzer(invalid_response=True),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        project = _create_project(client, auth_headers)
        document = _upload(
            client, auth_headers, project["id"], "invalid-report", "report.pdf", b"synthetic"
        )
        _post(
            client,
            auth_headers,
            f"/api/v1/projects/{project['id']}/criteria",
            "invalid-analysis-criterion",
            expected=201,
            json={"code": "SYN-INVALID", "description": "Synthetic criterion."},
        )
        report = _post(
            client,
            auth_headers,
            f"/api/v1/projects/{project['id']}/reports",
            "invalid-analysis-report",
            expected=201,
            json={
                "reportType": "durability",
                "periodStart": "2031-01-01",
                "periodEnd": "2031-12-31",
                "documents": [{"documentId": document["id"], "role": "main_report"}],
            },
        ).json()
        response = _post(
            client,
            auth_headers,
            f"/api/v1/reports/{report['id']}/analysis-jobs",
            "invalid-analysis-job",
            expected=202,
            json={"projectDocumentIds": [], "previousReportIds": []},
        )
        job = _wait_for_job(client, auth_headers, response.json()["id"])
        assert job["status"] == "failed"
        assert job["error"]["code"] == "ai_invalid_response"
        reports = client.get(
            f"/api/v1/projects/{project['id']}/reports", headers=auth_headers
        ).json()["items"]
        assert reports[0]["status"] == "analysis_failed"
