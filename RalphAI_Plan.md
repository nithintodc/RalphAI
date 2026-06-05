# RalphAI — Complete Assessment & Strategic Plan

**Prepared by:** Claude (AI Analysis)  
**Date:** June 5, 2026  
**Repo:** TODC-Projects/RalphAI  
**Client:** TheOnDemandCompany (TODC)

---

## Executive Summary

RalphAI has a solid architectural skeleton: a well-designed orchestration layer, multiple specialized agents, and real business logic captured in `Context.MD`. However, several critical agents are **stubs that return empty or hardcoded data**, the slot-level campaign intelligence already written in `ads_planner.py` is **not wired into the main pipeline**, and there are **4 inconsistent slot definitions** across the codebase. The data confirms your slot-level thesis is correct — Breakfast dominates volume, Dinner leads AOV, and Early Morning is your best new-customer acquisition window. The path forward is clear: close the stubs, standardize slots, and wire the intelligence that already exists into a unified loop.

---

## Part 1: What Exists and What Is Missing

### What Exists (and Works)

**Orchestration Layer** (`orchestrator/`)
- `todc_flow.py` — clean Python API: onboarding chain → full setup
- `flow_manager.py` — JSON contract chain with human approval gates, confidence floors, budget caps
- `state_machine.py` — operator lifecycle state management
- `event_router.py` + `scheduler.py` — event-driven dispatch

**DeepDive Agent** (`agents/deepdive/`)
- Full analysis pipeline: financial, sales, marketing, operations, support, executive summary
- Metric hierarchy builder
- HTML report generator
- Monthly reporting (App2.0 cloud pipeline internalized)
- SuperApp entry point

**MarketingReco Agent** (`agents/marketingreco/`)
- Three modes: `deepdive`, `manual`, `auto`
- `ads_planner.py` — **this is the most important file in the repo**: full slot-level DEFEND/GROW/HARVEST/SKIP tier logic using real transaction data
- Campaign mappings from combined analysis workbook
- Store-to-merchant ID alignment from FINANCIAL_DETAILED
- Register-based recommendation path

**Campaign Review Agent** (`agents/campaign_review/`)
- Pre/post campaign metrics with equal-length comparison windows
- ROAS, CTR, conversion rate, CPC, CPA, AOV lift, order volume lift
- Per-campaign breakdown by name with coverage percentage
- Budget utilization tracking

**Health Check Agent** (`agents/health_check/`)
- Full WoW pipeline: download → extract → build weekly CSVs → WoW analysis
- Multi-operator sequential processing with Multilogin support
- Campaign WoW outputs
- HTML/PDF report + Slack delivery
- Airtable operator directory integration

**Reporting Browser Use** (`agents/reporting_browser_use_browser/`)
- Real browser automation via browser-use library
- DoorDash login + report download (financial + marketing)
- Playwright-based flow

**Shared Models**
- `DeepDiveReport`, `MarketingPlan`, `RecommendedCampaign`, `CampaignSetupResult`, `CampaignReviewReport` — all well-defined Pydantic models

**Context.MD**
- Comprehensive business logic document: all formulas, slot definitions, bucketing rules, CSV parsing, date handling. This is the ground truth for all calculation logic.

---

### What Is Missing / Broken (Critical Gaps)

#### Gap 1: `doordash_client.py` Is an Empty Stub (BLOCKER)
```python
# agents/ingestion/doordash_client.py — current state
def fetch_operator_window(operator_id, days):
    return {"orders": [], "revenue": [], "ads": [], "menu": []}
```
The entire `ingestion/pipeline.py` → `flow_manager` → `deepdive` contract chain returns empty data. This means the "auto" flow via `todc_flow.py` / `flow_manager.py` produces zero results. The real data loading lives in `agents/deepdive/data_loader.py` (loads zip files) and `agents/reporting_browser_use_browser/agents/doordash_agent.py` (browser automation). These two paths are not unified.

