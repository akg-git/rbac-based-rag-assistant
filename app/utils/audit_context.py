"""Request-scoped audit context for authenticated FastAPI routes."""

from dataclasses import dataclass
import re
from typing import Any
from uuid import uuid4

from fastapi import Depends, Request

from app.authentication.auth import authenticate
from app.utils.audit_events import emit_audit_event


def initialize_request_audit_context(request: Request) -> tuple[str, str]:
    request_id = str(uuid4())
    incoming_correlation_id = request.headers.get("X-Correlation-ID", "")
    correlation_id = (
        incoming_correlation_id
        if re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", incoming_correlation_id)
        else request_id
    )
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    return request_id, correlation_id


@dataclass(frozen=True)
class AuditContext:
    username: str
    role: str
    request_id: str
    correlation_id: str

    def emit(
        self,
        *,
        action: str,
        resource: str,
        authorization_decision: str,
        result: str,
        outcome_status: str,
        query_mode: str = "administration",
    ) -> None:
        emit_audit_event(
            user_id=self.username,
            role=self.role,
            action=action,
            resource=resource,
            authorization_decision=authorization_decision,
            result=result,
            outcome_status=outcome_status,
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            query_mode=query_mode,
        )


def get_audit_context(
    request: Request,
    user: dict[str, Any] = Depends(authenticate),
) -> AuditContext:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    correlation_id = getattr(request.state, "correlation_id", request_id)
    return AuditContext(
        username=user["username"],
        role=user["role"],
        request_id=request_id,
        correlation_id=correlation_id,
    )
