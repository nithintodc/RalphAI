"""Shared Streamlit presentation helpers for the TODC analytics app."""

from html import escape
import re
from typing import Iterable, Optional, Tuple

import pandas as pd
import streamlit as st


TONE_STYLES = {
    "neutral": ("#344054", "#F8FAFC", "#E5E7EB"),
    "info": ("#1D4ED8", "#EFF6FF", "#BFDBFE"),
    "success": ("#047857", "#ECFDF3", "#A7F3D0"),
    "warning": ("#B45309", "#FFFBEB", "#FDE68A"),
    "danger": ("#B42318", "#FEF3F2", "#FDA29B"),
    "dd": ("#C2410C", "#FFF7ED", "#FED7AA"),
    "ue": ("#15803D", "#F0FDF4", "#BBF7D0"),
    "ads": ("#0F766E", "#F0FDFA", "#99F6E4"),
}


def inject_global_styles() -> None:
    """Inject a consistent SaaS-style visual system across Streamlit pages."""
    st.markdown(
        """
<style>
:root {
    --todc-bg: #F7F8FA;
    --todc-surface: #FFFFFF;
    --todc-surface-muted: #F8FAFC;
    --todc-border: #E5E7EB;
    --todc-border-strong: #D0D5DD;
    --todc-text: #101828;
    --todc-muted: #667085;
    --todc-subtle: #98A2B3;
    --todc-primary: #2563EB;
    --todc-primary-hover: #1D4ED8;
    --todc-success: #047857;
    --todc-warning: #B45309;
    --todc-danger: #B42318;
}

html, body, .stApp, .stMarkdown, p, label {
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}
.stApp {
    background: var(--todc-bg) !important;
    color: var(--todc-text) !important;
}
.block-container {
    max-width: 1500px;
    padding-top: 1.15rem;
    padding-bottom: 3.25rem;
}
#MainMenu, footer { visibility: hidden; }
header { background: transparent !important; }
h1, h2, h3, h4 {
    color: var(--todc-text) !important;
    letter-spacing: 0 !important;
}
p, label, .stCaption, .stMarkdown {
    color: #475467;
}
hr {
    border-color: var(--todc-border) !important;
    margin: 1.25rem 0;
}
section[data-testid="stSidebar"] {
    background: var(--todc-surface) !important;
    border-right: 1px solid var(--todc-border) !important;
}
section[data-testid="stSidebar"] * {
    color: var(--todc-text) !important;
}
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] p {
    color: var(--todc-muted) !important;
}
section[data-testid="stSidebar"] hr {
    margin: 1rem 0 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    justify-content: flex-start;
    background: #FFFFFF !important;
    color: #344054 !important;
    border: 1px solid var(--todc-border) !important;
    border-radius: 8px !important;
    min-height: 2.65rem !important;
    box-shadow: none !important;
    font-weight: 720 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #EFF6FF !important;
    border-color: #BFDBFE !important;
    color: var(--todc-primary-hover) !important;
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
    background: #EFF6FF !important;
    border-color: #BFDBFE !important;
    color: var(--todc-primary-hover) !important;
}
section[data-testid="stSidebar"] .stButton > button:disabled {
    background: #F8FAFC !important;
    border-color: #EAECF0 !important;
    color: #98A2B3 !important;
}

.stButton > button,
.stDownloadButton > button {
    min-height: 2.55rem;
    border-radius: 8px !important;
    border: 1px solid var(--todc-border-strong) !important;
    box-shadow: none !important;
    font-weight: 650 !important;
}
.stButton > button[data-testid="baseButton-primary"],
.stDownloadButton > button[data-testid="baseButton-primary"] {
    background: var(--todc-primary) !important;
    border-color: var(--todc-primary) !important;
    color: #FFFFFF !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stDownloadButton > button[data-testid="baseButton-primary"]:hover {
    background: var(--todc-primary-hover) !important;
    border-color: var(--todc-primary-hover) !important;
    color: #FFFFFF !important;
    transform: none !important;
}
.stButton > button:not([data-testid="baseButton-primary"]),
.stDownloadButton > button:not([data-testid="baseButton-primary"]) {
    background: #FFFFFF !important;
    color: #344054 !important;
}
.stButton > button:not([data-testid="baseButton-primary"]):hover,
.stDownloadButton > button:not([data-testid="baseButton-primary"]):hover {
    border-color: var(--todc-primary) !important;
    color: var(--todc-primary-hover) !important;
    background: #EFF6FF !important;
}
.stButton > button:disabled,
.stDownloadButton > button:disabled {
    background: #F2F4F7 !important;
    color: #98A2B3 !important;
    border-color: #EAECF0 !important;
}
.stTextInput input,
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stDateInput input {
    border-radius: 8px !important;
    border: 1px solid var(--todc-border-strong) !important;
    background: #FFFFFF !important;
}
.stTextInput input:focus {
    border-color: var(--todc-primary) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12) !important;
}
.stDataFrame, [data-testid="stDataFrame"] {
    border: 1px solid var(--todc-border) !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border: 1px solid var(--todc-border) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    padding: 0.95rem 1rem !important;
}
[data-testid="stMetric"] label {
    color: var(--todc-muted) !important;
    font-size: 0.76rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--todc-text) !important;
    font-size: 1.45rem !important;
    font-weight: 750 !important;
}
[data-testid="stTabs"] button {
    font-weight: 650 !important;
}

.saas-page-header {
    border-bottom: 1px solid var(--todc-border);
    padding: 0.25rem 0 1.05rem;
    margin-bottom: 1.15rem;
}
.saas-header-row {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-end;
}
.saas-kicker {
    color: var(--todc-primary);
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.28rem;
}
.saas-title {
    color: var(--todc-text);
    font-size: 1.9rem;
    line-height: 1.12;
    font-weight: 800;
}
.saas-subtitle {
    color: var(--todc-muted);
    font-size: 0.95rem;
    margin-top: 0.38rem;
    max-width: 820px;
}
.saas-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    justify-content: flex-end;
}
.saas-chip {
    display: inline-flex;
    align-items: center;
    min-height: 1.75rem;
    padding: 0.22rem 0.55rem;
    border-radius: 6px;
    border: 1px solid var(--todc-border);
    background: #FFFFFF;
    color: #344054;
    font-size: 0.74rem;
    font-weight: 750;
    white-space: nowrap;
}
.saas-section-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
    border-bottom: 1px solid var(--todc-border);
    padding: 0.25rem 0 0.6rem;
    margin: 1.2rem 0 0.85rem;
}
.saas-section-title {
    color: var(--todc-text);
    font-size: 1rem;
    font-weight: 780;
    line-height: 1.25;
}
.saas-section-subtitle {
    color: var(--todc-muted);
    font-size: 0.82rem;
    margin-top: 0.2rem;
}
.saas-stepper {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    margin: 0.5rem 0 1.1rem;
}
.saas-step {
    background: #FFFFFF;
    border: 1px solid var(--todc-border);
    border-left: 3px solid var(--todc-border-strong);
    border-radius: 8px;
    padding: 0.75rem 0.85rem;
}
.saas-step.done { border-left-color: var(--todc-success); }
.saas-step.active { border-left-color: var(--todc-primary); background: #F8FBFF; }
.saas-step.waiting { border-left-color: #D0D5DD; }
.saas-step-index {
    color: var(--todc-muted);
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.saas-step-title {
    color: var(--todc-text);
    font-weight: 760;
    font-size: 0.9rem;
    margin-top: 0.18rem;
}
.saas-step-note {
    color: var(--todc-muted);
    font-size: 0.76rem;
    margin-top: 0.2rem;
}
.saas-stat-card,
.saas-rule-card,
.saas-file-row,
.saas-status-card {
    background: #FFFFFF;
    border: 1px solid var(--todc-border);
    border-radius: 8px;
}
.saas-stat-card {
    padding: 0.85rem 0.95rem;
    min-height: 5.4rem;
}
.saas-stat-label {
    color: var(--todc-muted);
    font-size: 0.74rem;
    font-weight: 750;
}
.saas-stat-value {
    color: var(--todc-text);
    font-size: 1.25rem;
    line-height: 1.2;
    font-weight: 800;
    margin-top: 0.22rem;
}
.saas-stat-note {
    color: var(--todc-muted);
    font-size: 0.75rem;
    margin-top: 0.25rem;
}
.saas-rule-card {
    padding: 0.78rem 0.88rem;
    min-height: 6.2rem;
}
.saas-rule-pattern {
    color: var(--todc-text);
    font-weight: 800;
    font-size: 0.82rem;
}
.saas-rule-target {
    color: var(--todc-muted);
    font-size: 0.78rem;
    margin-top: 0.22rem;
}
.saas-rule-count {
    color: var(--todc-subtle);
    font-size: 0.72rem;
    margin-top: 0.55rem;
}
.saas-file-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 0.85rem;
    margin: 0.38rem 0;
}
.saas-file-token {
    width: 2rem;
    height: 2rem;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.78rem;
    font-weight: 850;
    flex: 0 0 auto;
}
.saas-file-main {
    min-width: 0;
    flex: 1;
}
.saas-file-name {
    color: var(--todc-text);
    font-weight: 720;
    font-size: 0.86rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.saas-file-meta {
    color: var(--todc-muted);
    font-size: 0.75rem;
    margin-top: 0.12rem;
}
.saas-status-card {
    padding: 0.85rem 0.9rem;
    min-height: 5.25rem;
}
.saas-status-label {
    color: var(--todc-muted);
    font-size: 0.75rem;
    font-weight: 720;
}
.saas-status-value {
    font-size: 0.95rem;
    font-weight: 800;
    margin-top: 0.18rem;
}
.saas-alert {
    border: 1px solid var(--todc-border);
    border-radius: 8px;
    background: #FFFFFF;
    padding: 0.85rem 0.95rem;
    color: #344054;
    font-size: 0.85rem;
}
.saas-alert.info { border-color: #BFDBFE; background: #EFF6FF; color: #1E3A8A; }
.saas-alert.success { border-color: #A7F3D0; background: #ECFDF3; color: #065F46; }
.saas-alert.warning { border-color: #FDE68A; background: #FFFBEB; color: #92400E; }
.saas-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.85rem;
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--todc-border);
    margin-bottom: 0.9rem;
}
.saas-toolbar-title {
    color: var(--todc-text);
    font-size: 0.95rem;
    font-weight: 780;
}
.saas-toolbar-subtitle {
    color: var(--todc-muted);
    font-size: 0.78rem;
    margin-top: 0.1rem;
}
.saas-compact-note {
    color: var(--todc-muted);
    font-size: 0.78rem;
}
.sidebar-shell {
    padding: 0.75rem 0.15rem 0.25rem;
}
.sidebar-brand {
    border: 1px solid var(--todc-border);
    border-radius: 10px;
    background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
    padding: 0.85rem 0.9rem;
}
.sidebar-brand-kicker {
    color: var(--todc-primary) !important;
    font-size: 0.68rem;
    font-weight: 850;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}
.sidebar-brand-title {
    color: var(--todc-text) !important;
    font-size: 1.12rem;
    line-height: 1.2;
    font-weight: 820;
    margin-top: 0.18rem;
}
.sidebar-brand-subtitle {
    color: var(--todc-muted) !important;
    font-size: 0.76rem;
    margin-top: 0.28rem;
}
.sidebar-panel {
    border: 1px solid var(--todc-border);
    border-radius: 10px;
    background: #FFFFFF;
    padding: 0.8rem 0.85rem;
    margin-top: 0.75rem;
}
.sidebar-panel-title {
    color: var(--todc-text) !important;
    font-size: 0.78rem;
    font-weight: 820;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.55rem;
}
.sidebar-status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.55rem;
    padding: 0.42rem 0;
    border-top: 1px solid #F2F4F7;
}
.sidebar-status-row:first-of-type {
    border-top: 0;
}
.sidebar-status-label {
    color: #344054 !important;
    font-size: 0.78rem;
    font-weight: 680;
}
.sidebar-status-value {
    border: 1px solid var(--todc-border);
    border-radius: 999px;
    padding: 0.12rem 0.42rem;
    font-size: 0.68rem;
    font-weight: 800;
    white-space: nowrap;
}
.sidebar-status-value.success {
    color: #047857 !important;
    background: #ECFDF3;
    border-color: #A7F3D0;
}
.sidebar-status-value.warning {
    color: #B45309 !important;
    background: #FFFBEB;
    border-color: #FDE68A;
}
.sidebar-status-value.neutral {
    color: #475467 !important;
    background: #F8FAFC;
    border-color: #E5E7EB;
}
.sidebar-nav-current {
    display: block;
    border: 1px solid #BFDBFE;
    border-radius: 8px;
    background: #EFF6FF;
    color: var(--todc-primary-hover) !important;
    padding: 0.68rem 0.75rem;
    font-size: 0.86rem;
    font-weight: 780;
    margin-bottom: 0.45rem;
}
.sidebar-nav-note {
    color: var(--todc-muted) !important;
    font-size: 0.72rem;
    line-height: 1.35;
    margin-top: 0.45rem;
}
.sidebar-mini-stat {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.45rem;
    margin-top: 0.65rem;
}
.sidebar-mini-card {
    border: 1px solid var(--todc-border);
    border-radius: 8px;
    background: #F8FAFC;
    padding: 0.55rem 0.6rem;
}
.sidebar-mini-label {
    color: var(--todc-muted) !important;
    font-size: 0.68rem;
    font-weight: 760;
}
.sidebar-mini-value {
    color: var(--todc-text) !important;
    font-size: 0.9rem;
    font-weight: 820;
    margin-top: 0.1rem;
}
.todc-section-header {
    border-bottom: 1px solid var(--todc-border) !important;
    color: var(--todc-text) !important;
    font-size: 0.98rem !important;
    letter-spacing: 0 !important;
}
.dashboard-heading,
.page-heading {
    border-bottom: 1px solid var(--todc-border) !important;
}
@media (max-width: 900px) {
    .saas-header-row,
    .saas-section-head,
    .saas-toolbar {
        display: block;
    }
    .saas-meta-row {
        justify-content: flex-start;
        margin-top: 0.8rem;
    }
    .saas-stepper {
        grid-template-columns: 1fr;
    }
    .saas-title {
        font-size: 1.55rem;
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def status_chip(label: str, tone: str = "neutral") -> str:
    """Return a small escaped status chip as an HTML string."""
    text, bg, border = TONE_STYLES.get(tone, TONE_STYLES["neutral"])
    return (
        f'<span class="saas-chip" '
        f'style="color:{text} !important; background:{bg}; border-color:{border};">'
        f'{escape(str(label))}</span>'
    )


def render_page_header(
    kicker: str,
    title: str,
    subtitle: str = "",
    meta_items: Optional[Iterable[Tuple[str, str]]] = None,
) -> None:
    """Render a consistent app page header."""
    meta_html = ""
    if meta_items:
        chips = [status_chip(label, tone) for label, tone in meta_items]
        meta_html = f'<div class="saas-meta-row">{"".join(chips)}</div>'
    st.markdown(
        f"""
<div class="saas-page-header">
    <div class="saas-header-row">
        <div>
            <div class="saas-kicker">{escape(kicker)}</div>
            <div class="saas-title">{escape(title)}</div>
            <div class="saas-subtitle">{escape(subtitle)}</div>
        </div>
        {meta_html}
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(
    title: str,
    subtitle: str = "",
    badge: Optional[Tuple[str, str]] = None,
) -> None:
    """Render a section heading with optional right-aligned badge."""
    badge_html = status_chip(badge[0], badge[1]) if badge else ""
    st.markdown(
        f"""
<div class="saas-section-head">
    <div>
        <div class="saas-section-title">{escape(title)}</div>
        <div class="saas-section-subtitle">{escape(subtitle)}</div>
    </div>
    <div>{badge_html}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(steps: Iterable[Tuple[str, str, str]]) -> None:
    """Render a three-step workflow indicator. Each step is title, note, status."""
    items = []
    for idx, (title, note, status) in enumerate(steps, start=1):
        css_status = status if status in {"done", "active", "waiting"} else "waiting"
        items.append(
            f"""
<div class="saas-step {css_status}">
    <div class="saas-step-index">Step {idx}</div>
    <div class="saas-step-title">{escape(title)}</div>
    <div class="saas-step-note">{escape(note)}</div>
</div>
            """
        )
    st.markdown(f'<div class="saas-stepper">{"".join(items)}</div>', unsafe_allow_html=True)


SIGNED_COLUMN_TERMS = (
    "growth",
    "yoy",
    "delta",
    "change",
    "pre vs post",
    "prevspost",
    "pre/post",
    "ly pre/post",
    "lastyear",
    "last year",
    "contribution",
    "lift",
    "variance",
    "diff",
)


def _column_is_signed(column) -> bool:
    """Return True when a column represents movement rather than a raw level."""
    if isinstance(column, tuple):
        column_text = " ".join(str(part) for part in column)
    else:
        column_text = str(column)
    normalized = column_text.lower().replace("_", " ")
    return any(term in normalized for term in SIGNED_COLUMN_TERMS)


def _parse_signed_number(value) -> Tuple[Optional[float], bool]:
    """Parse displayed currency / percent strings and detect explicit signs."""
    if value is None or isinstance(value, bool):
        return None, False

    if isinstance(value, (int, float)):
        return float(value), False

    text = str(value).strip()
    if not text:
        return None, False

    explicit_sign = bool(re.match(r"^\(?\s*[$%]?\s*[+-]", text))
    is_parenthetical_negative = text.startswith("(") and text.endswith(")")
    cleaned = text.replace(",", "").replace("$", "").replace("%", "").replace("x", "")
    cleaned = cleaned.replace("pts", "").replace("pt", "").strip()
    if is_parenthetical_negative:
        cleaned = f"-{cleaned.strip('()').strip()}"

    match = re.search(r"[+-]?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None, explicit_sign

    try:
        return float(match.group(0)), explicit_sign
    except ValueError:
        return None, explicit_sign


def style_signed_table(df: pd.DataFrame, signed_columns: Optional[Iterable[str]] = None, color_all_numbers: bool = False):
    """Return a Styler that colors signed movement cells red/green.

    Raw level columns stay neutral. Movement columns are inferred from common names
    like Growth%, YoY, Delta, Pre vs Post, and Contribution%.
    """
    if df is None or not hasattr(df, "style"):
        return df

    signed_column_names = {str(col).lower() for col in signed_columns or []}

    def build_styles(data: pd.DataFrame) -> pd.DataFrame:
        styles = pd.DataFrame("", index=data.index, columns=data.columns)
        for column in data.columns:
            column_key = str(column).lower()
            should_color_column = color_all_numbers or column_key in signed_column_names or _column_is_signed(column)
            for index, value in data[column].items():
                parsed_value, explicit_sign = _parse_signed_number(value)
                if parsed_value is None or parsed_value == 0:
                    continue
                if not should_color_column and not explicit_sign:
                    continue
                if parsed_value < 0:
                    styles.loc[index, column] = "color: #B42318; font-weight: 700;"
                elif parsed_value > 0:
                    styles.loc[index, column] = "color: #047857; font-weight: 700;"
        return styles

    return df.style.apply(build_styles, axis=None)
