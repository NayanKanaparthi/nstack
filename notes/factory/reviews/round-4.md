# Factory public skill review, round 4

Verdict: not done. 52 of 55 lines pass, 3 fail (17, 38, 55). Of the 3 lines open after round 3, line 24 is closed, line 17 is fixed in every place round 3 named but one leftover remains in a message the kit prints, and line 55 stays open because of the other two. Line 38 is a new failure: the first timed test run on a clean copy had 1 failing test out of 123; the next 5 runs passed.

Scope: `skills/factory/`, `CONTRIBUTING.md`, `notes/factory/` (checklist, check record, rounds 1 to 3) and `repo-changes/`. Nothing outside this folder was used. I never saw the build. No network, no model call, no real notification. Every Factory command I ran had `HOME` and `FACTORY_HOME` set to folders under `/tmp/fr4/`, `FACTORY_OSASCRIPT_BIN=/usr/bin/true`, and a `PATH` of system folders only. Python was `/usr/bin/python3` (3.9.6). I did not run `factory preflight` or `factory plain` without `--dry-run`. Timebox was 15 minutes, so lines not touched by the changes were spot-checked, not redone in full.

This round was done by a Claude session (Claude Fable 5.2).

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | Unchanged, spot-checked. 68 files under `skills/factory/` and `notes/factory/`. |
| 2 | PASS | Unchanged, spot-checked. |
| 3 | PASS | Unchanged, spot-checked. |
| 4 | PASS | Unchanged, spot-checked. |
| 5 | PASS | Unchanged, spot-checked. |
| 6 | PASS | Unchanged, spot-checked. |
| 7 | PASS | Unchanged, spot-checked. |
| 8 | PASS | Unchanged, spot-checked. |
| 9 | PASS | Unchanged, spot-checked. |
| 10 | PASS | Unchanged, spot-checked. |
| 11 | PASS | Unchanged, spot-checked. `README.md` still ends its limits at item 8, then "Tests". |
| 12 | PASS | `factory --help` first line: `factory 0.1.0: the factory kit`. |
| 13 | PASS | Six test runs from a copy of the skill folder alone in `/tmp/fr4/copy`. `diff -rq` between the copy and the original afterwards: no difference. |
| 14 | PASS | Two small projects under `/tmp/fr4/`. The project folders held only my files plus `factory.json`. Everything else the kit wrote was under `FACTORY_HOME` (`current.jsonl`, `runs/<project>/<build>/...`). The temp `HOME` held 0 files after all kit commands and test runs; 16 files appeared there only after I ran my own Python script as a wrapped program, and all 16 are the system Python's own compile cache (`Library/Caches/com.apple.python/...`), not written by the kit. |
| 15 | PASS | Scan for U+2014 and U+2013 over 71 files (`skills/factory`, `notes/factory`, `repo-changes`, `CONTRIBUTING.md`): 0 hits. |
| 16 | PASS | Hype word search: only the checklist's own list and earlier reviews quoting it. The reworded text in `SKILL.md:104`, `templates/GRAPH.yaml` and `templates/plain-rules.md` is plain. |
| 17 | FAIL | Checked in full. The three places round 3 named are fixed: `SKILL.md:104` now says "A dashboard can show a build as a plan of stages and pieces. No dashboard ships with this kit, but `factory new` writes the data one needs into `plan.json`"; `templates/GRAPH.yaml:5` says "a plan view (a dashboard that reads plan.json; none ships with this kit)"; `templates/plain-rules.md:1` says "in `factory status`, or in a dashboard if they have one". A search of `SKILL.md`, `README.md`, `PROCESS.md` and `templates/` for "page" finds only "one-page summary" (`SKILL.md:157`). One leftover: `scripts/factory.py:263` prints `factory: no stages block in the graph, so the page shows a flat list of pieces`. I got this line on my first `factory new demo --from-graph g.yaml` with a graph that has no `stages:` block. It is the same unexplained "the page" round 3 failed, now in text the kit shows the user, and the docs now say no such page ships. |
| 18 | PASS | Unchanged, spot-checked. The reworded `SKILL.md:104` still marks 40 and 160 as "our picks". |
| 19 | PASS | Unchanged, spot-checked. `README.md` mentions a dashboard only in limit 6. |
| 20 | PASS | Search for consulting, freelance, hire: only the checklist and earlier reviews quoting it. |
| 21 | PASS | Unchanged, spot-checked. |
| 22 | PASS | Pattern search for home paths and email addresses over all 71 files: 0 hits outside the synthetic test strings round 3 listed. |
| 23 | PASS | Unchanged, spot-checked. |
| 24 | PASS | Checked in full. `notes/factory/README.md:13-17` now records `privacy scan: 0 hits in 0 files (70 files scanned, 16352 added lines scanned)` and `exit 0`. The file count matches the branch: `repo-changes/branch-summary.txt` says "70 files changed", and I count 68 files in the two folders plus the 2 root files. Both things round 3 asked for are met. The scanner is not in this folder, so I could not rerun it; the line passes on the record. Three caveats in other finding 1. |
| 25 | PASS | `/usr/bin/python3 -m py_compile` over every `.py` file: no error. |
| 26 | PASS | Unchanged, spot-checked. |
| 27 | PASS | Unchanged, spot-checked. |
| 28 | PASS | Search of `scripts/` for `.claude` and `settings.json`: no match. |
| 29 | PASS | Search of `scripts/` for unlink, rmtree, os.remove, os.rename, os.replace, truncate: no match. `factory new` on an existing build: "already exists", exit 1. |
| 30 | PASS | `factory.py --help </dev/null`: exit 0, prints `factory 0.1.0`. |
| 31 | PASS | All 13 names are in the root help. |
| 32 | PASS | `plain` and `eval` are in the root help. |
| 33 | PASS | `--help` exited 0 for all 15 commands and 16 sub-commands (31 calls). |
| 34 | PASS | Every `--flag` in `SKILL.md`, `README.md`, `PROCESS.md` and `templates/*.md` appears in the collected help text: 0 missing. |
| 35 | PASS | Unchanged, spot-checked. All four exist. |
| 36 | PASS | 8 bad inputs with stdin closed: each printed one line starting `factory:` and no traceback (existing build, unknown step, unknown eval set, bad `--timeout`, agent call with no `--call`, bad build name, unknown command, gate with an empty recommendation). |
| 37 | PASS | The README command, run from the skill folder, found and ran 123 tests. |
| 38 | FAIL | New failure. Run 1, the exact README command on a clean copy, timed: `Ran 123 tests in 39.670s`, `FAILED (failures=1)`, exit 1. The failing test is `test_run_sigterm_stops_child_and_span` (`tests/test_agents.py:158`): "wrapped child did not start". The test gives the wrapped program 0.4 seconds to start (`tests/test_agents.py:155`) and it took longer. Runs 2, 3 and 4 with the same command passed, and so did 2 runs with a fresh, empty cache folder. So 1 failure in 6 runs. Run 1 was the first on this copy and the README cache folder did not exist yet; machine load was about 1.9 on the 1 minute average. The line asks for exit 0 on a clean copy and the first run on a clean copy did not give it. |
| 39 | PASS | Unchanged, spot-checked. No real notification could be sent in my runs; see other finding 4. |
| 40 | PASS | Wall time of the six runs: 39.76 s, 39.10 s, 38.67 s, 38.85 s, and 40.65 s and 40.05 s with an empty cache. Limit is 60 s. |
| 41 | PASS | Unchanged, spot-checked. |
| 42 | PASS | Unchanged, spot-checked. |
| 43 | PASS | Unchanged, spot-checked. |
| 44 | PASS | Unchanged, spot-checked. |
| 45 | PASS | Unchanged, spot-checked. |
| 46 | PASS | `README.md:105`: "No dashboard is included. The board is `factory status`." |
| 47 | PASS | Unchanged, spot-checked. One added row between `evidence-check` and `venture-assessor`. |
| 48 | PASS | Unchanged, spot-checked. |
| 49 | PASS | Unchanged, spot-checked. Section read from position, as before. |
| 50 | PASS | The diff has 2 added lines and 0 removed lines. |
| 51 | PASS | `repo-changes/branch-summary.txt` lists the checklist, the check record and rounds 1 to 3. This file (`round-4.md`) is new and still has to be added to the branch. |
| 52 | PASS | Branch summary: `git merge-base --is-ancestor origin/main HEAD: yes`; all 70 changed files are in the four allowed places. |
| 53 | PASS | I saw the skill folder and the checklist, plus what sections H and I need. No build notes or history. |
| 54 | PASS | Short this round because of the timebox. Cases under "What I ran". |
| 55 | FAIL | This round has two other failing lines (17 and 38). |

