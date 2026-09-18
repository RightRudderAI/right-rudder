"""The repair client: the verdict type, the prompt note, and the CLI wiring, with the service stubbed."""
import json
import fathom_read
from fathom_read import RegroundVerdict, Op
from fathom_read import cli


def _verdict(decision="reground"):
    return {"decision": decision, "keep": [] if decision == "reground" else ["c"], "kept": [],
            "dropped": [{"index": 0, "op": "add", "kind": "research", "key": "queries", "value": "a", "findings": ["duplicate_commit"]}],
            "facts": [{"kind": "research", "key": "queries", "holds": ["a", "b"], "truncated": False, "because": "duplicate_commit"},
                      {"kind": "record", "key": "r0", "renamed_to": "c0", "because": "stale_reference"},
                      {"kind": "field", "key": "owner", "value": "bob", "replaced": "alice", "because": "superseded_value"},
                      {"kind": "order", "committed_at": 7, "because": "post_commit_mutation"}],
            "proposals": 1, "read": {"coherent": True, "findings": 0, "ops_read": 2, "live_facts": 0}}


def test_verdict_roundtrip_and_note():
    v = RegroundVerdict.from_dict(_verdict())
    assert v.decision == "reground" and v.as_dict()["facts"][0]["holds"] == ["a", "b"]
    note = v.prompt_note(["a"])
    assert "already holds: 'a', 'b'" in note
    assert "renamed to 'c0'" in note
    assert "now carries 'bob', which replaced 'alice'" in note
    assert "committed at step 7" in note
    assert "Every proposal ('a') contradicts" in note


def test_cli_reground_exit_codes(monkeypatch, tmp_path, capsys):
    ops = [{"op": "add", "kind": "research", "key": "queries", "value": "a"}]
    p = tmp_path / "ops.json"
    p.write_text(json.dumps(ops))
    calls = {}

    def fake(ops_, proposals, supersede=None, key=None, endpoint=None):
        calls["proposals"] = list(proposals)
        return RegroundVerdict.from_dict(_verdict(calls.get("decision", "reground")))

    monkeypatch.setattr(cli, "reground", fake)
    rc = cli.main(["reground", str(p), "--proposals", json.dumps([{"op": "add", "kind": "research", "key": "queries", "value": "a"}])])
    assert rc == 3 and calls["proposals"][0]["value"] == "a"
    out = capsys.readouterr().out
    assert "reground (1 proposal(s)" in out and "COMMITTED STATE CHECK" in out
    calls["decision"] = "filter"
    rc = cli.main(["reground", str(p), "--proposals", "[]", "--json"])
    assert rc == 0 and json.loads(capsys.readouterr().out)["decision"] == "filter"


def test_reground_exported():
    assert callable(fathom_read.reground) and callable(fathom_read.request_key)
    assert fathom_read.__version__ == "0.6.0"
