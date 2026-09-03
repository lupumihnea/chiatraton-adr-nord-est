import time


def _headers(auth_headers, key):
    return {**auth_headers, "Idempotency-Key": key}


def _post(client, auth_headers, path, key, *, expected, **kwargs):
    response = client.post(path, headers=_headers(auth_headers, key), **kwargs)
    assert response.status_code == expected, response.text
    return response


def _wait_for_job(client, auth_headers, job_id):
    for _ in range(100):
        response = client.get(f"/api/v1/analysis-jobs/{job_id}", headers=auth_headers)
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(0.005)
    raise AssertionError("local job did not finish")


def _create_project(client, auth_headers, key="project-1", name="Synthetic project"):
    return _post(
        client,
        auth_headers,
        "/api/v1/projects",
        key,
        expected=201,
        json={
            "name": name,
            "completionDate": "2030-12-31",
            "monitoringEndDate": "2033-12-31",
        },
    ).json()


def _upload(client, auth_headers, project_id, key, filename, content):
    return _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_id}/documents",
        key,
        expected=201,
        files={"file": (filename, content, "application/pdf")},
    ).json()


def _extract(client, auth_headers, project_id, document_id, key="extract-1"):
    response = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project_id}/criterion-extraction-jobs",
        key,
        expected=202,
        json={"documentIds": [document_id]},
    )
    assert response.headers["Location"].endswith(response.json()["id"])
    job = _wait_for_job(client, auth_headers, response.json()["id"])
    assert job["status"] == "succeeded"
    proposals = client.get(
        f"/api/v1/criterion-extraction-jobs/{job['id']}/proposals",
        headers=auth_headers,
    )
    assert proposals.status_code == 200
    return job, sorted(proposals.json()["items"], key=lambda item: item["proposedCode"])


def _review_all(client, auth_headers, job_id, proposals, key="reviews-1"):
    payload = {
        "reviews": [
            {
                "proposalId": proposals[0]["id"],
                "proposalRevision": proposals[0]["revision"],
                "action": "accept",
            },
            {
                "proposalId": proposals[1]["id"],
                "proposalRevision": proposals[1]["revision"],
                "action": "correct",
                "correction": {
                    "code": "SYN-CORRECTED-002",
                    "description": "Corrected synthetic criterion for the demonstration.",
                    "deadline": None,
                    "sourceAnchors": proposals[1]["sourceAnchors"],
                },
                "comment": "Synthetic correction made by the user.",
            },
            {
                "proposalId": proposals[2]["id"],
                "proposalRevision": proposals[2]["revision"],
                "action": "reject",
                "comment": "Synthetic proposal rejected by the user.",
            },
        ]
    }
    return _post(
        client,
        auth_headers,
        f"/api/v1/criterion-extraction-jobs/{job_id}/proposal-reviews",
        key,
        expected=201,
        json=payload,
    )


