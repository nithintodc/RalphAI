"""Browser mode switch (multilogin vs native)."""

from __future__ import annotations

import json

import pytest

from shared.browser_settings import (
    BROWSER_MODE_MULTILOGIN,
    BROWSER_MODE_NATIVE,
    apply_browser_mode_to_env,
    get_browser_mode,
    multilogin_mode_active,
    save_browser_mode,
)


class TestBrowserSettings:
    def test_default_native_without_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BROWSER_MODE", "multilogin")
        monkeypatch.setenv("USE_MULTILOGIN", "true")
        monkeypatch.setenv("USE_LOCAL_BROWSER", "true")
        monkeypatch.setattr(
            "shared.browser_settings.browser_settings_path",
            lambda: tmp_path / "browser_settings.json",
        )
        assert get_browser_mode() == BROWSER_MODE_NATIVE
        assert not multilogin_mode_active()

    def test_env_does_not_override_persisted_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("BROWSER_MODE", "native")
        path = tmp_path / "browser_settings.json"
        path.write_text(json.dumps({"mode": "multilogin"}), encoding="utf-8")
        monkeypatch.setattr("shared.browser_settings.browser_settings_path", lambda: path)
        assert get_browser_mode() == BROWSER_MODE_MULTILOGIN

    def test_persisted_file_native(self, monkeypatch, tmp_path):
        path = tmp_path / "browser_settings.json"
        path.write_text(json.dumps({"mode": "native"}), encoding="utf-8")
        monkeypatch.setattr("shared.browser_settings.browser_settings_path", lambda: path)
        assert get_browser_mode() == BROWSER_MODE_NATIVE

    def test_apply_browser_mode_to_env_multilogin(self, monkeypatch, tmp_path):
        path = tmp_path / "browser_settings.json"
        path.write_text(json.dumps({"mode": "multilogin"}), encoding="utf-8")
        monkeypatch.setattr("shared.browser_settings.browser_settings_path", lambda: path)
        env: dict[str, str] = {}
        apply_browser_mode_to_env(env)
        assert env["BROWSER_MODE"] == BROWSER_MODE_MULTILOGIN
        assert env["USE_MULTILOGIN"] == "true"
        assert env["USE_LOCAL_BROWSER"] == "false"

    def test_save_browser_mode_writes_file(self, monkeypatch, tmp_path):
        path = tmp_path / "browser_settings.json"
        monkeypatch.setattr("shared.browser_settings.browser_settings_path", lambda: path)
        result = save_browser_mode("multilogin")
        assert result["mode"] == BROWSER_MODE_MULTILOGIN
        assert json.loads(path.read_text(encoding="utf-8"))["mode"] == "multilogin"

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="mode must be"):
            save_browser_mode("invalid")
