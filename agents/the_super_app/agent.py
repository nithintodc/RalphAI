import subprocess
from pathlib import Path
from typing import Any
import sys

def run_app(*, port: int = 3000, wait: bool = False) -> dict[str, Any]:
    """Launch TheSuperApp frontend UI via npm run dev (or similar) plus streamlit export API."""
    app_dir = Path(__file__).resolve().parent / "app"
    
    # Run the frontend (Vite)
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(app_dir),
    )
    
    result: dict[str, Any] = {
        "status": "started",
        "frontend_pid": frontend_proc.pid,
        "urls": {"the_super_app": "http://localhost:5173"}, # default vite port
    }
    
    if wait:
        frontend_proc.wait()
        result["status"] = "exited"
    return result
