"""Operator ↔ Multilogin profile mapping repository."""

import json
from pathlib import Path

import pytest

import shared.operator_profile_mapping as mapping_mod
from shared.multilogin_browser import profile_id_for_email
from shared.operator_profile_mapping import (
    build_venn_view,
    mapping_path,
    normalize_name,
    prepare_save_payload,
    profile_id_for_operator_name,
    save_mapping_payload,
    write_mapping,
)

ROOT = Path(__file__).resolve().parents[1]
_SAMPLE_EMAIL = "mcd+jeffreyopsllc@theondemandcompany.com"
_SAMPLE_PROFILE_ID = "76849c39-1f04-4948-a502-e6bf59b96faf"


class TestOperatorProfileMapping:
    def setup_method(self):
        mapping_mod._clear_indexes()

    def test_normalize_name_strips_doordash_prefix(self):
        assert normalize_name("DoorDash_Jeffreyops_LLC") == normalize_name("Jeffreyops LLC")

    def test_profile_id_for_email_from_json(self, tmp_path, monkeypatch):
        data = {
            "version": 1,
            "operators": [
                {
                    "operator_name": "Jeffreyops LLC",
                    "doordash_email": _SAMPLE_EMAIL,
                    "multilogin_profile_id": _SAMPLE_PROFILE_ID,
                    "multilogin_profile_name": "Jeffreyops_LLC",
                    "match_method": "legacy_csv_email",
                    "mapped": True,
                }
            ],
        }
        path = tmp_path / "operator_multilogin_mapping.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(path))

        assert profile_id_for_email(_SAMPLE_EMAIL.upper()) == _SAMPLE_PROFILE_ID
        assert profile_id_for_operator_name("Jeffreyops LLC") == _SAMPLE_PROFILE_ID

    def test_legacy_csv_fallback(self, tmp_path, monkeypatch):
        mapping = tmp_path / "missing.json"
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(mapping))
        monkeypatch.setenv(
            "MULTILOGIN_PROFILES_CSV",
            "multilogin/DD_Creds_with_profiles.csv",
        )
        assert profile_id_for_email(_SAMPLE_EMAIL) == _SAMPLE_PROFILE_ID

    def test_mapping_path_relative_to_repo_not_cwd(self, monkeypatch):
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", "operator_multilogin_mapping.json")
        reporting = ROOT / "agents" / "reporting_browser_use"
        monkeypatch.chdir(reporting)
        assert mapping_path() == (ROOT / "operator_multilogin_mapping.json").resolve()

    def test_build_venn_view(self):
        data = {
            "operators": [
                {"operator_name": "A", "mapped": False},
                {"operator_name": "B", "mapped": True, "multilogin_profile_id": "p1"},
            ],
            "unmatched_profiles": [{"profile_id": "p2", "profile_name": "Orphan"}],
        }
        venn = build_venn_view(data)
        assert venn["counts"]["only_airtable"] == 1
        assert venn["counts"]["in_both"] == 1
        assert venn["counts"]["only_multilogin"] == 1

    def test_prepare_save_payload_rejects_duplicate_profile(self):
        body = {
            "operators": [
                {"operator_name": "Op1", "doordash_email": "a@x.com", "multilogin_profile_id": "same-id"},
                {"operator_name": "Op2", "doordash_email": "b@x.com", "multilogin_profile_id": "same-id"},
            ],
            "unmatched_profiles": [],
        }
        with pytest.raises(ValueError, match="more than one operator"):
            prepare_save_payload(body)

    def test_save_mapping_payload_writes_file(self, tmp_path, monkeypatch):
        path = tmp_path / "operator_multilogin_mapping.json"
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(path))
        mapping_mod._clear_indexes()
        body = {
            "operators": [
                {
                    "operator_name": "Alpha",
                    "doordash_email": "alpha@example.com",
                    "multilogin_profile_id": "pid-1",
                    "multilogin_profile_name": "DoorDash_Alpha",
                }
            ],
            "unmatched_profiles": [{"profile_id": "pid-2", "profile_name": "Unused"}],
        }
        result = save_mapping_payload(body)
        assert path.is_file()
        assert result["mapping"]["operators"][0]["match_method"] == "manual"
        assert result["venn"]["counts"]["in_both"] == 1

    def test_write_mapping_emits_csv(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(tmp_path / "operator_multilogin_mapping.json"))
        data = {
            "version": 1,
            "operators": [
                {
                    "operator_name": "Alpha",
                    "doordash_email": "alpha@example.com",
                    "multilogin_profile_id": "pid-1",
                    "multilogin_profile_name": "DoorDash_Alpha",
                    "match_method": "operator_name",
                    "mapped": True,
                }
            ],
        }
        json_path, csv_path = write_mapping(data)
        assert json_path.is_file()
        assert csv_path.is_file()
        csv_text = csv_path.read_text(encoding="utf-8")
        assert "alpha@example.com" in csv_text
        assert ",True" in csv_text or ",True\n" in csv_text

    def test_save_updates_mapped_false_in_csv(self, tmp_path, monkeypatch):
        path = tmp_path / "operator_multilogin_mapping.json"
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(path))
        mapping_mod._clear_indexes()
        body = {
            "operators": [
                {
                    "operator_name": "Unmapped Op",
                    "doordash_email": "unmapped@example.com",
                    "multilogin_profile_id": "",
                }
            ],
            "unmatched_profiles": [],
        }
        result = save_mapping_payload(body)
        csv_path = Path(result["csv_path"])
        assert result["mapping"]["operators"][0]["mapped"] is False
        assert ",False" in csv_path.read_text(encoding="utf-8")
