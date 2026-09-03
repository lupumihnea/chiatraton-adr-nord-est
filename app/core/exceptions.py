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
