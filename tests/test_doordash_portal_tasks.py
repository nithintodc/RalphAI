"""DoorDash portal entry + mapping credential helpers."""

import shared.operator_profile_mapping as mapping_mod
from shared.doordash_portal_tasks import (
    build_merchant_logout_block,
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

    def test_build_portal_entry_native_includes_logout(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shared.doordash_portal_tasks._multilogin_session_active", lambda: False)
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
        assert "bottom-left" in block.lower()
        assert "log out" in block.lower()
        assert "Reports" in block
        assert "test@example.com" in block
        assert "secret" in block
        assert next_step == 1

    def test_build_merchant_logout_block(self):
        block = build_merchant_logout_block(step_num=3)
        assert "STEP 3" in block
        assert "Log out" in block
        assert "bottom-left" in block.lower()

    def test_build_portal_entry_multilogin_skips_logout(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shared.doordash_portal_tasks._multilogin_session_active", lambda: True)
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

        block, _ = build_portal_entry_steps("test@example.com", None, step_num=0)
        assert "Multilogin profile already signed in" in block
        assert "do not log out" in block.lower()
        assert resolve_doordash_credentials("test@example.com") == (
            "test@example.com",
            "secret",
        )

    def test_build_campaign_session_preamble_prepared(self):
        from shared.doordash_portal_tasks import build_campaign_session_preamble_prepared

        block = build_campaign_session_preamble_prepared()
        assert "already signed in" in block.lower()
        assert "do not log out" in block.lower()
