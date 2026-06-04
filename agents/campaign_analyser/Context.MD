# Context.MD - Complete Business Logic Reference

> Extracted from App2.0-cloud-app, App2.0-cloud-app-savvy, and App3.0 (monthly_reporter/cloud_app).
> This document captures every calculation, rule, threshold, and data-handling pattern used across all three apps.

---

## Table of Contents

1. [Data Sources & Input Files](#1-data-sources--input-files)
2. [CSV Parsing Rules (DD vs UE)](#2-csv-parsing-rules-dd-vs-ue)
3. [Date Handling & Period Logic](#3-date-handling--period-logic)
4. [Excluded Dates](#4-excluded-dates)
5. [Store Mapping & Normalization](#5-store-mapping--normalization)
6. [Pre-Processing Pipeline](#6-pre-processing-pipeline)
7. [Core Metric Definitions](#7-core-metric-definitions)
8. [Derived Metric Formulas](#8-derived-metric-formulas)
9. [Null / NaN / Zero Handling](#9-null--nan--zero-handling)
10. [Division-by-Zero Patterns](#10-division-by-zero-patterns)
11. [Rounding Rules](#11-rounding-rules)
12. [Summary Table Calculations](#12-summary-table-calculations)
13. [New Customers - Special Handling](#13-new-customers---special-handling)
14. [Combined Table Logic (DD + UE)](#14-combined-table-logic-dd--ue)
15. [Marketing: Corporate vs TODC](#15-marketing-corporate-vs-todc)
16. [Slot Analysis](#16-slot-analysis)
17. [Bucketing Analysis](#17-bucketing-analysis)
18. [New Analysis Engine (Diagnostic View)](#18-new-analysis-engine-diagnostic-view)
19. [Financial Summary & Breakdown](#19-financial-summary--breakdown)
20. [Display Formatting Rules](#20-display-formatting-rules)
21. [Export Formatting Rules](#21-export-formatting-rules)
22. [Export Sheet Structure](#22-export-sheet-structure)
23. [Date Export Structure](#23-date-export-structure)
24. [Store Selection Logic](#24-store-selection-logic)
25. [KPI Dashboard Metrics](#25-kpi-dashboard-metrics)
26. [Insights Generation](#26-insights-generation)
27. [Cloud Pipeline (App3.0)](#27-cloud-pipeline-app30)
28. [Headless Runner (App3.0)](#28-headless-runner-app30)
29. [Data Flow Diagram](#29-data-flow-diagram)
30. [Known Bugs & Edge Cases](#30-known-bugs--edge-cases)
31. [Key Business Rules Summary](#31-key-business-rules-summary)
32. [Evolution Across App Versions](#32-evolution-across-app-versions)

---

## 1. Data Sources & Input Files

### 1.1 DoorDash (DD) Financial Data

| Item | Value |
|------|-------|
| File | `dd-data.csv` (master financial export) |
| Header | Row 1 (standard CSV) |
| Store ID Column | `Merchant store ID` (primary), fallback `Store ID` |
| Sales Column | `Subtotal` |
| Payouts Column | `Net total`, fallback `Net total (for historical reference only)` |
| Orders Column | `DoorDash order ID` (counted as NUNIQUE per store) |
| Date Column | Matched from variations list (see Section 2) |

### 1.2 UberEats (UE) Financial Data

| Item | Value |
|------|-------|
| File | `ue-data.csv` (master financial export) |
| Header | Row 2 — loaded with `skiprows=[0], header=0` (first row is a pre-header) |
| Store ID Column | `Store ID` or `Shop ID` (normalized — see Section 5) |
| Sales Column | `Sales (excl. tax)` |
| Payouts Column | `Total payout` |
| Orders Column | `Order ID` (counted as NUNIQUE per store) |
| Date Column | **Hardcoded to column index 8** (9th column) — no name matching |
| Time Column | **Hardcoded to column index 9** or fallback to column containing "accept" + "time" |

### 1.3 Marketing Files

#### DoorDash Marketing (Modern — from folders)
- **Promotion files**: `MARKETING_PROMOTION*.csv` in `marketing_*` subdirectories
  - Key columns: `Date`, `Store ID`/`Shop ID`, `New customers acquired`, `Orders`, `Sales`, `Customer discounts from marketing | (Funded by you)` → renamed to `Spend`, `Is self serve campaign`
- **Sponsored Listing files**: `MARKETING_SPONSORED_LISTING*.csv`
  - Key columns: `Date`, `Orders`, `Sales`, `Marketing fees | (including any applicable taxes)` → renamed to `Spend`, `Is self serve campaign`

#### Legacy Marketing Files (fallback when no marketing folder)
- `dd-mkt-pre-24.csv`, `dd-mkt-post-24.csv`, `dd-mkt-pre-25.csv`, `dd-mkt-post-25.csv`
- `ue-mkt-pre-24.csv`, `ue-mkt-post-24.csv`, `ue-mkt-pre-25.csv`, `ue-mkt-post-25.csv`

### 1.4 User Inputs

| Input | Format | Example |
|-------|--------|---------|
| Pre period | `MM/DD/YYYY-MM/DD/YYYY` (split on first `-`) | `01/01/2025-01/31/2025` |
| Post period | Same format | `02/01/2025-02/28/2025` |
| Excluded dates | Comma-separated `MM/DD/YYYY` | `01/15/2025,01/20/2025` |
| Operator name | String (prefix for export filenames) | `BrandXYZ` |

---

## 2. CSV Parsing Rules (DD vs UE)

### 2.1 DoorDash CSV

```
pd.read_csv(file_path)  # standard header on row 1
df.columns = df.columns.str.strip()  # strip whitespace from column names
```

**Date column detection** — matched case-insensitively from this priority list:
```python
DD_DATE_COLUMN_VARIATIONS = [
    'Timestamp local date', 'Timestamp Local Date', 'Timestamp Local date',
    'timestamp local date', 'Date', 'date', 'Timestamp', 'timestamp'
]
```
Process: exact match first, then case-insensitive fallback.

**Date parsing cascade**:
1. Try `%m/%d/%Y` (MM/DD/YYYY)
2. If all NaN → try `%Y-%m-%d`
3. If still all NaN → auto-parse via `pd.to_datetime(errors='coerce')`
4. Drop rows where date is NaN

### 2.2 UberEats CSV

```
pd.read_csv(file_path, skiprows=[0], header=0)  # skip pre-header row
df.columns = df.columns.str.strip()
```

**Date column**: hardcoded to column index 8 (no name matching).

**Date parsing cascade**:
1. Try `%m/%d/%Y` on all rows
2. For rows that failed (still NaT) → auto-parse those specific rows
3. Drop rows where date is NaN

**UE type detection**: checks if column name matches `UE_DATE_COLUMN_VARIATIONS`, or same object reference, or filename contains `ue`/`ubereats`.

### 2.3 File Auto-Detection

When no file is explicitly uploaded, files are matched by keyword in filename (case-insensitive):
- **DD**: `FINANCIAL`, `DD`, `DOORDASH`
- **UE**: `UE`, `UBEREATS`, `ORDER`

---

## 3. Date Handling & Period Logic

### 3.1 Four Time Windows

From two user inputs (Pre range, Post range), four windows are derived:

| Window | Definition |
|--------|-----------|
| `pre_25` | User-entered Pre range (current year) |
| `post_25` | User-entered Post range (current year) |
| `pre_24` | Pre range shifted back exactly 1 year |
| `post_24` | Post range shifted back exactly 1 year |

### 3.2 Last Year Calculation

```python
def get_last_year_dates(start_date, end_date):
    # Uses pd.DateOffset(years=1) which handles leap years correctly
    ly_start = pd.Timestamp(start_date) - pd.DateOffset(years=1)
    ly_end = pd.Timestamp(end_date) - pd.DateOffset(years=1)
    return (ly_start.strftime('%m/%d/%Y'), ly_end.strftime('%m/%d/%Y'))
```

### 3.3 Date Range Filtering

Inclusive on both ends:
```python
df[(df[date_col] >= start_date) & (df[date_col] <= end_date)]
```

---

## 4. Excluded Dates

- Converted to `date` objects (not datetime) — tries `MM/DD/YYYY` first, then auto-parse
- Applied **after** date-range filtering
- Comparison at date level using a temporary `_date_only` column:
  ```python
  df['_date_only'] = df[date_col].dt.date
  df = df[~df['_date_only'].isin(excluded_set)]
  df = df.drop(columns=['_date_only'])
  ```
- Applied to: financial files, marketing promotion files, marketing sponsored files
- **NOT applied** to UE legacy marketing files (explicit design decision)

---

## 5. Store Mapping & Normalization

### 5.1 Generic Store ID Normalization

```python
def normalize_store_id_column(df):
    if 'Store ID' in df.columns:
        return (df, 'Store ID')
    elif 'Shop ID' in df.columns:
        df = df.rename(columns={'Shop ID': 'Store ID'})
        return (df, 'Store ID')
    return (df, None)
```

### 5.2 DD Store ID Resolution

Primary store column: `Merchant store ID`
Fallback: `Store ID`

In App2.0-savvy, resolved by `get_dd_financial_store_id_column()`:
```python
# Checks in order: 'Store ID', 'Merchant Store ID', 'Merchant store ID'
```

After groupby aggregation, the grouped key is renamed to `Store ID` for downstream merge consistency.

### 5.3 UE Store ID Resolution (App2.0-savvy & App3.0)

Two-step process:

**Step 1 — `normalize_ue_store_key_column(df)`**:
- If `Shop ID` exists: drop existing `Store ID`, rename `Shop ID` → `Store ID`
- If only `Store ID` exists: use it

**Step 2 — `finalize_ue_canonical_store_id_column(df)`**:
- If `Store Name` is non-empty → use Store Name as canonical key
- Otherwise → use External Store ID (with float normalization: `200.0` → `200`)
- Rationale: UE chain-level Store ID repeats across storefronts; Store Name is unique per location

**Store Name detection** (`find_ue_store_name_column`):
```python
# Tries: 'Store Name', 'Restaurant Name', 'Restaurant name',
#         'Merchant Name', 'Store name',
#         or any column with "store" + "name" (case-insensitive)
```

### 5.4 Store ID Type Coercion

All Store IDs are cast to `str` before merging:
```python
df['Store ID'] = df['Store ID'].astype(str)
```

---

## 6. Pre-Processing Pipeline

### 6.1 Column Cleaning
```python
df.columns = df.columns.str.strip()
```

### 6.2 Numeric Coercion
```python
pd.to_numeric(df[col], errors='coerce')  # non-numeric → NaN
```
Applied to: Sales, Payouts, and all financial columns.

### 6.3 Row Dropping
- Rows with NaN Store ID → **dropped** (`df.dropna(subset=[store_col])`)
- Rows with NaN date → **dropped** (`df.dropna(subset=[date_col])`)

### 6.4 Marketing-Specific
- After coercion: `.fillna(0)` applied to Orders, Sales, Spend columns
- New Customers: `pd.to_numeric(errors='coerce')`, then `dropna(subset=[store_col, new_customers_col])`

### 6.5 Aggregation per Window

**DoorDash**:
```python
df.groupby(store_col).agg({
    'Subtotal': 'sum',         # → Sales
    'Net total': 'sum',        # → Payouts
    'DoorDash order ID': 'nunique'  # → Orders (distinct count)
}).rename(columns={...})
```

**UberEats**:
```python
df.groupby('Store ID').agg({
    'Sales (excl. tax)': 'sum',  # → Sales
    'Total payout': 'sum',      # → Payouts
    'Order ID': 'nunique'       # → Orders (distinct count)
}).rename(columns={...})
```

---

## 7. Core Metric Definitions

### 7.1 Source Column Mapping

| Metric | DD Source Column | UE Source Column | Aggregation |
|--------|-----------------|------------------|-------------|
| Sales | `Subtotal` | `Sales (excl. tax)` | SUM by Store ID |
| Payouts | `Net total` (fallback: `Net total (for historical reference only)`) | `Total payout` | SUM by Store ID |
| Orders | `DoorDash order ID` | `Order ID` | **NUNIQUE** (distinct count) by Store ID |
| New Customers | `New customers acquired` (marketing promotion files) | `New customers` (legacy files) | SUM by Store ID (DD) / Platform total (UE) |

### 7.2 DD Payout Column Selection

For 2024 (last year) data: explicitly uses `Net total (for historical reference only)`
For 2025 (current year) data: uses `Net total`
If expected column is missing, tries the alternate name.

---

## 8. Derived Metric Formulas

### 8.1 Store-Level Derived Metrics

Applied identically to Sales, Payouts, Orders, and New Customers per store:

| Metric | Formula |
|--------|---------|
| `PrevsPost` | `post_25 - pre_25` |
| `LastYear_Pre_vs_Post` | `post_24 - pre_24` |
| `YoY` | `post_25 - post_24` |
| `Growth%` | `(PrevsPost / pre_25.replace(0, 1)) * 100` |
| `YoY%` | `(YoY / post_24.replace(0, 1)) * 100` |

After Growth%/YoY% calculation:
```python
.replace([float('inf'), float('-inf')], 0).fillna(0)
```

### 8.2 Summary-Level Derived Metrics

**Profitability** (Payouts as % of Sales):
```
profitability = (payouts / sales) * 100    # 0 if sales == 0
PrevsPost     = profitability_post - profitability_pre
Growth%       = (PrevsPost / profitability_pre) * 100  # 0 if pre == 0
YoY           = profitability_post - profitability_LY_post
YoY%          = (YoY / profitability_LY_post) * 100    # 0 if LY_post == 0
```

**Average Check / AOV** (Sales / Orders):
```
aov       = sales / orders    # 0 if orders == 0
PrevsPost = aov_post - aov_pre
Growth%   = (PrevsPost / aov_pre) * 100    # 0 if aov_pre == 0
YoY       = aov_post - aov_LY_post
YoY%      = (YoY / aov_LY_post) * 100     # 0 if LY_post == 0
```

**Summary Growth%/YoY%** are recalculated from aggregated totals (not averaged from stores):
```
Growth% = (sum(PrevsPost) / sum(pre_25)) * 100    # if sum(pre_25) != 0
YoY%    = (sum(YoY) / sum(post_24)) * 100         # if sum(post_24) != 0
```

---

## 9. Null / NaN / Zero Handling

| Context | Rule |
|---------|------|
| After outer merge of 4 windows | `result.fillna(0)` — missing stores in any period get 0 |
| Numeric coercion | `pd.to_numeric(errors='coerce').fillna(0)` |
| Empty DataFrames | Created with explicit column names when source data is missing |
| Store ID is NaN | Row dropped (`dropna(subset=[store_col])`) |
| Date is NaN | Row dropped (`dropna(subset=[date_col])`) |
| Marketing NaN | `.fillna(0)` on numeric columns after conversion |
| Infinity values | `.replace([float('inf'), float('-inf')], 0)` in Growth%/YoY% |
| Display filtering | Rows with empty Store ID AND both Pre/Post == 0 are removed |

---

## 10. Division-by-Zero Patterns

Three distinct patterns are used across the codebase:

### Pattern 1: Replace-with-1 (Store-Level)
```python
growth_pct = (delta / denominator.replace(0, 1)) * 100
```
**Behavior**: When denominator is 0, it becomes 1, so result = numerator * 100.
Example: pre=0, post=500 → Growth% = (500/1)*100 = 50000% (not 0%).
Then `.replace([inf, -inf], 0).fillna(0)` catches actual infinities.

### Pattern 2: Explicit Guard (Summary-Level)
```python
value = (numerator / denominator * 100) if denominator != 0 else 0
```
**Behavior**: Returns exactly 0 when denominator is 0. Used in `create_summary_tables`.

### Pattern 3: Safe Divide (New Analysis Engine)
```python
def safe_divide(numerator, denominator):
    denom = denominator.replace(0, pd.NA)
    result = numerator / denom
    return result.replace([float('inf'), float('-inf')], 0).fillna(0)
```
**Behavior**: Returns 0 for all zero-denominator cases. Cleanest approach.

> **INCONSISTENCY WARNING**: Pattern 1 and Pattern 2 produce different results for the same edge case. Pattern 1 (store-level) can produce very large percentages when the base period is 0; Pattern 2 (summary-level) returns 0.

---

## 11. Rounding Rules

### 11.1 Store-Level Data
All numeric columns rounded to **1 decimal place**: `round(1)`
Columns: `pre_24, post_24, pre_25, post_25, PrevsPost, LastYear_Pre_vs_Post, YoY, Growth%, YoY%`

### 11.2 Summary Tables
All summary values rounded to **1 decimal place**: `round(value, 1)`

### 11.3 Financial Summary / Breakdown
- Dollar values: **2 decimal places** (`round(val, 2)`)
- Percentages: **1 decimal place** (`round(val, 1)`)

### 11.4 Bucketing Analysis
- `Profitability_%`: **1 decimal place** via `np.round(..., 1)`
- `AOV`: **1 decimal place** via `np.round(..., 1)`

### 11.5 Date Export
- `Avg-Value` column: **1 decimal place** (`round(..., 1)`)

---

## 12. Summary Table Calculations

### 12.1 Summary Table Structure

**Table 1 (Pre vs Post)**: columns = `Metric, Pre, Post, PrevsPost, LastYear Pre vs Post, Growth%`
**Table 2 (YoY)**: columns = `Metric, last year-post, post, YoY, YoY%`

### 12.2 Metric Rows

| Platform | Metrics |
|----------|---------|
| DoorDash | Sales, Payouts, Orders, New Customers, Profitability, Average Check |
| UberEats | Sales, Payouts, Orders, Profitability, Average Check *(no New Customers)* |
| Combined | Sales, Payouts, Orders, New Customers, Profitability, Average Check |

### 12.3 Aggregation Rule

Summary values are summed from **selected stores only** (except DD New Customers — see Section 13).

Profitability and Average Check are computed from the aggregated sums (not averaged from per-store values):
```
Combined Profitability = (Total Payouts / Total Sales) * 100
Combined AOV           = Total Sales / Total Orders
```

---

## 13. New Customers - Special Handling

### 13.1 DoorDash New Customers

- **Source**: `MARKETING_PROMOTION*.csv` in `marketing_*` subdirectories
- **Column**: case-insensitive match for `new customers acquired`
- **Aggregation**: SUM by Store ID per date window
- **Date filtering**: same as main data (with excluded dates applied)
- **CRITICAL RULE**: In summary tables, DD new customers are summed across **ALL stores from marketing files**, NOT filtered by selected stores. Rationale: marketing Store IDs may not match financial Store IDs.

### 13.2 UberEats New Customers

- **Source**: legacy `ue-mkt-*.csv` files
- **Column**: `New customers`
- **NO date filtering** applied to UE marketing files
- Returns **platform-level totals** (single number per window), NOT store-level
- Stored in `st.session_state['ue_new_customers_totals']` as dict:
  ```python
  {'pre_24': X, 'post_24': X, 'pre_25': X, 'post_25': X}
  ```
- `process_new_customers_data()` returns empty DataFrame for UE (`is_ue=True`)
- No Growth%/YoY% computed at store level for new customers (computed at summary level only)

### 13.3 Combined New Customers

```
Combined = DD (all stores, unfiltered) + UE (platform totals from session state)
```

---

## 14. Combined Table Logic (DD + UE)

### 14.1 Combined Store Tables

**Merge strategy**:
```python
pd.merge(dd, ue, on='Store ID', how='outer', suffixes=('_dd', '_ue'))
```

**Numeric columns summed**: `Pre, Post, PrevsPost, LastYear Pre vs Post` (Table 1) and `last year-post, post, YoY` (Table 2).
- For stores in both platforms: values are added
- For stores in only one platform: `fillna(0)` for the missing platform

**Growth%/YoY% recalculated**:
```python
Growth% = (PrevsPost / Pre * 100).replace([inf, -inf], 0).fillna(0).round(1)
YoY%    = (YoY / last_year_post * 100).replace([inf, -inf], 0).fillna(0).round(1)
```

**Row filtering**: Rows where Store ID is NaN/empty AND both Pre/Post are 0 are removed.

**Store Name coalescing** (App2.0-savvy/App3.0): UE name preferred, then DD name.

### 14.2 Combined Summary Tables

- Simply adds DD + UE raw values for Sales, Payouts, Orders
- Growth%/YoY% recalculated from combined sums (NOT averaged from platforms)
- Profitability and Average Check are recalculated from combined totals

---

## 15. Marketing: Corporate vs TODC

### 15.1 Key Rule

Uses **ONLY the Post period** date range. Pre period is NOT used.

### 15.2 Grouping

Pivot on `Is self serve campaign` column:
- `False` → **Corporate**
- `True` → **TODC**

### 15.3 Metrics per Group

| Metric | Source |
|--------|--------|
| Orders | `Orders` column |
| Sales | `Sales` column |
| Spend | Promotion: `Customer discounts from marketing \| (Funded by you)`, Sponsored: `Marketing fees \| (including any applicable taxes)` |
| ROAS | `Sales / Spend` (0 if Spend == 0) |
| Cost per Order | `Spend / Orders` (0 if Orders == 0) |

### 15.4 Combined Marketing Table

Sums Orders, Sales, Spend from both Promotion and Sponsored for each group, then recalculates ROAS and Cost per Order from the summed values (not averaged).

---

## 16. Slot Analysis

### 16.1 DD Slot Definitions (slot_analysis.py)

| Slot | Minutes Since Midnight | Approximate Time |
|------|----------------------|------------------|
| Overnight | 0 – 299 | 12:00 AM – 4:59 AM |
| Breakfast | 300 – 658 | 5:00 AM – 10:58 AM |
| Lunch | 659 – 838 | 10:59 AM – 1:58 PM |
| Afternoon | 839 – 958 | 1:59 PM – 3:58 PM |
| Dinner | 959 – 1158 | 3:59 PM – 7:18 PM |
| Late night | 1159+ | 7:19 PM – 11:59 PM |

**DD time column**: `Timestamp local time` (variations: `Timestamp Local Time`, `timestamp local time`, `Order received local time`, `Order Received Local Time`)

### 16.2 UE Slot Definitions (slot_analysis.py)

| Slot | Minutes Since Midnight | Approximate Time |
|------|----------------------|------------------|
| Overnight | 0 – 299 | 12:00 AM – 4:59 AM |
| Breakfast | 300 – 659 | 5:00 AM – 10:59 AM |
| Lunch | 660 – 839 | 11:00 AM – 1:59 PM |
| Afternoon | 840 – 1019 | 2:00 PM – 4:59 PM |
| Dinner | 1020 – 1199 | 5:00 PM – 7:59 PM |
| Late night | 1200+ | 8:00 PM – 11:59 PM |

**UE time column**: column index 9, or column containing "accept" + "time" (case-insensitive)

### 16.3 New Analysis Engine Slots (new_analysis_engine.py)

| Slot | Hour Range |
|------|-----------|
| Breakfast | 5 – 10 (5:00 AM – 10:59 AM) |
| Lunch | 11 – 14 (11:00 AM – 2:59 PM) |
| Afternoon | 15 – 17 (3:00 PM – 5:59 PM) |
| Dinner | 18 – 22 (6:00 PM – 10:59 PM) |
| Late Night | 0–4 or 23 (11:00 PM – 4:59 AM) |
| Unknown | -1 (failed parse) |

### 16.4 Bucketing Analysis Day Parts (bucketing_analysis.py)

| Day Part | Hour Range |
|----------|-----------|
| Early morning | 00:00 – 05:59 |
| Breakfast | 06:00 – 10:59 |
| Lunch | 11:00 – 14:59 |
| Afternoon | 15:00 – 16:59 |
| Dinner | 17:00 – 21:59 |
| Late night | 22:00 – 23:59 |

> **WARNING**: There are 4 different slot/day-part systems across the codebase with inconsistent boundaries. The new app must standardize on ONE system.

### 16.5 Slot Analysis Outputs

4 tables per platform:
1. **Sales Pre vs Post**: `Slot, Pre, Post, Pre vs Post, Growth%`
2. **Sales YoY**: `Slot, Last year post, Post, YoY, Growth%`
3. **Payouts Pre vs Post**: same structure
4. **Payouts YoY**: same structure

Growth% in slot tables: formatted as string `f"{((post - pre) / pre * 100):.1f}%"`, returns `"0.0%"` when denominator is 0.

---

## 17. Bucketing Analysis

### 17.1 Transaction Type Filter

Only rows where `Transaction type == "Order"` are included (filters out adjustments, refunds, etc.).

### 17.2 Order-Level Aggregation

Groups by (`Merchant Store ID`, `DoorDash order ID`) summing: Subtotal, Net total, Marketing fees, Customer discounts.

### 17.3 Guest Count (GC) Buckets

| Bucket Label | Subtotal Range |
|-------------|---------------|
| GC $0-15 | $0.00 – $14.99 |
| GC $15-20 | $15.00 – $19.99 |
| GC $20-25 | $20.00 – $24.99 |
| GC $25-30 | $25.00 – $29.99 |
| GC $30-$35 | $30.00 – $34.99 |
| GC $35-$40 | $35.00 – $39.99 |
| GC $40+ | $40.00+ |

Negative subtotals → `None` (excluded from bucketing).

### 17.4 New Analysis Engine GC Buckets (DIFFERENT)

| Bucket Label | Subtotal Range |
|-------------|---------------|
| Under $15 | < $15 |
| $15-$25 | $15 – $24.99 |
| $25-$40 | $25 – $39.99 |
| $40-$60 | $40 – $59.99 |
| $60+ | $60+ |

> **NOTE**: The two GC bucket systems have different granularity. Bucketing analysis uses 7 fine-grained buckets; new analysis engine uses 5 broader buckets.

### 17.5 Marketing-Driven Order

An order is considered marketing-driven when either:
- `Marketing fees` is non-zero, OR
- `Customer discounts (funded by you)` is non-zero

### 17.6 Aggregation Dimensions

Groups by: `Merchant Store ID, Operator, Month, Week, Date, Day, Day part`

**Week label format**: `DD/MM - DD/MM` (Monday to Sunday of the week)

### 17.7 Bucketing Output Columns

```
Merchant Store ID, Operator, Month, Week, Date, Day, Day part,
Sales, Payouts, Mkt Spend, Customer Discounts, Orders,
GC $0-15, GC $15-20, GC $20-25, GC $25-30, GC $30-$35, GC $35-$40, GC $40+,
Count of Orders Mktg Driven, Profitability_%, AOV
```

---

## 18. New Analysis Engine (Diagnostic View)

### 18.1 Additive Metrics

`Sales, Payouts, Orders, Spends, Corp Spend, TODC Spend`

### 18.2 Derived Metrics

| Metric | Formula |
|--------|---------|
| AOV | `Sales / Orders` (safe_divide) |
| ROAS | `Sales / Spends` (safe_divide) |
| Payout Margin % | `(Payouts / Sales) * 100` |
| Cost per Order | `Spend / Orders` |

### 18.3 Marketing Spend Decomposition (DD only)

| Component | Source Columns |
|-----------|---------------|
| TODC Spend | `Marketing fees` + `Customer discounts (funded by you)` |
| Corp Spend | `DoorDash marketing credit` + `Third-party contribution` |
| Total Spends | TODC Spend + Corp Spend |

### 18.4 Marketing-to-Slot Allocation

Daily marketing spend is distributed across time slots based on sales mix weight:

```python
allocation_weight = Slot_Sales / Day_Sales  # per store-day
# Fallback if Day_Sales == 0: Slot_Orders / Day_Orders
# Fallback if both 0: uniform = 1 / number_of_slots_that_day
```

### 18.5 Sales Change Decomposition

```
orders_effect = (post_orders - pre_orders) * pre_aov
aov_effect    = (post_aov - pre_aov) * post_orders
```

### 18.6 Payout Change Decomposition

```
sales_effect  = (post_sales - pre_sales) * pre_margin
margin_effect = (post_margin - pre_margin) * post_sales
```

### 18.7 Metric Bridge

```
Delta          = Post - Pre
Growth%        = (Delta / Pre) * 100
Contribution%  = (Entity_Delta / Total_Delta) * 100
```

### 18.8 Percentile Ranking

```python
rank(pct=True, method='average') * 100
```
Applied on post-period values for each metric.

### 18.9 Exception Detection

Flags contradictory patterns:
- Sales down + Spend up
- Sales up + Payouts down
- Orders up + AOV down
- ROAS down + Spend up

### 18.10 Campaign Performance

Aggregated by `Campaign ID` + `Campaign Name` + `Source` (Promotion/Sponsored Listing):
- ROAS and Cost per Order recalculated from aggregated sums (not averaged)

---

## 19. Financial Summary & Breakdown

### 19.1 Financial Summary Metrics

| Metric | DD Source Column | UE Source Column |
|--------|-----------------|------------------|
| Sales | DD Subtotal + UE Sales (excl. tax) | — |
| DD Sales | `Subtotal` | — |
| DD Commission | `abs(Commission)` | — |
| DD Ads Spend | `abs(Marketing fees)` | — |
| DD Promo Spend | `abs(Customer discounts from marketing)` | — |
| DD Error Charges | `abs(Error charges)` | — |
| DD Adjustments | `abs(Adjustments)` | — |
| DD Payouts | `Net total` | — |
| DD Profitability% | `(DD Payouts / DD Sales) * 100` | — |
| UE Sales | — | `Sales (excl. tax)` |
| UE Error Charges | — | `Order Error Adjustments` |
| UE Promo | — | `Offers on items` |
| UE Commissions | — | `abs(Marketplace Fee)` |
| UE Payouts | — | `Total payout` |
| UE Profitability% | — | `(UE Payouts / UE Sales) * 100` |

> **Note**: DD Commission, Ads, Promo, Errors, Adjustments, and UE Commissions use `abs()` to present as positive values.

### 19.2 Financial Summary Derived Columns

| Column | Formula |
|--------|---------|
| Pre vs Post | Post - Pre |
| Linear Growth% | `(Pre vs Post / Pre) * 100` |
| LY Pre vs Post | LY Post - LY Pre |
| LY Linear % | `(LY Pre vs Post / LY Pre) * 100` |
| YoY | Post - LY Post |
| YoY% | `(YoY / LY Post) * 100` |

### 19.3 DD Financial Breakdown (Per-Store)

- Auto-discovers all financial columns starting from "Subtotal" onwards
- Skips known non-financial columns (Store ID, Order ID, Date, etc.)
- For each financial line item per store:
  - Value = SUM of that column
  - `%` = Value / Subtotal (0 when Subtotal == 0)
- Post-Pre diff computed as percentage-point change

---

## 20. Display Formatting Rules

### 20.1 UI Components (Streamlit)

| Data Type | Format | Example |
|-----------|--------|---------|
| Dollar values (Sales, Payouts) | `f"${x:,.1f}"` | $1,234.5 |
| Percentages (Growth%, YoY%) | `f"{x:.1f}%"` | 12.3% |
| Orders / New Customers | `f"{int(round(x)):,}"` | 1,234 |
| Profitability | `f"{x:.1f}%"` | 65.2% |
| Average Check | `f"${x:,.1f}"` | $25.3 |

### 20.2 Column Display Renames

**Table 1 (Pre vs Post)**:

| Internal Name | Display Name |
|--------------|--------------|
| pre_25 | Pre |
| post_25 | Post |
| PrevsPost | PrevsPost |
| LastYear_Pre_vs_Post | LastYear Pre vs Post |
| Growth% | Growth% |

**Table 2 (YoY)**:

| Internal Name | Display Name |
|--------------|--------------|
| post_24 | last year-post |
| post_25 | post |
| YoY | YoY |
| YoY% | YoY% |

---

## 21. Export Formatting Rules

### 21.1 Excel Export Formatting

| Context | Format |
|---------|--------|
| Sales, Spend, Cost per Order (marketing) | `f"${value:,.2f}"` (2 decimals) |
| ROAS | `f"{value:.2f}"` (2 decimals, no $) |
| Orders column | `f"{int(round(value)):,}"` |
| Growth% / YoY% | `f"{value:.1f}%"` |
| Default dollar values (store tables) | `f"${value:,.1f}"` (1 decimal) |
| Average Check | `f"${value:,.1f}"` |
| Profitability | `f"{value:.1f}%"` |
| Financial summary values | `#,##0.00` number format |
| Financial summary percentages | `0.0` number format |
| Slot dollar values | `f"${value:,.2f}"` |

> **NOTE**: Export uses 2 decimals for marketing/financial values, while UI display uses 1 decimal. This is intentional.

---

## 22. Export Sheet Structure

### 22.1 Full Report Export

| Sheet | Contents |
|-------|----------|
| Summary Tables | Summary Metrics table (col 1) + Merchant Store IDs/Markups table (col 8, 5-col gap) |
| Store-Level Tables | Combined Store T1/T2, DD Store T1/T2, UE Store T1/T2 |
| Corporate vs TODC | Combined, Promotion, Sponsored Listing tables |
| DD-slotWise | 4 slot analysis tables |
| UE-slotWise | 4 slot analysis tables |
| DD Financial-Aggregate | Unified financial summary (App2.0-savvy/App3.0) |
| DD Financial Breakdown | Per-store financial detail (App2.0-savvy/App3.0) |
| Insights | Platform, Store, Slot, Date insights |

**Filename**: `{operator_name}_analysis_export_{timestamp}.xlsx` or `analysis_export_{timestamp}.xlsx`
**Upload destination**: Google Drive → `cloud-app-uploads/outputs`

### 22.2 Bucketing Export (App2.0-savvy/App3.0)

| Sheet | Contents |
|-------|----------|
| By Period | Bucketed data by period |
| By Slot-Period | Bucketed by slot and period |
| By Day | Daily bucketed data |
| Slot Pre vs Post | Slot comparison tables |
| Slot YoY | Slot year-over-year tables |
| Day-Slot Pre vs Post | Day x Slot comparison |
| Day-Slot YoY | Day x Slot YoY |
| Daypart GC | 2x2 layout (Post/Pre on top, Delta/Delta% below) |
| Store Daypart GC | Same layout with store sub-rows |

---

## 23. Date Export Structure

### 23.1 Sheets

`DD_25_Sales`, `DD_25_Payouts`, `DD_25_Orders`, `UE_25_Sales`, `UE_25_Payouts`, `UE_25_Orders`

### 23.2 Layout per Sheet

Four side-by-side blocks with 1-column gap between each:

```
| Pre 25 block | gap | Post 25 block | gap | Pre 24 block | gap | Post 24 block |
```

### 23.3 Each Block Structure

- Pivot table: Date as index (rows), Store ID as columns
- Date format: `YYYY-MM-DD` (`strftime('%Y-%m-%d')`)
- **Total column**: row sum of all store columns
- **Avg-Value column**: `daily_average - row_total` where `daily_average = grand_total / num_days`
- **Total row**: column sum across all dates
- Corner cell (Total row × Total column) = grand total

### 23.4 Upload

Google Drive → `cloud-app-uploads/date-exports`

---

## 24. Store Selection Logic

- **Default**: All stores selected (`sorted(df['Store ID'].unique().tolist())`)
- **Session state keys**: `selected_stores_DoorDash`, `selected_stores_UberEats`
- **Filtering**: `df[df['Store ID'].isin(selected_stores)]`
- **Critical rule**: Store selection filters Sales, Payouts, Orders at summary/store level. **DD New Customers are intentionally NOT filtered** by store selection (see Section 13).

---

## 25. KPI Dashboard Metrics

Five top-level KPIs displayed:

| KPI | Source |
|-----|--------|
| Sales Growth (Pre→Post) | `combined_summary1['Sales']['Growth%']` |
| Sales Growth (YoY) | `combined_summary2['Sales']['YoY%']` |
| Order Growth | `combined_summary1['Orders']['Growth%']` |
| New Customer Growth | `combined_summary1['New Customers']['Growth%']` |
| Payout Lift / Store | `combined_summary1['Payouts']['PrevsPost'] / count(selected_DD_stores)` |

### Summary Metrics Table (exported)

| Row | Value |
|-----|-------|
| Active Stores | `"DoorDash: {dd_count} \| UberEats: {ue_count}"` |
| Pre Period | Date string |
| Post Period | Date string |
| Sales Growth (Pre→Post) | % value |
| Sales Growth (YoY) | % value |
| Order Growth | % value |
| New Customer Growth | % value |
| Payout Lift per Store | $ value |
| Average Markup | *(placeholder — empty string)* |
| Pre TODC Growth YoY | *(placeholder — empty string)* |

### Merchant Store IDs / Markups Table (export only)

- Deduped list of all selected DD + UE store IDs
- Markups column: all empty strings (placeholder for manual entry)

---

## 26. Insights Generation

### 26.1 Platform Insights
Pre vs Post change and percentage for each metric from combined summary.

### 26.2 Store Insights
Top 3 worst and top 3 best stores by Growth% for each platform.

### 26.3 Date Insights
Daily sales in Post period, top/bottom 5 dates by sales.
Sale column detection: searches for columns with `subtotal`, `order value`, or `sales` (excluding `tax`), then `amount` or `total`.

### 26.4 Slot Insights
Pre vs Post change per slot from DD sales slot table.

---

## 27. Cloud Pipeline (App3.0)

### 27.1 Infrastructure

- Config from env vars: `GCP_PROJECT_ID`, `GCP_REGION`, `GCS_UPLOAD_BUCKET`, `CLOUD_RUN_ANALYSIS_JOB`, `ANALYSIS_OUTPUT_PREFIX`
- Files uploaded to GCS path: `uploads/{job_id}/{logical_name}/{filename}`
- Triggers Cloud Run Job with env var overrides for all input URIs and date parameters
- Job ID format: `{prefix}-{YYYYMMDD-HHMMSS}-{8-char-uuid}`

### 27.2 Cloud Job Runner

- Downloads DD/UE/marketing files from GCS to temp directory
- Runs: `create_date_export_from_master_files`, `create_bucketing_export`, `build_financial_summary_table`
- Uploads results back to GCS under `{output_prefix}/`
- Writes `status.json` with job metadata, artifact URIs, and success/failure status

---

## 28. Headless Runner (App3.0)

### 28.1 Purpose

`ralph_runner.py` enables API/programmatic execution without Streamlit UI.

### 28.2 Interface

```python
generate_monthly_report_bundle(inputs: ReportInputs) -> dict
# Returns: excel_bytes, filename, summary_text, tables (JSON), date_export_bytes, date_export_filename
```

### 28.3 Input

```python
@dataclass
class ReportInputs:
    pre_range: str           # "MM/DD/YYYY-MM/DD/YYYY"
    post_range: str          # "MM/DD/YYYY-MM/DD/YYYY"
    excluded_dates_text: str # comma-separated MM/DD/YYYY
    operator_name: str
    dd_store_ids_text: str   # comma-separated store IDs
    ue_store_ids_text: str   # comma-separated store IDs
```

### 28.4 Thread Safety

Thread-safe via `_REPORT_LOCK` (RLock). Installs a dummy `streamlit` module that stubs out all UI calls.

---

## 29. Data Flow Diagram

```
User Input (dates, files, excluded dates)
    │
    ▼
app.py (orchestrator)
    │
    ├── load_and_aggregate_dd_data / load_and_aggregate_ue_data
    │       │
    │       ├── get_last_year_dates (compute 4 windows)
    │       └── process_master_file_for_dd / process_master_file_for_ue (per window)
    │               │
    │               ├── filter_master_file_by_date_range (read CSV, parse dates, filter)
    │               ├── filter_excluded_dates
    │               └── groupby Store ID → SUM Sales, SUM Payouts, NUNIQUE Orders
    │
    ├── process_data (merge 4 windows, compute derived metrics, round)
    │       ⇒ dd_sales_df, dd_payouts_df, dd_orders_df (per-store, all periods + deltas)
    │
    ├── load_and_aggregate_new_customers
    │       │
    │       ├── process_marketing_promotion_files_for_new_customers (DD, per window)
    │       └── get_ue_platform_total (UE, per window, legacy files)
    │
    ├── process_new_customers_data (merge DD NC, return empty for UE)
    │
    ├── get_platform_store_tables (filter by selected stores, rename columns)
    ├── get_platform_summary_tables → create_summary_tables (aggregate, Profitability/AOV)
    ├── create_combined_summary_tables (DD + UE summaries)
    ├── create_combined_store_tables (DD + UE store merge)
    ├── create_corporate_vs_todc_table (Post-only marketing analysis)
    ├── process_slot_analysis / process_ue_slot_analysis (time-of-day breakdowns)
    │
    ├── export_to_excel (full report generation)
    ├── create_date_export_from_master_files (date pivot export)
    ├── create_bucketing_export (bucketing analysis export)
    │
    └── new_analysis_screen → new_analysis_engine (diagnostic deep-dive)
            │
            └── build_analysis_dataset (order-level unified dataset)
                    ├── marketing spend allocation across slots
                    ├── sales/payout decomposition
                    ├── percentile ranking
                    ├── exception detection
                    └── campaign-level performance
```

---

## 30. Known Bugs & Edge Cases

### 30.1 DD Slot Boundary Off-by-One

DD `get_time_slot` function has off-by-one errors vs stated time ranges:
- Breakfast boundary `< 659` means 10:58 AM is last minute (not 10:59 AM)
- Dinner boundary `< 1159` means 7:18 PM is last (should be ~7:59 PM or 8:00 PM)
- Orders between 7:19 PM and 7:59 PM fall into Late Night instead of Dinner

UE slot boundaries are cleaner and don't have this issue.

### 30.2 Division-by-Zero Inconsistency

Store-level uses `.replace(0, 1)` which can produce very large percentages (e.g., 50000%) when base period is 0. Summary-level uses explicit `if != 0 else 0` which returns 0. These produce different results for the same edge case.

### 30.3 UE Marketing No Date Filtering

UE legacy marketing files (`ue-mkt-*.csv`) have NO date filtering applied — full file contents are used regardless of user's date range selection.

### 30.4 Session State Dependency

UE New Customers in combined tables come from `st.session_state`, not from the DataFrame. If session state is not populated (e.g., headless runner), defaults to 0.

### 30.5 Caching

`load_and_aggregate_new_customers` uses `@st.cache_data`. Other functions are not cached. This can cause stale data if inputs change without cache invalidation.

### 30.6 DD Payout Column Name Change

DD changed `Net total` to `Net total (for historical reference only)` at some point. The code handles both, but the fallback logic differs between date-export (explicit selection by year) and main processing (generic fallback).

---

## 31. Key Business Rules Summary

| # | Rule |
|---|------|
| 1 | Corporate vs TODC analysis uses **ONLY Post period** — Pre period is never used |
| 2 | DD New Customers in summary are summed across **ALL stores** (not filtered by store selection) |
| 3 | UE New Customers are **platform-level totals**, never distributed to individual stores |
| 4 | Combined store tables sum values for overlapping stores, then **recalculate** Growth%/YoY% |
| 5 | Store merge uses **outer join** — single-platform stores appear with 0 for missing platform |
| 6 | Profitability and AOV are computed from **aggregated totals** (not averaged from per-store values) |
| 7 | Orders are counted as **distinct** (NUNIQUE), not row count |
| 8 | All Store IDs are cast to **string** before merging |
| 9 | UE CSV skips first row (pre-header); date column is **index-based**, not name-based |
| 10 | Excluded dates are **not applied** to UE legacy marketing files |
| 11 | Marketing spend allocation to slots is based on **sales mix weight** (with orders fallback) |
| 12 | Financial line items (Commission, Ads, etc.) use **abs()** to display as positive |
| 13 | Export uses **2 decimal places** for financial values; UI uses **1 decimal place** |

---

## 32. Evolution Across App Versions

### App2.0 (Base)
- Core pipeline: 4-window comparison (Pre/Post × Current/LastYear)
- Platforms: DD + UE financial data processing
- Outputs: Summary tables, store tables, marketing Corporate/TODC, DD slot analysis, Excel export, date export
- Insights generation (platform, store, date, slot)

### App2.0-savvy (Enhanced)
All of App2.0, plus:
- **UE Store Name canonical keying** (Store Name replaces numeric ID when available)
- **Financial Summary Table** (detailed P&L rollup with 15 line items)
- **DD Financial Breakdown** (auto-discovered per-store financial columns)
- **Bucketing Analysis** (order-level, 7 GC buckets, day parts, marketing-driven flag)
- **New Analysis Engine** (order-level diagnostics, spend allocation, decomposition, percentile ranking)
- **UE Slot Analysis** (added alongside DD)

### App3.0 (Cloud-Ready)
All of App2.0-savvy, plus:
- **Cloud Pipeline** (GCS upload + Cloud Run Job execution)
- **Headless Runner** (`ralph_runner.py` for API/programmatic execution)
- **SaaS-style Design System** (`app_design.py` with consistent styling)
- **Google Drive Integration** (shared drive support, flat folder strategy)
- **Thread-safe execution** (RLock for concurrent report generation)

---

## Appendix A: All Column Name Variations

### DD Date Column Variations
```
Timestamp local date, Timestamp Local Date, Timestamp Local date,
timestamp local date, Date, date, Timestamp, timestamp
```

### DD Time Column Variations
```
Timestamp local time, Timestamp Local Time, timestamp local time,
Order received local time, Order Received Local Time
```

### UE Store Name Column Variations
```
Store Name, Restaurant Name, Restaurant name,
Merchant Name, Store name, [any column with "store" + "name"]
```

### DD Store ID Column Resolution Order (savvy)
```
Store ID → Merchant Store ID → Merchant store ID
```

---

## Appendix B: Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `selected_stores_DoorDash` | list[str] | Selected DD store IDs |
| `selected_stores_UberEats` | list[str] | Selected UE store IDs |
| `ue_new_customers_totals` | dict | UE new customer platform totals per window |
| `pre_period` | str | Pre date range string |
| `post_period` | str | Post date range string |
| `excluded_dates` | str | Comma-separated excluded dates |
| `operator_name` | str | Operator/brand name |
