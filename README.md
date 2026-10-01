# right-rudder

**Catch the step where an AI agent contradicts a decision it already made.**

> Fathom is now Right Rudder, by Embedded Risk Analytics. `pip install right-rudder` replaces `fathom-read`, the `right-rudder` command replaces `fathom`, and the reads and free keys stay as they were. Code that imports `fathom_read` keeps working through the final `fathom-read` release.

On a long task, an agent loses track of what it already decided and starts acting against it. It renames `guest_id` to `customer_id` at step 1, then writes new code against `guest_id` at step 6. The change compiles, imports, and passes the tests. It fails at runtime.

`right-rudder` turns the traces your framework already records into an action stream and sends it to the Right Rudder read, which reconstructs the state the agent committed and flags the step that contradicts it. Deterministic. No model access. Nothing runs in your production path.

![right-rudder demo](docs/demo.gif)

## Install

```
pip install right-rudder
```

## Run

```
right-rudder demo                                              # the bundled rename example, coherent and not
right-rudder read trace.json --supersede guest_id=customer_id  # your own trace
right-rudder read history.json --format langgraph              # or name the format
right-rudder read trace.json --ops                             # see the action stream before anything is sent
right-rudder formats                                           # the formats it reads
```

`right-rudder read` exits 0 when the committed state is coherent and 2 when it finds a contradiction, so it drops into a test suite or a CI step as it is. Add `--json` for a machine-readable verdict.

## The expiry read

```
right-rudder expiry trace.json                                  # functional life remaining, and the exposure alarm
right-rudder expiry trace.json --calibration airline_tool_agent # score under a named workload calibration
right-rudder expiry trace.json --json                           # the full per-step report
```

Every agent run spoils eventually. `right-rudder expiry` reads the same action stream and reports how much functional life the run has left before its committed state contradicts itself, in steps, together with an alarm that fires while a rejected or corrupted action stands in the record. Both the estimate and the alarm move when the agent acts and stay flat while it only looks. A wall clock enters nowhere, because in our measurements the step count alone carries no information about when a run spoils once what stands in the record is accounted for.

The read scores on what the agent has committed and what it still holds, read as shares of the steps it has taken, so the quantities stay inside a fixed range however long a run gets. Across every trace we hold, 3552 runs over seven agent frameworks, none leaves the region its calibration was fitted on.

The read scores under a calibration fitted on a population of runs of a workload. The service lists the calibrations on offer, and with none named the read scores under a pooled default and labels the result a shape rather than a number. A calibration for your own workload comes from a batch of your traces, which is the readout we already offer. `right-rudder expiry` exits 3 when the alarm fired and 0 when it did not.

The read withholds rather than guesses in two cases. A run whose covariates leave the region its calibration was fitted on gets that condition in place of a life estimate and an alarm, naming the covariate, the step it left at, and how far the calibration carries the run. A run whose reported life falls short of the stretch it has already survived since its last contradiction keeps its alarm and loses the life estimate, since the run itself refutes that number. Both cases exit 0, because neither reports a clean bill of health and neither is an alarm.

```
$ right-rudder expiry rename_starved.json --format edits --supersede guest_id=customer_id

rename_starved.json
  calibration pooled_default (shape), 10 steps read, 5 contradiction(s)
  functional life remaining at step 9: about 3 step(s), median
  with the standing rejected action cleared: about 8 step(s)
  exposure alarm: first fired at step 6
```

That trace ships with the package, so the output above reproduces. A run the read declines looks like this instead.

```
  calibration pooled_default (shape), 443 steps read, 115 contradiction(s)
  no functional life remaining is reported. This run has already taken 34 step(s) without a
  contradiction, which is longer than the life the calibration puts on it, so the run itself
  refutes the estimate.
  exposure alarm: none
```

The package ships with a demo key that is rate-limited per day, and `right-rudder key you@example.com` issues a free key with a higher limit on the spot. Set `RIGHT_RUDDER_API_KEY`. `--ops` shows exactly what would be sent: the ops the adapter produced, and nothing else.

## The repair

