from agents.deepdive.agent import run as deepdive_run
from agents.marketingreco.agent import run as reco_run


def test_marketingreco_after_deepdive(tmp_path, monkeypatch):
    monkeypatch.setenv("TODC_DATA_DIR", str(tmp_path))
    deepdive_run(operator_id="x")
    out = reco_run("x")
    assert out["operator_id"] == "x"
    assert out["approval_status"] == "pending"
    assert len(out["recommended_campaigns"]) >= 1
