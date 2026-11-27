# Factory

A build process for coding agents, as a Claude Code skill plus a small set of command line tools. You hand it a goal. It plans, has the plan reviewed, writes the tests first, builds piece by piece with a maker and a separate checker, and stops at two gates where only you decide. Two words you will see often: **spec-first** means the written plan (what to build and how to tell it is done) comes before any code, so a login form starts as "a user can sign in with an email and password", not as code. **Multi-agent** means several separate AI agent sessions each do one job (plan, build, check) instead of one session doing everything. Everything it does goes into one log, and a script turns that log into a report card.

Version 0.1.0.

## What it does

- Runs one process on any project: intake, plan, plan review, approval gate, tests first, build loop, integration, end to end checks, release approval gate, release, retro.
- Keeps maker and checker apart, and asks a different vendor to review the plan and the final diff. [on trust]
- Logs every agent call and command to an append-only log (new lines are only ever added at the end, old lines are never edited, like a ship's log). Logging is done by the tools, not typed by hand.
- Catches gaps: a check compares the calls that were planned with the calls that were logged. [enforced by code]
- Asks plain questions at the gates, and notifies you only through channels you configured. The gate command refuses ids and long questions. [enforced by code]
- Computes bottlenecks and a short report card from the log, with no model call.
- Shows the board in a terminal (`factory status`) or in your browser (`factory dashboard`), and closes a build with `factory finish`.

Rule labels. Every rule the docs state is marked `[enforced by code]` (a named test in this kit fails if the rule breaks) or `[on trust]` (an instruction to the agents that no code checks). The table and the list under Known limits name each one.

Project specifics (tests, eval metrics, release steps, optional rules file) live in a settings file, not in the kit.

## Commands

`init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `dashboard`, `finish`, `preflight`, `trace-report`, `report-card`, `plain` and `eval` (`eval run`, `eval show`, `eval diagnose`, `eval improve`).

`log end`, `log event`, `run` and `step` take `--plain` (a one to three sentence summary in plain words), `--stop-reason` (`on_purpose`, `usage_limit`, `stuck`, `error`), and `--next-step`; `run` also takes `--plain-file` and `--group`. `factory plain` writes summaries for steps that have none (`--dry-run`, `--limit`, `--timeout`, `--fallback-only`). `factory new --from-graph` writes `plan.json` from the graph's `stages:` block, and `--stop-plain "GATE B=Release decision"` names a deadline in plain words. `gate open --node <piece>` ties a question to a piece.

`factory finish` closes a build: `factory finish --build demo/alpha` names the build (without it, the newest one), `--leftover B2="not needed after all"` gives a reason for each call or piece you leave open on purpose (repeat it for more than one), and `--plain "..."` sets the one plain sentence shown for the close. An open question to you can never be a leftover. When something is still open and has no reason, the command prints what is open, writes nothing and exits with 1.

## Dashboard

`factory dashboard` opens the board in your browser: what needs you first, one plain sentence about where the build is, the plan as stages, and a card for every piece. Select a card to see what each attempt did. It reads the same logs as `factory status`, from the Factory home (`$FACTORY_HOME`, or `~/.factory`), and it updates by itself while agents work: every 3 seconds while a build is moving, every 10 seconds when it is quiet (both numbers are the author's picks). Leave it open next to your session.

It runs on this computer only (`127.0.0.1`), changes nothing, and cannot answer a question for you: decisions still happen in your Claude Code session. Ids, models and raw notes stay hidden until you turn on `Show technical details` in a panel. The first time you open it in a browser tab it plays a short intro (about 1.5 seconds, the author's pick); click or press any key to skip it. It does not play when your system asks for reduced motion.

Credit line. The dashboard shows a small credit line, `factory · by Nayan Kanaparthi`, in the bottom left corner of every view. It links to the project repo. The intro also says `by Nayan Kanaparthi`. This is there by the author's choice, and it is the only personal detail the dashboard shows.

Flags: `factory dashboard --port 7878` picks the first port to try (7878 is the default, the author's pick; if it is taken, the next free one is used and the command says which), `factory dashboard --no-open` prints the address without opening a browser, `factory dashboard --build demo/alpha` opens on one build. Stop it with Ctrl-C. The dashboard is read-only and local. [enforced by code]

What stays out, on purpose: answering a question or approving a gate from the page, reaching it from another computer (no sign-in, no sharing link), instant push updates (it asks for changes every few seconds), charts, search, filters, history across builds, settings, running it as a background service, and any model call, network call or tracking.

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

Requirements: Python 3.9 or newer, standard library only. Git. The agent CLIs the default settings require: `claude`, `codex` and `opencode` (`ollama` and `cursor` are optional). See "Set up your models" below if you have only one of them. If one is missing, preflight reports `Not ready`. Change `vendors` and `roles` in `factory.json` to fit what you have.

1. Copy this folder to `~/.claude/skills/factory` (or link it there).
2. In a project folder, run `python3 ~/.claude/skills/factory/scripts/factory.py init`. This writes `factory.json`.
3. Optional, once per machine: copy `machine.example.json` to `~/.factory/config.json` for private settings (notification command, runner locations). Set `FACTORY_HOME` to use a different folder.
4. Start of day: `python3 ~/.claude/skills/factory/scripts/factory.py preflight`.
5. In Claude Code, run `/factory` and describe what you want built.

The tools never change Claude Code configuration files.

## Set up your models

You do not need every tool. You need one main tool where the builder runs, and it works best when a second source from another company does the checking. Terms: a **model** is the AI program an agent runs on. A **runner** is the command line program that starts a model (`claude`, `codex`, `opencode`, `ollama`). A **free model** is one that its provider offers at no charge; check the provider's own terms, because it may keep what you send. This guide has not tested any model. Every model name below is either a placeholder you replace or an example you check first. A **local model** runs on your own computer through a program such as Ollama.

Use outside models as text only: hand them a file to read and ask for an answer in words. Do not let them edit files or run commands in your project.

### 1. Sign in to one main tool

Pick one tool you already have and follow its own sign-in steps. For Codex, `codex login` is the command to try; for Claude Code, start `claude` and follow what it asks. Check with the tool's own help if a step differs on your version. One is enough to start. With both, one builds and the other checks.

### 2. Add free models with OpenCode (no key)

OpenCode is a program that reaches many models through one command. Install it by following its own install page; this kit does not install tools for you. Then run `opencode models` to see the list of models your install offers. Whether a model on that list is free, needs a key or needs sign-in is for you to read from your own list and the provider's terms.

Try one in an empty folder, because `opencode run` starts an agent that may use tools: `opencode run -m <model from your list> "Say ok"`. Replace `<model from your list>` with a name copied from the output of `opencode models`. If it answers, use it; if it does not, pick another. Do the same for a model for quick decisions, and ask it non-private questions only.

A free model's provider may keep what you send. So the kit refuses to send them private material unless the call is marked `--non-private` and the input passes the kit's scan. [enforced by code]

### 3. Optional: an OpenRouter key

OpenRouter is a separate service that has its own terms and pricing; read them first. If you already have a key, `opencode auth login` is the command to try. Follow what it asks and see which models then show in `opencode models`. The kit has no separate OpenRouter setting; it reaches any such model through OpenCode.

### 4. Optional: local models with Ollama

Ollama runs models on your computer. Install it from its own site. Run `ollama list` to see what you already have, or pick a model on Ollama's site and check its size before you pull it. As an example only, `ollama pull qwen3:14b` fetches the model the author uses; model downloads can be many gigabytes, so check the size first. Use your own pick if you prefer. A model that runs on your computer does not send your text to its maker while you run it; confirm that for your own setup before you rely on it for private material.

### 5. Tell the kit what you have

Edit `vendors` and `roles` in `factory.json`, then run `factory preflight`. `vendors.required` lists the programs that must be installed. `roles` says which model does which job. Each block below names only the keys it changes; paste it over the same keys in your `factory.json`. Every `model` value in the blocks is a placeholder in capitals: replace each one with a name from your own tool's model list (for example the output of `opencode models`), then run `factory preflight`, which sends a real one-line request to each model and shows whether it answered. The blocks are not ready to run until you have done that. They do load and pass the kit's settings check, which looks at the shape of the settings and the company behind each model, not at whether a model exists or answers. The check refuses an outside role that names the maker's company. [enforced by code]

**Only Claude Code** (Claude does the planning, building and checking; a model from your OpenCode list and a local model are the outside checks):

```json
{
  "vendors": {"required": ["claude", "opencode"], "optional": ["ollama", "cursor"]},
  "roles": {
    "planner": {"runner": "claude", "model": "PICK-A-CLAUDE-MODEL-FROM-YOUR-LIST", "effort": "medium"},
    "maker": {"runner": "claude", "model": "PICK-A-CLAUDE-MODEL-FROM-YOUR-LIST"},
    "checker": {"runner": "claude", "model": "PICK-A-CLAUDE-MODEL-FROM-YOUR-LIST"},
    "plan-reviewer": {"runner": "opencode", "model": "opencode/PICK-A-MODEL-FROM-OPENCODE-MODELS", "effort": "high",
                      "fallback": [{"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST"}]},
    "test-writer": {"runner": "opencode", "model": "opencode/PICK-A-MODEL-FROM-OPENCODE-MODELS",
                    "fallback": [{"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST"}]},
    "final-reviewer": {"runner": "opencode", "model": "opencode/PICK-A-MODEL-FROM-OPENCODE-MODELS",
                       "fallback": [{"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST"}]}
  }
}
```

**Only Codex** (Codex does the planning, building and checking; a model from your OpenCode list and a local model are the outside checks):

```json
{
  "vendors": {"required": ["codex", "opencode"], "optional": ["ollama", "cursor"]},
  "roles": {
    "planner": {"runner": "codex", "model": "PICK-A-CODEX-MODEL-FROM-YOUR-LIST", "effort": "medium"},
    "maker": {"runner": "codex", "model": "PICK-A-CODEX-MODEL-FROM-YOUR-LIST"},
    "checker": {"runner": "codex", "model": "PICK-A-CODEX-MODEL-FROM-YOUR-LIST"},
    "plan-reviewer": {"runner": "opencode", "model": "opencode/PICK-A-MODEL-FROM-OPENCODE-MODELS", "effort": "high",
                      "fallback": [{"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST"}]},
    "test-writer": {"runner": "opencode", "model": "opencode/PICK-A-MODEL-FROM-OPENCODE-MODELS",
                    "fallback": [{"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST"}]},
    "final-reviewer": {"runner": "opencode", "model": "opencode/PICK-A-MODEL-FROM-OPENCODE-MODELS",
                       "fallback": [{"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST"}]},
    "summaries": {"runner": "ollama", "model": "PICK-A-LOCAL-MODEL-FROM-OLLAMA-LIST", "fallback": []}
  }
}
```

A warning that matters: with a single paid company, the outside check of private code can only come from a local model, because a free model's provider may keep what it is sent. The kit refuses to send private material to the free model, so for private work move the `ollama` entry to the first place in those three roles.

### Who does what

| Job | Use | Effort | If it is not available | Does the kit enforce it today? |
|---|---|---|---|---|
| Planning | The strongest model you have | medium | The next strongest. Ask the owner before going lower. | On trust |
| Building | A solid coding model from your main tool | the tool's default | The same company's stronger model after two failed tries | On trust |
| Checking by another company | A model from a different company than the builder | high | The next outside company: an OpenCode free model, then a local model. Never the builder's company. When none is left, stop and ask the owner. | The settings check refuses a same-company fallback (enforced by code). Which model really runs: on trust |
| Quick decisions | A free model from the `opencode models` list, non-private questions only | default | Your checking model | On trust |
| Routine work: summaries, formatting | A free or local model | low | The kit's built-in plain wording (`factory plain --fallback-only`) | `factory plain` reads the `summaries` role from settings (enforced by code). Everything else: on trust |

Today the kit checks your settings and tests that each model answers. It does not choose the model when an agent starts: the session that starts the agent types it. So the split above is on trust until the model picker ships.

## How a run goes

1. `factory preflight` checks settings, the log folder, every model your roles use, the vendors, that the machine stays awake and that notifications reach you.
2. `factory new <build-id> --title "..."` starts a build and its log.
3. The orchestrator writes the plan from `templates/`, a reviewer from another vendor checks it, and you answer a short list of plain questions at GATE A. [on trust]
4. A test writer writes failing tests. Their hashes are recorded in `TESTLOCK`. Makers cannot change them. [on trust]
5. Each piece is built by a maker and judged by a checker, in a loop, with breakers (automatic stops that fire when a piece is stuck, for example the same check failing twice). [on trust]
6. Integration, end to end checks and (for projects that need them) evals run through `factory step`.
7. You approve the release candidate at GATE B. Nothing is pushed, published or merged before then. [on trust]
8. `factory trace-report` and `factory report-card` show where the time went. `factory status` shows the board at any moment.
9. `factory finish` marks the build finished. It refuses while a call or a piece is still open, unless you give a reason for each one. Until then the board never says "Finished". [enforced by code]

Commands: `init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `dashboard`, `finish`, `preflight`, `trace-report`, `report-card`. Run any of them with `--help`.

Numbers in this kit (3 plan review rounds, 5 questions per gate, a 480 second wait, summary lengths) are the author's choices, not rules of nature. Most are settings you can change in `factory.json`.

## Files

- `SKILL.md`: the `/factory` command text.
- `PROCESS.md`: the process in detail.
- `factory.example.json`: the project settings file.
- `machine.example.json`: the private machine settings file.
- `templates/`: plan and packet templates.
- `dashboard/`: the local dashboard behind `factory dashboard`: a small server and one web page, no dependencies.
- `scripts/`: the tools. `tests/`: their tests, using synthetic data only.

## Known limits

1. An in-session sub-agent beyond the first tries seeded from the plan is on record only if the orchestrator logs it. The check cannot know an agent existed if both the log call and the add call were forgotten.
2. Built and proven on one machine, running macOS.
3. The sleep check and the desktop notification are macOS only. On other systems they report `not checked` or count as not delivered.
4. Preflight cannot read remaining credit. It sends a real one-line request and reports whether the model answered.
5. In-session sub-agents are logged by two short commands, not by a hook. `factory check` is what catches a missed one.
6. The dashboard is read-only and local. It cannot answer decisions, it cannot be reached from another computer, and it checks for changes every few seconds rather than instantly. `factory status` shows the same board in a terminal.
7. Only secret-looking values (API keys, tokens, passwords) in a wrapped program's output are replaced before anything is shown or saved. Other personal data, such as an email address, is kept as the program printed it, in the saved output and in `factory status`. Do not wrap programs whose output holds personal data you would not want stored.
   A related limit: a single line longer than 1 MB with no line break is not saved at all: it is replaced by a short note saying how big it was, because it cannot be checked safely while it streams.
8. Evals run one example at a time and are scored by a fixed formula only; no model does the scoring. The improve loop is small: it changes project code only, one change per round, and keeps a change only if the tests and evals still pass. Improve-loop privacy limit: the kit never hands example text to the research agent, but that agent has file tools and may search the web, and keeping it out of your eval files is an instruction in its prompt that the kit cannot enforce. If your eval inputs must never leave this machine, do not run the improve loop.

### Rules the code enforces

Each row is a rule marked `[enforced by code]` in these docs. The second column is the name of a test in `tests/` that passes today and would fail if the rule broke.

| Rule | Test that proves it |
|---|---|
| An outside role (plan reviewer, test writer, stuck diagnosis, final reviewer) cannot name a model from the maker's company, in its own settings or in its fallback list. | `test_T_TN_14_outside_roles_cannot_fall_back_to_maker_company` |
| `factory finish` refuses while a question, a call or a piece is still open, and writes nothing when it refuses. | `test_T_TN_08_finish_refuses_questions_calls_and_pieces_atomically` |
| A build is shown as "Finished" only after `factory finish`, never because all pieces are done. | `test_T_TN_05_all_done_is_not_finished_without_marker` |
| A model that may keep what it is sent gets a call only when it is marked `--non-private` and the input is public or passes the scan. | `test_run_data_retention_rule` |
| A prompt typed only on the command line is refused: an agent call needs `--call` and an `--input` file. | `test_run_rejects_uncaptured_agent_but_supports_commands_and_missing_program` |
| A gate question that holds ids, is empty or is longer than 300 characters is refused, and nothing is logged. | `test_gate_rejects_ids_empty_missing_long_and_id_recommendation` |
| `factory check` reports calls that were planned and never logged, duplicates and unplanned calls. | `test_check_missing_duplicate_unplanned_and_late_fixes` |
| The dashboard answers only GET and HEAD, so it cannot change anything. | `test_T_DB_13_all_write_methods_are_read_only` |
| The dashboard refuses a request whose `Host` is not this computer's own address. | `test_T_DB_14_host_header_is_exact` |
| `factory plain` needs the `summaries` role from your settings and refuses without it. | `test_T_PG_25_to_32_plain_rewriter_is_append_only_bounded_and_idempotent` |

### Rules on trust

These rules are instructions to the agents. No code stops an agent that breaks them, and nothing checks afterwards unless you read the log. Each one is marked `[on trust]` where the docs state it.

1. A model from a different company than the maker reviews the plan, writes the tests, diagnoses stuck pieces and reviews the final change. The settings check refuses a same-company fallback, but the kit does not pick or verify the model that really ran.
2. Maker and checker are never the same session.
3. Makers cannot change locked tests. `TESTLOCK` is a record, not a lock.
4. Nothing is pushed, published or merged before GATE B.
5. Breakers fire when a piece is stuck. They are computed by the orchestrator, not by the kit.
6. A maker gets a small packet and never the whole plan.
7. A wait timer runs whenever an agent runs.
8. Raw log lines never go into a model prompt.
9. Nothing that existed before the build is deleted or overwritten.
10. `factory check` runs before each gate, and project commands run only through `factory step`.
11. The model each role uses is the one in your settings. The command that starts an agent takes whatever model is typed.
12. `factory finish` is run at the end. Until it is, the board says the build is not closed.

## Tests

Python tests. Run from the kit folder: `PYTHONPYCACHEPREFIX=/tmp/factory-test-cache python3 -m unittest discover -s tests -t .` (the setting keeps Python's compiled files in one temporary folder, so the many small test programs do not each recompile the kit; without it the run takes about twice as long and one timing test can fail; with it the run took about 40 seconds on the author's Mac). This one command runs the Python tests only. The tests use synthetic fixtures and fake agent programs. They never call a real model and never use the internet; the dashboard tests start a small server on this computer only (`127.0.0.1`), so they need a machine that allows that.

Browser checks. The checks that open the dashboard in a real browser are a separate, optional runner that is not part of the command above. See `tests/browser/README.md` for how to run it.
