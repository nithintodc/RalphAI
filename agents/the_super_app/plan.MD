# TheSuperApp - Implementation Plan

## Vision
The ultimate restaurant performance analytics SaaS app — a superset of ALL existing TODC apps (App2.0, App3.0, Ralph-Analyse, VB_Dashboard, Marketing-Breakdown). Client-side processing, zero server costs, instant analysis.

---

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | React 18 + Vite | Fast dev, modern, matches design files |
| Styling | TailwindCSS + CSS variables | Design system from `design/app3.0/styles.css` |
| State | Zustand | Lightweight, no boilerplate |
| CSV Parsing | PapaParse | Battle-tested, streaming, web workers |
| ZIP Handling | JSZip | Client-side unzip |
| Charts | Recharts | Composable React charts + custom SVG where needed |
| Routing | React Router v6 | SPA navigation |
| Date Utils | date-fns | Lightweight date manipulation |
| Export | SheetJS (xlsx) | Excel export |

---

## Architecture

```
src/
├── main.jsx                    # Entry point
├── App.jsx                     # Root: router + global state
├── stores/                     # Zustand stores
│   ├── dataStore.js            # Uploaded data, parsed DataFrames
│   ├── configStore.js          # Dates, excluded stores/dates, platform config
│   └── uiStore.js              # Active screen, theme, filters
├── lib/                        # Data processing (ported from App3.0 Python)
│   ├── parsers/
│   │   ├── zipHandler.js       # Unzip + file detection
│   │   ├── ddFinancial.js      # DD financial CSV parsing
│   │   ├── ddMarketing.js      # DD marketing CSV parsing
│   │   ├── ddSales.js          # DD sales CSV parsing
│   │   ├── ddOperations.js     # DD operations CSV parsing
│   │   ├── ddProductMix.js     # DD product mix CSV parsing
│   │   └── ueFinancial.js      # UE CSV parsing
│   ├── engine/
│   │   ├── aggregator.js       # Core: groupBy store, sum/nunique
│   │   ├── periodEngine.js     # 4-window logic (pre/post × current/LY)
│   │   ├── metrics.js          # Derived metrics (Growth%, YoY%, AOV, etc.)
│   │   ├── comparison.js       # Comparison engine (ported from comparison_engine.py)
│   │   ├── marketing.js        # Corp vs TODC analysis
│   │   ├── slots.js            # Slot/daypart analysis
│   │   ├── buckets.js          # Order bucketing by ticket size
│   │   ├── operations.js       # Operations quality metrics
│   │   └── diagnostics.js      # Decomposition, percentile, exceptions
│   └── utils/
│       ├── formatters.js       # USD, PCT, INT formatters
│       ├── safeMath.js         # safe_divide, inf handling
│       └── dateUtils.js        # Date parsing, period calculations
├── components/                 # Reusable UI (from design files)
│   ├── layout/
│   │   ├── Sidebar.jsx
│   │   ├── Topbar.jsx
│   │   └── Shell.jsx
│   ├── ui/
│   │   ├── KpiCard.jsx
│   │   ├── DeltaPill.jsx
│   │   ├── PeriodPill.jsx
│   │   ├── PlatformTabs.jsx
│   │   ├── DataTable.jsx
│   │   ├── Sparkline.jsx
│   │   └── FilterChip.jsx
│   └── charts/
│       ├── TrendChart.jsx
│       ├── BarChart.jsx
│       ├── DonutChart.jsx
│       ├── HeatmapChart.jsx
│       ├── WaterfallChart.jsx
│       └── ScatterChart.jsx
├── screens/
│   ├── upload/
│   │   ├── UploadScreen.jsx    # Screen 1: File upload wizard
│   │   └── FileCard.jsx        # Individual file upload card
│   ├── config/
│   │   ├── ConfigScreen.jsx    # Screen 2: Dates, exclusions
│   │   ├── DateRangePicker.jsx
│   │   ├── StoreExcluder.jsx
│   │   └── DateExcluder.jsx
│   ├── dashboard/
│   │   ├── OverviewScreen.jsx
│   │   ├── CompareScreen.jsx
│   │   ├── DiagnosticsScreen.jsx
│   │   ├── StoresScreen.jsx
│   │   ├── StoreDetailScreen.jsx
│   │   ├── SlotsScreen.jsx
│   │   ├── BucketsScreen.jsx
│   │   ├── MarketingScreen.jsx
│   │   ├── OperationsScreen.jsx    # NEW: from operations data
│   │   └── ProductMixScreen.jsx    # NEW: from product mix data
│   └── export/
│       └── ExportPanel.jsx
└── theme/
    ├── tokens.css              # Design tokens from styles.css
    └── tailwind.config.js
```

