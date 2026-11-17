# Step 3: Write the design

You now fill the rest of `MEMORY-DESIGN.md`. The file is for you to build from in step 4 and for the reviewer to check in step 5. It has a fixed shape so a script can check that nothing is missing.

Where a decision needs judgment, the file makes you state it as one of a few fixed values. The script then holds you to the rule that follows from the value you chose. It does not try to read meaning out of your sentences, so choose the value honestly: the reviewer is shown every choice a script cannot verify.

## 1. Read the reference files you need

Read one file per memory type you marked `build`, when you get to that type. Do not read the files for types you marked `skip`.

| What | Reference file | Read it when |
|---|---|---|
| Applies to every store, and the run log | `reference/every-store.md` | Always |
| Working memory | `reference/working-memory.md` | Always |
| Procedural memory | `reference/procedural-memory.md` | Always |
| Parametric memory | `reference/parametric-memory.md` | Always (it is short) |
| Actions with side effects | `reference/side-effects.md` | A4 says `yes`, whatever you decided about prospective memory |
| Semantic memory | `reference/semantic-memory.md` | It is `build` |
| Episodic memory | `reference/episodic-memory.md` | It is `build` |
| External memory and retrieval | `reference/external-memory-and-retrieval.md` | It is `build` |
| Prospective memory | `reference/prospective-memory.md` | It is `build` |

`reference/example-email-agent.md` walks one agent through the whole thing, and `assets/example-memory-design.md` is its filled design file. Read them if you want to see what a finished design looks like.

Each reference file gives the questions to answer, the defaults to start from, the pieces of code the design must name, and the tests that try to break them. Answer the questions from the project. Use the defaults unless this agent gives you a reason not to, and when you change one, say why in section 10.

## 2. Fill the sections

Work through the template in order. Every blank is marked `<fill: ...>`. Sections 5 to 8 are left out when they do not apply: section 5 when A4 says `none`, section 6 when retrieval is `skip`, section 7 when prospective memory is `skip`, section 8 when A2 says `one agent`.

**Section 3, what is saved.** One row per kind of thing the agent saves: each kind of fact, summaries of old messages, episodes, suggested and learned procedures, future tasks, approvals, the record of actions taken, the run log and the audit log.

- **Memory type** is one of the six memory types that can be built, or `Run log`, `Audit log`, or `Side effect protection` (approvals and the record of actions taken).
- **Expiry** is one or more of four forms, joined by a semicolon:
  - `<number> <minutes, hours, days, working days, weeks, months or years> after <what>`, such as `90 days after the run`
  - `when <an event code can test>, told` or `, asked`, such as `when the case closes, told by the case screen`. `told`: the app is told when the event happens and stamps an end time. `asked`: the read function asks before it returns the item.
  - `replaced when <what>`, such as `replaced when the owner changes it`. A rule that ends only when replaced, or only on an event, needs no set time if something still removes it when nothing replaces it or the event never comes (the owner leaves). The reviewer is asked about each such row.
  - `permanent: <the reason>`. Most things that feel permanent are not.
  - The record of actions taken is kept longer than how far the catch-up looks back and longer than any window in which an event can be delivered again or a service retries, or a late repeat finds no key.
- **Source** is what code will set: `user stated`, `agent worked out`, `outside content`, or `system record: <a trusted system>`. Use `system record: the app` for the agent's own bookkeeping (logs, future tasks, approvals, actions taken, a marker of how far it has read a source). Any other system is named on the line "Trusted systems".
- **Enters as** follows from the source. `agent worked out` and `outside content` enter as `unconfirmed`. `user stated` and `system record` enter as `confirmed`.
- **Size limit** is `<number> <of what>, then <refuse | retire the oldest | replace the old one | stop the run | shorten>`, or `bounded by retention` for a store that only grows until its expiry removes rows, or `same as <another row's exact name>` when several kinds share one table and one limit.

The lines under the table, each one only when it applies:

- `Run log holds content: yes` or `no`. Always present.
- `Trusted systems:` when a row is a `system record` from something other than the app.
- `Kinds an owner can set for themselves:` when a row is `user stated`. Each is `<item> (allowed: <the values accepted>, else refused)`, or `else unconfirmed)`. A kind that matters (no interviews before 10:00) may be on it when the person asked for it. When the model reads the value out of the owner's words, code reads it back to them in their own terms ("no interviews before 10:00?"), and it counts only once they confirm that read-back.
- `Kinds that hold a list:` the kinds where a new item is added beside the old ones (action items, claims) instead of replacing the old one (a reply language).
- `Who may confirm an unconfirmed item:` when a row enters as unconfirmed. A role and where they do it. Write `no one: <why>` only when every unconfirmed row is something like a summary or an episode, which is only ever shown as content to read.
- `Expired rows are removed by:` when anything besides the run log is saved. The procedure in section 4 that removes expired rows, on a timer or at the start of each run.
- `Audit log kept in: the record of actions taken`, only when the record of actions taken is the one thing saved besides the run log and its history is kept as the audit log (`reference/every-store.md`, section 8). There is then no `Audit log` row.

