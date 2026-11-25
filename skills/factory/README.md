# Factory

A build process for coding agents, as a Claude Code skill plus a small set of command line tools. You hand it a goal. It plans, has the plan reviewed, writes the tests first, builds piece by piece with a maker and a separate checker, and stops at two gates where only you decide. Everything it does goes into one log, and a script turns that log into a report card.

Version 0.1.0.

## What it does

- Runs one process on any project: intake, plan, plan review, approval gate, tests first, build loop, integration, end to end checks, release approval gate, release, retro.
- Keeps maker and checker apart, and asks a different vendor to review the plan and the final diff.
- Logs every agent call and command to an append-only log. Logging is done by the tools, not typed by hand.
- Catches gaps: a check compares the calls that were planned with the calls that were logged.
- Asks plain questions at the gates, and notifies you only through channels you configured.
- Computes bottlenecks and a short report card from the log, with no model call.

Project specifics (tests, eval metrics, release steps, optional rules file) live in a settings file, not in the kit.

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
5. Each piece is built by a maker and judged by a checker, in a loop, with breakers for stuck pieces.
6. Integration, end to end checks and (for projects that need them) evals run through `factory step`.
7. You approve the release candidate at GATE B. Nothing is pushed, published or merged before then.
8. `factory trace-report` and `factory report-card` show where the time went. `factory status` shows the board at any moment.

Commands: `init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `preflight`, `trace-report`, `report-card`. Run any of them with `--help`.

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
7. Secrets in a wrapped program's output are replaced as the output streams. A few rare shapes can still slip through: a secret placed right after a very long run of other secret-shaped text (tens of kilobytes on one line with no spaces). Normal program output is not affected. A simpler line-based design is planned for the next version.

## Tests

Run from the kit folder: `python3 -m unittest discover -s tests -t .` (the tests use synthetic fixtures and fake agent programs, and never call a model or the network).
