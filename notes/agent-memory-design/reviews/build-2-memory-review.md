# Memory review: interview scheduling agent

Reviewer: a separate Claude, started as a sub-agent. I did not see the design conversation or the build. Skill used: the frozen copy at `_review/round-5/skill-snapshot/` (Part B of `steps/5-review.md`, `CHECKLIST.md`, "Words these files use" in `SKILL.md`). Date: 2026-11-17.

## What I ran

1. **Checker.** From the project folder: `python3 -B <skill>/scripts/check_design.py MEMORY-DESIGN.md --project .` Result: "RESULT: no problems found." It printed 25 items for the reviewer (answered below) and three lines that cannot apply: 17, 21, 22.
2. **Tests.** The command on the first line of `_run/tests.txt`: `cd <project> && python3 -B -m unittest discover -s tests -v`. Before I added my tests: `Ran 65 tests ... OK`. After adding `tests/review/`: `Ran 83 tests ... FAILED (failures=7)`. The 65 builder tests all pass; the 7 failures are my attack tests, listed below.
3. **Rule removal, done again by me.** 137 removals, each in its own copy outside the project (`~/review-e2e2/rr/work/`), each run against the builder's 65 tests only (`tests/review/` left out of the copies). 106 were caught, 31 were not. Appendix A lists every one. I did not reuse `_run/rule_removal.py`.
4. **Attack tests.** 18 tests in `tests/review/test_review_attacks.py` (plus `tests/review/__init__.py` so `unittest discover` finds them). 11 pass, 7 fail. No other file in the project was changed.

