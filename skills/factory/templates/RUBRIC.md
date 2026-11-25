# RUBRIC: <build id>

For the checker. It is never the maker's session. Judge each item PASS or FAIL with evidence: the command you ran and its output, or `file:line`. "I read the code and it looks right" is not evidence for an item that says run. Verdict per piece: `APPROVED`, or `REJECTED:` with numbered fixes, each naming the item.

Record the verdict with `factory log end <span_id> --verdict approved|rejected --rubric-pass R1,R2 --rubric-fail R3 --why "..."`.

## A. Every piece

| Id | Item | Evidence required |
|---|---|---|
| G-1 | The piece's own tests pass, and the fast suite is green. | Run the fast suite with `factory step tests.fast`. Paste the summary and the seconds. |
| G-2 | No locked test file was touched. | Compare the diff with `TESTLOCK`. Hashes match. |
| G-3 | The diff touches only files the piece owns in GRAPH.yaml. | The diff file list next to `owns_files`. |
| G-4 | Nothing existing was deleted or overwritten unless the plan says so. | The diff stat. |
| G-5 | Every error path in the piece's spec gives the stated exit code and a plain message with no traceback. | Run at least three error cases the tests do not cover. |
| G-6 | Behavior matches the spec where tests are silent. | Pick two statements no test covers and check them by running. |

## B. Piece specific

| Id | Piece | Item | Evidence required |
|---|---|---|---|
| C-1 | N1 | What this piece must additionally prove. | The command and its output. |

## C. Integration and release candidate

| Id | Item | Evidence required |
|---|---|---|
| I-1 | Every MUST criterion in GOALS.md is met, or the owner approved a change. | A table: criterion, tests, result. |
| I-2 | A review by a different vendor than the maker has no open blocker or major finding. | The review file. |
| I-3 | Nothing was merged, pushed or published before GATE B. | The git log and remote state. |
| I-4 | `factory check` on this build is clean, or each finding is explained. | The check output with its counts line. |
