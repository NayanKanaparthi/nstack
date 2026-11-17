# Review 3 of agent-memory-design v0.1 (2026-11-16)

Reviewer: a fresh Claude that saw none of the build or fixes. Verdict: NOT READY, 3 blocking.
R3, R4, R5, R9, R10 pass. R1, R2, R6, R8 fail; R7 fails on one minor tag.

Round 2 blocking items: 1, 2, 3, 5, 6 fixed. 4 and 7 partly.

## Blocking
B1. A scheduled agent can act twice. "Every Friday, post a summary" is sent to prospective skip, the honest stable key (team + week) is refused, and a per-run key passes. A timer that fires twice makes two runs and two posts.
B2. Renaming episodes escapes the no-outcome-signal rule. Notes about past runs filed under Semantic memory pass with no reviewer item. (Same family as round 2 item 4: second appearance.)
B3. Agents whose only saved records are side effect records get no secrets, delete or audit-log tests, although those records can hold the full message text.

## Minor
M1 run log "short expiry" checked for form only. M2 two actions can share one key template. M3 "the model" accepted as approver. M4 suggested procedures allowed without episodes; episode count never required. M5 episodes built while the run log holds no content. M6 "a person" picks up unfinished actions when no person is involved. M7 number check matches bare digits. M8 false reason text on required tests. M9 no place for a draft waiting for approval when there is no future task. M10 what counts as several agents is unclear. M11 one source tag claims more than the source says. M12 approval sketch ignores the record version. M13 one test name accepted where three tests are required.

Reviewer's dry runs (C: HR handbook agent, D: weekly status poster, tiny rewriter) and attacks are in reviewer/.
