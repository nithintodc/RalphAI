import subprocess
from pathlib import Path
from typing import Any

def run_app(*, port: int = 3000, wait: bool = False) -> dict[str, Any]:
    """Launch the Marketing Breakdown Node.js UI."""
    server = Path(__file__).resolve().parent / "server.js"
    proc = subprocess.Popen(
        ["node", str(server)],
        cwd=str(server.parent),
    )
    result: dict[str, Any] = {
        "status": "started",
        "pid": proc.pid,
        "urls": {"marketing_breakdown": "http://localhost:3000"},
    }
    if wait:
        result["exit_code"] = proc.wait()
        result["status"] = "exited"
    return result
