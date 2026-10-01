"""AG2 (AutoGen) math dialogues: quantities stated in code and the boxed answer.

AG2 (AutoGen) math dialogues: a proxy or verifier agent, a solver, and in the improved topology a
code executor, exchanging messages until an answer is boxed.

Input: {"trajectory": [{"content": [line, ...] or str, "role", "name"}, ...]} as the MAST corpus
stores it, or the bare message list.

AG2 records no tool boundary, so committed state is what the agents state. Every top-level
assignment of a numeric literal in a python block becomes a fact (kind "fact", the variable name)
carrying the number, prefixed with the name so that values are not bare tokens (an assignment of an
expression is a computation rather than a stated quantity and produces no op, and a re-run block
that restates a quantity already held produces none either); a block the executor reports as
failed leaves nothing behind. Every \\boxed{...} becomes the fact "answer"
carrying the boxed content; boxing the value that already stands (a summary, or a verifier echoing
the solver) restates it and produces no op, a different value is a revision, and a later return to
an earlier boxed value is what the read reports. A verifier's SOLUTION_FOUND is an answer
standing on the boxed fact. Prose reasoning produces no ops.
"""
from __future__ import annotations

import ast
import re
from typing import Any, Dict, List

from ..ops import Op

_CODE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)
_ASSIGN = re.compile(r"^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?(?:\s*/\s*\d+)?)\s*(?:#.*)?$", re.M)
_BOXED = re.compile(r"\\boxed\{((?:[^{}]|\{[^{}]*\})*)\}")
_EXEC_FAIL = re.compile(r"exitcode:\s*[1-9]|Error:|Traceback")
_EXEC_OK = re.compile(r"exitcode:\s*0|Code output:|^\s*-?\d")
_SOLUTION = re.compile(r"SOLUTION_FOUND\**\s*:?\s*(\\boxed\{((?:[^{}]|\{[^{}]*\})*)\}|\**([^\n*]*))")


def _text(m: Any) -> str:
    c = m.get("content", "") if isinstance(m, dict) else m
    return "\n".join(str(x) for x in c) if isinstance(c, list) else str(c)


def _norm_answer(s: str) -> str:
    """Normalise a boxed answer so the same quantity in two spellings compares equal: 43/2, 21.5 and
    $21.50 all become 21.5. Non-numeric answers keep their text with spacing and wrappers removed."""
    s = s.replace("\\text{", "").replace("\\,", "").replace("\\%", "%").replace("$", "").replace(",", "")
    s = re.sub(r"\\(d)?frac\{([^{}]*)\}\{([^{}]*)\}", r"\2/\3", s)
    s = re.sub(r"\s+", "", s).strip("{}. ")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)(?:/(\d+(?:\.\d+)?))?%?", s)
    if m:
        try:
            v = float(m.group(1)) / (float(m.group(2)) if m.group(2) else 1.0)
            s = (f"{v:.6f}".rstrip("0").rstrip(".")) + ("%" if s.endswith("%") else "")
        except (ValueError, ZeroDivisionError):
            pass
    return s


