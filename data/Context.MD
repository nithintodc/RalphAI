# Context: TODC Analytics data flow & naming conventions

This document explains **how data moves through the app** from raw CSV exports (DoorDash / UberEats / Marketing) to the **final dashboard tables and exported Excel report**, including **renaming conventions**, **file responsibilities**, and what we mean by **Corporate vs TODC**, **Pre**, **Post**, and **YoY**.

## High-level flow (raw → final report)

- **User inputs (UI)**
  - **Pre period** and **Post period** are entered as date ranges (MM/DD/YYYY-MM/DD/YYYY).
  - Optional **Excluded dates** can be entered (individual days to remove from all calculations).
  - Optional **Operator name** is used only for export filename prefixes.

- **Raw data sources**
  - **DoorDash master financial export**: `dd-data.csv`
  - **UberEats master financial export**: `ue-data.csv`
  - **Marketing exports**: uploaded as multiple CSV files and organized into `marketing_*` folders in a temp directory at runtime.

- **Filtering**
  - Each platform’s master file is filtered into the required time windows (current-year Pre/Post + last-year equivalents).
  - Excluded dates are removed after the range filter.

- **Normalization**
  - Store identifier columns are normalized (especially for UE and marketing files).
  - Data types are coerced (sales/payouts numeric, dates parsed).

- **Aggregation**
  - For each platform and each window (pre_24, post_24, pre_25, post_25):
    - Aggregate **Sales**, **Payouts**, **Orders** by **Store ID**.
  - For **New Customers**:
    - DoorDash: derived from marketing promotion exports (`MARKETING_PROMOTION*.csv`) by Store ID.
    - UberEats: treated as **platform totals** (legacy files), not store-level.

- **Derived metrics**
  - Pre vs Post deltas and growth are computed.
  - YoY deltas and growth are computed (Post this year vs Post last year).

- **Presentation**
  - Store selectors filter which stores are included in most platform/store tables.
  - Marketing “Corporate vs TODC” tables are computed from marketing exports **using only the Post period**.

- **Exports**
  - “Export Full Report”: generates a multi-sheet Excel workbook and uploads to Google Drive (if configured).
  - “Export by Date”: generates a date-pivot Excel workbook from master files for Pre/Post + last-year windows.

## What “Pre”, “Post”, “24”, “25”, and “YoY” mean

This app uses **four time windows** derived from your entered Pre/Post ranges.

- **Pre (Current Year)**: the date range you type into the Pre field.
  - Stored as: **`pre_25`**
- **Post (Current Year)**: the date range you type into the Post field.
  - Stored as: **`post_25`**
- **Pre (Last Year equivalent)**: the Pre range shifted back by 1 year.
  - Stored as: **`pre_24`**
- **Post (Last Year equivalent)**: the Post range shifted back by 1 year.
  - Stored as: **`post_24`**

Derived comparisons:

- **Pre vs Post (current year change)**:
  - Stored as: **`PrevsPost = post_25 - pre_25`**
  - Growth % stored as: **`Growth% = PrevsPost / pre_25`** (guarded against divide-by-zero)
- **LastYear Pre vs Post (last year change)**:
  - Stored as: **`LastYear_Pre_vs_Post = post_24 - pre_24`**
- **Year over Year (YoY)**:
  - Stored as: **`YoY = post_25 - post_24`**
  - YoY % stored as: **`YoY% = YoY / post_24`** (guarded against divide-by-zero)

Where this is implemented:

- Last-year range shifting: `data_processing.get_last_year_dates`
- Derived metrics for sales/payouts/orders: `data_processing.process_data`
- Derived metrics for new customers: `data_processing.process_new_customers_data` (DoorDash only; UE is handled at summary level)

## Data definitions (what each metric represents)

### DoorDash (DD)

Data is read from **`dd-data.csv`** and aggregated by store.

- **Store ID**
  - Primary column used: `Merchant store ID`
  - Fallback: `Store ID` if the primary column is missing
