# Memory design: Leafline support email agent

> A filled example. The shop, the people and the numbers are made up. See `reference/example-email-agent.md` for the story behind it.
> File, function and test names are the planned places, as they would be written before the build.

## 1. About the agent
- A1 What the agent is for: Drafts replies to customer emails about orders, for staff to approve and send. (worked out)
- A2 Agents and users: one agent. One shop, two support staff, many customers. (worked out)
- A3 How runs start, and how long work lasts: an event; a person. A customer's email arriving starts a run, and staff approving a draft starts one. Work goes on across days: it follows up when a customer does not reply. (worked out)
- A4 Actions with side effects: yes. Sending an email, which cannot be undone. A refund function exists in the project and the agent must not use it. (asked)
- A5 Outcome signal: yes. Staff approve the draft as written, edit it, or reject it. (asked)
- A6 What it reads that nobody checked: Customer emails. (worked out)
- A7 What goes wrong if it forgets or misremembers: Forgets: re-asks for an order number, drops a follow-up. Misremembers: honours a promise nobody made, writes in the wrong language, quotes an old policy, emails a customer twice. (worked out)
- A8 Model, and what it cannot know: The hosted model named in the project's settings file. It cannot know orders, shipping status, the current policy, or anything a customer said before. (worked out)

## 2. Memory types
| Memory type | Decision | Reason |
|---|---|---|
| Working memory | build | Each reply needs the email, the order, the policy and the customer's facts in one call, and long threads must be trimmed |
| Procedural memory | build | Sending must wait for staff approval and refunds are off limits, whatever the model is asked |
| Semantic memory | build | A customer's language and the shop's tone are needed again on every later email |
| Episodic memory | build | Staff edits are an outcome signal, and late delivery and wrong item cases come back every week |
| External memory and retrieval | build | Orders, shipping status and policy live in the shop's systems and change daily |
| Prospective memory | build | The follow-up on unanswered emails happens days later, when the model is not running |

## 3. What is saved
| Item | Memory type | Owner | Scope | Expiry | Source | Enters as | Size limit |
|---|---|---|---|---|---|---|---|
| Run log | Run log | The shop | Debugging and audits only. Read by staff and by the job that writes episodes, never put in a model call as it is | 30 days after the run | system record: the app | confirmed | 500 steps per run, then stop the run |
| Audit log | Audit log | The shop | The owner and staff only, never shown to the model | 24 months after the entry was written | system record: the app | confirmed | bounded by retention |
| Customer's reply language | Semantic memory | The customer | That customer's cases | replaced when the customer asks for another language; 12 months after their last email | user stated | confirmed | 50 current facts per customer across all kinds, then refuse |
| Shop tone and sign-off | Semantic memory | The shop | Every case | replaced when the owner changes it on the settings screen | user stated | confirmed | 1 value for the shop, then replace the old one |
| Claims a customer makes about what the shop owes them | Semantic memory | The shop | That customer's cases, shown to staff only until staff confirm one | when the case closes, told by the case screen | outside content | unconfirmed | same as Customer's reply language |
| Facts the model infers about a customer | Semantic memory | The customer | That customer's cases, shown to staff only until staff confirm one | 30 days after it was inferred | agent worked out | unconfirmed | same as Customer's reply language |
| Thread summaries | Working memory | The customer | That thread only, shown to the model as content to read | 12 months after the customer's last email | agent worked out | unconfirmed | 2,000 words per summary, then shorten |
| Episodes | Episodic memory | The shop | Cases of the same kind, shown to the model only as a note about a past case, with other customers' details left out | 18 months after it was written | agent worked out | unconfirmed | 200 per kind of problem, then retire the oldest |
| Suggested and learned procedures | Procedural memory | The shop | A suggestion is shown to the owner only. One she approved is loaded with the instructions, with a version number | when the owner rejects it or switches it off, told by the approve screen | agent worked out | unconfirmed | 20 live learned procedures, then refuse |
| Follow-up tasks | Prospective memory | The shop | The one case it belongs to | 90 days after the task is closed | system record: the app | confirmed | 5 pending tasks per case, then refuse |
| Approvals | Side effect protection | The shop | The one exact email it was given for | 90 days after it stops counting | system record: the app | confirmed | bounded by retention |
| Actions taken | Side effect protection | The shop | Read by run_action() and the case screen only, never shown to the model. A reply waiting for staff is a row here with the status `waiting for approval` | 90 days after the action | system record: the app | confirmed | bounded by retention |
- Run log holds content: yes
- Kinds an owner can set for themselves: Customer's reply language (allowed: English, Spanish, French, else unconfirmed); Shop tone and sign-off (allowed: friendly or formal, and a sign-off of up to 40 characters, else refused)
- Kinds that hold a list: Claims a customer makes about what the shop owes them; Facts the model infers about a customer
- Who may confirm an unconfirmed item: support staff, on the case screen. The owner, for a suggested procedure. The customer, for a reply language read back to them, by the button in the reply
- Expired rows are removed by: Cleanup of expired rows

