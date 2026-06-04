# TheSuperApp — Consolidation Tasks

> Goal: Make TheSuperApp the single source of truth for all TODC analytics,
> absorbing every capability from the six satellite apps.

---

## Coverage Matrix

| Capability | Source App(s) | In SuperApp? | Priority |
|---|---|---|---|
| DD Financial parsing & analysis | App2.0, App3.0, Ralph-Analyse | YES | — |
| UE Financial parsing & analysis | App2.0, App3.0, Ralph-Analyse | YES | — |
| Pre/Post 4-window comparison | App2.0, App3.0, Ralph-Analyse | YES | — |
| YoY / Growth% metrics | App2.0, App3.0, Ralph-Analyse | YES | — |
| Store-level drill-down | App2.0, App3.0, Ralph-Analyse | YES | — |
| Marketing Corp vs TODC | App2.0, App3.0, Ralph-Analyse | YES | — |
| Slot / Daypart analysis | App2.0, App3.0 | YES | — |
| Order bucket analysis | App2.0, App3.0 | YES | — |
| Diagnostics (waterfall, decomposition) | App2.0, App3.0 | YES | — |
| Product Mix analysis | App2.0 | YES | — |
| Operations (downtime, cancellations) | App2.0 | YES | — |
| Excel workbook export | App2.0, App3.0, Ralph-Analyse | YES | — |
| Google Sheets (via Streamlit companion) | App2.0 | YES | — |
| App2 Date-Wise / Bucketing views | App2.0 | YES | — |
| **Slack `/report` bot** | App2.0, App2.0-cloud-savvy, App3.0 | **NO** | P1 |
| **Direct Google Drive upload** | App2.0, App2.0-cloud-savvy, App3.0 | **Partial** | P1 |
| **GCP Cloud Pipeline (GCS + Cloud Run)** | App2.0-cloud-savvy, App3.0 | **NO** | P2 |
| **Data validation screen** | App3.0 | **NO** | P1 |
| **Campaign-level drill-down** | Marketing-Breakdown | **NO** | P1 |
| **Sales by channel (DashPass/Marketplace/Pickup)** | Marketing-Breakdown | **NO** | P2 |
| **Combined unified table (fin+mkt+sales by date)** | Marketing-Breakdown | **NO** | P2 |
| **Slack alerts (ROAS < threshold)** | Marketing-Breakdown (planned) | **NO** | P3 |
| **GrubHub platform support** | Marketing-Breakdown (planned) | **NO** | P3 |
| **Markup contribution calculator** | markup-app | **NO** | P2 |
| **P&L scenario modeling** | markup-app | **NO** | P2 |
| **In-store vs delivery unit economics** | markup-app | **NO** | P2 |
| **New customer tracking (DD store-level)** | App2.0, Ralph-Analyse | **Verify** | P1 |
| **Period analysis (comparison across periods)** | App3.0 | **Verify** | P1 |

---

## PHASE 1 — High Priority (Core Gaps)

### Task 1: Slack `/report` Bot Integration
- **Source:** App2.0 (`slack_report_bot.py`), App3.0 (`slack_report_bot.py`)
- **What:** Build a lightweight Node/Bun backend or serverless function that:
  - Listens for Slack `/report` slash command
  - Opens a modal for date range + operator name input
  - Accepts file uploads (dd-data.csv, ue-data.csv, marketing ZIPs)
  - Triggers TheSuperApp analysis pipeline (headless)
  - Posts the generated Excel workbook back to the Slack channel
- **Why:** App2.0 and App3.0 teams actively use this for automated reporting
- **Effort:** Large (needs a thin backend since SuperApp is client-side)

### Task 2: Direct Google Drive Export (Native)
- **Source:** App2.0 (`gdrive_utils.py`), App2.0-cloud-savvy (`gdrive_utils.py`)
- **What:** Replace the Streamlit companion app with native Drive upload:
  - Service account auth (JSON credentials)
  - Upload Excel to Shared Drive (`Data-Analysis-Uploads`)
  - Flat folder structure (avoids `teamDriveHierarchyTooDeep` error)
  - Date-stamped folders: `YYYY-MM-DD_HH-MM-SS_UUID`
  - Convert to native Google Sheet after upload
- **Current:** TheSuperApp has a Streamlit companion for this — consolidate into one flow
- **Effort:** Medium

### Task 3: Data Validation Screen
- **Source:** App3.0 (`validation_screen.py`)
- **What:** Add a validation step between Upload and Config screens:
  - Verify expected columns exist in each CSV/ZIP
  - Show detected date ranges and row counts per file
  - Flag missing or malformed data (e.g., non-numeric Sales columns)
  - Show column mapping summary (which columns were auto-detected)
  - Warn if date ranges don't overlap across platforms
- **Why:** Users currently proceed to analysis with bad data and only notice downstream
- **Effort:** Medium

### Task 4: Campaign-Level Drill-Down
- **Source:** Marketing-Breakdown (`app.js`)
- **What:** Extend the Marketing dashboard screen to support:
  - Filter by individual Campaign ID
  - View per-campaign metrics: Orders, Sales, Spend, ROAS, Cost per Order
  - Self-serve campaign flag toggle (show Corp/TODC/All)
  - Date-level pivot within a campaign
- **Why:** Marketing-Breakdown exists solely because SuperApp lacks campaign granularity
- **Effort:** Medium

