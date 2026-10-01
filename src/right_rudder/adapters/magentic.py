"""Magentic-One console logs: the orchestrator's fact sheet, rewritten at every re-plan.

Magentic-One console logs: the orchestrator's fact sheet and plan, rewritten at every re-plan,
around the turns of WebSurfer, FileSurfer, Coder and ComputerTerminal.

Input: the text of a run's console_log.txt (AutoGen's `---------- Speaker ----------` transcript),
or a JSON document {"log": text}.

Committed state is the fact sheet. Every line the orchestrator writes under the four headings
(GIVEN OR VERIFIED FACTS, FACTS TO LOOK UP, FACTS TO DERIVE, EDUCATED GUESSES) becomes a fact
keyed by its normalised text (a rephrased line joins an earlier fact when the two share at least
half their content words, JACCARD_MIN), whose value is the standing the orchestrator gave it ("verified",
"lookup", "derive" or "guess", prefixed to the key). A rewrite that carries a line forward unchanged
re-asserts the sheet and produces no op; a rewrite that moves a line between headings supersedes
its standing, and a later rewrite that restores the earlier standing is what the read reports. A
line that disappears from the sheet is removed. FINAL ANSWER is an answer that stands on every fact
verified at that point. The agents' turns read the world and write nothing, so they produce no ops.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from ..ops import Op

_SPEAKER = re.compile(r"^---------- ([A-Za-z_]+) ----------\s*$")
_HEADING = re.compile(r"^\s*(\d)\.\s+(GIVEN OR VERIFIED FACTS|FACTS TO LOOK UP|FACTS TO DERIVE|EDUCATED GUESSES)\s*:?\s*$", re.I)
_BULLET = re.compile(r"^\s*[-*•]\s+(.*\S)\s*$")
_FINAL = re.compile(r"^\s*FINAL ANSWER:\s*(.*)$")
STANDING = {"GIVEN OR VERIFIED FACTS": "verified", "FACTS TO LOOK UP": "lookup", "FACTS TO DERIVE": "derive", "EDUCATED GUESSES": "guess"}
_EMPTY = {"none", "none specified in the request", "none specified", "n/a", "not applicable", "none provided"}
ORCHESTRATOR = "MagenticOneOrchestrator"
JACCARD_MIN = 0.5
_STOP = set("the a an of to in on for and or is are was were be by with as at from that this it its which".split())


def _words(key: str) -> set:
    return {w for w in key.split() if w not in _STOP and len(w) > 2}


class _Identity:
    """Maps each sheet line to a fact key, joining rephrasings of an earlier line."""

    def __init__(self) -> None:
        self.keys: List[Tuple[str, set]] = []

    def key_for(self, norm: str) -> str:
        w = _words(norm)
        best, match = 0.0, None
        for k, kw in self.keys:
            if k == norm:
                return k
            j = len(w & kw) / max(1, len(w | kw))
            if j > best:
                best, match = j, k
        if match is not None and best >= JACCARD_MIN:
            return match
        self.keys.append((norm, w))
        return norm


def _norm(text: str) -> str:
    t = re.sub(r"\*\*|__|`", "", text.lower())
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _turns(text: str) -> List[Tuple[str, List[str]]]:
    turns: List[Tuple[str, List[str]]] = []
    for line in text.splitlines():
        m = _SPEAKER.match(line)
        if m:
            turns.append((m.group(1), []))
        elif turns:
            turns[-1][1].append(line)
    return turns


def _sheets(lines: List[str]) -> List[Dict[str, List[str]]]:
    """Every fact sheet in an orchestrator turn, as {standing: [line, ...]}. A re-plan turn may print
    the initial sheet's heading and then the updated sheet; the last complete sheet is the one that stands."""
    sheets: List[Dict[str, List[str]]] = []
    cur: Dict[str, List[str]] = {}
    standing = None
    for l in lines:
        h = _HEADING.match(l)
        if h:
            name = STANDING[h.group(2).upper()]
            if name == "verified" and cur:
                sheets.append(cur); cur = {}
            standing = name
            cur.setdefault(standing, [])
            continue
        if standing is None:
            continue
        if not l.strip():
            continue
        b = _BULLET.match(l)
        if b:
            cur[standing].append(b.group(1))
        elif not l.startswith((" ", "\t")):
            # prose after the sheet (the plan) ends it
            standing = None
    if cur:
        sheets.append(cur)
    return sheets


def load(doc: Any, **_) -> List[Op]:
    text = doc.get("log", "") if isinstance(doc, dict) else str(doc)
    ops: List[Op] = []
    ledger: Dict[str, str] = {}   # fact key -> standing
    ident = _Identity()
    for speaker, lines in _turns(text):
        if speaker != ORCHESTRATOR:
            continue
        for sheet in _sheets(lines):
            seen: Dict[str, str] = {}
            for standing, items in sheet.items():
                for item in items:
                    norm = _norm(item)
                    if not norm or norm in _EMPTY:
                        continue
                    seen.setdefault(ident.key_for(norm), standing)
            for key in sorted(set(ledger) - set(seen)):
                ops.append(Op("remove", "fact", key, step=len(ops), source="sheet"))
                ledger.pop(key)
            for key, standing in seen.items():
                if ledger.get(key) == standing:
                    continue   # a line carried forward unchanged re-asserts the sheet; only a change is a write
                # The value carries the key so that standings are not token-like ids shared across facts.
                ops.append(Op("set", "fact", key, value=f"{standing} {key}", step=len(ops), source="sheet"))
                ledger[key] = standing
        for l in lines:
            m = _FINAL.match(l)
            if m:
                refs = [("fact", k) for k, s in ledger.items() if s == "verified"]
                ops.append(Op("answer", "answer", "final", value=m.group(1).strip(), refs=refs, step=len(ops), source="final_answer"))
    return ops


def looks_like(text: str) -> bool:
    return "---------- MagenticOneOrchestrator ----------" in text
