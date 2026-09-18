import json

from fathom_read import load_ops
from fathom_read.adapters import detect


def _trace():
    # an orchestrator that delegates the same task twice (a duplicate delegation), a sub-agent
    # search that returns a source, and a final report that cites a slug one transposition off it
    return {
        "calls": [
            {"tool": "task", "args": {"description": "research memory systems"}, "ok": True, "agent": "orchestrator"},
            {"tool": "task", "args": {"description": "research memory systems"}, "ok": True, "agent": "orchestrator"},
            {"tool": "tavily_search", "args": {"query": "cognee vs zep"}, "ok": True,
             "agent": "research-agent (task 1)",
             "results": [["https://example.com/cognee-vs-zep-vs-mem0", "Cognee vs Zep vs Mem0"]]},
            {"tool": "write_file", "args": {"file_path": "/final_report.md",
                                            "content": "See https://example.com/cognee-vs-mem0-vs-zep for the comparison."},
             "ok": True, "agent": "research-agent (task 1)"},
        ],
        "final_message": "",
    }


def test_deepagents_detects():
    assert detect(_trace()) == "deepagents"
    assert detect(_trace()["calls"]) == "deepagents"


def test_deepagents_ops(tmp_path):
    p = tmp_path / "trace.json"
    p.write_text(json.dumps(_trace()))
    ops = load_ops(str(p))

    sig = [(o.op, o.kind, o.key) for o in ops]
    # both delegations map into the run-wide collection, so the read can catch the duplicate
    assert sig.count(("add", "research", "delegations")) == 2
    # the fetched source is held
    assert any(o.kind == "source" for o in ops)
    # the report is a file set that carries the cited url as a source ref, the stale-citation path
    report = [o for o in ops if o.op == "set" and o.kind == "file" and o.key.endswith("final_report.md")]
    assert report and any(k == "source" for k, _v in report[-1].refs)


def test_registry_unbroken(tmp_path):
    # the crewai example still detects and loads, so adding deepagents did not disturb the table
    crewai = {"events": [{"type": "tool_usage_finished", "tool_name": "write_record",
                          "tool_args": {"record": "r0", "content": "customer_id: 1"}}]}
    p = tmp_path / "c.json"
    p.write_text(json.dumps(crewai))
    assert detect(crewai) == "crewai"
    assert len(load_ops(str(p))) == 1
