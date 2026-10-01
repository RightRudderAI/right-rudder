"""Shared fixtures for the framework-log adapter tests: one small clean record per framework, in the
framework's own log format, with helpers to build variations of it."""
import textwrap

from right_rudder.adapters import openmanus

OPENMANUS_CLEAN = textwrap.dedent("""\
    2025-03-31 21:37:42.119 | INFO     | app.flow.planning:_create_initial_plan:138 - Creating initial plan with ID: plan_1
    2025-03-31 21:37:43.815 | INFO     | app.flow.planning:_create_initial_plan:179 - Plan creation result: Plan created successfully with ID: plan_1

    Plan: Two steps (ID: plan_1)

    Steps:
    0. [ ] Write the script.
    1. [ ] Run it.

    2025-03-31 21:37:47.316 | INFO     | app.agent.toolcall:think:86 - 🧰 Tools being prepared: ['str_replace_editor']
    2025-03-31 21:37:47.316 | INFO     | app.agent.toolcall:think:89 - 🔧 Tool arguments: {"command":"create","path":"/w/a.py","file_text":"x = 1"}
    2025-03-31 21:37:47.343 | INFO     | app.agent.toolcall:act:150 - 🎯 Tool 'str_replace_editor' completed its mission! Result: Observed output of cmd `str_replace_editor` executed:
    File created successfully at: /w/a.py
    2025-03-31 21:37:50.000 | INFO     | app.agent.toolcall:think:86 - 🧰 Tools being prepared: ['str_replace_editor']
    2025-03-31 21:37:50.000 | INFO     | app.agent.toolcall:think:89 - 🔧 Tool arguments: {"command":"str_replace","path":"/w/a.py","old_str":"x = 1","new_str":"x = 2"}
    2025-03-31 21:37:50.010 | INFO     | app.agent.toolcall:act:150 - 🎯 Tool 'str_replace_editor' completed its mission! Result: Observed output of cmd `str_replace_editor` executed:
    The file /w/a.py has been edited.
    2025-03-31 21:37:51.000 | INFO     | app.flow.planning:_mark_step_completed:301 - Marked step 0 as completed in plan plan_1
    2025-03-31 21:37:52.000 | INFO     | app.agent.toolcall:think:86 - 🧰 Tools being prepared: ['terminate']
    2025-03-31 21:37:52.000 | INFO     | app.agent.toolcall:think:89 - 🔧 Tool arguments: {"status":"success"}
    2025-03-31 21:37:52.010 | INFO     | app.agent.toolcall:act:150 - 🎯 Tool 'terminate' completed its mission! Result: Observed output of cmd `terminate` executed:
    The interaction has been completed with status: success
    2025-03-31 21:37:53.000 | INFO     | app.flow.planning:_mark_step_completed:301 - Marked step 1 as completed in plan plan_1
    """)

from right_rudder.adapters import chatdev

from right_rudder.adapters._code import apply_unified_diff

def _cd_update(ts, name, diff):
    return f"[{ts} INFO] **[Update Codes]**\n\n{name} updated.\n\n\n```\n'''\n\n'''\n{diff}\n```\n\n"

CHATDEV_CLEAN = (
    "[2025-29-03 23:36:43 INFO] **[Preprocessing]**\n\n**ChatDev Starts** (20250329233643)\n\n"
    + _cd_update("2025-29-03 23:44:09", "question.py", "--- Old\n+++ New\n@@ -1 +1,2 @@\n-# None\n+class Question:\n+    pass")
    + _cd_update("2025-29-03 23:44:09", "main.py", "--- Old\n+++ New\n@@ -1 +1,2 @@\n-# None\n+from question import Question\n+app = Question()")
    + "[2025-29-03 23:44:09 INFO] **[Software Info]**:\n\n"
    + _cd_update("2025-29-03 23:45:00", "question.py", "--- Old\n+++ New\n@@ -1,2 +1,3 @@\n class Question:\n-    pass\n+    def check(self):\n+        return True")
    + "[2025-29-03 23:46:00 INFO] **[Post Info]**\n\ndone\n"
)

from right_rudder.adapters import magentic

def _m1_sheet(verified, lookup, guess=()):
    out = ["", "Here is the updated fact sheet:", "", "1. GIVEN OR VERIFIED FACTS"]
    out += [f"   - {v}" for v in verified] or ["   - None"]
    out += ["", "2. FACTS TO LOOK UP"] + ([f"   - {v}" for v in lookup] or ["   - None"])
    out += ["", "3. FACTS TO DERIVE", "   - None", "", "4. EDUCATED GUESSES"] + ([f"   - {v}" for v in guess] or ["   - None"])
    out += ["", "Here is the plan to follow as best as possible:", "", "- WebSurfer will search.", ""]
    return "\n".join(out)

