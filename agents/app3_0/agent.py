import subprocess
import sys
from pathlib import Path
from typing import Any

def run_app(*, port: int = 8503, wait: bool = False) -> dict[str, Any]:
    """Launch the App3.0 Streamlit UI."""
    app = Path(__file__).resolve().parent / "app.py"
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app),
         "--server.port", str(port), "--server.headless", "true"],
        cwd=str(app.parent),
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {"app3_0": f"http://localhost:{port}"},
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result
