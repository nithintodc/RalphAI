# RalphAI — Next Steps (Consolidated)

> Single source of truth for all open bugs, fixes, performance gaps, architecture improvements, and SuperApp tasks.
> Consolidated from: `bugs.md`, `edge_cases.md`, `failure_postmortem.md`, `performance_analysis.md`, `optimiser.MD`, `system_audit_report.md`, `RalphAI_Plan.md`, `agents/the_super_app/tasks.MD`
> Last updated: 2026-06-16

---

## Quick Summary

Four systemic problems explain slowness, failures, and the store-wide-campaign incidents:

1. **Fork/prompt deadlock (N1)** — Ralph uses the main `reporting_browser_use` fork (the only one with `_run_campaign_items`) but that fork still has the **retired portal UI prompt** ("Discount for all customers"). Current carousel prompts are only in melt/savvy. Estimated cost: +70–300 s per campaign; Ralph runs ~1.5–2.1× slower. The 2026-06-09 run completed **3 of 77 campaigns in ~10 hours**.
2. **Store-wide campaign bug class is detection-proof (N2/N3/N16)** — STEP 6 verification never checks the schedule; `set_schedule_grid` never confirms the Save persisted; success = the LLM's own claim; `Successful` rows are skipped forever.
3. **No validation layer (N4/N8/N9)** — slot tags outside 1–42 abort the entire run; unparseable money silently defaults ($10 subtotal / $3 bid / budget 0 → LLM picks spend); CSV upload passes `"nan"` / `"14351.0"` store IDs into the browser.
4. **State and reporting are not trustworthy (N5/N6/N11)** — run status hardcoded `"success"` even at 0/N; manual-mode status writeback silently broken; killed runs leave `meta.json` stuck at `"queued"`.

---

## Part 1 — Bug Register

**Legend:** 🔴 High (money risk / run failure) · 🟡 Medium · 🟢 Low · Status: Open / Fixed / Mitigated

### P0 — Fix Immediately (live money/correctness, every run affected)

#### N1. Ralph locked to stale-UI main fork — 🔴 Open
`_run_campaign_items` / `run_offers_campaigns_from_combos` / `run_ads_campaigns_from_rows` exist **only** in `agents/reporting_browser_use/agents/doordash_agent.py` (2,936 lines). Current carousel prompts ("More ways to help you grow" → "Offer a discount promotion", name-first store search, STEP 3B Target audience) exist **only** in melt/savvy. Flipping `MARKETINGRECO_REPORTING_ROOT` to savvy raises AttributeError.

**Fix:** port savvy's STEP 1 + name-first search + STEP 3B into the main fork's `get_task_description_campaign_for_subtotal_combo` (`:1468`) and `get_task_description_ads_campaign` (`:2432`). Longer term: one shared module.

#### N2. No schedule verification → store-wide all-day campaign recorded Successful — 🔴 Open
Portal default = "Run all day". STEP 6 checks subtotal+name only (`:1592-1596`); `set_schedule_grid` verifies grid pre-Save but never post-Save (`:804-809`); success = `history.is_successful()` (`:2728-2734`); `Successful` rows skipped forever (`:146-149`).

**Fix:** (a) post-Save readback (modal closed + summary shows custom schedule); (b) STEP 6 must assert the schedule summary; (c) post-run portal verifier that diffs created campaigns + schedules vs workbook; alert on "Every day, All day" TODC-* campaigns.

#### N4. One malformed row aborts the entire run — 🔴 Open
`task_builder(item)` sits **outside** the per-item try (`doordash_agent.py:2722`). Slot tag >42 (no range check in `_parse_slot_tags`, `:127-143`) → IndexError in `_GRID_ROWS[(t-1)//7]` (`:1494-1500` / `:2461-2468`) → loop dies, browser killed, remaining rows never attempted.

**Fix:** validate tags ∈1–42 at parse (reject row, continue); move `task_builder` inside the per-item try.

#### N8. Silent money defaults — LLM can choose spend — 🔴 Open
Unparseable `Minimum Subtotal` → $10 (`:195-197`); bid → $3 (`:266-268`); missing budget → 0 (`:271-275`) and the prompt then says "leave default **or set a reasonable weekly budget**" (`doordash_agent.py:2509-2513`). Legacy path default is $20 (`campaign_params.py:475-485`).

