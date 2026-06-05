"""Registry for reporting_browser_use fork directories."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"

# Forks that use Gemini (main.py checks GEMINI_API_KEY).
_GEMINI_FORKS = frozenset(
    {
        "reporting_browser_use",
        "reporting_browser_use_melt",
        "reporting_browser_use_savvy",
    }
)

_BROWSER_USE_FORKS = frozenset({"reporting_browser_use_browser"})

_STUB_FORKS = frozenset(
    {
        "reporting_browser_use_new",
    }
)

ALL_FORK_IDS = tuple(
    sorted(_GEMINI_FORKS | _BROWSER_USE_FORKS | _STUB_FORKS)
)


class ForkMeta(TypedDict):
    id: str
    name: str
    description: str
    llm: str
    llm_env_key: str
    runnable: bool
    path: str
    note: str


def fork_directory(fork_id: str) -> Path:
    if fork_id not in ALL_FORK_IDS:
        raise KeyError(fork_id)
    return AGENTS_DIR / fork_id


def fork_main_script(fork_id: str) -> Path:
    return fork_directory(fork_id) / "main.py"


def is_fork_runnable(fork_id: str) -> bool:
    return fork_main_script(fork_id).is_file()


def _llm_for_fork(fork_id: str) -> tuple[str, str]:
    if fork_id in _BROWSER_USE_FORKS:
        return "browser_use", "BROWSER_USE_API_KEY"
    return "gemini", "GEMINI_API_KEY"


def _display_name(fork_id: str) -> str:
    if fork_id == "reporting_browser_use":
        return "Reporting Browser Use (Main)"
    suffix = fork_id.removeprefix("reporting_browser_use_")
    return f"Reporting Browser Use ({suffix.replace('_', ' ').title()})"


def _description(fork_id: str, llm: str) -> str:
    if fork_id == "reporting_browser_use":
        return "Default production fork — Multilogin + Gemini, full download → analysis → campaign pipeline."
    if fork_id == "reporting_browser_use_browser":
        return "Browser Use cloud LLM (BROWSER_USE_API_KEY) instead of Gemini."
    if fork_id == "reporting_browser_use_melt":
        return "Store-ID normalization in analysis/campaign params (Gemini)."
    if fork_id == "reporting_browser_use_savvy":
        return "Savvy variant — same lineage as melt (Gemini)."
    if fork_id in _STUB_FORKS:
        return "Reserved fork name — main.py not installed in this directory yet."
    return f"Reporting browser-use fork ({llm})."


def fork_metadata(fork_id: str) -> ForkMeta:
    if fork_id not in ALL_FORK_IDS:
        raise KeyError(fork_id)
    llm, llm_key = _llm_for_fork(fork_id)
    runnable = is_fork_runnable(fork_id)
    note = ""
    if fork_id in _STUB_FORKS:
        note = "Stub only — copy a full reporting_browser_use tree here or remove this fork."
    elif not runnable:
        note = "main.py missing — fork cannot run."
    return {
        "id": fork_id,
        "name": _display_name(fork_id),
        "description": _description(fork_id, llm),
        "llm": llm,
        "llm_env_key": llm_key,
        "runnable": runnable,
        "path": str(fork_directory(fork_id)),
        "note": note,
    }


def list_fork_metadata() -> list[ForkMeta]:
    return [fork_metadata(fid) for fid in ALL_FORK_IDS]


# Env keys passed through from the server .env (never from the browser).
SERVER_ENV_KEYS = (
    "GEMINI_API_KEY",
    "BROWSER_USE_API_KEY",
    "USE_MULTILOGIN",
    "MULTILOGIN_USERNAME",
    "MULTILOGIN_PASSWORD",
    "MULTILOGIN_PASSWORD_B64",
    "OPERATOR_PROFILE_MAPPING",
    "MULTILOGIN_PROFILES_CSV",
    "MULTILOGIN_FOLDER_ID",
    "MULTILOGIN_CDP_URL",
    "MULTILOGIN_AUTOMATION_TYPE",
    "LOCAL_BROWSER_CDP_URL",
    "CHROME_USER_DATA_DIR",
    "FORCE_FULL_RUN",
    "MAX_CAMPAIGNS_PER_SESSION",
    "SLACK_WEBHOOK_URL",
    "GOOGLE_SPREADSHEET_ID",
    "GCP_CREDENTIALS_PATH",
    "GCP_SERVICE_ACCOUNT_JSON",
    "OPERATOR_NAME",
    "DOORDASH_PARALLEL_CAMPAIGNS_BY_STORE",
    "USE_LOCAL_BROWSER",
)


def credential_env_keys() -> tuple[str, str]:
    return "DOORDASH_EMAIL", "DOORDASH_PASSWORD"


def env_status_for_fork(fork_id: str) -> dict[str, Any]:
    """Which env inputs are set on the server (values never returned)."""
    import os

    meta = fork_metadata(fork_id)
    email_key, password_key = credential_env_keys()
    keys = [email_key, password_key, meta["llm_env_key"], *SERVER_ENV_KEYS]
    configured: dict[str, bool] = {}
    for key in keys:
        val = os.getenv(key, "")
        configured[key] = bool(str(val).strip())
    return {
        "fork_id": fork_id,
        "runnable": meta["runnable"],
        "llm_env_key": meta["llm_env_key"],
        "configured": configured,
        "ready_to_run": meta["runnable"] and configured.get(meta["llm_env_key"], False),
    }
