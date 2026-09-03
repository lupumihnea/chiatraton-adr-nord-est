import json
from pathlib import Path

import pytest

from app.models.domain import (
    AnalysisJob,
    AnalysisJobCreate,
    Criterion,
    CriterionCreate,
    CriterionExtractionJobCreate,
    CriterionProposalReviewBatch,
    CriterionProposalReviewBatchResult,
    Document,
    PaginatedCriterionProposals,
    PaginatedValidations,
    Project,
    ProjectCreate,
    Report,
    ReportCreate,
    UserDecision,
    UserDecisionCreate,
)
from app.models.errors import ProblemDetails

ROOT = Path(__file__).resolve().parents[2]

EXAMPLE_MODELS = {
    "analysis-job-create.request.json": AnalysisJobCreate,
    "analysis-job.accepted.json": AnalysisJob,
    "analysis-job.succeeded.json": AnalysisJob,
    "criterion-create.request.json": CriterionCreate,
    "criterion-create.response.json": Criterion,
    "criterion-extraction-job-create.request.json": CriterionExtractionJobCreate,
    "criterion-extraction-job.accepted.json": AnalysisJob,
    "criterion-extraction-job.succeeded.json": AnalysisJob,
    "criterion-proposal-review-conflict.response.json": ProblemDetails,
    "criterion-proposal-reviews.request.json": CriterionProposalReviewBatch,
    "criterion-proposal-reviews.response.json": CriterionProposalReviewBatchResult,
    "criterion-proposals-list.response.json": PaginatedCriterionProposals,
    "document-upload.response.json": Document,
    "problem.response.json": ProblemDetails,
    "project-create.request.json": ProjectCreate,
    "project-create.response.json": Project,
    "report-create.request.json": ReportCreate,
    "report-create.response.json": Report,
    "user-decision-create.request.json": UserDecisionCreate,
    "user-decision.response.json": UserDecision,
    "validations-list.response.json": PaginatedValidations,
}


@pytest.mark.parametrize("filename,model", EXAMPLE_MODELS.items())
def test_contract_examples_validate_against_pydantic_models(filename, model):
    payload = json.loads((ROOT / "contracts" / "examples" / filename).read_text("utf-8"))
    model.model_validate(payload)


def test_every_json_example_is_covered():
    filenames = {path.name for path in (ROOT / "contracts" / "examples").glob("*.json")}
    assert filenames == set(EXAMPLE_MODELS)


def test_project_ui_metadata_is_optional_and_serialized_with_contract_names():
    legacy_payload = {"name": "Proiect sintetic fără metadate externe"}
    assert ProjectCreate.model_validate(legacy_payload).smis_code is None

    payload = {
        **legacy_payload,
        "smisCode": "654321",
        "fundingCallId": 42,
        "beneficiaryName": "Organizație Sintetică Delta",
    }
    project = ProjectCreate.model_validate(payload)
    assert project.model_dump(by_alias=True, mode="json") == payload


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("smisCode", "12345"),
        ("smisCode", "ABC123"),
        ("fundingCallId", 0),
    ],
)
def test_project_ui_metadata_rejects_invalid_values(field, value):
    payload = {
        "name": "Proiect sintetic",
        field: value,
    }
    with pytest.raises(ValueError):
        ProjectCreate.model_validate(payload)