def test_complete_monitoring_workflow_and_append_only_history(client, auth_headers):
    project = _create_project(client, auth_headers)
    source = _upload(
        client,
        auth_headers,
        project["id"],
        "source-document",
        "synthetic-source.pdf",
        b"Synthetic source document. No beneficiary data.",
    )
    report_document = _upload(
        client,
        auth_headers,
        project["id"],
        "report-document",
        "synthetic-report.pdf",
        b"Synthetic periodic report. No beneficiary data.",
    )

    extraction_job, proposals = _extract(client, auth_headers, project["id"], source["id"])
    assert extraction_job["proposalCount"] == 3
    assert all(
        proposal["sourceAnchors"][0]["documentId"] == source["id"]
        and proposal["sourceAnchors"][0]["pageNumber"] >= 1
        and proposal["sourceAnchors"][0]["passage"]
        for proposal in proposals
    )

    review_response = _review_all(client, auth_headers, extraction_job["id"], proposals)
    reviews = review_response.json()["items"]
    assert [item["action"] for item in reviews] == ["accept", "correct", "reject"]
    assert reviews[0]["createdCriterion"] is not None
    assert reviews[1]["createdCriterion"]["code"] == "SYN-CORRECTED-002"
    assert reviews[2]["createdCriterion"] is None
    review_replay = _review_all(client, auth_headers, extraction_job["id"], proposals)
    assert review_replay.json() == review_response.json()
    assert review_replay.headers["Idempotency-Replayed"] == "true"

    audited_proposals = client.get(
        f"/api/v1/criterion-extraction-jobs/{extraction_job['id']}/proposals",
        headers=auth_headers,
    ).json()["items"]
    assert all(item["review"] is not None for item in audited_proposals)

    criteria_response = client.get(
        f"/api/v1/projects/{project['id']}/criteria", headers=auth_headers
    )
    assert criteria_response.status_code == 200
    criteria = criteria_response.json()["items"]
    assert len(criteria) == 2
    assert {item["version"] for item in criteria} == {1}

    report_response = _post(
        client,
        auth_headers,
        f"/api/v1/projects/{project['id']}/reports",
        "report-1",
        expected=201,
        json={
            "reportType": "durability",
            "periodStart": "2031-01-01",
            "periodEnd": "2031-12-31",
            "documents": [{"documentId": report_document["id"], "role": "main_report"}],
            "externalSystem": "other",
            "externalId": "SYN-EXT-001",
            "externalStatus": "synthetic_external_pending",
        },
    )
    report = report_response.json()
    assert report["status"] == "created"
    assert report["externalStatus"] == "synthetic_external_pending"

    analysis_response = _post(
        client,
        auth_headers,
        f"/api/v1/reports/{report['id']}/analysis-jobs",
        "analysis-1",
        expected=202,
        json={"projectDocumentIds": [source["id"]], "previousReportIds": []},
    )
    analysis_job = _wait_for_job(client, auth_headers, analysis_response.json()["id"])
    assert analysis_job["status"] == "succeeded"
    assert analysis_job["criteriaSnapshotVersion"] == 2

    validations_response = client.get(
        f"/api/v1/reports/{report['id']}/validations", headers=auth_headers
    )
    assert validations_response.status_code == 200
    validations = validations_response.json()["items"]
    assert len(validations) == 2
    assert all(item["revision"] == 1 for item in validations)
    assert all(
        item["sourceAnchors"][0]["documentId"] == report_document["id"] for item in validations
    )

    _post(
        client,
        auth_headers,
        f"/api/v1/validations/{validations[0]['id']}/decisions",
        "decision-confirm",
        expected=201,
        json={"action": "confirm", "validationRevision": 1},
    )
    _post(
        client,
        auth_headers,
        f"/api/v1/validations/{validations[1]['id']}/decisions",
        "decision-correct",
        expected=201,
        json={
            "action": "correct",
            "validationRevision": 1,
            "finalOutcome": "compliant",
            "comment": "Synthetic final correction.",
        },
    )

    decided = client.get(
        f"/api/v1/reports/{report['id']}/validations", headers=auth_headers
    ).json()["items"]
    assert all(item["status"] == "decided" and item["userDecision"] for item in decided)
    reports = client.get(f"/api/v1/projects/{project['id']}/reports", headers=auth_headers).json()[
        "items"
    ]
    assert reports[0]["status"] == "completed"
    assert reports[0]["externalStatus"] == "synthetic_external_pending"

    reanalysis_response = _post(
        client,
        auth_headers,
        f"/api/v1/reports/{report['id']}/analysis-jobs",
        "analysis-2",
        expected=202,
        json={"projectDocumentIds": [source["id"]], "previousReportIds": []},
    )
    assert (
        _wait_for_job(client, auth_headers, reanalysis_response.json()["id"])["status"]
        == "succeeded"
    )

    current = client.get(
        f"/api/v1/reports/{report['id']}/validations", headers=auth_headers
    ).json()["items"]
    assert len(current) == 2
    assert all(item["revision"] == 2 and item["userDecision"] is None for item in current)
    history = client.get(
        f"/api/v1/reports/{report['id']}/validations?includeHistory=true",
        headers=auth_headers,
    ).json()["items"]
    assert len(history) == 4
    assert sum(item["revision"] == 1 and item["userDecision"] is not None for item in history) == 2

    stale = _post(
        client,
        auth_headers,
        f"/api/v1/validations/{validations[0]['id']}/decisions",
        "stale-decision",
        expected=409,
        json={"action": "confirm", "validationRevision": 1},
    )
    assert stale.json()["code"] == "stale_validation_revision"


def test_pagination_cursor_is_opaque_scoped_and_rejects_invalid_values(client, auth_headers):
    _create_project(client, auth_headers, "page-project-1", "Synthetic page 1")
    _create_project(client, auth_headers, "page-project-2", "Synthetic page 2")
    first = client.get("/api/v1/projects?limit=1", headers=auth_headers)
    assert first.status_code == 200
    cursor = first.json()["nextCursor"]
    assert cursor and "offset" not in cursor
    second = client.get(f"/api/v1/projects?limit=1&cursor={cursor}", headers=auth_headers)
    assert second.status_code == 200
    assert second.json()["items"][0]["id"] != first.json()["items"][0]["id"]

    invalid = client.get("/api/v1/projects?cursor=not-a-server-cursor", headers=auth_headers)
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "validation_error"
