"""reporting_browser_use fork registry."""

from shared.reporting_browser_use_forks import (
    ALL_FORK_IDS,
    fork_metadata,
    is_fork_runnable,
    list_fork_metadata,
)


class TestReportingBrowserUseForks:
    def test_five_forks_registered(self):
        assert len(ALL_FORK_IDS) == 5

    def test_main_fork_is_runnable(self):
        assert is_fork_runnable("reporting_browser_use")

    def test_stub_forks_not_runnable(self):
        for fid in ("reporting_browser_use_new",):
            assert not is_fork_runnable(fid)

    def test_browser_fork_uses_browser_use_key(self):
        meta = fork_metadata("reporting_browser_use_browser")
        assert meta["llm_env_key"] == "BROWSER_USE_API_KEY"

    def test_list_metadata_matches_ids(self):
        ids = {m["id"] for m in list_fork_metadata()}
        assert ids == set(ALL_FORK_IDS)
