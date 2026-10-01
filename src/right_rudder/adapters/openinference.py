"""
OpenInference traces, the span format Arize Phoenix stores.

Input: a list of spans, each with an "attributes" dict carrying openinference.span.kind,
tool.name, tool.parameters (or input.value), and output.value; or {"spans": [...]}. Only TOOL spans
matter. Some instrumentors (Arize's CrewAI instrumentor among them) put the tool's argument schema in
tool.parameters and the call's actual arguments in input.value; when tool.parameters is missing or
reads as a schema, the arguments come from input.value. Edit tools fold through the edits adapter when
the document carries "initial_files".
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

from ..ops import Op
from . import edits as _edits
from ._tools import op_from_tool, load_map

KIND = "openinference.span.kind"
TOOL_NAME = "tool.name"
TOOL_PARAMS = "tool.parameters"
INPUT = "input.value"
OUTPUT = "output.value"


def _parse(v, default=None):
    if v is None:
        return default
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return default


def _looks_like_schema(params: Any) -> bool:
    return isinstance(params, dict) and ("properties" in params or params.get("type") == "object" and "properties" in params)


def _arguments(a: Dict[str, Any]) -> Dict[str, Any]:
    """The call's arguments: tool.parameters when it carries them, else input.value."""
    params = _parse(a.get(TOOL_PARAMS), None)
    if isinstance(params, dict) and params and not _looks_like_schema(params):
        return params
    inp = _parse(a.get(INPUT), None)
    if isinstance(inp, dict):
        return inp
    return params if isinstance(params, dict) else {}


def load(doc: Any, mapping_path: str = None, **_) -> List[Op]:
    spans = doc.get("spans", []) if isinstance(doc, dict) else doc
    initial_files = doc.get("initial_files") if isinstance(doc, dict) else None
    mapping = load_map(mapping_path)
    tool_spans: List[Dict[str, Any]] = []
    for sp in spans:
        a = sp.get("attributes", sp)
        if str(a.get(KIND, "")).upper() == "TOOL":
            status = sp.get("status_code")
            if status is None:
                status = sp.get("status")
                if isinstance(status, dict):
                    status = status.get("code", status.get("status_code"))
            a = dict(a)
            a["_span_error"] = str(status or "").upper() in ("ERROR", "STATUS_CODE_ERROR", "2")
            tool_spans.append(a)
    tool_spans.sort(key=lambda a: a.get("start_time", a.get("start", 0)) or 0)

    edit_records = []
    ops: List[Op] = []
    for i, a in enumerate(tool_spans):
        name = a.get(TOOL_NAME, "")
        params = _arguments(a)
        raw_out = a.get(OUTPUT)
        ret = _parse(raw_out, raw_out)
        ok = not a.get("_span_error", False)
        if not ok:
            pass  # the span itself reports failure
        elif isinstance(ret, dict) and "success" in ret:
            ok = bool(ret["success"])
        elif isinstance(ret, dict) and ret.get("error"):
            ok = False
        elif isinstance(ret, str) and ret.lower().startswith("error"):
            ok = False
        if str(name).strip().lower() in _edits.EDIT_TOOLS:
            edit_records.append({"tool": name, "args": params, "ok": ok})
            continue
        op = op_from_tool(name, params, ok, i, mapping, source="span")
        if op is not None:
            ops.append(op)
    if edit_records:
        ops = _edits.load({"initial_files": initial_files or {}, "edits": edit_records}) + ops
    return ops