#### Gap 2: `ads_flow.py` and `offers_flow.py` Are Stubs (BLOCKER)
```python
# agents/campaign_setup/ads_flow.py — current state
def run_ads(*, store_ids, plan_fragment):
    return CreatedCampaign(campaign_id="dd_ads_stub", status="scheduled", ...)
```
Campaign setup never actually creates campaigns. The real browser automation for setting up campaigns exists in the `reporting_browser_use_*` family but is not connected to the `campaign_setup` agent.

#### Gap 3: `plan_generator.py` Returns Two Hardcoded Campaigns (CRITICAL)
```python
# agents/marketingreco/plan_generator.py — current state
campaigns = [
    RecommendedCampaign(campaign_type="sponsored_listing", campaign_name="Weekend traffic test", budget=150.0, ...),
    RecommendedCampaign(campaign_type="promo", campaign_name="AOV lift — spend threshold", budget=0.0, ...),
]
```
The `ads_planner.py` has a full slot-level intelligence engine (DEFEND/GROW/HARVEST/SKIP) that reads real transaction data and produces granular slot × store × DOW recommendations. But `plan_generator.py` (used in the `deepdive` mode) ignores it entirely, returning the same two campaigns for every operator.

#### Gap 4: No UberEats Ingestion Pipeline
`ingestion/schema.py` defines `IngestionData` but the pipeline only supports `source == "doordash"`. UberEats data is handled in the App2.0/cloud pipeline but not in the agentic flow. For multi-platform operators, this means incomplete analysis.

#### Gap 5: Inconsistent Slot Definitions (4 Different Standards)
The codebase has 4 different slot time mappings across files, none of which fully match each other:

| File | Early Morning | Breakfast | Lunch | Afternoon | Dinner | Late Night |
|------|--------------|-----------|-------|-----------|--------|------------|
| `slot_analysis.py` (legacy) | 0–4:59 AM | 5–10:58 AM | 10:59–1:58 PM | 1:59–3:58 PM | 3:59–7:18 PM | 7:19 PM+ |
| `new_analysis_engine.py` | 11 PM–4:59 AM | 5–10:59 AM | 11 AM–2:59 PM | 3–5:59 PM | 6–10:59 PM | — |
| `ads_planner.py` | 0–4 AM | 5–10 AM | 11 AM–1 PM | 2–4 PM | 5–7 PM | 8 PM+ |
| `bucketing_analysis.py` | — | 5–10:58 AM | 10:59–1:58 PM | 1:59–3:58 PM | 3:59–7:18 PM | 7:19 PM+ |

This means campaign slot tags written by one agent are misread by another.

#### Gap 6: Time Data Parsing for Slot Analysis
The `FINANCIAL_DETAILED` export has null `Order received local time` in many exports (confirmed in BICAN sample data). The slot analysis in `ads_planner.py` relies on this column. The fallback should be `SALES_BY_ORDER` which consistently has `Order placed time` (confirmed present in the BICAN data with 72,491 order rows). This fallback is not implemented in `ads_planner.py` or `deepdive/analyzer.py`.

#### Gap 7: Multiple Forked reporting_browser_use Directories
```
agents/reporting_browser_use/
agents/reporting_browser_use_browser/
agents/reporting_browser_use_copy1/
agents/reporting_browser_use_copy2/
agents/reporting_browser_use_copy3/
agents/reporting_browser_use_melt/
agents/reporting_browser_use_new/
agents/reporting_browser_use_savvy/
```
8 near-identical copies. This causes version divergence and maintenance overhead. Only `reporting_browser_use_browser` should exist as the canonical agent.

#### Gap 8: No Automated Onboarding Flow
The defined process is: restaurant adds TODC email as admin → TODC downloads data. There is no agent that:
- Detects new operator access
- Triggers the initial 90-day data pull
- Runs the first DeepDive automatically
- Sends an onboarding confirmation to the operator

#### Gap 9: `ingestion/pipeline.py` Is Disconnected from Real Data
Even if `doordash_client.py` were fixed, the ingestion schema only has `orders`, `revenue`, `ads`, `menu` — it doesn't map to the actual DoorDash export files (`FINANCIAL_DETAILED`, `MARKETING_PROMOTION`, `MARKETING_SPONSORED_LISTING`, `SALES_BY_TIME`, `SALES_BY_ORDER`, `PRODUCT_MIX`, `OPERATIONS_QUALITY`). The schema and client need to be redesigned to match the real export structure.

