"""Shared Streamlit presentation helpers for the TODC analytics app."""

from html import escape
import re
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

import pandas as pd
import streamlit as st


TONE_STYLES = {
    "neutral": ("#344054", "#F8FAFC", "#E2E8F0"),
    "info": ("#1D4ED8", "#EFF6FF", "#BFDBFE"),
    "success": ("#047857", "#ECFDF3", "#A7F3D0"),
    "warning": ("#B45309", "#FFFBEB", "#FDE68A"),
    "danger": ("#B42318", "#FEF3F2", "#FDA29B"),
    "dd": ("#C2410C", "#FFF7ED", "#FED7AA"),
    "ue": ("#15803D", "#F0FDF4", "#BBF7D0"),
    "ads": ("#0F766E", "#F0FDFA", "#99F6E4"),
}


def inject_global_styles() -> None:
    st.markdown(
        """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
    --t-bg: #F0F4F8;
    --t-surface: #FFFFFF;
    --t-surface-raised: #FFFFFF;
    --t-surface-muted: #F1F5F9;
    --t-surface-hover: #F8FAFC;
    --t-border: #E2E8F0;
    --t-border-strong: #CBD5E1;
    --t-border-focus: #93C5FD;
    --t-text: #0F172A;
    --t-text-secondary: #475569;
    --t-text-muted: #94A3B8;
    --t-primary: #2563EB;
    --t-primary-hover: #1D4ED8;
    --t-primary-dark: #1E40AF;
    --t-primary-light: #EFF6FF;
    --t-primary-lighter: #DBEAFE;
    --t-primary-ghost: rgba(37, 99, 235, 0.05);
    --t-success: #059669;
    --t-success-light: #ECFDF5;
    --t-success-border: #6EE7B7;
    --t-warning: #D97706;
    --t-warning-light: #FFFBEB;
    --t-warning-border: #FCD34D;
    --t-danger: #DC2626;
    --t-danger-light: #FEF2F2;
    --t-radius-sm: 8px;
    --t-radius: 12px;
    --t-radius-lg: 16px;
    --t-radius-xl: 20px;
    --t-shadow-xs: 0 1px 2px rgba(0,0,0,0.03);
    --t-shadow-sm: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    --t-shadow: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
    --t-shadow-md: 0 10px 15px -3px rgba(0,0,0,0.08), 0 4px 6px -4px rgba(0,0,0,0.05);
    --t-shadow-lg: 0 20px 25px -5px rgba(0,0,0,0.08), 0 8px 10px -6px rgba(0,0,0,0.04);
    --t-shadow-primary: 0 4px 14px rgba(37, 99, 235, 0.2);
    --t-ease: cubic-bezier(0.4, 0, 0.2, 1);
    --t-ease-bounce: cubic-bezier(0.34, 1.56, 0.64, 1);
}

html, body, .stApp, .stMarkdown, p, label,
span:not([data-testid="stIconMaterial"]),
div, input, select, textarea, button {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}
/* Preserve Streamlit's icon font for Material Symbols */
[data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded' !important;
    -webkit-font-smoothing: antialiased;
}
section[data-testid="stSidebar"] [data-testid="stIconMaterial"] {
    font-family: 'Material Symbols Rounded' !important;
}
.stApp {
    background: var(--t-bg) !important;
    color: var(--t-text) !important;
}
.block-container {
    max-width: none !important;
    padding: 1.75rem 2.5rem 4rem !important;
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] {
    background: rgba(240, 244, 248, 0.8) !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
    border-bottom: 1px solid var(--t-border) !important;
}
h1, h2, h3, h4 {
    color: var(--t-text) !important;
    letter-spacing: -0.025em !important;
    font-weight: 700 !important;
}
h1 { font-size: 1.65rem !important; }
h2 { font-size: 1.3rem !important; }
h3 { font-size: 1.05rem !important; }
p, label, .stCaption, .stMarkdown { color: var(--t-text-secondary); }
hr {
    border: none !important;
    border-top: 1px solid var(--t-border) !important;
    margin: 1.5rem 0 !important;
}

/* ═══════════════════════════════════════════
   SIDEBAR — Enterprise navigation panel
   ═══════════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #FAFBFD 100%) !important;
    border-right: 1px solid var(--t-border) !important;
    box-shadow: 2px 0 12px rgba(0,0,0,0.03) !important;
}
section[data-testid="stSidebar"] * { color: var(--t-text) !important; }
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] p { color: var(--t-text-muted) !important; }
section[data-testid="stSidebar"] hr { margin: 0.75rem 0 !important; }

/* Sidebar nav buttons — the key issue: make them look clickable and alive */
section[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    justify-content: flex-start;
    background: var(--t-surface) !important;
    color: var(--t-text) !important;
    border: 1px solid var(--t-border) !important;
    border-radius: var(--t-radius) !important;
    min-height: 2.85rem !important;
    box-shadow: var(--t-shadow-xs) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    transition: all 0.2s var(--t-ease) !important;
    padding: 0 1rem !important;
    position: relative !important;
    overflow: hidden !important;
}
section[data-testid="stSidebar"] .stButton > button::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: transparent;
    border-radius: 0 3px 3px 0;
    transition: all 0.2s var(--t-ease);
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: var(--t-primary-light) !important;
    border-color: var(--t-border-focus) !important;
    color: var(--t-primary) !important;
    box-shadow: var(--t-shadow-sm) !important;
    transform: translateX(2px) !important;
}
section[data-testid="stSidebar"] .stButton > button:hover::before {
    background: var(--t-primary);
}
section[data-testid="stSidebar"] .stButton > button[data-testid="baseButton-primary"] {
    background: var(--t-primary-light) !important;
    border-color: var(--t-border-focus) !important;
    color: var(--t-primary) !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] .stButton > button:disabled {
    background: var(--t-surface-muted) !important;
    border-color: transparent !important;
    color: var(--t-text-muted) !important;
    box-shadow: none !important;
    transform: none !important;
    opacity: 0.5;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] .stButton > button:disabled::before {
    background: transparent !important;
}

/* ═══════════════════════════════════════════
   BUTTONS — Polished with depth
   ═══════════════════════════════════════════ */
.stButton > button,
.stDownloadButton > button {
    min-height: 2.75rem;
    border-radius: var(--t-radius) !important;
    border: 1px solid var(--t-border) !important;
    box-shadow: var(--t-shadow-xs) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    transition: all 0.2s var(--t-ease) !important;
    letter-spacing: -0.01em !important;
}
.stButton > button[data-testid="baseButton-primary"],
.stDownloadButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: var(--t-shadow-primary) !important;
    font-weight: 700 !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stDownloadButton > button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%) !important;
    box-shadow: 0 6px 20px rgba(37, 99, 235, 0.35) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[data-testid="baseButton-primary"]:active,
.stDownloadButton > button[data-testid="baseButton-primary"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3) !important;
}
.stButton > button:not([data-testid="baseButton-primary"]),
.stDownloadButton > button:not([data-testid="baseButton-primary"]) {
    background: var(--t-surface) !important;
    color: var(--t-text-secondary) !important;
}
.stButton > button:not([data-testid="baseButton-primary"]):hover,
.stDownloadButton > button:not([data-testid="baseButton-primary"]):hover {
    border-color: var(--t-primary) !important;
    color: var(--t-primary) !important;
    background: var(--t-primary-light) !important;
    box-shadow: var(--t-shadow-sm) !important;
    transform: translateY(-1px) !important;
}
.stButton > button:disabled,
.stDownloadButton > button:disabled {
    background: var(--t-surface-muted) !important;
    color: var(--t-text-muted) !important;
    border-color: transparent !important;
    box-shadow: none !important;
    transform: none !important;
    opacity: 0.55;
}

/* ═══════════════════════════════════════════
   FORM INPUTS — Refined
   ═══════════════════════════════════════════ */
.stTextInput input,
.stSelectbox > div > div,
.stMultiSelect > div > div,
.stDateInput input {
    border-radius: var(--t-radius) !important;
    border: 1.5px solid var(--t-border) !important;
    background: var(--t-surface) !important;
    transition: all 0.2s var(--t-ease) !important;
    font-size: 0.875rem !important;
    box-shadow: var(--t-shadow-xs) !important;
}
.stTextInput input:focus,
.stSelectbox > div > div:focus-within,
.stMultiSelect > div > div:focus-within {
    border-color: var(--t-primary) !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12), var(--t-shadow-xs) !important;
}

/* ═══════════════════════════════════════════
   DATA TABLES — Clean with depth
   ═══════════════════════════════════════════ */
.stDataFrame, [data-testid="stDataFrame"] {
    border: 1px solid var(--t-border) !important;
    border-radius: var(--t-radius) !important;
    overflow: hidden !important;
    box-shadow: var(--t-shadow-sm) !important;
}

/* ═══════════════════════════════════════════
   METRICS — Cards with hover
   ═══════════════════════════════════════════ */
[data-testid="stMetric"] {
    background: var(--t-surface) !important;
    border: 1px solid var(--t-border) !important;
    border-radius: var(--t-radius) !important;
    box-shadow: var(--t-shadow-xs) !important;
    padding: 1.1rem 1.25rem !important;
    transition: all 0.25s var(--t-ease) !important;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--t-primary) 0%, #60A5FA 100%);
    opacity: 0;
    transition: opacity 0.25s var(--t-ease);
}
[data-testid="stMetric"]:hover {
    box-shadow: var(--t-shadow) !important;
    border-color: var(--t-border-strong) !important;
    transform: translateY(-2px);
}
[data-testid="stMetric"]:hover::before { opacity: 1; }
[data-testid="stMetric"] label {
    color: var(--t-text-muted) !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: var(--t-text) !important;
    font-size: 1.5rem !important;
    font-weight: 800 !important;
    letter-spacing: -0.03em !important;
}

/* ═══════════════════════════════════════════
   TABS — Modern segmented control
   ═══════════════════════════════════════════ */
[data-testid="stTabs"] { background: transparent !important; }
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 2px;
    border-bottom: 2px solid var(--t-border);
    padding-bottom: 0;
    background: transparent !important;
}
[data-testid="stTabs"] button {
    font-weight: 600 !important;
    border-radius: var(--t-radius) var(--t-radius) 0 0 !important;
    padding: 0.7rem 1.25rem !important;
    color: var(--t-text-muted) !important;
    border: none !important;
    border-bottom: 2px solid transparent !important;
    margin-bottom: -2px !important;
    transition: all 0.2s var(--t-ease) !important;
    font-size: 0.875rem !important;
}
[data-testid="stTabs"] button:hover {
    color: var(--t-text-secondary) !important;
    background: var(--t-surface-muted) !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--t-primary) !important;
    border-bottom: 2.5px solid var(--t-primary) !important;
    background: var(--t-primary-ghost) !important;
    font-weight: 700 !important;
}

/* ═══════════════════════════════════════════
   EXPANDER
   ═══════════════════════════════════════════ */
[data-testid="stExpander"] {
    border: 1px solid var(--t-border) !important;
    border-radius: var(--t-radius) !important;
    box-shadow: var(--t-shadow-xs) !important;
    background: var(--t-surface) !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    color: var(--t-text) !important;
}

/* ═══════════════════════════════════════════
   PAGE HEADER
   ═══════════════════════════════════════════ */
.t-page-header {
    padding: 0.25rem 0 1.5rem;
    margin-bottom: 1.75rem;
    border-bottom: 2px solid var(--t-border);
    position: relative;
}
.t-page-header::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 120px;
    height: 2px;
    background: linear-gradient(90deg, var(--t-primary), transparent);
}
.t-header-row {
    display: flex;
    justify-content: space-between;
    gap: 2rem;
    align-items: flex-end;
}
.t-kicker {
    display: inline-block;
    color: var(--t-primary);
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 0.5rem;
    padding: 0.2rem 0.6rem;
    background: var(--t-primary-light);
    border-radius: 4px;
    border: 1px solid var(--t-primary-lighter);
}
.t-title {
    color: var(--t-text);
    font-size: 2.1rem;
    line-height: 1.15;
    font-weight: 800;
    letter-spacing: -0.03em;
}
.t-subtitle {
    color: var(--t-text-secondary);
    font-size: 0.92rem;
    margin-top: 0.5rem;
    max-width: 680px;
    line-height: 1.55;
}
.t-meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: flex-end;
}

/* ═══════════════════════════════════════════
   CHIPS / BADGES
   ═══════════════════════════════════════════ */
.t-chip {
    display: inline-flex;
    align-items: center;
    min-height: 1.85rem;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    border: 1px solid var(--t-border);
    background: var(--t-surface);
    color: var(--t-text-secondary);
    font-size: 0.72rem;
    font-weight: 600;
    white-space: nowrap;
    letter-spacing: 0.01em;
    box-shadow: var(--t-shadow-xs);
}
.todc-badge, .todc-badge-dd, .todc-badge-ue { display: none; }

/* ═══════════════════════════════════════════
   SECTION HEADER
   ═══════════════════════════════════════════ */
.t-section-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
    border-bottom: 2px solid var(--t-border);
    padding: 0.25rem 0 0.75rem;
    margin: 2rem 0 1.15rem;
    position: relative;
}
.t-section-head::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 60px;
    height: 2px;
    background: var(--t-primary);
}
.t-section-title {
    color: var(--t-text);
    font-size: 1.05rem;
    font-weight: 700;
    line-height: 1.3;
    letter-spacing: -0.015em;
}
.t-section-subtitle {
    color: var(--t-text-muted);
    font-size: 0.82rem;
    margin-top: 0.15rem;
    line-height: 1.45;
}

/* ═══════════════════════════════════════════
   STEPPER — Much more visual
   ═══════════════════════════════════════════ */
.t-stepper {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    margin: 1rem 0 1.75rem;
    position: relative;
}
.t-stepper::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 10%;
    right: 10%;
    height: 2px;
    background: var(--t-border);
    z-index: 0;
}
.t-step {
    background: var(--t-surface);
    border: 1.5px solid var(--t-border);
    border-radius: var(--t-radius);
    padding: 1rem 1.15rem;
    box-shadow: var(--t-shadow-sm);
    transition: all 0.3s var(--t-ease);
    position: relative;
    z-index: 1;
}
.t-step:hover { box-shadow: var(--t-shadow); transform: translateY(-2px); }
.t-step.done {
    border-color: var(--t-success-border);
    background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 50%, var(--t-surface) 100%);
    box-shadow: 0 2px 8px rgba(5, 150, 105, 0.08);
}
.t-step.done .t-step-index { color: var(--t-success); }
.t-step.active {
    border-color: var(--t-border-focus);
    background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 30%, var(--t-surface) 100%);
    box-shadow: 0 2px 12px rgba(37, 99, 235, 0.1);
}
.t-step.active .t-step-index { color: var(--t-primary); }
.t-step.waiting {
    border-color: var(--t-border);
    background: var(--t-surface-muted);
    opacity: 0.6;
}
.t-step-index {
    color: var(--t-text-muted);
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
.t-step-title {
    color: var(--t-text);
    font-weight: 700;
    font-size: 0.95rem;
    margin-top: 0.25rem;
    letter-spacing: -0.01em;
}
.t-step-note {
    color: var(--t-text-muted);
    font-size: 0.76rem;
    margin-top: 0.25rem;
    line-height: 1.4;
}

/* ═══════════════════════════════════════════
   CARDS — Unified styling
   ═══════════════════════════════════════════ */
.t-card,
.saas-stat-card,
.saas-rule-card,
.saas-file-row,
.saas-status-card {
    background: var(--t-surface);
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    box-shadow: var(--t-shadow-xs);
    transition: all 0.2s var(--t-ease);
}
.t-card:hover, .saas-stat-card:hover, .saas-status-card:hover {
    box-shadow: var(--t-shadow-sm);
    border-color: var(--t-border-strong);
}
.saas-stat-card { padding: 1rem 1.15rem; min-height: 5.5rem; }
.saas-stat-label {
    color: var(--t-text-muted);
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.saas-stat-value {
    color: var(--t-text);
    font-size: 1.35rem;
    line-height: 1.2;
    font-weight: 800;
    margin-top: 0.35rem;
    letter-spacing: -0.02em;
}
.saas-stat-note {
    color: var(--t-text-muted);
    font-size: 0.73rem;
    margin-top: 0.35rem;
}
.saas-rule-card {
    padding: 0.9rem 1.05rem;
    min-height: 5.8rem;
    border-left: 3px solid var(--t-primary);
}
.saas-rule-pattern {
    color: var(--t-text);
    font-weight: 700;
    font-size: 0.84rem;
    font-family: 'SF Mono', 'Fira Code', monospace !important;
}
.saas-rule-target {
    color: var(--t-text-secondary);
    font-size: 0.78rem;
    margin-top: 0.3rem;
}
.saas-rule-count {
    color: var(--t-text-muted);
    font-size: 0.72rem;
    margin-top: 0.6rem;
    font-weight: 500;
}
.saas-file-row {
    display: flex;
    align-items: center;
    gap: 0.9rem;
    padding: 0.85rem 1.1rem;
    margin: 0.4rem 0;
}
.saas-file-token {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.85rem;
    font-weight: 700;
    flex: 0 0 auto;
}
.saas-file-main { min-width: 0; flex: 1; }
.saas-file-name {
    color: var(--t-text);
    font-weight: 600;
    font-size: 0.875rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.saas-file-meta {
    color: var(--t-text-muted);
    font-size: 0.75rem;
    margin-top: 0.15rem;
}
.saas-status-card {
    padding: 0.95rem 1.1rem;
    min-height: 5rem;
    position: relative;
    overflow: hidden;
}
.saas-status-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: var(--t-border);
}
.saas-status-label {
    color: var(--t-text-muted);
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.saas-status-value {
    font-size: 1.05rem;
    font-weight: 700;
    margin-top: 0.25rem;
}
.saas-compact-note {
    color: var(--t-text-muted);
    font-size: 0.72rem;
    margin-top: 0.3rem;
}

/* ═══════════════════════════════════════════
   ALERTS
   ═══════════════════════════════════════════ */
.saas-alert {
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    background: var(--t-surface);
    padding: 0.95rem 1.1rem;
    color: var(--t-text-secondary);
    font-size: 0.86rem;
    line-height: 1.55;
}
.saas-alert.info { border-color: #BFDBFE; background: #EFF6FF; color: #1E3A8A; }
.saas-alert.success { border-color: #A7F3D0; background: #ECFDF5; color: #065F46; }
.saas-alert.warning { border-color: #FDE68A; background: #FFFBEB; color: #92400E; }

/* ═══════════════════════════════════════════
   TOOLBAR & ACTION ROW
   ═══════════════════════════════════════════ */
.t-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    padding: 0.85rem 0;
    border-bottom: 1px solid var(--t-border);
    margin-bottom: 1rem;
}
.t-toolbar-title {
    color: var(--t-text);
    font-size: 0.95rem;
    font-weight: 700;
}
.t-toolbar-subtitle {
    color: var(--t-text-muted);
    font-size: 0.78rem;
    margin-top: 0.15rem;
}
.t-action-row {
    background: var(--t-surface);
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    padding: 0.9rem 1.1rem;
    margin: 1.25rem 0 1.5rem;
    box-shadow: var(--t-shadow-xs);
}
.t-action-row .stButton > button,
.t-action-row .stDownloadButton > button { width: 100%; }
.saas-focus-row .stButton > button { margin-top: 1.62rem; }

/* ═══════════════════════════════════════════
   SIDEBAR — Brand, Nav, Controls
   ═══════════════════════════════════════════ */
.sidebar-shell { padding: 0.35rem 0 0.25rem; }
.sidebar-brand {
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    background: linear-gradient(135deg, #FFFFFF 0%, #F0F4FF 100%);
    padding: 1.1rem 1rem;
    position: relative;
    overflow: hidden;
}
.sidebar-brand::before {
    content: '';
    position: absolute;
    top: 0; left: 0; bottom: 0;
    width: 4px;
    background: linear-gradient(180deg, var(--t-primary) 0%, #60A5FA 100%);
    border-radius: 4px 0 0 4px;
}
.sidebar-brand-kicker {
    color: var(--t-primary) !important;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.sidebar-brand-title {
    color: var(--t-text) !important;
    font-size: 1.2rem;
    line-height: 1.2;
    font-weight: 800;
    margin-top: 0.2rem;
    letter-spacing: -0.02em;
}
.sidebar-brand-subtitle {
    color: var(--t-text-muted) !important;
    font-size: 0.75rem;
    margin-top: 0.3rem;
    line-height: 1.4;
}
.sidebar-panel {
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    background: var(--t-surface);
    padding: 0.9rem 0.95rem;
    margin-top: 0.75rem;
    box-shadow: var(--t-shadow-xs);
}
.sidebar-panel-title {
    color: var(--t-text) !important;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 0.65rem;
    color: var(--t-text-muted) !important;
}
.sidebar-status-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--t-surface-muted);
}
.sidebar-status-row:first-of-type { border-top: 0; }
.sidebar-status-label {
    color: var(--t-text-secondary) !important;
    font-size: 0.78rem;
    font-weight: 500;
}
.sidebar-status-value {
    border-radius: 999px;
    padding: 0.18rem 0.55rem;
    font-size: 0.66rem;
    font-weight: 700;
    white-space: nowrap;
    letter-spacing: 0.02em;
}
.sidebar-status-value.success {
    color: #059669 !important;
    background: #ECFDF5;
    border: 1px solid #6EE7B7;
}
.sidebar-status-value.warning {
    color: #D97706 !important;
    background: #FFFBEB;
    border: 1px solid #FCD34D;
}
.sidebar-status-value.neutral {
    color: var(--t-text-muted) !important;
    background: var(--t-surface-muted);
    border: 1px solid var(--t-border);
}
.sidebar-nav-current {
    display: flex;
    align-items: center;
    border: 1.5px solid var(--t-border-focus);
    border-left: 4px solid var(--t-primary);
    border-radius: var(--t-radius);
    background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
    color: var(--t-primary) !important;
    padding: 0.75rem 0.9rem;
    font-size: 0.875rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
}
.sidebar-nav-note {
    color: var(--t-text-muted) !important;
    font-size: 0.73rem;
    line-height: 1.45;
    margin-top: 0.5rem;
    padding: 0.55rem 0.7rem;
    background: var(--t-surface-muted);
    border-radius: var(--t-radius-sm);
    border: 1px solid var(--t-border);
}
.sidebar-mini-stat {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
    margin-top: 0.7rem;
}
.sidebar-mini-card {
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    background: var(--t-surface-muted);
    padding: 0.65rem 0.75rem;
    transition: all 0.2s var(--t-ease);
}
.sidebar-mini-card:hover {
    background: var(--t-surface);
    box-shadow: var(--t-shadow-xs);
}
.sidebar-mini-label {
    color: var(--t-text-muted) !important;
    font-size: 0.63rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.sidebar-mini-value {
    color: var(--t-text) !important;
    font-size: 1rem;
    font-weight: 800;
    margin-top: 0.12rem;
    letter-spacing: -0.02em;
}

/* ═══════════════════════════════════════════
   LINK BUTTON
   ═══════════════════════════════════════════ */
.saas-link-btn {
    display: inline-flex;
    align-items: center;
    min-height: 2.65rem;
    padding: 0 1.1rem;
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    background: var(--t-surface);
    color: var(--t-text-secondary);
    text-decoration: none;
    font-weight: 600;
    font-size: 0.875rem;
    box-shadow: var(--t-shadow-xs);
    transition: all 0.2s var(--t-ease);
}
.saas-link-btn:hover {
    border-color: var(--t-primary);
    color: var(--t-primary);
    background: var(--t-primary-light);
    box-shadow: var(--t-shadow-sm);
    transform: translateY(-1px);
    text-decoration: none;
}

/* ═══════════════════════════════════════════
   FILTER CARD
   ═══════════════════════════════════════════ */
.saas-filter-card {
    background: var(--t-surface);
    border: 1px solid var(--t-border);
    border-radius: var(--t-radius);
    padding: 1.1rem 1.2rem 0.35rem;
    margin-bottom: 1.1rem;
    box-shadow: var(--t-shadow-xs);
}
.saas-filter-card .saas-filter-head { margin-bottom: 0.65rem; }
.saas-filter-title {
    color: var(--t-text);
    font-size: 0.92rem;
    font-weight: 700;
}
.saas-filter-subtitle {
    color: var(--t-text-muted);
    font-size: 0.78rem;
    margin-top: 0.15rem;
}

/* ═══════════════════════════════════════════
   RESPONSIVE
   ═══════════════════════════════════════════ */
@media (max-width: 900px) {
    .t-header-row, .t-section-head, .t-toolbar { display: block; }
    .t-meta-row { justify-content: flex-start; margin-top: 0.8rem; }
    .t-stepper { grid-template-columns: 1fr; }
    .t-title { font-size: 1.55rem; }
    .block-container { padding: 1rem 1rem 2rem !important; }
}

/* ═══════════════════════════════════════════
   BACKWARD COMPAT (old class aliases)
   ═══════════════════════════════════════════ */
.saas-page-header { padding: 0.25rem 0 1.5rem; margin-bottom: 1.75rem; border-bottom: 2px solid var(--t-border); position: relative; }
.saas-page-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.65rem; margin: -0.2rem 0 1rem; padding: 0.6rem 0.85rem; background: var(--t-surface); border: 1px solid var(--t-border); border-radius: var(--t-radius); box-shadow: var(--t-shadow-xs); }
.saas-header-row { display: flex; justify-content: space-between; gap: 2rem; align-items: flex-end; }
.saas-kicker { display: inline-block; color: var(--t-primary); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.5rem; padding: 0.2rem 0.6rem; background: var(--t-primary-light); border-radius: 4px; }
.saas-title { color: var(--t-text); font-size: 2.1rem; line-height: 1.15; font-weight: 800; letter-spacing: -0.03em; }
.saas-subtitle { color: var(--t-text-secondary); font-size: 0.92rem; margin-top: 0.5rem; max-width: 680px; line-height: 1.55; }
.saas-meta-row { display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: flex-end; }
.saas-chip { display: inline-flex; align-items: center; min-height: 1.85rem; padding: 0.25rem 0.75rem; border-radius: 999px; border: 1px solid var(--t-border); background: var(--t-surface); color: var(--t-text-secondary); font-size: 0.72rem; font-weight: 600; white-space: nowrap; box-shadow: var(--t-shadow-xs); }
.saas-section-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem; border-bottom: 2px solid var(--t-border); padding: 0.25rem 0 0.75rem; margin: 2rem 0 1.15rem; }
.saas-section-title { color: var(--t-text); font-size: 1.05rem; font-weight: 700; line-height: 1.3; letter-spacing: -0.015em; }
.saas-section-subtitle { color: var(--t-text-muted); font-size: 0.82rem; margin-top: 0.15rem; line-height: 1.45; }
.saas-stepper { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem; margin: 1rem 0 1.75rem; }
.saas-step { background: var(--t-surface); border: 1.5px solid var(--t-border); border-radius: var(--t-radius); padding: 1rem 1.15rem; box-shadow: var(--t-shadow-sm); }
.saas-step.done { border-color: var(--t-success-border); background: linear-gradient(135deg, #ECFDF5, var(--t-surface)); }
.saas-step.active { border-color: var(--t-border-focus); background: linear-gradient(135deg, #EFF6FF, #DBEAFE 30%, var(--t-surface)); }
.saas-step.waiting { border-color: var(--t-border); background: var(--t-surface-muted); opacity: 0.6; }
.saas-step-index { color: var(--t-text-muted); font-size: 0.62rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; }
.saas-step-title { color: var(--t-text); font-weight: 700; font-size: 0.95rem; margin-top: 0.25rem; }
.saas-step-note { color: var(--t-text-muted); font-size: 0.76rem; margin-top: 0.25rem; line-height: 1.4; }
.saas-toolbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 0.85rem 0; border-bottom: 1px solid var(--t-border); margin-bottom: 1rem; }
.saas-toolbar-title { color: var(--t-text); font-size: 0.95rem; font-weight: 700; }
.saas-toolbar-subtitle { color: var(--t-text-muted); font-size: 0.78rem; margin-top: 0.15rem; }
.saas-action-row { background: var(--t-surface); border: 1px solid var(--t-border); border-radius: var(--t-radius); padding: 0.9rem 1.1rem; margin: 1.25rem 0 1.5rem; box-shadow: var(--t-shadow-xs); }
.saas-action-row .stButton > button, .saas-action-row .stDownloadButton > button { width: 100%; }
.todc-section-header { border-bottom: 1px solid var(--t-border) !important; color: var(--t-text) !important; }
.dashboard-heading, .page-heading { border-bottom: 1px solid var(--t-border) !important; }
</style>
        """,
        unsafe_allow_html=True,
    )


