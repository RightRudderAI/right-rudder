"""Adapters turn what a framework already records into the op stream the read consumes."""
from . import events, edits, openinference, langgraph, crewai, letta, dbos  # noqa: F401
from . import openmanus, chatdev, metagpt, magentic, hyperagent, appworld, ag2  # noqa: F401
from . import deepagents  # noqa: F401

FORMATS = {
    "events": events,
    "edits": edits,
    "openinference": openinference,
    "langgraph": langgraph,
    "crewai": crewai,
    "letta": letta,
    "dbos": dbos,
    "openmanus": openmanus,
    "chatdev": chatdev,
    "metagpt": metagpt,
    "magentic": magentic,
    "hyperagent": hyperagent,
    "appworld": appworld,
    "ag2": ag2,
    "deepagents": deepagents,
}

# Formats whose native record is a text log rather than a JSON document, tried in this order on text input.
TEXT_FORMATS = ("chatdev", "metagpt", "openmanus", "magentic", "appworld", "hyperagent", "ag2")


def detect(doc) -> str:
    """Guess the format of a loaded document, a parsed JSON value or the text of a log."""
    if isinstance(doc, str):
        for name in TEXT_FORMATS:
            mod = FORMATS[name]
            if mod.looks_like(doc):
                return name
        raise ValueError("could not detect the log format; pass --format")
    if isinstance(doc, dict):
        if "trajectory" in doc and "instance_id" in doc:
            if ag2.looks_like(doc):
                return "ag2"
            tr = doc.get("trajectory")
            if isinstance(tr, list) and tr and isinstance(tr[0], str) and tr[0].startswith("HyperAgent_"):
                return "hyperagent"
        if "calls" in doc and deepagents.looks_like(doc):
            return "deepagents"
        if "log" in doc and isinstance(doc["log"], str):
            return detect(doc["log"])
        if "ops" in doc:
            return "events"
        if "spans" in doc or "resourceSpans" in doc:
            return "openinference"
        if "edits" in doc or "initial_files" in doc:
            return "edits"
        if "blocks" in doc or "passages" in doc:
            return "letta"
        if "steps" in doc and "workflow_id" in doc:
            return "dbos"
        if "events" in doc:
            return "crewai"
        if "snapshots" in doc or "history" in doc:
            return "langgraph"
    if isinstance(doc, list) and doc:
        first = doc[0]
        if isinstance(first, dict):
            if "op" in first and "key" in first:
                return "events"
            if deepagents.looks_like(doc):
                return "deepagents"
            if "attributes" in first or "span_kind" in first:
                return "openinference"
            if "values" in first and ("next" in first or "config" in first or "metadata" in first or "step" in first):
                return "langgraph"
            if "type" in first and ("tool_name" in first or "task_name" in first or first.get("type", "").startswith(("tool_", "task_"))):
                return "crewai"
            if "step_name" in first:
                return "dbos"
            if "tool" in first and "args" in first:
                return "edits"
    raise ValueError("could not detect the trace format; pass --format")