---

## Part 2: Data Analysis — BICAN Sample Findings

**Operator:** McDonald's South Bend (3 stores, Jan 2025 – Jun 2026, ~18 months)  
**Total orders analyzed:** 72,491  
**Total gross sales:** ~$1.47M  
**Net payouts:** ~$1.07M (avg payout ratio ~72.5%)  
**Avg AOV (all slots):** ~$20.26

### Slot-Level Findings (from SALES_BY_ORDER — 72,491 orders)

| Slot | Orders | Gross Sales | AOV | New Customers | Repeat Customers |
|------|--------|-------------|-----|---------------|------------------|
| Breakfast | 18,273 | $350,877 | $19.20 | 2,721 | 15,529 |
| Late Night | 13,556 | $273,332 | $20.16 | 2,753 | 10,774 |
| Lunch | 11,418 | $234,091 | $20.50 | 1,767 | 9,638 |
| Dinner | 10,350 | $224,496 | **$21.69** | 1,562 | 8,774 |
| Afternoon | 9,921 | $208,762 | $21.04 | 1,517 | 8,391 |
| Early Morning | 8,973 | $181,852 | $20.27 | **3,605** | 5,252 |

**Key Insights:**
1. **Breakfast = volume engine**: 25% of all orders, the primary retention slot (15,529 repeat customers). Defend this aggressively.
2. **Dinner = profitability slot**: Highest AOV at $21.69. Best slot for spend-threshold promotions to move customers up a basket bucket.
3. **Early Morning = new customer magnet**: 40% of Early Morning customers are new (3,605 / 8,973). This is your acquisition slot — target sponsored listings here.
4. **Late Night = underutilized**: 20% new customer rate, solid AOV. Strong weekend play.
5. **Weekend Early Morning dominates**: Saturday (3,230) and Sunday (3,297) have the highest Early Morning order counts. Weekend sponsored listings in Early Morning are high-priority.

### Bucketing Opportunity (from Context.MD GC buckets)
At an AOV of ~$20, most orders land in the GC $15–25 bucket. The slot-aware campaign strategy is:
- Dinner slot: push customers from GC $20–25 into GC $25–30 with a spend threshold promo ("Spend $25, get 15% off")
- Breakfast slot: volume play, no minimum, drive orders
- Early Morning: new customer acquisition — free delivery or flat discount to convert first-time orders

### Marketing Efficiency (from MARKETING data)
- 4,687 promotion rows, 1,602 sponsored listing rows in 18 months
- Marketing spend funded by restaurant: -$162,575 across the period
- ROAS tracked per campaign but not yet used to close the loop on next-period recommendations

---

## Part 3: Is the Current Process Correct?

### What's Correct
The overall flow logic is sound:
1. Onboarding → data download ✅ (concept is right, execution is stub)
2. DeepDive → insights ✅ (good foundation)
3. MarketingReco → plan ✅ (ads_planner is excellent, but disconnected)
4. Campaign Setup → browser execution ✅ (concept right, execution is stub)
5. Weekly Health Check → WoW analysis ✅ (this is the most complete agent)
6. Campaign Review → performance → next plan ✅ (solid pre/post logic)

### What Needs Correction

**Process Gap: The Slot-Level Thesis Is Right But Not Implemented End-to-End**

Your insight is correct: placing campaigns at the slot + day level (e.g., "Sunday Early Morning Sponsored Listing" vs "Friday Dinner Promo") is more precise and delivers better ROI than blanket campaigns. `ads_planner.py` already has this logic with DEFEND/GROW/HARVEST/SKIP tiers. The gap is that this output is not:
- Fed into `plan_generator.py`
- Executed via `campaign_setup`
- Tracked back via `campaign_review` with slot-level attribution

**Process Gap: Missing Feedback Loop**

