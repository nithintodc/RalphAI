"""Tests for account directory (CSV parser + Airtable loader)."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.utils.account_directory import load_account_operators, load_account_operators_csv


class TestAccountDirectory(unittest.TestCase):
    def test_load_groups_and_picks_credentials(self) -> None:
        td = Path(tempfile.mkdtemp())
        p = td / "accounts.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                [
                    "Business Name (original)",
                    "DoorDash Login",
                    "DoorDash Password",
                ]
            )
            w.writerow(["Alpha Ops", "", ""])
            w.writerow(["Alpha Ops", "a@x.com", "secret1"])
            w.writerow(["Beta LLC", "b@y.com", ""])

        ops, err = load_account_operators_csv(p)
        self.assertIsNone(err)
        self.assertEqual(len(ops), 2)
        self.assertEqual(ops[0]["business_name"], "Alpha Ops")
        self.assertEqual(ops[0]["doordash_email"], "a@x.com")
        self.assertEqual(ops[0]["doordash_password"], "secret1")
        self.assertEqual(ops[1]["business_name"], "Beta LLC")
        self.assertEqual(ops[1]["doordash_email"], "b@y.com")
        self.assertEqual(ops[1]["doordash_password"], "")

    def test_load_missing_file(self) -> None:
        ops, err = load_account_operators_csv(Path("/nonexistent/no.csv"))
        self.assertEqual(ops, [])
        self.assertIsNotNone(err)

    @patch("shared.utils.airtable_directory.load_account_operators_airtable")
    def test_load_account_operators_delegates_to_airtable(self, mock_airtable) -> None:
        mock_airtable.return_value = (
            [{"business_name": "Acme", "operator_id": "Acme", "doordash_email": "a@x.com", "doordash_password": "pw"}],
            None,
        )
        ops, err = load_account_operators()
        mock_airtable.assert_called_once()
        self.assertIsNone(err)
        self.assertEqual(ops[0]["business_name"], "Acme")


if __name__ == "__main__":
    unittest.main()
