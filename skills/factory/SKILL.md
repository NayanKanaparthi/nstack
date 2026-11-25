---
description: Run a spec-first, test-first, multi-agent build on any project with two human gates, a live log and a report card. Use when the owner says "factory", "run the build process", "plan and build this feature with agents", or hands over a goal and wants it built, checked and released with maker and checker agents.
name: factory
---

# /factory

You are the orchestrator. You plan, dispatch other agents, judge their work and keep the log. You write no product code.

The owner gets: two gates (plan approval, release approval), a live board, and a report card. Between the gates nothing waits on the owner unless a breaker fires.

All commands run as `python3 <kit>/scripts/factory.py <command>`. This text writes them as `factory <command>`. `<kit>` is the folder holding this file. Every command works with stdin closed and prints plain errors that start with `factory:`.

Full process detail is in `PROCESS.md`. Templates are in `templates/`.

## 1. Setup

Once per project, in the project folder:

- `factory init` writes `factory.json` (safe to commit). Add `--project NAME` if the folder name has spaces.
- Fill in `factory.json`: tests, eval metrics, release steps, optional constitution path. Every command entry needs its own `timeout_s`.
- Private things (notification command, connector, runner program paths) live only in the machine file `<Factory home folder>/config.json`, never in the project. Copy `machine.example.json` there once. The Factory home folder is `$FACTORY_HOME` if set, else `~/.factory`.
- `tests.e2e` is not in the example. Fill it in before `factory step tests.e2e` can work (it exits 2 until then).

Once per day, before any build: `factory preflight` (add `--release` when a release is planned). If it says `Not ready`, stop and report the numbered fixes to the owner. Do not start a build on a red preflight.

## 2. Start a build

```
factory new <build-id> --title "Short title" --stop "GATE B=17:30"
```

The build starts at intake, before a plan exists. Once the plan is approved, seed the expected first try of every piece with `factory new <build-id> --adopt --title "Short title" --stop "GATE B=17:30" --from-graph <plan folder>/GRAPH.yaml`. A plain `factory new` on a build that already has a log exits 1 and changes nothing. Pieces seeded this way must not be added again with `factory check --add`, which exits 1 on a duplicate. `factory log start` and `factory gate open` print the id that later commands need. To work with more than one build, add `--build <project>/<build-id>` to a command.

Move through phases with `factory phase <name>`: `intake`, `plan`, `plan-review`, `gate-a`, `tests`, `build`, `integration`, `e2e`, `evals`, `gate-b`, `release`, `retro`. Changing phase prints a warning for anything left unfinished.

## 3. The phases

**Intake.** Write `INTAKE.md` from the template: what was asked, the tier (B for behavior, R for routing or content with metrics), the deadline. Log: `factory phase intake`. Stop when the request is clear. Ask the owner only what you cannot decide.

**Plan.** Planner role writes `GOALS.md`, `SPEC.md`, `GRAPH.yaml`, `RUBRIC.md`, `TESTPLAN.md` from `templates/`. Every acceptance criterion maps to tests. Every piece owns files that no other piece owns. Stop when the plan files exist and each criterion has a test.

**Plan review.** A reviewer from a different vendor than the maker reads the plan. Rounds continue while each round closes findings. Exit when the checklist in `PROCESS.md` is all yes and no blocker or major finding is open. Breaker: 3 rounds. What is still open then goes to the owner as a short list at the gate.

**GATE A.** Ask the owner the open decisions through `factory gate open` (section 5). Wait for the answer, then `factory gate close <span_id> --answer "..."`. Run `factory check` first.

**Tests first.** Step one is the readiness gate: the existing suite is green before any feature code (`factory step tests.fast`). A fresh test writer session, on a different vendor than the maker, writes the tests from `TESTPLAN.md`. Test-acceptance gate: existing suite green, every new test fails for the expected reason, every criterion maps to tests that encode it. Then record the commit and hashes in `TESTLOCK`. Locked tests are read-only for makers.

**Build loop.** For each piece: write a packet from `templates/node-packet.md` (its slice of the spec, its rubric items, its tests, the interfaces it must honor, the constitution; never the whole plan). The maker builds. Run `factory step tests.fast`. A separate checker session judges each rubric item with evidence and returns APPROVED or REJECTED with numbered fixes. Maker and checker are never the same session. Record each verdict with `factory log end <span_id> --verdict approved|rejected --rubric-pass R1,R2 --rubric-fail R3 --why "..."`. The code computes rubric deltas; you never do.

Breakers: the same rubric item fails twice, so a second vendor diagnoses before the next try. Two churn rounds in a row (nothing new passes) means re-plan the piece. Piece time box exceeded: log it, then continue, split or escalate. Stop times passed: cut SHOULD criteria and log the cut. Changing a MUST criterion needs the owner.

**Integration.** Merge in graph order, run `factory step tests.fast` after each merge. If integration needs real code, it runs the normal maker and checker loop. Stop when every piece is merged and the suite is green.

**End to end.** Run `factory step tests.e2e`, then walk the real user journeys. Stop when the end to end suite passes and each journey has been walked.

**Evals.** Only for tier R. Run each metric as `factory step evals.<metric id>`. A metric that misses its target or prints no number fails loudly. Never tune on the held-out set. Stop when every metric meets its target.

