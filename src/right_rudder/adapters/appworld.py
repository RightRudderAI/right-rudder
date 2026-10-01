"""AppWorld agent logs: mutations through the app APIs and the task's completion.

AppWorld agent logs: a supervisor agent and per-app agents that act by writing Python against
`apis.<app>.<call>(...)`, with each code block's execution output logged after it.

Input: the text of one task's log (the `Task k/n (<id>)` banner, `Response from <X> Agent` code
blocks and `Code Execution Output` blocks), or a JSON document {"log": text}.

Committed state is what the agents changed through the app APIs. A call whose name reads
(show_*, search_*, api_docs.*, login, logout, verification and password flows) is a lookup and
produces no op. Any other call is a mutation, recorded as an "add" of its literal argument text
to the collection "<app>.<call>", so the same mutation issued again in identical literal form reads as a
duplicate commit; a call bound to variables carries its block index, since the log records the
code and not the values, and the same text can act on different targets. `apis.supervisor.complete_task(...)` is a commit of the task, after which a
further mutation reads as a post-commit change. A code block whose execution output reports a
failure marks every call in that block as rejected, since the block ran as a unit and its calls
did not stand.
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

from ..ops import Op

_CALL = re.compile(r"apis\.([a-z_]+)\.([a-z_]+)\((.*?)\)", re.S)
_HDR = re.compile(r"^\s*(Response from (\w+) Agent|Code Execution Output|Message to (\w+) Agent|Response from send_message API|Entering (\w+) Agent message loop|Exiting (\w+) Agent message loop)\s*$")
READ_PREFIXES = ("show_", "search_", "get_", "list_")
READ_CALLS = {"login", "logout", "signup", "send_verification_code", "verify_account", "send_password_reset_code", "reset_password"}
_FAIL = re.compile(r"Execution failed|Traceback")


def _blocks(text: str) -> List[Tuple[str, str, str]]:
    """(kind, agent, body) for every Response/Output block, in order."""
    blocks: List[Tuple[str, str, List[str]]] = []
    for line in text.splitlines():
        m = _HDR.match(line)
        if m:
            h = m.group(1)
            if h.startswith("Response from") and m.group(2):
                blocks.append(("code", m.group(2), []))
            elif h == "Code Execution Output":
                blocks.append(("output", "", []))
            elif h.startswith("Message to"):
                blocks.append(("message", m.group(3), []))
            else:
                blocks.append(("other", "", []))
        elif blocks:
            blocks[-1][2].append(line)
    return [(k, a, "\n".join(b)) for k, a, b in blocks]


def _is_read(app: str, call: str) -> bool:
    return app == "api_docs" or call.startswith(READ_PREFIXES) or call in READ_CALLS


def _norm_args(args: str) -> str:
    return re.sub(r"\s+", " ", args).strip()


_LITERAL_ARG = re.compile(r"^\s*(\w+\s*=\s*)?(\"[^\"]*\"|'[^']*'|-?\d+(\.\d+)?|True|False|None)\s*$")


_CREDENTIAL = re.compile(r"^\s*(access_token|token|username|password|api_key)\s*=", re.I)


def _literal(args: str) -> bool:
    """True when every argument is a literal and at least one names a target, so the call text
    names the exact mutation. A call bound to variables (song_id=song_id_to_remove) is the same
    text for different targets, and a call carrying only credentials (next_song(access_token=...))
    advances state rather than writing a target, so repeating it is the task and not a duplicate."""
    parts = [p for p in re.split(r",(?![^\[\]\(\)\{\}]*[\]\)\}])", args) if p.strip()]
    targets = [p for p in parts if not _CREDENTIAL.match(p)]
    return bool(targets) and all(_LITERAL_ARG.match(p) for p in parts)


def load(doc: Any, **_) -> List[Op]:
    text = doc.get("log", "") if isinstance(doc, dict) else str(doc)
    ops: List[Op] = []
    blocks = _blocks(text)
    for i, (kind, agent, body) in enumerate(blocks):
        if kind != "code":
            continue
        # The block's result is the next output block, or for an app agent the next message back to it.
        result = ""
        for k2, a2, b2 in blocks[i + 1:i + 3]:
            if k2 in ("output", "message"):
                result = b2
                break
        head = "\n".join([l for l in result.splitlines() if l.strip()][:3])
        ok = not _FAIL.search(head)   # the framework prints "Execution failed. Traceback:" at the top of a failed block
        for app, call, args in _CALL.findall(body):
            if _is_read(app, call):
                continue
            if app == "supervisor" and call == "complete_task":
                ops.append(Op("answer", "task", "task", value=_norm_args(args) or "done", ok=ok, step=len(ops), source=f"{agent}:{call}"))
                ops.append(Op("commit", "task", "task", ok=ok, step=len(ops), source=f"{agent}:{call}"))
                continue
            value = _norm_args(args) if _literal(args) else f"{_norm_args(args)} @block{i}"
            ops.append(Op("add", "task", f"{app}.{call}", value=value, ok=ok, step=len(ops), source=f"{agent}:{call}"))
    return ops


def looks_like(text: str) -> bool:
    return "Response from Supervisor Agent" in text and "Code Execution Output" in text
