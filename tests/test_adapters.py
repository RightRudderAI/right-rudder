import json, os
from fathom_read import load_ops
from fathom_read.cli import EXAMPLES, main


def test_examples_detect_and_normalize():
    expected = {"rename_coherent.json": 10, "rename_starved.json": 10, "knowledge_update.json": 4,
                "order_duplicate.json": 5, "crewai_events.json": 4, "langgraph_history.json": 4}
    for name, n in expected.items():
        ops = load_ops(os.path.join(EXAMPLES, name))
        assert len(ops) == n, name
        assert all(o.op in ("set", "remove", "rename", "add", "answer", "commit") for o in ops)


def test_rejected_edit_is_marked_not_ok():
    ops = load_ops(os.path.join(EXAMPLES, "rename_starved.json"))
    assert sum(1 for o in ops if not o.ok) == 5


def test_openinference_adapter(tmp_path):
    spans = {"initial_files": {"a.py": "guest_id"}, "spans": [
        {"attributes": {"openinference.span.kind": "TOOL", "tool.name": "str_replace_editor",
                        "tool.parameters": json.dumps({"path": "a.py", "old_str": "guest_id", "new_str": "customer_id"}),
                        "output.value": json.dumps({"success": True})}}]}
    p = tmp_path / "trace.json"; p.write_text(json.dumps(spans))
    ops = load_ops(str(p))
    assert [o.value for o in ops] == ["guest_id", "customer_id"]


def test_letta_and_dbos_adapters(tmp_path):
    letta = {"tool_calls": [{"name": "core_memory_replace", "args": {"label": "facts", "new_content": "customer_id"}, "ok": True}],
             "blocks": [{"label": "facts", "value": "customer_id"}], "passages": [{"id": "p1", "text": "guest_id"}]}
    p = tmp_path / "mem.json"; p.write_text(json.dumps(letta))
    assert [o.kind for o in load_ops(str(p))] == ["block", "block", "passage"]
    dbos = {"workflow_id": "w1", "steps": [{"step_name": "set_value", "args": {"key": "plan", "value": "A"}, "ok": True}]}
    p = tmp_path / "steps.json"; p.write_text(json.dumps(dbos))
    ops = load_ops(str(p))
    assert ops[0].key == "plan" and ops[0].value == "A"


def test_custom_map(tmp_path):
    m = {"save_decision": {"op": "set", "kind": "decision", "key": "topic", "value": "text"}}
    mp = tmp_path / "map.json"; mp.write_text(json.dumps(m))
    doc = {"workflow_id": "w", "steps": [{"step_name": "save_decision", "args": {"topic": "db", "text": "postgres"}}]}
    p = tmp_path / "s.json"; p.write_text(json.dumps(doc))
    ops = load_ops(str(p), mapping_path=str(mp))
    assert ops[0].kind == "decision" and ops[0].key == "db" and ops[0].value == "postgres"


def test_cli_ops_only_sends_nothing(capsys):
    assert main(["read", os.path.join(EXAMPLES, "knowledge_update.json"), "--ops"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 4 and out[-1]["op"] == "answer"


def test_openinference_span_status_and_plain_text_errors():
    from fathom_read.adapters import openinference
    def span(name, params, out, status=None):
        s = {"attributes": {"openinference.span.kind": "TOOL", "tool.name": name,
                            "tool.parameters": json.dumps(params), "output.value": out}}
        if status:
            s["status_code"] = status
        return s
    spans = [span("write_file", {"path": "a.py", "content": "x"}, "ok"),
             span("write_file", {"path": "b.py", "content": "y"}, "error: disk quota exceeded"),
             span("write_file", {"path": "c.py", "content": "z"}, "written", status="ERROR")]
    ops = openinference.load({"spans": spans})
    assert [o.ok for o in ops] == [True, False, False]


def test_openinference_arguments_from_input_value_when_parameters_is_a_schema():
    """Arize's CrewAI instrumentor stores the argument schema in tool.parameters and the call in input.value."""
    from fathom_read.adapters import openinference
    schema = json.dumps({"description": "Input for SerperDevTool.", "properties": {"search_query": {"type": "string"}},
                         "required": ["search_query"], "title": "SerperDevToolSchema", "type": "object"})
    spans = [{"attributes": {"openinference.span.kind": "TOOL", "tool.name": "Search the internet with Serper",
                             "tool.parameters": schema, "input.value": json.dumps({"search_query": q})},
              "start_time": i} for i, q in enumerate(["ai in finance", "ai in finance"])]
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"search_the_internet_with_serper": {"op": "add", "kind": "research", "key": "queries", "value": "search_query"}}, f)
        path = f.name
    try:
        ops = openinference.load({"spans": spans}, mapping_path=path)
    finally:
        os.unlink(path)
    assert [(o.op, o.key, o.value) for o in ops] == [("add", "queries", "ai in finance"), ("add", "queries", "ai in finance")]


def test_openinference_arguments_from_parameters_when_they_carry_the_call():
    from fathom_read.adapters import openinference
    spans = [{"attributes": {"openinference.span.kind": "TOOL", "tool.name": "write_record",
                             "tool.parameters": json.dumps({"record": "r0", "content": "customer_id: 1"}),
                             "input.value": json.dumps({"ignored": True})}, "start_time": 0}]
    ops = openinference.load({"spans": spans})
    assert [(o.op, o.kind, o.key, o.value) for o in ops] == [("set", "record", "r0", "customer_id: 1")]