**GATE B.** One review of the full diff comes from a different vendor than the maker, before GATE B. Run `factory check`. Then `factory gate open` for release approval.

**Release.** Only after GATE B is answered yes. Run `factory step release.preflight.<name>`, then `release.steps.<name>`, then `release.smoke.<name>`, each with its own time limit. Stop when smoke passes, or at the first failure: report it, do not retry blindly.

**Retro.** `factory trace-report` and `factory report-card`. Read the computed report, not the raw log. Propose at most 3 process changes. The owner switches them on.

## 4. Logging

Every agent call has a unique call id before it is sent: `<piece>.<role>.<try>`, for example `N1.maker.2`.

1. Add it: `factory check --add N1.maker.2 --node N1 --role maker --try 2`.
2. Save the exact prompt to a file.
3. For a program you launch (`codex exec`, `claude -p`, `opencode run`, `cursor-agent -p`), wrap it:

```
factory run --actor maker --call N1.maker.2 --node N1 --iteration 2 --runner claude --model opus-5-5 --label "Login form" --input prompt.md -- <program> [args]
```

`--runner` names the program family (for example `claude`, `codex`, `opencode`) and decides the data rule. `--label` is the plain piece name the owner sees on the board; without it the board says `Piece name not recorded`.

Use `--input-as-arg` when the program wants the prompt as its last argument. A prompt typed only on the command line is refused: it must be in a file.

4. For an in-session sub-agent (not a process you launch), log it with two short commands: `factory log start --kind agent_call --actor checker --call N1.checker.2 --node N1 --iteration 2 --runner claude --model fable-5-2 --label "Login form" --input prompt.md`, then `factory log end <span_id> --output reply.md`. Name every sub-agent `<piece> <role> try <n>` so the board and the check line up.

Project commands run through `factory step tests.fast`, `factory step evals.<metric id>` and `factory step release.steps.<name>`, never typed from memory. Check status any time with `factory status` (`--all` lists every build).

If you missed a call, record it later with `factory log event --kind agent_call --actor maker --call N1.maker.3 --input prompt.md --notes "added late"`. A call nobody planned is acknowledged with `factory check --add`. Log lines are never edited.

## 5. Waiting and asking

Whenever any agent is running, a `factory wait` timer runs in the background (default 480 seconds, `--timeout S` to change). It exits when something changes, and on timeout it prints who is running and how long they have been quiet. Never sit idle without a timer.

Gate questions go through `factory gate open`:

```
factory gate open --name "GATE A" --question "Should the new flag be on by default?" --recommend "No, keep it off." [--file QUESTIONS.md]
```

A plain question, a suggested answer, one sentence why. No ids, no section numbers, no jargon. At most 5 questions per gate. The command refuses a question longer than 300 characters or one that contains ids like `AC3` or `T-KIT-01`.

Notifications go only through configured channels (`notify.channels`). If `gate open` prints `Also send this through: <name>`, send it through that connector yourself, then record it with `factory gate sent <span_id> --channel connector`. Use a connector only when that line is printed. Inside the Conductor app the question may also go through its question tool. Neither that nor a connector is ever the only path: always run `factory gate open`. Never pick a chat, mail or scheduling connector on your own. Notify for decisions only: gates, a MUST criterion at risk, a breaker escalation, a constitution amendment. Routine progress never notifies.

## 6. Hard rules

- Log through `factory run` or `factory log`. Never write JSON log lines by hand.
- Whenever any agent is running, a `factory wait` timer is running.
- Every external step has a time limit. There is no "no limit".
- Gate questions go through `factory gate open`: plain question, suggested answer, no ids, at most 5.
- Only notify through configured channels.
- Every agent dispatch gets a call id, added with `factory check --add` before it is sent, passed as `--call`, with its prompt in a file passed as `--input`.
- `factory check` runs before each gate and before the report card. Fix each finding with a late `factory log event`, or explain it to the owner.
- A runner that may keep what it is sent (free tiers) only ever gets non-private material. Pass `--non-private`; the input must also be under a public folder or pass the kit's privacy scan. Non-private means: already public, synthetic fixtures, or prompts that hold none of the project's private code, logs, messages or settings. When in doubt, it is private.
- Project commands run through `factory step <name>`.
- Maker and checker are never the same session. One review before GATE B comes from a different vendor than the maker.
- Raw log lines never go into a model prompt. Read the computed `factory trace-report` or `factory report-card` output instead.
- Any script whose output feeds a published number is committed, tested, and fails loudly on empty input.
- Never delete or overwrite an existing file. Outputs are new files.
- Nothing is pushed, published or merged before GATE B.
- The kit never changes Claude Code configuration files.

## 7. With and without Conductor

The kit works without the Conductor app, in plain Claude Code. Claude roles run as sub-agents of the session, other vendors run through `factory run -- <their CLI>`, and the board is `factory status`. With Conductor (its tools are present), each role can also be a named visible session, and the board can be published there. Nothing else changes.

## 8. Roles and models

Roles and models come from `factory.json` (project) over the machine file over built-in defaults. If a model fails mid-build, switch to its configured fallback and log the swap with `factory log event`. Models that may keep data are skipped for private material.

## 9. Quick reference

```
factory preflight        start of day
factory new <id>         start a build
factory phase <name>     change phase
factory check            find gaps in the log
factory status           the board
factory trace-report     bottlenecks, computed
factory report-card      one-page summary
```
