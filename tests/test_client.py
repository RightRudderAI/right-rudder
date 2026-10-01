import io, json
import urllib.request
from right_rudder import Op, read, Verdict


class _Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_client_posts_ops_and_parses_verdict(monkeypatch):
    seen = {}
    def fake_urlopen(req, timeout=0):
        seen["url"] = req.full_url; seen["auth"] = req.get_header("Authorization"); seen["body"] = json.loads(req.data)
        return _Resp(json.dumps({"coherent": False, "ops_read": 2, "ops_rejected": 0, "live_facts": 1,
                                 "findings": [{"kind": "superseded_value", "step": 1, "key": "k", "detail": "d", "cites": 0}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    v = read([Op("set", "fact", "k", value="a"), Op("answer", "fact", "k", value="a")], supersede=[("x", "y")], key="k_test", endpoint="https://example.test/v1/read")
    assert isinstance(v, Verdict) and not v.coherent and v.findings[0].kind == "superseded_value"
    assert seen["auth"] == "Bearer k_test" and seen["body"]["supersede"] == [["x", "y"]] and len(seen["body"]["ops"]) == 2
