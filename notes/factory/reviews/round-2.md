# Factory public skill review, round 2

Verdict: not done. 48 of 55 lines pass, 7 fail (17, 19, 24, 38, 40, 51, 55). Of the 21 lines open after round 1, 15 are closed and 6 are still open (17, 19, 24, 38, 40, 55). Line 51 passed in round 1 and fails now on new evidence.

Scope: `skills/factory/`, `CONTRIBUTING.md`, `notes/factory/CHECKLIST.md`, `notes/factory/reviews/round-1.md` and `repo-changes/`. Nothing outside this folder was used. I never saw the build. No network, no model call. Every Factory command I ran had `HOME` and `FACTORY_HOME` set to folders under `/tmp/fv11r2/` and `FACTORY_OSASCRIPT_BIN=/usr/bin/true`. Python was `/usr/bin/python3` (3.9.6).

One thing I could not fully confirm: the test harness removes `FACTORY_OSASCRIPT_BIN` from the environment of the commands it starts (`tests/common.py:86-90`), so my override did not reach them. The shared test settings use `"notify": {"channels": []}` (`tests/common.py:173`) and the notification tests set their own fake program, so a real notification is unlikely, but I did not trace every test. See other finding 1.

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | Every skill file is under `skills/factory/` (file listing; `repo-changes/branch-summary.txt` shows the same). |
| 2 | PASS | `skills/factory/SKILL.md` exists with front matter at lines 1-4. |
| 3 | PASS | `SKILL.md:3` is `name: factory`. |
| 4 | PASS | `SKILL.md:2` holds the description. |
| 5 | PASS | Measured length: 310 characters. |
| 6 | PASS | `SKILL.md:2`: "Use when the owner says "factory", "run the build process" ... or hands over a goal". |
| 7 | PASS | `skills/factory/README.md` exists. |
| 8 | PASS | `README.md:7-16`, "What it does". |
| 9 | PASS | `README.md:66-76`, "Install", requirements and 5 steps. |
| 10 | PASS | `README.md:78-89`, "How a run goes", 8 steps. |
| 11 | PASS | `README.md:102-112`, "Known limits". |
| 12 | PASS | `README.md:5` says "Version 0.1.0."; `factory --help` prints `factory 0.1.0`. |
| 13 | PASS | Round 1 open line, closed. The test that looked for a scanner outside the skill is gone; a search of `tests/*.py` for paths leaving the skill folder found none; the suite ran from a copy of the skill folder alone in `/tmp` with no missing-file error. |
| 14 | PASS | Round 1 open line, closed by narrowing the checklist promise (round 1 allowed that): reads are now "files you name on the command line or in `factory.json`, plus its own folder". Checked by running: after about 60 commands, `find /tmp/fv11r2/h -type f` (the temp `HOME`) listed 0 files; all new files were in the project folder or under `FACTORY_HOME`. Outside reads happened only for paths I named (`--from-graph /tmp/.../outside-GRAPH.yaml`, eval `file: ../outside.jsonl`). |
| 15 | PASS | Scan for U+2014 over `skills/factory`, `notes/factory`, `repo-changes`, `CONTRIBUTING.md`: 0 matches. No U+2013 either. |
| 16 | PASS | Round 1 open line, closed. Case-insensitive search for 21 hype words over the skill: no match. The README evals section is now a numbered walk-through (`README.md:28-64`) with each setting on its own line. |
| 17 | FAIL | Round 1 open line, partly closed. The seven terms round 1 named are now explained (`SKILL.md:12`, `README.md:3,11,32,41,64`, `PROCESS.md:10-16`). Still unexplained at first use: "Conductor app" (`SKILL.md:118,140-142`; never explained anywhere, and it is an outside product), "rubric" (`SKILL.md:43,51`; `PROCESS.md:33`; never defined), "constitution" (`SKILL.md:23`, explained only in `PROCESS.md:60`). |
| 18 | PASS | Round 1 open line, closed. Marked as picked: 3 rounds (`SKILL.md:45`, `PROCESS.md:122`), summary length (`SKILL.md:100`), 40 and 160 characters (`SKILL.md:104`), 480 seconds (`SKILL.md:108`), 5 questions and 300 characters (`SKILL.md:116`), 3 process changes (`SKILL.md:65`), table speeds (`PROCESS.md:88`), plus the blanket statement at `README.md:91`. No number is attributed to a source. A few numbers lean only on the blanket statement; see other finding 9. |
| 19 | FAIL | Round 1 open line, partly closed. The two `PROCESS.md` claims are now marked as the author's observation (`PROCESS.md:122,165`). New: `README.md:24-26` describes "The dashboard's Factory view" and says "Approval stays in the app; the page only reads", but no dashboard, page or app is in the folder, and `README.md:109` says "No dashboard is included". Also `README.md:112` says "see its list of what is left out"; no such list exists in the folder or in `factory eval improve --help`. |
| 20 | PASS | Search for consulting, hire, paid, services, contact, fee over the skill: no match. |
| 21 | PASS | Name search found only two vendor names used as rejection probes (`tests/fixtures/page/plain_probes.json:427-428`). No private person, client or employer name. |
| 22 | PASS | Pattern search for home paths, emails and key shapes: only the checklist's own `/Users/<name>` placeholders and synthetic key strings built from repeated letters (`tests/test_factorylib.py:175-177`). |
| 23 | PASS | The kit's own `scan_text` run over every file in `skills/factory/`: 0 findings. Fixtures are generated (`tests/fixtures/generate_fixtures.py`) and agent programs are fakes. |
| 24 | FAIL | Round 1 open line, still open. The scanner with a `--git-changed` mode is not in this folder (search for `git-changed` over the skill: no match) and `repo-changes/` holds no scan output, so the command on this line cannot be run or checked. Stand-in evidence only: the kit's `scan_text` over all supplied files flagged just the placeholder paths in the checklist and in round 1. |
| 25 | PASS | `/usr/bin/python3 --version` is 3.9.6; `py_compile` over every `.py` file exited 0. |
| 26 | PASS | Import list: standard library only, plus the kit's own `factorylib`, `evals` and `tests`. |
| 27 | PASS | `README.md:68`: "Python 3.9 or newer, standard library only. Git." and the agent CLIs. |
| 28 | PASS | Search of `scripts/` for `.claude` and `settings.json`: no match. |
| 29 | PASS | `grep -rn "unlink\|rmtree\|os.remove" scripts`: no match. Also no `os.rename`, `os.replace` or truncate. New files are opened in create-only mode (`factory.py:373`, `agents.py:413`). `factory init` run twice left `factory.json` byte-identical. |
| 30 | PASS | `factory.py --help </dev/null`: exit 0, first line `factory 0.1.0: the factory kit`. |
| 31 | PASS | All 13 names are in the root help. |
| 32 | PASS | `plain` and `eval` (the README's two extra names, `README.md:20`) are in the root help too. |
| 33 | PASS | Round 1 open line, closed. `--help` exited 0 for all 15 commands and for `eval run`, `eval show`, `eval diagnose`, `eval improve` (and `start`, `next`, `brief`, `decide`, `report`), `log start/end/event/beat`, `gate open/close/sent`. |
| 34 | PASS | Every `--flag` found in `SKILL.md`, `README.md`, `PROCESS.md` and `templates/*.md` appears in the collected help text: 0 missing. |
| 35 | PASS | `PROCESS.md`, `templates/`, `factory.example.json`, `machine.example.json` all exist. |
| 36 | PASS | About 40 bad inputs with stdin closed all printed one `factory:` line and no traceback (unknown command, missing arguments, `../evil` build id, unknown span, bad verdict, bad kind, broken `factory.json`, missing input file, missing program). One rough edge in other finding 6. |
| 37 | PASS | `python3 -m unittest discover -s tests -t .` from the skill folder found and ran 123 tests. |
| 38 | FAIL | Round 1 open line, still open. Clean copy in `/tmp`, run twice. Checklist command: `Ran 123 tests in 81.724s`, `FAILED (failures=1)`, exit 1. README command (`compileall -q scripts && unittest ...`): `Ran 123 tests in 82.649s`, `FAILED (failures=1)`, exit 1. Both times: `test_wait_timeout_nothing_running_and_no_build`, `tests/test_agents.py:318`, `AssertionError: 0.1299... not less than 0.1`. This is the same test round 1 reported; the 0.1 second limit is unchanged and the privacy-scanner failure is the one that went away. |
| 39 | PASS | The only network code is the local model service probe in `scripts/preflight.py:237-243`; tests use fake programs and `tests/test_evals.py:1137` forbids network modules in the eval code. No model was called in my runs. Caveat in other finding 1. |
| 40 | FAIL | Round 1 open line, still open. Wall time 82.03 s (checklist command) and 82.98 s (README command) on an idle machine (load about 1.7). Limit is 60 s. `README.md:116` says "about a minute". |
| 41 | PASS | `README.md:102-112`, 8 limits. |
| 42 | PASS | `README.md:105`. |
| 43 | PASS | `README.md:106`. |
| 44 | PASS | `README.md:107`. |
| 45 | PASS | `README.md:104` and `108`. |
| 46 | PASS | `README.md:109`. But see line 19 for the section that contradicts it. |
| 47 | PASS | Round 1 open line, closed. `repo-changes/README-and-CHANGELOG.diff`: one added row, between `evidence-check` and `venture-assessor`, starting with a verb like its neighbours ("Runs a spec-first build on any project..."). |
| 48 | PASS | Round 1 open line, closed. The row says what it does and ends "Use it when you hand over a goal and want it built and checked by agents." No offer of a service. |
| 49 | PASS | Round 1 open line, closed. One added line, "Skills: factory 0.1.0. ...", in the list that ends just before `### Changed`, at line 11 of the file. The diff does not show the `Unreleased` and `Added` headings themselves, so the section is read from position. |
| 50 | PASS | Round 1 open line, closed. The diff has 2 added lines and 0 removed lines. |
| 51 | FAIL | Passed in round 1, fails on the repository evidence. Both files are on disk in `notes/factory/`, but `repo-changes/branch-summary.txt` lists only `notes/factory/CHECKLIST.md` under `notes/`. `notes/factory/reviews/round-1.md` is not in the branch diff, so the review rounds are not saved on the branch that would be merged. |
| 52 | PASS | Round 1 open line, closed. `git merge-base --is-ancestor origin/main HEAD: yes`; all 66 changed files are under `skills/factory/`, `notes/factory/`, or are `README.md` and `CHANGELOG.md`. |
| 53 | PASS | I saw the skill folder and the checklist, plus the review inputs needed for sections H and I (`CONTRIBUTING.md`, round 1, `repo-changes/`). No build notes or history. |
| 54 | PASS | Cases below under "What I ran". |
| 55 | FAIL | Round 1 open line, still open. This round has 6 other failing lines. |

## Open lines

- **Line 17.** Done means: one sentence each, with an example, the first time "rubric", "constitution" (in `SKILL.md`) and "Conductor app" appear, or the Conductor text is removed.
- **Line 19.** Done means: `README.md:24-26` is removed, or it says plainly that the page is a separate thing that is not shipped and what the kit provides for it; and the "see its list of what is left out" pointer at `README.md:112` leads to a list that exists in the folder.
- **Line 24.** Done means: the exact scan command and its output (exit 0) are saved in `repo-changes/`, or the scanner is supplied so the reviewer can run it.
- **Line 38.** Done means: the README test command exits 0 on a clean copy, three runs in a row. The `0.1` second limit at `tests/test_agents.py:318` measures a whole Python start-up and failed in both of my runs and in round 1; it needs a limit that holds on an ordinary machine, or a different way to prove "exits at once".
- **Line 40.** Done means: the README command finishes in under 60 seconds of wall time on `/usr/bin/python3` 3.9, with the timing shown, and `README.md:116` states the measured figure.
- **Line 51.** Done means: `git diff --stat origin/main` lists `notes/factory/reviews/round-1.md` and `round-2.md` (and any later round).
- **Line 55.** Done means: a later independent round passes all 55 lines.

## What I ran (cases the author did not show)

- **README eval example, copied exactly.** `factory init`, the two-line `evals.jsonl`, the `evals` block, `factory new demo --title Demo`, `factory eval run upper`. Output: `eval upper: 2 of 2 passed, accuracy 1.0000 (target >=0.9 met)`, exit 0. `eval show`, `eval diagnose`, `status` and `report-card` agreed. It works. One snag in other finding 4.
- **Broken eval sets.** Invalid JSON line (`bad.jsonl line 2: not valid JSON`, exit 2), empty file (exit 4), duplicate id (exit 2), missing file (exit 3), string-form scorer (clear message, exit 2), program that exits 7 (0 of 2, exit 1), program slower than its limit (`timed out after 0.3 s`, exit 1), program that prints a token (redacted, not found on disk).
- **Build ids and titles.** `../evil`, `a/b`, empty, a name with a space and an accent: all refused. Existing build without `--adopt`: refused, nothing changed.
- **Log and gates.** Closing a span twice, unknown span, bad verdict, bad kind, a question holding `AC3`, a too-long question, closing a gate twice: all refused with plain messages.
- **Wrapped program** that prints three secrets and exits 3: exit code passed through, two of three secrets replaced (other finding 2).
- **25 `log event` commands at the same moment** on one build: all 26 lines of the log parsed as JSON, none lost.
- **Graphs.** Unknown dependency and unknown stage member: refused. Binary junk: refused. Duplicate ids and a cycle: accepted (other finding 3).
- **`factory plain --dry-run` and `--fallback-only`**: counted and filled 6 summaries with no model.

## Other findings

1. **The tests remove the caller's notification override.** `tests/common.py:86-90` deletes `FACTORY_OSASCRIPT_BIN` (and the other `FACTORY_*_BIN` settings) before starting commands. A person who sets it to keep the suite silent is not protected; safety rests on each test's own settings. Worth a test that proves no test can reach the real notifier.
2. **A bearer token is not redacted.** A wrapped program printed `API_KEY=...`, `password: ...` and `Authorization: Bearer <32 letters and digits>`. The first two became `[REDACTED]`; the bearer token was printed and saved as is in `messages/s015.out.md`. `README.md:110` promises that tokens are replaced.
3. **A graph with a duplicate piece id and a cycle is accepted.** `A depends_on [B]`, `B depends_on [A]`, and a second piece also named `A`: `factory new g4 --from-graph` exited 0. `plan.json` holds two pieces with id `A`, and the first `A` lost its dependency without a word (`"depends_on": []`). `PROCESS.md:103` says each piece is distinct and merges go in graph order. Also `plan.json` always records `"source": "GRAPH.yaml"` whatever the file was called (`factorylib.py:2282`).
4. **The README's replace instruction does not match what `init` writes.** `README.md:50` says to replace `"evals": {"metrics": [], "sets": []}`, but `factory init` writes that block across four lines, so a literal search finds nothing. The text matches `factory.example.json` only.
5. **`factory phase` accepts any name.** `factory phase bogus` printed `phase: bogus`, exit 0. `SKILL.md:37` lists twelve phase names.
6. **A 300-character build id** gives `factory: unexpected error (OSError: [Errno 63] File name too long: ...)`, exit 1. No traceback, but not a plain message. An empty `--title ""` and a 5000-character title are accepted.
7. **Gate limits differ from the text.** `SKILL.md:116` says the command refuses a question over 300 characters. In practice a single-sentence question is refused at 200 characters ("Its first sentence is longer than 200 characters"), and another message mentions 400 characters (`factorylib.py:599-600`). The limit of 5 questions per gate is not enforced: 7 were open under `GATE A` at once. The text says "at most 5" as a rule for the orchestrator, so this is a note, not a broken promise.
8. **`factory check` wording for a call that is still running.** A planned call that was started but not ended is reported as "Expected but not logged", with `unfinished 0`. After `log end` it matched. "Started, not finished" would be truer.
9. **Numbers that rest only on the README's blanket statement:** the breaker limits "fails twice" and "two churn rounds" (`SKILL.md:53`, `PROCESS.md:128-129`), the 1 MB line limit (`README.md:111`), "top 3 risks" (`PROCESS.md:119`), "at most 3 process changes" in `PROCESS.md:181` (marked in `SKILL.md:65` only), and the 200 and 400 character limits in finding 7.
10. **Small things.** `factory status` showed "No activity since Nov 26" when the local date was Nov 25 (it uses the UTC date) and showed it seconds after activity. `factory eval ... --help` text starts with `factory: usage:`, which looks like an error. `factory report-card` on a build with no timed work prints `factory: ... Report not written.` and exits 0. The checklist says it was "written before the skill folder goes into this repo", but line 14 was reworded after round 1; worth a dated note in the checklist. Refused commands show up on the board as "WARNING 5 log entries failed and were not recorded", which is accurate but alarming for typing mistakes.

Round 1 other findings, rechecked: the README scorer example is fixed (1); the email limit is now documented at `README.md:110` (4); the missing repository files are supplied through `repo-changes/` (6).
