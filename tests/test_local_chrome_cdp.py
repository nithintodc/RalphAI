"""Local Chrome CDP helpers for native browser-use."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from shared.local_chrome_cdp import (
    chrome_profile_status,
    ensure_local_chrome_cdp,
    is_local_cdp_host,
    parse_cdp_host_port,
    resolve_chrome_launch_config,
    resolve_user_data_dir,
)


class TestLocalChromeCdp:
    def test_parse_cdp_host_port_defaults(self):
        assert parse_cdp_host_port("http://localhost:9222") == ("localhost", 9222)

    def test_parse_cdp_host_port_explicit(self):
        assert parse_cdp_host_port("http://127.0.0.1:9333") == ("127.0.0.1", 9333)

    def test_is_local_cdp_host(self):
        assert is_local_cdp_host("localhost")
        assert is_local_cdp_host("127.0.0.1")
        assert not is_local_cdp_host("10.0.0.5")

    def test_resolve_user_data_dir_from_env(self, monkeypatch, tmp_path):
        profile = tmp_path / "my-profile"
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(profile))
        assert resolve_user_data_dir() == profile.resolve()

    def test_resolve_user_data_dir_default(self, monkeypatch, tmp_path):
        monkeypatch.delenv("CHROME_USER_DATA_DIR", raising=False)
        monkeypatch.setattr("shared.subprocess_env.repo_root", lambda: tmp_path)
        assert resolve_user_data_dir() == (tmp_path / ".cursor" / "chrome-debug-profile").resolve()

    def test_ensure_skips_when_cdp_already_up(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(tmp_path / "profile"))
        profile = resolve_user_data_dir()
        with patch("shared.local_chrome_cdp.is_cdp_available", return_value=True):
            with patch("shared.local_chrome_cdp.read_active_cdp_profile", return_value=profile):
                with patch("shared.local_chrome_cdp.subprocess.Popen") as popen:
                    ensure_local_chrome_cdp("http://localhost:9222")
                    popen.assert_not_called()

    def test_ensure_starts_chrome_when_cdp_down(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(tmp_path / "profile"))
        calls = {"n": 0}

        def fake_available(_url: str, *, timeout: float = 2.0) -> bool:
            calls["n"] += 1
            return calls["n"] > 1

        with patch("shared.local_chrome_cdp.is_cdp_available", side_effect=fake_available):
            with patch("shared.local_chrome_cdp.chrome_executable", return_value="/chrome"):
                with patch("shared.local_chrome_cdp._chrome_profile_in_use", return_value=False):
                    with patch("shared.local_chrome_cdp.subprocess.Popen") as popen:
                        ensure_local_chrome_cdp("http://localhost:9222", wait_seconds=3.0)
                        popen.assert_called_once()
                        args = popen.call_args[0][0]
                        assert args[0] == "/chrome"
                        assert "--remote-debugging-port=9222" in args
                        assert f"--user-data-dir={tmp_path / 'profile'}" in args

    def test_resolve_work_profile_path(self, monkeypatch):
        work = (
            Path.home() / "Library/Application Support/Google/Chrome/Profile 2"
        ).resolve()
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(work))
        cfg = resolve_chrome_launch_config()
        assert cfg.user_data_dir == work
        assert cfg.profile_directory is None
        assert cfg.effective_profile_path == work
        assert cfg.profile_display_name == "Work"

    def test_resolve_user_data_dir_per_operator_when_enabled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(tmp_path / "profile"))
        monkeypatch.setenv("RALPH_PER_OPERATOR_CHROME_PROFILES", "1")
        shared = resolve_user_data_dir()
        op = resolve_user_data_dir("ops@example.com")
        assert shared == (tmp_path / "profile").resolve()
        assert op == (tmp_path / "profile" / "operators" / "ops_example_com").resolve()

    def test_ensure_restarts_chrome_when_profile_changes(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(tmp_path / "profile"))
        monkeypatch.setenv("RALPH_PER_OPERATOR_CHROME_PROFILES", "1")
        profile_a = resolve_user_data_dir("a@example.com")
        profile_b = resolve_user_data_dir("b@example.com")
        calls = {"n": 0}

        def fake_available(_url: str, *, timeout: float = 2.0) -> bool:
            calls["n"] += 1
            return calls["n"] != 2  # up on first probe, down after stop, up again after start

        with patch("shared.local_chrome_cdp.is_cdp_available", side_effect=fake_available):
            with patch("shared.local_chrome_cdp.read_active_cdp_profile", return_value=profile_a):
                with patch("shared.local_chrome_cdp.stop_local_chrome_cdp") as stop:
                    with patch("shared.local_chrome_cdp.chrome_executable", return_value="/chrome"):
                        with patch("shared.local_chrome_cdp._chrome_profile_in_use", return_value=False):
                            with patch("shared.local_chrome_cdp.subprocess.Popen") as popen:
                                ensure_local_chrome_cdp(
                                    "http://localhost:9222",
                                    wait_seconds=2.0,
                                    doordash_email="b@example.com",
                                )
                                stop.assert_called_once()
                                popen.assert_called_once()
                                assert f"--user-data-dir={profile_b.parent}" in popen.call_args[0][0] or (
                                    f"--user-data-dir={profile_b}" in popen.call_args[0][0]
                                )

    def test_ensure_raises_when_chrome_missing(self):
        with patch("shared.local_chrome_cdp.is_cdp_available", return_value=False):
            with patch("shared.local_chrome_cdp.chrome_executable", return_value=None):
                with pytest.raises(RuntimeError, match="no Chrome executable"):
                    ensure_local_chrome_cdp("http://localhost:9222")

    def test_ensure_skips_remote_host(self):
        with patch("shared.local_chrome_cdp.is_cdp_available", return_value=False) as probe:
            with patch("shared.local_chrome_cdp.subprocess.Popen") as popen:
                ensure_local_chrome_cdp("http://10.0.0.5:9222")
                probe.assert_not_called()
                popen.assert_not_called()

    def test_chrome_profile_status_mismatch(self, monkeypatch, tmp_path):
        configured = tmp_path / "configured"
        active = tmp_path / "active"
        monkeypatch.setenv("CHROME_USER_DATA_DIR", str(configured))
        monkeypatch.setenv("LOCAL_BROWSER_CDP_URL", "http://localhost:9222")
        with patch("shared.local_chrome_cdp.is_cdp_available", return_value=True):
            with patch("shared.local_chrome_cdp.read_active_cdp_profile", return_value=active):
                status = chrome_profile_status()
        assert status["profile_mismatch"] is True
        assert status["warning"]
        assert str(configured.resolve()) == status["configured_profile"]
        assert str(active.resolve()) == status["active_cdp_profile"]