### Task 5: Verify & Fix New Customer Tracking
- **Source:** App2.0 (`marketing_analysis.py`), Ralph-Analyse (`marketing.py`)
- **What:** Confirm SuperApp correctly handles:
  - DD new customers: store-level aggregation from `MARKETING_PROMOTION_*.csv` → `New customers acquired` column
  - UE new customers: platform-level totals (not store-level)
  - Display in summary tables and KPI cards
- **If missing:** Port logic from Ralph-Analyse's `marketing.py`
- **Effort:** Small–Medium

### Task 6: Verify Period Analysis Modes
- **Source:** App3.0 (`period_analysis_screen.py`, `comparison_screen.py`)
- **What:** Confirm SuperApp's `dateAnalysisMode` fully supports:
  - PvP (period vs period) — already exists
  - QoQ (quarter over quarter)
  - MoM (month over month)
  - WoW (week over week)
  - Single Range
  - Single Week
  - Side-by-side metric bridge tables (App3.0's comparison_screen)
- **If incomplete:** Port the comparison engine from App3.0
- **Effort:** Small–Medium

---

## PHASE 2 — Medium Priority (Feature Parity+)

### Task 7: Markup Contribution Calculator Module
- **Source:** markup-app (`index.html`)
- **What:** Add a new "Pricing Tools" section to the SuperApp with:
  - **Section A — In-Store vs Delivery:** Base price, markup %, food & paper %, labor % → calculates online price, new cost %s, savings delta
  - **Section B — P&L Scenarios:** Configurable scenarios (TODC Avg Order, Corp Avg Order, Business-level) with full P&L: Sales → Marketing Fee → Promo Spend → Commission → Food & Paper → Labor → Rent → OPNAD → Local → Contribution Margin
  - Allow adding/removing custom scenarios
- **Why:** markup-app is a standalone tool that franchise ops teams use for pricing decisions
- **Effort:** Medium

### Task 8: Sales Channel Breakdown
- **Source:** Marketing-Breakdown (`app.js` — Sales by Time/Product view)
- **What:** Parse `SALES_viewByTime_byStoreProductPerformance_*.csv` files and display:
  - Gross Sales, Orders, AOV by channel (DashPass, Marketplace Classic, Pickup)
  - Promotion fees vs Ad fees breakdown
  - Store-level channel mix analysis
- **Why:** Channel mix visibility doesn't exist in SuperApp today
- **Effort:** Medium

### Task 9: Combined Unified Table (Date-Level)
- **Source:** Marketing-Breakdown (`app.js` — Combined view)
- **What:** Add a "Daily Detail" view that merges by date:
  - Financial columns (Subtotal, Marketing Fees, Customer Discounts)
  - Marketing columns (Campaign Orders, Sales, Spend)
  - Sales columns (Gross Sales, Orders, AOV, Promo/Ad metrics)
  - 16+ columns side-by-side for correlation analysis
- **Why:** Marketing-Breakdown's unified table is its most-used feature
- **Effort:** Medium

### Task 10: GCP Cloud Pipeline
- **Source:** App2.0-cloud-savvy (`cloud_pipeline.py`)
- **What:** Optional cloud processing path:
  - Upload large files to Google Cloud Storage
  - Trigger Cloud Run jobs for heavy analysis
  - Stream results back to client
  - Monitor job execution status
- **Why:** Enables async processing for very large datasets (50+ stores)
- **Effort:** Large

### Task 11: P&L Contribution Margin in Analysis
- **Source:** markup-app (3PO Commission logic)
- **What:** Integrate markup/commission modeling into the financial analysis:
  - Apply user-configured markup % to calculate "true" in-store equivalent
  - Show contribution margin per store after commission, F&P, labor
  - Compare profitability: delivery vs in-store per order
- **Effort:** Medium

---

## PHASE 3 — Low Priority (Future)

### Task 12: GrubHub Platform Support
- **Source:** Marketing-Breakdown (planned feature)
- **What:** Add GrubHub as a third delivery platform:
  - GrubHub CSV parser
  - GrubHub-specific store mapping
  - Combined 3-platform summaries
- **Effort:** Large

### Task 13: Slack Alerts (Threshold-Based)
- **Source:** Marketing-Breakdown (planned feature)
- **What:** Configurable alert rules that fire via Slack webhook:
  - ROAS drops below threshold (e.g., < 4)
  - Sales decline > X% week-over-week
  - New store goes offline (operations)
- **Effort:** Medium

### Task 14: Retire Satellite Apps
- **What:** After all features are absorbed:
  - [ ] Archive App2.0 repo (add deprecation notice pointing to TheSuperApp)
  - [ ] Archive App2.0-cloud-app-savvy
  - [ ] Archive App3.0
  - [ ] Archive Marketing-Breakdown
  - [ ] Archive markup-app
  - [ ] Archive Ralph-Analyse
  - [ ] Update any bookmarks, Slack shortcuts, or docs that reference old apps
- **Effort:** Small (per app)

---

## Quick Reference: What Each Satellite App Contributes

| App | Unique Contribution to SuperApp | Status |
|---|---|---|
| **App2.0** | Slack bot, GDrive upload, Slack report automation | Must port |
| **App2.0-cloud-savvy** | GCP Cloud Run pipeline, cloud validation | Must port |
| **App3.0** | Comparison screen, period analysis, validation screen | Verify/port |
| **Marketing-Breakdown** | Campaign drill-down, channel mix, unified date table | Must port |
| **markup-app** | Pricing calculator, P&L modeling, contribution margin | Must port |
| **Ralph-Analyse** | Clean 4-step UX, KPI card layout (mostly absorbed) | Verify only |