**Section 4, procedures.** One row per rule.

- **Procedure** is a short name. Every other place in the file that points to the procedure uses this name, exactly.
- **Rule** is the rule in one sentence, starting with who asked for it: `person:` when the person stated it ("never post a password", "copy my manager on refunds"), `design:` when you added it. Every rule the person stated is a row here, in their meaning. Where the rule checks something, it says exactly what it catches.
- **If skipped once** starts with one of: `harmless`, `costs money`, `sends something out`, `cannot be undone`, `leaks data`, `corrupts memory`, `misses a promised action`. A note may follow after a comma. `misses a promised action` means something a person relies on silently does not happen (a reminder, a follow-up). `corrupts memory` means something false or unchecked gets saved, or gets shown to the model as true. `harmless` means the worst result is a poorer answer that stays inside the system.
- **Lives in** is `code` or `instructions`. Anything but `harmless` is `code`.
- **Guards** names the actions from section 5 this procedure protects, or `none`.
- Under the table, when section 3 has a Procedural memory row: `- Episodes before a procedure is suggested: 3 episodes`, or `none: <why>` when a person writes every procedure. A number needs episodic memory built.
- **Test** is the test that tries to break it: `<test name> in <file>`. Several are joined with a semicolon, and a note may follow in brackets. A name with spaces goes in double quotes. `none` for a procedure in instructions. Before the build, write the names you plan to use. After the build, the real ones.
- Under the table, when A3 names `a schedule` or `an event`, or prospective memory is `build`: `- What wakes the app: <the timer job, queue or listener, and how often it runs>`.
- Under the table, when A3 names `a schedule` or `an event`: `- Missed firings are caught up by: <a procedure name from this table>`. The app is sometimes down when a schedule fires or an event arrives. When it starts again, this procedure finds each firing it missed, back to a limit, and runs it like any other firing, so a key tied to the firing stops it if it did run after all. The procedure lives in code. How far back it looks is arbitrary and goes in section 10.

**Section 5, actions with side effects.** Every action from A4.

- **Idempotency key** is written with curly braces around each part that changes, such as `task-{task_id}-send`.
- **Key parts** says where each part in braces comes from: `task_id: stored id`. A `stored id` is saved in a table before the first try, so it is the same on every try. A `step name` is fixed text that names the step. A `scheduled time` is the time a trigger was set for, such as the 09:00 slot of 20 November, never the time the run began. An `event id` is the id the triggering event carries, such as an email's message id. An `item id` is the id of the thing acted on, saved before the firing by something other than the run, such as the order id the shop wrote when the order came in. Nothing else may go in a key: not the time a run started, not an id the run made for itself, not a random value, not a count of tries. Two actions never share a key.
- **Content it carries** is one or more of `none`, `fixed or templated`, `outside content`, `agent worked out`, joined by semicolons. `fixed or templated` is fixed text with only the app's own values filled in. Text the model wrote is `agent worked out`, even when it is built from outside content.
- **Guarded by** names the procedures from section 4 that guard it. Every action is guarded by the procedure that stops a repeat. An action that needs approval is also guarded by the procedure that checks the approval. An action that carries `outside content` or `agent worked out` and needs no approval is also guarded by each procedure on the line `Content checked before sending by` (one, or several joined by semicolons when the checks are split).
- The lines under the table name those two procedures, the rows in section 3 where approvals and actions taken are kept, who may approve, how long an approval lasts, who picks up an action that started and never finished (one or more, joined by semicolons), and how long a run holds an action it claimed before another run may take it over (`A claimed action is held for: 15 minutes`, longer than one action can take). How runs start is A3. A draft waiting for approval is a row in the record of actions taken, with the status `waiting for approval`, so it needs no row of its own.
- When A3 says runs start only on a schedule or an event and prospective memory is `skip`, nothing is written ahead for each firing, so every key has a part that is the same across firings for the same thing: a `scheduled time`, `event id` or `item id`. `reference/side-effects.md` says why.

**Section 6, retrieval.** One row per thing the agent looks for. Method is `exact lookup`, `filtered query` (exact values for several fields, such as one project and a date range), `keyword search`, `embedding search`, `no search` (the whole source is small and is loaded every time) or `new items` (everything that arrived since the last run, as when reading an inbox). Filters are `none` only when every user may see the whole source; a source holding items of different owners filters by owner. When a row reads a setting a person keeps that changes over time, and a stale value would make the agent do the wrong thing, add the line `- Settings a person keeps current: <the row's exact name>: checked by <a procedure name from section 4>`. A setting that does not change needs nothing beyond being read fresh.

