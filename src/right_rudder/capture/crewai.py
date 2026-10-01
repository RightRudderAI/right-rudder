"""
Record a CrewAI crew's tool calls and task completions to a JSON file the read accepts.

    from right_rudder.capture.crewai import RightRudderListener
    listener = RightRudderListener("events.json")   # keep a reference; CrewAI holds listeners weakly
    crew.kickoff()
    listener.close()

Then:  right-rudder read events.json --format crewai

The listener records three events from crewai's event bus: tool_usage_finished (with the tool's
name, arguments, and whether it reported failure), tool_usage_error, and task_completed. Nothing
else is captured and nothing is sent anywhere by the listener itself.
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

try:
    from crewai.events import BaseEventListener, crewai_event_bus
    from crewai.events import ToolUsageFinishedEvent, ToolUsageErrorEvent, TaskCompletedEvent
except ImportError as e:  # pragma: no cover
    raise ImportError("right_rudder.capture.crewai needs crewai installed: pip install crewai") from e


def _jsonable(x: Any) -> Any:
    if isinstance(x, (str, int, float, bool)) or x is None:
        return x
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return str(x)


class RightRudderListener(BaseEventListener):
    """Collects the crew's committed actions as a list of events; writes them on close()."""

    def __init__(self, path: Optional[str] = "events.json") -> None:
        self.path = path
        self.events: List[dict] = []
        super().__init__()

    def setup_listeners(self, bus) -> None:  # noqa: D401
        @bus.on(ToolUsageFinishedEvent)
        def _finished(source, event):
            self.events.append({
                "type": "tool_usage_finished",
                "tool_name": event.tool_name,
                "tool_args": _jsonable(event.tool_args),
                "output": _jsonable(getattr(event, "output", None)),
                "failure": _jsonable(getattr(event, "failure", None)),
                "agent": getattr(event, "agent_role", None) or getattr(event, "agent_key", None),
            })

        @bus.on(ToolUsageErrorEvent)
        def _error(source, event):
            self.events.append({
                "type": "tool_usage_error",
                "tool_name": event.tool_name,
                "tool_args": _jsonable(event.tool_args),
                "error": str(getattr(event, "error", "")),
                "agent": getattr(event, "agent_role", None) or getattr(event, "agent_key", None),
            })

        @bus.on(TaskCompletedEvent)
        def _task(source, event):
            out = getattr(event, "output", None)
            self.events.append({
                "type": "task_completed",
                "task_name": getattr(out, "name", None) or getattr(getattr(event, "task", None), "name", None)
                             or getattr(out, "description", "")[:80],
                "output": getattr(out, "raw", "") if out is not None else "",
            })

    def close(self) -> str:
        """Write the events to self.path and return the path."""
        if self.path:
            with open(self.path, "w") as f:
                json.dump({"events": self.events}, f, indent=1)
        return self.path or ""


# The name before the Right Rudder rebrand, kept so existing code keeps working.
FathomListener = RightRudderListener
