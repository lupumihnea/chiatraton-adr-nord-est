"""Test-only application route for exercising idempotency end to end."""

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.dependencies import CurrentUserDep, IdempotencyDep
from app.core.config import Settings
from app.core.exceptions import OperationNotImplementedError
from app.main import create_app

TEST_SECRET = "synthetic-idempotency-test-secret"


class IdempotencyHarness:
    def __init__(self) -> None:
        self.executions: defaultdict[tuple[str, str], int] = defaultdict(int)
        self.router = APIRouter()

        async def execute(
            *,
            counter_resource: str,
            response_resource: str,
            payload: dict[str, Any],
            response: Response,
            user: CurrentUserDep,
        ) -> dict[str, Any]:
            counter_key = (user.subject, counter_resource)
            self.executions[counter_key] += 1
            execution = self.executions[counter_key]
            if payload.get("delay"):
                await asyncio.sleep(0.05)
            if payload.get("force5xx"):
                raise OperationNotImplementedError("testOnlyFailure")
            response.headers["Location"] = f"/__test__/idempotency/{response_resource}/{execution}"
            return {
                "executionCount": execution,
                "resource": response_resource,
                "value": payload.get("value"),
            }

        @self.router.post(
            "/__test__/idempotency/{resource}",
            status_code=status.HTTP_201_CREATED,
            include_in_schema=False,
        )
        async def operation(
            resource: str,
            payload: dict[str, Any],
            response: Response,
            user: CurrentUserDep,
            idempotency: IdempotencyDep,
        ) -> dict[str, Any]:
            del idempotency
            return await execute(
                counter_resource=resource,
                response_resource=resource,
                payload=payload,
                response=response,
                user=user,
            )

        @self.router.post(
            "/__test__/idempotency-alternate/{resource}",
            status_code=status.HTTP_201_CREATED,
            include_in_schema=False,
        )
        async def alternate_operation(
            resource: str,
            payload: dict[str, Any],
            response: Response,
            user: CurrentUserDep,
            idempotency: IdempotencyDep,
        ) -> dict[str, Any]:
            del idempotency
            return await execute(
                counter_resource=f"alternate/{resource}",
                response_resource=resource,
                payload=payload,
                response=response,
                user=user,
            )


harness = IdempotencyHarness()
app = create_app(
    Settings(environment="test", jwt_secret=TEST_SECRET),
    extra_routers=[harness.router],
)
