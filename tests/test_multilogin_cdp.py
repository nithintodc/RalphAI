"""Multilogin CDP URL helpers."""

from multilogin.connect import _automation_type, _cdp_websocket_url, _pick_page_cdp_target


class TestMultiloginCdp:
    def test_default_automation_type_is_playwright(self, monkeypatch):
        monkeypatch.delenv("MULTILOGIN_AUTOMATION_TYPE", raising=False)
        assert _automation_type() == "playwright"

    def test_pick_page_cdp_target_prefers_non_chrome_url(self):
        targets = [
            {
                "type": "page",
                "url": "chrome://newtab/",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/newtab",
            },
            {
                "type": "page",
                "url": "https://merchant-portal.doordash.com/merchant/reports",
                "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/reports",
            },
        ]
        assert _pick_page_cdp_target(targets) == "ws://127.0.0.1:9222/devtools/page/reports"

    def test_cdp_websocket_prefers_browser_version_over_page_targets(self, monkeypatch):
        class ListResp:
            status_code = 200

            @staticmethod
            def json():
                return [
                    {
                        "type": "page",
                        "url": "https://merchant-portal.doordash.com/",
                        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/abc",
                    }
                ]

        class VersionResp:
            status_code = 200

            @staticmethod
            def json():
                return {"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/root"}

        import multilogin.connect as mod

        def fake_get(url, timeout=10):
            if url.endswith("/json/version"):
                return VersionResp()
            if url.endswith("/json/list"):
                return ListResp()
            raise AssertionError(url)

        monkeypatch.setattr(mod.requests, "get", fake_get)
        ws = _cdp_websocket_url("http://127.0.0.1:55555", attempts=1, pause_s=0)
        assert ws == "ws://127.0.0.1:9222/devtools/browser/root"

    def test_cdp_websocket_falls_back_to_json_version(self, monkeypatch):
        class VersionResp:
            status_code = 200

            @staticmethod
            def json():
                return {"webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/abc"}

        import multilogin.connect as mod

        def fake_get(url, timeout=10):
            if url.endswith("/json/list"):
                class EmptyResp:
                    status_code = 200

                    @staticmethod
                    def json():
                        return []

                return EmptyResp()
            if url.endswith("/json/version"):
                return VersionResp()
            raise AssertionError(url)

        monkeypatch.setattr(mod.requests, "get", fake_get)
        ws = _cdp_websocket_url("http://127.0.0.1:55555", attempts=1, pause_s=0)
        assert ws == "ws://127.0.0.1:9222/devtools/browser/abc"
