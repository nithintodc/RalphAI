from agents.deepdive.agent import run as deepdive_run
from agents.marketingreco.agent import run as reco_run
from agents.campaign_setup.agent import run as setup_run
from agents.campaign_review.agent import run as review_run


def test_review(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    deepdive_run(operator_id="z")
    reco_run("z")
    setup_run("z", campaign_type="ads")
    out = review_run("z")
    assert out["operator_id"] == "z"
    assert "campaign_reviews" in out
