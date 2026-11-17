# Review 2 of agent-memory-design v0.1 (2026-11-16)

Reviewer: a fresh Claude that saw neither the build nor the fix. Verdict: NOT READY. R1, R2, R6, R8 fail; R4 and R7 fail narrowly. R3, R5, R9, R10 pass.

Of round 1's 18 failures: 12 fixed at the cause, 5 partly, 1 could not be checked.

## Blocking
1. A tiny agent does not get a tiny design. An agent that "saves nothing" is forced to keep a run log and an audit log and gets a 120 line design.
2. The checklist has no rule for lines that cannot apply (for example approval checks for an agent with no outside actions), so the review can never end.
3. The checker does not read everything: tables under an extra heading, duplicate row names, blanks left on some lines, and an audit log standing in for the run log all pass.
4. Required tests depend on a label. Filing facts under a different memory type removes their tests.
5. "system record" is defined loosely enough that a tool result from another app can be saved as confirmed.
6. The checker's word matching is fooled by rewording (19 wrong designs pass), rejects honest designs (12 fail), and "reviewed: any three words" waves a problem through with exit 0.
7. Decisions with no checklist line or test: the count of 3 episodes, search index kept in step on a change, a full store, a write appearing in the audit log.

## Major, not blocking
8. An approved action is lost if the app crashes between approval and sending.
9. No recovery after a crash for an agent that has outside actions but no future tasks.
10. Whether approving an exact action also confirms the record behind it is not said.
11. No source label fits a value the model extracted from outside text, or a value code computed from unconfirmed input.
12. Approval lifetime when the action is scheduled weeks ahead.
13. The reviewer sub-agent is not given SKILL.md, so the terms it must judge are undefined for it.
14-17. The examples contradict the reference files in four places.

## Minor
18. Two source tags claim more than the source says; several default bullets are untagged.
19-22. Sketch bugs, small checker bugs, a stale bytecode file, six unexplained terms.

The reviewer's dry runs and attack files are in reviewer/ in this folder.
