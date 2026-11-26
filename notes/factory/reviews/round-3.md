# Factory public skill review, round 3

Verdict: not done. 52 of 55 lines pass, 3 fail (17, 24, 55). Of the 7 lines open after round 2, 4 are closed (19, 38, 40, 51) and 3 are still open (17, 24, 55). Every line that was open after round 1 is closed except 17, 24 and 55.

Scope: `skills/factory/`, `CONTRIBUTING.md`, `notes/factory/` (checklist, check record, rounds 1 and 2) and `repo-changes/`. Nothing outside this folder was used. I never saw the build. No network, no model call, no real notification. Every Factory command I ran had `HOME` and `FACTORY_HOME` set to folders under `/tmp/fr3/`, `FACTORY_OSASCRIPT_BIN=/usr/bin/true`, and a `PATH` of system folders only, so no agent program could be found. Python was `/usr/bin/python3` (3.9.6). I did not run a full `factory preflight` or `factory plain` without `--fallback-only`, because those are the two commands that would call a model.

This round was done by a Claude session (Claude Fable 5.2). See other finding 1: the check record says otherwise.

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | Every skill file is under `skills/factory/`; `repo-changes/branch-summary.txt` shows the same. |
| 2 | PASS | `skills/factory/SKILL.md` exists, front matter at lines 1-4. |
| 3 | PASS | `SKILL.md:3` is `name: factory`. |
| 4 | PASS | `SKILL.md:2` holds the description. |
| 5 | PASS | Measured length: 310 characters. |
| 6 | PASS | `SKILL.md:2`: "Use when the owner says "factory", "run the build process" ... or hands over a goal". |
| 7 | PASS | `skills/factory/README.md` exists. |
| 8 | PASS | `README.md:7-16`, "What it does". |
| 9 | PASS | `README.md:62-72`, "Install": requirements and 5 steps. |
| 10 | PASS | `README.md:74-83`, "How a run goes", 8 steps. |
| 11 | PASS | `README.md:98-108`, "Known limits". |
| 12 | PASS | `README.md:5` "Version 0.1.0."; `factory --help` prints `factory 0.1.0`. |
| 13 | PASS | The suite ran 4 times from a copy of the skill folder alone in `/tmp` with no missing file. After the runs, `diff -rq` between the copy and the original showed no difference, so the tests write nothing into the skill folder. |
| 14 | PASS | After about 120 commands, the temp `HOME` held 0 files. The two project folders held only what I put there plus `factory.json` from `factory init`. Everything else the kit wrote was under `FACTORY_HOME` (`current.jsonl`, `runs/<project>/<build>/...`). Reads outside those places happened only for paths I named (`--from-graph /tmp/fr3/cyc.yaml`, an eval set with an absolute `file`). |
| 15 | PASS | Scan for U+2014 and U+2013 over all 70 files in `skills/factory`, `notes/factory`, `repo-changes` and `CONTRIBUTING.md`: 0 hits. |
| 16 | PASS | Case-insensitive search for 21 hype words: the only hits are the checklist's own list at `CHECKLIST.md:27`. The README reads as plain steps. |
| 17 | FAIL | Round 2's three terms are fixed: "rubric" (`SKILL.md:43`, `PROCESS.md:33`), "constitution" (`SKILL.md:23`), "Conductor app" (`SKILL.md:118`). Still unexplained: "the page" and "the Factory page". `SKILL.md:104` says "The plan for the page comes from `GRAPH.yaml`" and "so the page stays readable"; `templates/GRAPH.yaml:5,9,13` and `templates/plain-rules.md:1,3` say "the Factory page" and "the page shows only the first sentence on a card". No page is in the folder, nothing says what it is, and `README.md:105` says no dashboard is included. Round 2 failed line 19 for this same thing in the README; it was removed there and left in these three files. |
| 18 | PASS | Marked as picked: 3 rounds (`SKILL.md:45`, `PROCESS.md:122`), summary length (`SKILL.md:100`), 40 and 160 characters (`SKILL.md:104`), 480 seconds (`SKILL.md:108`), 5 questions and 300 characters (`SKILL.md:116`), 3 process changes (`SKILL.md:65`), table speeds (`PROCESS.md:88`), blanket statement at `README.md:87`. The one measured number ("about 40 seconds on the author's Mac", `README.md:112`) names where it came from, and I measured the same. A few numbers still lean only on the blanket statement; see other finding 8. |
| 19 | PASS | Round 2 open line, closed. The README section about a dashboard view is gone, and so is the pointer to a "list of what is left out". A search of `README.md` for "dashboard" finds only limit 6 ("No dashboard is included"). The two `PROCESS.md` claims are marked as the author's observation (`PROCESS.md:122,165`). The README claims I could test held: the eval example prints the exact line it says, and the test time matches. |
| 20 | PASS | Search for consulting, hire, paid work, services, contact, fee, freelance over the skill and notes: only the checklist's own question and the earlier reviews quoting it. |
| 21 | PASS | No private person, client or employer name in `skills/factory/` or `notes/factory/`. Names found are AI products used as settings or test probes. |
| 22 | PASS | Pattern search for home paths, email addresses and key shapes: only synthetic key strings built in tests (`tests/test_plain.py:330,465`, `tests/test_factorylib.py:176`) and the checklist's own placeholder at `CHECKLIST.md:36`. |
| 23 | PASS | Fixtures are generated (`tests/fixtures/generate_fixtures.py`, `tests/fixtures/page/make_page_fixtures.py`); agent programs in tests are fakes written by `tests/common.py:150-156`. |
| 24 | FAIL | Round 1 open line, still open. The scan is now on record in `notes/factory/README.md`, and the record shows it did not pass: `notes/factory/reviews/round-1.md:88: secret: [12 chars]`, `privacy scan: 1 hits in 1 files (68 files scanned, 16241 added lines scanned)`, `exit 1`. The hit looks like a false alarm (that line of round 1 quotes a key name followed by the kit's own replaced-value marker, not a real secret), but the line asks for exit 0 and the record says exit 1. The scan also covered 68 files while the branch summary lists 69. |
| 25 | PASS | `/usr/bin/python3 --version`: 3.9.6. `py_compile` over every `.py` file: no error. |
| 26 | PASS | Parsed every import: standard library only, plus the kit's own `factorylib`, `evals` and `tests`. |
| 27 | PASS | `README.md:64`: "Python 3.9 or newer, standard library only. Git." and the agent programs. |
| 28 | PASS | Search of `scripts/` for `.claude` and `settings.json`: no match. Temp `HOME` stayed empty. |
| 29 | PASS | `grep -rn "unlink\|rmtree\|os.remove" scripts`: no match. No `os.rename`, `os.replace` or truncate either. The log is opened in append mode (`factorylib.py:229,1058`, `agents.py:145`). `factory new` on an existing build exits 1 and changes nothing. A changed plan on `--adopt` was saved beside the old one as `plan-20261126T015343Z.json`, and `plan.json` was kept. |
| 30 | PASS | `factory.py --help </dev/null`: exit 0, first line `factory 0.1.0: the factory kit`. |
| 31 | PASS | All 13 names are in the root help. |
| 32 | PASS | `plain` and `eval` (`README.md:20`) are in the root help too. |
| 33 | PASS | `--help` exited 0 for all 15 commands and for `eval run/show/diagnose/improve`, `eval improve start/next/brief/decide/report`, `log start/end/event/beat`, `gate open/close/sent` (31 help calls). |
| 34 | PASS | Every `--flag` in `SKILL.md`, `README.md`, `PROCESS.md` and `templates/*.md` appears in the collected help text: 0 missing. |
| 35 | PASS | `PROCESS.md`, `templates/`, `factory.example.json`, `machine.example.json` all exist. |
| 36 | PASS | About 45 bad inputs with stdin closed (both `</dev/null` and `<&-`): each printed one line starting `factory:` and no traceback. Covered: unknown phase and step names, bad build ids, missing input file, bad kind and verdict, bad `--timeout`, broken, empty and wrong-shaped `factory.json`, unknown eval set, Factory home that is a file or is read-only. Rough edges in other finding 6. |
| 37 | PASS | `PYTHONPYCACHEPREFIX=/tmp/factory-test-cache python3 -m unittest discover -s tests -t .` from the skill folder found and ran 123 tests. `README.md:112` gives the same command. |
| 38 | PASS | Round 1 open line, closed. Clean copy in `/tmp`, 4 runs in a row, all `Ran 123 tests`, `OK`, exit 0. Three with the README's cache folder and one with a fresh, empty cache folder. The 0.1 second limit at `tests/test_agents.py:318` is unchanged but held every time; see other finding 5. |
| 39 | PASS | The only network code is the local model service probe in `scripts/preflight.py:238-245`. Preflight tests point every agent program at a fake (`tests/test_preflight.py:61-65`), and the shared test settings have no notification channel (`tests/common.py:173`). Caveat in other finding 4. |
| 40 | PASS | Round 1 open line, closed. Wall time of the four runs: 40.56 s, 39.13 s, 39.29 s, and 40.51 s with an empty cache. Limit is 60 s. `README.md:112` says "about 40 seconds". |
| 41 | PASS | `README.md:98-108`, 8 limits. |
| 42 | PASS | `README.md:101`. |
| 43 | PASS | `README.md:102`. |
| 44 | PASS | `README.md:103`. |
| 45 | PASS | `README.md:100` and `104`. |
| 46 | PASS | `README.md:105`. |
| 47 | PASS | `repo-changes/README-and-CHANGELOG.diff`: one added row, between `evidence-check` and `venture-assessor`, starting with a verb like its neighbours. |
| 48 | PASS | The row says what it does and ends "Use it when you hand over a goal and want it built and checked by agents." No offer of a service. |
| 49 | PASS | One added line, "Skills: factory 0.1.0. ...", in the list that ends just before `### Changed`. The diff does not show the `Unreleased` and `Added` headings, so the section is read from position, as in round 2. |
| 50 | PASS | The diff has 2 added lines and 0 removed lines. |
| 51 | PASS | Round 2 open line, closed. `repo-changes/branch-summary.txt` now lists `notes/factory/CHECKLIST.md`, `README.md`, `reviews/round-1.md` and `reviews/round-2.md`. This file (`round-3.md`) is new and still has to be added to the branch. |
| 52 | PASS | `git merge-base --is-ancestor origin/main HEAD: yes`. All 69 changed files are under `skills/factory/`, `notes/factory/`, or are `README.md` and `CHANGELOG.md`. |
| 53 | PASS | I saw the skill folder and the checklist, plus what sections H and I need (`CONTRIBUTING.md`, the two earlier rounds, the check record, `repo-changes/`). No build notes or history. |
| 54 | PASS | Cases listed under "What I ran". |
| 55 | FAIL | This round has two other failing lines (17 and 24). |

## Open lines

- **Line 17.** Done means: `SKILL.md:104`, `templates/GRAPH.yaml:5,9,13` and `templates/plain-rules.md:1,3` no longer speak of a page nobody can find. Either say once, with an example, what "the page" is (for instance "the board that `factory status` prints", or "a separate web page that is not shipped with this kit and reads `plan.json`"), or reword the lines to name `factory status` and the report card.
- **Line 24.** Done means: the scan record in `notes/factory/README.md` ends in `0 hits` and `exit 0`, and its file count matches the branch (it will be 70 with this round). Two honest ways to get there: teach the scanner that the kit's replaced-value marker is not a secret, or reword `round-1.md:88` with a dated note saying the author changed that one line and why. This file was written to avoid key-shaped text, so it should add no hit, but the rerun has to show it.
- **Line 55.** Done means: a later independent round passes all 55 lines. If only lines 17 and 24 change, that round can be short.

## What I ran (cases the author did not show)

- **README eval example, copied exactly.** `factory init`, the two-line `evals.jsonl`, the `evals` block from `README.md:49-53`, `factory new demo --title Demo`, `factory eval run upper`. Output: `eval upper: 2 of 2 passed, accuracy 1.0000 (target >=0.9 met)`, exit 0. `eval show`, `eval diagnose`, `status`, `trace-report` and `report-card` agreed. It works. One snag, carried from round 2, in other finding 3.
- **Scorers and odd examples.** `number` (1 of 2, clear reason), `contains`, `json_field` against output that is not JSON (0 of 1, clear reason), an object as input, a null expected value, accented text, a 300-example set (1.7 s, all right), a program that prints 3 MB (marked "output too large", nothing huge saved), a program that leaves a child process behind (did not hang), cost lines with a negative and a not-a-number value (ignored, "cost: not reported"), a cost target with no cost reported (target not met), an empty `targets` (refused with the exact setting named), a file with a byte order mark and Windows line ends (refused, see finding 7), an absolute path to a system file as the set file (refused as not valid JSON).
- **Six runs of one eval set started at the same moment.** All six finished, each wrote its own pair of result files, and every line of the log and the eval index still parsed as JSON.
- **Improve loop commands** outside a git project: `start` refused with "improve needs a git project with no uncommitted changes"; `next`, `brief`, `report` said there is no session; `decide --suite maybe` refused. No model was reached.
- **Wrapped programs.** One that prints nine kinds of secret and exits 3 (exit code passed through; results in finding 2). One killed by signal 9 (exit 137). One that prints a 1.5 MB line (replaced by a note with the size; the next line was still checked and its key replaced). A run with no `--input` (refused). A model that may keep data, without and with `--non-private` from a private folder (both refused, nothing sent).
- **Gates.** A 350-character question, a question with a criterion id, closing and marking as sent a question that does not exist: all refused. Seven questions open under one gate: all accepted (finding 8). With the example machine file in place and the fake notifier, `gate open` exited 0 and `preflight --only notify:desktop` reported `PASS`.
- **Graphs.** A 60-character `plain_name` and a piece in no stage: refused with both problems listed. A cycle with a repeated piece id: accepted (finding 3).
- **Broken surroundings.** `factory.json` cut off, empty, a list, or with a step that has no time limit: one plain line each. No `factory.json` at all: `status` still shows the current build, `new` asks for a project name. Factory home that is a file or read-only: one line, no traceback (finding 6). A junk line added to a log: `status` warned "1 line in the log could not be read and was skipped" and carried on.

## Other findings

1. **The check record names the wrong reviewer for this round.** `notes/factory/README.md:7` says "Round 1 and round 3 were done by GPT 5.6". This round was done by a Claude session. The line was also written before this round existed. It should be corrected before merge; a record of how something was checked should not say things in advance.
2. **Three kinds of secret are still not replaced in a wrapped program's output.** Replaced: a key assignment, a password line, a code-host token, a cloud access key id, an AI vendor key on stderr, and the first line of a private key block. Printed and saved as they were (in `messages/s002.out.md` under the build): a bearer token in an authorization line (round 2 finding 2, unchanged), the body and last line of the private key block, and a password inside a web address of the form `scheme://user:password@host`. `README.md:106` says API keys, tokens and passwords are replaced. Either catch these three or narrow the sentence to what is caught. No checklist line covers this, so it is not counted as a FAIL, but it is the finding I would fix first.
3. **Carried from round 2, unchanged.**
   - A graph with a cycle and a repeated piece id is accepted. `plan.json` held two pieces named `A`, the first with its dependency dropped without a word, and `"source": "GRAPH.yaml"` although the file was called `cyc.yaml`.
   - `README.md:46` says to replace `"evals": {"metrics": [], "sets": []}`, but `factory init` writes that block over several lines, so a search for that text in the new `factory.json` finds nothing. The reader has to work out what to replace.
   - `factory phase bogus` prints `phase: bogus` and exits 0.
   - `SKILL.md:116` says the command refuses a question longer than 300 characters. The real rule is 200 characters for the first sentence and 400 or three sentences in all (`factorylib.py:599-602`).
   - `factory status` says "No activity since Nov 26" seconds after activity, on a machine whose local date was Nov 25.
   - Help for `factory eval ...` starts with `factory: usage:`, which reads like an error.
4. **The tests still drop the caller's notifier override.** `tests/common.py:86-90` removes `FACTORY_OSASCRIPT_BIN` before starting commands. I read every test that names a desktop channel and each one sets its own fake program, so no real notification was sent in my runs. A test that proves no test can reach the real notifier would make that safe against future tests.
5. **The 0.1 second limit is still there.** `tests/test_agents.py:318` times a whole program start. It passed 4 of 4 here because the cache setting makes start-up fast, and `README.md:112` says plainly that without the setting "one timing test can fail". A wider limit, or checking the printed message instead of the clock, would remove the risk on a slower or busier machine.
6. **Three errors are not in plain words.** A 300-character build id, a Factory home that is a file, and a Factory home that cannot be written each give `factory: unexpected error (<Python error name>: ...)`. No traceback, so line 36 holds, but "the Factory home folder cannot be written" would be kinder.
7. **Small gaps between text and behaviour in evals.** `README.md:28` says `expected` can be any JSON value, but the `exact` scorer fails an example whose expected value is not text ("expected must be a string") and `json_field` wants an object. An example file saved with a byte order mark is refused as "line 1: not valid JSON", which will puzzle someone who saved it from a Windows editor.
8. **Numbers and limits, as in round 2.** The limit of 5 questions per gate is not enforced (7 were open at once); the text gives it as a rule for the orchestrator, so this is a note. Numbers that rest only on the blanket statement at `README.md:87`: "fails twice" and "two churn rounds" (`SKILL.md:53`), the 1 MB line limit (`README.md:107`), "top 3 risks" (`PROCESS.md:119`).
9. **Board wording.** After failed eval runs and refused commands, `factory status` says "WARNING 24 log entries failed and were not recorded". Most of those were eval runs that missed a target and typing mistakes that were refused, which is alarming for what happened. `factory check` shows "Piece name not recorded [A]" for a piece whose `plain_name` is in `plan.json`. The board showed the replaced-value marker as the last words of a failed agent row instead of the plain summary I gave.
10. **The checklist header still says it was "written before the skill folder goes into this repo"**, while line 14 was reworded after round 1. A dated note in the checklist would keep the record straight.
