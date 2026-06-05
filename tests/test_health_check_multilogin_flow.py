"""Health check → Multilogin CSV lookup wiring (no live Multilogin API)."""

import shared.multilogin_browser as mlx_mod
from agents.health_check.agent import _resolve_multilogin_profile_id
from shared.multilogin_browser import profile_id_for_email

_SAMPLE_EMAIL = "mcd+jeffreyopsllc@theondemandcompany.com"
_SAMPLE_PROFILE_ID = "76849c39-1f04-4948-a502-e6bf59b96faf"


class TestHealthCheckMultiloginFlow:
    def setup_method(self):
        mlx_mod._profile_index = None

    def test_csv_lookup_matches_csv_row(self, monkeypatch):
        monkeypatch.setenv("USE_MULTILOGIN", "true")
        pid = profile_id_for_email(_SAMPLE_EMAIL)
        assert pid == _SAMPLE_PROFILE_ID
        assert _resolve_multilogin_profile_id(_SAMPLE_EMAIL) == pid

    def test_csv_lookup_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("USE_MULTILOGIN", "true")
        assert profile_id_for_email(_SAMPLE_EMAIL.upper()) == _SAMPLE_PROFILE_ID

    def test_multilogin_disabled_returns_none(self, monkeypatch):
        monkeypatch.delenv("USE_MULTILOGIN", raising=False)
        monkeypatch.delenv("MULTILOGIN_CDP_URL", raising=False)
        assert _resolve_multilogin_profile_id(_SAMPLE_EMAIL) is None
