# Factory

A build process for coding agents, as a Claude Code skill plus a small set of command line tools. You hand it a goal. It plans, has the plan reviewed, writes the tests first, builds piece by piece with a maker and a separate checker, and stops at two gates where only you decide. Two words you will see often: **spec-first** means the written plan (what to build and how to tell it is done) comes before any code, so a login form starts as "a user can sign in with an email and password", not as code. **Multi-agent** means several separate AI agent sessions each do one job (plan, build, check) instead of one session doing everything. Everything it does goes into one log, and a script turns that log into a report card.

Version 0.1.0.

## What it does

- Runs one process on any project: intake, plan, plan review, approval gate, tests first, build loop, integration, end to end checks, release approval gate, release, retro.
- Keeps maker and checker apart, and asks a different vendor to review the plan and the final diff.
- Logs every agent call and command to an append-only log (new lines are only ever added at the end, old lines are never edited, like a ship's log). Logging is done by the tools, not typed by hand.
- Catches gaps: a check compares the calls that were planned with the calls that were logged.
- Asks plain questions at the gates, and notifies you only through channels you configured.
- Computes bottlenecks and a short report card from the log, with no model call.

Project specifics (tests, eval metrics, release steps, optional rules file) live in a settings file, not in the kit.

## Commands

`init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `preflight`, `trace-report`, `report-card`, `plain` and `eval` (`eval run`, `eval show`, `eval diagnose`, `eval improve`).

`log end`, `log event`, `run` and `step` take `--plain` (a one to three sentence summary in plain words), `--stop-reason` (`on_purpose`, `usage_limit`, `stuck`, `error`), and `--next-step`; `run` also takes `--plain-file` and `--group`. `factory plain` writes summaries for steps that have none (`--dry-run`, `--limit`, `--timeout`, `--fallback-only`). `factory new --from-graph` writes `plan.json` from the graph's `stages:` block, and `--stop-plain "GATE B=Release decision"` names a deadline in plain words. `gate open --node <piece>` ties a question to a piece.

## Evals

An eval is a small quiz for your program: a list of inputs with the answer you expect, and a score for how many it got right. Evals are optional and only matter when the build changes what a program picks, ranks or says.

**1. The example file.** An eval set is a JSONL file ("JSON Lines": a plain text file with one JSON object per line, no commas between lines). Each line is one example, for instance `{"id": "e1", "input": "hello", "expected": "HELLO", "tags": ["greeting"]}`. `id` and tags use letters, digits, dot, dash and underscore. `input` and `expected` can be any JSON value.

**2. The settings.** Declare the set in the project's `factory.json` under `evals.sets`:

- `id`: the name you type in `factory eval run <id>`.
- `file`: the example file, relative to the project folder.
- `cmd`: the command that reads one input on stdin and prints one answer.
- `example_timeout_s`: seconds each example may take (a number you choose).
- `scorer`: how an answer is marked, always an object with a `type`: `{"type": "exact"}` (answer must equal the expected text), `number`, `contains` (expected text appears in the answer) or `json_field`.
- `targets`: the scores you want, written like `">=0.9"`. `accuracy` is the share of examples right. `p95_s` is a percentile timing: sort all example times from fastest to slowest and take the one 95% of the way up, so `"<=2"` means 19 of 20 examples finished within 2 seconds. `cost_per_example` is the average cost.

**3. A complete example that works.** Save the lines below as `evals.jsonl` in your project folder:

```
{"id": "e1", "input": "hello", "expected": "HELLO", "tags": ["greeting"]}
{"id": "e2", "input": "world", "expected": "WORLD", "tags": ["greeting"]}
```

Then in `factory.json`, replace `"evals": {"metrics": [], "sets": []}` with:

```
"evals": {"metrics": [], "sets": [
  {"id": "upper", "file": "evals.jsonl", "cmd": "tr a-z A-Z",
   "example_timeout_s": 10, "scorer": {"type": "exact"},
   "targets": {"accuracy": ">=0.9"}}
]}
```

Start a build with `factory new demo --title Demo`, then run `factory eval run upper`. It prints `2 of 2 passed, accuracy 1.0000 (target >=0.9 met)`. (`tr a-z A-Z` is a standard Unix program that upper-cases its input, so no model is needed to try this.)

**Other settings.** A program can print `factory-cost: 0.01` on stderr to report what an example cost; `evals.cost_unit` (default `USD`) only changes how it is printed. `evals.improve` (`max_rounds`, `max_minutes`, `stall_rounds`) bounds the optional improve loop, which asks an agent to try fixes when a target is missed. The limits are yours to set; the kit does not pick a number for you. `factory eval run <set id>` scores every example, writes new files under the build's `evals/` folder, and shows up on the report card and in `factory status`. A missed target is information for the owner, not a release block by itself. `templates/EVALSET.jsonl` is a one-line example file.

**Held-out set.** If you tune a program against an eval set, keep a second set aside that you never look at while tuning, and score on it only at the end. That second set is the held-out set. It tells you whether the program really got better or just learned the first set (like a student who memorized last year's exam).

## Install

Requirements: Python 3.9 or newer, standard library only. Git. The agent CLIs the default settings require: `claude`, `codex` and `opencode` (`ollama` and `cursor` are optional). If one is missing, preflight reports `Not ready`. Change `vendors` and `roles` in `factory.json` to fit what you have.

1. Copy this folder to `~/.claude/skills/factory` (or link it there).
2. In a project folder, run `python3 ~/.claude/skills/factory/scripts/factory.py init`. This writes `factory.json`.
3. Optional, once per machine: copy `machine.example.json` to `~/.factory/config.json` for private settings (notification command, runner locations). Set `FACTORY_HOME` to use a different folder.
4. Start of day: `python3 ~/.claude/skills/factory/scripts/factory.py preflight`.
5. In Claude Code, run `/factory` and describe what you want built.

The tools never change Claude Code configuration files.

## How a run goes

1. `factory preflight` checks settings, the log folder, every model your roles use, the vendors, that the machine stays awake and that notifications reach you.
2. `factory new <build-id> --title "..."` starts a build and its log.
3. The orchestrator writes the plan from `templates/`, a reviewer from another vendor checks it, and you answer a short list of plain questions at GATE A.
4. A test writer writes failing tests. They are locked. Makers cannot change them.
5. Each piece is built by a maker and judged by a checker, in a loop, with breakers (automatic stops that fire when a piece is stuck, for example the same check failing twice).
6. Integration, end to end checks and (for projects that need them) evals run through `factory step`.
7. You approve the release candidate at GATE B. Nothing is pushed, published or merged before then.
8. `factory trace-report` and `factory report-card` show where the time went. `factory status` shows the board at any moment.

Commands: `init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `preflight`, `trace-report`, `report-card`. Run any of them with `--help`.

Numbers in this kit (3 plan review rounds, 5 questions per gate, a 480 second wait, summary lengths) are the author's choices, not rules of nature. Most are settings you can change in `factory.json`.

## Files

- `SKILL.md`: the `/factory` command text.
- `PROCESS.md`: the process in detail.
- `factory.example.json`: the project settings file.
- `machine.example.json`: the private machine settings file.
- `templates/`: plan and packet templates.
- `scripts/`: the tools. `tests/`: their tests, using synthetic data only.

## Known limits

1. An in-session sub-agent beyond the first tries seeded from the plan is on record only if the orchestrator logs it. The check cannot know an agent existed if both the log call and the add call were forgotten.
2. Built and proven on one machine, running macOS.
3. The sleep check and the desktop notification are macOS only. On other systems they report `not checked` or count as not delivered.
4. Preflight cannot read remaining credit. It sends a real one-line request and reports whether the model answered.
5. In-session sub-agents are logged by two short commands, not by a hook. `factory check` is what catches a missed one.
6. No dashboard is included. The board is `factory status`.
7. Only secret-looking values (API keys, tokens, passwords) in a wrapped program's output are replaced before anything is shown or saved. Other personal data, such as an email address, is kept as the program printed it, in the saved output and in `factory status`. Do not wrap programs whose output holds personal data you would not want stored.
   A related limit: a single line longer than 1 MB with no line break is not saved at all: it is replaced by a short note saying how big it was, because it cannot be checked safely while it streams.
8. Evals run one example at a time and are scored by a fixed formula only; no model does the scoring. The improve loop is small: it changes project code only, one change per round, and keeps a change only if the tests and evals still pass. Improve-loop privacy limit: the kit never hands example text to the research agent, but that agent has file tools and may search the web, and keeping it out of your eval files is an instruction in its prompt that the kit cannot enforce. If your eval inputs must never leave this machine, do not run the improve loop.

## Tests

Run from the kit folder: `PYTHONPYCACHEPREFIX=/tmp/factory-test-cache python3 -m unittest discover -s tests -t .` (the setting keeps Python's compiled files in one temporary folder, so the many small test programs do not each recompile the kit; without it the run takes about twice as long and one timing test can fail; with it the run took about 40 seconds on the author's Mac; the tests use synthetic fixtures and fake agent programs, and never call a model or the network).
