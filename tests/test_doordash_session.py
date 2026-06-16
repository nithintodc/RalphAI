"""Tests for per-operator DoorDash Chrome session tracking."""

from __future__ import annotations

from pathlib import Path

from shared.doordash_session import (
    emails_match,
    operator_profile_dir,
    per_operator_chrome_profiles_enabled,
    read_profile_session_email,
    should_switch_operator_session,
    write_profile_session_email,
)
from shared.local_chrome_cdp import resolve_user_data_dir


def test_shared_chrome_profile_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROME_USER_DATA_DIR", str(tmp_path / "chrome"))
    monkeypatch.delenv("RALPH_PER_OPERATOR_CHROME_PROFILES", raising=False)
    base = resolve_user_data_dir()
    assert resolve_user_data_dir("a@example.com") == base
    assert resolve_user_data_dir("b@example.com") == base
    assert not per_operator_chrome_profiles_enabled()


def test_operator_profile_dir_isolated_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROME_USER_DATA_DIR", str(tmp_path / "chrome"))
    monkeypatch.setenv("RALPH_PER_OPERATOR_CHROME_PROFILES", "1")
    a = resolve_user_data_dir("mcd+3principles@example.com")
    b = resolve_user_data_dir("dmd@example.com")
    assert a != b
    assert a == operator_profile_dir(tmp_path / "chrome", "mcd+3principles@example.com")


def test_should_switch_only_when_marker_differs(tmp_path):
    profile = tmp_path / "chrome"
    assert not should_switch_operator_session(profile, "c@example.com")
    write_profile_session_email(profile, "a@example.com")
    assert not should_switch_operator_session(profile, "a@example.com")
    assert should_switch_operator_session(profile, "b@example.com")


def test_profile_session_marker_roundtrip(tmp_path):
    profile = tmp_path / "op-profile"
    write_profile_session_email(profile, "DMD@Example.COM")
    assert read_profile_session_email(profile) == "dmd@example.com"
    assert emails_match("dmd@example.com", "DMD@Example.COM")
