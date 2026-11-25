# The process

This is the process behind the `/factory` command. `SKILL.md` is the short version the orchestrator follows. This file holds the reasons and the detail.

Words used here:
- **Owner**: the person the work is for.
- **Orchestrator**: the agent that plans, dispatches and judges. It writes no product code.
- **Piece**: one unit of the build graph. It owns a set of files.
- **Gate**: a point where only the owner can decide.

## The shape

```
Intake > Plan > Plan review > GATE A > Tests first (red, locked)
  > Build loop per piece (maker, fast checks, checker, fix loop)
  > Integration > End to end as a user > Evals (tier R) > GATE B > Release > Retro
```

Two human gates. Between them nothing waits on the owner unless a breaker fires.

## Roles

| Role | Job | Rule |
|---|---|---|
| Orchestrator | Holds the graph, writes every message to other agents, keeps the log. | Writes no product code. |
| Planner | Writes goals, spec, graph, rubric and test plan. | Highest effort setting. |
| Plan reviewer | Finds what is missing or wrong in the plan. | A different vendor than the maker. |
| Test writer | Writes tests from the test plan before any code exists. | Fresh session. A different vendor than the maker. |
| Maker | Builds one piece from a small packet. | Never sees the whole plan. |
| Checker | Runs everything, judges each rubric item with evidence. | Never the same session as the maker. |
| Stuck diagnosis | Looks at a piece when one rubric item fails twice. | A different vendor than the maker. |
| Final reviewer | One pass over the full diff before GATE B. | A different vendor than the maker. |
| Summaries | Mechanical work, log summaries. | A local model when the material is private. |

Roles and models are settings, not part of the process. A project may add roles the kit has never heard of. They are probed, logged and shown like any other.

## Artifacts

In the project, under `plan_dir` (default `build/<feature>/`): `INTAKE.md`, `GOALS.md`, `SPEC.md`, `GRAPH.yaml`, `RUBRIC.md`, `TESTPLAN.md`, `QUESTIONS.md`, and `TESTLOCK` once tests are locked. Templates for each are in `templates/`.

Outside the project, in the Factory home folder (`$FACTORY_HOME`, else `~/.factory`): the build log and messages. Logs are private. They are never copied into a public repo.

Context discipline: a maker gets a node packet, not the plan. A packet holds its slice of the spec, its rubric items, its tests, the interfaces it must honor and the constitution.

## Goals

The loop runs until the goal is met. A goal has three kinds of conditions, all of which must hold:

1. **Acceptance criteria.** Behavior a stranger can check. Each one is tagged MUST or SHOULD and maps to tests.
2. **Eval targets.** Numbers that say the feature does its job well, not only that it runs.
3. **Invariants.** The project's constitution plus anything feature-specific.

A constitution is a short list of rules every feature inherits. It can change through an amendment: a short note that says what changes, why, what evidence supports it and what it costs. The owner approves it at a gate.

## Tiers

- **Tier B** (behavior, commands, packaging, docs): acceptance tests, a regression suite and an install-and-run journey. No evals.
- **Tier R** (anything that changes what a system picks, ranks or cites): also needs metrics with a baseline measured first, a noise floor, targets above the noise, guards, a held-out set and a kill criterion. Metrics live in `factory.json` under `evals.metrics` and run with `factory step evals.<metric id>`.

Rules for evals: baseline before treatment. Lock the rubric before runs. Score artifacts, not self-reports. Never tune on the held-out set. Two models agreeing is not validation of a fact that can be looked up; look it up.

## Tests

Step zero is the readiness gate: confirm the existing suites are green on untouched code, add one fast command that runs them all, confirm it is green, and freeze that harness. Tests cannot be trusted while their harness is changing.

Then:
1. Cases are designed at plan time in `TESTPLAN.md`: id, layer, input, expected result, which criterion it proves.
2. A test writer from a different vendor writes them as code.
3. **Test-acceptance gate.** The existing suite is still green. Every new test fails for the expected reason (a failing assertion about missing behavior, not a syntax error, missing fixture or import crash). Each criterion maps to tests that encode it.
4. Lock the test files by recording their commit and content hashes in `TESTLOCK`.
5. Test files are read-only inputs for makers. The checker fails any piece whose diff touches a locked test. Only the test writer may change one, and only after the planner records a `test-wrong` decision.

| Layer | What | Speed |
|---|---|---|
| L0 static | validators, schema, parity checks | seconds |
| L1 unit | pure functions, error paths, edge cases | seconds |
| L2 contract | every command and flag: output, errors, exit code, determinism | seconds |
| L3 end to end | the installed or packed product, real user journeys | about a minute |
| L4 agent evals | real agents using the product | hours, milestones only |

Run L0 to L2 on every maker pass. Tests must be fast: a test never waits out a real limit, because every limit is a setting that tests set to a fraction of a second.

## The build graph

```yaml
nodes:
  - id: P1
    depends_on: []
    owns_files: [src/x.py]
    exposes: "function(args) -> result"
    tests: [T1, T2]
    goal: [AC1, AC2]
integration_node: INT
```

