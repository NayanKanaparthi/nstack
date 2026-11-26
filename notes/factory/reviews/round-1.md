# Factory public skill review, round 1

Review scope: `CONTRIBUTING.md`, `notes/factory/CHECKLIST.md`, and `skills/factory/`. I did not use network access, send a notification, or call a model. Every Factory command used fresh temporary `HOME` and `FACTORY_HOME` folders and `FACTORY_OSASCRIPT_BIN=/usr/bin/true`.

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | `find skills/factory -mindepth 1 -maxdepth 1` listed only the skill's files and folders under `skills/factory/`: `PROCESS.md`, `README.md`, `SKILL.md`, examples, scripts, templates, and tests. |
| 2 | PASS | `skills/factory/SKILL.md:1-4` exists and has front matter. |
| 3 | PASS | `skills/factory/SKILL.md:3` is `name: factory`, matching the folder. |
| 4 | PASS | `skills/factory/SKILL.md:2` contains a description. |
| 5 | PASS | Command: `description=$(sed -n '2s/^description: //p' SKILL.md); printf '%s\n' "${#description}"`. Output: `310`, below 1024. |
| 6 | PASS | `skills/factory/SKILL.md:2` says to use it when the owner says "factory", asks to run the build process, or hands over a goal for an agent build. |
| 7 | PASS | `skills/factory/README.md` exists. |
| 8 | PASS | `skills/factory/README.md:7-16` says what the skill does. |
| 9 | PASS | `skills/factory/README.md:32-42` gives requirements and five install/start steps. |
| 10 | PASS | `skills/factory/README.md:44-55` describes a run from preflight through the report card. |
| 11 | PASS | `skills/factory/README.md:66-75` is a known limits section. |
| 12 | PASS | `skills/factory/README.md:5` states version 0.1.0, which matches `skills/factory/scripts/factorylib.py:26`. |
| 13 | FAIL | The shipped tests require a file that is not in the skill. Test output: `AssertionError: False is not true : planned privacy scanner missing`. The reference is at `skills/factory/tests/test_plain.py:491-500`. |
| 14 | FAIL | The code reads arbitrary paths, not only the kit, project, or Factory home: `skills/factory/scripts/factory.py:202-207` reads any `--from-graph` path and `skills/factory/scripts/factory.py:126-135` reads any input path. Dynamic proof from a project folder: `factory new external-read --from-graph /tmp/.../outside-GRAPH.yaml` exited 0 and its `plan.json` contained `"id": "OUT"`. |
| 15 | PASS | Command: a Python scan for `chr(0x2014)` across `skills/factory` and `notes/factory`. Output: `em_dash_matches=0`. |
| 16 | FAIL | The listed hype-word scan found no skill prose match, but the plain-words part fails. `skills/factory/README.md:30` puts `JSONL`, `example_timeout_s`, `p95_s`, `cost_per_example`, scorer names, and improve-loop settings into one paragraph before giving plain explanations for several terms. |
| 17 | FAIL | Terms needing explanation are not explained at first use. Examples: `spec-first` and `multi-agent` at `skills/factory/SKILL.md:2`, `append-only` at `skills/factory/README.md:11`, and `p95_s` at `skills/factory/README.md:30`. |
| 18 | FAIL | Picked limits are presented as rules without being marked as the author's choices or tied to a source. Examples include 3 review rounds at `skills/factory/SKILL.md:43`, 1 to 3 sentences and 40/160 character limits at `skills/factory/SKILL.md:98-102`, a 480 second wait at `skills/factory/SKILL.md:106`, and 5 questions/300 characters at `skills/factory/SKILL.md:114`. |
| 19 | FAIL | Claims about the world lack a source. `skills/factory/PROCESS.md:115` says a plan that has not converged after 3 rounds "almost always" needs an owner decision, and `skills/factory/PROCESS.md:158` calls delayed gate questions the most common way a build loses time. Neither names evidence. |
| 20 | PASS | Command: `rg -ni '\b(consulting|consultant|hire me|paid work|our services?|contact me)\b' skills/factory notes/factory`. Output only matched the checklist's own question about services; no skill text offers a service. |
| 21 | PASS | Searches for likely person and organization names found only synthetic test labels and public model-vendor probes, such as `Eval Test` in `skills/factory/tests/test_evals.py:150-151` and rejection probes in `skills/factory/tests/fixtures/page/plain_probes.json:427-430`. No private person, client, employer, or private company name was found. |
| 22 | PASS | Commands searching for `/Users/<value>`, `/home/<value>`, and email-shaped values found no personal data. Secret-looking test values are built from synthetic repeated characters at `skills/factory/tests/test_factorylib.py:175-176`; no real token, key, or account detail was found. |
| 23 | PASS | `skills/factory/README.md:79` identifies synthetic fixtures. The tests create fake programs and temporary settings, for example `skills/factory/tests/common.py:35-49` and `skills/factory/tests/test_preflight.py:58-64`; no real log or message fixture was found. |
| 24 | FAIL | The required scanner is absent, as the failing test at `skills/factory/tests/test_plain.py:491-500` shows. Also, `git rev-parse --verify origin/main` output `fatal: Needed a single revision`, so `--git-changed origin/main` cannot run in this review copy. |
| 25 | PASS | Command: `/usr/bin/python3 -m py_compile $(rg --files -g '*.py' | sort)`. Output: `py_compile_exit=0`. `/usr/bin/python3 --version` output `Python 3.9.6`. |
| 26 | PASS | The import scan showed only Python standard-library modules plus the skill's own `factorylib` and test helpers. Representative source imports are at `skills/factory/scripts/factory.py:14-27`, `skills/factory/scripts/agents.py:17-34`, and `skills/factory/scripts/evals.py:19-33`. |
| 27 | PASS | `skills/factory/README.md:34` says Python 3.9 or newer, standard library only, Git, required agent command line tools, and optional tools. |
| 28 | PASS | Static scan for `.claude`, settings files, and write calls found no script write to Claude Code configuration. The contract test at `skills/factory/tests/test_core_commands.py:68-105` also checks that behavior. |
| 29 | PASS | Command: `grep -rn 'unlink\|rmtree\|os.remove' skills/factory/scripts`. Output: no matches. Creation uses exclusive mode, for example `skills/factory/scripts/factory.py:177-178` and `skills/factory/scripts/agents.py:408-415`. |
| 30 | PASS | `/usr/bin/python3 scripts/factory.py --help </dev/null` exited 0 and began `factory 0.1.0: the factory kit`. |
| 31 | PASS | The same root help listed all 13 names in this line: `init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `preflight`, `trace-report`, and `report-card`. |
| 32 | PASS | Root help also listed the README additions `plain` and `eval`; `skills/factory/README.md:20` lists the same top-level commands. |
| 33 | FAIL | Top-level command help exited 0, but documented eval subcommands do not. Command: `factory eval run --help </dev/null`. Output: `factory: usage: ...`; exit 2. `eval show --help` and `eval diagnose --help` also exited 2. |
| 34 | PASS | I extracted every `--flag` in `SKILL.md`, combined the relevant top-level and nested help text, and checked each token. Output: `missing_skill_flags=0`. This includes `--build`, `--title`, `--stop`, `--adopt`, `--from-graph`, `--call`, `--input`, `--runner`, `--label`, and `--non-private`. |
| 35 | PASS | Command checking required references output `PROCESS.md present`, `factory.example.json present`, `machine.example.json present`, and `templates present`. |
| 36 | PASS | With stdin closed, `factory not-a-command </dev/null` printed `factory: unknown command 'not-a-command'...`, no traceback, and exited 2. Missing graph input printed `factory: graph file not found: absent.yaml`, no traceback, and exited 3. |
| 37 | PASS | From `skills/factory/`, `/usr/bin/python3 -m unittest discover -s tests -t .` discovered and ran 123 tests in one command. |
| 38 | FAIL | The documented clean-copy command exited 1 with 2 failures: `test_wait_timeout_nothing_running_and_no_build` took 0.114701542 seconds against a 0.1 second assertion, and `test_T_PG_61_and_62_templates_are_private_safe_plain_and_valid` reported the missing privacy scanner. |
| 39 | PASS | Tests use local fake programs for model names, for example `skills/factory/tests/fixtures/evals/spy_program.py` and `skills/factory/tests/test_preflight.py:58-64`. `skills/factory/tests/test_evals.py:1137-1145` explicitly rejects network modules and installs spies under model-runner names. No real model or network call occurred in the review run. |
| 40 | FAIL | Timed documented-suite output: `Ran 123 tests in 85.417s`, `real 85.68`. This exceeds 60 seconds. |
| 41 | PASS | `skills/factory/README.md:66-75` lists 8 known limits. |
| 42 | PASS | `skills/factory/README.md:69` says it was built and proven on one machine running macOS. |
| 43 | PASS | `skills/factory/README.md:70` says the sleep check and desktop notification are macOS only. |
| 44 | PASS | `skills/factory/README.md:71` says preflight cannot read remaining credit and sends a real one-line request. |
| 45 | PASS | `skills/factory/README.md:68,72` says in-session sub-agents are on record only when the orchestrator logs them. |
| 46 | PASS | `skills/factory/README.md:73` says there is no included dashboard and the board is `factory status`. |
| 47 | FAIL | Command: `test -e README.md`. Output from the repository root check: `README.md MISSING`; the required skills-table row cannot be reviewed. |
| 48 | FAIL | `README.md MISSING`, so there is no available factory row to check for content, timing, voice, or a service offer. |
| 49 | FAIL | Command: `test -e CHANGELOG.md`. Output: `CHANGELOG.md MISSING`; no Unreleased/Added line can be checked. |
| 50 | FAIL | Both root `README.md` and `CHANGELOG.md` are missing, and `origin/main` is missing, so an additions-only diff cannot be produced. |
| 51 | PASS | `find notes/factory -maxdepth 2 -type f` output `notes/factory/CHECKLIST.md` and `notes/factory/reviews/round-1.md`. |
| 52 | FAIL | `git branch --show-current` output `main`, but `git rev-parse --verify origin/main` failed and every `git diff ... origin/main` command reported an unknown revision. Branch ancestry and allowed diff scope cannot be verified. |
| 53 | PASS | This review was performed by the public reviewer with only the user-provided review scope. The initial file inventory contained `CONTRIBUTING.md`, `notes/factory/CHECKLIST.md`, and files below `skills/factory/`; no builder notes or build history were supplied. |
| 54 | PASS | Untried isolated cases included a dot/underscore build id and Unicode title, path traversal input, a missing graph, two invalid `log end` combinations, an outside graph path, fake secret output, a wrapped local Python program, a 2-example eval set, fallback-only summaries, and a small staged graph. Outputs included clean `factory:` errors, a redacted key, a generated `plan.json`, `Expected 4, logged 4, matched 4`, and a passing eval. |
| 55 | FAIL | This round has FAIL rows, so its last review does not pass every prior checklist line. |

## Open lines

- Line 13: Add every required runtime and test file inside `skills/factory/`. Done means the documented test command no longer reports a missing privacy scanner and no test reaches outside the skill for a required file.
- Line 14: Constrain direct file reads and writes to the kit, current project, or Factory home, or narrow the checklist promise. Done means absolute and parent-traversal paths outside those roots are refused with a plain `factory:` error and tests cover the boundary.
- Line 16: Rewrite dense technical passages in plain words. Done means a first-time reader can follow the README without decoding setting names or specialist shorthand.
- Line 17: Explain each necessary term at first use with a short example. At minimum cover spec-first, multi-agent, append-only, JSONL, scorer, percentile timing, and held-out set.
- Line 18: Mark every selected limit as the author's choice and name a source for every sourced number. Done means limits such as review rounds, wait time, question count, and character caps are labeled consistently.
- Line 19: Source, qualify as the author's observation, or remove the claims at `PROCESS.md:115` and `PROCESS.md:158`, plus any similar claims found in the final writing pass.
- Line 24: Ship the planned privacy scanner and patterns file, then run its changed-tree mode against an available `origin/main`; done is exit 0 with the exact command and output recorded.
- Line 33: Make `factory eval run --help`, `factory eval show --help`, `factory eval diagnose --help`, and the documented improve help paths exit 0 with useful command-specific help.
- Line 38: Make all 123 currently discovered tests pass from a clean isolated home. The wait test needs a non-flaky timing contract, and the privacy-scanner fixture must exist.
- Line 40: Bring the documented full suite below 60 seconds on the required Python 3.9 runtime, with timing evidence from the exact README command.
- Lines 47 and 48: Provide the repository root README with one alphabetized factory row in the existing table and voice; the row must state what it does and when to use it without offering a service.
- Lines 49 and 50: Provide the root changelog entry under Unreleased/Added and an `origin/main` diff showing the README and changelog edits only add lines.
- Line 52: Provide the `origin/main` reference and show ancestry plus `git diff --stat origin/main` limited to the four allowed path groups.
- Line 55: Repeat independent review after every open line is fixed; done means the newest round passes all 55 lines.

## Other findings

1. The README's eval settings example is wrong. `skills/factory/README.md:30` says `scorer` is a string such as `exact`, but `skills/factory/scripts/factorylib.py:1334-1338` requires an object such as `{"type": "exact"}`. Using the README form made every command fail early with `factory: factory.json: "evals.sets[0].scorer" must be an object with a "type"`. Correct the README and add a complete copyable eval-set example.

2. The isolated core workflow otherwise worked. `init` exited 0; `new odd.name_7 --title "Odd café build" --from-graph GRAPH.yaml` exited 0; `plan.json` held 2 pieces and 2 stages; `log start/end --plain`, the wrapped harmless program, `status`, `check`, `trace-report`, and `report-card` all exited 0. `factory plain --fallback-only` reported `rewrote 0, fell back on 2, left 0 for later` without calling a model.

3. After fixing only the temporary review fixture to match the actual scorer schema and stdin contract, `factory eval run tiny` and `factory eval show tiny` both reported `2 of 2 passed`, accuracy `1.0000`, targets met, and exit 0. This validates the new commands but also shows why the README schema defect is user-visible.

4. The wrapped-output secret test printed and saved `API_KEY=[REDACTED]`, so the fake key did not leak. A synthetic email address was not redacted and appeared in the saved output and `factory status`, even though a valid `--plain` summary was present. The README promises secret redaction, not email redaction, but the skill's own privacy scanner treats emails as private at `skills/factory/scripts/factorylib.py:398-415`. Either redact private-looking output before storage/status or document that wrapped output may retain personal data.

5. The first failed eval run was retained and the later passing run became the shown result, as expected. Reports still showed one never-closed feature because this review intentionally did not advance or close the full build lifecycle; this is not counted as a product failure.

6. Repository integration lines 47-50 and 52 fail because the supplied review copy lacks root `README.md`, root `CHANGELOG.md`, and `origin/main`. Those failures are evidence gaps in the submitted review package as well as release blockers; they are not inferred defects in unseen files.
