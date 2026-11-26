# Factory public skill review, round 5

Verdict: done. 55 of 55 lines pass. The three lines round 4 left open (17, 38, 55) are closed. No regression found in the other lines. Five things are still worth fixing but none is a checklist line; they are under "Other findings".

Scope: `skills/factory/`, `CONTRIBUTING.md`, `notes/factory/` (checklist, check record, rounds 1 to 4) and `repo-changes/`. Nothing outside this folder was used. I never saw the build. No network, no model call, no real notification. Every Factory command and test run had `HOME` and `FACTORY_HOME` set to folders under `/tmp/fr5/`, `FACTORY_OSASCRIPT_BIN=/usr/bin/true`, and a `PATH` of system folders only, so `python3` was `/usr/bin/python3` (3.9.6). I did not run `factory preflight`, or `factory plain` without `--dry-run`. Timebox was 15 minutes: lines 17, 38 and 55 were checked in full, the rest were spot-checked for regressions.

This round was done by a Claude session (Claude Fable 5.2).

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | Unchanged, spot-checked. 69 files under `skills/factory/` and `notes/factory/` (68 plus round 4). |
| 2 | PASS | Unchanged, spot-checked. |
| 3 | PASS | Unchanged, spot-checked. `name: factory`. |
| 4 | PASS | Unchanged, spot-checked. |
| 5 | PASS | Unchanged, spot-checked. |
| 6 | PASS | Unchanged, spot-checked. Description still has "Use when the owner says ...". |
| 7 | PASS | Unchanged, spot-checked. |
| 8 | PASS | Unchanged, spot-checked. |
| 9 | PASS | Unchanged, spot-checked. |
| 10 | PASS | Unchanged, spot-checked. |
| 11 | PASS | Unchanged, spot-checked. Limits at `README.md:100-107`, then "Tests" at 110. |
| 12 | PASS | `README.md:5`: "Version 0.1.0." Help first line: `factory 0.1.0: the factory kit`. |
| 13 | PASS | All test runs were from a copy of the skill folder alone in `/tmp/fr5/copy`. `diff -rq` between the copy and the original after every run: no difference. |
| 14 | PASS | One small project under `/tmp/fr5/proj` with two builds. The project folder held only my two graph files plus `factory.json`. The builds and `plan.json` went under `FACTORY_HOME/runs/proj/`. The temp `HOME` held 16 files, all the system Python's own compile cache (`Library/Caches/com.apple.python/...`) caused by my timing helper, not by the kit; the count did not change across the kit commands. |
| 15 | PASS | Scan for U+2014 and U+2013 over `skills`, `notes`, `repo-changes`, `CONTRIBUTING.md`: 0 hits. |
| 16 | PASS | Hype word search outside the checklist and earlier reviews: 0 hits. The new message at `scripts/factory.py:263` is plain. |
| 17 | PASS | Checked in full. `scripts/factory.py:263` now prints `factory: no stages block in the graph, so the plan has no stages and a plan view shows a flat list of pieces`. I got exactly this on `factory new demo --from-graph g.yaml` with a graph that has no `stages:` block. "The page" is gone. "Plan view" is explained where a reader meets it first: `templates/GRAPH.yaml:5` ("a plan view (a dashboard that reads plan.json; none ships with this kit)") and `SKILL.md:104`; `templates/GRAPH.yaml:13` uses the same words as the message. A search of `scripts/factory.py` for "page" finds nothing, and a search of `SKILL.md`, `README.md`, `PROCESS.md` and `templates/` finds only "one-page summary" (`SKILL.md:157`). The test that checks the message (`tests/test_plan_board.py:173`) matches the unchanged first half and passes. One small accuracy note in other finding 1. |
| 18 | PASS | Unchanged, spot-checked. `SKILL.md:104` still marks 40 and 160 as "our picks". The README's "about 40 seconds on the author's Mac" names where the number comes from, and my runs agree. |
| 19 | PASS | Unchanged, spot-checked. |
| 20 | PASS | Search for consulting, freelance, hire outside the checklist and earlier reviews: 0 hits. |
| 21 | PASS | Unchanged, spot-checked. |
| 22 | PASS | Pattern search for home paths and email addresses over all files: 0 hits. |
| 23 | PASS | Unchanged, spot-checked. |
| 24 | PASS | `notes/factory/README.md:13-17` records `privacy scan: 0 hits in 0 files (71 files scanned, 16445 added lines scanned)` and `exit 0`. The file count matches `repo-changes/branch-summary.txt` ("71 files changed"). The scanner is not in this folder, so the line passes on the record, as in round 4. Caveats in other finding 2. |
| 25 | PASS | `/usr/bin/python3 -m py_compile` over every `.py` file in the copy: no error. |
| 26 | PASS | Import list of `scripts/`: standard library only, plus the kit's own `factorylib` and `evals`. |
| 27 | PASS | Unchanged, spot-checked. `README.md:64`. |
| 28 | PASS | Search of `scripts/` for `.claude` and `settings.json`: no match. |
| 29 | PASS | Search of `scripts/` for unlink, rmtree, os.remove, os.rename, os.replace, truncate: no match. `factory new` on an existing build: "already exists", exit 1. |
| 30 | PASS | `factory.py --help </dev/null`: exit 0, prints `factory 0.1.0`. |
| 31 | PASS | All 13 names are in the root help. |
| 32 | PASS | `plain` and `eval` are in the root help. |
| 33 | PASS | `--help` exited 0 for all 15 commands. Sub-commands not redone this round. |
| 34 | PASS | Every `--flag` in `SKILL.md`, `README.md` and `PROCESS.md` appears in the collected help text of the 15 commands: 0 missing. |
| 35 | PASS | Unchanged, spot-checked. All four exist. |
| 36 | PASS | 7 bad inputs with stdin closed: each printed one line starting `factory:` and no traceback (existing build, unknown step, unknown command, bad `--timeout`, bad build name, missing graph file, unknown gate flag). |
| 37 | PASS | The README command, run from the skill folder, found and ran 123 tests. |
| 38 | PASS | Checked in full. `/tmp/factory-test-cache` did not exist before run 1 (an older one was there; I moved it aside, see "What I ran"). The exact README command on a clean copy, three times in a row: run 1 (no cache folder) `Ran 123 tests in 39.910s`, `OK`, exit 0; run 2 `39.044s`, `OK`, exit 0; run 3 `39.112s`, `OK`, exit 0. A fourth run with a different, empty cache folder: `40.664s`, `OK`, exit 0. Load during the runs was 1.9 to 3.0 on the 1 minute average, higher than in round 4. The test that failed in round 4 (`test_run_sigterm_stops_child_and_span`) run alone 10 times, each with its own empty cache folder: 10 of 10 passed, 0.29 s to 0.42 s each. The fix: the wait for the child to start went from 0.4 s to 0.95 s (`tests/test_agents.py:155`) and the wait after the stop signal from 0.5 s to 0.95 s (`:160`). So 0 failures in 4 full runs and 10 single runs. Remaining risk in other finding 3. |
| 39 | PASS | Unchanged, spot-checked. The tests use fake programs; no real notification could be sent in my runs. See other finding 5. |
| 40 | PASS | Wall time of the four full runs: 40.2 s, 39.1 s, 39.2 s, 41 s. Limit is 60 s. |
| 41 | PASS | Unchanged, spot-checked. |
| 42 | PASS | `README.md:101`. |
| 43 | PASS | `README.md:102`. |
| 44 | PASS | `README.md:103`. |
| 45 | PASS | `README.md:100`. |
| 46 | PASS | `README.md:105`: "No dashboard is included. The board is `factory status`." |
| 47 | PASS | Unchanged, spot-checked. One added row. |
| 48 | PASS | Unchanged, spot-checked. |
| 49 | PASS | Unchanged, spot-checked. One added line. |
| 50 | PASS | The diff has 2 added lines and 0 removed lines. |
| 51 | PASS | `repo-changes/branch-summary.txt` lists the checklist, the check record and rounds 1 to 4. This file (`round-5.md`) is new and still has to be added to the branch. |
| 52 | PASS | Branch summary: `git merge-base --is-ancestor origin/main HEAD: yes`; all 71 changed files are in the four allowed places. |
| 53 | PASS | I saw the skill folder and the checklist, plus what sections H and I need. No build notes or history. |
| 54 | PASS | Short this round because of the timebox. Cases under "What I ran". Rounds 1 to 4 carry the heavier attempts to break it. |
| 55 | PASS | This round passes lines 1 to 54. |

