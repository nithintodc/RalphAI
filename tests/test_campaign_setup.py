from agents.marketingreco.agent import run as reco_run
from agents.campaign_setup.agent import run as setup_run

from tests.helpers import write_min_deepdive


def test_campaign_setup_ads(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    write_min_deepdive(tmp_path, "y")
    reco_run("y")
    out = setup_run("y", campaign_type="ads")
    assert out["operator_id"] == "y"
    assert "review_scheduled_at" in out
