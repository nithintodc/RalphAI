"""
SuperApp entry point — launches the internalized TheSuperApp from the DeepDive agent.

TheSuperApp (TODC DoorDash/UberEats analytics dashboard) lives in `superapp/`:
- `superapp/app/`            React + Vite dashboard (parsers, period engine, exports)
- `superapp/streamlit_app/`  Streamlit Export Hub (Google Drive connectivity)
- `superapp/streamlit_app/export_api.py`  Local export API (Excel → Drive/Sheets,
  Partnership Report HTML → Google Doc)

Usage:
    from agents.deepdive import run_superapp, run_superapp_export_api
    run_superapp()                      # full stack (React + Streamlit + export API)
    run_superapp_export_api(port=8765)  # export API only (headless)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SUPERAPP_DIR = Path(__file__).resolve().parent / "superapp"


def superapp_dir() -> Path:
    return SUPERAPP_DIR


def run_superapp(
    *,
    vite_port: int = 5173,
    streamlit_port: int = 8501,
    export_api_port: int = 8765,
    wait: bool = False,
) -> dict[str, Any]:
    """
    Launch the full SuperApp stack via its `run.sh` (installs deps on first run,
    auto-bumps busy ports). Returns process info; set `wait=True` to block.
    """
    script = SUPERAPP_DIR / "run.sh"
    if not script.is_file():
        return {"status": "error", "message": f"run.sh not found at {script}"}

    env = {
        **os.environ,
        "VITE_PORT": str(vite_port),
        "STREAMLIT_PORT": str(streamlit_port),
        "EXPORT_API_PORT": str(export_api_port),
    }
    proc = subprocess.Popen(["bash", str(script)], cwd=str(SUPERAPP_DIR), env=env)
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {
            "react": f"http://localhost:{vite_port}",
            "streamlit": f"http://localhost:{streamlit_port}",
            "export_api": f"http://localhost:{export_api_port}/export",
        },
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result


def run_superapp_export_api(*, port: int = 8765, wait: bool = False) -> dict[str, Any]:
    """
    Launch only the SuperApp export API (no UI) — serves POST /export (Excel →
    Drive/Sheets) and POST /export-doc (Partnership Report HTML → Google Doc).
    """
    script = SUPERAPP_DIR / "streamlit_app" / "export_api.py"
    if not script.is_file():
        return {"status": "error", "message": f"export_api.py not found at {script}"}

    env = {**os.environ, "EXPORT_API_PORT": str(port)}
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(script.parent),
        env=env,
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {"export_api": f"http://localhost:{port}/export"},
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result


if __name__ == "__main__":
    import json

    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    if mode == "export-api":
        out = run_superapp_export_api(wait=True)
    else:
        out = run_superapp(wait=True)
    print(json.dumps(out, indent=2))