- **Sales**
  - Column: `Subtotal`
- **Payouts**
  - Column: `Net total`
  - Fallback: `Net total (for historical reference only)`
- **Orders**
  - Column: `DoorDash order ID` (counted as **unique** per store)
- **Date filter**
  - Uses a flexible list of “date column name variations” (e.g., `Timestamp local date`, `Date`, etc.)

Implemented in:

- Date-range filtering: `utils.filter_master_file_by_date_range` (DD path)
- Store-level aggregation: `data_loading.process_master_file_for_dd`

### UberEats (UE)

Data is read from **`ue-data.csv`** and aggregated by store.

UE files are handled differently than DD:

- **Header row**: UE reads CSV with `skiprows=[0]` (expects the header on row 2 of the export).
- **Date column**
  - UE filtering uses the **9th column** (index 8) as the date column.
- **Store ID**
  - UE may use `Store ID` or `Shop ID` → normalized to `Store ID`.
- **Sales**
  - Column: `Sales (excl. tax)`
- **Payouts**
  - Column: `Total payout`
- **Orders**
  - Column: `Order ID` (counted as **unique** per store)

Implemented in:

- UE-specific file processing: `data_loading.process_master_file_for_ue`
- UE date filtering: `utils.filter_master_file_by_date_range` (UE path)

### Excluded dates (applies to all platform calculations)

Excluded dates are a list of specific days removed from datasets *after* filtering to the date window.

- Implemented in: `utils.filter_excluded_dates`
- Called from:
  - `utils.filter_master_file_by_date_range` (both DD/UE filtering)
  - marketing new-customer processing (promotion files)
  - marketing corporate/TODC processing (promotion + sponsored)

## “Corporate vs TODC” meaning (marketing)

The app’s “Corporate vs TODC” section is built from **DoorDash marketing exports** (promotion + sponsored listing CSVs).

Key idea:

- Marketing CSVs contain a column named **`Is self serve campaign`**.
- The app treats that column as a boolean-like key:
  - **`False` → “Corporate”**
  - **`True` → “TODC”**

Important rule:

- Corporate vs TODC calculations use **ONLY the Post period** date range.
  - Pre period is not used for these marketing tables.

Which files & columns are used:

- **Promotion exports**: `MARKETING_PROMOTION*.csv`
  - Orders: `Orders`
  - Sales: `Sales`
  - Spend: `Customer discounts from marketing | (Funded by you)` (renamed internally to `Spend`)
- **Sponsored listing exports**: `MARKETING_SPONSORED_LISTING*.csv`
  - Orders: `Orders`
  - Sales: `Sales`
  - Spend: `Marketing fees | (including any applicable taxes)` (renamed internally to `Spend`)

Computed marketing metrics:

- **ROAS** = Sales / Spend (0 if Spend is 0)
- **Cost per Order** = Spend / Orders (0 if Orders is 0)

Implemented in:

- `marketing_analysis.process_marketing_promotion_files`
- `marketing_analysis.process_marketing_sponsored_files`
- `marketing_analysis.create_corporate_vs_todc_table`

## “New Customers” meaning (marketing-derived)

New Customers is treated differently for DD vs UE.

### DoorDash new customers (store-level, marketing-derived)

- Source: **marketing promotion exports** (`MARKETING_PROMOTION*.csv`)
- Column: **“New customers acquired”** (case-insensitive match)
- Aggregation: summed by Store ID for each time window (pre_24, pre_25, post_24, post_25)

Implemented in:

- `data_processing.load_and_aggregate_new_customers` (DoorDash path)
  - Searches the uploaded marketing folder for `marketing_*` directories and `MARKETING_PROMOTION*.csv` files.
  - Normalizes store ID (Store ID vs Shop ID).
  - Parses dates and filters into the specified window.
  - Applies excluded-date filtering.

### UberEats new customers (platform total, legacy)