**Section 7, future tasks.** One row per kind of task. Trigger starts with `time`, `event` or `condition`. Statuses include `pending`, `running` and `done`. What wakes the app is the line in section 4.

**Section 8, who can read and write.** One row per agent and store, naming rows from section 3.

**Section 9, tests.** The standing tests this design needs, each with its test names and file. A test is needed because of what is saved and done, so filing a row under a different memory type does not remove it. Each case is its own test, and the checker counts them. This table is the one list of the cases. The reference files say what each test does.

| Standing test | Needed when | Cases, one test each |
|---|---|---|
| Every run is logged | Always | A run is logged and nothing from the log reaches a model call. A log entry past its expiry is gone once the cleanup has run. A run that reaches the run log's size limit does what the design says. When A3 names a schedule or an event: a firing that does nothing is logged as a run |
| Expired items never come back | Section 3 saves anything besides the run log | An item past its date is not returned by any read function, without cleanup. When a row expires on an event: an item whose event has happened is not returned |
| A repeat, a contradiction or two saves at once leave one current item | Section 3 has a row under any memory type | A repeat and a contradiction leave one current item (a list kind adds to its list). Two saves started together lose nothing |
| Outside content stays unconfirmed and the model cannot set the source | A row has the source `user stated`, `outside content` or `agent worked out`, or an action carries `outside content` or `agent worked out` | For such a row: text from outside stays unconfirmed, and the model passing `user stated` is ignored. When a row is `user stated`: a value outside the allowed list is refused or unconfirmed, as the kinds line says, and the same statement from a sender the app has not checked, or from someone who may not speak for the owner, is refused or stays unconfirmed. When someone may confirm an unconfirmed item: an attempt to confirm that is not the exact confirm form (a reply with a negation or a quote, or one that only contains the code) confirms nothing. For such an action: the record of actions never reaches a model call |
| Delete removes everywhere | Section 3 saves anything besides the run log, or the run log holds content | After a delete, nothing of the owner's is in any store, index, summary or log, except each action's key, status and times |
| Secrets are never saved or sent out | Section 3 saves anything besides the run log, or the run log holds content | A secret is refused by every store, the run log and the audit log. When an action carries `outside content` or `agent worked out`: a secret in that text is not sent |
| One owner cannot see another's | Section 3 has a row under any memory type, or a section 6 row has filters, or A2 says `several agents` | Owner A never gets B's item, through every read function and every job that works by owner. With several agents: an agent writing a store it may not is refused |
| Size limits hold, cleanup runs, and every write is in the audit log | Section 3 saves anything besides the run log | A write is in the audit log. The cleanup removes expired rows and the removal is in the audit log. For each row besides the run log whose size limit is a number, its own test: a full store does what the design says (a limit of 1 that replaces the old one is the one-value case of the test above) |
| Search finds the known answers and never an old or deleted version | Section 6 uses keyword search or embedding search | The scored test set. When the searched store, or an index of it, is saved in section 3: a changed or deleted item is not found by its old wording |
| An action happens exactly once | Section 5 has a row | Crash after the action. Crash before the action. Unknown result. Two at the same moment. When A3 names a schedule: a late second firing. When A3 names an event: the same event again. When delete is needed: delete, make true again what starts the action, and start it again. When an action needs approval: crash after the approval, before the action |
| A wrong or expired approval is refused | An action needs approval | Wrong approval. Expired approval. Changed after approval. Not allowed to approve |
| A task fired twice acts once and a stuck task runs again | Section 7 has a row | Fire twice at once. Crash after the claim. When a task waits for approval: crash after the approval. When section 5 has an action: an action held by another run's claim leaves the task open, and it runs again |
| An episode is written only after the outcome, only when it teaches, and carries no outside text | Section 3 has an Episodic memory row. When it has none but the model writes other rows, or a Semantic memory row holds outside content, the reviewer decides whether one of them is notes about past runs | No outcome, no episode. An ordinary success writes nothing. A sentence planted in outside content is in no episode |
| A procedure is suggested only at the set count and is not live before approval | Section 3 has a Procedural memory row | One episode short of the count gives no suggestion. A suggestion is absent from the model call before approval and after switching off. When the count is a number: the set number of episodes from one run gives no suggestion, and one episode against the lesson stops the suggestion |

**Section 10, open questions and arbitrary numbers.** Every answer you marked `(assumed)`, starting with its number and ending `(told)` or `(not told yet: <how and when they will be told>)`. Anything else you guessed. Every number in an expiry, a size limit, an approval lifetime, the stuck task time, the lease on a claimed action, the count of episodes before a procedure is suggested, the line `What wakes the app` or the catch-up's Rule, written with the word that follows it in the design (`90 days`, `500 steps`), and whether the person chose it or it is a starting value. Any default you changed, any choice the person made to leave a type out, and the episode copy check length when episodic memory is built.

