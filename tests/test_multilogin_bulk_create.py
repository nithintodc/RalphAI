"""Multilogin bulk profile creation helpers."""

from multilogin.connect import parse_multilogin_proxy_string

PROXY = (
    "gate.multilogin.com:1080:"
    "2235439324_289b34cb_e0e8_4128_adc9_855b8406f1f3_multilogin_com-country-us-sid-jJjr0eFg-ttl-1h-filter-medium:"
    "71cdxsor65"
)


class TestMultiloginBulkCreate:
    def test_parse_proxy_string(self):
        p = parse_multilogin_proxy_string(PROXY)
        assert p["host"] == "gate.multilogin.com"
        assert p["port"] == "1080"
        assert "multilogin_com-country-us" in p["username"]
        assert p["password"] == "71cdxsor65"