```
right-rudder key you@example.com                                # a free key, printed once; export RIGHT_RUDDER_API_KEY=...
right-rudder reground trace.json --proposals '[{"op":"add","kind":"research","key":"queries","value":"..."}]'
```

The read names the step where an agent contradicted its own committed state. The repair runs in front of that step. Send the run so far and the actions the agent proposes to take next, in the agent's own order, and the service returns one of three decisions. Proceed means every proposal is consistent with what the agent has already committed. Filter means some are, and the first of them is the agent's own consistent alternative, so take it. Reground means none are, and the response carries the facts the proposals contradicted, the collection and what it already holds, the fact and the value it carries now, the key and the name it was renamed to, so you can put them back in front of the agent and ask again. `RegroundVerdict.prompt_note()` renders those facts as a note for the prompt.

On DBOS's own published Hacker News research agent (gpt-4o-mini, five topics, ten iterations), the repair in front of the one step where the agent proposes its next queries took repeated searches from 14 of 50 to 0 of 50, redundant thread reads from 42 percent to 12 percent, and distinct threads covered up 35 percent, at the same model and iteration count. The runs, the mapping, and every decision the repair made sit in the [coherence census](https://github.com/RightRudderAI/coherence-census/tree/main/rows/dbos-hn-agent).

The read and the repair are free to run. The two reads accept the demo key at a daily limit with no sign-up. The repair needs a key, and `right-rudder key` issues one on the spot for an email address, with a limit of 2,000 calls a day, a repair call counting as two. The service records call metadata (route, format, counts, decision, timing) and never the content of your ops unless you opt in. `right-rudder reground` exits 3 on reground and 0 otherwise.

```
$ right-rudder reground ops.json --proposals '[{"op":"add","kind":"research","key":"queries","value":"postgres performance"}]'

== ops.json: reground (1 proposal(s), 0 kept, 1 dropped)
  drop  add research 'queries' = 'postgres performance'  (duplicate_commit)
COMMITTED STATE CHECK. The following is already established in this run and must be honored:
- research 'queries' already holds: 'postgres performance', 'postgres indexing strategies'. Do not propose any of these again.
```

## What it reads

| Format | What you export | How |
|---|---|---|
| `langgraph` | The checkpoint lineage | `[{"values": s.values, "step": s.metadata["step"]} for s in graph.get_state_history(config)]` |
| `openinference` | The spans Arize Phoenix stores | Export the trace's spans as JSON; only TOOL spans matter |
| `crewai` | The crew's event log | A listener on the event bus, capturing `tool_usage_finished`, `tool_usage_error`, `task_completed` |
| `letta` | Blocks, passages, and the memory-edit tool calls | `agents.blocks.list`, `agents.passages.list`, the tool calls from `agents.messages.list` |
| `dbos` | A workflow's step stream | `{"workflow_id": ..., "steps": [{"step_name", "args", "result", "ok"}]}` |
| `edits` | A coding agent's edit log | `{"initial_files": {...}, "edits": [{"tool": "str_replace_editor", "args": {...}, "ok": true}]}` |
| `deepagents` | A deepagents run's tool calls, with sub-agent ancestry | One `RightRudderCapture` at the graph root (langchain-right-rudder), which follows the orchestrator into its sub-agents |
| `events` | The native op stream | One op per line: `{"op": "set", "kind": "file", "key": "a.py", "value": "...", "ok": true}` |

Seven frameworks are read from the log files they already write, with no export step. Point `right-rudder read` at the file and the format is recognised from the log's own markers.

