"""HyperAgent trajectories: the regions and symbols the Editor intern wrote.

HyperAgent trajectories: the Planner's messages to its Navigator, Editor and Executor interns,
with each intern's Thought and Action, as logged on SWE-bench-Lite.

Input: {"instance_id", "trajectory": [log line, ...]} as the MAST corpus stores it, or the
trajectory text itself.

Committed state is what the Editor wrote. Every `editor._run(relative_file_path=..., start_line=N,
end_line=M, patch=patch)` call becomes a "set" on the region "<path>:<N>-<M>" carrying the patch
text and a "set" on each symbol the patch defines (kind "symbol", "<module>.<name>") carrying the
patch text as its body, so an edit applied a second time in identical form is a set of the value
its region already holds, which the read reports as a duplicate commit, and a symbol rewritten
back to an earlier body reads as a superseded value. The log does not carry the editor tool's result, so
every edit is taken as accepted. Only the Editor intern's own responses count; the Editor->Planner
relay repeats them, the logger writes many records twice in a row, and the prompt template with its
worked example is echoed into the log, and all three are skipped. Navigator lookups and Executor
runs are reads and produce no ops. The Planner's Final Answer is an answer standing on every
region edited.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from ..ops import Op
from ._code import python_symbols, module_name

_EDIT = re.compile(r"editor\._run\(\s*relative_file_path\s*=\s*['\"]([^'\"]+)['\"]\s*,\s*start_line\s*=\s*(\d+)\s*,\s*end_line\s*=\s*(\d+)\s*,\s*patch\s*=\s*(\w+)\s*\)")
_PATCH = re.compile(r"(\w+)\s*=\s*(?:'''|\"\"\")(.*?)(?:'''|\"\"\")", re.S)
_RESPONSE = re.compile(r"^HyperAgent_\S+ - INFO - ([A-Za-z\->' ]+?)(?:'s Response)?: ")
_FINAL = re.compile(r"Final Answer:\s*(.*)", re.S)



def _messages(lines: List[str]) -> List[Dict[str, str]]:
    """Group the flat log into messages by their `HyperAgent_... - INFO - <who>:` prefix."""
    msgs: List[Dict[str, str]] = []
    for l in lines:
        m = _RESPONSE.match(l)
        if m:
            msgs.append({"who": m.group(1).strip(), "text": l[m.end():]})
        elif msgs:
            msgs[-1]["text"] += "\n" + l
        else:
            msgs.append({"who": "log", "text": l})
    return msgs


def load(doc: Any, **_) -> List[Op]:
    if isinstance(doc, dict):
        lines = doc.get("trajectory", [])
        lines = lines if isinstance(lines, list) else str(lines).splitlines()
    elif isinstance(doc, list):
        lines = [str(x) for x in doc]
    else:
        text = str(doc)
        if text.startswith("instance_id:") and "\ntrajectory:" in text:
            text = text.split("\ntrajectory:", 1)[1]           # the MAD corpus's YAML-like dump
            lines = [l[2:] if l.startswith("  ") else l for l in text.splitlines()]
        else:
            lines = text.splitlines()
    ops: List[Op] = []
    edited: List[str] = []
    last_editor_text = None
    for msg in _messages(lines):
        who, text = msg["who"], msg["text"]
        if who.startswith("Inner-Editor"):
            # The logger writes many records twice in a row; a byte-identical repeat is the log, not the agent.
            if text == last_editor_text:
                continue
            last_editor_text = text
            if text.lstrip().startswith("Use the following format"):
                continue  # the intern's prompt template, echoed with its worked example
            patches = {name: body for name, body in _PATCH.findall(text)}
            for path, start, end, var in _EDIT.findall(text):
                patch = patches.get(var, "")
                region = f"{path}:{start}-{end}"
                for sym in sorted(python_symbols(module_name(path), patch)):
                    ops.append(Op("set", "symbol", sym, value=patch.strip(), step=len(ops), source="editor"))
                ops.append(Op("set", "region", region, value=patch.strip(), step=len(ops), source="editor"))
                if region not in edited:
                    edited.append(region)
        elif who.startswith("Planner"):
            m = _FINAL.search(text)
            if m and edited:
                ops.append(Op("answer", "answer", "final", value=m.group(1).strip()[:200], refs=[("region", r) for r in edited],
                              step=len(ops), source="planner_final"))
    return ops


def looks_like(text: str) -> bool:
    return "HyperAgent_" in text and "Intern Name:" in text