def _messages_from_text(text: str) -> List[Dict[str, Any]]:
    """The MAD corpus stores AG2 dialogues as text, either concatenated Python dict reprs
    ({'content': [...], 'role': ..., 'name': ...} ...) or a YAML-like dump with indented
    content/role/name blocks. Either form comes back as the message list."""
    t = text.strip()
    if t.startswith("{'content'") or t.startswith('{"content"'):
        starts = [m.start() for m in re.finditer(r"\{['\"]content['\"]:", t)]
        msgs = []
        for a, b in zip(starts, starts[1:] + [len(t)]):
            seg = t[a:b].strip()
            try:
                m = ast.literal_eval(seg)
                if isinstance(m, dict):
                    msgs.append(m); continue
            except (ValueError, SyntaxError):
                pass
            nm = re.search(r"['\"]name['\"]:\s*['\"]([^'\"]+)['\"]\s*\}\s*$", seg)
            msgs.append({"content": seg, "name": nm.group(1) if nm else ""})
        return msgs
    # YAML-like dump: "  content:" / indented lines / "  role: x" / "  name: y"
    msgs, cur, body, ind = [], None, [], None
    for line in text.splitlines():
        m = re.match(r"^(\s*)(content|role|name):(.*)$", line)
        if m and (ind is None or len(m.group(1)) == ind):
            ind = len(m.group(1))
            key, val = m.group(2), m.group(3).strip()
            if key == "content":
                if cur is not None:
                    cur["content"] = "\n".join(body); msgs.append(cur)
                cur, body = {"content": ""}, ([val] if val else [])
            elif cur is not None:
                cur[key] = val
        elif cur is not None:
            body.append(line[ind + 6:] if line.startswith(" " * (ind + 6)) else line.strip())
    if cur is not None:
        cur["content"] = "\n".join(body); msgs.append(cur)
    return msgs


def _current_answer(ops: List[Op]):
    for o in reversed(ops):
        if o.kind == "answer" and o.key == "final" and o.op == "set":
            return o.value
    return None


def load(doc: Any, **_) -> List[Op]:
    if isinstance(doc, str):
        doc = _messages_from_text(doc)
    msgs = doc.get("trajectory", []) if isinstance(doc, dict) else doc
    if isinstance(msgs, str):
        msgs = _messages_from_text(msgs)
    texts = [_text(m) for m in msgs]
    ops: List[Op] = []
    facts: Dict[str, str] = {}
    for i, text in enumerate(texts):
        who = msgs[i].get("name", "") if isinstance(msgs[i], dict) else ""
        for block in _CODE.findall(text):
            nxt = texts[i + 1] if i + 1 < len(texts) else ""
            ok = not _EXEC_FAIL.search(nxt[:400])
            for name, expr in _ASSIGN.findall(block):
                if name.startswith("print"):
                    continue
                value = f"{name} {expr.strip()}"
                if ok and facts.get(name) == value:
                    continue   # a re-run block restates the quantity; only a changed value is a write
                ops.append(Op("set", "fact", name, value=value, ok=ok, step=len(ops), source=f"{who}:code"))
                if ok:
                    facts[name] = value
        prose = _CODE.sub("", text)   # a \\boxed inside a code block is a template, not a stated answer
        for boxed in _BOXED.findall(prose):
            if "$" in boxed and "{" in boxed:
                continue
            val = _norm_answer(boxed)
            if val and not re.fullmatch(r"[A-Za-z_]\w*", val) and _current_answer(ops) != f"boxed {val}":
                ops.append(Op("set", "answer", "final", value=f"boxed {val}", step=len(ops), source=f"{who}:boxed"))
        m = _SOLUTION.search(text)
        if m:
            val = _norm_answer(m.group(2) if m.group(2) is not None else (m.group(3) or ""))
            if val and _current_answer(ops) != f"boxed {val}":
                ops.append(Op("set", "answer", "final", value=f"boxed {val}", step=len(ops), source=f"{who}:solution_found"))
            ops.append(Op("answer", "answer", "solution", value=val or "none", refs=[("answer", "final")], step=len(ops), source=f"{who}:solution_found"))
    return ops


_NAMES = ("mathproxyagent", "Agent_Verifier", "Agent_Code_Executor", "Agent_Problem_Solver")


def looks_like(doc: Any) -> bool:
    if isinstance(doc, str):
        head = doc[:4000]
        return ("'content'" in head or "content:" in head) and any(n in doc for n in _NAMES)
    msgs = doc.get("trajectory", []) if isinstance(doc, dict) else doc
    if isinstance(msgs, str):
        return looks_like(msgs)
    names = {m.get("name") for m in msgs if isinstance(m, dict)}
    return bool(names & set(_NAMES))
