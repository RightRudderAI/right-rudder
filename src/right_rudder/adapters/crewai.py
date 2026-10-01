"""
CrewAI event logs: the events the crew's event bus already emits.

Input: a list of events (or {"events": [...]}) with "type" in tool_usage_finished,
tool_usage_error, task_completed; tool events carry tool_name and tool_args. A write tool's
arguments name the record and the content committed to it; a task_completed event commits
the task's output under the task name. Capture them with a listener on crewai's event bus.
"""
from __future__ import annotations

from typing import Any, List

from ..ops import Op
from ._tools import op_from_tool, load_map


def load(doc: Any, mapping_path: str = None, **_) -> List[Op]:
    events = doc.get("events", []) if isinstance(doc, dict) else doc
    mapping = load_map(mapping_path)
    ops: List[Op] = []
    for i, ev in enumerate(events):
        t = (ev.get("type") or ev.get("_type") or "").replace("Event", "").lower()
        t = {"toolusagefinished": "tool_usage_finished", "toolusageerror": "tool_usage_error",
             "taskcompleted": "task_completed"}.get(t, t)
        if t in ("tool_usage_finished", "tool_usage_error"):
            ok = t == "tool_usage_finished" and not bool(ev.get("failure"))
            op = op_from_tool(ev.get("tool_name", ""), ev.get("tool_args"), ok, i, mapping, source=t)
            if op is not None:
                ops.append(op)
        elif t == "task_completed":
            name = ev.get("task_name") or ev.get("task") or f"task_{i}"
            out = ev.get("output") or ev.get("raw") or ""
            ops.append(Op("set", "task", str(name), value=str(out), ok=True, step=i, source="task_completed"))
    return ops
