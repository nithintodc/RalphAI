"""`/marketingreco`"""

from __future__ import annotations


def handle(
    operator_id: str,
    *,
    mode: str = "deepdive",
    financial_report_path: str | None = None,
    doordash_email: str | None = None,
    doordash_password: str | None = None,
    reporting_root: str = "Reporting-browser-use-claude-code",
) -> dict:
    from agents.marketingreco.agent import run

    return run(
        operator_id,
        mode=mode,  # type: ignore[arg-type]
        financial_report_path=financial_report_path,
        doordash_email=doordash_email,
        doordash_password=doordash_password,
        reporting_root=reporting_root,
    )
