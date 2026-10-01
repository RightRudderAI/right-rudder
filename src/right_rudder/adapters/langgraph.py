"""
LangGraph state history: the checkpoint lineage from graph.get_state_history(config).

Input: a list of snapshots, each with "values" (the channel values at that step), newest
first as LangGraph returns them, or {"snapshots": [...]}. The adapter diffs consecutive
snapshots and emits one op per changed channel: a scalar or string channel that changed is a
"set"; a list channel that grew is an "add" per new element. Every checkpoint is a
successful commit, so ok is always true here; the read then checks what those commits say
against one another.

To export from a running graph:
    import json
    history = [{"values": s.values, "step": s.metadata.get("step")} for s in graph.get_state_history(config)]
    json.dump(history, open("history.json", "w"), default=str)
"""
from __future__ import annotations

import json
from typing import Any, List

from ..ops import Op


def _as_text(v: Any) -> str:
    return v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=str)


def load(doc: Any, **_) -> List[Op]:
    snaps = doc.get("snapshots", doc.get("history", [])) if isinstance(doc, dict) else doc
    snaps = list(snaps)
    if len(snaps) > 1:
        # get_state_history returns newest first; put them in run order.
        s0 = snaps[0].get("step", snaps[0].get("metadata", {}).get("step"))
        s1 = snaps[-1].get("step", snaps[-1].get("metadata", {}).get("step"))
        if s0 is None or s1 is None or s0 > s1:
            snaps = snaps[::-1]
    ops: List[Op] = []
    prev: dict = {}
    step = 0
    for snap in snaps:
        values = snap.get("values", {}) or {}
        for chan, val in values.items():
            old = prev.get(chan)
            if isinstance(val, list) and isinstance(old, list) and len(val) >= len(old) and val[:len(old)] == old:
                for item in val[len(old):]:
                    ops.append(Op("add", "channel", chan, value=_as_text(item), step=step, source="checkpoint"))
                    step += 1
            elif isinstance(val, list) and old is None:
                for item in val:
                    ops.append(Op("add", "channel", chan, value=_as_text(item), step=step, source="checkpoint"))
                    step += 1
            elif val != old:
                ops.append(Op("set", "channel", chan, value=_as_text(val), step=step, source="checkpoint"))
                step += 1
        prev = values
    return ops
