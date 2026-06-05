"""DoorDash portal entry + mapping credential helpers."""

import shared.operator_profile_mapping as mapping_mod
from shared.doordash_portal_tasks import (
    build_portal_entry_steps,
    resolve_doordash_credentials,
)
from shared.operator_profile_mapping import credentials_for_email


class TestDoorDashPortalTasks:
    def setup_method(self):
        mapping_mod._clear_indexes()

    def test_credentials_for_email_from_mapping(self, tmp_path, monkeypatch):
        data = {
            "version": 1,
            "operators": [
                {
                    "operator_name": "3 Principles Integrated LLC",
                    "doordash_email": "mcd+3principlesillc@theondemandcompany.com",
                    "doordash_password": "mcdonalds1!",
                    "multilogin_profile_id": "abc",
                    "mapped": True,
                }
            ],
        }
        path = tmp_path / "operator_multilogin_mapping.json"
        path.write_text(__import__("json").dumps(data), encoding="utf-8")
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(path))

        email, password = credentials_for_email("mcd+3principlesillc@theondemandcompany.com")
        assert email == "mcd+3principlesillc@theondemandcompany.com"
        assert password == "mcdonalds1!"

    def test_build_portal_entry_includes_conditional_paths(self, tmp_path, monkeypatch):
        data = {
            "version": 1,
            "operators": [
                {
                    "operator_name": "Test Op",
                    "doordash_email": "test@example.com",
                    "doordash_password": "secret",
                    "multilogin_profile_id": "pid",
                    "mapped": True,
                }
            ],
        }
        path = tmp_path / "operator_multilogin_mapping.json"
        path.write_text(__import__("json").dumps(data), encoding="utf-8")
        monkeypatch.setenv("OPERATOR_PROFILE_MAPPING", str(path))

        block, next_step = build_portal_entry_steps("test@example.com", None, step_num=0)
        assert "PATH A" in block and "PATH B" in block
        assert "merchant/reports" in block
        assert "test@example.com" in block
        assert "secret" in block
        assert next_step == 1
        assert resolve_doordash_credentials("test@example.com") == (
            "test@example.com",
            "secret",
        )
