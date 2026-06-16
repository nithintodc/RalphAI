# RalphAI Agent Architecture — Audit Report

**Date:** 2026-06-10 · **Scope:** all `reporting_browser_use*` forks, Ralph AI (Offers/Ads/Strategist), shared browser layer, API orchestration.
All paths relative to repo root. Line numbers reflect the current working tree (uncommitted changes included).

---

## 1. System map

```
                         ANALYSIS INPUT
   ┌────────────────────────────────────────┬─────────────────────────────────────────────┐
   │ AUTO: Strategist browser run           │ MANUAL: DD "register" upload                │
   │ POST /api/runs/strategist (mode=auto)  │ POST /api/runs/strategist (mode=manual)     │
   │   api/main.py:1168                     │   api/main.py:1195-1262                     │
   │   → run_strategist_auto_worker         │   → run_strategist_manual_worker            │
   │     api/browser_agent_runs.py:241      │     api/browser_agent_runs.py:289           │
   │   → agents/strategist/agent.py:756     │   → agents/strategist/agent.py:690          │
   │     subprocess per operator inside     │     register_reco.build_recommendations_    │
   │     REPORTING_ROOT (agent.py:617-625,  │     from_register (register_reco.py:420)    │
   │     timeout=1200s): browser-use report │     + plan_builder.build_marketing_plan     │
   │     download → marketing_agent /       │     (plan_builder.py:75)                    │
   │     analysis_agent / combined_report   │                                             │
   └──────────────────┬─────────────────────┴───────────────────┬─────────────────────────┘
                      ▼                                         ▼
        _read_day_slots_per_store (agent.py:425)      register_to_per_store (register_reco.py:380)
                      └───────────────┬─────────────────────────┘
                                      ▼
              PLANNING (deterministic, NO LLM)
              classify_slot_action / uplift_min_subtotal / bottom_order_slot_keys
              (agents/strategist/register_reco.py:159-239)
                                      ▼
              GENERATION  write_campaigns_workbook_from_per_store
              (agents/strategist/campaign_workbook.py:33-147)
              → data/Strategist/<biz>/<ts>/campaigns.xlsx (+ slot_info.csv, result.json)
                                      │
        ┌─────────────────────────────┼──────────────────────────────┐
        │ AUTO: find_campaign_workbook│  MANUAL: sheet upload        │
        │ (strategist_campaign_sheets │  POST /api/runs/{offers|ads} │
        │  .py:78-96, latest run dir) │  Excel→CSV (api/main.py:     │
        │                             │  244-320)                    │
        └─────────────┬───────────────┴───────────┬──────────────────┘
                      ▼                           ▼
        RALPH OFFERS agents/offers/agent.py:34    RALPH ADS agents/ads/agent.py:34
        load_offers_combos[_from_path]            load_ads_rows[_from_path]
        (strategist_campaign_sheets.py:170-348; _status_skip skips successful/success)
                      └───────────────┬───────────┘
                                      ▼
        FORK IMPORT  MARKETINGRECO_REPORTING_ROOT (shared/config/settings.py:91-98,
        default agents/reporting_browser_use) → import_reporting_agents_module
        (shared/reporting_imports.py:21-43 — sys.modules["agents"] swap)
                                      ▼
        BROWSER EXECUTION  _run_campaign_items (doordash_agent.py:2580-2853)
        compact login → per item: nav-reset agent → campaign agent (Gemini
        gemini-3-flash-preview, _get_llm:1603) + custom CDP tools
        set_schedule_grid / click_leftmost_max_discount (:62-906)
        browser restart every MAX_CAMPAIGNS_PER_SESSION=5 (:24)
                                      ▼
        STATUS WRITEBACK  write_strategist_campaign_statuses
        (strategist_campaign_sheets.py:518-549) → campaigns.xlsx + slot_info.csv
                                      ▼
        REPORTING  result.json + run.log (api/browser_agent_runs.py:39-86),
        Slack (shared/ralph_slack_messages.py + fork slack_log_notifier.py),
        dashboard polling (OffersPage/AdsPage/StrategistPage.tsx)
```

---

## 2. The `reporting_browser_use*` family

### 2.1 Fork inventory (measured, current tree)

