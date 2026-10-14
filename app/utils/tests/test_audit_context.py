import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.utils.audit_context import (
    AuditContext,
    get_audit_context,
    initialize_request_audit_context,
)


class TestAuditContext(unittest.TestCase):
    def make_request(self, correlation_id=""):
        return SimpleNamespace(
            headers={"X-Correlation-ID": correlation_id},
            state=SimpleNamespace(),
        )

    def test_request_ids_are_unique_and_correlation_id_is_preserved(self):
        first_request = self.make_request("trace-123")
        second_request = self.make_request("trace-456")

        first_request_id, first_correlation_id = initialize_request_audit_context(first_request)
        second_request_id, second_correlation_id = initialize_request_audit_context(second_request)

        self.assertNotEqual(first_request_id, second_request_id)
        self.assertEqual(first_correlation_id, "trace-123")
        self.assertEqual(second_correlation_id, "trace-456")

    def test_invalid_correlation_id_falls_back_to_request_id(self):
        request = self.make_request("contains spaces")

        request_id, correlation_id = initialize_request_audit_context(request)

        self.assertEqual(correlation_id, request_id)

    def test_dependency_uses_authenticated_actor_and_request_state(self):
        request = self.make_request()
        request.state.request_id = "request-1"
        request.state.correlation_id = "correlation-1"

        audit = get_audit_context(
            request,
            user={"username": "admin", "role": "C-Level"},
        )

        self.assertEqual(
            audit,
            AuditContext(
                username="admin",
                role="C-Level",
                request_id="request-1",
                correlation_id="correlation-1",
            ),
        )

    @patch("app.utils.audit_context.emit_audit_event")
    def test_emit_reuses_context_fields(self, emit_audit_event):
        audit = AuditContext(
            username="admin",
            role="C-Level",
            request_id="request-1",
            correlation_id="correlation-1",
        )

        audit.emit(
            action="user.create",
            resource="user:analyst",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
        )

        emit_audit_event.assert_called_once_with(
            user_id="admin",
            role="C-Level",
            action="user.create",
            resource="user:analyst",
            authorization_decision="allowed",
            result="success",
            outcome_status="authorized",
            request_id="request-1",
            correlation_id="correlation-1",
            query_mode="administration",
        )


if __name__ == "__main__":
    unittest.main()
