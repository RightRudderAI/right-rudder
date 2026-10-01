"""OpenManus run logs: the plan with per-step status and the agent's tool calls.

OpenManus run logs: the planning flow's plan with per-step status, and the Manus agent's tool calls.

Input: the text of an OpenManus log (loguru lines from app.flow.planning and app.agent.toolcall),
as produced by `python run_flow.py`. Pass the log's text, or a JSON document {"log": text}.

Committed state is the plan and the workspace. Each plan step becomes a fact (kind "plan_step",
key "<plan_id>:<n>") when the plan is created and is removed when the flow marks it completed; a
later execution of a removed step is a stale reference, which is what step repetition looks like in
the record. A file the editor creates becomes a fact (kind "file"), a str_replace folds onto it, and
a rejected editor call leaves nothing behind. Browser actions and python execution read the world
and write nothing, so they produce no ops. A terminate call is an answer keyed on the step it ends.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from ..ops import Op

_TS = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+ \| (\w+)\s*\| ([\w.]+):(\w+):(\d+) - (.*)$")
_PLAN_ID = re.compile(r"ID: (plan_\d+)")
_STEP_LINE = re.compile(r"^(\d+)\. \[.\] (.*)$")
_MARKED = re.compile(r"Marked step (\d+) as completed in plan (plan_\d+)")
_TOOL_PREP = re.compile(r"Tools being prepared: \[(.*)\]")
_TOOL_ARGS = re.compile(r"Tool arguments: (.*)$")
_TOOL_DONE = re.compile(r"Tool '([\w_]+)' completed its mission! Result: (.*)$")
_EXEC_ERR = re.compile(r"Error executing step (\d+):")

MARKER = "app.agent.toolcall"
DEFAULT_PLAN_STEPS = ("Analyze request", "Execute task", "Verify results")
_OUT_PREFIX = re.compile(r"^Observed output of cmd `\w+` executed:\s*")


def _accepted(out: str) -> bool:
    """A tool result the framework reported as an error marks the call as rejected."""
    body = _OUT_PREFIX.sub("", out).strip()
    head = body.split("\n", 1)[0].lower()
    return not (head.startswith("error") or head.startswith("traceback") or " failed:" in head)


def _parse(text: str):
    """Yield (level, module, func, message, trailing_lines) per loguru record."""
    recs = []
    for line in text.splitlines():
        m = _TS.match(line)
        if m:
            recs.append([m.group(1), m.group(2), m.group(3), m.group(5), []])
        elif recs:
            recs[-1][4].append(line)
    return recs


def load(doc: Any, **_) -> List[Op]:
    text = doc.get("log", "") if isinstance(doc, dict) else str(doc)
    ops: List[Op] = []
    files: Dict[str, str] = {}
    plan: Optional[str] = None
    pending_tool: Optional[str] = None
    pending_args: Any = None
    step = 0

    def emit(op: Op) -> None:
        nonlocal step
        op.step = step
        step += 1
        ops.append(op)

    for level, module, func, msg, tail in _parse(text):
        if module == "app.flow.planning" and func == "_create_initial_plan" and "Creating initial plan with ID" in msg:
            m = _PLAN_ID.search(msg)
            plan = m.group(1) if m else "plan"
            continue
        if module == "app.flow.planning" and func == "_create_initial_plan" and "Creating default plan" in msg:
            # The flow falls back to its built-in three-step plan and does not print it.
            for i, name in enumerate(DEFAULT_PLAN_STEPS):
                emit(Op("set", "plan_step", f"{plan or 'plan'}:{i}", value=name, source="default_plan"))
            continue
        if module == "app.flow.planning" and func == "_create_initial_plan" and "Plan creation result" in msg:
            m = _PLAN_ID.search(msg) or _PLAN_ID.search("\n".join(tail))
            plan = m.group(1) if m else "plan"
            for t in tail:
                s = _STEP_LINE.match(t.strip())
                if s:
                    emit(Op("set", "plan_step", f"{plan}:{s.group(1)}", value=s.group(2).strip(), source="plan"))
            continue
        if module == "app.flow.planning" and func == "_mark_step_completed":
            m = _MARKED.search(msg)
            if m:
                key = f"{m.group(2)}:{m.group(1)}"
                emit(Op("add", "plan", f"{m.group(2)}:completed", value=m.group(1), refs=[("plan_step", key)], source="mark_step_completed"))
                emit(Op("remove", "plan_step", key, source="mark_step_completed"))
            continue
        if module == "app.flow.planning" and func == "_execute_step" and level == "ERROR":
            m = _EXEC_ERR.search(msg)
            if m and plan:
                emit(Op("set", "plan_step", f"{plan}:{m.group(1)}", value=None, ok=False, refs=[("plan_step", f"{plan}:{m.group(1)}")], source="execute_step_error"))
            continue
        if module != MARKER:
            continue
        m = _TOOL_PREP.search(msg)
        if m:
            names = [n.strip().strip("'\"") for n in m.group(1).split(",") if n.strip()]
            pending_tool = names[0] if names else None
            pending_args = None
            continue
        m = _TOOL_ARGS.search(msg)
        if m:
            try:
                pending_args = json.loads(m.group(1))
            except ValueError:
                pending_args = {}
            continue
        m = _TOOL_DONE.search(msg)
        if m:
            name = m.group(1)
            out = "\n".join([m.group(2)] + tail).strip()
            ok = _accepted(out)
            args = pending_args if isinstance(pending_args, dict) else {}
            if name == "str_replace_editor":
                cmd = args.get("command")
                path = str(args.get("path", ""))
                if cmd == "create":
                    if ok:
                        files[path] = str(args.get("file_text", ""))
                    emit(Op("set", "file", path, value=str(args.get("file_text", "")), ok=ok, source="create"))
                elif cmd == "str_replace":
                    old, new = args.get("old_str"), args.get("new_str")
                    applied = bool(ok and path in files and old and old in files[path])
                    if applied:
                        files[path] = files[path].replace(old, new or "")
                    emit(Op("set", "file", path, value=files.get(path), ok=applied, refs=[("file", path)], source="str_replace"))
                elif cmd == "insert":
                    applied = bool(ok and path in files)
                    if applied:
                        files[path] = files[path] + "\n" + str(args.get("new_str", ""))
                    emit(Op("set", "file", path, value=files.get(path), ok=applied, refs=[("file", path)], source="insert"))
            elif name == "terminate":
                emit(Op("answer", "task", plan or "task", value=str(args.get("status", out[-80:])), source="terminate"))
            pending_tool, pending_args = None, None
            continue
    return ops


def looks_like(text: str) -> bool:
    return "app.agent.toolcall" in text and "app.flow.planning" in text