## Open lines

- **Line 17.** Done means: `scripts/factory.py:263` no longer says "the page". For example: "no stages block in the graph, so no plan.json is written and a plan view would show a flat list of pieces". If a test checks the old words, change it with the message. A one-line change.
- **Line 38.** Done means: the README test command exits 0 on a clean copy on the first run as well as on later ones. The honest fix is in the test, not in the README: do not judge start-up by a 0.4 second clock. Wait several seconds for the pid file (the loop ends as soon as the file appears, so a passing run gets no slower), and give the same room to the 0.5 second and 0.4 second waits at `tests/test_agents.py:160,167`. Round 3 finding 5 warned about the sibling 0.1 second limit at `tests/test_agents.py:318`; fix that in the same pass, because it is the same kind of risk.
- **Line 55.** Done means: a later independent round passes all 55 lines. If only lines 17 and 38 change, that round can be short, but it should run the tests several times, starting with no cache folder.

## What I ran

- **Tests.** Six timed runs from a clean copy, as listed at lines 38 and 40.
- **A graph with no stages.** `factory init`, then `factory new demo --title Demo --from-graph g.yaml` with one piece and no `stages:` block: exit 0, the "page" message of line 17, and no `plan.json` written.
- **The template graph.** `templates/GRAPH.yaml` copied as it ships: `factory new` exit 0, `plan.json` written. `factory status`, `factory check` (exit 0, "Expected 4, logged 1, matched 1, missing 3") and `factory report-card` all ran.
- **A wrapped program that prints six fake secrets.** Results in other finding 2.
- **`factory plain --dry-run`.** "0 entries would be rewritten", exit 0, no model reached.
- **Bad inputs.** The 8 listed at line 36, plus `factory phase bogus` (other finding 3).