## 4. Procedures
| Procedure | Rule | If skipped once | Lives in | Where | Guards | Test |
|---|---|---|---|---|---|---|
| Friendly, short tone | design: replies are short and friendly, in the customer's language | harmless, a stiff reply that staff fix before sending | instructions | prompts/support.md, section Tone | none | none |
| Order looked up before drafting | design: the order named in the email is fetched before the model is called | harmless, a reply with no order facts that staff catch | code | build_context() in agent/context.py always fetches the order | none | test_order_is_in_the_call in tests/test_context.py |
| Fixed order and trimming of the model call | design: instructions first, then the email, the order, the policy, facts and one past case; older thread messages are summarized when the call is too long | harmless, a poor draft that staff catch | code | build_context() in agent/context.py | none | test_huge_thread_keeps_instructions in tests/test_context.py |
| No send without staff approval | person: no email goes out until a member of staff approves its exact text | sends something out, an email that cannot be taken back | code | check_approval() called by send_email() in agent/actions.py | Send a reply email; Send a follow-up email | test_send_refused_without_matching_approval in tests/test_actions.py |
| A send cannot happen twice | design: every send is claimed by its key in one transaction before the mail service is called | sends something out, the same email twice after a crash or a retry | code | run_action() in agent/actions.py, the one function every send passes through | Send a reply email; Send a follow-up email | test_one_key_one_send in tests/test_actions.py |
| No refunds by the agent | person: the agent never issues a refund | costs money | code | the tool list in agent/tools.py leaves the refund tool out | none | test_model_has_no_refund_tool in tests/test_tools.py |
| Fact entry rules | design: code sets each fact's source from how it arrived; claims from emails are saved unconfirmed | corrupts memory, a stranger's claim is treated as true in later replies | code | save_fact() in memory/facts.py sets the source and the status | none | test_email_claim_is_unconfirmed in tests/test_facts.py |
| Only the sender's own orders | design: an order is returned only when its email address matches the sender's | leaks data, a customer reads someone else's order | code | find_order() in memory/retrieval.py | none | test_other_customers_order_is_not_returned in tests/test_retrieval.py |
| Episode only after the outcome | design: an episode is written only after staff approve, edit or reject, and only when the run teaches something | corrupts memory, a run nobody checked teaches the next one | code | write_episode() in memory/episodes.py | none | test_no_episode_without_staff_decision in tests/test_episodes.py |
| A suggested procedure stays off until the owner approves | design: a suggestion is never loaded with the instructions until the owner approves it | corrupts memory, a rule nobody read changes every later reply | code | approve_procedure() in memory/procedures.py, and build_context() loads approved versions only | none | test_suggestion_absent_until_approved in tests/test_procedures.py |
| A task is claimed before it acts | design: a follow-up task moves from pending to running in one step before it does anything | sends something out, two firings of one task both draft a follow-up | code | on_wake() in agent/tasks.py | none | test_task_fired_twice_drafts_once in tests/test_tasks.py |
| Catch up on missed emails | design: when the app starts, every email that arrived while it was down, back 7 days, is handled like a new one | harmless, a late reply that staff see on the case screen | code | catch_up() in agent/inbox.py | none | test_missed_email_handled_once in tests/test_inbox.py |
| Cleanup of expired rows | design: expired rows are removed from every store each night, and each removal is written to the audit log | leaks data, content kept past the time the shop promised | code | cleanup() in memory/cleanup.py, run by the nightly timer job | none | test_cleanup_removes_and_audits in tests/test_cleanup.py |
- Episodes before a procedure is suggested: 3 episodes
- What wakes the app: a timer job every minute that checks the tasks table and the inbox, and a nightly timer job for cleanup
- Missed firings are caught up by: Catch up on missed emails

