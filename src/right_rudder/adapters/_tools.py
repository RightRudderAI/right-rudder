"""Shared mapping from tool calls to ops. Adapters that see (tool name, args, result, ok) use this."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..ops import Op

# Default mapping: tool name -> how to build an op from its arguments.
# "key" and "value" name the argument fields; "kind" labels the fact; "op" is the ledger op.
DEFAULT_MAP: Dict[str, Dict[str, Any]] = {
    # coding agents (OpenHands, CodeAct-style editors); content folding lives in the edits adapter
    "str_replace_editor": {"op": "edit"},
    "edit_file": {"op": "edit"},
    "write_file": {"op": "set", "kind": "file", "key": "path", "value": "content"},
    "create_file": {"op": "set", "kind": "file", "key": "path", "value": "content"},
    "delete_file": {"op": "remove", "kind": "file", "key": "path"},
    # record-keeping crews and workflows
    "write_record": {"op": "set", "kind": "record", "key": "record", "value": "content"},
    "update_record": {"op": "set", "kind": "record", "key": "record", "value": "content"},
    "commit_record": {"op": "set", "kind": "record", "key": "record", "value": "content"},
    "set_value": {"op": "set", "kind": "fact", "key": "key", "value": "value"},
    "update_value": {"op": "set", "kind": "fact", "key": "key", "value": "value"},
    "delete_value": {"op": "remove", "kind": "fact", "key": "key"},
    "rename_key": {"op": "rename", "kind": "fact", "key": "old", "to": "new"},
    # Letta memory tools
    "core_memory_append": {"op": "append", "kind": "block", "key": "label", "value": "content"},
    "core_memory_replace": {"op": "set", "kind": "block", "key": "label", "value": "new_content"},
    "memory_replace": {"op": "set", "kind": "block", "key": "label", "value": "new_str"},
    "memory_insert": {"op": "append", "kind": "block", "key": "label", "value": "new_str"},
    "memory_rethink": {"op": "set", "kind": "block", "key": "label", "value": "new_memory"},
    "archival_memory_insert": {"op": "add", "kind": "passage", "key": "archival", "value": "content"},
    # ordering and transactions (web agents, customer-service agents)
    "add_item": {"op": "add", "kind": "order", "key": "cart", "value": "item"},
    "add_to_cart": {"op": "add", "kind": "order", "key": "cart", "value": "item"},
    "remove_item": {"op": "remove_member", "kind": "order", "key": "cart", "value": "item"},
    "place_order": {"op": "commit", "kind": "order", "key": "order"},
    "checkout": {"op": "commit", "kind": "order", "key": "order"},
    "submit": {"op": "commit", "kind": "order", "key": "order"},
    "book_reservation": {"op": "set", "kind": "reservation", "key": "reservation_id", "value": "details"},
    "cancel_reservation": {"op": "remove", "kind": "reservation", "key": "reservation_id"},
}


def _first(args: Dict[str, Any], *names: str) -> Optional[str]:
    for n in names:
        if n in args and args[n] is not None:
            v = args[n]
            return v if isinstance(v, str) else json.dumps(v, sort_keys=True)
    return None


def load_map(path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    m = dict(DEFAULT_MAP)
    if path:
        with open(path) as f:
            m.update(json.load(f))
    return m


def op_from_tool(name: str, args: Any, ok: bool, step: int, mapping: Dict[str, Dict[str, Any]],
                 source: str = "") -> Optional[Op]:
    """Build an op from one tool call, or None when the tool does not write committed state."""
    name = (name or "").strip().lower().replace(" ", "_")
    spec = mapping.get(name)
    if spec is None:
        return None
    if not isinstance(args, dict):
        try:
            args = json.loads(args) if args else {}
        except (TypeError, ValueError):
            args = {}
    kind = spec.get("kind", "fact")
    op = spec["op"]
    key = _first(args, spec.get("key", "key"), "key", "record", "path", "label", "name", "id") or spec.get("key", name)
    value = _first(args, spec.get("value", "value"), "value", "content", "new_str", "new_content", "text")
    if op == "edit":
        return None  # the edits adapter folds these with file contents
    if op == "append":
        return Op("set", kind, key, value=value, ok=ok, step=step, source=source or name)
    if op == "remove_member":
        return Op("remove", kind, f"{key}:{value}", ok=ok, step=step, source=source or name)
    if op == "rename":
        to = _first(args, spec.get("to", "new"), "new", "to")
        return Op("rename", kind, key, to=to, ok=ok, step=step, source=source or name)
    if op == "commit":
        return Op("commit", kind, key, ok=ok, step=step, source=source or name)
    return Op(op, kind, key, value=value, ok=ok, step=step, source=source or name)