## Other findings

1. **Three caveats on the privacy scan record (line 24).**
   - The record says 16352 added lines were scanned. The branch summary says 16293 insertions, and my own count of the 70 files gives 16293 too. The scan counted 59 more lines than the branch adds, and the record does not say why. If the scanner also read files that are not on the branch, the record should say so.
   - Round 3 found 1 hit at `notes/factory/reviews/round-1.md:88`. That line is unchanged, and the scan now finds 0 hits, so the scanner or its pattern list must have changed. The record should say in one sentence what changed, so a reader can tell a taught scanner from a loosened one.
   - This file makes the branch 71 files. The scan has to be run again after it is added, and the record updated. I wrote this file without key-shaped text so it should add no hit.
2. **Three kinds of secret are still not replaced in a wrapped program's output.** Carried from round 3 finding 2, unchanged. Replaced: a key assignment line and the first line of a private key block. Printed and saved as they were in `messages/*.out.md`: a bearer value in an authorization line, the body and last line of the private key block, and a password inside a web address of the form `scheme://user:password@host`. `README.md:106` still says API keys, tokens and passwords are replaced. Either catch these three or narrow the sentence. No checklist line covers it, so it is not counted as a FAIL, but it is the finding I would fix first. Also carried: `factory status` shows the replaced-value marker as the last words of the agent row instead of the plain summary I gave with `--plain`.
3. **Carried from round 3, still there where I looked.** `factory phase bogus` prints `phase: bogus` and exits 0. `factory status` says "No activity since Nov 26" seconds after activity on a machine whose local date is Nov 25. `factory check` shows "Piece name not recorded [N0]" for a piece whose `plain_name` is in `plan.json`. I did not recheck the rest of round 3 findings 3 and 6 to 10 in this round; nothing in the changed text suggests they moved.
4. **The tests still drop the caller's notifier override** (`tests/common.py:86-90` removes `FACTORY_OSASCRIPT_BIN`). Carried from round 3 finding 4. No real notification was sent in my runs.
5. **The check record is corrected on who reviewed.** `notes/factory/README.md:7` now says round 1 was done by GPT 5.6 and "rounds 2 and later" by Claude sessions, which is right for rounds 2, 3 and 4. It still speaks for rounds that do not exist yet; naming the rounds done so far would be safer.
6. **Code comments point to a document that is not in the folder.** `scripts/factorylib.py`, `scripts/agents.py` and `scripts/factory.py` cite "PAGE-SPEC" sections on 13 lines, and `tests/fixtures/page/` keeps the name. These are comments and fixture names, not reader text, so they do not count under line 17, but a reader of the code cannot find the document they point to.
