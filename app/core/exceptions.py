from __future__ import annotations

from dataclasses import dataclass, field

from app.models.errors import FieldError


@dataclass(slots=True)
class ProblemException(Exception):
    status: int
    code: str
    title: str
    detail: str
    errors: list[FieldError] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


class OperationNotImplementedError(Exception):
    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id
        super().__init__(operation_id)