## 3. When the agent's main data comes in unconfirmed

Sometimes the thing the agent exists to handle arrives from a source nobody checked. An agent that pulls action items out of meeting notes is an example: the notes are a file and the model does the pulling, so every action item is `outside content` and enters as `unconfirmed`.

Three rules decide the source in cases that are easy to get wrong:

- **A value the model pulled out of outside text is `outside content`,** not `agent worked out`. The invoice total the model read off an invoice is the invoice's claim, not the model's idea.
- **A value the model read out of the owner's own words is `agent worked out`,** and unconfirmed until the owner confirms code's read-back of it, even for a kind they can set for themselves. "I can't do mornings" read as "no interviews before 12:00" is the model's reading, not theirs.
- **A value code computed from unconfirmed input is unconfirmed too.** "This invoice matches purchase order 88" is only as good as the invoice fields it was computed from. It carries the source of its least trusted input, and it becomes confirmed when those inputs are.

Code may do two things with an unconfirmed item: keep it, and show it to a person who may confirm it. It may not show it to the model as a fact, and it may not act on it: an unconfirmed item never decides who an action goes to, how much it pays, or whether it happens at all. No reminder, no payment and no email starts from an unconfirmed item. The one message that may be sent about it is the request asking a person to confirm it.

Passing text on is different from acting on it. An action may carry outside content or model-written text as its content (a summary of what came in, a quoted line) when section 5 says so, and then that content passes the check on the line `Content checked before sending by` before it goes out. What the action does and who it reaches still come from confirmed items and code. A choice the model makes during the run is not a saved item, and it may decide an action the person asked to happen with nobody checking each one (label each new issue, mark a duplicate) when code accepts only choices fixed in advance and named in the Rule of the content check (a label from a fixed list, an issue the run was handed) and refuses anything else. Section 5 then lists the action's content as `agent worked out`. Such a choice never picks who the action reaches or how much it pays, and it is not saved as a fact.

So the product needs a confirm step, and that is a decision for the person, not something to design around quietly. Tell them in chat, in plain words: "The agent will not act on what it reads until someone confirms it. Who should confirm, and where: a screen, a reply to a message?" Write the answer on "Who may confirm an unconfirmed item". It may be a person outside the system, such as a candidate who replies to an email, when the design names them. Their reply counts only when the sender matches the person on record, quoted text is stripped before it is read, and what is left is an exact form: the one-time code saved before the request was sent and one fixed word, on their own, or a button that carries the code. Containing the word or the code is not enough: "sorry, I can't confirm 4821 yet" and a "no" that quotes the request are never a yes.

If the request to confirm goes out as a message, that message is a side effect like any other. It is listed in section 5 with its own idempotency key, it goes only to the people who may confirm, and it shows the item as unconfirmed material to read. Values code chose for the request (a proposed time) may be in it.

**An approval can do the confirming.** When a person approves one exact action and the screen showed them the content the action is built from, that approval confirms that content for that action, and for nothing else. Staff who approve "pay 1,200 to Acme for invoice 77" have confirmed the amount and the supplier for that payment. The invoice record does not become a confirmed fact for later runs unless the design also has a separate confirm step. Say which it is in section 10.

## 4. Check your own design against the agent's failures

Go back to A7, what goes wrong if the agent forgets or misremembers. For each failure, point to the line in the design that stops it. If you cannot, the design has a hole. This is the part no script can do.

## 5. Run the checker

```
python3 -B <path to this skill>/scripts/check_design.py MEMORY-DESIGN.md
```

(`-B` stops Python from leaving a compiled copy of the script in the skill's folder.)

Fix what it reports and run it again until it reports no problems. Fix the design, not the wording: if it says a row from outside content is marked confirmed, the answer is to change how that item gets in, not to relabel the source. There is no way to mark a problem as accepted. If the only way to make it pass is to write something untrue or to leave out something the agent really saves, stop and tell the person what the checker could not express.

Then read the list it prints "for the reviewer to judge". These are the choices a script cannot verify: whether the outcome signal is real, whether a procedure you called harmless is, whether each key part really is stored before the first try. The reviewer will check each one against the code. Check them yourself first.

The checker only knows whether the file is complete and agrees with itself. A design can pass and still be wrong for the agent. It does not replace step 5.

## 6. Tell the person

In chat, in a few lines: what you will build, what you are skipping and why, anything you assumed, and the numbers you picked that are arbitrary (how many episodes before a procedure is suggested, how long logs are kept, how long an approval lasts). Do not send them to read the file. Then mark each assumed answer in section 10 `(told)`.

If they asked only for a design, or you may not write files yet, stop here until they say build. Otherwise read `steps/4-build.md`.