**Fix:** unparseable money → reject row with loud report; budget 0 → never delegate to LLM.

#### N5. Run status hardcoded "success" — 🔴 Open
`_run_campaign_items` returns `{"status": "success", …}` unconditionally (`:2842-2851`). A run with 0 created, or aborted after relogin failure (`:2653-2663`), still reports success.

**Fix:** `success` only if `failed==0` and not aborted; else `partial`/`failed`; include unattempted count.

---

### P1 — Before Production Scale-Up

#### Post-run Portal Verifier (new small agent)
Scrape Marketing → Campaigns, diff names + schedules vs workbook `Successful` rows, alert on "Every day, All day" TODC-* campaigns and missing campaigns. Single component converts N2/N3/5.5/5.11 from invisible to detected.

#### N3. LLM self-reported success + prose-based duplicate detection — 🔴 Open
`completed_ok = history.is_successful()` (`:2728-2734`); duplicate = substring match on LLM prose (`:2739-2747`) — "no duplicate warning appeared" is a false positive; a paraphrase is a false negative. Hallucinated success → permanent skip, campaign never exists.

**Fix:** structured `done()` payload (JSON: created|duplicate|failed + confirmation text); DOM-based duplicate-dialog detection.

#### N6. Manual-mode status writeback silently broken — 🔴 Open
Excel uploads are converted to **CSV** (`api/main.py:277-279`); `update_campaign_workbook_status` calls `openpyxl.load_workbook` on CSV → exception caught as warning, returns False (`strategist_campaign_sheets.py:393-397`). Every manual run loses all per-campaign status.

**Fix:** keep uploads as xlsx (write back to extracted sheet), or add a CSV writeback path.

#### N9. CSV path: no NaN-cleaning / store-id normalization — 🔴 Open
Excel rows are NaN-cleaned (`:165`); CSV rows are not (`:227-234`, `:307-314`) → `store_id "nan"` passes truthiness check (`:187-190`); mixed-dtype Excel exports yield `"14351.0"`. A browser run is burned searching a nonexistent store.

**Fix:** shared row-cleaning + `int(float(s))` ID normalization; reject non-numeric IDs.

#### N13. Non-atomic workbook saves; no older-run fallback — 🟡 Open
`wb.save()` per campaign (`:417`); a kill mid-save corrupts campaigns.xlsx; next auto run picks only the newest dir (`:61-75`) and dies on the corrupt file.

**Fix:** tmp+rename writes; fall back to next-newest run dir.

#### N11. Killed-run state loss — 🟡 Open (observed 2026-06-09)
Three offers runs: `meta.json` stuck `"queued"` while 3–17 MB run.logs accumulated; no `result.json` (written only on success, `api/browser_agent_runs.py:53-54`); reconciler flips only `running` jobs (`shared/browser_agent_jobs.py:63-78`) — queued jobs phantom forever.

**Fix:** meta heartbeat (queued→running→progress), `result.json` on failure paths, reconcile queued jobs, persist queue.

#### N7. `sys.modules["agents"]` surgery corrupts the repo package — 🔴 Open
`shared/reporting_imports.py:36-41` deletes the top-level `agents` module. Consequences: `tests/test_strategist_manual.py` fails deterministically; 6 multilogin test modules fail collection; 9 total failures trace to this. Same pollution in the live FastAPI worker.

**Fix:** load the fork via `importlib.util.spec_from_file_location` under a unique namespace (`reporting_fork.*`); never mutate `sys.modules["agents"]`.

#### N14. No credential↔operator↔workbook consistency check — 🟡 Open
Free-typed dashboard creds (`api/main.py:725-797`) + lexicographic latest-dir lookup can execute operator A's plan in operator B's merchant account. Passwords interpolated plaintext into prompts (`shared/doordash_portal_tasks.py:98,107`).

**Fix:** bind workbook to operator_id at generation; verify portal account matches before the loop; redact secrets in logs.

---

### P2 — Improvements

