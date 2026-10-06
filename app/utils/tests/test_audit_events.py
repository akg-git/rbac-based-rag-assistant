import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from app.utils.audit_events import create_audit_event, write_audit_event


class TestAuditEventProducer(unittest.TestCase):
    def test_create_audit_event_hashes_canonical_fields(self):
        event = create_audit_event(
            user_id="alice",
            role="employee",
            action="read_data",
            resource="employee_records",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
            request_id="request-1",
            correlation_id="correlation-1",
            event_id="event-1",
            timestamp="2026-10-06T00:00:00Z",
        )

        fields = (
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
        )
        canonical = json.dumps(
            {field: event[field] for field in fields},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        self.assertEqual(
            event["event_hash"],
            hashlib.sha256(canonical).hexdigest(),
        )

    def test_write_audit_event_appends_jsonl_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "audit.jsonl"
            event = create_audit_event(
                user_id="bob",
                role="general",
                action="query",
                resource="sql_query",
                authorization_decision="denied",
                result="failure",
                outcome_status="denied",
                request_id="request-2",
                correlation_id="correlation-2",
                event_id="event-1",
            )

            first = write_audit_event(event, log_path=log_path)
            second = write_audit_event(
                {
                    **event,
                    "event_id": "event-2",
                    "request_id": "request-3",
                },
                log_path=log_path,
            )

            lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["event_id"], "event-1")
            self.assertEqual(json.loads(lines[1])["event_id"], "event-2")
            self.assertEqual(first["correlation_id"], "correlation-2")
            self.assertEqual(second["request_id"], "request-3")


if __name__ == "__main__":
    unittest.main()
