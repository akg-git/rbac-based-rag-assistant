import asyncio
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.routes.document_routes import upload_docs


class TestDocumentUploadAuthorization(unittest.TestCase):
    def run_upload(self, role, user):
        return asyncio.run(upload_docs(file=None, role=role, user=user))

    def test_non_admin_cannot_upload(self):
        with self.assertRaises(HTTPException) as context:
            self.run_upload("Finance", {"username": "analyst", "role": "Finance"})

        self.assertEqual(context.exception.status_code, 403)

    def test_missing_authenticated_user_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            self.run_upload("Finance", None)

        self.assertEqual(context.exception.status_code, 401)

    @patch("app.routes.document_routes.get_sqlite_conn")
    def test_unknown_target_role_is_rejected(self, get_sqlite_conn):
        cursor = Mock()
        cursor.fetchone.return_value = None
        get_sqlite_conn.return_value.cursor.return_value = cursor

        with self.assertRaises(HTTPException) as context:
            self.run_upload("Unknown", {"username": "admin", "role": "C-Level"})

        self.assertEqual(context.exception.status_code, 400)
        cursor.execute.assert_called_once_with(
            "SELECT 1 FROM roles WHERE role_name = ?", ("Unknown",)
        )


if __name__ == "__main__":
    unittest.main()