#### N12. Duplicate churn by design — 🟡 Open
Deterministic names (`TODC-ADS-{store}`, `TODC-{store}-${min}`, `campaign_workbook.py:98,125`) collide with last week's live campaigns; `Skipped (duplicate)` retried every run (`:146-149` honors only successful/success). AOV drift creates a new name alongside the old one → overlapping discounts.

**Fix:** week-stamped names or terminal duplicate status + live-campaign pre-flight.

#### N18. Missing audit ledger + global serialization — 🟡 Open
No `campaigns_executed.csv`/JSONL in Ralph path; single worker thread serializes all browser runs (`shared/browser_agent_jobs.py:94-127`) — queue waits of hours; Strategist auto runs operators serially at ≤1200 s each (`agents/strategist/agent.py:617-625`), subprocess timeout can orphan Chrome.

**Fix:** per-item JSONL ledger; per-operator workers; process-group kill.

#### N10. Dead health check — 🟡 Open
`(i-1) % MAX != 0 and (i-1) % 5 == 0` unsatisfiable at MAX=5 (`doordash_agent.py:2242`, `:2678`). The only mid-session liveness probe never runs — and it only detects blank pages, not login screens.

**Fix:** decouple cadence from MAX; add login-screen detection; consecutive-CDP-failure → immediate browser restart.

#### N15. Silent slot-tag drops at 3 layers — 🟡 Open
Unknown daypart/day → None → dropped with no log: `ralph_ads_excel.py:36-37`, `campaign_workbook.py:71-73`, `plan_builder.py:51-52`; tag-less rows silently skipped (`:192-194`); `_DOW_COL` requires full day names (`ralph_ads_excel.py:10-18`).

**Fix:** count + log every drop; fail the run above a threshold; reconcile plan-vs-loaded row counts.

#### N16. `set_schedule_grid` residual gaps — 🟡 Open
Empty `wanted_tags` clears all 42 cells and saves an empty schedule (verify trivially passes, `:741-743`, `:804-808`); PARTIAL path delegates Save to the LLM (`:811-817`); manual fallback assumes a clean grid after a dirty failure (`:1503-1532`).

**Fix:** reject empty set; post-Save readback; clear-first fallback text.

#### N17. Writeback matching flaws — 🟡 Open
`update_campaign_workbook_status` updates the **first** name match only (`:413-419`); slot_info "Offer + Ads" rows share one Status cell — ads writeback overwrites offer outcome (`:487-501`); fixed `DictWriter` header destroys operator-added columns (`:509-512`).

**Fix:** update all matches; separate Offer/Ads status columns; preserve headers.

#### Legacy sync bugs (confirmed open)
| # | Issue | Sev |
|---|---|---|
| 1 | Ads naming: `TODC-{sid}-Ads` vs `TODC-ADS-{sid}` — standardize on `TODC-ADS-{store_id}` | 🔴 |
| 2 | Manual Ads upload rejects Strategist workbook — `api/main.py:268-270` accepts only `"ads"`; fix: accept `"ads campaigns"` | 🔴 |
| 3 | Status casing: `doordash_agent.py:2000,2126` filter `!= "Successful"` (exact) vs tolerant `_status_skip` — one `normalize_campaign_status()` everywhere | 🔴 |
| 14 | `Late Night` vs `Late night` in `slots.js:13` vs backend canon — display-only, align the constant | 🟢 |
| 18 | Health-check regex `^TODC-\d+-Ads$` never matches `TODC-ADS-{id}` — fix with #1 | 🟢 |

**Fork consolidation:** one canonical `reporting_browser_use` package with a fork/profile config layer; delete the ~31k LOC of redundant copies (`slack_log_notifier.py` alone is byte-identical in 6 places).

---

### P3 — Future Optimization