| Fork | `doordash_agent.py` | Offers STEP 1 UI | Target-audience step | Ralph entry points (`_run_campaign_items`, `run_offers_campaigns_from_combos`, `run_ads_campaigns_from_rows`) |
|---|---|---|---|---|
| `agents/reporting_browser_use` (default) | 2,936 lines | **OLD** — "Discount for all customers" card (`:1553-1557`), store search by ID first (`:1562`) | absent | **YES** (only fork that has them) |
| `agents/reporting_browser_use_melt` | 1,772 lines (54% similar to main) | **NEW** — carousel: "More ways to help you grow" → "Offer a discount promotion" | present | no |
| `agents/reporting_browser_use_savvy` | 1,772 lines (54% similar) | **NEW** — carousel (`:1046-1053`), name-first store search (`:1042`), STEP 3B Target audience (`:1073-1076`) | present | no |
| `agents/reporting_browser_use_browser` | 1,735 lines (54% similar) | OLD card UI | absent | no |

**Architectural deadlock:** Ralph can only import the main fork (it alone exports the campaign-loop entry points), but the main fork carries the stale portal-UI prompt. The current-UI prompts live in melt/savvy, which Ralph cannot use (flipping `MARKETINGRECO_REPORTING_ROOT` → AttributeError). `.env:26` has the variable commented out, so Ralph runs the main fork today — confirmed in live run logs (`data/runs/offers/d5c12897…/run.log` shows `STEP 1: Open campaign builder (Select 'Discount for all custom…`).

### 2.2 Execution flow (main fork)

- `run_browser_use.py` — minimal single-task financial-report downloader (login + Reports + download, `:64-92`). Not the production path.
- `main.py` — production entry: Phase 1 downloads financial + marketing reports, runs `marketing_agent` / `analysis_agent` in parallel (`main.py:168`), builds `combined_analysis_*.xlsx` via `combined_report_agent` (`:200-226`); campaign combos derived from the workbook's "Campaign Mappings" via `campaign_params.py` (resume across runs via `copy_campaign_mappings_from_previous`, `doordash_agent.py:2119-2135`). Phase 2 (`doordash_agent.py:2188-2429`) creates campaigns in the same browser session as Phase 1 (`keep_alive=True`, `:1966`).
- Analysis modules: `analysis_agent.py` (24K), `combined_report_agent.py` (17K), `marketing_agent.py` (12K), `campaign_params.py` (19K). **This Phase-1 analysis pipeline is exactly what Ralph AI externalizes** — Ralph receives the equivalent of "Campaign Mappings" as a Strategist workbook or manual upload.

### 2.3 Prompts (main fork; melt/savvy differ in STEP 1/3B)

| Prompt | Source | Size | Key instructions |
|---|---|---|---|
| Offers campaign | `get_task_description_campaign_for_subtotal_combo` (`doordash_agent.py:1468-1600`) | ~2.5–3 KB | 6 steps + 4B; "Wait 2s" after subtotal (`:1570`); "wait 3s" modal retry rule (`:1549`); `set_schedule_grid(wanted_tags=…)` call (`:1526-1532`) with manual-click fallback; duplicate → done immediately (`:1597`); STEP 6 verification checks **subtotal and name only — not schedule** (`:1592-1596`) |
| Ads campaign | `get_task_description_ads_campaign` (`:2432-2564`) | ~2 KB | 8 steps; "Existing customers" audience hardcoded (`:2538`); budget step conditional — budget 0 lets the LLM "set a reasonable weekly budget" (`:2509-2513`) |
| Compact login | `build_compact_login_task` (`shared/doordash_portal_tasks.py:83-99`) | ~0.6 KB | credentials interpolated in plaintext |
| Nav reset / fallback / health check | module constants (`doordash_agent.py:27-47`) | ~0.3 KB each | shared verbatim by Phase 2 and Ralph |

### 2.4 Custom CDP tools

- **`set_schedule_grid`** (`doordash_agent.py:62-906`): anchors on a button with `textContent === 'Weekdays'` (`:114-122`); clears the grid via Weekdays/Weekends toggles, then clicks wanted cells by coordinates; hardcoded sleeps 2.0+0.5+2.0+0.3+0.2 s (+0.05 s/cell, +0.5 s on correction) ≈ 5.3–7.1 s/campaign; **verifies all 42 cells before Save and refuses to save a wrong grid** (`:737-802`); but does **not** verify the modal actually persisted after the Save click (`:804-809`), accepts an empty tag set (clears everything and saves), and on error hands off to a manual LLM fallback whose instructions assume a clean grid (`:1503-1532`).
- **`click_leftmost_max_discount`**: selects the leftmost/maximum-discount option deterministically.

