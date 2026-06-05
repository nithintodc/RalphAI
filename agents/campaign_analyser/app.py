"""Campaign Slot Analyzer — Streamlit app.

Run:  streamlit run app.py

Inputs (three CSV uploads):
  1. Financial transactions  (FINANCIAL_DETAILED_TRANSACTIONS_*.csv)
  2. Marketing promotion     (MARKETING_PROMOTION_*.csv)
  3. Campaign plan / slot tags  (campaigns-infinite.csv-style)

Outputs:
  - Headline KPIs (orders, marketing-driven %, AOV, ROAS, spend)
  - Campaign roll-up: planned slots vs actual attribution vs in-slot eligibility
  - Zero-fire diagnosis (campaigns that never kicked off + the reason)
  - Slot heatmap (orders by day x time-slot)
  - Per-campaign drilldown: slot-by-slot eligible vs attributed
"""
from __future__ import annotations

import io
import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# constants
# ----------------------------------------------------------------------------
TIME_SLOTS = ["Overnight", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

SLOT_HOUR_RANGES = {
    "Overnight": "12 AM – 4:59 AM",
    "Breakfast":     "5 AM – 10:59 AM",
    "Lunch":         "11 AM – 1:59 PM",
    "Afternoon":     "2 PM – 4:59 PM",
    "Dinner":        "5 PM – 7:59 PM",
    "Late night":    "8 PM – 11:59 PM",
}


def slot_tag_to_dayslot(tag: int) -> tuple[str, str]:
    """Tag numbering: 1 = Mon Overnight, 2 = Tue Overnight, ..., 8 = Mon Breakfast, ..., 42 = Sun Late night."""
    tag = int(tag)
    time_idx = (tag - 1) // 7
    day_idx = (tag - 1) % 7
    return DAYS[day_idx], TIME_SLOTS[time_idx]


def hour_to_slot(h: int) -> str:
    if 0 <= h < 5:   return "Overnight"
    if 5 <= h < 11:  return "Breakfast"
    if 11 <= h < 14: return "Lunch"
    if 14 <= h < 17: return "Afternoon"
    if 17 <= h < 20: return "Dinner"
    return "Late night"


def parse_slot_tags(s) -> list[tuple[str, str]]:
    s = str(s).strip().strip('"')
    if not s or s.lower() == "nan":
        return []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    out = []
    for p in parts:
        try:
            out.append(slot_tag_to_dayslot(int(float(p))))
        except Exception:
            continue
    return out


def extract_short_id(name: str | None) -> str | None:
    """McDonald's (240-CHGO-2425 E 79TH) -> '240'"""
    if not isinstance(name, str) or "(" not in name:
        return None
    inside = name.split("(", 1)[1]
    return inside.split("-", 1)[0]


# ----------------------------------------------------------------------------
# loaders
# ----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_financial(file_bytes: bytes) -> pd.DataFrame:
    usecols = [
        "Timestamp local date", "Order received local time", "Store name", "Merchant store ID",
        "Transaction type", "DoorDash order ID", "Subtotal",
        "Customer discounts from marketing | (funded by you)",
        "Marketing fees | (including any applicable taxes)",
    ]
    df = pd.read_csv(io.BytesIO(file_bytes), usecols=usecols, low_memory=False)
    df = df[df["Transaction type"] == "Order"].copy()
    df["Date"] = pd.to_datetime(df["Timestamp local date"], errors="coerce")
    df["LocalDT"] = pd.to_datetime(df["Order received local time"], errors="coerce")
    df["Hour"] = df["LocalDT"].dt.hour
    df = df.dropna(subset=["Date", "Hour"])
    df["Hour"] = df["Hour"].astype(int)
    df["Slot"] = df["Hour"].apply(hour_to_slot)
    df["DOW"] = df["Date"].dt.day_name().str[:3]
    df["Subtotal"] = pd.to_numeric(df["Subtotal"], errors="coerce").fillna(0)
    df["MktDisc"] = (
        pd.to_numeric(df["Customer discounts from marketing | (funded by you)"], errors="coerce")
        .fillna(0).abs()
    )
    df["MktFee"] = (
        pd.to_numeric(df["Marketing fees | (including any applicable taxes)"], errors="coerce")
        .fillna(0).abs()
    )

    # collapse to one row per order (rows can be split per order)
    grp = df.groupby(["Merchant store ID", "DoorDash order ID"], as_index=False).agg(
        Subtotal=("Subtotal", "sum"),
        MktDisc=("MktDisc", "sum"),
        MktFee=("MktFee", "sum"),
        Date=("Date", "first"),
        Slot=("Slot", "first"),
        DOW=("DOW", "first"),
        StoreName=("Store name", "first"),
    )
    grp["MerchantStoreID"] = grp["Merchant store ID"].astype(str).str.replace(r"\.0$", "", regex=True)
    grp["IsMktDriven"] = (grp["MktDisc"] > 0) | (grp["MktFee"] > 0)
    return grp


@st.cache_data(show_spinner=False)
def load_marketing(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    spend_col = "Customer discounts from marketing | (Funded by you)"
    df["Spend"] = pd.to_numeric(df[spend_col], errors="coerce").fillna(0)
    df["Orders"] = pd.to_numeric(df["Orders"], errors="coerce").fillna(0)
    df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce").fillna(0)
    df["DOW"] = df["Date"].dt.day_name().str[:3]
    return df


@st.cache_data(show_spinner=False)
def load_campaigns(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    df["DaySlots"] = df["Slot Tags"].apply(parse_slot_tags)
    df["NumSlots"] = df["DaySlots"].apply(len)
    df["Store ID"] = df["Store ID"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["Minimum Subtotal"] = pd.to_numeric(df["Minimum Subtotal"], errors="coerce").fillna(0)
    return df


# ----------------------------------------------------------------------------
# analytics
# ----------------------------------------------------------------------------
def build_slot_perf(campaigns: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """For each (campaign × tagged day × tagged slot): total orders, eligible, marketing-driven."""
    store_lookup = orders.groupby("MerchantStoreID")["StoreName"].first().reset_index()
    store_lookup["ShortID"] = store_lookup["StoreName"].apply(extract_short_id)
    short_to_merch = dict(zip(store_lookup["ShortID"], store_lookup["MerchantStoreID"]))

    rows = []
    for _, c in campaigns.iterrows():
        merch = short_to_merch.get(str(c["Store ID"]))
        if merch is None:
            continue
        store_orders = orders[orders["MerchantStoreID"] == merch]
        min_sub = float(c["Minimum Subtotal"])
        for day, slot in c["DaySlots"]:
            seg = store_orders[(store_orders["DOW"] == day) & (store_orders["Slot"] == slot)]
            eligible = seg[seg["Subtotal"] >= min_sub]
            rows.append({
                "Store": c["Store ID"],
                "Campaign": c["Campaign Name"],
                "MinSub": min_sub,
                "Day": day,
                "Slot": slot,
                "SlotHours": SLOT_HOUR_RANGES[slot],
                "TotalOrders": len(seg),
                "EligibleOrders": len(eligible),
                "MktDrivenOrders": int(seg["IsMktDriven"].sum()),
                "EligibleAndMktDriven": int(eligible["IsMktDriven"].sum()),
                "EligibleSales": float(eligible["Subtotal"].sum()),
            })
    return pd.DataFrame(rows)


def build_campaign_summary(slot_perf: pd.DataFrame, marketing: pd.DataFrame, campaigns: pd.DataFrame) -> pd.DataFrame:
    if slot_perf.empty:
        return pd.DataFrame()
    s = slot_perf.groupby(["Store", "Campaign", "MinSub"], as_index=False).agg(
        SlotsAssigned=("Day", "count"),
        InSlotOrders=("TotalOrders", "sum"),
        Eligible=("EligibleOrders", "sum"),
        MktDrivenInSlot=("MktDrivenOrders", "sum"),
        EligibleMktDriven=("EligibleAndMktDriven", "sum"),
    )
    mkt_agg = marketing.groupby("Campaign name", as_index=False).agg(
        AttrOrders=("Orders", "sum"),
        AttrSales=("Sales", "sum"),
        AttrSpend=("Spend", "sum"),
        DaysActive=("Date", "nunique"),
    ).rename(columns={"Campaign name": "Campaign"})
    s = s.merge(mkt_agg, on="Campaign", how="left").fillna(
        {"AttrOrders": 0, "AttrSales": 0, "AttrSpend": 0, "DaysActive": 0}
    )
    s["AOV_Attributed"] = (s["AttrSales"] / s["AttrOrders"].replace(0, np.nan)).fillna(0).round(2)
    s["ROAS"] = (s["AttrSales"] / s["AttrSpend"].replace(0, np.nan)).fillna(0).round(2)
    s["FireRate%"] = (
        (s["EligibleMktDriven"] / s["Eligible"].replace(0, np.nan)) * 100
    ).fillna(0).round(1)
    s["CostPerOrder"] = (s["AttrSpend"] / s["AttrOrders"].replace(0, np.nan)).fillna(0).round(2)
    return s.sort_values(["Store", "Campaign"]).reset_index(drop=True)


def diagnose_zero_fire(camp_summary: pd.DataFrame) -> pd.DataFrame:
    if camp_summary.empty:
        return pd.DataFrame()
    z = camp_summary[camp_summary["AttrOrders"] == 0].copy()
    def reason(r):
        if r["InSlotOrders"] == 0:
            return "DEAD SLOT — no customer traffic at all in the tagged day × time-slot windows"
        if r["Eligible"] == 0:
            return f"MIN SUBTOTAL TOO HIGH — {int(r['InSlotOrders'])} orders existed in slot but none crossed ${r['MinSub']:.0f}"
        return "CONFIG ISSUE — eligible orders existed but DoorDash never attributed (timezone / activation / overlap)"
    z["Reason"] = z.apply(reason, axis=1)
    return z


def slot_heatmap(orders: pd.DataFrame, value: str = "orders") -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame()
    if value == "orders":
        pivot = orders.pivot_table(index="Slot", columns="DOW", values="DoorDash order ID", aggfunc="count", fill_value=0)
    elif value == "mkt_driven":
        pivot = orders.pivot_table(index="Slot", columns="DOW", values="IsMktDriven", aggfunc="sum", fill_value=0)
    elif value == "aov":
        pivot = orders.pivot_table(index="Slot", columns="DOW", values="Subtotal", aggfunc="mean", fill_value=0).round(2)
    return pivot.reindex(index=TIME_SLOTS, columns=DAYS).fillna(0)


# ----------------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Campaign Slot Analyzer", layout="wide")
st.title("Campaign Slot Analyzer")
st.caption(
    "Upload Financial transactions, Marketing promotion, and your Campaign plan. "
    "The app slices financial data into the 6 time-slots × 7 days = 42-slot grid, "
    "joins it to the campaign plan, and tells you exactly which campaigns are firing, "
    "which aren't, and why."
)

with st.sidebar:
    st.header("1. Upload data")
    fin_file = st.file_uploader("Financial transactions CSV", type=["csv"], key="fin")
    mkt_file = st.file_uploader("Marketing promotion CSV", type=["csv"], key="mkt")
    camp_file = st.file_uploader("Campaign plan CSV (Slot Tags 1-42)", type=["csv"], key="camp")

    st.divider()
    st.markdown("**Slot tag legend** (1-42):")
    st.markdown(
        "- 1 = Mon Overnight, 2 = Tue Overnight, ..., 7 = Sun Overnight\n"
        "- 8 = Mon Breakfast, ..., 14 = Sun Breakfast\n"
        "- 15-21 = Lunch · 22-28 = Afternoon · 29-35 = Dinner · 36-42 = Late night"
    )

if not (fin_file and mkt_file and camp_file):
    st.info("Upload all three files in the sidebar to begin.")
    st.stop()

with st.spinner("Parsing financial transactions…"):
    orders = load_financial(fin_file.getvalue())
with st.spinner("Parsing marketing promotion…"):
    marketing = load_marketing(mkt_file.getvalue())
with st.spinner("Parsing campaign plan…"):
    campaigns = load_campaigns(camp_file.getvalue())

# constrain financial to campaign-active window
todc_only = marketing[marketing["Campaign name"].isin(campaigns["Campaign Name"])]
if not todc_only.empty:
    win_start = todc_only["Date"].min()
    win_end = todc_only["Date"].max()
else:
    win_start, win_end = orders["Date"].min(), orders["Date"].max()

with st.sidebar:
    st.divider()
    st.header("2. Filters")
    date_range = st.date_input(
        "Analysis window",
        value=(win_start.date(), win_end.date()),
        min_value=orders["Date"].min().date(),
        max_value=orders["Date"].max().date(),
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    else:
        start, end = win_start, win_end

orders_f = orders[(orders["Date"] >= start) & (orders["Date"] <= end)]
marketing_f = marketing[(marketing["Date"] >= start) & (marketing["Date"] <= end)]
marketing_f = marketing_f[marketing_f["Campaign name"].isin(campaigns["Campaign Name"])]

# ----------------------------------------------------------------------------
# KPI strip
# ----------------------------------------------------------------------------
total_orders = len(orders_f)
mkt_driven = int(orders_f["IsMktDriven"].sum())
total_sales = float(orders_f["Subtotal"].sum())
aov = total_sales / total_orders if total_orders else 0
attr_orders = int(marketing_f["Orders"].sum())
attr_sales = float(marketing_f["Sales"].sum())
attr_spend = float(marketing_f["Spend"].sum())
roas = attr_sales / attr_spend if attr_spend else 0
mkt_pct = (mkt_driven / total_orders * 100) if total_orders else 0

st.subheader(f"Headline — {start.date()} to {end.date()}")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total orders (financial)", f"{total_orders:,}")
c2.metric("Marketing-driven orders", f"{mkt_driven:,}", f"{mkt_pct:.1f}% of orders")
c3.metric("AOV (all orders)", f"${aov:,.2f}")
c4.metric("Attributed orders (mkt file)", f"{attr_orders:,}")
c5.metric("Attributed sales", f"${attr_sales:,.0f}")
c6.metric("ROAS / Spend", f"{roas:.2f}x", f"${attr_spend:,.0f} spend")

st.divider()

# ----------------------------------------------------------------------------
# Tabs: Campaigns / Zero-fire / Slot heatmap / Per-campaign drilldown / Raw
# ----------------------------------------------------------------------------
slot_perf = build_slot_perf(campaigns, orders_f)
camp_summary = build_campaign_summary(slot_perf, marketing_f, campaigns)
zero_fire = diagnose_zero_fire(camp_summary)

tabs = st.tabs([
    "Campaign roll-up",
    f"Zero-fire diagnosis ({len(zero_fire)})",
    "Slot heatmap",
    "Per-campaign drilldown",
    "Raw exports",
])

with tabs[0]:
    st.markdown("**One row per campaign.** Hover any column header in the table to sort. Definitions below.")

    with st.expander("📖 Column definitions", expanded=True):
        st.markdown("""
| Column | What it means |
|---|---|
| **Store** | Short store ID from the campaign plan (e.g. `240`) |
| **Campaign** | Campaign name as it appears in the marketing promotion file |
| **MinSub** | Minimum subtotal an order must hit for this campaign discount to apply |
| **SlotsAssigned** | How many of the 42 day×time-slots this campaign is tagged to run in |
| **InSlotOrders** | All orders the store received inside the tagged slots (any size) |
| **Eligible** | Of `InSlotOrders`, how many crossed the `MinSub` threshold — i.e. *could* have triggered the campaign |
| **MktDrivenInSlot** | Of `InSlotOrders`, how many were actually marketing-driven (had a discount or marketing fee) |
| **EligibleMktDriven** | Orders that were **both** ≥ `MinSub` **and** marketing-attributed — true campaign wins |
| **AttrOrders** | Orders DoorDash attributed to this campaign (from the marketing promotion file). May differ from `EligibleMktDriven` if DD runs the campaign outside the tagged slots |
| **AttrSales** | Total sales DoorDash attributed to this campaign |
| **AttrSpend** | Your spend on this campaign = customer discount funded by you |
| **DaysActive** | Distinct days this campaign attributed at least one order |
| **Campaign AOV** | `AttrSales / AttrOrders` — average ticket size of campaign-attributed orders |
| **ROAS** | `AttrSales / AttrSpend` — sales generated per $1 of campaign spend |
| **FireRate%** | `EligibleMktDriven / Eligible` — of orders that *could* have triggered the campaign in-slot, what % actually did. Below 90% = configuration issue worth checking |
| **CostPerOrder** | `AttrSpend / AttrOrders` — average discount given per attributed order |
        """)

    # Rename for clarity in the displayed table
    display = camp_summary.rename(columns={"AOV_Attributed": "Campaign AOV"})
    st.dataframe(
        display.style.format({
            "MinSub": "${:.0f}",
            "AttrOrders": "{:,.0f}",
            "AttrSales": "${:,.0f}",
            "AttrSpend": "${:,.0f}",
            "DaysActive": "{:.0f}",
            "Campaign AOV": "${:.2f}",
            "ROAS": "{:.2f}x",
            "FireRate%": "{:.1f}%",
            "CostPerOrder": "${:.2f}",
        }),
        use_container_width=True, height=560,
    )

with tabs[1]:
    if zero_fire.empty:
        st.success("Every campaign attributed at least one order in this window.")
    else:
        st.warning(f"{len(zero_fire)} campaigns did not fire a single order.")
        show = zero_fire[[
            "Store", "Campaign", "MinSub", "SlotsAssigned", "InSlotOrders", "Eligible", "Reason"
        ]]
        st.dataframe(
            show.style.format({"MinSub": "${:.0f}"}),
            use_container_width=True, height=400,
        )
        # group by reason for the headline
        st.markdown("**Reasons**")
        st.dataframe(zero_fire["Reason"].value_counts().rename_axis("Reason").reset_index(name="Campaigns"))

with tabs[2]:
    st.markdown("Orders sliced into the 42-slot grid. Rows = time-slot, columns = day-of-week.")
    metric = st.radio("Metric", ["orders", "mkt_driven", "aov"],
                      format_func={"orders": "Order count", "mkt_driven": "Marketing-driven orders", "aov": "AOV ($)"}.get,
                      horizontal=True)
    stores = ["(all stores)"] + sorted(orders_f["MerchantStoreID"].unique().tolist())
    pick = st.selectbox("Store filter", stores)
    sub = orders_f if pick == "(all stores)" else orders_f[orders_f["MerchantStoreID"] == pick]
    hm = slot_heatmap(sub, value=metric)
    if hm.empty:
        st.info("No data.")
    else:
        fmt = "{:,.0f}" if metric != "aov" else "${:.2f}"
        st.dataframe(hm.style.background_gradient(cmap="Greens", axis=None).format(fmt),
                     use_container_width=True)

with tabs[3]:
    if camp_summary.empty:
        st.info("No campaigns matched.")
    else:
        pick = st.selectbox("Pick a campaign", camp_summary["Campaign"].tolist())
        c = camp_summary[camp_summary["Campaign"] == pick].iloc[0]
        st.markdown(f"### {pick} (Store {c['Store']}) · Min ${c['MinSub']:.0f}")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Slots tagged", int(c["SlotsAssigned"]))
        k2.metric("Eligible orders in-slot", int(c["Eligible"]))
        k3.metric("Attributed orders", int(c["AttrOrders"]))
        k4.metric("Fire rate", f"{c['FireRate%']:.1f}%")
        k5.metric("ROAS", f"{c['ROAS']:.2f}x")

        slots_c = slot_perf[slot_perf["Campaign"] == pick]
        if not slots_c.empty:
            st.markdown("**Slot-by-slot breakdown**")
            st.dataframe(
                slots_c[["Day", "Slot", "SlotHours", "TotalOrders", "EligibleOrders",
                         "MktDrivenOrders", "EligibleAndMktDriven", "EligibleSales"]]
                .style.format({"EligibleSales": "${:,.2f}"}),
                use_container_width=True, height=380,
            )

with tabs[4]:
    def _to_excel_bytes() -> bytes:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            (camp_summary if not camp_summary.empty
             else pd.DataFrame()).to_excel(writer, sheet_name="Campaign roll-up", index=False)
            (slot_perf if not slot_perf.empty
             else pd.DataFrame()).to_excel(writer, sheet_name="Slot-level", index=False)
            (zero_fire if not zero_fire.empty
             else pd.DataFrame()).to_excel(writer, sheet_name="Zero-fire diagnosis", index=False)
        return buf.getvalue()

    st.download_button(
        "Download full report (XLSX — 3 sheets)",
        _to_excel_bytes(),
        file_name=f"campaign_slot_report_{start.date()}_{end.date()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption("Workbook sheets: **Campaign roll-up**, **Slot-level**, **Zero-fire diagnosis**.")

    with st.expander("Or download individual CSVs"):
        st.download_button("Campaign roll-up CSV",
                           camp_summary.to_csv(index=False).encode(),
                           file_name="campaign_summary.csv", mime="text/csv")
        st.download_button("Slot-level CSV",
                           slot_perf.to_csv(index=False).encode(),
                           file_name="slot_perf.csv", mime="text/csv")
        st.download_button("Zero-fire diagnosis CSV",
                           zero_fire.to_csv(index=False).encode(),
                           file_name="zero_fire.csv", mime="text/csv")