The current process is linear: analyze → plan → execute → review. It doesn't close the loop:
- Campaign Review output should feed the next MarketingReco run as "campaign_history"
- The `run()` signature in `marketingreco/agent.py` accepts `campaign_history` but the parameter is thrown away: `_ = campaign_history`

**Process Gap: Health Check vs Campaign Review Are Separate**

Health Check runs weekly WoW analysis on overall restaurant performance. Campaign Review analyzes marketing campaign performance specifically. These should be unified: a restaurant's overall sales movement needs to be correlated with which campaigns were active during that period.

---

## Part 4: Optimization Recommendations

### Priority 1 — Close the Critical Stubs (Week 1–2)

#### 1a. Fix `doordash_client.py`
Replace the stub with a file-based loader that reads from the operator's data directory. The pattern already exists in `deepdive/data_loader.py`:

```python
# agents/ingestion/doordash_client.py
from agents.deepdive.data_loader import load_ssm_zips
from shared.config.settings import deepdive_default_zip_dir

def fetch_operator_window(operator_id: str, days: int) -> dict:
    data_dir = deepdive_default_zip_dir(operator_id)
    datasets = load_ssm_zips(data_dir)
    return {
        "financial_detailed": datasets.get("financial_detailed", pd.DataFrame()),
        "marketing_promotions": datasets.get("marketing_promotions", pd.DataFrame()),
        "marketing_sponsored": datasets.get("marketing_sponsored", pd.DataFrame()),
        "sales_by_order": datasets.get("sales_by_order", pd.DataFrame()),
        "sales_by_time": datasets.get("sales_by_time", pd.DataFrame()),
        "product_mix": datasets.get("product_mix", pd.DataFrame()),
        "operations_quality": datasets.get("operations_quality", pd.DataFrame()),
    }
```
Also update `IngestionData` schema to match the real export structure.

#### 1b. Wire `ads_planner.py` into `plan_generator.py`
The `ads_planner.build_ads_plan()` function already takes a CSV path and returns slot-level campaign recommendations. Connect it:

```python
# agents/marketingreco/plan_generator.py
from .ads_planner import build_ads_plan

def generate_plan(deepdive_report, *, budget_cap=None):
    # Use ads_planner for slot-level campaigns instead of hardcoded stubs
    financial_csv = _get_financial_csv_for_operator(deepdive_report.operator_id)
    if financial_csv:
        ads_plan = build_ads_plan(str(financial_csv))
        # Convert ads_plan slots → RecommendedCampaign list
        campaigns = _ads_plan_to_campaigns(ads_plan, deepdive_report)
    else:
        campaigns = _fallback_campaigns(deepdive_report)
    return MarketingPlan(...)
```

#### 1c. Connect `campaign_setup` to Real Browser Automation
`ads_flow.py` and `offers_flow.py` should call the real DoorDash browser automation from `reporting_browser_use_browser`. The browser agent already knows how to:
- Log into DoorDash Merchant Portal
- Navigate to Promotions / Sponsored Listings
- Create/configure campaigns

Wire this by importing and calling the browser agent from `campaign_setup`.

### Priority 2 — Standardize Slot Definitions (Week 1)

Create a single canonical source in `shared/config/constants.py`:

```python
# shared/config/constants.py — add canonical slot definitions
SLOT_DEFINITIONS = {
    "Early morning": (0, 5),    # 12:00 AM – 4:59 AM
    "Breakfast":     (5, 11),   # 5:00 AM – 10:59 AM
    "Lunch":         (11, 14),  # 11:00 AM – 1:59 PM
    "Afternoon":     (14, 17),  # 2:00 PM – 4:59 PM
    "Dinner":        (17, 21),  # 5:00 PM – 8:59 PM
    "Late night":    (21, 24),  # 9:00 PM – 11:59 PM
}

def assign_slot(hour: int) -> str:
    for slot_name, (start, end) in SLOT_DEFINITIONS.items():
        if start <= hour < end:
            return slot_name
    return "Unknown"
```
Replace all 4 slot mapping implementations with imports from this single location.

