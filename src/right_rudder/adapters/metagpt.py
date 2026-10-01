"""MetaGPT communication logs: the code each role publishes and the answers it states.

MetaGPT communication logs: the roles' messages (SimpleCoder, SimpleTester, SimpleReviewer and
their kin) in the order the environment published them.

Input: the text of a `MetaGPT Agent Communication Log` file, or a JSON document {"log": text}.

Committed state is the code each role published. A code-writing role's message becomes a revision
of that role's file (kind "file", "<Role>.py"), with one fact per top-level symbol it defines and a
ref from the file to every sibling symbol it imports, so a tester that imports a function the coder
never wrote, or a coder that drops a function the tests still import, reads as a stale reference.
A reviewer's comment is talk about the code and produces no op. On question-answering tasks, a
message that states "The answer is (X)" sets the answer, and a later message restoring an earlier
answer is what the read reports.
"""
from __future__ import annotations

import re
from typing import Any, List

from ..ops import Op
from ._code import Workspace, emit_batch

_ROLE = re.compile(r"^([A-Z][A-Za-z]+):\s*$")
_SEP = re.compile(r"^-{20,}\s*$")
_NEW = re.compile(r"^\[[\d\- :]+\] NEW MESSAGES:\s*$")
_ANSWER = re.compile(r"The answer is \(?([0-9A-Da-d])\)?")
CODE_ROLES_HINT = ("Coder", "Tester", "Engineer", "Programmer", "Developer")


def _messages(text: str):
    """Yield (role, body) for every role message in the log."""
    role, body = None, []
    for line in text.splitlines():
        if _NEW.match(line) or _SEP.match(line) or line.startswith("=== "):
            if role is not None:
                yield role, "\n".join(body).strip()
            role, body = None, []
            continue
        m = _ROLE.match(line)
        if m and role is None:
            role = m.group(1)
            continue
        if role is not None:
            body.append(line)
    if role is not None:
        yield role, "\n".join(body).strip()


def _strip_fence(body: str) -> str:
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", body, re.S)
    return m.group(1) if m else body


def load(doc: Any, **_) -> List[Op]:
    text = doc.get("log", "") if isinstance(doc, dict) else str(doc)
    ops: List[Op] = []
    ws = Workspace()
    for role, body in _messages(text):
        if not body:
            continue
        code = _strip_fence(body)
        writes_code = any(h in role for h in CODE_ROLES_HINT) or re.search(r"^(def|class|import|from)\s", code, re.M)
        if writes_code and re.search(r"^(def|class|import|from|\w+\s*=)", code, re.M) and "Reviewer" not in role:
            emit_batch(ops, ws, [(f"{role}.py", code, True, role)])
            continue  # a code message states no answer; the string may occur inside its tests
        for a in _ANSWER.findall(body):
            ops.append(Op("set", "answer", "final", value=f"answer {a.upper()}", step=len(ops), source=role))
    return ops


def looks_like(text: str) -> bool:
    return "MetaGPT Agent Communication Log" in text