| Format | The file it reads | What counts as committed state |
|---|---|---|
| `chatdev` | The chat-chain `.log` in a WareHouse project folder | Every code update, folded onto the running copy of each file, with the symbols each file defines and the sibling symbols it imports |
| `metagpt` | The agent communication log | The code each role publishes, with its symbols and imports |
| `openmanus` | The `run_flow` log | The plan's steps, the files the editor creates and edits, and the terminate call |
| `magentic` | A Magentic-One `console_log.txt` | The orchestrator's fact sheet, one fact per line with the standing it was given, and the final answer |
| `hyperagent` | A HyperAgent trajectory (`.json` or the release's text dump) | The regions and symbols the Editor intern wrote |
| `appworld` | A task's agent log | Mutations through the app APIs, and the task's completion |
| `ag2` | An AG2 math dialogue (`.json`, or the release's text forms) | Numeric quantities stated in code and the boxed answer |

These seven were built on the MAST corpus ([Cemri et al., 2025](https://arxiv.org/abs/2503.13657)) and run over its 9,320 traces. Each adapter's docstring states what it treats as a write and what it treats as a read.

Your tools have their own names. Map them once with `--map tools.json`:

```json
{"save_decision": {"op": "set", "kind": "decision", "key": "topic", "value": "text"},
 "book_seat":     {"op": "add", "kind": "flight", "key": "seats", "value": "seat"},
 "confirm_booking": {"op": "commit", "kind": "flight", "key": "booking"}}
```

## What it finds

| Finding | The agent... |
|---|---|
| `stale_reference` | acts on a fact it already removed or renamed away |
| `superseded_value` | writes or answers with a value it already replaced |
| `authored_contradiction` | reintroduces a token into a record it had already migrated |
| `residual` | ends the run with a record still carrying a value it replaced elsewhere |
| `duplicate_commit` | adds an entity a collection already holds, or writes a fact with the value it already holds |
| `post_commit_mutation` | changes a thing after committing it |

Every finding cites the earlier step it contradicts, so the readout is a diff between what the agent decided and what it did.

## How it reads

The read folds the agent's successful actions into a ledger of committed facts and checks every later action against the ledger. Two rules make this a reconstruction rather than a transcript. A failed action is a no-op: an edit the tool rejected leaves nothing behind. And the read consults only the agent's own actions and their results, never an answer key, so it attaches the same way on any framework. The adapters and the CLI in this repository build the action stream; the read itself runs in ERA's service.

## Use it from Python

```python
from right_rudder import Op, read

ops = [
    Op("set", "fact", "user.city", value="Denver"),
    Op("set", "fact", "user.city", value="Austin"),
    Op("answer", "fact", "user.city", value="The user lives in Denver."),
]
verdict = read(ops)          # uses RIGHT_RUDDER_API_KEY, or the demo key
for f in verdict.findings:
    print(f.kind, f.step, f.detail)
# superseded_value 2 step 2 answers 'Denver' for fact 'user.city', a value the agent replaced with 'Austin' at step 1.

from right_rudder import expiry
report = expiry(ops, calibration="airline_tool_agent")
print(report["expiry"]["remaining"]["median_steps"], report["expiry"]["alarm"]["exposure_first_step"])
```

## What it does not do

It does not run your agent, call a model, or need one. It does not say why the agent contradicted itself or which repair would fix it; that is the [design-partner engagement](https://embeddedriskanalytics.com/contact.html). The expiry read predicts contradiction of committed state, and on the workloads we have measured a contradiction ends a task's chance of passing, but the read says nothing about task reward directly, and a life estimate for a single run carries a wide interval, which is why the alarm is the part to wire in. It reads agents whose committed state lives in tool calls, checkpoints, memory writes, or edits; an agent that keeps state only in free-text logs is out of scope.

## Research

The read comes out of the Right Rudder program at [Embedded Risk Analytics](https://embeddedriskanalytics.com). Case studies on LangGraph, CrewAI, Letta, OpenHands, Agent-E, ContextPilot, and τ-bench are at [embeddedriskanalytics.com/research](https://embeddedriskanalytics.com/research.html). The theory is in [Records, Reflexive Modeling, and the Conditions for Stable Physical Histories](https://ssrn.com/abstract=6683578) (SSRN, 2026). See [CITATION.cff](CITATION.cff).

## Send us a trace

If you run long-horizon agents and want a readout on your own traces, send a batch: [embeddedriskanalytics.com/contact](https://embeddedriskanalytics.com/contact.html).

## License

MIT. Right Rudder is a trademark of Embedded Risk Analytics.


---

If the read caught something in your own run, a star on this repository helps other teams find it.