### Priority 3 — Fix Time Data Parsing for Slot Analysis (Week 2)

In `ads_planner.py`, add fallback to `SALES_BY_ORDER` when `Order received local time` is null in FINANCIAL_DETAILED:

```python
# In ads_planner.py _load_transactions()
def _load_transactions(csv_path):
    df = pd.read_csv(csv_path)
    df['hour'] = pd.to_datetime(df.get('Order received local time'), format='%H:%M:%S', errors='coerce').dt.hour
    
    # If most times are null, try SALES_BY_ORDER in same directory
    null_pct = df['hour'].isna().mean()
    if null_pct > 0.5:
        sales_by_order = _find_sales_by_order(csv_path)
        if sales_by_order:
            orders_df = pd.read_csv(sales_by_order)
            orders_df['hour'] = pd.to_datetime(orders_df['Order placed time'], format='%H:%M:%S', errors='coerce').dt.hour
            # Merge hour back via Order ID
            df = _merge_hours_from_orders(df, orders_df)
    return df
```

### Priority 4 — Implement the Full Slot-Campaign Loop (Week 3–4)

This is the core of your product differentiation. The complete slot-level campaign plan should:

**Step 1: Slot Performance Scoring**
For each store × day-of-week × slot:
- Volume score: orders as % of that store's total
- AOV score: AOV vs store average
- New customer rate: new / total customers
- Marketing efficiency: ROAS from prior campaigns in that slot

**Step 2: Tier Assignment**
Using the existing DEFEND/GROW/HARVEST/SKIP framework in `ads_planner.py`:
- DEFEND: top 30% of volume slots → Sponsored Listing, automatic bid, all customers
- GROW: 10–30% volume slots with new customer opportunity → Sponsored Listing, custom bid, new customers
- HARVEST: 3–10% slots where lapsed customer re-engagement makes sense → Promo with minimum spend
- SKIP: < 3% slots → no campaign spend

**Step 3: Campaign Parameters per Slot**
For each DEFEND/GROW slot:
```
Campaign Name: "{Store} - {DayOfWeek} {Slot} - {Tier}"
Example: "McD 493 - Sunday Early Morning - GROW"
Target: New Customers
Bid: 22% of slot AOV = $4.47 (Early Morning AOV $20.27 × 0.22)
Schedule: Sundays 12:00 AM – 4:59 AM
```

**Step 4: Campaign Creation via Browser**
Map each planned campaign to the DoorDash Sponsored Listings interface:
- Store selection
- Campaign name, start/end dates
- Target audience (new / lapsed / all)
- Daily budget
- Bid amount (for sponsored listings) or discount % (for promos)
- Day-of-week + time-of-day targeting (DoorDash supports this natively)

**Step 5: Slot-Level Review**
After 1–2 weeks live, pull marketing data and compare:
- Was the slot-level campaign more efficient than the prior blanket campaign?
- Which slots had ROAS > 5x (keep and increase budget)?
- Which slots had ROAS < 2x (pause or reduce bid)?

### Priority 5 — Close the Feedback Loop (Week 4–5)

**Campaign History → Next Reco**
In `marketingreco/agent.py`, `campaign_history` is accepted but ignored. Implement:

```python
def _adjust_plan_from_history(plan, campaign_history):
    """Reduce budget for campaigns with ROAS < threshold. Increase for ROAS > target."""
    for campaign in plan.recommended_campaigns:
        historical = campaign_history.get(campaign.campaign_name)
        if historical:
            roas = historical.get('roas', 0)
            if roas < 2.0:
                campaign.budget *= 0.5  # halve the budget
                campaign.rationale += f" [Budget halved: prior ROAS {roas:.1f}x]"
            elif roas > 6.0:
                campaign.budget *= 1.5  # increase budget
                campaign.rationale += f" [Budget increased: prior ROAS {roas:.1f}x]"
```

**Review → Reco Chain**
After `campaign_review` completes, trigger `marketingreco` with the review output as `campaign_history`. This closes the optimization loop without any manual intervention.

