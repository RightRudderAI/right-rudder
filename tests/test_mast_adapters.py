"""Adapter tests for the seven framework-log formats (OpenManus, ChatDev, MetaGPT, Magentic-One,
HyperAgent, AppWorld, AG2). Each test checks the op stream an adapter produces from a small clean
record in the framework's own log format, and how that stream changes when the record changes. The
read that consumes the stream runs in the hosted service, so these tests stop at the ops."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _mast_fixtures import *  # noqa: F401,F403
from _mast_fixtures import _cd_update, _m1_sheet, _m1_log, _ha, _ha_edit, _aw_block, _ag2  # noqa: F401
from fathom_read import adapters, load_ops


# --- detection and the CLI's text path -------------------------------------------------------

def test_text_logs_detect_by_their_own_markers():
    assert adapters.detect(OPENMANUS_CLEAN) == "openmanus"
    assert adapters.detect(CHATDEV_CLEAN) == "chatdev"
    assert adapters.detect(METAGPT_CLEAN) == "metagpt"
    assert adapters.detect(_m1_log([_m1_sheet(["a fact"], [])])) == "magentic"
    assert adapters.detect(APPWORLD_CLEAN) == "appworld"
    assert adapters.detect(HYPERAGENT_CLEAN) == "hyperagent"
    assert adapters.detect(AG2_CLEAN) == "ag2"


def test_load_ops_reads_a_framework_log_file(tmp_path):
    p = tmp_path / "run.log"
    p.write_text(OPENMANUS_CLEAN)
    ops = load_ops(str(p))
    assert [o.source for o in ops][:3] == ["plan", "plan", "create"]
    q = tmp_path / "trace.json"
    q.write_text(json.dumps(HYPERAGENT_CLEAN))
    assert [o.kind for o in load_ops(str(q))] == ["symbol", "region", "symbol", "region", "answer"]


def test_formats_lists_fifteen_adapters():
    assert len(adapters.FORMATS) == 15
    for name in adapters.TEXT_FORMATS:
        assert hasattr(adapters.FORMATS[name], "looks_like")


# --- OpenManus -----------------------------------------------------------------------------------

def test_openmanus_plan_steps_files_and_terminate():
    ops = openmanus.load(OPENMANUS_CLEAN)
    assert [o.source for o in ops] == ["plan", "plan", "create", "str_replace", "mark_step_completed", "mark_step_completed",
                                       "terminate", "mark_step_completed", "mark_step_completed"]
    assert ops[3].value == "x = 2" and ops[3].refs == [("file", "/w/a.py")]
    marks = [o for o in ops if o.source == "mark_step_completed"]
    assert [(o.op, o.kind) for o in marks] == [("add", "plan"), ("remove", "plan_step")] * 2


def test_openmanus_rejected_create_leaves_the_edit_unapplied():
    rejected = OPENMANUS_CLEAN.replace("File created successfully at: /w/a.py", "Error: Permission denied: /w/a.py")
    ops = openmanus.load(rejected)
    assert ops[2].ok is False and ops[3].ok is False


def test_openmanus_default_plan_is_materialised():
    text = ("2025-03-31 20:57:08.268 | INFO     | app.flow.planning:_create_initial_plan:138 - Creating initial plan with ID: plan_9\n"
            "2025-03-31 20:57:16.213 | WARNING  | app.flow.planning:_create_initial_plan:183 - Creating default plan\n")
    assert [o.key for o in openmanus.load(text)] == ["plan_9:0", "plan_9:1", "plan_9:2"]


# --- ChatDev -------------------------------------------------------------------------------------

def test_chatdev_folds_diffs_and_commits_symbols_before_files():
    ops = chatdev.load(CHATDEV_CLEAN)
    files = {o.key: o.value for o in ops if o.kind == "file" and o.ok}
    assert files["question.py"] == "class Question:\n    def check(self):\n        return True"
    assert files["main.py"] == "from question import Question\napp = Question()"
    assert [(o.op, o.kind, o.key) for o in ops[:4]] == [("set", "symbol", "question.Question"), ("set", "symbol", "main.app"),
                                                       ("set", "file", "question.py"), ("set", "file", "main.py")]
    assert ops[3].refs == [("symbol", "question.Question")]


def test_chatdev_dropped_class_is_removed_before_the_dependent_file_is_rewritten():
    changed = CHATDEV_CLEAN.replace("[2025-29-03 23:46:00 INFO] **[Post Info]**",
        _cd_update("2025-29-03 23:45:30", "question.py", "--- Old\n+++ New\n@@ -1,3 +1,2 @@\n-class Question:\n-    def check(self):\n-        return True\n+def load():\n+    return []")
        + _cd_update("2025-29-03 23:45:40", "main.py", "--- Old\n+++ New\n@@ -1,2 +1,2 @@\n from question import Question\n-app = Question()\n+app = Question(1)")
        + "[2025-29-03 23:46:00 INFO] **[Post Info]**")
    ops = chatdev.load(changed)
    removed = next(o for o in ops if o.op == "remove" and o.key == "question.Question")
    rewrite = [o for o in ops if o.kind == "file" and o.key == "main.py"][-1]
    assert removed.step < rewrite.step and ("symbol", "question.Question") in rewrite.refs


def test_chatdev_diff_that_does_not_apply_is_rejected():
    bad = CHATDEV_CLEAN.replace("@@ -1,2 +1,3 @@\n class Question:\n-    pass", "@@ -1,2 +1,3 @@\n class Question:\n-    passX")
    rejected = [o for o in chatdev.load(bad) if not o.ok]
    assert len(rejected) == 1 and rejected[0].key == "question.py"


def test_unified_diff_applier_roundtrip():
    assert apply_unified_diff("a\nb\nc", "--- Old\n+++ New\n@@ -1,3 +1,3 @@\n a\n-b\n+B\n c") == ("a\nB\nc", True)
    assert apply_unified_diff("a\nb\nc", "--- Old\n+++ New\n@@ -1,3 +1,3 @@\n a\n-x\n+B\n c") == (None, False)


# --- Magentic-One -------------------------------------------------------------------------------

def test_magentic_sheet_lines_become_facts_with_a_standing():
    ops = magentic.load(_m1_log([
        _m1_sheet(["The video was released in 1961."], ["The name of the scientist who spoke first."]),
        _m1_sheet(["The video was released in 1961.", "Claude Shannon spoke first."], ["The year Shannon made the prediction."]),
    ]))
    kinds = [(o.op, o.kind, o.value.split(" ", 1)[0] if o.value else None) for o in ops]
    assert kinds[:2] == [("set", "fact", "verified"), ("set", "fact", "lookup")]
    assert any(o.op == "remove" for o in ops)             # the answered look-up left the sheet
    assert ops[-1].op == "answer" and len(ops[-1].refs) == 2


def test_magentic_carried_line_writes_nothing_and_a_moved_line_writes_once():
    fact = "The video was released in 1961."
    ops = magentic.load(_m1_log([_m1_sheet([fact], []), _m1_sheet([], [fact]), _m1_sheet([fact], [])]))
    sets = [o for o in ops if o.op == "set" and o.key == magentic._norm(fact)]
    assert [o.value.split(" ", 1)[0] for o in sets] == ["verified", "lookup", "verified"]


def test_magentic_rephrased_line_keeps_its_identity():
    a = "The album Tidal was released by Fiona Apple in 1996."
    b = "Fiona Apple released the album Tidal in 1996."
    ops = magentic.load(_m1_log([_m1_sheet([a], []), _m1_sheet([b], [])]))
    sets = [o for o in ops if o.op == "set"]
    assert len(sets) == 1 and sets[0].key == magentic._norm(a) and not any(o.op == "remove" for o in ops)


# --- HyperAgent ---------------------------------------------------------------------------------

def test_hyperagent_relay_and_logger_repeat_are_not_actions():
    ops = hyperagent.load(HYPERAGENT_CLEAN)
    assert [o.kind for o in ops] == ["symbol", "region", "symbol", "region", "answer"]
    assert [o.key for o in ops if o.kind == "region"] == ["pkg/a.py:10-12"] * 2
    assert ops[-1].refs == [("region", "pkg/a.py:10-12")]


def test_hyperagent_identical_reapplied_edit_sets_the_same_value_again():
    doc = dict(HYPERAGENT_CLEAN)
    doc["trajectory"] = HYPERAGENT_CLEAN["trajectory"][:5] + [
        _ha("x__y-1", "Inner-Editor-Assistant's Response", _ha_edit("pkg/a.py", 10, 12, "def f(x):\n    return x + 2", "Fix the indentation.")),
    ]
    regions = [o for o in hyperagent.load(doc) if o.kind == "region"]
    assert len(regions) == 3 and regions[1].value == regions[2].value


def test_hyperagent_prompt_template_is_skipped():
    doc = dict(HYPERAGENT_CLEAN)
    doc["trajectory"] = [_ha("x__y-1", "Inner-Editor-Assistant's Response", "Use the following format:\n\nFor example:\n" + _ha_edit("astropy/timeseries/sampled.py", 318, 318, "def remove_column(self, name):\n    pass"))]
    assert hyperagent.load(doc) == []


def test_hyperagent_reads_the_release_text_form():
    text = "instance_id: x__y-1\nproblem_statement: p\ntrajectory:\n" + "\n".join("  " + l for l in HYPERAGENT_CLEAN["trajectory"])
    assert [o.kind for o in hyperagent.load(text)] == ["symbol", "region", "symbol", "region", "answer"]


# --- AppWorld -----------------------------------------------------------------------------------

def test_appworld_reads_produce_no_ops_and_literal_mutations_are_distinct():
    ops = appworld.load(APPWORLD_CLEAN)
    assert [(o.op, o.key) for o in ops] == [("add", "spotify.like_song"), ("add", "spotify.like_song"), ("answer", "task"), ("commit", "task")]
    assert all(o.ok for o in ops)   # the evaluation dump after the final block is not a failure


def test_appworld_failed_block_is_rejected_and_variable_bound_calls_carry_their_block():
    text = ("Task 1/1 (x)\n"
        + _aw_block("Spotify", "resp = apis.spotify.remove_song_from_library(access_token=access_token, song_id=song_id_to_remove)", "Execution failed. Traceback:\nKeyError: 'song_id'")
        + _aw_block("Spotify", "resp = apis.spotify.remove_song_from_library(access_token=access_token, song_id=song_id_to_remove)", "Code executed successfully.")
        + _aw_block("Spotify", "resp = apis.spotify.remove_song_from_library(access_token=access_token, song_id=song_id_to_remove)", "Code executed successfully."))
    ops = appworld.load(text)
    assert [o.ok for o in ops] == [False, True, True]
    assert len({o.value for o in ops}) == 3


def test_appworld_credential_only_call_is_an_advance():
    text = ("Task 1/1 (x)\n"
        + _aw_block("Spotify", "apis.spotify.next_song(access_token='t')", "Code executed successfully.")
        + _aw_block("Spotify", "apis.spotify.next_song(access_token='t')", "Code executed successfully."))
    ops = appworld.load(text)
    assert len(ops) == 2 and ops[0].value != ops[1].value


# --- AG2 ----------------------------------------------------------------------------------------

def test_ag2_numeric_facts_and_boxed_answer():
    ops = ag2.load(AG2_CLEAN)
    assert [(o.kind, o.key, o.value) for o in ops] == [("fact", "daily", "daily 30"), ("fact", "days", "days 7"), ("answer", "final", "boxed 210")]


def test_ag2_restated_answer_writes_nothing_and_a_changed_answer_writes_once():
    doc = {"instance_id": "t", "trajectory": AG2_CLEAN["trajectory"] + [
        _ag2("mathproxyagent", "Continue."),
        _ag2("assistant", "So again, \\boxed{210}."),
        _ag2("mathproxyagent", "Continue."),
        _ag2("assistant", "On reflection \\boxed{200}."),
    ]}
    assert [o.value for o in ag2.load(doc) if o.key == "final"] == ["boxed 210", "boxed 200"]


def test_ag2_failed_execution_rejects_the_block_and_solution_found_is_parsed():
    doc = {"instance_id": "t", "trajectory": [
        _ag2("Agent_Code_Executor", "```python\nx = 5\nprint(x/0)\n```"),
        _ag2("Agent_Verifier", "exitcode: 1 (execution failed)\nZeroDivisionError"),
        _ag2("Agent_Problem_Solver", "The answer is \\boxed{5}."),
        _ag2("Agent_Verifier", "**SOLUTION_FOUND \\boxed{5}**"),
    ]}
    ops = ag2.load(doc)
    assert ops[0].ok is False and ops[-1].op == "answer" and ops[-1].value == "5" and ops[-1].refs == [("answer", "final")]


def test_ag2_fraction_and_decimal_spellings_are_one_answer():
    assert ag2._norm_answer("43/2") == ag2._norm_answer("21.5") == ag2._norm_answer("$21.50") == "21.5"
    doc = {"instance_id": "t", "trajectory": [
        _ag2("assistant", "```python\nprint(f\"\\\\boxed{${final}}\")\n```\nSo \\boxed{43/2}."),
        _ag2("mathproxyagent", "21.5"),
        _ag2("assistant", "\\boxed{21.5}"),
    ]}
    assert [o.value for o in ag2.load(doc) if o.key == "final"] == ["boxed 21.5"]


def test_ag2_reads_the_release_text_forms():
    repr_form = " ".join(repr({"content": m["content"], "role": m["role"], "name": m["name"]}) for m in AG2_CLEAN["trajectory"])
    assert [o.value for o in ag2.load(repr_form)] == ["daily 30", "days 7", "boxed 210"]


# --- MetaGPT ------------------------------------------------------------------------------------

def test_metagpt_roles_publish_files_and_tests_ref_the_coder_symbols():
    ops = metagpt.load(METAGPT_CLEAN)
    files = [o for o in ops if o.kind == "file"]
    assert [f.key for f in files] == ["SimpleCoder.py", "SimpleTester.py"]
    assert files[1].refs == [("symbol", "SimpleCoder.detect")]
    assert not any(o.kind == "answer" for o in ops)


def test_metagpt_republished_tests_set_the_same_value_again():
    tests = "SimpleTester: \nfrom SimpleCoder import detect\n\ndef test_detect():\n    assert detect(\"aba\")\n" + "-" * 80 + "\n\n"
    log = METAGPT_CLEAN.replace("=== Communication Log Ended", "[2025-03-31 12:54:50] NEW MESSAGES:\n\n" + tests + "=== Communication Log Ended")
    files = [o for o in metagpt.load(log) if o.kind == "file" and o.key == "SimpleTester.py"]
    assert len(files) == 2 and files[0].value == files[1].value
