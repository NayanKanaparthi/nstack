# factory: checklist

Written before the skill folder goes into this repo, from CONTRIBUTING.md. Every line is yes or no. A reviewer who never saw the work checks each one by reading the skill folder `skills/factory/` or by running the command shown.

Skill: factory. Version: 0.1.0.

## A. Skill folder (CONTRIBUTING: what every skill folder has)

1. Is the skill in one folder, `skills/factory/`?
2. Does `skills/factory/SKILL.md` exist?
3. Is the `name` in `SKILL.md` exactly `factory`, the same as the folder name?
4. Does `SKILL.md` have a `description`?
5. Is that `description` under 1024 characters?
6. Does the `description` say when to use the skill?
7. Does `skills/factory/README.md` exist?
8. Does the README say what the skill does?
9. Does the README say how to install it?
10. Does the README say how a run goes?
11. Does the README have a known limits section?
12. Does the README state the version, and is it 0.1.0?
13. Is everything the skill needs (templates, scripts, tests, example settings, process text) inside `skills/factory/`?
14. Does no file inside `skills/factory/` read or write anything outside its own folder, the project folder it is run in, or the Factory home folder (`$FACTORY_HOME`, else `~/.factory`)?

## B. Writing rules (CONTRIBUTING: writing rules)

15. Does `grep -rnP "\x{2014}" skills/factory notes/factory` (or a search for the em dash character) find nothing?
16. Is the text plain words, with no buzzwords (for example "seamless", "powerful", "robust", "leverage", "cutting-edge", "game-changing")?
17. Is each term that needs explaining explained with an example the first time it shows up?
18. Is every number that was picked by the author marked as picked, and does every claim from a source name the source?
19. Does the README claim nothing about the world that it does not back with something in the folder?
20. Does no text offer consulting, paid work or any service?

## C. Privacy

21. Does no file in `skills/factory/` or `notes/factory/` hold a private person name, company, client or employer name?
22. Does no file hold a personal path such as `/Users/<name>` or `/home/<name>`, an email address, a token, a key or an account detail?
23. Do the tests use synthetic fixtures only, with no real log, message or setting?
24. Does the privacy scan in the work tree (`--git-changed origin/main`) exit 0?

## D. Runs anywhere it says it does

25. Does every `.py` file compile with Python 3.9 (`python3.9 -m py_compile`, or `/usr/bin/python3 -m py_compile` where that is 3.9)?
26. Do the scripts import only the Python standard library?
27. Does the README say Python 3.9 or newer, standard library only, and list the other tools it needs?
28. Does the skill never change Claude Code configuration files, and does no script open one for writing?
29. Does no script delete a file or replace a file it did not create (`grep -rn "unlink\|rmtree\|os.remove" skills/factory/scripts` shows nothing that removes user files)?

## E. Commands match the text

30. Does `python3 skills/factory/scripts/factory.py --help` run, exit 0, and print the version 0.1.0?
31. For every command `SKILL.md` names (`init`, `new`, `phase`, `log`, `run`, `step`, `wait`, `gate`, `check`, `status`, `preflight`, `trace-report`, `report-card`), is it listed in that `--help` output?
32. For every command the README lists, is it in that `--help` output too?
33. Does `factory <command> --help` run for each of them and exit 0?
34. Does each flag `SKILL.md` shows in an example (for example `--build`, `--title`, `--stop`, `--adopt`, `--from-graph`, `--call`, `--input`, `--runner`, `--label`, `--non-private`) appear in the `--help` of its command?
35. Does every file `SKILL.md` and the README point to (`PROCESS.md`, `templates/`, `factory.example.json`, `machine.example.json`) exist?
36. Does a command with stdin closed print a plain error that starts with `factory:`, with no traceback, when given bad input?

## F. Tests

37. Do all tests run with one command from the skill folder, `python3 -m unittest discover -s tests -t .`?
38. Does that command exit 0 on a clean copy of the folder?
39. Do the tests never call a model or the network?
40. Do the tests run in under 60 seconds in total?

## G. Known limits

41. Does the README list known limits?
42. Does it say the kit was built and proven on one machine, running macOS?
43. Does it say the sleep check and the desktop notification are macOS only?
44. Does it say preflight cannot read remaining credit and sends a real one-line request instead?
45. Does it say an in-session sub-agent is on record only if the orchestrator logs it?
46. Does it say there is no dashboard and the board is `factory status`?

## H. Repo edits

47. Does the README skills table have one new row for factory, in alphabetical order, in the same voice as the other rows?
48. Does that row say what the skill does and when to use it, and offer no service?
49. Does the CHANGELOG have one new line for factory 0.1.0 under Unreleased, Added?
50. Do the README and CHANGELOG changes only add lines (`git diff` shows no removed line in either)?
51. Are the checklist and every review round saved in `notes/factory/`?
52. Is the branch cut from `origin/main`, and does `git diff --stat origin/main` show changes only in `skills/factory/`, `notes/factory/`, `README.md` and `CHANGELOG.md`?

## I. Review

53. Was the review done by an agent that saw only the skill folder and this checklist?
54. Did it run the skill on cases the builder did not try, and try to break it?
55. Does the last review round pass every line above?
