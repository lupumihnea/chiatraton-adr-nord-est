from __future__ import annotations

from typing import Any

from Services.monitoring_service import MonitoringService


class MonitoringAPI:
    """
    Thin application boundary used by NiceGUI and CLI.

    It keeps UI code away from repositories and from the OpenRouter adapter.
    An HTTP transport can be placed in front of the same methods later without
    changing the workflow service.
    """

    def __init__(self, service: MonitoringService | None = None):
        self.service = service or MonitoringService()

    def list_projects(self) -> list[dict[str, Any]]:
        return self.service.list_projects()

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        return self.service.get_project(project_id)

    def upsert_project(self, **kwargs) -> None:
        self.service.upsert_project(**kwargs)

    def list_documents(self) -> list[dict[str, Any]]:
        return self.service.list_documents()

    def add_document(self, **kwargs) -> int:
        return self.service.add_document(**kwargs)

    def link_documents(self, project_id: int, document_ids: list[int], role: str = "project_document") -> None:
        self.service.link_documents(project_id, document_ids, role)

    def extract_criteria(self, project_id: int, document_ids: list[int] | None = None) -> list[dict[str, Any]]:
        return self.service.extract_criteria(project_id, document_ids)

    def list_criteria(self, project_id: int) -> list[dict[str, Any]]:
        return self.service.list_criteria(project_id)

    def list_reports(self, project_id: int) -> list[dict[str, Any]]:
        return self.service.list_reports(project_id)

    def get_report(self, report_id: int) -> dict[str, Any] | None:
        return self.service.get_report(report_id)

    def add_report(self, **kwargs) -> int:
        return self.service.add_report(**kwargs)

    def analyze_report(self, report_id: int, force: bool = False) -> list[dict[str, Any]]:
        return self.service.analyze_report(report_id, force=force)

    def list_findings(self, report_id: int) -> list[dict[str, Any]]:
        return self.service.list_findings(report_id)

    def decide(self, validation_id: int, action: str, **kwargs) -> int:
        return self.service.decide(validation_id, action, **kwargs)

    def generate_output(self, report_id: int, kind: str) -> dict[str, Any]:
        return self.service.generate_output(report_id, kind)

    def history(self, report_id: int) -> dict[str, Any]:
        return self.service.history(report_id)