### Priority 6 — Add UberEats Ingestion (Week 5–6)

The UberEats data has `Order Accept Time` at column index 9 (hardcoded, confirmed in Context.MD). Add a UberEats loader to `ingestion/`:

```python
# agents/ingestion/ubereats_client.py
def load_ubereats_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, skiprows=[0], header=0)
    df.columns = df.columns.str.strip()
    # Time from column index 9
    time_col = df.columns[9]
    df['hour'] = pd.to_datetime(df[time_col], errors='coerce').dt.hour
    df['slot'] = df['hour'].apply(assign_slot)
    return df
```

Then update `ingestion/pipeline.py` to support `source == "ubereats"` and combine DD + UE slot analysis in the DeepDive output.

### Priority 7 — Consolidate reporting_browser_use (Week 1)

Delete the 7 duplicate directories. Keep `reporting_browser_use_browser` as the canonical agent, rename it to `reporting_browser_use`. Update all imports.

### Priority 8 — Build Automated Onboarding (Week 6–7)

Create `agents/onboarding/agent.py`:

```python
def run(operator_id: str, doordash_email: str, ubereats_email: str | None = None) -> dict:
    """
    1. Verify access (try downloading a 7-day report to confirm admin access)
    2. Download last 90 days of DD + UE data
    3. Run DeepDive analysis
    4. Generate initial slot-level campaign plan
    5. Send onboarding report to operator via Slack/email
    6. Register operator in Airtable with status = "onboarded"
    """
```

This turns the 4-step onboarding process into a single function call.

---

## Part 5: Proposed Architecture

```
RalphAI Pipeline (Optimized)
─────────────────────────────────────────────────────────────────────

ONBOARDING
  ├── Operator adds TODC email as admin (DD + UE portals)
  ├── onboarding/agent.py detects new access
  ├── Downloads last 90 days: DD (financial + marketing + sales) + UE
  └── Triggers: DeepDive → Slot Analysis → Campaign Plan → Review

WEEKLY LOOP (triggered every Mon morning)
  ├── health_check/agent.py
  │     ├── Downloads last 2 completed weeks per operator (Multilogin)
  │     ├── Builds WoW analysis (overall + by slot)
  │     └── Sends HTML/PDF report to operator + TODC Slack
  │
  ├── campaign_review/agent.py (runs alongside health check)
  │     ├── Pulls marketing data for active campaigns
  │     ├── Computes ROAS / CTR / AOV lift / new customer acquisition per slot
  │     └── Flags: Keep / Scale / Pause / Replace
  │
  └── marketingreco/agent.py (if Review flags changes needed)
        ├── Reads campaign_history from last review
        ├── Runs ads_planner.py slot-tier analysis on latest data
        ├── Produces updated campaign plan (slot-specific)
        └── → campaign_setup/agent.py (executes changes via browser)

SLOT-CAMPAIGN EXECUTION
  ├── campaign_setup/agent.py
  │     ├── For each slot-campaign in plan:
  │     │     ├── ads_flow.py → DoorDash Sponsored Listings (via browser-use)
  │     │     └── offers_flow.py → DoorDash Promos (via browser-use)
  │     └── Logs campaign IDs for review tracking

DATA LAYER
  ├── DD: FINANCIAL_DETAILED + MARKETING_PROMOTION + MARKETING_SPONSORED_LISTING
  │         + SALES_BY_ORDER (for time/slot) + SALES_BY_TIME + PRODUCT_MIX
  │         + OPERATIONS_QUALITY
  └── UE: order-level CSV (skiprows=1) + Marketing data
```

---

## Part 6: Slot-Level Campaign Strategy (Applied to BICAN Data)

Based on the 72,491 orders analyzed:

### Recommended Campaign Plan for McDonald's South Bend

**Store 493 (North Michigan) — High New Customer potential**

