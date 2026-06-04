#!/usr/bin/env python3
"""Create streamlit_app/.streamlit/secrets.toml from a service-account JSON if missing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
SECRETS_DIR = APP_DIR / ".streamlit"
SECRETS_FILE = SECRETS_DIR / "secrets.toml"
DEFAULT_JSON = APP_DIR / "todc-marketing-ad02212d4f16.json"


def _toml_escape_string(value: str) -> str:
    if "\n" in value:
        return '"""\n' + value + '\n"""'
    return json.dumps(value)


def json_to_secrets_toml(data: dict) -> str:
    lines = ["[gcp.service_account]"]
    for key, val in data.items():
        if val is None:
            continue
        lines.append(f"{key} = {_toml_escape_string(str(val))}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if SECRETS_FILE.is_file():
        print(f"secrets.toml already exists: {SECRETS_FILE}")
        return 0

    json_path = DEFAULT_JSON
    if not json_path.is_file():
        matches = sorted(APP_DIR.glob("todc-marketing-*.json"))
        json_path = matches[0] if matches else None

    if not json_path or not json_path.is_file():
        print(
            "No secrets.toml and no todc-marketing-*.json in streamlit_app/.\n"
            "Either copy secrets.toml.example → .streamlit/secrets.toml and fill in values,\n"
            "or place your service account JSON in streamlit_app/.",
            file=sys.stderr,
        )
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(json_to_secrets_toml(data), encoding="utf-8")
    print(f"Created {SECRETS_FILE} from {json_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
