import subprocess
from pathlib import Path
from typing import Any

DEFAULT_PORT = 5180


def run_app(*, port: int = DEFAULT_PORT, wait: bool = False) -> dict[str, Any]:
    """Launch TheSuperApp frontend UI on a dedicated Vite port (not Ralph dashboard 5173)."""
    app_dir = Path(__file__).resolve().parent / "app"

    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(port), "--strictPort"],
        cwd=str(app_dir),
    )

    result: dict[str, Any] = {
        "status": "started",
        "pid": frontend_proc.pid,
        "frontend_pid": frontend_proc.pid,
        "urls": {"the_super_app": f"http://localhost:{port}"},
    }

    if wait:
        frontend_proc.wait()
        result["status"] = "exited"
    return result
