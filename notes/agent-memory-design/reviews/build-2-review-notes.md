# Step 5 review of the interview scheduler (frozen skill copy), 2026-11-17

Result on the BUILT AGENT: 11 yes, 3 n/a, 10 no. Not passed. The review step found real bugs the builder missed:
- "Sorry, I can't confirm IV-XXXXXX yet" books the interview (confirm matched by containing a word).
- A card number with its expiry date is saved and sent (secret pattern gap).
- One recruiter's confirmation can book another candidate's proposal (a filter no test covered).
- A reminder is lost when a stuck task comes back inside another run's lease (held treated as done).
- Opening a case is not logged as a run; the timer job is promised but nothing calls it.
- An inactive interviewer's preferences are never cleaned up (event-only expiry with no backstop).
- The model's reading of an interviewer's free text is saved as `user stated`, confirmed.
- 31 of 137 clause-level rule removals were not caught by the builder's tests (14 change behavior).

Skill-level causes to fix (candidates for the last small fix, after the targeted re-check returns):
S1. Source of a value the model extracts from the owner's own free text: say it is `agent worked out` and unconfirmed until the owner confirms the read-back. Cross-check A6 against rows that enter confirmed.
S2. A confirmation by reply is matched exactly (the code and a fixed form), never by containing a word; negations and quotes cannot count.
S3. A claim held by another run never closes a task as done; the task stays open and retries.
S4. Rule removal is per clause of the Rule cell, not per procedure; a removal another check already covers is counted only if behavior changes.
S5. Event-only expiry (`asked` or `told`) needs a date backstop or a reviewer question, like replaced-only rows.
S6. "Crash after the approval" applies to actions waiting for approval, not only tasks.
S7. Review step: tests/review needs __init__.py for unittest; the builder never deletes reviewer tests; step 8 lists the tests/review condition; line 31 says key lookups that block repeats keep old keys; line 24 says whether screen actions are runs and what counts as "something wakes the app" in a library; line 37 says each numbered limit gets a case; person rules are judged against the design text.
