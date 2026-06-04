"""
Ralph-Analyse entry point — launches the internalized Ralph-Analyse Streamlit app
(DoorDash + UberEats pre/post period comparison dashboard) from the DeepDive agent.

Code lives in `ralph_analyse/` (app.py, analysis.py, data_loader.py, marketing.py).

Usage:
    from agents.deepdive import run_ralph_analyse
    run_ralph_analyse(port=8502)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

RALPH_ANALYSE_DIR = Path(__file__).resolve().parent / "ralph_analyse"


def ralph_analyse_dir() -> Path:
    return RALPH_ANALYSE_DIR


def run_ralph_analyse(*, port: int = 8502, wait: bool = False) -> dict[str, Any]:
    """
    Launch the Ralph-Analyse Streamlit dashboard. Returns process info;
    set `wait=True` to block until it exits.
    """
    app = RALPH_ANALYSE_DIR / "app.py"
    if not app.is_file():
        return {"status": "error", "message": f"app.py not found at {app}"}

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app),
            "--server.port",
            str(port),
            "--server.headless",
            "true",
        ],
        cwd=str(RALPH_ANALYSE_DIR),
        env={**os.environ},
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {"ralph_analyse": f"http://localhost:{port}"},
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result


if __name__ == "__main__":
    import json

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8502
    print(json.dumps(run_ralph_analyse(port=port, wait=True), indent=2))
