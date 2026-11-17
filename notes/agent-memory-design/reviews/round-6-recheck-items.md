# Items to re-check (targeted re-check after the last fix, 2026-11-17)

Judge each item FIXED or NOT FIXED in the current skill folder, with file, line and a short quote, and a real checker run where the item is about the checker.

## Final review blocking items
B1. The firing-key rule refused an honest per-item key (an order id saved before the firing) and its message steered to a slot key that double-acts when a catch-up overlaps. Expected: an `item id` key part exists, satisfies the firing rule, goes to the reviewer; `run id` stays refused; SKILL.md, side-effects.md and steps/3-design.md agree.
B2. The record of actions could expire before a repeat arrives (kept 2 days, catch-up looks back 30). Expected: rule stated where expiry is set; checker fails when shorter with the same unit, lists the comparison otherwise.
B3. A3 (how runs start) never went to the reviewer. Expected: a reviewer question and a line in the step 5 judgment list.
B4. A store shown to the model could be filed as the Audit log unflagged. Expected: audit log and record of actions never go into a model call (stated), and those rows get a reviewer question.
B5 (ATK3b). Notes about past runs filed as Semantic memory with source `outside content` escaped the episodic question, and line 21 printed n/a. Expected: question asked, line 21 not n/a.

## Final review minor items
m1. An unconfirmed item "never decides whether the action happens" collided with the person's request for automatic actions decided by the model reading outside text (labels, a duplicate comment). Expected: an in-run model choice may drive an action the person asked to be automatic when code limits it to fixed choices named in the content check.
m2. Pick-up of unfinished actions had no guidance for an agent with no timer. Expected: an option such as at the start of each run.
m3. The lease length was arbitrary but had no place to be recorded. Expected: it is recorded in section 10.
m4. Standing cases for suggested procedures did not require "3 episodes from the same run do not count" or "one episode against stops the suggestion". Expected: required where procedures are learned.
m5. No required test that a statement of an owner-settable kind from an unverified or different sender stays unconfirmed (or is refused).
m6. episodic-memory.md said "the first five are the standing test" while the steps and checker required 3 and 2. Expected: consistent.
m7. steps/2-decide.md said the smallest agent has one test; the checker required two. Expected: consistent.
m8. Template lacked the `replace the old one` choice and the wake and catch-up numbers the checker requires.
m9. The example's section 10 lacked the episode copy-check length.
m10. Form kinds could be `user stated` without an allowed-values list. Expected: consistent with the checker.
m11. With the record of actions as the audit log, run-log cleanup removals had no audit place. Expected: settled.
m12. The reviewer question for an `event id` key part asked a stored-id question. Expected: its own question, including whether a redelivery and a catch-up produce the same id.
m13. Same as B5.
m14. Test names with spaces (Jest, RSpec) could not be written.
m15. With --project, a Python test existing only inside a docstring passed.
m16. The number 1 was exempt from section 10 everywhere (an approval lasting 1 year needed no line).
m17. `./tests/x.py` and `tests/x.py` counted as two tests.
m18. The line 21 n/a reason carried an unrelated clause.
m19. "One owner cannot see another's" was required even for a public source nobody owns.
m20. "Not found by its old wording" was required for searching an outside service the agent does not index.
m21. CHECKLIST.md said "planted in an email" where the rule is outside content.
m22. "webhook" and "header" were unexplained.

## Second real build (interview scheduler) items
e1. Unconfirmed content vs the core flow: an email built from availability read out of an email. Expected: the request asking a person to confirm is allowed, and the outside sender can be the confirmer when the design names them.
e2. Approval was only "whoever is signed in and pressed the button". Expected: an outside party's reply counts only if the sender matches the person on record, it carries a one-time code saved before the request was sent, and quoted text is stripped first.
e3. Quoted replies containing the confirm text. Expected: covered by e2's quoted-text rule and a required or suggested test.
e4. SKILL.md rule on keys for event or schedule starts contradicted the reference files (two confirm emails would make two keys). Expected: consistent.
e5. "Delete, then the same action again" could pass vacuously. Expected: the test re-creates the condition that starts the action after the delete.
e6. Layered guards hide each other in rule-removal checks. Expected: each guard needs a test that fails when only it is removed, or the design names them as one guard; prospective-memory.md no longer claims the task claim alone stops a double action.
e7. The run log's step limit had no test. Expected: a required case.
e8. Off-list owner values: refused or stored unconfirmed, the design says which.
e9. Self-set kinds were limited to harmless things. Expected: allowed when the person asked, with allowed values written down and the saved value read back to the owner.
e10. A constraint that only ends by replacement or by an event was pushed toward a set-time expiry. Expected: accepted.
e11. "If skipped once" had no value for a promised action that silently does not happen. Expected: `misses a promised action`, which must live in code.
e12. A read marker with a message that always fails blocked the reader forever. Expected: flag it and move the marker on, with a test.
e13. "(not told yet)" with nobody to tell. Expected: allowed only with how and when.
e14. "Unfinished actions are picked up by" allowed one value. Expected: one or more.
e15. Whether a confirm request carrying code-chosen values from unconfirmed input is fixed content. Expected: settled.
e16. Working memory and parametric defaults assumed a chat agent. Expected: conditional on that.
e17. Checker messages referred to checklist line numbers with no text. Expected: short text printed; the builder is told when to read CHECKLIST.md.