- UE “new customer” marketing is treated as **platform totals**, not store-level.
- Totals are stored into session state as:
  - `st.session_state['ue_new_customers_totals'] = { pre_24, post_24, pre_25, post_25 }`
- UE summary tables use these totals directly (not distributed to stores).

Implemented in:

- `data_processing.load_and_aggregate_new_customers` (UE totals from legacy `ue-mkt-*.csv` files)
- `table_generation.create_summary_tables` (UE path uses `ue_new_customers_totals`)

## Naming & renaming conventions

### Store identifier normalization

Across the app we standardize to a common key:

- Standard store key: **`Store ID`**
- Normalization rule:
  - if `Shop ID` exists → rename to `Store ID`
  - else if `Store ID` exists → use it

Implemented in: `utils.normalize_store_id_column`

DoorDash special case:

- DD uses `Merchant store ID` as the primary identifier in master exports.
- DD aggregations rename the grouped key to `Store ID` after aggregation so downstream code can merge consistently.

Implemented in: `data_loading.process_master_file_for_dd`

### Period column naming

The app consistently uses the suffixes:

- `pre_24`, `post_24` → last-year equivalents
- `pre_25`, `post_25` → current year

When building the merged period tables, the app renames intermediate aggregated columns like:

- `Sales` → `pre_25` / `post_25` / `pre_24` / `post_24`
- `Payouts` → same
- `Orders` → same

Implemented in: `data_processing.process_data`

### Display/export label renames

Store-level table “friendly” column names are created from the canonical internal names:

- `pre_25` → `Pre`
- `post_25` → `Post`
- `LastYear_Pre_vs_Post` → `LastYear Pre vs Post`
- `post_24` → `last year-post`
- `post_25` → `post`

Implemented in: `table_generation.get_platform_store_tables`

## Where each transformation happens (file-by-file)

### `app.py` (orchestrator + dashboard)

- Controls **navigation** (upload screen vs dashboard).
- Loads inputs from `st.session_state` (date ranges, excluded dates, uploaded paths).
- Auto-detects `dd-data.csv` / `ue-data.csv` if not explicitly uploaded.
- Orchestrates:
  - `load_and_aggregate_*` for DD/UE
  - `process_data` and `process_new_customers_data`
  - summary/store/combined tables
  - marketing corporate/TODC tables
  - slot analysis tables
  - export actions

### `file_upload_screen.py` (upload + session state)

- Collects Pre/Post date ranges + operator name.
- Uploads and writes:
  - `dd-data.csv` and `ue-data.csv` into a temp folder.
  - multiple marketing CSVs into a temp `marketing_data/marketing_*` folder structure.
- Writes paths into session state:
  - `uploaded_dd_data`, `uploaded_ue_data`, `uploaded_marketing_folder`

### `utils.py` (core data utilities)

- `normalize_store_id_column`: harmonizes `Store ID` / `Shop ID`.
- `filter_excluded_dates`: removes specific dates (day-level) from a dataframe.
- `filter_master_file_by_date_range`: the main “read CSV + find date + parse + filter” utility.
  - DD vs UE parsing differences are handled here.

### `data_loading.py` (platform aggregation primitives)

- `process_master_file_for_dd`: DD window → aggregate (Sales, Payouts, Orders) by store.
- `process_master_file_for_ue`: UE window → aggregate (Sales, Payouts, Orders) by store.

### `data_processing.py` (windowing + merging + derived metrics)

- `get_last_year_dates`: shifts any range back by one year.
- `load_and_aggregate_dd_data` / `load_and_aggregate_ue_data`
  - Builds the four required windows by calling `process_master_file_for_*`.
- `load_and_aggregate_new_customers`
  - DoorDash: reads marketing promotion files and returns per-store new customers by window.
  - UberEats: returns platform totals from legacy UE marketing files.
- `process_data`
  - Merges the four windows into a single per-store table per metric (Sales/Payouts/Orders)
  - Computes PrevsPost / LastYear_Pre_vs_Post / YoY / Growth% / YoY%
