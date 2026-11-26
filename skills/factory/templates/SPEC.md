# SPEC: <build id>

Section numbers here are referenced by GRAPH.yaml, RUBRIC.md and TESTPLAN.md. Keep them stable.

Words used: define each term once, in plain language.

## 1. Layout

Files and folders the build adds or changes. Each path has one owner in GRAPH.yaml.

## 2. Settings

Every setting, its default, where it may come from, and what happens when it is invalid.

## 3. Behavior, command by command

For each command or function:
- Usage line with every flag.
- What it does, in numbered steps.
- Output: exact stdout and files written.
- Errors: each bad input, empty input, missing file and non-terminal case, with its exit code and its message.

## 4. Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | the command ran and the answer is "no" |
| 2 | bad usage or bad input |
| 3 | a needed file or folder is missing |
| 4 | the input is empty or has nothing usable |

## 5. Data formats

Schemas with an example line each.

## 6. Compatibility

What stays the same. Version bump decision.

## 7. Docs impact

Which files change and why.

## 8. Risks

The top 3, each with a mitigation.