- Per-operator queue workers keyed by MLX profile — multi-operator days go from sum-of-runs to max-of-runs.
- Replace nav-reset mini-agent with deterministic `navigate_to(marketing_url)` + modal dismiss (LLM fallback only) — saves 10–18 min per 50-campaign run.
- `max_steps≈40` / 420 s campaign timeout once prompts match the UI; revisit `MAX_CAMPAIGNS_PER_SESSION` 5→8–10 with data.
- Skip startup login when the MLX session is already authenticated (CDP probe of Reports URL).
- Delete dead `use_offer_tools` parameter (`:2725`) and dead health-check blocks (`:2242`, `:2678`); keep `set_schedule_grid` sleeps (they buy grid reliability).
- `dmd_stratgist_manual_mode` typo, terminology drift (#11/#13), docs/UI alignment (#5/#6/#7/#9/#10), register docs/columns (#15/#16).

---

## Part 2 — Performance Issues

### Current State (measured / estimated)

| Scenario | Best | Typical | Worst |
|---|---|---|---|
| Reporting (UI-matched prompts) | ~160 s/campaign | ~230–270 s | ~990 s |
| **Ralph today (mismatched prompts)** | ~220 s/campaign | **(est.) ~330–570 s** | ~990 s |
| Reporting 50-campaign run | ~2.2 h | ~3.2–3.8 h | ~13.7 h |
| **Ralph 50-campaign run** | ~3.1 h | **(est.) ~4.6–7.9 h** | ~13.7 h |

2026-06-09 evidence: 10+ hours, 3 Successful of 77 planned. **Ralph ≈ 1.5–2.1× slower — almost entirely prompt/UI mismatch.**

### Per-Campaign Time Breakdown

| Component | Cost |
|---|---|
| Stale STEP 1 prompt (N1) | **(est.) +70–300 s typ; 720 s worst** |
| ID-first store search | (est.) +15–30 s |
| Campaign agent intrinsic (~25–35 steps @ 6.8 s) | 170–240 s (matched) |
| Nav-reset mini-agent | 14–25 s |
| Relogin + session restart every 5 (amortized) | 7–24 s |
| `set_schedule_grid` sleeps (deliberate — keep them) | 5.3–7.1 s |
| Per-campaign writeback (measured) | 15 ms → negligible |

### Prioritized Optimizations

| # | Change | Expected gain |
|---|---|---|
| 1 | **Port savvy's carousel STEP 1 + name-first search + STEP 3B into main fork** (`:1468`, `:2432`) | (est.) **30–55% wall clock** + higher success rate |
| 2 | Cap `max_steps≈40` + `AGENT_CAMPAIGN_TIMEOUT≈420 s` once prompts match | 30–60% cut in worst-case per-campaign cost |
| 3 | Replace nav-reset mini-agent with direct `navigate_to` + deterministic modal dismiss | 14–25 s → ~3 s/campaign; 10–18 min /50 |
| 4 | Skip startup login when MLX profile session already authenticated (CDP probe); MAX_CAMPAIGNS_PER_SESSION 5→8–10 | 30–120 s/run; restart amortization saved |
| 5 | ≥2 queue workers keyed by operator/MLX profile; parallelize strategist operators | Multi-operator: hours → ~max(single run) |

**Not bottlenecks (verified):** per-campaign writeback (15 ms measured), `set_schedule_grid` sleeps (buy reliability — keep), Slack notifications (fire-and-forget).

---

## Part 3 — Tech Stack & Architecture Improvements

### Phase 1 — Stop the Bleeding (low risk, high impact)

1. **Async-ify / queue the blocking endpoints** — `post_deepdive`, `post_data_run`, `post_campaign_analyser`, reporting `subprocess.run`, and `POST /api/jobs/{id}/run` all hold the request thread for hours. Standardize on the enqueue + HTTP 202 + poll pattern already used by offers/ads.
2. **Byte-offset log tail + SSE/WebSocket** — `tail_run_log` reads the **whole log file** every 2 s per active run. Switch to byte-offset + streaming.
3. **`GZipMiddleware`**, **calamine** engine for Excel reads (10–80× faster), **orjson** for big JSON (5 MB Airtable snapshot parsed on hot paths).
4. **Dashboard:** `React.lazy` route splitting (all 14 pages imported synchronously), TanStack Query on `/api/account-directory` (fetched with full credentials on 4+ pages with zero caching), `AbortController` in poll loops (none today — keep running after navigation), pause polling when `document.visibilityState === "hidden"`.

### Phase 2 — Storage & Queue

5. **SQLite → Postgres** for runs/jobs index (currently O(n) full-file JSONL scans hit every 2–15 s by dashboard polling). **Redis** for job state/queues (already provisioned in `docker-compose.yml`, never imported).
6. **≥2 queue workers** keyed by operator/MLX profile; parallelize strategist/data-run analysis phases (currently serial `subprocess.run` per operator, timeout 1200 s).
7. **SSE log streaming** end to end (replaces 2–15 s polling).

### Phase 3 — Consolidation

8. **Merge the six `reporting_browser_use*` forks** (~38k LOC, ~31k redundant) into one package + config. This also directly fixes N1 (prompt mismatch), because fixing one file fixes all forks.
9. **Extract shared SuperApp `lib/` package**; deprecate the deepdive fork and legacy Streamlit apps (`app2_0`, `app2_0_savvy`, `deepdive/cloud_app` — combined ~37k LOC candidates for deprecation).
10. **Split `api/main.py` monolith** (2,022 lines, ~52 routes) into `api/routers/{runs,jobs,offers,ads,health_check,directory}.py`; lazy-import agent trees inside worker code only.

### Phase 4 — Super App Deep Work

11. **Web Worker** for ZIP/CSV parsing (currently freezes main thread on multi-ZIP upload); normalize data once at upload, store normalized arrays only.
12. **`@tanstack/react-virtual`** for DataTable (Register can exceed 50k DOM cells). Broad Zustand subscriptions (`useDataStore()` with no selector) → per-field selectors + shallow compare. Dynamic-import `xlsx` on click (currently in main bundle).
13. **Backend DuckDB ingest** for operators that exceed the 450 MB browser cap; also replace health-check `iterrows` with `groupby().agg()` (same CSV parsed twice per operator today).

### Pandas/Excel Anti-Patterns to Fix

| Location | Pattern | Fix |
|---|---|---|
| `health_check/data_processor.py:432` + `agent.py:768-783` | Same financial CSV fully parsed **twice** per operator | Read once, split with `groupby` + date bins |
| `health_check/data_processor.py:301-390` | `iterrows` before a groupby, then again after | Pure `groupby().agg()` |
| `strategist/campaign_workbook.py:88-127` | Per-cell openpyxl writes | `df.to_excel` / bulk row append |
| `campaign_analyser/analyzer.py:141-163` | Nested `iterrows` × repeated boolean filters | Pre-index orders by `(store, DOW, slot)` |
| `reporting_browser_use/agents/campaign_params.py:200,298,459` | Workbook read **3 times** with `iterrows` (×6 forks) | Read once; `to_dict("records")` |

---

## Part 4 — SuperApp Consolidation Tasks

### Phase 1 — High Priority (Core Gaps)

| Task | What | Source | Effort |
|---|---|---|---|
| 1. Slack `/report` bot | Slash command → modal (dates + operator) → triggers analysis headless → posts Excel to channel | App2.0, App3.0 | Large |
| 2. Google Drive native export | Service account auth, upload to Shared Drive, convert to Sheet — replace Streamlit companion | App2.0-cloud-savvy | Medium |
| 3. Data validation screen | Between Upload and Config: verify columns, date ranges, row counts, warn on bad data | App3.0 | Medium |
| 4. Campaign-level drill-down | Filter by Campaign ID; per-campaign ROAS, Orders, Sales, Spend, Cost per Order; date pivot | Marketing-Breakdown | Medium |
| 5. Verify new customer tracking | DD: store-level from `MARKETING_PROMOTION_*.csv` → `New customers acquired`; UE: platform totals | App2.0, Ralph-Analyse | Small–Med |
| 6. Period analysis modes | Confirm QoQ, MoM, WoW, Single Range, Single Week; side-by-side metric bridge tables | App3.0 | Small–Med |

### Phase 2 — Medium Priority

| Task | What |
|---|---|
| 7. Markup Contribution Calculator | In-store vs delivery P&L; contribution margin per store after commission, F&P, labor |
| 8. Sales Channel Breakdown | DashPass / Marketplace / Pickup split from `SALES_viewByTime_byStoreProductPerformance_*.csv` |
| 9. Combined Unified Table | Date-level merge: Financial + Marketing + Sales (16+ columns side-by-side) |
| 10. GCP Cloud Pipeline | Upload large files to GCS → Cloud Run jobs → stream results back |
| 11. P&L Contribution Margin in Analysis | Integrate markup/commission modeling into financial analysis |

### Phase 3 — Low Priority / Future

| Task | What |
|---|---|
| 12. GrubHub support | Third platform: CSV parser, store mapping, 3-platform summaries |
| 13. Slack threshold alerts | ROAS drops, sales declines, store goes offline |
| 14. Retire satellite apps | Archive App2.0, App2.0-cloud-app-savvy, App3.0, Marketing-Breakdown, markup-app, Ralph-Analyse after full feature absorption |

### SuperApp Performance Fixes Needed Now

- `zipHandler.js:127-207` parses every CSV sequentially on the main thread → move to **Web Worker**.
- The "4-window" filter runs on the **entire** dataset 4× in at least three places (`periodEngine.js`, `financialBreakdown.js`, `slots.js`) — pre-index by date key once.
- `buildDdFinancialEnrichment` groups entire dataset by orderId and is executed **twice** per Slots view (`slots.js:446-448` + `:543-545`).
- `slotAnalysis`, `bucketAnalysis`, `marketingTables`, register rows not cached — each tab recomputes from raw rows. Cache at analyze time like `storeTables`/`summaryTables`.
- `import * as XLSX from 'xlsx'` is in the main bundle — dynamic-import on click.
- `Late Night` vs `Late night` casing: `slots.js:13` → `'Late Night'`; backend canon `'Late night'` (`shared/time_slots.py:24`) — align the constant.

---

## Part 5 — Key Incidents (Reference)

### 2026-06-09: Ralph Offers — Near-Zero Throughput

3 runs totaling ~10 h, completed **3 Successful + 2 dup-skips of 77 planned**, all runs died without finishing.

| Run | Log size | Outcome |
|---|---|---|
| `d5c12897` | 15.1 MB | meta stuck `"queued"`, no result.json |
| `0206368f` | 17.4 MB | meta stuck `"queued"`, no result.json |
| `e60fd73c` | 3.3 MB | meta stuck `"queued"`, no result.json |

Root causes: (1) stale prompt / UI mismatch → LLM hunting for cards that no longer exist; (2) Chrome CDP instability (6× `Connect call failed`, 5× `No lifecycle events`, 5× frame churn, 4× modal blocked); (3) process killed without cleanup, no state durability.

### Browser/CDP Failure Signatures (for triage)

| Signature | Count | Likely cause |
|---|---|---|
| `Connect call failed ('::1', 9222)` | 6× | Chrome CDP died / port conflict |
| `No lifecycle events received for <url>` | 5× | Page never finished loading |
| `Frame with the given frameId is not found` | 5× | CDP session churn after navigation |
| `'Page.enable' wasn't found` | 3× | CDP protocol/library mismatch |
| Watchdog `Handling took more than 8.0s` | 6× | Event-loop starvation during DOM serialization |
| `timed out (page may be blocked by dialog)` | 4× | Portal modal blocked navigation |

### Fixed Incidents (regression-tested)

| Incident | Fix | Status |
|---|---|---|
| `Late Night` vs `Late night` → lost ads slots (B) | `normalize_slot_name()` case-insensitive | ✅ Fixed |
| Bottom-8 included zero-order slots (A) | `bottom_order_slot_keys()` ranks active slots only | ✅ Fixed |
| UI `action=promo` hid ads (C) | Fixed | ✅ Fixed |
| `slots.csv` grid key mismatch (#4/#8) | `_lookup_slot_tag` falls back to computed canonical tag | ⚠️ Mitigated (custom grids silently ignored) |

---

## Part 6 — Top Edge Cases by Leverage

### Top 6 Fixes (leverage-ordered)

1. **Post-run portal verifier** — scrape Marketing → Campaigns, diff names+schedules vs workbook: detects 5.5 (create-then-crash), 5.9 (Save not persisted), 5.10 (empty schedule), 6.2 (hallucinated success), 6.3 (all-day campaign) and replaces the duplicate heuristic with ground truth.
2. **Honest run status** (7.1) + `partial`/`aborted` semantics (5.12).
3. **Structured `done()` payload** + DOM-based duplicate detection (5.6) — stop branching on LLM prose.
4. **Schedule gate before Create** — validates the schedule summary in STEP 6 (kills the store-wide bug class at the source).
5. **Loader hardening** — NaN-clean CSV, normalize store IDs, tag range 1–42, reject unparseable money (1.5/1.6/1.9/3.4); move `task_builder` inside the per-item try.
6. **Atomic writes + per-item JSONL ledger** (5.14/6.4) — survive process kills without data loss.

### Input Edge Cases (highest risk)

- CSV-vs-Excel NaN asymmetry (1.5): Excel NaN-cleans, CSV does not → `"nan"` reaches the browser
- Float store IDs `"14351.0"` from mixed-dtype Excel (1.6): no `_norm_store_id` in loader
- Slot Tags junk ("1-5", "abc", "0", "43") (1.9): `_parse_slot_tags` drops silently; tag 43 aborts the run
- Duplicate campaign names in sheet (1.8): both executed; writeback updates first match only
- `Skipped (duplicate)` retried forever (3.1): not in the skip-list, so re-run on every subsequent session
- Shared Offer+Ads Status cell in `slot_info` (3.6): ads writeback overwrites offer outcome

### Browser Execution Edge Cases (highest risk)

- Session expiry mid-5-block: campaign tasks carry no credentials (`include_session_preamble=False`, `:2877,:2909`) — health probe is dead code, doesn't detect login screens
- Timeout after "Create promotion" clicked but before `done()` (5.5): campaign EXISTS in portal, recorded Failed → re-attempted next run (overlap risk)
- `set_schedule_grid` anchors: `'Weekdays'` text, teal-RGB checked heuristic, exact Save text — any portal redesign breaks it silently (5.7)
- Empty `wanted_tags` → clears all 42 cells, verification trivially passes, saves empty schedule (5.10)

---

## Suggested Overall Fix Order

1. **N1** — port carousel prompts into main fork (unblocks everything; biggest single win, low risk)
2. **N2 + N16** — schedule gate + post-Save verification + portal verifier
3. **N3 + N5** — structured done payload, DOM duplicate detection, honest run status
4. **N4 + N8 + N9** — loader hardening (tags 1–42, money, NaN/IDs) + `task_builder` inside try
5. **N6 + N13 + N17** — writeback correctness (manual mode, atomic saves, all-match updates)
6. **N7** — `importlib`-based fork loading (fixes the test suite)
7. **#1/#2/#3/#18** — naming / sheet / status unification (original sync bugs)
8. **N11 + N12 + N18** — run-state durability, duplicate semantics, ledger, queue
9. **Phase 1 tech stack** — async endpoints, byte-offset log tail, gzip/calamine/orjson, dashboard polish
10. **Fork consolidation** — merge six forks; then Phase 2 (SQLite/Redis) + Phase 3 (api router split) + Phase 4 (SuperApp deep work)
11. **SuperApp Phase 1 tasks** — Slack bot, Google Drive, validation screen, campaign drill-down
12. Remaining 🟡/🟢 legacy items + SuperApp Phase 2/3

---

## Verification Commands

```bash
# Full suite — must be green including test_strategist_manual (N7) in default order
.venv/bin/python -m pytest tests/ -q

# Strategist invariants (A/B/C regressions)
.venv/bin/python -m pytest tests/test_strategist_bottom_ads.py \
  tests/test_strategist_slot_info.py tests/test_register_reco.py \
  tests/test_ralph_ads_upload_rows.py tests/test_strategist_campaign_sheets.py \
  tests/test_time_slots.py -q

# N4: a row with Slot Tags "43" must be rejected at load, not abort the run
# N9: a CSV with a blank store-id cell must not yield store "nan"
# N1: the active fork must carry the carousel prompt
grep -l "More ways to help you grow" agents/reporting_browser_use/agents/doordash_agent.py
```

---

*Sources consolidated from: `bugs.md` (bug register N1–N18, #1–19, A–C), `system_audit_report.md` (executive summary, risk matrix, P0–P3 fix list), `performance_analysis.md` (per-campaign timing, bottleneck inventory), `optimiser.MD` (tech stack + architecture proposals), `edge_cases.md` (7-stage failure-mode catalog), `failure_postmortem.md` (2026-06-09 incident, browser failure signatures), `RalphAI_Plan.md` (original gaps assessment), `agents/the_super_app/tasks.MD` (consolidation task list).*
