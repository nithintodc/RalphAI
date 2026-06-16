import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_app(*, port: int = 0, wait: bool = False) -> dict[str, Any]:
    """Launch the main reporting browser-use pipeline."""
    root = Path(__file__).resolve().parent
    script = root / "main.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(root),
        env=env,
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result
