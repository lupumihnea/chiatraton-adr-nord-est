from __future__ import annotations

import re
from uuid import uuid4

from fastapi import Request

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def new_request_id() -> str:
    return f"req_{uuid4().hex}"


def request_id_from(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else new_request_id()


def accepted_request_id(request: Request) -> str:
    supplied = request.headers.get("X-Request-Id")
    if supplied and REQUEST_ID_PATTERN.fullmatch(supplied):
        return supplied
    return new_request_id()