## 5. Actions with side effects
| Action | Can be undone | Idempotency key | Key parts | Needs approval | Content it carries | Guarded by |
|---|---|---|---|---|---|---|
| Send a reply email | no | case-{case_id}-reply-{reply_number} | case_id: stored id; reply_number: stored id | yes | agent worked out | No send without staff approval; A send cannot happen twice |
| Send a follow-up email | no | task-{task_id}-send | task_id: stored id | yes | agent worked out | No send without staff approval; A send cannot happen twice |
- Repeats are stopped by: A send cannot happen twice
- Actions taken are recorded in: Actions taken
- Unfinished actions are picked up by: a job over the actions record
- Approval is checked by: No send without staff approval
- Approvals are saved in: Approvals
- Who may approve: support staff, signed in to the case screen
- An approval lasts: 24 hours
- A claimed action is held for: 15 minutes

## 6. Retrieval
| What it looks for | Where it lives | Method | Filters | Checks on results |
|---|---|---|---|---|
| The order | Shop order database | exact lookup | Order number from the email | The order's email address matches the sender |
| Shipping status | Carrier tracking | exact lookup | Tracking number from the order | Status time is from today |
| Policy for the problem | Six policy pages kept in the project | no search, all six pages are loaded every time | The version in force today | Older versions dropped by date |
| A similar past case | Episodes | embedding search | Same kind of problem, this shop, not expired | Other customers' details are not in the result |
| The customer's facts | Facts table | exact lookup | This customer, confirmed, not expired, not replaced | none beyond the filters |
- Retrieval test set: tests/retrieval_cases.json, scored by tests/score_retrieval.py

## 7. Future tasks
| Task | Trigger | Holds | Checks again on waking | Statuses |
|---|---|---|---|---|
| Follow up on an unanswered reply | time, 9am on the fourth working day after the reply was sent | Case id, what to draft, approval needed | Has the customer replied, was the case closed, what is the order's status now | pending, running, waiting for approval, done, cancelled, failed |
- A running task goes back to pending after: 10 minutes

