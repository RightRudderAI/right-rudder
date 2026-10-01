"""
Coding-agent edit logs: str_replace-style edits over a set of files.

Input: {"initial_files": {path: content}, "edits": [{"tool": "str_replace_editor",
        "args": {"path", "old_str", "new_str"}, "ok": true}, ...], "done": true}
or a bare list of edit records. The adapter folds each successful edit onto the file it
targets and emits one "set" op per edit with the file's new content, so the read can see what
the agent actually left in each file. A rejected edit changes nothing.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..ops import Op

EDIT_TOOLS = {"str_replace_editor", "edit_file", "str_replace", "apply_patch"}


def load(doc: Any, **_) -> List[Op]:
    if isinstance(doc, list):
        doc = {"edits": doc}
    files: Dict[str, str] = dict(doc.get("initial_files", {}))
    ops: List[Op] = []
    step = 0
    for path, content in files.items():
        ops.append(Op("set", "file", path, value=content, ok=True, step=step, source="initial"))
        step += 1
    for e in doc.get("edits", []):
        tool = (e.get("tool") or e.get("name") or "").strip().lower()
        args = e.get("args") or e.get("parameters") or {}
        ok = bool(e.get("ok", True)) and not bool(e.get("error"))
        if tool in EDIT_TOOLS:
            path, old, new = args.get("path"), args.get("old_str"), args.get("new_str")
            applied = False
            if ok and path in files and old and old in files[path]:
                files[path] = files[path].replace(old, new or "")
                applied = True
            ops.append(Op("set", "file", str(path), value=files.get(str(path)), ok=applied, step=step, source=tool))
        elif tool in ("write_file", "create_file"):
            if ok:
                files[str(args.get("path"))] = str(args.get("content", ""))
            ops.append(Op("set", "file", str(args.get("path")), value=str(args.get("content", "")), ok=ok, step=step, source=tool))
        elif tool in ("delete_file",):
            if ok:
                files.pop(str(args.get("path")), None)
            ops.append(Op("remove", "file", str(args.get("path")), ok=ok, step=step, source=tool))
        else:
            step += 1
            continue
        step += 1
    return ops
