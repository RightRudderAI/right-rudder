"""The CrewAI capture listener records the right events; tested against a stand-in event bus."""
import sys, types, json, tempfile, os

def _install_stub():
    ev = types.ModuleType("crewai.events"); crewai = types.ModuleType("crewai")
    class Bus:
        def __init__(self): self.h = {}
        def on(self, t):
            def deco(fn): self.h.setdefault(t, []).append(fn); return fn
            return deco
        def validate_dependencies(self): pass
        def emit(self, src, e):
            for fn in self.h.get(type(e), []): fn(src, e)
    bus = Bus()
    class BaseEventListener:
        def __init__(self): self.setup_listeners(bus); bus.validate_dependencies()
    class ToolUsageFinishedEvent:
        def __init__(self, **k): self.__dict__.update(k)
    class ToolUsageErrorEvent(ToolUsageFinishedEvent): pass
    class TaskCompletedEvent(ToolUsageFinishedEvent): pass
    ev.BaseEventListener = BaseEventListener; ev.crewai_event_bus = bus
    ev.ToolUsageFinishedEvent = ToolUsageFinishedEvent
    ev.ToolUsageErrorEvent = ToolUsageErrorEvent
    ev.TaskCompletedEvent = TaskCompletedEvent
    crewai.events = ev
    sys.modules["crewai"] = crewai; sys.modules["crewai.events"] = ev
    return bus, ToolUsageFinishedEvent, ToolUsageErrorEvent, TaskCompletedEvent


def test_listener_records_and_adapter_reads():
    bus, Fin, Err, Task = _install_stub()
    from right_rudder.capture.crewai import RightRudderListener
    from right_rudder import load_ops
    p = os.path.join(tempfile.mkdtemp(), "events.json")
    L = RightRudderListener(p)
    bus.emit(None, Fin(tool_name="write_record", tool_args={"record": "r0", "content": "customer_id: 100"}, output="ok", failure=None, agent_role="clerk"))
    bus.emit(None, Err(tool_name="write_record", tool_args={"record": "r1", "content": "customer_id: 101"}, error="timeout"))
    class Out: name = "rename"; raw = "done"; description = "Rename all"
    bus.emit(None, Task(output=Out(), task=None))
    L.close()
    doc = json.load(open(p))
    assert [e["type"] for e in doc["events"]] == ["tool_usage_finished", "tool_usage_error", "task_completed"]
    ops = load_ops(p, "crewai")
    assert [(o.op, o.key, o.ok) for o in ops][:2] == [("set", "r0", True), ("set", "r1", False)]
