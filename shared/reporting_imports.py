"""Import ``agents.*`` modules from the reporting_browser_use tree (avoids package shadowing)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


def _is_reporting_agents_package(pkg: ModuleType, reporting_root: Path) -> bool:
    root_s = str(reporting_root.resolve()).replace("\\", "/")
    for entry in getattr(pkg, "__path__", []) or []:
        if root_s in str(entry).replace("\\", "/"):
            return True
    return False


def import_reporting_agents_module(
    module_name: str,
    reporting_root: Path | None = None,
) -> ModuleType:
    """
    Import ``agents.<module_name>`` from ``reporting_browser_use``.

    RalphAI also has a top-level ``agents`` package (offers, ads, strategist). When the API
    imports ``agents.offers.agent`` first, that shadows ``reporting_browser_use/agents/``.
    Drop the cached top-level ``agents`` package so imports resolve from ``reporting_root``.
    """
    from shared.config.settings import marketingreco_reporting_root

    root = (reporting_root or marketingreco_reporting_root()).resolve()
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)

    pkg = sys.modules.get("agents")
    if pkg is not None and not _is_reporting_agents_package(pkg, root):
        del sys.modules["agents"]

    return importlib.import_module(f"agents.{module_name}")
