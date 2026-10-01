# Changelog

## 0.7.0 (unreleased)

Fathom is now Right Rudder, by Embedded Risk Analytics. The package installs as `right-rudder`, imports as `right_rudder`, and runs as the `right-rudder` command. The reads stay as they were. The same hosted service at read.embeddedriskanalytics.com forms every verdict, and existing free keys keep working.

Compatibility. The `fathom` command still works in this release. The `RIGHT_RUDDER_` environment variables take precedence, and the `FATHOM_` names still read as fallbacks. `FathomListener` remains as an alias of `RightRudderListener`. The final `fathom-read` release (0.7.0) depends on this package and re-exports it under `fathom_read` with a deprecation warning, so existing imports keep working.

## 0.6.0 (2026-09-18)

A deepagents adapter, so a deep-research run reads through the same committed-state path as the rest.

Adapter. `deepagents` maps a deepagents deep-research run to the op stream, the orchestrator's calls and each sub-agent's, a delegation to a research collection, a search to a query add with a source per result, a file write to a file set, and the report's cited urls to source refs, so a rewritten citation reads as a stale reference and a repeated search or delegation as a duplicate commit. `fathom read` recognises a deepagents trace from its own `calls` markers, and the package now reads fifteen formats. The trace comes from one `FathomCapture` at the graph root in langchain-fathom, which sees the sub-agents an orchestrator-level middleware does not.

## 0.5.0 (2026-09-17)

The repair, hosted, and free keys.

The repair. `fathom reground` and `fathom_read.reground()` send the run so far and the actions the agent proposes next,
and return proceed, filter, or reground, with the committed facts the proposals contradicted on a reground so the caller
can put them back in front of the agent and ask again. This is the step that ran in front of DBOS's Hacker News research
agent on 2 September, now served for any trace the adapters read. `RegroundVerdict.prompt_note()` renders the facts as a
prompt note.

Keys. `fathom key you@example.com` issues a free key on the spot, 2,000 calls a day with a repair call counting as two.
The two reads still accept the demo key with no sign-up. The service records call metadata and never op content.

## 0.4.1 (2026-09-16)

The openinference adapter takes a TOOL span's arguments from `input.value` when `tool.parameters` is missing or
carries the tool's argument schema instead of the call. Arize's CrewAI instrumentor writes spans that way (the schema
in `tool.parameters`, the arguments in `input.value`), and the adapter had read the schema as the arguments, so a
repeated search on such a span read as an add with no value. Spans whose `tool.parameters` carries the arguments read
as before.

## 0.4.0 (2026-09-15)

Seven adapters for frameworks that write their own log files, and one more thing the read reports.

Adapters. `chatdev`, `metagpt`, `openmanus`, `magentic`, `hyperagent`, `appworld` and `ag2` read the log a framework
already writes, with no export step, and `fathom read` recognises each from the log's own markers, so a `.log`, a
`.txt` or a trajectory `.json` can be passed as it is. The package now reads fourteen formats. The seven were built on
the MAST corpus (Cemri et al., 2025) and run over its 9,320 traces, and each adapter's docstring says what it treats
as a write and what it treats as a read. Two of them cover shapes the earlier adapters did not, a code workspace revised
across phases (ChatDev, MetaGPT, HyperAgent, and OpenManus's editor), where each file's symbols and imports are part of
the committed record, and an orchestrator's fact sheet rewritten every round (Magentic-One).

The read. A write of the value a fact already holds now reports as a `duplicate_commit`, beside the add of a member a
collection already holds. On the MAST corpus this is what a tester republishing an identical test file after a review
comment looks like, and an editor re-applying an identical patch, and until now the read treated both as no-ops. A
trace that re-sets an unchanged value read as coherent before this release and reports one duplicate commit after it.
Adapters whose records re-assert state by design (a fact sheet carried forward, an answer restated in a summary, a
code block re-run) write nothing for the re-assertion, so the report names actions taken twice.

The CLI. `fathom read` and `fathom expiry` accept a framework's log file where before they accepted JSON only, and
`fathom formats` lists all fourteen.

## 0.3.0 (2026-09-14)

The expiry read now carries covariates that cannot run off the end of their own calibration, and it refuses rather than
guesses where a read does not apply.

Covariates. The read scores on the share of steps the agent has committed on and the share of its live facts, both
derived from the ledger the adapters already build, replacing a cumulative write count that grew without bound on any
agent that keeps committing. Each covariate's fitted range is now its structural bound, so a long run stays inside the
region its calibration was fitted on. Scored across every trace we hold, 3552 runs over seven agent frameworks, none
leaves that region; the previous covariates covered the first 18 steps of a 514-step run.

Refusals. When more than a fifth of a run's steps fall outside the range its calibration was fitted on, the read
returns that condition in place of a life estimate and an alarm, and names the covariate, the step it left at and how
far the calibration carries the run. When the reported life falls below a quarter of the stretch a run has already
survived since its last contradiction, the read withholds the life estimate alone and says so, since the run itself
refutes the number.

The load alarm. This release withdraws it. Across our traces it fired within the first few steps of every run of every
commit-heavy workload regardless of when that run actually contradicted itself, so it tracked the step count rather than
the run. The exposure alarm stays, and the covariates behind the withdrawn alarm still feed the hazard and the life
estimate. `fathom expiry` exits 3 when the exposure alarm fired, and 0 when it did not or when the read does not apply.

Calibrations. All three are refitted on the op streams the adapters produce rather than on harness-recorded counts. The
pooled default and the relational calibration ship a first-contradiction fit only, because on the recurring-event
definition neither beat a plain step counter and a calibration that loses to counting steps does not ship.

## 0.2.0 (2026-09-13)

The expiry read. `fathom expiry trace.json` and `fathom_read.expiry(ops)` send the same op stream to the hosted service and get back, per step, the hazard that the agent's committed state spoils, the survival curve, the functional life remaining in steps, and two alarms, one that fires while a rejected action stands in the record and one that fires on committed load alone. Calibrations are named per workload and listed by the service; with none named the read scores under a pooled default and labels the result a shape rather than a number. Exit code 3 when an alarm fired. The contradiction read is unchanged and its verdict rides along in the expiry response.

## 0.1.0 (2026-09-02)

First release. Adapters and a CLI for the committed-state read, which reports six findings (stale reference, superseded value, authored contradiction, residual, duplicate commit, post-commit mutation), the `fathom` command, and adapters for native op streams, coding-agent edit logs, OpenInference spans, LangGraph state history, CrewAI event logs, Letta memory exports, and DBOS step streams.