- `process_new_customers_data`
  - DoorDash new-customer merging and derived metrics (UE returns empty; handled at summary level)

### `table_generation.py` (summary & combined tables)

- `create_summary_tables`
  - Builds platform summaries aggregated across selected stores.
  - Special cases:
    - UE new customers pulled from `st.session_state['ue_new_customers_totals']`
    - DD new customers are summed across *all* marketing-derived rows (not filtered by store selection)
- `create_combined_summary_tables`
  - Adds DD + UE totals into combined summary tables.
- `create_combined_store_tables`
  - Merges DD + UE store-level tables and sums overlapping stores.
- `get_platform_store_tables` / `get_platform_summary_tables`
  - Thin wrappers that select stores from session state and call the above.

### `marketing_analysis.py` (Corporate vs TODC marketing)

- Scans `marketing_*` folders and reads:
  - `MARKETING_PROMOTION*.csv`
  - `MARKETING_SPONSORED_LISTING*.csv`
- Filters strictly to the **Post** date range (+ excluded dates).
- Groups by `Is self serve campaign` and labels:
  - `False` → Corporate
  - `True` → TODC

### `slot_analysis.py` (time-of-day slot tables)

Builds slot-based tables for sales and payouts:

- Slots:
  - Overnight, Breakfast, Lunch, Afternoon, Dinner, Late night
- DD slot assignment: from local timestamp column (e.g. `Timestamp local time`).
- UE slot assignment: from “column J” (index 9) or a column containing “accept” + “time”.

### `export_functions.py` (Excel outputs + Drive upload)

- `export_to_excel`
  - Produces a multi-sheet workbook:
    - `Summary Tables`
    - `Store-Level Tables`
    - `Corporate vs TODC` (if marketing tables exist)
    - `Slot-based Analysis` (if slot tables exist)
    - `Insights`
  - Uploads the generated Excel to Google Drive under a “flat” folder naming strategy to avoid shared-drive hierarchy depth limits.
- `create_date_export_from_master_files`
  - Reads master files, filters into each window, and creates a workbook with sheets like:
    - `DD_25_Sales`, `DD_25_Payouts`, `DD_25_Orders`
    - `UE_25_Sales`, `UE_25_Payouts`, `UE_25_Orders`
    - `DD_24_Sales`, `DD_24_Payouts`, `DD_24_Orders`
    - `UE_24_Sales`, `UE_24_Payouts`, `UE_24_Orders`
  - Each sheet shows **Pre block** and **Post block** side-by-side (with a gap), pivoted by Date × Store ID and includes totals.

### `gdrive_utils.py` (Google Drive / Docs integration)

- Encapsulates Google Drive auth (secrets/env/file fallback) and:
  - shared drive discovery
  - shallow folder strategy (avoid “teamDriveHierarchyTooDeep”)
  - file uploads to date-stamped “flat” folders
  - optional creation of Google Docs with native tables

### `config.py` (paths/constants)

- Defines root path and canonical filenames:
  - `dd-data.csv`, `ue-data.csv`
  - legacy marketing files: `dd-mkt-*.csv`, `ue-mkt-*.csv`

### Utility / support scripts

- `get_drive_id.py`: helper to print the shared drive ID by name.
- `test_data_loading.py`: quick CSV loading test script for UE exports (not used by the app runtime).

## Notes / gotchas worth knowing

- **UE parsing differences are deliberate**:
  - UE expects header on row 2 and uses column index 8 for date filtering in multiple places.
- **Marketing “Corporate vs TODC” uses only Post**:
  - If you want Pre-vs-Post marketing, you’d need to change `marketing_analysis.py` to use both windows.
- **DoorDash “New Customers” store IDs may not match financial Store IDs**:
  - Summary logic intentionally sums *all* DD marketing new customers rather than filtering by selected stores.
- **Division-by-zero handling**:
  - Growth% and YoY% are guarded; when denominators are 0, the percentage is set to 0.