## Open lines

None.

Two things must still happen before merge. They are bookkeeping, not open lines:

- Add this file to the branch (line 51). That makes the branch 72 files.
- Run the privacy scan again after adding it and update the count in `notes/factory/README.md` (line 24). I wrote this file with no key-shaped text, no path under a home folder and no address, so it should add no hit.

## What I ran

- **Tests.** Four timed full runs and 10 runs of the one test that failed in round 4, as listed at lines 38 and 40. Before run 1 a folder `/tmp/factory-test-cache` already existed from earlier work. I did not delete it; I moved it to `/tmp/fr5/old-factory-test-cache-moved-aside`, so run 1 started with no cache folder. A new `/tmp/factory-test-cache` now exists from my runs.
- **A graph with no stages.** `factory init`, then `factory new demo --title Demo --from-graph g.yaml` with one piece and no `stages:` block: exit 0, the new message of line 17, no `plan.json` written.
- **The same build again.** "already exists", exit 1.
- **The template graph.** `templates/GRAPH.yaml` copied as it ships: `factory new demo2` exit 0, `plan.json` written under `FACTORY_HOME`. `factory status` ran, exit 0.
- **`factory plain --dry-run`.** "0 entries would be rewritten", exit 0, no model reached.
- **Bad inputs.** The 7 listed at line 36.
- **Not redone this round:** the wrapped program that prints fake secrets, `factory check`, `factory report-card`, the 16 sub-command help calls, `factory phase bogus`. Round 4's results for these stand unchecked; nothing in the changed text touches them.

