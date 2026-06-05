"""
DoorDash order origin: organic / promo / ads / both (promo_ads in JS).

Rules (FINANCIAL_DETAILED, order-level sums):
- Organic: |mkt fees| == 0, all discount cols == 0, optional hist cols == 0 if present
- Promo + Ads: |mkt fees| > 0.99 AND any promo signal (you/DD/3P disc or hist mkt > 0)
- Ads: |mkt fees| > 0.99 AND no promo signals
- Promo: promo signal AND |mkt fees| <= 0.99
"""

from __future__ import annotations

DD_ADS_FEE_THRESHOLD = 0.99
ZERO_EPS = 0.005

MKT_FEE_COL = "Marketing fees | (including any applicable taxes)"
MKT_DISCOUNT_COLS = [
    "Customer discounts from marketing | (funded by you)",
    "Customer discounts from marketing | (funded by DoorDash)",
    "Customer discounts from marketing | (funded by a third-party)",
]
MKT_FEE_HIST_COL = "Marketing fees (for historical reference only) | (all discounts and fees)"
AD_FEE_HIST_COL = "Ad fee (for historical reference only)"


def _is_zero(value: float) -> bool:
    return abs(float(value or 0)) < ZERO_EPS


def _abs_money(value: float) -> float:
    return abs(float(value or 0))


def classify_dd_order(
    *,
    marketing_fees: float,
    customer_discounts_you: float = 0,
    customer_discounts_doordash: float = 0,
    customer_discounts_third_party: float = 0,
    marketing_fees_historical: float | None = None,
    ad_fee_historical: float | None = None,
    both_label: str = "both",
) -> str:
    mkt_abs = _abs_money(marketing_fees)
    cd_you = _abs_money(customer_discounts_you)
    cd_dd = _abs_money(customer_discounts_doordash)
    cd_3p = _abs_money(customer_discounts_third_party)

    has_hist_col = marketing_fees_historical is not None
    has_ad_hist_col = ad_fee_historical is not None
    hist_mkt = _abs_money(marketing_fees_historical) if has_hist_col else 0.0
    ad_hist = _abs_money(ad_fee_historical) if has_ad_hist_col else 0.0

    if (
        _is_zero(marketing_fees)
        and cd_you == 0
        and cd_dd == 0
        and cd_3p == 0
        and (not has_hist_col or hist_mkt == 0)
        and (not has_ad_hist_col or ad_hist == 0)
    ):
        return "organic"

    has_promo_signal = (
        cd_you > 0
        or cd_dd > 0
        or cd_3p > 0
        or (has_hist_col and hist_mkt > 0)
    )
    has_ads_signal = mkt_abs > DD_ADS_FEE_THRESHOLD

    if has_ads_signal and has_promo_signal:
        return both_label
    if has_ads_signal:
        return "ads"
    if has_promo_signal:
        return "promo"
    if mkt_abs > 0:
        return "ads"
    return "organic"


def classify_dd_order_from_discount_list(
    mkt_fee: float,
    disc_vals: list[float],
    *,
    mkt_hist: float | None = None,
    ad_hist: float | None = None,
    both_label: str = "both",
) -> str:
    """disc_vals order: you, [doordash, third-party] when columns exist."""
    you = disc_vals[0] if len(disc_vals) > 0 else 0.0
    dd = disc_vals[1] if len(disc_vals) > 1 else 0.0
    tp = disc_vals[2] if len(disc_vals) > 2 else 0.0
    return classify_dd_order(
        marketing_fees=mkt_fee,
        customer_discounts_you=you,
        customer_discounts_doordash=dd,
        customer_discounts_third_party=tp,
        marketing_fees_historical=mkt_hist,
        ad_fee_historical=ad_hist,
        both_label=both_label,
    )