### 2.5 State, retries, validation, failure handling

- Status writeback: Phase 2 → `campaigns_executed.csv` + combined-workbook "Campaign Mappings" (`:2382-2394`); Ralph → `campaigns.xlsx`/`slot_info.csv` (`:2779-2797`) — **no executed-CSV audit log in the Ralph path**.
- Session restart every `MAX_CAMPAIGNS_PER_SESSION=5` (`:24`) with 2 relogin attempts; relogin failure aborts the remaining loop (`:2628-2663`).
- Timeouts: login 180 s, nav reset 90 s, campaign 720 s, health 30 s (`:17-21`).
- **Health-check-every-5 is dead code** under default config: `(i-1) % MAX != 0 and (i-1) % 5 == 0` is unsatisfiable when MAX=5 (`:2242`, `:2678`).
- Success = `history.is_successful()` — the LLM's own `done()` claim (`:2728-2734`); duplicate detection = substring match on LLM prose (`:2739-2747`). **No portal-side verification of any created campaign, and no schedule verification at all.**
- Slack: `slack_agent.py` fire-and-forget daemon thread (failures only warn, `:54-69`); `slack_log_notifier.py` converts log-line signals to Slack, deduped per process (`:14-38`).

---

## 3. Ralph AI stack

### 3.1 Responsibilities

| Agent | File | Role |
|---|---|---|
| Strategist | `agents/strategist/agent.py` | Analysis ingestion (auto subprocess or register upload) → deterministic planning → `campaigns.xlsx` + `slot_info.csv` |
| Ralph Offers | `agents/offers/agent.py` (3.3K wrapper) | Load offers rows → fork's `run_offers_campaigns_from_combos` |
| Ralph Ads | `agents/ads/agent.py` | Load ads rows → fork's `run_ads_campaigns_from_rows` |
| ralph_analyse | `agents/ralph_analyse/` | Streamlit-based analysis helper (out of execution path) |
| health_check | `agents/health_check/` | WoW sales-report downloader + ROAS review — **not** a campaign verifier |

### 3.2 Planning rules (no LLM)

