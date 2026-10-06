"""Production audit event producer for RBAC authorization outcomes."""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
AUDIT_EVENT_LOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "rag_evaluator"
    / "audit_monitoring"
    / "logs"
    / "audit_events.jsonl"
)

AUDIT_EVENT_FIELDS = (
    "event_id",
    "timestamp",
    "user_id",
    "role",
    "request_id",
    "action",
    "resource",
    "authorization_decision",
    "result",
    "outcome_status",
    "correlation_id",
    "query_mode",
    "source_count",
)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_audit_event(
    *,
    user_id: str,
    role: str,
    action: str,
    resource: str,
    authorization_decision: str,
    result: str,
    outcome_status: str,
    request_id: str | None = None,
    correlation_id: str | None = None,
    query_mode: str | None = None,
    source_count: int | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Create a canonical, hash-integrity-protected RBAC audit event."""
    normalized_decision = authorization_decision.casefold()
    if normalized_decision not in {"allowed", "denied"}:
        raise ValueError("authorization_decision must be 'allowed' or 'denied'")

    normalized_outcome = outcome_status.casefold()
    if normalized_outcome not in {
        "authorized",
        "denied",
        "unauthorized",
        "failed",
        "policy_breach",
    }:
        raise ValueError(f"Unsupported outcome_status: {outcome_status}")

    event = {
        "event_id": event_id or str(uuid.uuid4()),
        "timestamp": timestamp or _utc_timestamp(),
        "user_id": user_id,
        "role": role,
        "request_id": request_id or str(uuid.uuid4()),
        "action": action,
        "resource": resource,
        "authorization_decision": normalized_decision,
        "result": result.casefold(),
        "outcome_status": normalized_outcome,
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "query_mode": query_mode.casefold() if query_mode else None,
        "source_count": source_count if source_count is not None else None,
    }

    canonical_payload = json.dumps(
        {field: event[field] for field in AUDIT_EVENT_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    event["event_hash"] = hashlib.sha256(canonical_payload).hexdigest()
    return event


def write_audit_event(event: dict[str, Any], log_path: str | Path | None = None) -> dict[str, Any]:
    """Append one canonical audit event to an append-only JSONL store."""
    path = Path(log_path) if log_path is not None else AUDIT_EVENT_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(event, sort_keys=True, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as audit_file:
        audit_file.write(serialized + "\n")
        audit_file.flush()
        os.fsync(audit_file.fileno())
    return event


def load_audit_events(log_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load canonical JSONL audit events, ignoring malformed or incomplete records."""
    path = Path(log_path) if log_path is not None else AUDIT_EVENT_LOG_PATH
    if not path.exists():
        return []

    events = []
    with path.open("r", encoding="utf-8") as audit_file:
        for line_number, line in enumerate(audit_file, start=1):
            try:
                event = json.loads(line)
                if not isinstance(event, dict) or not event.get("event_id"):
                    continue
                events.append(event)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed audit event at line %s", line_number)
    return events


def emit_audit_event(
    *,
    user_id: str,
    role: str,
    action: str,
    resource: str,
    authorization_decision: str,
    result: str,
    outcome_status: str,
    request_id: str | None = None,
    correlation_id: str | None = None,
    query_mode: str | None = None,
    source_count: int | None = None,
    log_path: str | Path | None = None,
) -> dict[str, Any]:
    """Create and persist a single authorization audit event."""
    try:
        event = create_audit_event(
            user_id=user_id,
            role=role,
            action=action,
            resource=resource,
            authorization_decision=authorization_decision,
            result=result,
            outcome_status=outcome_status,
            request_id=request_id,
            correlation_id=correlation_id,
            query_mode=query_mode,
            source_count=source_count,
        )
        return write_audit_event(event, log_path=log_path)
    except Exception as exc:
        logger.error("Unable to persist audit event: %s", exc, exc_info=True)
        return {}