| Campaign | Type | Slot | Target | Bid/Discount |
|----------|------|------|--------|--------------|
| McD 493 - Weekend Early Morning - GROW | Sponsored | Sat+Sun 12–4:59 AM | New customers | $4.46 (~22% of $20.27 AOV) |
| McD 493 - Breakfast Daily - DEFEND | Sponsored | Mon–Fri 5–10:59 AM | All customers | Auto bid |
| McD 493 - Dinner Basket Builder | Promo | Daily 5–8:59 PM | All customers | $3 off $25+ spend |
| McD 493 - Late Night Weekend | Sponsored | Fri–Sat 9 PM–12 AM | Lapsed customers | $3.75 custom bid |

**Store 655825 (Western) — Volume-first approach**

| Campaign | Type | Slot | Target | Bid/Discount |
|----------|------|------|--------|--------------|
| McD Western - Saturday Breakfast - DEFEND | Sponsored | Sat 5–10:59 AM | All customers | Auto bid |
| McD Western - Lunch Lift | Promo | Mon–Fri 11 AM–1:59 PM | All customers | 10% off $20+ |

**Key rationale:**
- Early Morning weekend campaigns target the 3,605 new customers who order in that slot — highest new customer concentration in the data
- Dinner promos with spend thresholds push the 10,350 dinner orders (AOV $21.69) toward the $25–30 GC bucket
- Breakfast sponsored listings defend the 18,273-order volume base (highest volume slot)

---

## Part 7: Revenue Model Impact

**Current state:** $200/store/month. 3 McDonald's stores = $600/month for this operator.

**Growth path:**
- Each new operator referral adds $200/month
- At 50 stores (10–15 restaurant groups): $10K/month
- At 200 stores (40–50 restaurant groups): $40K/month

**The RalphAI leverage:** Automating the analysis-to-execution loop means each analyst can manage 50–100 operators instead of 5–10. The slot-level precision increases campaign ROI, which increases restaurant satisfaction, which drives referrals.

**Key metric to track:** Operator-reported sales lift after TODC campaign activation. Target: 15–25% sales increase in the first 90 days. This is the referral engine.

---

## Part 8: Immediate Action Items (Prioritized)

| # | Action | Agent/File | Effort | Impact |
|---|--------|-----------|--------|--------|
| 1 | Standardize slot definitions in `shared/config/constants.py` | All agents | 1 day | Fixes cross-agent slot mismatch |
| 2 | Fix `doordash_client.py` to load from real zip files | `ingestion/` | 1 day | Unblocks full pipeline |
| 3 | Wire `ads_planner.py` into `plan_generator.py` | `marketingreco/` | 2 days | Activates slot-level reco |
| 4 | Add SALES_BY_ORDER time fallback in `ads_planner.py` | `marketingreco/` | 1 day | Fixes null time issue |
| 5 | Delete 7 duplicate `reporting_browser_use_*` dirs | `agents/` | 0.5 days | Reduces maintenance debt |
| 6 | Connect `campaign_setup` to real browser automation | `campaign_setup/` | 3 days | Enables automated execution |
| 7 | Implement `campaign_history` in `marketingreco/agent.py` | `marketingreco/` | 1 day | Closes optimization loop |
| 8 | Add UberEats loader to `ingestion/` | `ingestion/` | 2 days | Completes dual-platform analysis |
| 9 | Build `onboarding/agent.py` | `agents/onboarding/` | 3 days | Automates new operator setup |
| 10 | Instrument slot-level metrics in `campaign_review` | `campaign_review/` | 2 days | Enables slot-specific ROAS tracking |

---

## Part 9: One Observation on Process

You have one of the most complete AI agent architectures I've seen for this use case. The business logic in `Context.MD` is thorough, the `ads_planner.py` tier logic is production-quality, and the health check WoW pipeline is real and working. The gap is a classic "last 20%" problem — the stubs and disconnected pipes mean the system never actually runs end-to-end.

The order of operations matters: fix the stubs first (doordash_client, ads_flow, offers_flow), then wire the existing intelligence (ads_planner → plan_generator → campaign_setup), then close the loop (campaign_review → campaign_history → next reco). Each step is days of work, not weeks, because the intelligence is already written — it just needs to be connected.

---

*End of RalphAI Assessment & Strategic Plan*