- Offer per active slot: `min_subtotal = ceil(AOV × 1.2 / 5) × 5` (`register_reco.py:159-164`); slot active if orders>0 or sales>0 (`:182-205`).
- Ads: bottom-8 active slots by orders (`:212-239`), fixed `$140/wk` + `$3` bid (`:22-24`).
- Slot tag math: `tag = daypart_row*7 + dow_col + 1` — duplicated in 3 places (`agents/strategist/agent.py:39-46`, `shared/campaign_planning/ralph_ads_excel.py:29-38`, `slot_info.py:33-39`) plus the fork's `_GRID_ROWS/_GRID_COLS`.
- Tag lookup fallback chain (`register_reco.py:369-380`): slots.csv grid (raw keys) → raw-day retry → **computed canonical tag**. The fallback means a casing mismatch in slots.csv no longer yields a null tag (mitigates bugs.md #4/#8), but it also means a deliberately customized slots.csv is silently ignored on key mismatch.

### 3.3 The fork-import mechanism (fragile)

`shared/reporting_imports.py:21-43` deletes `sys.modules["agents"]` and re-imports so the fork's `agents/` package wins. Side effects observed in this audit:

- `tests/test_strategist_manual.py` **fails deterministically** — after importing `agents.strategist.agent`, monkeypatch can no longer resolve `agents.strategist` ("module 'agents' has no attribute 'strategist'").
- 6 multilogin test modules fail **collection** and 2 more tests fail when the full suite runs in default order (all pass in isolation) — `sys.modules` pollution leaks across tests, and by implication across any same-process consumers (the FastAPI worker imports both the repo's `agents.*` and the fork's).
- `shared/ralph_slack_messages.py` is imported *by the fork* only because `shared/subprocess_env.py:25-38` puts the repo root on `PYTHONPATH` — the import topology is order-dependent.

### 3.4 Loop alignment with reporting Phase 2 (bugs.md #19 verification)

Confirmed aligned in the current tree: nav reset + fallback (`:2665-2676` vs `:2227-2239`), relogin every 5 (`:2628-2663` vs `:2192-2225`), `sleep(1)` (`:2830` vs `:2396`), `include_session_preamble=False` (`:2877`, `:2909`), compact login (`_login_for_campaigns:2567-2577`). Residual deltas: no `campaigns_executed.csv`, different writeback target, fresh login per run (Phase 2 amortizes Phase 1's session), dead `use_offer_tools` param (`:2725` selects the same tools in both branches).

---

## 4. Ralph AI vs reporting_browser_use — differences summary

**Ralph adds:** inspectable planning artifacts with human-editable Status (campaigns.xlsx/slot_info.csv); manual upload at planning and execution layers; async priority queue + run API + dashboard (`shared/browser_agent_jobs.py`, `api/browser_agent_runs.py`); multi-operator Airtable credential resolution; deterministic planning replacing LLM-adjacent analysis extraction.

**Ralph loses:** `campaigns_executed.csv` audit trail; Campaign-Mappings cross-run resume; Phase-1→Phase-2 session continuity (extra login); the current-UI prompts (locked to the stale main fork).

**Duplicated (drift hazards):** the ~250-line campaign loop exists twice in the same file (Phase 2 vs `_run_campaign_items`) × 5 fork copies; download-discovery helpers copy-pasted into the Strategist subprocess script (`agents/strategist/agent.py:160-241`); slot-tag math ×3; four near-identical fork trees plus a top-level copy.

---

## 5. Design weaknesses & missing safeguards (evidence-backed)

1. **Fork/prompt deadlock (P0):** Ralph's entry points exist only in the stale-UI main fork; current-UI prompts exist only in forks without those entry points (§2.1). Live logs confirm Ralph executes the old prompt.
2. **No schedule verification → store-wide campaign risk (P0):** slot-specificity depends entirely on the LLM honoring STEP 4; STEP 6 never checks the schedule (`:1592-1596`); `set_schedule_grid` doesn't verify persistence post-Save (`:804-809`); success is self-reported (`:2728-2734`). A "Successful" row can be an all-day, store-default campaign.
3. **Silent slot loss:** unmappable day/slot labels drop tags with no log at three layers (`ralph_ads_excel.py:36-37`, `campaign_workbook.py:71-73`, `plan_builder.py:51-52`); rows without tags are silently skipped (`strategist_campaign_sheets.py:192-194`).
4. **`task_builder` outside the per-item try** (`doordash_agent.py:2722`): one malformed row (e.g. slot tag 43 → IndexError at `:1494-1500`) aborts the whole run; no tag range validation upstream (`:127-143`).
5. **Silent money defaults:** subtotal→$10 (`strategist_campaign_sheets.py:195-197`), bid→$3 (`:266-268`), budget→0 → LLM chooses spend (`doordash_agent.py:2509-2513`).
6. **Manual-mode writeback broken:** Excel uploads become CSV (`api/main.py:277-279`) but writeback uses openpyxl → silent warning, no status persistence, no resume for any manual run (`strategist_campaign_sheets.py:393-397`).
7. **Run status hardcoded "success"** (`doordash_agent.py:2842-2851`) even at 0/N created or after an abort.
8. **Dead health check** (§2.5) — the only mid-session liveness probe never runs, and it detects blank pages, not login screens.
9. **`sys.modules` surgery** (§3.3) is provably leaking — failing tests are the canary.
10. **No credential↔operator↔workbook consistency check** (`api/main.py:725-797`); free-typed creds + lexicographic latest-run-dir lookup can pair the wrong plan with the wrong merchant account; passwords travel in plaintext prompts.
11. **No spend/approval gate in the live path** — the only gate lives in unused legacy `orchestrator/flow_manager.py:31-47`; `MarketingPlan.approval_status="pending"` (`plan_builder.py:101`) is never enforced.
12. **Crash-recovery gaps:** in-memory queue; `result.json` only on success (`api/browser_agent_runs.py:53-54`); `meta.json` observed stuck at `"queued"` while 17 MB of run.log accumulated (2026-06-09 runs); non-atomic `wb.save` per campaign (`strategist_campaign_sheets.py:417`); Strategist 1200 s subprocess timeout discards all partial work and can orphan Chrome (`agents/strategist/agent.py:617-625`).

Cross-references: full failure-mode tables in `edge_cases.md`; incident analysis in `failure_postmortem.md`; latency quantification in `performance_analysis.md`; consolidated priorities in `system_audit_report.md`.
