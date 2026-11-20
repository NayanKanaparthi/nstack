# What applies to every store, and the run log

Read this once in step 3, whichever memory types you are building. These are the pieces that are easy to leave out because they belong to no single memory type. Each one is something that goes wrong in ordinary use, not a rare case.

Sections 1 and 2 apply to every agent. Sections 5, 7, 8 and 10 (delete, size limits, the audit log, secrets) apply once the agent saves anything besides the run log, the records of side effects included. Sections 3, 4 and 6 apply to rows under a memory type. For side effect records, two runs at once is handled by the idempotency key (`reference/side-effects.md`). Section 9 applies when A2 says `several agents`.

## 1. Owner, scope, expiry and size limit on every row

Every saved item, in every store, has an owner, a scope, an expiry and a size limit. (video for owner, scope and expiry on facts; applying them to every store, and the size limit, are ours) A row with no owner cannot be filtered by permission. A row with no expiry lives forever and is eventually wrong.

**Owner when there are no accounts.** If the agent has no users it can tell apart, the owner is whoever runs the app. (ours)

**Expiry is written in one of five forms** (ours), and two can be joined with a semicolon:

- a set time after something: `90 days after the run`,
- an event, ending in `told` or `asked` (below): `when the order is delivered, told`,
- replacement: `replaced when the owner states a new one`,
- `permanent: <the reason>`. Most things that feel permanent are not.
- no end: `no end, checked by evidence`, for a fact nothing ends and people rely on (`reference/feedback-and-improvement.md`). It is not a row with no expiry: the fact is kept, and evidence, not a date, says how sure the agent can still be.

**How code acts on an expiry by event.** (ours) Save the name of the event and the id it is about, such as "order delivered" for order 4412. Then one of two ways, and the expiry says which, as its last word:

