from __future__ import annotations

import time

from app.models.domain import AIOutcome, SourceAnchor
from app.services.ports import ReportAnalysisRequest, ValidationCandidate
from app.main import create_app
from fastapi.testclient import TestClient

from tests.api.test_complete_workflow import _create_project, _post


def _wait_for_job(client, auth_headers, job_id):
    for _ in range(400):
        response = client.get(f"/api/v1/analysis-jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    raise AssertionError("local analysis job did not finish")


def _upload_category(client, auth_headers, project_id, key, filename, content, category):
    return _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_id}/documents",
        key,
        expected=201,
        files={"file": (filename, content, "application/pdf")},
        data={"displayName": category},
    ).json()


class PeriodOutcomeAnalyzer:
    async def analyze(self, request: ReportAnalysisRequest) -> list[ValidationCandidate]:
        report_document_id = request.report.documents[0].document_id
        outcome = (
            AIOutcome.COMPLIANT
            if request.report.period_end.month == 3
            else AIOutcome.NON_COMPLIANT
        )
        return [
            ValidationCandidate(
                criterion_id=criterion.id,
                criterion_version=criterion.version,
                outcome=outcome,
                rationale="Stare sintetică pentru testul istoricului de progres.",
                source_anchors=(
                    SourceAnchor(
                        document_id=report_document_id,
                        page_number=1,
                        passage=f"Dovadă raport curent pentru {criterion.code}.",
                    ),
                ),
            )
            for criterion in request.criteria
        ]


def test_progress_upload_requires_initial_documents_and_confirmed_baseline(client, auth_headers):
    project = _create_project(client, auth_headers, key="ordered-project")

    before_initial = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project['id']}/documents",
        "progress-too-early",
        expected=409,
        files={"file": ("progress-1.pdf", b"progress-early", "application/pdf")},
        data={"displayName": "Rapoarte de progres"},
    )
    assert before_initial.json()["code"] == "initial_documents_required"

    _upload_category(
        client,
        auth_headers,
        project["id"],
        "initial-doc",
        "cerere.pdf",
        b"initial-source",
        "Documente inițiale",
    )

    before_review = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project['id']}/documents",
        "progress-before-review",
        expected=409,
        files={"file": ("progress-2.pdf", b"progress-before-review", "application/pdf")},
        data={"displayName": "Rapoarte de progres"},
    )
    assert before_review.json()["code"] == "confirmed_baseline_required"

    _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project['id']}/criteria",
        "confirmed-obligation",
        expected=201,
        json={"code": "ORD-1", "description": "Obligație confirmată pentru test."},
    )

    accepted = _upload_category(
        client,
        auth_headers,
        project["id"],
        "progress-after-baseline",
        "progress-3.pdf",
        b"progress-after-baseline",
        "Rapoarte de progres",
    )
    assert accepted["displayName"] == "Rapoarte de progres"


def test_each_report_records_criterion_state_change(settings, auth_headers):
    app = create_app(settings, report_analyzer=PeriodOutcomeAnalyzer())
    with TestClient(app, raise_server_exceptions=False) as client:
        project = _create_project(client, auth_headers, key="timeline-project")
        initial = _upload_category(
            client,
            auth_headers,
            project["id"],
            "timeline-initial",
            "cerere.pdf",
            b"timeline-initial",
            "Documente inițiale",
        )
        criterion = _post(
            client,
            auth_headers,
            f"/api/v1/projects/{project['id']}/criteria",
            "timeline-criterion",
            expected=201,
            json={
                "code": "TIMELINE-1",
                "description": "Menținerea obligației în perioada de monitorizare.",
                "sourceAnchors": [
                    {
                        "documentId": initial["id"],
                        "pageNumber": 1,
                        "passage": "Obligație inițială sintetică.",
                    }
                ],
            },
        ).json()

        first_doc = _upload_category(
            client,
            auth_headers,
            project["id"],
            "timeline-progress-1",
            "progress-q1.pdf",
            b"timeline-q1",
            "Rapoarte de progres",
        )
        first_report = _post(
            client,
            auth_headers,
            f"/api/v1/projects/{project['id']}/reports",
            "timeline-report-1",
            expected=201,
            json={
                "reportType": "implementation_progress",
                "periodStart": "2031-01-01",
                "periodEnd": "2031-03-31",
                "documents": [{"documentId": first_doc["id"], "role": "main_report"}],
            },
        ).json()
        first_job = _post(
            client,
            auth_headers,
            f"/api/v1/reports/{first_report['id']}/analysis-jobs",
            "timeline-analysis-1",
            expected=202,
            json={"projectDocumentIds": [], "previousReportIds": []},
        ).json()
        assert _wait_for_job(client, auth_headers, first_job["id"])["status"] == "succeeded"
        first_validation = client.get(
            f"/api/v1/reports/{first_report['id']}/validations", headers=auth_headers
        ).json()["items"][0]
        assert first_validation["criterionId"] == criterion["id"]
        assert first_validation["aiOutcome"] == "compliant"
        assert "Schimbare față" not in first_validation["aiRationale"]

        second_doc = _upload_category(
            client,
            auth_headers,
            project["id"],
            "timeline-progress-2",
            "progress-q2.pdf",
            b"timeline-q2",
            "Rapoarte de progres",
        )
        second_report = _post(
            client,
            auth_headers,
            f"/api/v1/projects/{project['id']}/reports",
            "timeline-report-2",
            expected=201,
            json={
                "reportType": "implementation_progress",
                "periodStart": "2031-04-01",
                "periodEnd": "2031-06-30",
                "documents": [{"documentId": second_doc["id"], "role": "main_report"}],
            },
        ).json()
        second_job = _post(
            client,
            auth_headers,
            f"/api/v1/reports/{second_report['id']}/analysis-jobs",
            "timeline-analysis-2",
            expected=202,
            json={"projectDocumentIds": [], "previousReportIds": []},
        ).json()
        finished = _wait_for_job(client, auth_headers, second_job["id"])
        assert finished["status"] == "succeeded"
        assert first_report["id"] in finished["previousReportIds"]

        second_validation = client.get(
            f"/api/v1/reports/{second_report['id']}/validations", headers=auth_headers
        ).json()["items"][0]
        assert second_validation["criterionId"] == criterion["id"]
        assert second_validation["aiOutcome"] == "non_compliant"
        assert (
            "Schimbare față de raportul anterior: Îndeplinită → "
            "Neîndeplinită / neconformă."
        ) in second_validation["aiRationale"]
