"""
Letta (MemGPT) memory: the blocks and passages the agent persists, and the edit calls that produced them.

Input: {"blocks": [{"label", "value"}], "passages": [{"text"}], "tool_calls": [{"name", "args", "ok"}]}.
Blocks and passages give the final committed memory; tool_calls give the stream. Export with
agents.blocks.list, agents.passages.list, and the tool_call messages from agents.messages.list.
"""
from __future__ import annotations

from typing import Any, List

from ..ops import Op
from ._tools import op_from_tool, load_map


def load(doc: Any, mapping_path: str = None, **_) -> List[Op]:
    mapping = load_map(mapping_path)
    ops: List[Op] = []
    step = 0
    for tc in doc.get("tool_calls", []) or []:
        op = op_from_tool(tc.get("name", ""), tc.get("args"), bool(tc.get("ok", True)), step, mapping, source="tool_call")
        if op is not None:
            ops.append(op)
            step += 1
    # The persisted memory at the end of the run, as the final committed values.
    for b in doc.get("blocks", []) or []:
        ops.append(Op("set", "block", str(b.get("label", "block")), value=str(b.get("value", "")), step=step, source="persisted"))
        step += 1
    for i, p in enumerate(doc.get("passages", []) or []):
        ops.append(Op("set", "passage", str(p.get("id", i)), value=str(p.get("text", "")), step=step, source="persisted"))
        step += 1
    return ops