---

## Screen Flow

### Screen 1: Upload Wizard
```
┌─────────────────────────────────────────────────────┐
│  Ralph Analyse — Upload Your Data                   │
│                                                     │
│  ┌─── DoorDash (9 files) ──────────────────────┐   │
│  │                                              │   │
│  │  ☑ Financial    ☑ Marketing    ☐ Product Mix │   │
│  │  ☐ Sales×3      ☐ Ops-Order   ☐ Ops-Store   │   │
│  │  ☐ Ops-Time                                  │   │
│  │                                              │   │
│  │  Progress: ██████░░░░░░ 2/9                  │   │
│  │  You'll see: Financials ✓, Marketing ✓       │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─── UberEats (1 file) ──────────────────────┐    │
│  │  ☑ Financial Export (CSV)                   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ┌─── Available Analysis ──────────────────────┐   │
│  │  ✅ Financials   ✅ Marketing   ❌ Ops      │   │
│  │  ❌ Product Mix  ❌ Sales Views              │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│                              [ Continue → ]         │
└─────────────────────────────────────────────────────┘
```

**File detection logic** (by zip filename prefix):
| Prefix | Type | Enables |
|--------|------|---------|
| `financial_*` | DD Financial | Core metrics, Bucketing, Slots |
| `marketing_*` | DD Marketing | Corp vs TODC, ROAS, New Customers |
| `product_mix_*` | DD Product Mix | Product Mix screen |
| `sales_*` (by order) | DD Sales | Order-level analysis |
| `sales_*` (by time) | DD Sales | Time-based views |
| `sales_*` (by store) | DD Sales | Store-level sales |
| `OPERATIONS_*Order*` | DD Ops | Order quality metrics |
| `OPERATIONS_*Store*` | DD Ops | Store quality metrics |
| `OPERATIONS_*Time*` | DD Ops | Time-based ops quality |
| `*.csv` (UE format) | UE Financial | UE financial metrics |

### Screen 2: Configuration
```
┌──────────────────────────────────────────────────────┐
│  Configure Analysis Periods                          │
│                                                      │
│  ┌─ DoorDash ─────────────────────────────────────┐ │
│  │  Pre Period:  [01/01/2025] → [01/31/2025]      │ │
│  │  Post Period: [02/01/2025] → [02/28/2025]      │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ UberEats ─────────────────────────────────────┐ │
│  │  Pre Period:  [01/01/2025] → [01/31/2025]      │ │
│  │  Post Period: [02/01/2025] → [02/28/2025]      │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  [ ✓ Apply same dates to all platforms ]             │
│                                                      │
│  ┌─ Exclude Stores ──────────────────────────────┐  │
│  │  DD: [dropdown multiselect from detected IDs]  │  │
│  │  UE: [dropdown multiselect from detected IDs]  │  │
│  │  [ ✓ Apply same exclusions to all ]            │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌─ Exclude Dates ───────────────────────────────┐  │
│  │  DD: [date picker / comma-separated]           │  │
│  │  UE: [date picker / comma-separated]           │  │
│  │  [ ✓ Apply same to all ]                       │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│              [ ← Back ]  [ Analyze → ]               │
└──────────────────────────────────────────────────────┘
```

### Screen 3+: Dashboard (Sidebar Navigation)

**Nav Structure:**
```
Analyze
  ├── Overview          — Hero KPIs, trends, top movers
  ├── Pre vs Post       — Full comparison tables
  └── Diagnostics       — Decomposition, exceptions

Breakdowns
  ├── Stores            — Store-level drill-down
  ├── Slots & Heatmap   — Time-of-day analysis
  ├── Order Buckets     — Ticket size distribution
  ├── Marketing         — Corp vs TODC
  ├── Operations        — Quality metrics (NEW)
  └── Product Mix       — Item performance (NEW)
```

---

## Metrics Matrix (Superset)

