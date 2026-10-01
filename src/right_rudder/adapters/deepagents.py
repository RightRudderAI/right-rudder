"""deepagents deep-research runs: the callback tool trace (task, tavily_search, write_file, edit_file).

Input: {"calls": [...], "final_message": "..."} or {"calls": [...], "messages": [...]} or a bare
list of calls. Each call carries tool, args, ok, agent, and (for tavily_search) results as [url, title]
pairs. A run that never writes /final_report.md delivers its report in the final message, read the same
way. This mapping matches deep_research_ops.py, the mapping the hosted read validated on the 9/16 runs.
"""
from __future__ import annotations

import json
import re
from typing import Any, List

from ..ops import Op

URL = re.compile(r"https?://[^\s\)\]>\"'`]+")
READ_ONLY = {"read_file", "ls", "glob", "grep", "think_tool"}


def _norm(s: Any) -> str:
    return " ".join(str(s or "").lower().split())


def _norm_url(u: str) -> str:
    return u.strip().rstrip(".,;:").rstrip("/").lower()


def looks_like(doc) -> bool:
    calls = doc.get("calls") if isinstance(doc, dict) else doc
    if not isinstance(calls, list) or not calls or not isinstance(calls[0], dict):
        return False
    tools = {c.get("tool") for c in calls if isinstance(c, dict)}
    return bool(tools & {"task", "tavily_search", "write_file"}) and "args" in calls[0]


def _final_message(doc) -> str:
    if not isinstance(doc, dict):
        return ""
    if isinstance(doc.get("final_message"), str):
        return doc["final_message"]
    msgs = doc.get("messages")
    if isinstance(msgs, list):
        ai = [m for m in msgs if m.get("type") == "ai"]
        if ai:
            c = ai[-1].get("data", {}).get("content")
            return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def load(doc: Any, mapping_path: str = None, **_) -> List[Op]:
    calls = doc.get("calls", doc) if isinstance(doc, dict) else doc
    final = _final_message(doc)
    ops: List[Op] = []
    files: dict = {}

    def emit(op, kind, key, value=None, ok=True, refs=None, source=""):
        ops.append(Op(op=op, kind=kind, key=str(key),
                      value=None if value is None else str(value), ok=bool(ok),
                      refs=[(k, str(v)) for k, v in (refs or [])], step=len(ops), source=source))

    for c in calls:
        name = c.get("tool", "")
        args = c.get("args") or {}
        ok = bool(c.get("ok", True))
        who = c.get("agent") or "orchestrator"
        src = f"{who}.{name}"
        if name in READ_ONLY:
            continue
        if name == "write_todos":
            emit("set", "plan", "todos", json.dumps(args.get("todos"), sort_keys=True), ok, source=src)
        elif name == "task":
            emit("add", "research", "delegations", _norm(args.get("description")), ok, source=src)
        elif name == "tavily_search":
            emit("add", "research", "queries", _norm(args.get("query")), ok, source=src)
            for pair in (c.get("results") or []):
                u = pair[0]
                title = pair[1] if len(pair) > 1 else ""
                emit("set", "source", _norm_url(u), title or "", ok, source=src)
        elif name == "write_file":
            path = str(args.get("file_path") or args.get("path") or "")
            content = str(args.get("content") or "")
            if ok:
                files[path] = content
            refs = []
            if path.endswith("final_report.md"):
                seen = set()
                for m in URL.finditer(content):
                    u = _norm_url(m.group(0))
                    if u not in seen:
                        seen.add(u)
                        refs.append(("source", u))
            emit("set", "file", path, content, ok, refs=refs, source=src)
        elif name == "edit_file":
            path = str(args.get("file_path") or args.get("path") or "")
            old, new = str(args.get("old_string") or ""), str(args.get("new_string") or "")
            cur = files.get(path, "")
            folded = cur.replace(old, new) if args.get("replace_all") else cur.replace(old, new, 1)
            if ok:
                files[path] = folded
            emit("set", "file", path, folded, ok, source=src)

    if not any(k.endswith("final_report.md") for k in files) and final:
        seen, refs = set(), []
        for m in URL.finditer(final):
            u = _norm_url(m.group(0))
            if u not in seen:
                seen.add(u)
                refs.append(("source", u))
        emit("answer", "research", "report", final, True, refs=refs, source="orchestrator.final_message")
    return ops