def _m1_log(sheets, final="42"):
    body = "---------- user ----------\nWhat is the answer?\n"
    for s in sheets:
        body += "---------- MagenticOneOrchestrator ----------\n" + s + "\n---------- WebSurfer ----------\nI typed a query.\n"
    body += f"---------- MagenticOneOrchestrator ----------\nFINAL ANSWER: {final}\n"
    return body

from right_rudder.adapters import hyperagent

def _ha(inst, who, text):
    return f"HyperAgent_{inst} - INFO - {who}: {text}"

def _ha_edit(path, start, end, body, thought="Apply the change."):
    return f"Thought: {thought}\n\nAction:\n```python\npatch = '''\n{body}\n'''\nresult = editor._run(relative_file_path=\"{path}\", start_line={start}, end_line={end}, patch=patch)\nprint(result)\n```"

HYPERAGENT_CLEAN = {"instance_id": "x__y-1", "trajectory": [
    _ha("x__y-1", "Planner's Response", "Thought: Locate the bug.\nIntern Name: Codebase Editor\nSubgoal: fix it"),
    _ha("x__y-1", "Inner-Editor-Assistant's Response", _ha_edit("pkg/a.py", 10, 12, "def f(x):\n    return x + 1")),
    _ha("x__y-1", "Inner-Editor-Assistant's Response", _ha_edit("pkg/a.py", 10, 12, "def f(x):\n    return x + 1")),  # logger repeat
    _ha("x__y-1", "Editor->Planner", _ha_edit("pkg/a.py", 10, 12, "def f(x):\n    return x + 1")),                    # relay
    _ha("x__y-1", "Inner-Editor-Assistant's Response", _ha_edit("pkg/a.py", 10, 12, "def f(x):\n    return x + 2", "Adjust the constant.")),
    _ha("x__y-1", "Planner's Response", "Thought: Done.\nFinal Answer: The fix is applied."),
]}

from right_rudder.adapters import appworld

def _aw_block(agent, code, output):
    return f"Response from {agent} Agent\n" + "\n".join("    " + l for l in code.splitlines()) + "\n\nCode Execution Output\n\n" + "\n".join("    " + l for l in output.splitlines()) + "\n\n"

APPWORLD_CLEAN = ("******************** Task 1/1 (abc) ********************\nLike two songs.\n"
    + _aw_block("Supervisor", "print(apis.api_docs.show_api_descriptions(app_name='spotify'))", "[...]")
    + _aw_block("Supervisor", "apis.spotify.like_song(song_id=55, access_token='t')", "Code executed successfully.")
    + _aw_block("Supervisor", "apis.spotify.like_song(song_id=30, access_token='t')", "Code executed successfully.")
    + _aw_block("Supervisor", "apis.supervisor.complete_task()", "Code executed successfully.\n{\"trace\": \"AssertionError: ...\"}"))

from right_rudder.adapters import ag2, metagpt

def _ag2(name, text):
    return {"role": "user", "name": name, "content": text.split("\n")}

AG2_CLEAN = {"instance_id": "t", "trajectory": [
    _ag2("mathproxyagent", "Solve it. Put the answer in \\boxed{}."),
    _ag2("assistant", "Key idea: multiply.\n```python\ndaily = 30\ndays = 7\ntotal = daily * days\nprint(total)\n```"),
    _ag2("mathproxyagent", "210"),
    _ag2("assistant", "So the answer is \\boxed{210}."),
]}

METAGPT_CLEAN = """=== MetaGPT Agent Communication Log - Started at 2025-03-31 12:53:42 ===

[2025-03-31 12:53:42] FROM: Human TO: {'<all>'}
ACTION: metagpt.actions.add_requirement.UserRequirement
CONTENT:
Write a palindrome detector.
--------------------------------------------------------------------------------

[2025-03-31 12:54:14] NEW MESSAGES:

SimpleCoder: 
def detect(text):
    return text == text[::-1]
--------------------------------------------------------------------------------

[2025-03-31 12:54:30] NEW MESSAGES:

SimpleTester: 
from SimpleCoder import detect

def test_detect():
    assert detect("aba")
--------------------------------------------------------------------------------

[2025-03-31 12:54:40] NEW MESSAGES:

SimpleReviewer: One critical comment: add an empty-string case. The answer is (0) is not relevant here.
--------------------------------------------------------------------------------

=== Communication Log Ended at 2025-03-31 12:55:09 ===
"""
