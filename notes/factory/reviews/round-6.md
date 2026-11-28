# Factory public skill review, round 6

Verdict: not done. 45 of 55 checklist lines pass. Lines 18, 19, 21, 22, 24, 37, 38, 39, 46 and 55 fail.

Scope: only `skills/factory/`, `CONTRIBUTING.md`, `notes/factory/CHECKLIST.md`, and `notes/factory/reviews/round-5.md`. No external network, browser, notification, or real model call. Commands used `/usr/bin/python3` 3.9.6 with temporary `HOME`, `FACTORY_HOME`, and bytecode folders. `FACTORY_OSASCRIPT_BIN` was always `/usr/bin/true`.

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | The skill is wholly under `skills/factory/` with 75 files. |
| 2 | PASS | `skills/factory/SKILL.md` exists. |
| 3 | PASS | Front matter says `name: factory`. |
| 4 | PASS | Front matter has a description. |
| 5 | PASS | The description is 310 characters. |
| 6 | PASS | It says to use the skill when the owner asks for Factory or an agent build. |
| 7 | PASS | `skills/factory/README.md` exists. |
| 8 | PASS | The opening and What it does section explain the process. |
| 9 | PASS | Install steps are at README lines 77 to 87. |
| 10 | PASS | How a run goes is at lines 174 to 188. |
| 11 | PASS | Known limits is at lines 200 to 210. |
| 12 | PASS | README and help both say 0.1.0. |
| 13 | PASS | Scripts, dashboard, templates, settings examples, process text, and tests are inside the skill folder. |
| 14 | PASS | New dashboard code has no write primitives and reads only its own assets and Factory home; other writes remain project or Factory home writes. |
| 15 | PASS | Search found no em dash in `skills/factory` or `notes/factory`. |
| 16 | PASS | The named hype-word search found no hit outside prior review/checklist quotations. |
| 17 | PASS | User-facing terms are explained with examples; the model guide defines model, runner, free, and local. |
| 18 | FAIL | New picked values, including 3 and 10 second refreshes, a 1.5 second intro, and default port 7878, are not marked as author choices. |
| 19 | FAIL | The model guide makes outside claims about runner login, free-model availability, OpenRouter, Ollama, model privacy, and a 9 GB download without evidence in the folder. |
| 20 | PASS | No consulting, paid-work, or service offer was found. |
| 21 | FAIL | The new dashboard and README contain a full personal author name; the dashboard privacy test explicitly removes it before scanning. |
| 22 | FAIL | The dashboard contains and tests a personal GitHub account URL, which is an account detail. No home path, email, token, or key was found. |
| 23 | PASS | Test fixtures are synthetic. |
| 24 | FAIL | The required changed-tree privacy command and a current result are not present. Round 5 also said the scan had to be rerun after that review was added. |
| 25 | PASS | All 27 Python files compiled with `/usr/bin/python3` 3.9.6. |
| 26 | PASS | Product Python imports are standard library plus the kit's own modules. |
| 27 | PASS | README says Python 3.9+, standard library only, Git, and lists the configured agent tools. |
| 28 | PASS | Product scripts contain no Claude settings path or write. |
| 29 | PASS | Product scripts contain none of the listed deletion or replacement calls. |
| 30 | PASS | Root help exited 0 and printed `factory 0.1.0`. |
| 31 | PASS | Every command named by SKILL, including dashboard and finish, is in root help. |
| 32 | PASS | Every README command is in root help. |
| 33 | PASS | Help exited 0 for all 17 root commands. |
| 34 | PASS | Every flag named in README, SKILL, and PROCESS appeared in command help. |
| 35 | PASS | PROCESS, templates, and both settings examples exist. |
| 36 | PASS | Closed-stdin bad input exited 2 with a one-line `factory:` error and no traceback. |
| 37 | FAIL | The README unittest command is not all tests. `tests/browser/README.md` says the new Playwright runner is separate from the standard Python command. |
| 38 | FAIL | The exact isolated command ran 176 tests but exited 1: 4 failures and 18 errors, all from loopback binds denied by this sandbox. One test was skipped. |
| 39 | FAIL | No real model ran, but the new dashboard tests do use loopback sockets and HTTP, contradicting the literal no-network checklist and README claim. |
| 40 | PASS | The suite completed in 47.451 seconds, 47.77 seconds wall time. |
| 41 | PASS | README has a numbered Known limits section. |
| 42 | PASS | Limit 2 says built and proven on one macOS machine. |
| 43 | PASS | Limit 3 says sleep and desktop notification are macOS only. |
| 44 | PASS | Limit 4 says preflight sends a real one-line model request because it cannot read credit. |
| 45 | PASS | Limits 1 and 5 state the in-session logging limitation. |
| 46 | FAIL | The checklist still requires the README to say no dashboard exists. The update now ships and documents a dashboard. |
| 47 | PASS | Carried from round 5; the repository README row was unchanged by the supplied update. |
| 48 | PASS | Carried from round 5; the row wording previously passed. |
| 49 | PASS | Carried from round 5; the changelog entry previously passed. |
| 50 | PASS | Carried from round 5; its root-file diff previously passed. |
| 51 | PASS | The checklist, supplied prior review, and this review are under `notes/factory/`. |
| 52 | PASS | Carried from round 5; no supplied change is outside `skills/factory/` or `notes/factory/`. |
| 53 | PASS | This reviewer used only the four allowed inputs and never saw the build. |
| 54 | PASS | It ran the required isolated command, attempted the new server journey, and audited new claims and test mappings. |
| 55 | FAIL | This round has 10 failed lines. |

## Open lines

1. Update the checklist for the intentional dashboard change, then include the separate browser runner in the documented test command or stop calling the Python command all tests.
2. Rerun the Python suite and `factory dashboard --no-open --port 0` on a host that permits `127.0.0.1` binds. Here the command printed `factory: could not start the dashboard (Operation not permitted)`, so no address existed for curl; PID 9096 had exited with 1 and was confirmed stopped.
3. Make the model guide honest: do not put an uncalled model in a ready configuration. Confirm every named model without private data, or use placeholders selected from the user's own model list. The current tests check JSON shape and company-family strings, not whether a model exists or answers.
4. Remove or explicitly approve the personal name and account link, and rerun the changed-tree privacy scan.
5. Mark the dashboard timing and port choices as picks, and either back the outside product claims with included evidence or narrow them to instructions the user verifies.

## Other findings

- Rule labels are sound where they say `[enforced by code]`: the 10 table entries name real unittest functions, and related notification coverage also exists. The broader claim that every rule is labeled is false. SKILL hard rules at lines 128, 130, 131, 133, 134, 137 and 144 have neither label. The label-lint test checks only a short phrase list, so it does not catch these.
- The dashboard journey was attempted exactly with isolated homes, `--no-open`, port 0, curl, and PID cleanup. Platform socket policy blocked the bind before curl, not an observed dashboard response.
- The standard suite's 47.451 second test time remains below 60 seconds, but its dashboard coverage now depends on permission to bind loopback sockets.
