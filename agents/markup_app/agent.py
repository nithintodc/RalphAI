import subprocess
import sys
from pathlib import Path
from typing import Any

def run_app(*, port: int = 8000, wait: bool = False) -> dict[str, Any]:
    """Launch the Markup App via a simple HTTP server."""
    app_dir = Path(__file__).resolve().parent
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port)],
        cwd=str(app_dir),
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {"markup_app": f"http://localhost:{port}"},
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result
