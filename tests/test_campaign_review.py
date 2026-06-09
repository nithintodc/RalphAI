from agents.campaign_setup.agent import run as setup_run
from agents.health_check.campaign_review import run as review_run

from tests.helpers import write_min_deepdive, write_min_marketing_plan


def test_review(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    write_min_deepdive(tmp_path, "z")
    write_min_marketing_plan(tmp_path, "z")
    setup_run("z", campaign_type="ads")
    out = review_run("z")
    assert out["operator_id"] == "z"
    assert "campaign_reviews" in out


def test_campaign_review_manual_mode_metrics(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))

    promo = tmp_path / "MARKETING_PROMOTION_test.csv"
    promo.write_text(
        "Campaign name,Orders,Sales,Customer discounts from marketing | (funded by you),New customers acquired,Impressions,Clicks\n"
        "Promo A,10,300,-60,6,1200,90\n",
        encoding="utf-8",
    )
    sponsored = tmp_path / "MARKETING_SPONSORED_LISTING_test.csv"
    sponsored.write_text(
        "Campaign name,Orders,Sales,Marketing fees | (including any applicable taxes),Impressions,Clicks\n"
        "Ads A,8,200,-40,1000,70\n",
        encoding="utf-8",
    )

    active = {
        "campaigns_created": [
            {"campaign_id": "c1", "campaign_name": "Promo A", "campaign_type": "promo"},
            {"campaign_id": "c2", "campaign_name": "Ads A", "campaign_type": "sponsored_listing"},
        ]
    }
    out = review_run(
        "z",
        mode="manual",
        data_files=[str(promo), str(sponsored)],
        active_campaigns=active,
    )
    assert out["operator_id"] == "z"
    assert out["mode"] == "manual"
    assert "summary_metrics" in out
    assert out["summary_metrics"]["combined"]["orders"] == 18.0
    assert out["summary_metrics"]["combined"]["clicks"] == 160.0
    assert len(out["campaign_reviews"]) == 2


def test_campaign_review_equal_pre_post_windows(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    # 3-day campaign Jan 10–12; pre window is Jan 7–9 (same length)
    hdr = (
        "Date,Is self serve campaign,Campaign ID,Campaign name,Campaign start date,Campaign end date,"
        "Orders,Sales,Customer discounts from marketing | (funded by you),"
        "New customers acquired,Impressions,Clicks\n"
    )
    rows = []
    for d, o, s, disc, imp, clk in [
        ("2026-01-07", 1, 20, -5, 100, 10),
        ("2026-01-08", 2, 40, -10, 200, 20),
        ("2026-01-09", 1, 25, -5, 150, 15),
        ("2026-01-10", 4, 120, -30, 400, 40),
        ("2026-01-11", 2, 60, -15, 300, 30),
        ("2026-01-12", 3, 90, -20, 350, 35),
    ]:
        rows.append(
            f"{d},false,cid-1,Winter Promo,2026-01-10,2026-01-12,{o},{s},{disc},0,{imp},{clk}\n"
        )
    promo = tmp_path / "MARKETING_PROMOTION_window.csv"
    promo.write_text(hdr + "".join(rows), encoding="utf-8")

    active = {
        "campaigns_created": [
            {"campaign_id": "c1", "campaign_name": "Winter Promo", "campaign_type": "promo"},
        ]
    }
    out = review_run("z", mode="manual", data_files=[str(promo)], active_campaigns=active)
    assert out["mode"] == "manual"
    cr = out["campaign_reviews"][0]
    assert cr["post_window_days"] == 3
    assert cr["pre_window_days"] == 3
    assert cr["pre_data_coverage_pct"] == 100.0
    assert cr["pre_metrics"]["orders"] == 4.0
    assert cr["post_metrics"]["orders"] == 9.0
    cmp_tbl = out["summary_metrics"]["campaign_comparison"]
    assert len(cmp_tbl) == 1
    assert cmp_tbl[0]["rank"] == 1
    assert cmp_tbl[0]["post_window_days"] == 3
