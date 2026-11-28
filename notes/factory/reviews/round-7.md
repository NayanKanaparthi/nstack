# Factory public skill review, round 7

Verdict: 55 of 55 checklist lines pass.

Scope: only the supplied `skills/factory/`, `CONTRIBUTING.md`, `CHANGELOG.md`, `notes/factory/`, and `evidence/maintainer-test-run.txt`. No external network, browser window, notification, or real model call. Commands set `FACTORY_OSASCRIPT_BIN=/usr/bin/true`.

| Line | Result | Evidence |
|---:|:---:|---|
| 1 | PASS | All 75 skill files are under `skills/factory/`. |
| 2 | PASS | `skills/factory/SKILL.md` exists. |
| 3 | PASS | Front matter says `name: factory`, matching the folder. |
| 4 | PASS | Front matter has a description. |
| 5 | PASS | The description is 310 characters. |
| 6 | PASS | It states when to use Factory and gives request examples. |
| 7 | PASS | `skills/factory/README.md` exists. |
| 8 | PASS | The opening and `What it does` explain the skill. |
| 9 | PASS | `Install` gives requirements and five setup steps. |
| 10 | PASS | `How a run goes` describes the run from preflight through finish. |
| 11 | PASS | `Known limits` is present. |
| 12 | PASS | README and command help both say 0.1.0. |
| 13 | PASS | Scripts, tests, templates, examples, process text, and dashboard assets are inside the skill folder. |
| 14 | PASS | Path and write-call audit confines writes to the project or Factory home; the dashboard has no write primitive and reads its own assets and Factory data. |
| 15 | PASS | Search found no em dash character in `skills/factory` or `notes/factory`. |
| 16 | PASS | The named buzzwords occur only in the checklist's prohibited-word examples. |
| 17 | PASS | Specialized user-facing terms are defined with examples at first use. |
| 18 | PASS | Dashboard refreshes, intro length, and port now say they are author picks; the process numbers likewise identify choices or user settings. |
| 19 | PASS | The model guide uses placeholders, labels untested examples, tells the reader to check installed lists and provider terms, and does not present a named model as verified. |
| 20 | PASS | No consulting, paid-work, or service offer was found. |
| 21 | PASS | No private person, client, employer, or private company name was found. The author credit is exactly the checklist's explicit exception. |
| 22 | PASS | No personal home path, email, token, key, or account detail was found. The one repository link is exactly the checklist's explicit exception. |
| 23 | PASS | Tests use toy builds, fake programs, and synthetic fixtures only. |
| 24 | PASS | The current dashboard-update record reports 0 hits in 0 files, 35 files and 13066 added lines scanned, exit 0. |
| 25 | PASS | Every Python file compiled with `/usr/bin/python3` 3.9.6. |
| 26 | PASS | Product Python imports only the standard library and the kit's own modules. |
| 27 | PASS | README requires Python 3.9+, says standard library only, names Git, and lists agent tools. |
| 28 | PASS | No product script writes Claude Code configuration; the contract test also covers this. |
| 29 | PASS | Product scripts contain none of the listed user-file deletion calls. |
| 30 | PASS | Root help exited 0 and printed `factory 0.1.0`. |
| 31 | PASS | Every command named by the checklist and SKILL appears in root help. |
| 32 | PASS | Every README command appears in root help, including `dashboard`, `finish`, `plain`, and `eval`. |
| 33 | PASS | Help exited 0 for all 17 root commands. |
| 34 | PASS | Documented example flags are present in their command help; passing documentation contract tests support the mapping. |
| 35 | PASS | `PROCESS.md`, `templates/`, and both settings examples exist. |
| 36 | PASS | Closed-stdin bad input produced a one-line `factory:` error, no traceback, and exit 2. |
| 37 | PASS | README gives the exact unittest command and clearly says real-browser checks are a separate optional runner not included in it. |
| 38 | PASS | This sandbox denied loopback binds, an environment limit rather than a defect. The supplied maintainer Mac run is therefore the result used: 176 tests, exit 0, one skip. |
| 39 | PASS | Static and test audit found fake runners only, no real model or internet use; dashboard tests use only `127.0.0.1`, and the browser runner blocks outside requests. |
| 40 | PASS | Maintainer run took 51.365 seconds, under 60. The sandbox run reached all 176 tests in 46.301 seconds before reporting only bind-policy failures. |
| 41 | PASS | README lists eight known limits. |
| 42 | PASS | Limit 2 says built and proven on one macOS machine. |
| 43 | PASS | Limit 3 says sleep and desktop notification checks are macOS only. |
| 44 | PASS | Limit 4 says preflight cannot read remaining credit and sends a real one-line request. |
| 45 | PASS | Limits 1 and 5 explain that an in-session sub-agent exists on record only when the orchestrator logs it. |
| 46 | PASS | Limit 6 says the dashboard is read-only and local, cannot answer decisions, and has the same board as `factory status`. |
| 47 | PASS | Round 5's in-folder review record checked one added, alphabetically placed Factory row; no supplied update changes that root row. |
| 48 | PASS | Round 5 checked that the row says what Factory does and when to use it, with no service offer. |
| 49 | PASS | Current CHANGELOG has one Factory 0.1.0 line under `Unreleased` / `Added`. |
| 50 | PASS | Round 5 records two added root-doc lines and zero removed; no supplied update changes that result. |
| 51 | PASS | The checklist and review rounds 1 through 7 are saved under `notes/factory/`. |
| 52 | PASS | Round 5 records `origin/main` as an ancestor and all changes in the four allowed locations; later supplied changes are confined to `skills/factory/` and `notes/factory/`. |
| 53 | PASS | This fresh reviewer used only the isolated review packet and never saw the build. |
| 54 | PASS | It ran the suite in isolation, compiled all Python, checked every help command, exercised closed-stdin and invalid-port errors, audited paths and privacy, and visually inspected every screenshot. |
| 55 | PASS | This round passes lines 1 through 54. |

## Open lines

None.

## Other findings

- Screenshot privacy: no private content is visible. The only person name is the expressly allowed author credit. The builds, times, labels, model names, and technical ids are plainly synthetic.
- Screenshot quality: `01` through `07` and `09` look coherent and support their captions. `08-finished.jpg` is broken as review evidence: the page is clipped at the top and its right-side elapsed-time text is cut off. It may be a scrolled or poorly framed capture rather than a dashboard defect, but it is misleading as a picture of the complete finished view and should be retaken.
- Environment limit: this sandbox denies binding `127.0.0.1`. The local run's bind-only failures were not counted as defects; the maintainer's supplied successful result was used as directed.

## Maintainer note

The maintainer opened `08-finished.jpg` at full size after this review: the whole page is in view (title, status, plan, footer, credit line), nothing is cut off. One real wording slip in that picture: a finished build still says "so far" after its running time. Recorded for a later fix.
