"""Marketing analysis: Corporate vs TODC using Post period only."""

import pandas as pd
import numpy as np
from data_loader import filter_by_date_range, filter_excluded_dates


def create_corporate_vs_todc(promo_df, sponsored_df, post_start, post_end,
                              excluded_dates=None):
    """
    Analyse marketing spend split by Corporate (not self-serve) vs TODC (self-serve).
    Uses ONLY the Post period date range per Context.MD rule.

    Returns: dict with keys 'promotion', 'sponsored', 'combined', each containing
             a DataFrame with rows [Corporate, TODC] and cols [Orders, Sales, Spend, ROAS, Cost per Order].
    """
    results = {}

    for label, df in [("promotion", promo_df), ("sponsored", sponsored_df)]:
        if df is None or df.empty:
            results[label] = _empty_table()
            continue

        filtered = filter_by_date_range(df, "Date", post_start, post_end)
        if excluded_dates:
            filtered = filter_excluded_dates(filtered, "Date", excluded_dates)

        if filtered.empty:
            results[label] = _empty_table()
            continue

        self_serve_col = None
        for c in filtered.columns:
            if "self serve" in c.lower():
                self_serve_col = c
                break
        if self_serve_col is None:
            results[label] = _empty_table()
            continue

        filtered[self_serve_col] = filtered[self_serve_col].astype(str).str.strip().str.lower()
        corp = filtered[filtered[self_serve_col].isin(["false", "0", "no"])]
        todc = filtered[filtered[self_serve_col].isin(["true", "1", "yes"])]

        rows = []
        for name, grp in [("Corporate", corp), ("TODC", todc)]:
            orders = pd.to_numeric(grp["Orders"], errors="coerce").fillna(0).sum() if "Orders" in grp.columns else 0
            sales = pd.to_numeric(grp["Sales"], errors="coerce").fillna(0).sum() if "Sales" in grp.columns else 0
            spend = pd.to_numeric(grp["Spend"], errors="coerce").fillna(0).sum() if "Spend" in grp.columns else 0
            roas = round(sales / spend, 2) if spend != 0 else 0
            cpo = round(spend / orders, 2) if orders != 0 else 0
            rows.append({"Group": name, "Orders": round(orders), "Sales": round(sales, 2),
                         "Spend": round(spend, 2), "ROAS": roas, "Cost per Order": cpo})
        results[label] = pd.DataFrame(rows).set_index("Group")

    # Combined
    if "promotion" in results and "sponsored" in results:
        p = results["promotion"]
        s = results["sponsored"]
        combined_rows = []
        for grp in ["Corporate", "TODC"]:
            po = p.loc[grp] if grp in p.index else pd.Series({"Orders": 0, "Sales": 0, "Spend": 0})
            so = s.loc[grp] if grp in s.index else pd.Series({"Orders": 0, "Sales": 0, "Spend": 0})
            orders = po.get("Orders", 0) + so.get("Orders", 0)
            sales = po.get("Sales", 0) + so.get("Sales", 0)
            spend = po.get("Spend", 0) + so.get("Spend", 0)
            roas = round(sales / spend, 2) if spend != 0 else 0
            cpo = round(spend / orders, 2) if orders != 0 else 0
            combined_rows.append({"Group": grp, "Orders": round(orders), "Sales": round(sales, 2),
                                  "Spend": round(spend, 2), "ROAS": roas, "Cost per Order": cpo})
        results["combined"] = pd.DataFrame(combined_rows).set_index("Group")

    return results


def _empty_table():
    return pd.DataFrame({
        "Orders": [0, 0], "Sales": [0.0, 0.0], "Spend": [0.0, 0.0],
        "ROAS": [0.0, 0.0], "Cost per Order": [0.0, 0.0]
    }, index=pd.Index(["Corporate", "TODC"], name="Group"))
