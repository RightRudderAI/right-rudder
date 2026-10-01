"""ChatDev chat-chain logs: every code update in the software company's phases.

ChatDev chat-chain logs: the software company's phases, with every code update written as a
unified diff under an `**[Update Codes]**` heading.

Input: the text of a `<Project>_<Org>_<timestamp>.log` file from ChatDev's WareHouse, or a JSON
document {"log": text}.

Committed state is the project's code. Each `[Update Codes]` block names a file and carries the
diff the phase applied; the adapter folds the diff onto its running copy of the file and emits a
"set" op with the file's new content. Consecutive updates from one phase form a batch, and the
batch commits its symbols before its files so that a file importing a sibling's class resolves
against the state the phase as a whole wrote. A diff that does not apply to the running copy is
emitted as a rejected op. Seminar conclusions, reviews and test reports are talk about the code
rather than writes to it, so they produce no ops. `[Post Info]` closes the run as an answer.
"""
from __future__ import annotations

import re
from typing import Any, List, Optional, Tuple

from ..ops import Op
from ._code import Workspace, apply_unified_diff, emit_batch

_MARK = re.compile(r"^\[[\d\- :]+ \w+\] \*\*\[([A-Za-z_ ]+)\]\*\*")
_UPDATED = re.compile(r"^(\S+) updated\.\s*$")
_NEW_FILE_SEED = "# None"


def _blocks(text: str) -> List[Tuple[str, List[str]]]:
    """Split the log into (heading, lines) blocks at every **[Heading]** marker."""
    blocks: List[Tuple[str, List[str]]] = []
    for line in text.splitlines():
        m = _MARK.match(line)
        if m:
            blocks.append((m.group(1).strip(), []))
        elif blocks:
            blocks[-1][1].append(line)
    return blocks


def _diff_of(lines: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (file name, diff text) from an Update Codes block."""
    name = None
    for l in lines:
        m = _UPDATED.match(l.strip())
        if m:
            name = m.group(1)
            break
    if name is None:
        return None, None
    fence: List[str] = []
    inside = False
    for l in lines:
        if l.strip().startswith("```"):
            if inside:
                break
            inside = True
            continue
        if inside:
            fence.append(l)
    return name, "\n".join(fence)


def load(doc: Any, **_) -> List[Op]:
    text = doc.get("log", "") if isinstance(doc, dict) else str(doc)
    ops: List[Op] = []
    ws = Workspace()
    running: dict = {}   # the running copy per file, updated as each diff lands, ahead of the batch flush
    batch: List[Tuple[str, Optional[str], bool, str]] = []
    phase = "start"

    def flush() -> None:
        nonlocal batch
        if batch:
            emit_batch(ops, ws, batch)
            batch = []

    for heading, lines in _blocks(text):
        if heading == "Update Codes":
            name, diff = _diff_of(lines)
            if name is None:
                continue
            old = running.get(name, _NEW_FILE_SEED)
            new, applied = apply_unified_diff(old, diff or "")
            if not applied and name not in running and diff and "+++ New" in diff:
                # A fresh file whose diff was cut against something other than the seed: take the added lines.
                new = "\n".join(l[1:] for l in diff.split("\n") if l.startswith("+") and not l.startswith("+++"))
                applied = bool(new.strip())
            if applied:
                running[name] = new
            batch.append((name, new if applied else None, applied, f"update_codes/{phase}"))
            continue
        flush()
        if heading in ("Start Chat", "chatting"):
            for l in lines[:12]:
                m = re.search(r"\|\s*\*\*phase_name\*\*\s*\|\s*(\w+)", l)
                if m:
                    phase = m.group(1)
                    break
        elif heading == "Post Info":
            ops.append(Op("answer", "run", "post_info", value="\n".join(lines).strip()[:200] or "done", step=len(ops),
                          refs=[("file", p) for p in sorted(ws.files)], source="post_info"))
    flush()
    return ops


def looks_like(text: str) -> bool:
    return "**ChatDev Starts**" in text or "**[Update Codes]**" in text
