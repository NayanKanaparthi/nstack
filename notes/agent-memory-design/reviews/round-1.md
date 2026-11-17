# Review 1 of agent-memory-design v0.1 (2026-11-16)

Reviewer: a separate Claude that did not see the build. Verdict: NOT READY. 5 of 10 lines fail.

| Line | Result |
|---|---|
| R1 Followable (dry run on a meeting-notes agent) | FAIL: 14 guesses; passing the checker needed a false label and deleting two real stores |
| R2 Every checklist line is driven by an instruction | PASS |
| R3 Builds code and tests, not only notes | PASS |
| R4 Plain words | FAIL: 20+ terms used before being explained, or never explained |
| R5 No dashes, no buzzwords | PASS |
| R6 Consistency | FAIL: the example saves email content as confirmed; run log cannot exist when episodic memory is skipped; "3 successes" vs "3 corrections" |
| R7 Honesty about sources | FAIL: source tags do not name the source; "a person switches it on" tagged as from a source when it is our judgment |
| R8 Checker | FAIL: 12 wrong designs pass, 10 reasonable designs fail, crash on a non UTF-8 file |
| R9 Asks only what it cannot work out | PASS |
| R10 Loading and description | PASS |

## Failures, most serious first
1. The model can label a sentence from an email as "user stated", so it is saved as confirmed. Code must set the source, not the model.
2. Several decisions have no checklist line or required test: episode rule, procedure approval, approval tied to one action, look up before retry, two saves at once, one owner cannot see another's.
3. The run log is filed under episodic memory, so it cannot exist when episodic memory is skipped.
4. Idempotency keys and approvals are filed under prospective memory, so an agent that sends things but has no future tasks never reads them.
5. The checker treats a random idempotency key and a money rule left in instructions as warnings, and still prints "no problems found".
6. "3 successes" is undefined for a procedure that does not exist yet, and the example counts 3 corrections.
7. Episodes are model-written summaries marked as a trusted record, so email text can reach the model through them.
8. The design file cannot list stores under working memory or external memory.
9. A crash between claiming a task and sending leaves it stuck in "running" forever. The crash test cannot see this.
10. No honest value for an answer Claude had to assume.
11. No instruction for planning mode, when files cannot be written yet.
12. Checker bugs: encoding crash, angle brackets treated as blanks, only the first table read, non-English reasons rejected, hollow tests accepted.
13. A command in the review step does not run from the project folder.
14. The two example files disagree; 24 hours recorded as the owner's answer when nobody asked.
15. Source tags unnamed or overstated.
16. Plain-words list of unexplained terms.
17. Bugs in the code sketches.
18. Smaller items: list-valued facts, no field for who may approve, "no search" not allowed as a method.

Attack files and the dry run are in this folder (attacks/make.py regenerates the attacks).
