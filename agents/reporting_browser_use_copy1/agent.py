import subprocess
import sys
from pathlib import Path
from typing import Any

def run_app(*, port: int = 0, wait: bool = False) -> dict[str, Any]:
    """Launch the Browser-Use script."""
    script = Path(__file__).resolve().parent / "main.py"
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(script.parent),
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result