Each file has exactly one owning piece. When two pieces need the same file, one owns it and exposes an interface, or the pieces run in sequence. The integration piece only wires things together and resolves conflicts. If it contains real code, it runs the normal maker and checker loop.

Independent chains can run in parallel worktrees, merged in graph order with the fast suite after each merge. For a small feature, one build stream plus the integration review is enough.

## Plan review: exit on quality

The plan leaves review when every checklist item is yes and the reviewer has no open blocker or major finding.

1. Every outcome has acceptance criteria, and every criterion maps to tests.
2. A stranger could check every criterion without asking what was meant.
3. Every command's error and edge behavior is specified (bad input, empty input, missing files, no terminal).
4. The tier is set, and its evidence plan is complete.
5. The graph has dependencies, file ownership and an integration piece.
6. Every constitution rule is checked: pass, or an amendment.
7. Backward compatibility and versioning are decided.
8. Docs impact is listed.
9. The top 3 risks each have a mitigation.
10. The budget fits the deadline.

Rounds continue while each round closes findings. **Breaker at 3 rounds.** A plan that has not converged by then almost always has a decision only the owner can make, so those go to the owner at GATE A as a short list.

## Build loop and breakers

A piece loops until its goal is met.

- The same rubric item fails twice: a second vendor diagnoses before the next try.
- Two churn rounds in a row (a round where no new item passes): stop and re-plan the piece. The packet or the spec is the problem, not effort. Thrash is an item that flips from pass to fail.
- Piece time box exceeded (`timers.node_timebox_s`): log it, then continue, split or escalate.
- Absolute stop times (set with `factory new --stop`): feature freeze, integration start, GATE B, release start. If a piece threatens one, SHOULD criteria are cut and the cut is logged. Cutting or changing a MUST criterion after GATE A needs the owner. Without that approval the result is a release candidate, not a release.
- Eval kill criterion reached: stop and report.

Failure classes are a fixed list: `spec-ambiguity`, `test-wrong`, `impl-bug`, `env-tooling`, `flaky`, `scope-creep`, `context-overflow`, `model-stall`. Work that was not planned is logged as `scope-creep`. Improvements noticed along the way go to `IMPROVEMENTS.md`, and the planner triages them at the next planning round.

## The log

Every build writes one append-only log of spans: a feature holds phases, a phase holds pieces, a piece holds iterations, and an iteration holds agent calls, commands and waits. The code fills ids, times, durations and rubric deltas. You never type them.

Rules:
- The log is not memory. Raw log lines never go into a model prompt. Only the computed report may be shown to a model.
- Code decides, the model suggests. Durations, loop counts and bottlenecks come from `factory trace-report`.
- Append only. A span changes state by appending another line.
- Secrets are removed before a line is written.
- A person switches on process changes. Reports propose and change nothing.

Wrapped calls log themselves (`factory run`, `factory step`). Everything else uses `factory log start` and `factory log end`. Because the second path depends on the orchestrator remembering, `factory check` compares the calls that were expected with the calls that were logged and reports anything missing, unplanned, duplicated or never finished. It runs before each gate and before the report card.

## Data rule

Every role handles private material. Whether a call may go to a model that keeps what it is sent (some free tiers) is decided per call. Such a call needs `--non-private` on `factory run`, and the input must prove it: under a folder listed in `public_roots`, or clean under the kit's built-in scan. Only non-private material may go to such a model: content already public, synthetic fixtures, and prompts that hold none of the project's private code, logs, messages or settings. When in doubt, it is private.

## Visibility and approvals

- Every agent is visible: either a named session in an app that shows sessions, or a row on `factory status`.
- One board shows each piece, its phase, loop count, time spent, last verdict and what it waits on.
- Notifications are for decisions only. Routine progress never notifies. Channels are the configured ones, nothing else.
- Agents run without per-command approval inside their own worktree. Safety comes from isolation: own branch, nothing pushed, published or merged without GATE B.
- Every approval is logged as a wait on a person, so waiting is measured like any other bottleneck.

## Gates

Gate questions are plain: one question, one suggested answer, one sentence why. No ids, no section numbers. At most 5 per gate. `factory gate open` refuses jargon and long text. Questions that wait longer than they should are the most common way a build loses time, so write them to be answered in one reply.

## Release

Preflight at the start of the day, not the end: `factory preflight --release` runs each `release.preflight` entry (for example a registry login check). If one fails, the day's outcome is a tagged, checked release candidate, not a release.

Release candidate:
1. Clean tree on the feature branch, all CI green, fast suite green, end-to-end journey green from the built package.
2. Version bumped everywhere it appears, changelog entry, docs updated.
3. Inspect package contents. Nothing private.
4. Record the candidate commit in the log.

GATE B: the owner approves the candidate commit and the publish. After that: merge, tag, publish, then the smoke steps (`factory step release.smoke.<name>`). A broken publish gets a deprecation or yank plus a fixed patch release. Never overwrite a version.

## Retro

Run `factory check`, then `factory trace-report` and `factory report-card`. They answer: which phase, piece or actor took longest; how many loops each piece needed and whether they made progress; how much time was spent waiting on a person; where nobody was working. Pick at most 3 process changes to propose, and change one process variable per build so the effect can be told apart.
