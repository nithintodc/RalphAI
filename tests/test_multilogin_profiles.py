"""Multilogin profile CSV mapping."""

import os
from pathlib import Path

import shared.multilogin_browser as mlx_mod
from shared.multilogin_browser import _profiles_csv, profile_id_for_email

ROOT = Path(__file__).resolve().parents[1]


class TestMultiloginProfiles:
    def setup_method(self):
        mlx_mod._profile_index = None

    def test_profile_id_for_email_case_insensitive(self):
        pid = profile_id_for_email("MCD+jeffreyopsllc@theondemandcompany.com")
        assert pid == "76849c39-1f04-4948-a502-e6bf59b96faf"

    def test_profiles_csv_relative_to_repo_not_cwd(self, monkeypatch):
        monkeypatch.setenv("MULTILOGIN_PROFILES_CSV", "multilogin/DD_Creds_with_profiles.csv")
        reporting = ROOT / "agents" / "reporting_browser_use"
        monkeypatch.chdir(reporting)
        csv_path = _profiles_csv()
        assert csv_path.is_file()
        assert csv_path == (ROOT / "multilogin" / "DD_Creds_with_profiles.csv").resolve()
