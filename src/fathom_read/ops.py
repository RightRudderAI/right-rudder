"""The op stream: what an adapter produces and the hosted read consumes."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

Ref = Tuple[str, str]


@dataclass
class Op:
    """One action the agent took.

    op:     "set" writes a value to (kind, key); "remove" deletes it; "rename" moves (kind, key)
            to (kind, to); "add" inserts an entity into a collection under (kind, key); "answer"
            is an assertion the agent made (a final answer, a report); "commit" marks a terminal
            action (an order placed, a booking confirmed).
    kind:   what sort of thing the key names: "file", "record", "block", "fact", "order", or your own.
    key:    the name of the thing.
    value:  the content written (for set/add/answer).
    to:     the new name (for rename).
    ok:     whether the tool accepted the action. False makes the op a no-op.
    refs:   facts this op depends on, as (kind, key) pairs.
    step:   the position of the op in the stream (set by the reader if omitted).
    source: where the op came from (an adapter's note).
    """
    op: str
    kind: str
    key: str
    value: Optional[str] = None
    to: Optional[str] = None
    ok: bool = True
    refs: List[Ref] = field(default_factory=list)
    step: Optional[int] = None
    source: Optional[str] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Op":
        refs = [tuple(r) for r in d.get("refs", [])]
        return cls(op=d["op"], kind=d.get("kind", "fact"), key=str(d["key"]),
                   value=None if d.get("value") is None else str(d.get("value")),
                   to=d.get("to"), ok=bool(d.get("ok", True)), refs=refs,
                   step=d.get("step"), source=d.get("source"))

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["refs"] = [list(r) for r in self.refs]
        return d


@dataclass
class Finding:
    kind: str
    step: Optional[int]
    key: str
    detail: str
    cites: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Verdict:
    coherent: bool
    findings: List[Finding]
    ops_read: int
    ops_rejected: int
    live_facts: int

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Verdict":
        return cls(coherent=bool(d["coherent"]), findings=[Finding(**f) for f in d.get("findings", [])],
                   ops_read=int(d.get("ops_read", 0)), ops_rejected=int(d.get("ops_rejected", 0)),
                   live_facts=int(d.get("live_facts", 0)))

    def as_dict(self) -> Dict[str, Any]:
        return {"coherent": self.coherent, "findings": [f.as_dict() for f in self.findings],
                "ops_read": self.ops_read, "ops_rejected": self.ops_rejected, "live_facts": self.live_facts}


@dataclass
class RegroundVerdict:
    """What the repair returned for a set of proposed next actions.

    decision:  "proceed" (every proposal is consistent with the committed state), "filter" (some are; take the
               first of `keep`, the agent's own consistent alternative), or "reground" (none are; put `facts` back
               in front of the agent and ask again).
    keep:      the values of the proposals the agent can take, in the agent's own order.
    kept:      the same proposals in full (index, op, kind, key, value).
    dropped:   the proposals that contradict the committed state, each with the finding kinds it would create.
    facts:     on reground, the committed facts the proposals contradicted: a collection and what it already holds,
               a fact and the value it carries now, a key and the name it was renamed to, or a commit and its step.
    read:      the read over the ops as sent (coherent, findings, ops_read, live_facts).
    """
    decision: str
    keep: List[Optional[str]]
    kept: List[Dict[str, Any]]
    dropped: List[Dict[str, Any]]
    facts: List[Dict[str, Any]]
    proposals: int
    read: Dict[str, Any]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RegroundVerdict":
        return cls(decision=str(d["decision"]), keep=list(d.get("keep", [])), kept=list(d.get("kept", [])),
                   dropped=list(d.get("dropped", [])), facts=list(d.get("facts", [])),
                   proposals=int(d.get("proposals", 0)), read=dict(d.get("read", {})))

    def as_dict(self) -> Dict[str, Any]:
        return {"decision": self.decision, "keep": self.keep, "kept": self.kept, "dropped": self.dropped,
                "facts": self.facts, "proposals": self.proposals, "read": self.read}

    def prompt_note(self, proposed: Optional[List[str]] = None) -> str:
        """The facts as a note to append to the agent's prompt before asking again. Plain words, no scores."""
        lines = ["", "", "COMMITTED STATE CHECK. The following is already established in this run and must be honored:"]
        for f in self.facts:
            kind, key = f.get("kind"), f.get("key")
            if "holds" in f:
                lines.append(f"- {kind} '{key}' already holds: {', '.join(repr(v) for v in f['holds'])}"
                             + (" (and more)" if f.get("truncated") else "") + ". Do not propose any of these again.")
            elif f.get("renamed_to") is not None:
                lines.append(f"- {kind} '{key}' was renamed to '{f['renamed_to']}'. Use the new name.")
            elif f.get("absent"):
                live = f.get("live") or []
                lines.append(f"- {kind} '{key}' is not in the committed state." + (f" Known {kind}s: {', '.join(repr(v) for v in live)}." if live else ""))
            elif "replaced" in f:
                lines.append(f"- {kind} '{key}' now carries '{f.get('value')}', which replaced '{f['replaced']}'. Use the current value.")
            elif f.get("committed_at") is not None:
                lines.append(f"- {kind} was committed at step {f['committed_at']}; do not change it.")
            elif "value" in f:
                lines.append(f"- {kind} '{key}' already carries '{f.get('value')}'.")
        if proposed:
            lines.append(f"Every proposal ({', '.join(repr(p) for p in proposed)}) contradicts the above. Propose alternatives that do not.")
        return "\n".join(lines)
