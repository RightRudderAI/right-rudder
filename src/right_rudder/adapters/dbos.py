"""
DBOS step streams: the inputs and outputs of each step in a workflow, in order.

Input: {"workflow_id": "...", "steps": [{"step_name", "args", "result", "ok"}]} or a bare list.
Step names map to ops through the tool mapping (pass --map for your own step names).
"""
from __future__ import annotations

from typing import Any, List

from ..ops import Op
from ._tools import op_from_tool, load_map


def load(doc: Any, mapping_path: str = None, **_) -> List[Op]:
    steps = doc.get("steps", []) if isinstance(doc, dict) else doc
    mapping = load_map(mapping_path)
    ops: List[Op] = []
    for i, s in enumerate(steps):
        ok = bool(s.get("ok", True)) and not bool(s.get("error"))
        args = s.get("args") or s.get("inputs") or {}
        op = op_from_tool(s.get("step_name") or s.get("name", ""), args, ok, i, mapping, source="step")
        if op is not None:
            ops.append(op)
    return ops