- `told`: the app is told when the event happens (it receives the delivery update). The code that handles the event stamps an end time on every item waiting for it, in the same step.
- `asked`: the app only finds out by asking. Then the read function asks (it looks up the order's status) before it returns the item.

Either way the item stops coming back from the read function the moment the event is true. An expiry no code can test, such as "when the customer changes their mind", is not an expiry. Give it a set time as well.

**Cleanup.** (ours) The read function is what keeps an expired item out. Separately, a procedure in code removes expired rows, so stores do not grow forever and deleted content is really gone. It runs on a timer, or at the start of each run when the agent has no timer, and each removal goes in the audit log when there is one. Removals from the run log are not audited. When anything besides the run log is saved, it is named on the section 3 line `Expired rows are removed by`. When the run log is the only store, its cleanup is tested under "Every run is logged".

## 2. The run log

Every agent keeps a run log: the record of the steps of every run, kept for a short time. This holds whatever you decided about episodic memory. (source: Konishi guide for a log of raw events kept for days to a few months; requiring it for every agent is ours)

- **What counts as a run.** (ours) Every start: a person's request, each firing of a schedule (a late one, a repeat and a catch-up too, even when it ends up doing nothing), each event, and each pick-up of an unfinished action or task.
- **What it holds.** (ours) Normally: the request, each call to a tool and what came back, errors, the final output, and the outcome when it arrives. For an agent that saves nothing else, it may hold only step names, sizes and errors, and none of the content. The design says which, on the line `Run log holds content: yes` or `no`.
- **Entries are added and never changed.** (ours) A log like that is called append only.
- **Secrets are removed before a step is logged,** by the same check the write functions use (section 10). (ours)
- **Nothing puts it into a model call.** (ours) It is for a person finding out what happened. One job may read it: the episode writer, if episodic memory is built, which turns a run into a short note under the rules in `reference/episodic-memory.md`.
- **It has a size limit and an expiry,** like any store. (ours) A limit on steps per run also stops a run that is going round in circles.
- **It is deleted with the owner's data** when a user asks for theirs to be removed, if it holds content. (ours)

In the design file the run log is the one row in section 3 with the memory type `Run log`. Its source is `system record: the app`.

## Starting values

Offer these when the person has no number in mind. Every one is ours. Each number you use goes in section 10 of the design with its source (`steps/3-design.md`, section 10).

| What | Starting value | Source |
|---|---|---|
| Run log | 30 days after the run, 500 steps per run | policy for the days; default for the steps (measure: runs stopped at the limit) |
| Audit log | 24 months after the entry was written | policy |
| Facts per owner | 50 | default (how often the limit is reached) |
| A fact the model inferred and nobody confirmed | 30 days after it was inferred | policy |
| Episodes | 18 months after writing, 200 per kind of task | policy for the months; default for the count |
| Live procedures learned from episodes | 20 | default (how often the limit is reached) |
| Closed tasks, approvals, records of actions | 90 days. The record of actions outlasts the catch-up and any redelivery or retry window | policy |
| Review age and cap of a fact with no end | 90 days, at most 1 year, for a preference. 180 days, at most 2 years, for a role or a standing fact. 30 days, at most 90 days, for the row that takes facts of no listed kind | default (the kind's correction rate, and its learned review age once measured) |
| The wait after a confirmation | 2 times longer | default (facts corrected soon after their wait was lengthened) |
| Prior for a source | 9 of 10 answers for `user stated` and `system record`, 5 of 10 answers for `agent worked out` and `outside content` | default (the kind's measured rate) |
| When a kind's own rate replaces the prior | its 95 percent interval is narrower than 20 points | default (kinds whose rate moves a lot after the switch) |
| Learned review age | the age by which 10 percent of the kind's facts were corrected | default (the share of facts corrected before their first review) |
| Alert on a kind's rate | a drop of 15 points between two runs of the job | default (alerts that fire with nothing wrong) |
| Seen with no correction counts after | 7 days | default (corrections that arrive after the window) |
| Optimizer budget | 150 metric calls a run | policy |
| Fewest examples the optimizer runs on | 20 | default (how much the score moves when one example is added) |
| A limit on an action (an amount, a number of recipients, a list of who it may reach) | none: ask | policy |
| Freshness window before a risky action | a third of the fact's review age | default (risky actions that had to wait for a confirmation, and corrections that arrive just after one went ahead) |
| How long a task waits for confirmation before it ends | 7 days | default (waits that ended with no answer, and answers that came after the wait had ended) |
| Time allowed for memory reads before the model call | the stated response time less what the model call needs, or 300 ms | requirement, or default (memory read time for the slowest 5%) |
| An alert line | none: pick from the first weeks of numbers | default (alerts that fire with nothing wrong, and failures no alert caught) |
| Counter roll-up | every 15 minutes | default (how far the counters lag the events) |
| Replaced versions move to cheaper storage | after 12 months | default (how often an old version is read) |
| Extra model calls per turn | at most 2 | default (turns that reach the cap) |
| How long a worker holds a job | 10 minutes, and always longer than the longest a job may take | default (jobs taken by a second worker while the first still runs) |
| Tries before a job is set to `failed` | 5 | default (jobs set to failed that a later try would have finished) |
| Writes kept in the spool while the store is down | 1,000 | default (writes dropped) |
| Numbers kept in the process while the store is down | 10,000 | default (numbers lost in an outage) |
| Time allowed for the quick check that the store is up | 100 ms | default (actions blocked while the store was up) |
| How old a model's reading can be and still count as saved wrong when the person's later words disagree | 14 days | default (the share of test set rows a person rejects on review) |

Which source the usual numbers have:

| Number | Source | The measure to name, for a default |
|---|---|---|
| How long anything is kept: every expiry of the form `<number> <unit> after` (run log, audit log, facts, episodes, summaries, closed tasks, approvals, records of actions) | policy | |
| How long an approval lasts | policy | |
| A time or a count the person's own request sets (when a follow-up goes out, how many reminders) | policy | |
| A number an outside system or a standard fixes (a provider's limit, a protocol's timeout). Not an expiry or an approval lifetime: those stay policy | requirement, written `[requirement: <the system> allows N = N]`, like `[requirement: the mail service allows 25 MB = 25 MB]` | |
| A size limit (facts per owner, episodes per kind, live procedures, pending tasks, words per summary) | default | how often the limit is reached |
| Steps per run in the run log | default | runs stopped at the limit |
| Episodes before a procedure is suggested | default | the share of suggested procedures the person rejects |
| How often the app is woken | default | how late a firing is handled |
| How far the catch-up looks back | default | firings found older than the look-back |
| How long a running task waits before it goes back to pending | default | tasks returned to pending while still running |
| How long a claimed action is held | default | actions taken over while the first run was still working |
| The episode copy check length, a count of tries, any other tuning value | default | name the measure |
| Review age and cap of a fact with no end | default | the kind's correction rate, and its learned review age once measured |
| The wait after a confirmation | default | facts corrected soon after their wait was lengthened |
| Prior for a source | default | the kind's measured rate |
| When a kind's own rate replaces the prior | default | kinds whose rate moves a lot after the switch |
| Learned review age | default | the share of facts corrected before their first review |
| Alert on a kind's rate | default | alerts that fire with nothing wrong |
| Seen with no correction counts after | default | corrections that arrive after the window |
| Optimizer budget | policy | |
| Fewest examples the optimizer runs on | default | how much the score moves when one example is added |
| A limit on an action (an amount, a number of recipients, a list of who it may reach) | policy | |
| Freshness window before a risky action | default | risky actions that had to wait for a confirmation, and corrections that arrive just after one went ahead |
| How long a task waits for confirmation before it ends | default | waits that ended with no answer, and answers that came after the wait had ended |
| Time allowed for memory reads before the model call | requirement when the person stated a response time, written like `[requirement: 2 seconds for the reply - 1.7 seconds for the model = 300 ms]`; default otherwise | memory read time for the slowest 5% |
| The number in an alert line | default | alerts that fire with nothing wrong, and failures no alert caught |
| How often counters are rolled up | default | how far the counters lag the events |
| When replaced versions move to cheaper storage | default | how often an old version is read |
| Extra model calls per turn | default | turns that reach the cap |
| How long a worker holds a job, tries before a job fails, the spool and the numbers kept in the process, the quick check of the store | default | as in the table above |
| How many candidates a reranker takes, and how many it keeps | default, or data once measured | questions whose right item the reranker moves down, or leaves out |
| A reranker's two counts from the retrieval test set (the right item in the wide pass, and in what reaches the model) | data, written like `[data: tests/score_retrieval.py on tests/retrieval_cases.json]` | |
| The expected volume (users, facts, runs) | requirement when the person stated it, written like `[requirement: 2,000 people x 10 runs a day = 20,000]`; data when measured from records | |
| How old a model's reading can be and still count as saved wrong | default | the share of test set rows a person rejects on review |

## 3. Repeats and contradictions

(ours) A new item that repeats an existing one stores nothing.

For a new item that differs, the design says which of two kinds it is:

- **A kind that holds one value** (a reply language, a time zone). The new one replaces the old one, once it is confirmed. The old one is kept as history and never shown to the model.
- **A kind that holds a list** (action items, things a customer has claimed). The new one is added beside the others.

Never store two values of a one-value kind as current: the model will pick one at random.

## 4. The search index stays in step

(ours) If a store has a search index (a second copy arranged for fast search, such as embeddings), every change and delete in the store reaches the index.

- If the index lives in the same database, change both in one transaction, which is a group of steps the database does all together or not at all.
- If the index is a separate product, write a row saying "this change is waiting for the index" in the same transaction as the change, and have a background job apply the waiting rows. The job is not optional: a change is not finished until its row is cleared.

A fact that was corrected in the table but not in the index keeps coming back in its old form.

## 5. Delete means everywhere

(ours) When a user deletes an item, or asks for all their data to be deleted, it goes from every place it lives:

- the table,
- a fact's old versions and, for a fact with no end, its fact events (`reference/feedback-and-improvement.md`),
- the search index,
- the run log,
- any episode that mentions it,
- summaries of old messages that include it,
- any temporary copy kept for speed (called a cache),
- the record of actions taken: what was sent and what is needed to redo it. Each action's key, status and times stay, for as long as the same action could be started again, so a repeat after the delete is still stopped (`reference/side-effects.md`).
- the spool and the set-aside file of `reference/production.md`: that owner's writes waiting there (and `drain_spool` skips a write whose owner was deleted). Job rows and measure rows hold ids and counts, not content.

Write one delete function per owner that knows every store, and add each new store to it when the store is built. The audit log keeps a record that a delete happened, without the deleted content.

## 6. Two runs at once

(ours) Two runs can try to write the same thing at the same moment: two messages from the same user, a background job and a live conversation. Without care, one write silently overwrites the other.

- Do the read, the check and the write of a save inside one transaction. Or keep a version number on the row and refuse a write that was based on an old version.
- For future tasks, taking a task out of `pending` is a single step that either happens fully or not at all (an atomic step), so two firings cannot both take it.
- For anything that must be one of a kind (one current value per owner and one-value kind, one row per idempotency key), put the rule in the database itself, where it is called a unique constraint: the database refuses a second row with the same value. A rule that lives only in the code can be beaten by two runs at once. For facts this is a partial unique index: a uniqueness rule over the current rows only, so the history can hold as many old versions as it needs.

## 7. Size limits

(ours) Every store has a limit: facts per owner, episodes per kind of task, live procedures, pending tasks per owner, steps per run in the run log. Without one, a store grows until retrieval gets slow and full of noise, and one misbehaving loop can fill it.

The design writes each limit as a number and what happens when it is reached: the write function refuses, retires the oldest, replaces the old one, stops the run, or shortens the text. A store that only ever grows until its expiry removes rows, such as an audit log, is written `bounded by retention`. Replacing an item does not count against the limit, because the number of current items stays the same.

## 8. An audit log

(ours) A record of every write, change, confirm, delete, approval and side effect: who or what did it, when, on which item. Reads of sensitive items too, if the agent handles any. It is how you answer "why did the agent do that" a month later. It never goes into a model call, and neither does the record of actions. Entries are added and never changed, and it does not hold the content of deleted items or any secret. The fact events of a fact with no end (`reference/feedback-and-improvement.md`) are not the audit log: the audit log says who changed memory, fact events say what was learned about a fact, and a correction writes to both.

It is built when the agent saves anything besides the run log, the records of side effects included. An agent whose only store is the run log has nothing to audit. The app's own code writes it.

When the only thing saved besides the run log is the record of actions taken, that record's history may be the audit log, so the agent keeps one table, not two. Then every change to an action row (claimed, sent, done, taken over, content removed by a delete, removed by cleanup) is kept as its own entry with who or what did it and when, and none is ever overwritten. The design says so on the section 3 line `Audit log kept in: the record of actions taken`, and has no `Audit log` row.

## 9. Several agents

(ours) If A2 says `several agents`, the design says which agent may read and which may write each store, one row per agent and store in section 8. Enforce it in the read and write functions, by the agent's identity as the app knows it, not by what an agent says about itself. A common safe shape: many agents may read confirmed facts, and only one may write them.

## 10. Secrets are never saved or sent out

(ours) Passwords, the keys that let code use an account or a paid service, card numbers, bank account numbers and government id numbers are refused by every write function, and removed before anything is written to the run log or the audit log. When an action carries outside content or model-written text, the same check runs on it before it is sent (`reference/side-effects.md`). Check on the way in with patterns for the common shapes. This is a floor, not a guarantee: tell the person that pattern checks miss things, and that the surest protection is not passing secrets through the agent at all.

## Tests that try to break these

Each group below is one standing test in section 9 of the design. `steps/3-design.md` says when each is needed.

- **Every run is logged.** Each case is its own test. (1) Run the agent once. The run log has the run. Build the next model call: nothing from the log is in it. If the design says the log holds no content, put an unusual sentence in the request and check it is nowhere in the log. (2) Write a log entry dated past its expiry, then run the cleanup the way the app runs it (its timer job, or the start of a run). The entry is gone. (3) Make a run reach the run log's size limit. It does what the design says, such as stopping. (4) When runs start on a schedule or an event: a firing that does nothing (a repeat, a catch-up with nothing to do) is in the log as a run.
- **Expired items never come back.** Save an item that expired yesterday and do not run cleanup. It does not come back. Save an item that expires on an event, make the event happen, and read without running cleanup. It does not come back. Do this for every read function of every store besides the run log, the records of side effects and the audit log included.
- **A repeat, a contradiction or two saves at once leave one current item.** Save the same item twice: one row. Save two different values of a one-value kind: one current value, and the old one in the history. Save two items of a list kind: both are current. Run two saves of the same kind at the same moment, many times: history is never lost and there is exactly one current item.
- **Delete removes everywhere.** Delete an owner's data, then look in every store, the index, the summaries and the logs for it. Nothing, except each action's key, status and times.
- **Secrets are never saved or sent out.** Save text containing a key or a card number, and run a step whose tool result contains one. Refused, and absent from the store, the run log and the audit log. When an action carries outside content or model-written text, a second test: put a key in that text and run the action. Nothing with the key is sent.
- **One owner cannot see another's.** Read and search as owner A for something only owner B has, where B's item matches every other condition the function applies. Nothing of B's comes back. Do the same for every job that works through rows by owner, such as a pick-up or a cleanup. With several agents, a second test: as agent B, write to a store only agent A may write. Refused.
- **Size limits hold, cleanup runs, and every write is in the audit log.** Each case is its own test. (1) Do a write, then read the audit log. The write is there. (2) Put an expired row in each store, run the procedure named on `Expired rows are removed by` the way the app runs it. The rows are gone and the removal is in the audit log. (3) For each store with a limit given as a number, its own test: fill it to its limit, then save one more. What the design says happens, happens. Replace an item in a full store. It works.

Also save an item with no owner, or no expiry, into each store. Refused. This belongs with the test of the write function's own procedure in section 4.

## In the design file

- Section 3: the `Run log` row and the line `Run log holds content`. An `Audit log` row when anything else is saved. An expiry and a size limit on every row. The line "Kinds that hold a list".
- Section 8: one row per agent and store, when A2 says `several agents`.
- Section 9: the standing tests above that this design needs.
- Section 10: every number, with its source.
