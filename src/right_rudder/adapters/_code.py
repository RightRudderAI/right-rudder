"""Shared helpers for code-workspace adapters: a unified-diff applier and a Python symbol scan.

A workspace adapter turns each committed revision of a file into a "set" op carrying the file's
content, plus one "set" op per top-level symbol the file defines (kind "symbol", key
"<module>.<name>") and a "remove" for each symbol the revision drops. A file that imports a
sibling module's symbol carries that symbol as a ref, so a revision that still depends on a
symbol the agent has already removed reads as a stale reference.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from ..ops import Op

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
_DEF = re.compile(r"^(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)", re.M)
_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*(?::[^=\n]+)?=[^=]", re.M)
_FROM_IMPORT = re.compile(r"^from\s+([A-Za-z_][\w.]*)\s+import\s+([^\n#]+)", re.M)
_IMPORT = re.compile(r"^import\s+([A-Za-z_][\w.]*)", re.M)


def apply_unified_diff(old: str, diff: str) -> Tuple[Optional[str], bool]:
    """Apply a unified diff to old text. Returns (new_text, applied). A hunk whose context does
    not match the running copy fails the whole diff, and the caller marks the op rejected."""
    old_lines = old.split("\n") if old else []
    out: List[str] = []
    pos = 0
    lines = diff.split("\n")
    i = 0
    seen_hunk = False
    while i < len(lines):
        m = _HUNK.match(lines[i])
        if not m:
            i += 1
            continue
        seen_hunk = True
        start = int(m.group(1)) - 1 if int(m.group(1)) > 0 else 0
        i += 1
        body: List[str] = []
        while i < len(lines) and not _HUNK.match(lines[i]) and not lines[i].startswith(("--- ", "+++ ")):
            body.append(lines[i])
            i += 1
        while body and body[-1] == "":
            body.pop()
        # Copy unchanged lines up to the hunk.
        if start < pos:
            return None, False
        out.extend(old_lines[pos:start])
        pos = start
        for b in body:
            if b.startswith("-"):
                if pos >= len(old_lines) or old_lines[pos] != b[1:]:
                    return None, False
                pos += 1
            elif b.startswith("+"):
                out.append(b[1:])
            elif b.startswith("\\"):
                continue
            else:
                ctx = b[1:] if b.startswith(" ") else b
                if pos >= len(old_lines) or old_lines[pos] != ctx:
                    return None, False
                out.append(old_lines[pos])
                pos += 1
    if not seen_hunk:
        return None, False
    out.extend(old_lines[pos:])
    return "\n".join(out), True


def python_symbols(module: str, content: str) -> Set[str]:
    names = set(_DEF.findall(content or "")) | set(_ASSIGN.findall(content or ""))
    return {f"{module}.{n}" for n in names}


def python_refs(content: str, known_modules: Set[str]) -> List[Tuple[str, str]]:
    """Symbols this file imports from sibling modules the workspace defines."""
    refs: List[Tuple[str, str]] = []
    for mod, names in _FROM_IMPORT.findall(content or ""):
        if mod not in known_modules:
            continue
        for n in names.replace("(", "").replace(")", "").split(","):
            n = n.strip().split(" as ")[0].strip()
            if n and n != "*":
                refs.append(("symbol", f"{mod}.{n}"))
    return refs


def module_name(path: str) -> str:
    base = path.rsplit("/", 1)[-1]
    return base[:-3] if base.endswith(".py") else base


class Workspace:
    """Tracks files and their symbols across revisions and emits the ops for each revision."""

    def __init__(self) -> None:
        self.files: Dict[str, str] = {}
        self.symbols: Dict[str, Set[str]] = {}

    def modules(self) -> Set[str]:
        return {module_name(p) for p in self.files if p.endswith(".py")}

    def revise(self, path: str, content: Optional[str], ok: bool, source: str) -> Tuple[List[Op], Op]:
        """Ops for one revision of a file, as (symbol ops, file op) without steps. The caller
        emits every symbol op of a batch before any file op, so a file's refs resolve against the
        state the whole batch commits."""
        if not ok or content is None:
            return [], Op("set", "file", path, value=content, ok=False, source=source)
        new_syms = python_symbols(module_name(path), content) if path.endswith(".py") else set()
        old_syms = self.symbols.get(path, set())
        sym_ops: List[Op] = []
        for s in sorted(old_syms - new_syms):
            sym_ops.append(Op("remove", "symbol", s, source=source))
        for s in sorted(new_syms - old_syms):
            sym_ops.append(Op("set", "symbol", s, value=s, source=source))
        self.files[path] = content
        self.symbols[path] = new_syms
        return sym_ops, Op("set", "file", path, value=content, ok=True, source=source)

    def file_refs(self, path: str) -> List[Tuple[str, str]]:
        content = self.files.get(path, "")
        return python_refs(content, self.modules() - {module_name(path)}) if path.endswith(".py") else []


def emit_batch(ops: List[Op], ws: "Workspace", revisions: List[Tuple[str, Optional[str], bool, str]]) -> None:
    """Commit a batch of (path, content, ok, source) revisions: symbols first, then files with refs.
    A file republished byte-for-byte is a set of the value the key already holds, which the read
    reports as a duplicate commit on its own."""
    pending = []
    for path, content, ok, source in revisions:
        sym_ops, file_op = ws.revise(path, content, ok, source)
        for o in sym_ops:
            o.step = len(ops); ops.append(o)
        pending.append(file_op)
    for o in pending:
        if o.ok:
            o.refs = ws.file_refs(o.key)
        o.step = len(ops); ops.append(o)
