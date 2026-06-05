"""DoorDash order origin classification (register / buckets / health check parity)."""

import pytest

from shared.dd_order_classification import (
    DD_ADS_FEE_THRESHOLD,
    classify_dd_order,
    classify_dd_order_from_discount_list,
)


def test_organic_all_zeros():
    assert classify_dd_order(
        marketing_fees=0,
        customer_discounts_you=0,
        customer_discounts_doordash=0,
        marketing_fees_historical=0,
        ad_fee_historical=0,
    ) == "organic"


def test_promo_you_funded_only():
    assert classify_dd_order(
        marketing_fees=0,
        customer_discounts_you=-4.89,
        marketing_fees_historical=-4.89,
    ) == "promo"


def test_promo_dd_funded_only():
    assert classify_dd_order(
        marketing_fees=0,
        customer_discounts_doordash=-5.03,
    ) == "promo"


def test_promo_historical_only():
    assert classify_dd_order(
        marketing_fees=0,
        customer_discounts_you=0,
        marketing_fees_historical=-5.99,
    ) == "promo"


def test_ads_only():
    assert classify_dd_order(
        marketing_fees=-3.0,
        customer_discounts_you=0,
        ad_fee_historical=-3.0,
    ) == "ads"


def test_both_strict_threshold():
    assert classify_dd_order(
        marketing_fees=-3.0,
        customer_discounts_you=-4.0,
    ) == "both"


def test_mkt_exactly_099_is_promo_not_both():
    """21802C73 case: |mkt| == 0.99 is not > threshold."""
    assert classify_dd_order(
        marketing_fees=-0.99,
        customer_discounts_you=-4.31,
        marketing_fees_historical=-5.30,
    ) == "promo"


def test_both_requires_mkt_above_threshold():
    assert classify_dd_order(
        marketing_fees=-(DD_ADS_FEE_THRESHOLD + 0.01),
        customer_discounts_you=-2.0,
    ) == "both"


def test_skips_missing_historical_columns():
    assert classify_dd_order(
        marketing_fees=0,
        customer_discounts_you=0,
        marketing_fees_historical=None,
        ad_fee_historical=None,
    ) == "organic"


def test_classify_from_discount_list_padding():
    assert classify_dd_order_from_discount_list(-3.0, [-1.0]) == "both"
    assert classify_dd_order_from_discount_list(0, [0, -5.0, 0]) == "promo"