| Metric | Source | Comparisons |
|--------|--------|-------------|
| Sales | DD Subtotal + UE Sales (excl. tax) | WoW, MoM, QoQ, YoY, PrePost, LY PrePost |
| Payouts | DD Net total + UE Total payout | Same |
| Orders | DD order ID nunique + UE Order ID nunique | Same |
| AOV | Sales / Orders | Same |
| Profitability % | Payouts / Sales × 100 | Same |
| Promo Spend | Customer discounts from marketing | Same |
| Ads Spend | Marketing fees | Same |
| Total Spend | Promo + Ads | Same |
| ROAS | Sales / Total Spend | Same |
| Cost per Order | Total Spend / Orders | Same |
| New Customers | DD: marketing promo, UE: platform total | Same |
| Corp Spend | DoorDash marketing credit + 3rd party | Post only |
| TODC Spend | Marketing fees + Customer discounts | Post only |
| Organic Orders | Orders with no marketing fees/discounts | Same |
| Promo Orders | Orders with customer discounts | Same |
| Ads Orders | Orders with marketing fees | Same |
| Promo+Ads Orders | Orders with both | Same |
| Order Buckets | $0-5, $6-10, ..., $46-50, $50+ | PrePost |
| Downtime % | Operations data | PrePost |
| Cancellation Rate | Operations data | PrePost |
| Missing/Incorrect % | Operations data | PrePost |

---

## Granularity Levels

| Dimension | Options |
|-----------|---------|
| Platform | Combined, DoorDash, UberEats |
| Store | All stores, individual store |
| Period | Pre, Post, LY Pre, LY Post |
| Time | Month, Week, Quarter, Date, Day |
| Slot | Overnight, Breakfast, Lunch, Afternoon, Dinner, Late Night |
| Bucket | $0-5 through $50+ (11 buckets) |

---

## Implementation Phases

### Phase 1: Project Setup + Upload Screen
1. Vite + React + Tailwind + dependencies
2. Design system (tokens, typography, colors from styles.css)
3. Zustand stores (data, config, UI)
4. Upload screen with file detection, progress, capability display
5. ZIP extraction + CSV parsing pipeline

### Phase 2: Configuration Screen
1. Date range pickers (Pre/Post for each platform)
2. Store exclusion multiselect (populated from parsed data)
3. Date exclusion picker
4. "Apply same to all" toggles
5. Auto-compute LY dates

### Phase 3: Core Data Engine
1. Port aggregator (groupBy + sum/nunique)
2. Port periodEngine (4-window logic)
3. Port metrics (Growth%, YoY%, safe_divide)
4. Port comparison engine
5. Port marketing analysis
6. Port slot analysis
7. Port bucketing analysis

### Phase 4: Dashboard Screens
1. Layout shell (Sidebar + Topbar from design files)
2. Overview screen (KPI cards, trends, movers)
3. Compare screen (Pre vs Post tables)
4. Stores screen (store-level drill-down)
5. Slots & Heatmap screen
6. Buckets screen
7. Marketing screen
8. Diagnostics screen
9. Operations screen (NEW)
10. Product Mix screen (NEW)

### Phase 5: Polish
1. Dark mode toggle
2. Excel export
3. Platform tab filtering
4. Responsive layout
5. Loading states + error handling

---

## Data Processing Pipeline (Client-Side)

```
User drops ZIP/CSV files
        │
        ▼
    JSZip.loadAsync()
        │
        ▼
    Detect file type by name prefix
        │
        ▼
    PapaParse.parse() each CSV
        │
        ▼
    Normalize columns (handle variations)
        │
        ▼
    Store in Zustand (raw DataFrames as arrays of objects)
        │
        ▼
    User configures dates/exclusions
        │
        ▼
    Filter by date range → 4 windows
        │
        ▼
    Filter excluded dates/stores
        │
        ▼
    Aggregate by Store ID (sum Sales/Payouts, nunique Orders)
        │
        ▼
    Compute derived metrics per store
        │
        ▼
    Build summary tables
        │
        ▼
    Render dashboard
```

---

## Key Files to Port from App3.0

| Python Source | JS Target | Lines | Priority |
|--------------|-----------|-------|----------|
| data_loading.py | parsers/*.js | 278 | P0 |
| data_processing.py | engine/periodEngine.js + aggregator.js | 819 | P0 |
| comparison_engine.py | engine/comparison.js | 384 | P0 |
| marketing_analysis.py | engine/marketing.js | 335 | P1 |
| slot_analysis.py | engine/slots.js | 399 | P1 |
| bucketing_analysis.py | engine/buckets.js | 353 | P1 |
| new_analysis_engine.py | engine/diagnostics.js | 810 | P2 |

---

## Design Tokens (from design/app3.0/styles.css)

```css
--accent: #059669 (Emerald)
--bg: #FAFAF9
--surface: #FFFFFF
--text: #0C0A09
--text-muted: #57534E
--positive: #059669
--negative: #DC2626
--dd-color: #EF4444 (DoorDash red)
--ue-color: #111827 (UberEats black)
--font: 'Geist', sans-serif
--font-mono: 'Geist Mono', monospace
--sidebar-width: 232px
--topbar-height: 56px
```
