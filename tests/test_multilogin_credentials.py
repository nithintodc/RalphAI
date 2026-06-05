"""Multilogin password resolution from base64 env."""

import base64

import hashlib

from multilogin.credentials import multilogin_password, multilogin_password_for_api


class TestMultiloginCredentials:
    def test_b64_decodes_password(self, monkeypatch):
        raw = "Upworks123$"
        monkeypatch.delenv("MULTILOGIN_PASSWORD", raising=False)
        monkeypatch.setenv("MULTILOGIN_PASSWORD_B64", base64.b64encode(raw.encode()).decode())
        assert multilogin_password() == raw

    def test_plain_password_fallback(self, monkeypatch):
        monkeypatch.delenv("MULTILOGIN_PASSWORD_B64", raising=False)
        monkeypatch.setenv("MULTILOGIN_PASSWORD", "plain-only")
        assert multilogin_password() == "plain-only"

    def test_api_password_is_md5_hex_by_default(self, monkeypatch):
        monkeypatch.delenv("MULTILOGIN_SIGNIN_PASSWORD_PLAIN", raising=False)
        monkeypatch.setenv("MULTILOGIN_PASSWORD", "Upworks123$")
        expected = hashlib.md5(b"Upworks123$").hexdigest()
        assert multilogin_password_for_api() == expected

    def test_b64_takes_priority_over_plain(self, monkeypatch):
        monkeypatch.setenv("MULTILOGIN_PASSWORD", "wrong")
        monkeypatch.setenv(
            "MULTILOGIN_PASSWORD_B64",
            base64.b64encode(b"from-b64").decode(),
        )
        assert multilogin_password() == "from-b64"
