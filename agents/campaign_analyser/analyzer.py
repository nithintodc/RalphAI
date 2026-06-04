"""
Campaign Slot Analyzer — headless core (extracted from app.py, no Streamlit).

Slices DoorDash financial transactions into the 6 time-slots × 7 days = 42-slot
grid, joins to the campaign plan (Slot Tags 1-42), and determines which campaigns
are firing, which aren't, and why.

Slot numbering: 1 = Mon Early morning, 2 = Tue Early morning, ...,
8 = Mon Breakfast, ..., 42 = Sun Late night.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd

TIME_SLOTS = ["Early morning", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

SLOT_HOUR_RANGES = {
    "Early morning": "12 AM – 4:59 AM",
    "Breakfast":     "5 AM – 10:59 AM",
    "Lunch":         "11 AM – 1:59 PM",
    "Afternoon":     "2 PM – 4:59 PM",
    "Dinner":        "5 PM – 7:59 PM",
    "Late night":    "8 PM – 11:59 PM",
}


def _read_bytes(src: str | Path | bytes) -> bytes:
    if isinstance(src, bytes):
        return src
    return Path(src).read_bytes()


def slot_tag_to_dayslot(tag: int) -> tuple[str, str]:
    """Tag numbering: 1 = Mon Early morning, ..., 42 = Sun Late night."""
    tag = int(tag)
    time_idx = (tag - 1) // 7
    day_idx = (tag - 1) % 7
    return DAYS[day_idx], TIME_SLOTS[time_idx]


def hour_to_slot(h: int) -> str:
    if 0 <= h < 5:   return "Early morning"
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
def load_financial(src: str | Path | bytes) -> pd.DataFrame:
    usecols = [
        "Timestamp local date", "Timestamp local time", "Store name", "Merchant store ID",
        "Transaction type", "DoorDash order ID", "Subtotal",
        "Customer discounts from marketing | (funded by you)",
        "Marketing fees | (including any applicable taxes)",
    ]
    df = pd.read_csv(io.BytesIO(_read_bytes(src)), usecols=usecols, low_memory=False)
    df = df[df["Transaction type"] == "Order"].copy()
    df["Date"] = pd.to_datetime(df["Timestamp local date"], errors="coerce")
    df["LocalDT"] = pd.to_datetime(df["Timestamp local time"], errors="coerce")
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


def load_marketing(src: str | Path | bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_read_bytes(src)))
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    spend_col = "Customer discounts from marketing | (Funded by you)"
    df["Spend"] = pd.to_numeric(df[spend_col], errors="coerce").fillna(0)
    df["Orders"] = pd.to_numeric(df["Orders"], errors="coerce").fillna(0)
    df["Sales"] = pd.to_numeric(df["Sales"], errors="coerce").fillna(0)
    df["DOW"] = df["Date"].dt.day_name().str[:3]
    return df


def load_campaigns(src: str | Path | bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(_read_bytes(src)))
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