## Other findings

1. **The new message is a little off about `plan.json` (line 17, not a FAIL).** With no `stages:` block the kit writes no `plan.json` at all (I checked, and `tests/test_plan_board.py:172` asserts it). The message says "the plan has no stages", which reads as if a plan was written. `SKILL.md:104` also says `--from-graph` "writes `plan.json` into the build folder" with no "if the graph has a stages block". A reader building a dashboard would look for a file that is not there. Suggested words: "no stages block in the graph, so no plan.json is written; a plan view would show a flat list of pieces".
2. **Caveats on the privacy scan record (line 24), carried from round 4.**
   - The record says 16445 added lines were scanned. The branch summary says 16385 insertions, and my own count of the 71 files gives 16385. The scan counted 60 more lines than the branch adds (59 in round 4), and the record still does not say why.
   - Round 3 found 1 hit at `notes/factory/reviews/round-1.md:88`; the scan now finds 0 and the record still does not say what changed in the scanner or its pattern list.
   - The record says "this record itself is the only line added after the run". With this file added that is no longer true until the scan is rerun.
3. **The timing limits in the tests are wider but still under one second (line 38, not a FAIL).** Round 4 asked for several seconds of room. The fix gave 0.95 s at `tests/test_agents.py:155,160`, left 0.4 s at `:167,297,304`, and the sibling limits are 0.6 s (`:318`), 0.7 s (`:299`) and 0.95 s (`:108,256,382`). In my runs the child started well inside the limit (the whole test took 0.29 s to 0.42 s cold), so the margin is about two to three times, not ten. On a slower or busier machine the same failure can come back. The wait loops end as soon as the file appears, so raising the start-up and shutdown waits to 5 s would cost a passing run nothing. Also, `README.md:112` says "without it ... one timing test can fail": that is an honest note, and it would be better not to need it.
4. **Carried from rounds 3 and 4, not rechecked except where noted.**
   - Three kinds of secret are not replaced in a wrapped program's output (a bearer value in an authorization line, the body and last line of a private key block, a password inside a web address), while `README.md:106` says keys, tokens and passwords are replaced. Not rechecked this round. Still the finding I would fix first.
   - `factory status` said "No activity since Nov 26" seconds after I made the build, on a machine whose local date is Nov 25. Seen again this round.
   - `factory phase bogus` exits 0; `factory check` shows "Piece name not recorded" for a piece whose `plain_name` is in `plan.json`. Not rechecked.
   - Code comments cite "PAGE-SPEC" sections on 13 lines of `scripts/`, and `scripts/factorylib.py:2801` speaks of "the dashboard and the browser tests"; neither the document nor a dashboard is in the folder. Comments only, so not counted under line 17.
5. **The tests still drop the caller's notifier override** (`tests/common.py:87-90` removes `FACTORY_OSASCRIPT_BIN`). Carried from round 3. The tests that notify pass their own fake program, and no real notification was sent in my runs, but the override a careful person sets is ignored.
6. **The check record still speaks for future rounds.** `notes/factory/README.md:7` says "Rounds 2 and later were done by fresh Claude sessions". True for rounds 2 to 5. Naming the rounds done so far would be safer.