def status_chip(label: str, tone: str = "neutral") -> str:
    text, bg, border = TONE_STYLES.get(tone, TONE_STYLES["neutral"])
    return (
        f'<span class="t-chip" '
        f'style="color:{text} !important; background:{bg}; border-color:{border};">'
        f'{escape(str(label))}</span>'
    )


def render_page_header(
    kicker: str,
    title: str,
    subtitle: str = "",
    meta_items: Optional[Iterable[Tuple[str, str]]] = None,
) -> None:
    meta_html = ""
    if meta_items:
        chips = [status_chip(label, tone) for label, tone in meta_items]
        meta_html = f'<div class="t-meta-row">{"".join(chips)}</div>'
    st.markdown(
        f"""
<div class="t-page-header">
    <div class="t-header-row">
        <div>
            <div class="t-kicker">{escape(kicker)}</div>
            <div class="t-title">{escape(title)}</div>
            <div class="t-subtitle">{escape(subtitle)}</div>
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
    badge_html = status_chip(badge[0], badge[1]) if badge else ""
    st.markdown(
        f"""
<div class="t-section-head">
    <div>
        <div class="t-section-title">{escape(title)}</div>
        <div class="t-section-subtitle">{escape(subtitle)}</div>
    </div>
    <div>{badge_html}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_stepper(steps: Iterable[Tuple[str, str, str]]) -> None:
    items = []
    for idx, (title, note, status) in enumerate(steps, start=1):
        css_status = status if status in {"done", "active", "waiting"} else "waiting"
        icon = {"done": "&#10003;", "active": "&#9679;", "waiting": "&#9675;"}.get(css_status, "&#9675;")
        items.append(
            f"""
<div class="t-step {css_status}">
    <div class="t-step-index">{icon} Step {idx}</div>
    <div class="t-step-title">{escape(title)}</div>
    <div class="t-step-note">{escape(note)}</div>
</div>
            """
        )
    st.markdown(f'<div class="t-stepper">{"".join(items)}</div>', unsafe_allow_html=True)


SIGNED_COLUMN_TERMS = (
    "growth", "yoy", "delta", "change", "pre vs post", "prevspost",
    "pre/post", "ly pre/post", "lastyear", "last year",
    "contribution", "lift", "variance", "diff",
)


def _column_is_signed(column) -> bool:
    if isinstance(column, tuple):
        column_text = " ".join(str(part) for part in column)
    else:
        column_text = str(column)
    normalized = column_text.lower().replace("_", " ")
    return any(term in normalized for term in SIGNED_COLUMN_TERMS)


def _parse_signed_number(value) -> Tuple[Optional[float], bool]:
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
    if df is None or not hasattr(df, "style"):
        return df
    styled = df
    if isinstance(styled, pd.DataFrame):
        if styled.columns.duplicated().any():
            styled = styled.loc[:, ~styled.columns.duplicated()].copy()
        if not styled.index.is_unique:
            styled = styled.reset_index()
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
                    styles.loc[index, column] = "color: #DC2626; font-weight: 600;"
                elif parsed_value > 0:
                    styles.loc[index, column] = "color: #059669; font-weight: 600;"
        return styles

    return styled.style.apply(build_styles, axis=None)


def render_filter_card(title: str, subtitle: str = "") -> None:
    subtitle_html = (
        f'<div class="saas-filter-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    )
    st.markdown(
        f"""
<div class="saas-filter-card">
  <div class="saas-filter-head">
    <div class="saas-filter-title">{escape(title)}</div>
    {subtitle_html}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_action_toolbar(
    title: str,
    subtitle: str = "",
    button_specs: Sequence[Mapping[str, Any]] = (),
) -> dict[str, bool]:
    subtitle_html = (
        f'<div class="t-toolbar-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    )
    st.markdown(
        f"""
<div class="t-action-row">
  <div class="t-toolbar">
    <div>
      <div class="t-toolbar-title">{escape(title)}</div>
      {subtitle_html}
    </div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    if not button_specs:
        return {}
    specs = list(button_specs)
    cols = st.columns(len(specs))
    clicked: dict[str, bool] = {}
    for col, spec in zip(cols, specs):
        with col:
            key = str(spec["key"])
            clicked[key] = st.button(
                str(spec["label"]),
                key=key,
                type="primary" if spec.get("primary") else "secondary",
                disabled=bool(spec.get("disabled", False)),
                help=str(spec.get("help", "")),
                use_container_width=True,
            )
    return clicked


def render_button_group(
    specs: Sequence[Mapping[str, Any]],
    *,
    equal_width: bool = True,
) -> dict[str, bool]:
    if not specs:
        return {}
    items = list(specs)
    cols = st.columns(len(items))
    clicked: dict[str, bool] = {}
    for col, spec in zip(cols, items):
        with col:
            key = str(spec["key"])
            clicked[key] = st.button(
                str(spec["label"]),
                key=key,
                type="primary" if spec.get("primary") else "secondary",
                disabled=bool(spec.get("disabled", False)),
                use_container_width=equal_width,
            )
    return clicked


def render_page_actions_bar(
    back_href: str = "/",
    back_label: str = "Back to dashboard",
    *,
    download_label: str | None = None,
    download_data: bytes | None = None,
    download_file_name: str | None = None,
    download_key: str = "page_download",
) -> None:
    left, right = st.columns([1, 1])
    with left:
        st.markdown(
            f'<a class="saas-link-btn" href="{escape(back_href)}" target="_self">{escape(back_label)}</a>',
            unsafe_allow_html=True,
        )
    with right:
        if download_label and download_data is not None:
            st.download_button(
                download_label,
                data=download_data,
                file_name=download_file_name or "export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=download_key,
                use_container_width=True,
            )


def render_focus_action_row(
    selectbox_label: str,
    options: Sequence[str],
    selectbox_key: str,
    button_label: str,
    button_key: str,
) -> tuple[str, bool]:
    st.markdown('<div class="saas-focus-row">', unsafe_allow_html=True)
    left, right = st.columns([4, 1])
    with left:
        selected = st.selectbox(selectbox_label, list(options), key=selectbox_key)
    with right:
        clicked = st.button(button_label, key=button_key, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    return selected, clicked