## 9. Tests
| Test | Where |
|---|---|
| Every run is logged | test_run_is_logged in tests/test_run_log.py; test_old_log_entry_removed_by_cleanup in tests/test_run_log.py; test_run_stopped_at_step_limit in tests/test_run_log.py; test_repeated_email_logged_as_run in tests/test_run_log.py |
| Expired items never come back | test_expired_fact_and_episode_not_returned in tests/test_expiry.py; test_claims_gone_when_case_closes in tests/test_expiry.py |
| A repeat, a contradiction or two saves at once leave one current item | test_language_replaced_and_repeat_ignored in tests/test_facts.py; test_two_saves_at_once in tests/test_facts.py |
| Outside content stays unconfirmed and the model cannot set the source | test_email_claim_is_unconfirmed in tests/test_facts.py; test_model_cannot_claim_user_stated in tests/test_facts.py; test_language_off_the_list_is_unconfirmed in tests/test_facts.py; test_language_from_other_sender_unconfirmed in tests/test_facts.py; test_inexact_confirm_reply_confirms_nothing in tests/test_facts.py; test_actions_record_never_in_model_call in tests/test_context.py |
| Delete removes everywhere | test_delete_customer_everywhere in tests/test_delete.py |
| Secrets are never saved or sent out | test_card_number_refused_everywhere in tests/test_secrets.py; test_card_number_in_draft_not_sent in tests/test_secrets.py |
| One owner cannot see another's | test_customer_a_never_gets_b in tests/test_owners.py |
| Size limits hold, cleanup runs, and every write is in the audit log | test_write_is_audited in tests/test_limits.py; test_cleanup_removes_and_audits in tests/test_cleanup.py; test_fact_limit_refuses in tests/test_limits.py; test_long_summary_shortened in tests/test_limits.py; test_oldest_episode_retired in tests/test_limits.py; test_live_procedure_limit_refuses in tests/test_limits.py; test_pending_task_limit_refuses in tests/test_limits.py |
| Search finds the known answers and never an old or deleted version | score_retrieval in tests/score_retrieval.py; test_changed_fact_not_found_by_old_wording in tests/test_retrieval.py |
| An action happens exactly once | test_crash_after_send in tests/test_actions.py; test_crash_before_send in tests/test_actions.py; test_forgotten_key_looks_up_first in tests/test_actions.py; test_two_sends_at_once in tests/test_actions.py; test_same_email_delivered_twice_one_reply in tests/test_actions.py; test_delete_then_same_reply_not_sent in tests/test_actions.py; test_crash_after_staff_approval_sends_once in tests/test_actions.py |
| A wrong or expired approval is refused | test_send_refused_without_matching_approval in tests/test_actions.py; test_send_refused_after_approval_expires in tests/test_actions.py; test_send_refused_after_case_changed in tests/test_actions.py; test_approval_by_unnamed_person_refused in tests/test_actions.py |
| A task fired twice acts once and a stuck task runs again | test_task_fired_twice_drafts_once in tests/test_tasks.py; test_stuck_task_runs_again in tests/test_tasks.py; test_crash_after_approval_sends_once in tests/test_tasks.py; test_held_send_leaves_task_open in tests/test_tasks.py |
| An episode is written only after the outcome, only when it teaches, and carries no outside text | test_no_episode_without_staff_decision in tests/test_episodes.py; test_approved_as_written_saves_no_episode in tests/test_episodes.py; test_planted_sentence_not_in_episode in tests/test_episodes.py |
| A procedure is suggested only at the set count and is not live before approval | test_two_episodes_no_suggestion in tests/test_procedures.py; test_suggestion_absent_until_approved in tests/test_procedures.py; test_three_episodes_one_run_no_suggestion in tests/test_procedures.py; test_episode_against_stops_suggestion in tests/test_procedures.py |

## 10. Open questions and arbitrary numbers
- 12 months for customer facts and thread summaries was the owner's answer.
- 24 hours for an approval is a starting value. Nobody chose it. The owner should set it.
- 30 days for the run log, and 90 days, 18 months, 24 months and 30 days elsewhere, are starting values the owner has not confirmed.
- The catch-up looks back 7 days. That is a starting value. The episode copy check refuses 8 words in a row copied from the email, also a starting value.
- A procedure is suggested when 3 separate episodes carry the same lesson and none goes against it. The 3 is arbitrary.
- The size limits (50 current facts, 2,000 words, 500 steps, 200 per kind of problem, 20 live learned procedures, 5 pending tasks) are starting values.
- 10 minutes before a running task goes back to pending, and 15 minutes for which a claimed send is held, are starting values.
- "Fourth working day" for the follow-up is a guess. The owner said "if they do not reply" without a number.