## Result

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Every memory type is marked build or skip with a reason tied to this agent | yes | Section 2 decides all six. Each reason names this agent: one candidate email per call; booking only after the candidate confirms; interviewer preferences and each candidate's case surviving the days between emails; episodic skipped because nobody checks the reading of availability (A5); inbox, calendars and the applicant tracking system; the day-before reminder. |
| 2 | Everything saved has an owner, a scope, an expiry and a size limit | yes | The 9 rows of section 3 match the 9 tables in `db.py` SCHEMA (run_log, audit_log, cases, availability, preferences, inbox_marker, actions, confirmations, tasks). Nothing else is saved: no summaries, index or learned procedures. Owners are set by `candidate_owner()`, `interviewer_owner()` and `HIRING_TEAM`; expiries are `expires_at`, `replaced_at`, `closed_at` and the ATS `active` lookup. Wording note, not counted: the Actions taken scope says "read by run_action() and the recruiter's case screen only", but `open_holds()` (slot search), `open_booking_for_code()`, `current_booking()`, `unfinished()` and `get_action()` read it too. The `asked` expiry of Interviewer preference is acted on by reads but never by the cleanup (counted under 16). |
| 3 | Source set by code, outside text never confirmed except owner-settable kinds, system records by exact lookup | no | Interviewer preference enters as `user stated`, confirmed, but the stored value is the model's reading: `Agent.tell_preference()` sends the interviewer's free text through `build_context("read_preference")` and `self.model`, and `Store.save_preference()` saves whatever kind and value come back if they are on the allowed list. The design's own A6 lists "the model's reading of ... interviewers' preference messages" as something nobody checked; section 10 says of the misreading "Nobody has accepted this limit yet" and says "Anything else they write is refused on the screen", which no code enforces. `test_review_misread_preference_not_saved_as_confirmed` FAILS: "nothing after 10am" read as earliest start 10:00 is saved confirmed (`out["saved"] == [('earliest_start', '10:00')]`) and then decides slots and bookings, which cannot be undone. Under the skill's words a value the model inferred is `agent worked out`. The rest holds: `save_availability()` hard-codes outside content / unconfirmed (`test_email_availability_is_unconfirmed`, `test_model_cannot_set_source`; removal 45 caught); `Store.open_case()` copies the case from `ats.candidate()` by exact id; no model-written text enters a model call; `test_review_candidate_email_cannot_set_interviewer_preference` passes. |
| 4 | Every procedure says what happens if skipped once; anything but harmless lives in code | no | "Model reads, does not decide" is `instructions`, `harmless, a poorer reading that code checks`. On the preference path the only code check is the allowed-values list, so if the model does not "leave out anything you are unsure of", a wrong value enters memory as confirmed and decides interview times: that is `corrupts memory`, not harmless. Same evidence as line 3. Every other procedure marked harmless lives in code. |
| 5 | Every outside action listed with key parts, approval, content and guards | yes | The only call that changes another app is `service.perform(...)` in `run_action()` (`actions.py`), used for the outbox (proposal, reminder) and the calendar (invite); `test_only_run_action_calls_services` passes; `llm.call_model()` only reads. All three are in section 5. `msg-{message_id}-propose` uses the inbox message id (event id). `case-{case_id}-book-{proposal_id}`: both written by `write_proposal()` in one transaction before anything is sent. `task-{task_id}-remind-{c or i}-{id}`: the task row and its people list are written by `schedule_reminder()` inside the booking's `on_done` transaction, before `on_wake()` can run. No run id or random value is in any key (`Run.run_id` is log-only; confirm codes are not in keys). Proposal, invite and reminder text is built in `Agent.propose()`, `_booking_payload()` and `on_wake()` from ATS names, code-computed times and the code: `fixed or templated` is right. Only the invite needs approval; the proposal is the request to confirm and goes only to the candidate on record. Note: the secret part of `check_outgoing()` misses a card followed by its expiry (counted under 14). |
| 6 | No reliable outcome signal means episodic memory is skipped | yes | A5 is no and episodic is skip. The reason holds: the candidate's yes or no is about their own calendar and nobody reviews the agent's reading. No episode code exists. |
| 7 | Worked out / asked / assumed marked; assumptions and numbers in section 10 | yes | A1 to A7 worked out, A8 assumed; section 10: "A8 assumed: ... (not told yet)". Spot checks: A4's three actions match the three `run_action` call sites; A3's person / event / schedule match `tell_preference`/`open_case`/`recruiter_confirm`, `handle_message`, `timer_tick`. Every number in expiries, size limits, the approval lifetime, the stuck task time, the wake interval and the catch-up is in section 10 as a starting value nobody chose. I cannot see the conversation, so I took section 10 as the record of what the person was told. |
| 8 | Every run logged briefly, never in a model call; something wakes the app and catches up | no | (a) A3 says runs start with "a recruiter opening a case", but `Agent.open_case()` writes no run (only an audit line); `close_case`, `delete_case` and `change_interviewer` write none either. `test_review_opening_a_case_is_a_logged_run` FAILS. (b) Section 4: "What wakes the app: a timer job every 5 minutes that calls timer_tick()". Nothing in the project calls `timer_tick()` on a timer: no `__main__`, loop or cron line, and `config.TICK_EVERY` is defined and never used. `steps/4-build.md` layer 6 says to build it. Holds: one run log row, 14 days, `Run.step()` keeps only `_LOG_FIELDS` and stops at 200 steps (`test_run_stops_at_200_steps`), cleanup (`test_old_log_entry_removed_by_cleanup`), never read into a model call (`test_run_is_logged_without_content`), a tick that does nothing is a run (`test_tick_that_does_nothing_is_logged`). I read the log of a full run: ids, counts and sizes only. Catch-up: `poll_inbox()` and `due_tasks()` (`test_missed_emails_and_reminders_caught_up`). |
| 9 | Every code procedure tested, fails when removed; person rules present; each Rule catches what it says | no | Tests pass (65). My removals: 106 of 137 caught. Failing: (1) Interviewer limits promises "no slot starts before an interviewer's earliest start"; code enforces the model's reading of it, and section 10 says nobody accepted that limit. (2) Secrets refused promises any 13 to 19 digit Luhn card; `looks_like_secret()` misses "4111 1111 1111 1111 12/27" because the greedy `_CARD` match takes the trailing digits and then fails Luhn (`test_review_card_with_expiry_refused` FAILS). (3) Cleanup of expired rows promises "rows past their expiry from every store"; it never removes an inactive interviewer's preferences (`test_review_cleanup_removes_preferences_of_inactive_interviewer` FAILS). (4) Book only after the candidate confirms, in the person's meaning: "Sorry, I can't confirm IV-XXXXXX yet" books the interview (`test_review_negated_confirm_does_not_book` FAILS); `_CONFIRM` matches anywhere in the reply's own text, any case. (5) Rule clauses no builder test catches when removed (Appendix A): the word CONFIRM (15), "the calendar event still exists" (82), "every confirmed booking not yet made" (90), "after 5 tries becomes failed" (88), "received in the last 14 days" (93), the AKIA, PEM and password shapes (112 to 114), the audit-log scrub (110), the case filter in `current_booking()` (66), attendees in the fingerprint (4), "another case" including closed ones (38). Four of these now have passing reviewer tests that fail on the copy with the rule removed; they are mine, not the builder's. |
| 10 | Expired items never come back on read, every store, by date and by event | yes | `test_expired_items_not_returned` reads with no cleanup: `get_availability`, `latest_confirmation`, `due_tasks`, `tasks_for_case`, `open_holds`, `current_booking`, `get_preferences` (asked), `audit_entries`, `case_for_sender`, `get_case`. `test_closed_case_items_not_returned` covers the told event; `test_expired_proposal_frees_slot`. Each expiry filter removed: caught (11, 47, 50, 53, 56, 57, 60, 62 to 65, 67, 68), except where a stricter filter in the same function or the stamp written by `close_case()` already drops the row (19, 51, 61). Caveat: `get_action()` and `unfinished()` read the actions record with no `expires_at` filter; every caller uses such a row only to stop a repeat or is refused later (open_until, the 24-hour confirmation), so no expired item is acted on. `preference_history()` returns replaced rows by design and no app code calls it. |
| 11 | Repeat, contradiction, two saves at once: one current item and full history | yes | `test_same_email_twice_one_availability_set`, `test_new_availability_replaces_old`, `test_new_preference_replaces_old`, `test_two_preference_saves_at_once` (20 threads: one current row, every replaced row has `replaced_by`, every save audited). `DB.tx()` is BEGIN IMMEDIATE. Removals 28, 32, 49 caught. |
| 12 | Outside text stays unconfirmed; model cannot set the source; actions record never in a model call | yes | `test_model_cannot_set_source` (the model returns "user stated" / "confirmed" / another interviewer id; rows stay outside content and unconfirmed, the preference is saved for the signed-in interviewer only); `test_off_list_preference_is_not_current` (off-list is refused, stricter than stored unconfirmed). No action carries outside or model text, and `build_context()` takes only the one message. `test_review_other_candidate_code_and_address_never_reach_the_model` and `test_review_candidate_email_cannot_set_interviewer_preference` pass. The misread preference is counted under 3, 4 and 9. |
| 13 | Delete removes everywhere except action key, status and times | yes | `test_delete_candidate_everywhere` searches all 9 tables, logs included, for name, address, code, slot and title; candidate tables empty; action keys and statuses unchanged with payload and result NULL; a delete audit line. `test_delete_interviewer_preferences`. Removals 116 to 123 all caught. `test_review_booking_not_repeated_after_delete` passes. |
| 14 | Secrets never saved or sent | no | `test_review_card_with_expiry_refused` FAILS: an ATS record named "Pat 4111 1111 1111 1111 12/27" is saved in `cases` and `actions` and is sent in the proposal body; `looks_like_secret()` and `scrub()` both miss it (probe: "4111111111111111 12/25" and "5500 0000 0000 0004 06/27" are missed too). Removing the AKIA, PEM or password pattern, or the audit-log scrub, fails no builder test (110, 112 to 114). `test_secret_refused_by_every_store_and_logs` passes for an sk- key and a bare card. |
| 15 | One owner cannot see another's items through any read or job | no | Removing the case filter in `current_booking()` (`actions.py`) fails no builder test (removal 66). Without it `recruiter_confirm("R1", Dana's case)` approves and books whichever case has the newest open proposal; `test_review_recruiter_confirm_books_only_that_case` passes on the code as built and fails on that copy. The other owner filters are caught: `get_availability` (48), `get_preferences` (52), `case_for_recruiter` (58), `flagged_cases` (59), `open_booking_for_code` (18), `get_case` (135), `case_for_sender` (46). The owner comes from `case_for_sender()` on the sender address and from the signed-in id the screen passes; the model has no tools. Jobs: `test_jobs_by_owner_stay_with_owner`; `test_review_removed_interviewer_gets_no_reminder` passes. |
| 16 | Size limits in code; cleanup runs; every write and removal audited | no | (a) `Store.cleanup()` deletes preferences only when replaced more than 30 days ago. A current preference of an interviewer no longer active (section 3: expires "when the interviewer is no longer active ... asked") is never removed and has no date backstop. `test_review_cleanup_removes_preferences_of_inactive_interviewer` FAILS. Closed cases and their cancelled tasks are likewise kept until their date expiry, because `cleanup()` ignores `closed_at`. (b) `Store.set_marker()` (Inbox read marker, a section 3 row) and `Store.claim_task()` write without an audit line. `test_review_inbox_marker_write_is_audited` FAILS. Holds: `test_write_is_audited`; `test_cleanup_removes_and_audits` runs through `timer_tick()` and checks each removal is audited; limits tested for open cases, windows, proposals and run steps. "1 pending reminder per case" and "1 confirmation per proposal" had no builder test (removals 79, 133 not caught); `test_review_full_stores_do_what_the_design_says` shows both behave as section 3 says. |
| 17 | Search test set; changed or deleted item not found by old wording | n/a | Checker: "nothing is found by keyword search or embedding search". Confirmed: section 6 uses new items, exact lookup and filtered query; there is no search function in `scheduler_agent`. |
| 18 | No action happens twice and none is lost | no | `test_review_reminder_not_lost_when_stuck_task_returns_inside_a_lease` FAILS. With an outbox that takes 6 minutes a call, the process dies on the first interviewer's reminder (claimed 09:06, lease to 09:21). The 09:15 tick returns the stuck task; `run_action()` answers "held" (None) for that reminder; `on_wake()` treats it as sent and closes the task "done"; `unfinished()` never picks up `remind` actions. ana@co.example gets no reminder through 11:00. The builder's cases exist and pass: `test_crash_after_send`, `test_crash_before_send`, `test_unknown_result_looks_up_first`, `test_two_sends_at_once`, `test_late_second_firing_of_reminder`, `test_same_email_delivered_twice`, `test_delete_then_same_email_again`. My two-at-once, delete-repeat and crash-after-confirmation tests for proposals and invites pass. |
| 19 | Approval covers one exact action and runs out; wrong, expired, changed or unauthorised refused | yes | `test_wrong_confirmation_refused`, `test_expired_confirmation_refused` (25 hours), `test_case_changed_after_confirmation_refused` (changed and changed back), `test_confirmation_by_unnamed_person_refused`. Removals 0 to 3 and 5 to 8 caught. 24 hours and who may approve are in section 5. Confirmations hold `content_hash()`, not content. |
| 20 | A task fired twice acts once; a crashed task runs again; it looks again on waking | no | Same failure as line 18: a task that crashed after it was claimed runs again but closes as done with one reminder never sent. `test_task_fired_twice_sends_once` and `test_stuck_task_runs_again` pass; on waking `on_wake()` re-reads the case and the calendar event (cancelled, moved and started tests pass; "event still exists" is untested, counted under 9). |
| 21 | Episodes only after the outcome, only when they teach, no outside text | n/a | Checker: no Episodic memory row, no model-written row outside procedural memory, record of actions never in a model call. Confirmed: no episode table, function or job; actions never reach `build_context()`. Caveat: the preference value is model output (line 3), so the middle clause of the checker's reason is not literally true; nothing in this agent is a note about a past run, so I kept n/a. |
| 22 | Procedures suggested only at the set count, never live before approval | n/a | Checker: no Procedural memory row in section 3. Confirmed: no suggested or learned procedures and no switch. Same caveat as 21. |
| 23 | Nothing built for a skipped type or a part the agent does not have | yes | No episode or procedure tables or jobs; section 8 is left out and nothing multi-agent exists. Run log, audit log and side effect protection are built, as required. |
| 24 | A separate Claude checked every line after the last fix | no | Lines 3, 4, 8, 9, 14, 15, 16, 18 and 20 are no. I am a separate Claude, this pass covered all 24 lines, and my attack tests are in `tests/review/` and listed below. |

11 of the 24 are `yes`, 3 are `n/a`, 10 are `no`. The work has not passed.

## The 25 items the checker left for the reviewer

1. Scheduling case expires "when the recruiter closes or deletes the case, told by the case screen": yes, `Store.close_case()` stamps `closed_at` and `delete_owner()` removes it; every case read filters `closed_at`. The cleanup does not act on the stamp (line 16).
2. Scheduling case confirmed from the applicant tracking system: yes, `Store.open_case()` copies `ats.candidate(candidate_id)` by exact id, no model.
3. Interviewer preference expires "when the interviewer is no longer active ..., asked": reads ask (`get_preferences()` calls `ats.interviewer()`); the cleanup never does (line 16).
4. Interviewer preference as an owner-settable kind: the set of values is small and code checks the signed-in interviewer against the ATS, but it is not harmless if wrong (a wrong earliest start or cap sends proposals and invites at times the interviewer refused) and the value is the model's reading, not the owner's words. Line 3 and 4 `no`.
5. Inbox read marker "replaced when the next message is handled": `poll_inbox()` calls `set_marker()` after every message and the upsert only moves forward. One integer per inbox, no personal data. Its writes are not audited (line 16).
6. Reminder tasks expire "when the case is closed or deleted, told": `close_case()` sets them `cancelled`; `delete_owner()` deletes them; `due_tasks()` filters both.
7. Run log 14 days: acceptable for finding out what happened. A case can run a little longer (a proposal up to 14 days ahead, open for up to 72 hours), so the earliest runs of a long case may be gone before its reminder; it is a starting value and section 10 says so.
8. Run log holds no content: true. `Run.step()` keeps only `_LOG_FIELDS` and `scrub()`s; the log of a full run holds ids, counts and sizes only (`test_run_is_logged_without_content`).
9. Reminder tasks hold ids and what to do: case id, calendar event id, interview start, people as `candidate:<id>`/`interviewer:<id>`. Nothing from outside or the model. Never shown to the model.
10. Inbox read marker filed under External memory: it really is a read marker.
11. Person rules: from the design text (I cannot see the request) the six `person:` rows are there and in code. Two do not hold in the person's meaning: "Book only after the candidate confirms" (a negated reply books, line 9) and "Interviewer limits" (enforced against the model's reading, line 9).
12. Harmless in instructions: "Model reads, does not decide" is not harmless on the preference path (line 4).
13. No stored id made fresh by each run: true for every key (line 5).
14. Proposal key `msg-{message_id}-propose`: the message id comes from the inbox event and is the same on every redelivery (`test_same_email_delivered_twice`).
15. Proposal cannot be undone and needs no approval: intended. It is the request to confirm, sent only to the candidate's address on record, with templated text.
16. Proposal carries only fixed or templated content: true (`Agent.propose()`).
17. Invite key parts `case_id`, `proposal_id`: both stored by `write_proposal()` before the first try.
18. Invite carries only fixed or templated content: true (`_booking_payload()`: ATS name and emails, code-computed slot).
19. Reminder key parts `task_id`, `person_id`: stored by `schedule_reminder()` in the booking's transaction before the first try.
20. Reminder cannot be undone and needs no approval: intended; it follows a confirmed booking and re-checks the calendar on waking.
21. Reminder carries only fixed or templated content: true (`on_wake()`).
22. Who may approve: the candidate is matched on the sender address (spoofable on its own) plus the random 6-character code that was sent only to that address; the recruiter is the signed-in id checked by `case_for_recruiter()`. Never the model.
23. Settings a person keeps current: Interviewer busy times is listed and re-read at booking. Interviewer preferences are not listed, but `book_interview()` re-checks them through `slot_allowed()` (`test_changed_preference_blocks_booking`). Not counted.
24. A2 one agent: true. The only background job is `timer_tick()` in the same agent.
25. Every function that sends, pays, posts, deletes or changes another app is listed: true (line 5).

## Attack tests (`tests/review/test_review_attacks.py`)

| Test | Attacks | Result |
|---|---|---|
| `test_review_misread_preference_not_saved_as_confirmed` | outside / model content saved as confirmed (lines 3, 4, 9) | FAIL |
| `test_review_candidate_email_cannot_set_interviewer_preference` | a candidate email posing as an interviewer (lines 3, 12) | pass |
| `test_review_negated_confirm_does_not_book` | booking without a real confirmation (line 9) | FAIL |
| `test_review_two_ticks_at_once_one_proposal` | two timer runs handle the same email at once (line 18) | pass |
| `test_review_candidate_and_recruiter_confirm_at_once_one_invite` | candidate and recruiter confirm at once (line 18) | pass |
| `test_review_crash_after_confirmation_books_once` | crash between the saved confirmation and the booking (lines 18, 20) | pass |
| `test_review_booking_not_repeated_after_delete` | CONFIRM email redelivered after delete and reopen (line 18) | pass |
| `test_review_reminder_not_lost_when_stuck_task_returns_inside_a_lease` | slow outbox, crash mid-task, stuck task returned inside a lease (lines 18, 20) | FAIL |
| `test_review_removed_interviewer_gets_no_reminder` | reminder job after an interviewer is swapped out (line 15) | pass |
| `test_review_other_candidate_code_and_address_never_reach_the_model` | another candidate's data in the model call (lines 12, 15) | pass |
| `test_review_card_with_expiry_refused` | card number followed by its expiry (lines 9, 14) | FAIL |
| `test_review_opening_a_case_is_a_logged_run` | a run start with no run log entry (line 8) | FAIL |
| `test_review_cleanup_removes_preferences_of_inactive_interviewer` | cleanup of an expiry by event, asked (lines 9, 16) | FAIL |
| `test_review_inbox_marker_write_is_audited` | a write with no audit line (line 16) | FAIL |
| `test_review_full_stores_do_what_the_design_says` | the two numbered limits the builder did not fill (line 16) | pass |
| `test_review_recruiter_confirm_books_only_that_case` | owner filter in `current_booking()` (lines 9, 15) | pass; fails on the copy with removal 66 |
| `test_review_code_without_confirm_word_does_not_book` | the word CONFIRM in the confirmation rule (line 9) | pass; fails on the copy with removal 15 |
| `test_review_reminder_skipped_when_event_deleted` | "the calendar event still exists" (line 9) | pass; fails on the copy with removal 82 |

## Rule removals the builder's tests did not catch, and how I counted them

Counted against a line (the clause is in a Rule cell, or is an owner filter, and removing it changes what happens on some input): 4, 15, 38, 66, 82, 88, 90, 93, 110, 112, 113, 114 (lines 9, 14, 15), and the two size limits 79, 133 (line 16).

Not counted, because another check in the same path already stops the same input, so behaviour does not change: 9 (`approve()` status; callers only pass waiting bookings and `_claim()` blocks the rest), 10 and 17 (`open_until` is checked in both `approve()` and `open_booking_for_code()`; no test covers the recruiter path through `approve()` alone), 13 (the quote-header stop: `>` lines are skipped and the proposal template cannot match the CONFIRM pattern), 19 (row expiry is looser than `open_until`), 25 (not in any Rule), 51 and 61 (`close_case()` already stamps availability and tasks), 54 (the dict built from rowid-ordered rows keeps the newest anyway), 55 (no unconfirmed preference can exist), 71 (callers filter those statuses), 80 and 81 (no code path re-books a booked case), 107 (the allowed list refuses first), 132 and 134 (the unique indexes back up code checks), 136 (not a rule).

## Other observations (not counted against a line)

- Two timer runs at once send one proposal, but the losing run hits an IntegrityError on the action key and flags the case "a message could not be handled" after the proposal went out.
- `NeedsAPerson` raised inside `on_wake()` is not caught; it ends that `timer_tick()` before cleanup. The next tick recovers.
- A planned or started proposal whose case was closed stays in that status and is picked up, as a no-op, on every tick until its 90-day expiry.
- The action lease and the stuck-task time are both 15 minutes, and no timeout is set on outbox or calendar calls; a call that outlives its lease can be sent again unless the real service honours keys.
- `recruiter_confirm()` on a proposal past its open window is refused only by `approve()`'s `open_until` check, which no test covers.

## Appendix A: every rule removal (copies under `~/review-e2e2/rr/work/`, builder tests only)

| # | Procedure | Removed | Result |
|---|---|---|---|
| 0 | Book only after the candidate confirms | check_approval() call removed from book_interview() | caught: test_book_refused_without_confirmation, test_case_changed_after_confirmation_refused, test_expired_confirmation_refused (+1 more) |
| 1 | Book only after the candidate confirms | 24-hour counts_until check removed | caught: test_expired_confirmation_refused |
| 2 | Book only after the candidate confirms | content fingerprint check removed | caught: test_wrong_confirmation_refused |
| 3 | Book only after the candidate confirms | case version check removed | caught: test_case_changed_after_confirmation_refused |
| 4 | Book only after the candidate confirms | attendees dropped from the fingerprint | **not caught** (65 ran, all passed) |
| 5 | Book only after the candidate confirms | slot (start, end) dropped from the fingerprint | caught: test_wrong_confirmation_refused |
| 6 | Book only after the candidate confirms | may_approve() check removed from approve() | caught: test_confirmation_by_unnamed_person_refused |
| 7 | Book only after the candidate confirms | candidate address check in may_approve() removed | caught: test_confirmation_by_unnamed_person_refused |
| 8 | Book only after the candidate confirms | recruiter check in may_approve() removed | caught: test_confirmation_by_unnamed_person_refused |
| 9 | Book only after the candidate confirms | waiting-for-approval status check in approve() removed | **not caught** (65 ran, all passed) |
| 10 | Book only after the candidate confirms | proposal open_until check in approve() removed | **not caught** (65 ran, all passed) |
| 11 | Read filters | expiry filter in latest_confirmation() removed | caught: test_expired_items_not_returned |
| 12 | Confirmation read from the candidate's own words | skipping '>' quoted lines removed | caught: test_quoted_proposal_is_not_a_confirmation |
| 13 | Confirmation read from the candidate's own words | stop at quote header removed | **not caught** (65 ran, all passed) |
| 14 | Confirmation read from the candidate's own words | own_text() bypassed entirely | caught: test_quoted_proposal_is_not_a_confirmation |
| 15 | Confirmation read from the candidate's own words | the word CONFIRM no longer required before the code | **not caught** (65 ran, all passed) |
| 16 | Confirmation read from the candidate's own words | code must match the proposal (open_booking_for_code) | caught: test_old_proposal_code_refused |
| 17 | Confirmation read from the candidate's own words | open_until check in open_booking_for_code removed | **not caught** (65 ran, all passed) |
| 18 | Read filters | case filter in open_booking_for_code removed | caught: test_candidate_a_never_gets_b |
| 19 | Read filters | row expiry filter in open_booking_for_code removed | **not caught** (65 ran, all passed) |
| 20 | Interviewer limits | earliest-start check removed | caught: test_changed_preference_blocks_booking, test_full_flow_end_to_end, test_no_slot_before_earliest_start |
| 21 | Interviewer limits | max-per-day check removed | caught: test_max_per_day_counts_calendar_and_open_proposals |
| 22 | Interviewer limits | open proposals not counted toward max per day | caught: test_max_per_day_counts_calendar_and_open_proposals |
| 23 | Interviewer limits | calendar interviews not counted toward max per day | caught: test_max_per_day_counts_calendar_and_open_proposals |
| 24 | Interviewer limits | slot recheck at booking removed | caught: test_changed_preference_blocks_booking, test_slot_taken_after_proposal_not_booked |
| 25 | Interviewer limits | inactive interviewer check in slot_allowed removed | **not caught** (65 ran, all passed) |
| 26 | Both interviewers free | calendar busy overlap check removed | caught: test_busy_interviewer_slot_skipped, test_no_slot_flags_recruiter_and_sends_nothing, test_slot_taken_after_proposal_not_booked |
| 27 | Both interviewers free | open-proposal hold overlap check removed | caught: test_open_proposal_holds_slot |
| 28 | Newest preference wins | old value not marked replaced | caught: test_cleanup_removes_and_audits, test_delete_interviewer_preferences, test_new_preference_replaces_old (+1 more) |
| 29 | Newest preference wins | allowed-values check removed | caught: test_model_cannot_set_source, test_off_list_preference_is_not_current |
| 30 | Newest preference wins | allowed-values check keeps only the kind | caught: test_off_list_preference_is_not_current |
| 31 | Newest preference wins | signed-in interviewer check removed | caught: test_model_cannot_set_source |
| 32 | Newest preference wins / Send once | BEGIN IMMEDIATE replaced by deferred BEGIN | caught: test_two_preference_saves_at_once, test_two_sends_at_once |
| 33 | Never share one candidate's details with another | check_outgoing() call removed from run_action() | caught: test_other_candidates_name_blocks_send, test_recipient_outside_case_refused, test_secret_refused_by_every_store_and_logs |
| 34 | Never share one candidate's details with another | recipient check removed | caught: test_recipient_outside_case_refused |
| 35 | Never share one candidate's details with another | other email check removed | caught: test_other_candidates_name_blocks_send |
| 36 | Never share one candidate's details with another | other name check removed | caught: test_other_candidates_name_blocks_send |
| 37 | Never share one candidate's details with another | other confirm code check removed | caught: test_other_candidates_name_blocks_send |
| 38 | Never share one candidate's details with another | other cases narrowed to open cases only | **not caught** (65 ran, all passed) |
| 39 | Secrets refused | secret check on outgoing content removed | caught: test_secret_refused_by_every_store_and_logs |
| 40 | One case per model call | escaping of material block tags removed | caught: test_planted_order_stays_in_material_block |
| 41 | One case per model call | cut to 6000 characters removed | caught: test_huge_email_keeps_instructions |
| 42 | Model output checked | time zone check removed | caught: test_bad_windows_dropped |
| 43 | Model output checked | end-after-start check removed | caught: test_bad_windows_dropped |
| 44 | Model output checked | past / beyond 14 days check removed | caught: test_bad_windows_dropped |
| 45 | Entry rules | availability saved as user stated / confirmed | caught: test_email_availability_is_unconfirmed, test_model_cannot_set_source |
| 46 | Sender matched to one case | exact address match removed | caught: test_bad_message_does_not_block_inbox, test_call_holds_one_case_only, test_candidate_a_never_gets_b (+8 more) |
| 47 | Read filters | closed/expired filter removed from case_for_sender | caught: test_closed_case_items_not_returned, test_expired_items_not_returned |
| 48 | Read filters | case filter in get_availability removed | caught: test_candidate_a_never_gets_b, test_expired_items_not_returned |
| 49 | Read filters | replaced filter in get_availability removed | caught: test_new_availability_replaces_old |
| 50 | Read filters | expiry filter in get_availability removed | caught: test_expired_items_not_returned |
| 51 | Read filters | closed/expired case filter in get_availability removed | **not caught** (65 ran, all passed) |
| 52 | Read filters | interviewer filter in get_preferences removed | caught: test_candidate_a_never_gets_b, test_model_cannot_set_source |
| 53 | Read filters | active (asked) check in get_preferences removed | caught: test_expired_items_not_returned |
| 54 | Read filters | replaced filter in get_preferences removed | **not caught** (65 ran, all passed) |
| 55 | Read filters | confirmed filter in get_preferences removed | **not caught** (65 ran, all passed) |
| 56 | Read filters | closed filter in the live-case condition removed | caught: test_closed_case_items_not_returned |
| 57 | Read filters | expiry filter in the live-case condition removed | caught: test_expired_items_not_returned |
| 58 | Read filters | recruiter check in case_for_recruiter removed | caught: test_candidate_a_never_gets_b |
| 59 | Read filters | recruiter filter in flagged_cases removed | caught: test_no_slot_flags_recruiter_and_sends_nothing |
| 60 | Read filters | task expiry filter in due_tasks removed | caught: test_expired_items_not_returned |
| 61 | Read filters | closed/expired case filter in due_tasks removed | **not caught** (65 ran, all passed) |
| 62 | Read filters | expiry filter in tasks_for_case removed | caught: test_expired_items_not_returned |
| 63 | Read filters | row expiry filter in open_holds removed | caught: test_expired_items_not_returned |
| 64 | Read filters | open_until filter in open_holds removed | caught: test_expired_proposal_frees_slot |
| 65 | Read filters | status filter in open_holds removed | caught: test_closed_case_items_not_returned, test_expired_items_not_returned |
| 66 | Read filters | case filter in current_booking removed | **not caught** (65 ran, all passed) |
| 67 | Read filters | expiry filter in current_booking removed | caught: test_expired_items_not_returned |
| 68 | Read filters | expiry filter in audit_entries removed | caught: test_expired_items_not_returned |
| 69 | Send once | lease (held) check removed | caught: test_two_sends_at_once |
| 70 | Send once | done check removed | caught: test_late_second_firing_of_reminder |
| 71 | Send once | blocked statuses can be taken over | **not caught** (65 ran, all passed) |
| 72 | Send once | look-up by reference before retry removed | caught: test_crash_after_send, test_unknown_result_looks_up_first |
| 73 | Send once | stop for a person removed (blind retry when the service cannot be asked) | caught: test_no_way_to_know_asks_a_person |
| 74 | Send once | repeat check in handle_message removed | caught: test_no_way_to_know_asks_a_person |
| 75 | Send once | status skip list in _send_proposal removed | caught: test_no_way_to_know_asks_a_person |
| 76 | Proposal limit | proposal count check removed | caught: test_fourth_proposal_refused |
| 77 | Day-before reminder | schedule_reminder() call removed from on_done | caught: test_booking_saves_reminder_task, test_cleanup_removes_and_audits, test_closed_case_items_not_returned (+9 more) |
| 78 | Day-before reminder | reminder due on the interview day instead of the day before | caught: test_booking_saves_reminder_task, test_full_flow_end_to_end, test_late_second_firing_of_reminder (+4 more) |
| 79 | Size limit: 1 pending reminder per case | old pending reminder not replaced | **not caught** (65 ran, all passed) |
| 80 | Reminder checks again on waking | case-still-booked check removed | **not caught** (65 ran, all passed) |
| 81 | Reminder checks again on waking | same-start check on the case removed | **not caught** (65 ran, all passed) |
| 82 | Reminder checks again on waking | event-exists check removed | **not caught** (65 ran, all passed) |
| 83 | Reminder checks again on waking | cancelled-event check removed | caught: test_reminder_skipped_when_event_cancelled |
| 84 | Reminder checks again on waking | moved-event check removed | caught: test_reminder_skipped_when_event_moved |
| 85 | Reminder checks again on waking | interview-started check removed | caught: test_reminder_skipped_after_interview_started |
| 86 | Task claimed before acting | pending-only condition in claim_task removed | caught: test_task_fired_twice_sends_once |
| 87 | Stuck tasks run again | return_stuck_tasks() does nothing | caught: test_stuck_task_runs_again |
| 88 | Stuck tasks run again | 5-tries-then-failed removed | **not caught** (65 ran, all passed) |
| 89 | Pick up unfinished actions | pick_up_unfinished() loop removed | caught: test_crash_after_send, test_crash_before_send, test_no_way_to_know_asks_a_person |
| 90 | Pick up unfinished actions | confirmed-but-not-booked part of unfinished() removed | **not caught** (65 ran, all passed) |
| 91 | Pick up unfinished actions | started/planned part of unfinished() removed | caught: test_crash_after_send, test_crash_before_send, test_no_way_to_know_asks_a_person |
| 92 | Catch up on missed firings | inbox catch-up limited to the last tick interval | caught: test_missed_emails_and_reminders_caught_up |
| 93 | Catch up on missed firings | 14-day look-back limit removed | **not caught** (65 ran, all passed) |
| 94 | Catch up on missed firings | reminder catch-up limited to the last tick interval | caught: test_missed_emails_and_reminders_caught_up, test_reminder_skipped_after_interview_started, test_stuck_task_runs_again |
| 95 | Cleanup of expired rows | cleanup() does nothing | caught: test_cleanup_removes_and_audits, test_old_log_entry_removed_by_cleanup |
| 96 | Cleanup of expired rows | removal not audited | caught: test_cleanup_removes_and_audits |
| 97 | Cleanup of expired rows | run_log not cleaned (direct expiry) | caught: test_cleanup_removes_and_audits, test_old_log_entry_removed_by_cleanup |
| 98 | Cleanup of expired rows | audit_log not cleaned (direct expiry) | caught: test_cleanup_removes_and_audits |
| 99 | Cleanup of expired rows | actions not cleaned (direct expiry) | caught: test_cleanup_removes_and_audits |
| 100 | Cleanup of expired rows | tasks not cleaned (direct expiry) | caught: test_cleanup_removes_and_audits |
| 101 | Cleanup of expired rows | confirmations not cleaned (direct expiry) | caught: test_cleanup_removes_and_audits |
| 102 | Cleanup of expired rows | availability not cleaned (direct expiry) | caught: test_cleanup_removes_and_audits |
| 103 | Cleanup of expired rows | expired cases not removed | caught: test_cleanup_removes_and_audits |
| 104 | Cleanup of expired rows | replaced preference history not removed | caught: test_cleanup_removes_and_audits |
| 105 | Secrets refused | refuse_secret removed from open_case | caught: test_secret_refused_by_every_store_and_logs |
| 106 | Secrets refused | refuse_secret removed from save_availability | caught: test_secret_refused_by_every_store_and_logs |
| 107 | Secrets refused | refuse_secret removed from save_preference | **not caught** (65 ran, all passed) |
| 108 | Secrets refused | refuse_secret removed from approve | caught: test_secret_refused_by_every_store_and_logs |
| 109 | Secrets refused | scrub removed from the run log | caught: test_secret_refused_by_every_store_and_logs |
| 110 | Secrets refused | scrub removed from the audit log | **not caught** (65 ran, all passed) |
| 111 | Secrets refused | sk- pattern removed | caught: test_secret_refused_by_every_store_and_logs |
| 112 | Secrets refused | AKIA pattern removed | **not caught** (65 ran, all passed) |
| 113 | Secrets refused | PEM header pattern removed | **not caught** (65 ran, all passed) |
| 114 | Secrets refused | password: pattern removed | **not caught** (65 ran, all passed) |
| 115 | Secrets refused | card number check removed from looks_like_secret | caught: test_secret_refused_by_every_store_and_logs |
| 116 | Delete a candidate or an interviewer | availability not deleted | caught: test_delete_candidate_everywhere |
| 117 | Delete a candidate or an interviewer | confirmations not deleted | caught: test_delete_candidate_everywhere |
| 118 | Delete a candidate or an interviewer | tasks not deleted | caught: test_delete_candidate_everywhere |
| 119 | Delete a candidate or an interviewer | action content not cleared | caught: test_delete_candidate_everywhere |
| 120 | Delete a candidate or an interviewer | case row not deleted | caught: test_delete_candidate_everywhere, test_delete_then_same_email_again, test_jobs_by_owner_stay_with_owner |
| 121 | Delete a candidate or an interviewer | interviewer preferences not deleted | caught: test_delete_interviewer_preferences |
| 122 | Delete a candidate or an interviewer | delete not audited | caught: test_delete_candidate_everywhere |
| 123 | Delete a candidate or an interviewer | action keys deleted instead of kept | caught: test_delete_candidate_everywhere, test_delete_then_same_email_again |
| 124 | Every write audited | audit() writes nothing | caught: test_cleanup_removes_and_audits, test_delete_candidate_everywhere, test_expired_items_not_returned (+2 more) |
| 125 | Every run logged | Run.step() writes nothing | caught: test_run_is_logged_without_content, test_run_stops_at_200_steps, test_task_fired_twice_sends_once (+1 more) |
| 126 | Every run logged | ids/sizes/codes whitelist removed | caught: test_run_is_logged_without_content |
| 127 | Every run logged (size limit) | 200-step stop removed | caught: test_run_stops_at_200_steps |
| 128 | No email when the agent cannot proceed | flag_for_recruiter() sets nothing | caught: test_bad_message_does_not_block_inbox, test_changed_preference_blocks_booking, test_fourth_proposal_refused (+5 more) |
| 129 | A bad message does not stop the inbox | the per-message catch removed | caught: test_bad_message_does_not_block_inbox, test_secret_refused_by_every_store_and_logs |
| 130 | Size limit: 20 windows per email | window count check removed | caught: test_too_many_windows_refused |
| 131 | Size limit: 1 open case per candidate | one_open_case unique index removed | caught: test_second_open_case_refused |
| 132 | Size limit: 1 pending reminder per case | one_live_reminder unique index removed | **not caught** (65 ran, all passed) |
| 133 | Size limit: 1 confirmation per proposal | repeat confirmation check in approve() removed | **not caught** (65 ran, all passed) |
| 134 | Size limit: 2 current values per interviewer | one_current_preference unique index removed | **not caught** (65 ran, all passed) |
| 135 | Read filters | case filter in get_case removed (owner filter used by every job) | caught: test_bad_message_does_not_block_inbox, test_candidate_a_never_gets_b, test_expired_items_not_returned (+3 more) |
| 136 | Reminder checks again on waking | task people list replaced by the case's current people | **not caught** (65 ran, all passed) |

11 of the 24 are `yes`, 3 are `n/a`, 10 are `no`. The work has not passed.
