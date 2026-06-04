"""Health check operator loading from Airtable."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from shared.utils.airtable_directory import load_health_check_operators


class TestHealthCheckOperators(unittest.TestCase):
    @patch("shared.utils.airtable_directory.load_account_operators_airtable")
    def test_dedupes_by_email_and_requires_credentials(self, mock_load) -> None:
        mock_load.return_value = (
            [
                {
                    "business_name": "Alpha Ops",
                    "operator_id": "Alpha Ops",
                    "doordash_email": "a@x.com",
                    "doordash_password": "secret",
                },
                {
                    "business_name": "Alpha Ops Duplicate",
                    "operator_id": "Alpha Ops Duplicate",
                    "doordash_email": "a@x.com",
                    "doordash_password": "secret",
                },
                {
                    "business_name": "No Creds LLC",
                    "operator_id": "No Creds LLC",
                    "doordash_email": "",
                    "doordash_password": "",
                },
                {
                    "business_name": "Beta LLC",
                    "operator_id": "Beta LLC",
                    "doordash_email": "b@y.com",
                    "doordash_password": "pw2",
                },
            ],
            None,
        )
        ops, warning = load_health_check_operators()
        self.assertIsNone(warning)
        self.assertEqual(len(ops), 2)
        emails = {op["email"] for op in ops}
        self.assertEqual(emails, {"a@x.com", "b@y.com"})
        alpha = next(op for op in ops if op["email"] == "a@x.com")
        self.assertEqual(alpha["business_name"], "Alpha Ops")


if __name__ == "__main__":
    unittest.main()
