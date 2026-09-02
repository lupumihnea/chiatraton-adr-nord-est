"""Explicit no-op boundary for use cases deferred to later PRs."""

from typing import NoReturn

from app.core.exceptions import OperationNotImplementedError


class UnimplementedApplicationService:
    """Every public method is resolved explicitly and fails safely.

    Explicit methods keep route-to-service calls visible and testable while this
    PR stays focused on the transport contract. A later PR replaces this dependency
    with concrete services backed by repository interfaces.
    """

    async def _raise(self, operation_id: str) -> NoReturn:
        raise OperationNotImplementedError(operation_id)

    async def create_project(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createProject")

    async def list_projects(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("listProjects")

    async def upload_project_document(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("uploadProjectDocument")

    async def create_project_criterion(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createProjectCriterion")

    async def list_project_criteria(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("listProjectCriteria")

    async def create_criterion_extraction_job(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createCriterionExtractionJob")

    async def create_project_report(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createProjectReport")

    async def list_project_reports(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("listProjectReports")

    async def create_report_analysis_job(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createReportAnalysisJob")

    async def get_analysis_job(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("getAnalysisJob")

    async def list_criterion_extraction_proposals(
        self, *args: object, **kwargs: object
    ) -> NoReturn:
        return await self._raise("listCriterionExtractionProposals")

    async def create_criterion_proposal_reviews(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createCriterionProposalReviews")

    async def list_report_validations(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("listReportValidations")

    async def create_validation_decision(self, *args: object, **kwargs: object) -> NoReturn:
        return await self._raise("createValidationDecision")
