# Memory design: <fill: name of the agent>

> Written by Claude with the agent-memory-design skill. Claude builds from this file and a separate reviewer checks it. Delete these note lines when the file is filled. Keep the headings, the table headings and the start of each dash line exactly as they are: `scripts/check_design.py` reads them and reports every line it does not recognise.
> Where a cell or a line holds one of a few fixed values, it starts with that value, and a note may follow after a comma or a full stop. Leave out sections 5 to 8 when they do not apply, and delete any dash line marked "only if". The checker says what it expects.

## 1. About the agent
- A1 What the agent is for: <fill: one sentence> (<fill: worked out, asked or assumed>)
- A2 Agents and users: <fill: one agent or several agents>. <fill: who uses it: one person, many separate people, teams> (<fill: worked out, asked or assumed>)
- A3 How runs start, and how long work lasts: <fill: a person, a schedule or an event, several joined by semicolons>. <fill: one conversation or across days> (<fill: worked out, asked or assumed>)
- A4 Actions with side effects: <fill: none or yes>. <fill: which actions, and which cannot be undone> (<fill: worked out, asked or assumed>)
- A5 Outcome signal: <fill: yes or no>. <fill: how the agent knows a run went well, or why it cannot> (<fill: worked out, asked or assumed>)
- A6 What it reads that nobody checked: <fill: emails, web pages, files, tool results> (<fill: worked out, asked or assumed>)
- A7 What goes wrong if it forgets or misremembers: <fill: the failures the tests must try to cause> (<fill: worked out, asked or assumed>)
- A8 Model, and what it cannot know: <fill: model name; private, recent or exact things> (<fill: worked out, asked or assumed>)

## 2. Memory types
| Memory type | Decision | Reason |
|---|---|---|
| Working memory | build | <fill: reason about this agent> |
| Procedural memory | build | <fill: reason about this agent> |
| Semantic memory | <fill: build or skip> | <fill: reason about this agent> |
| Episodic memory | <fill: build or skip> | <fill: reason about this agent> |
| External memory and retrieval | <fill: build or skip> | <fill: reason about this agent> |
| Prospective memory | <fill: build or skip> | <fill: reason about this agent> |

## 3. What is saved
| Item | Memory type | Owner | Scope | Expiry | Source | Enters as | Size limit |
|---|---|---|---|---|---|---|---|
| Run log | Run log | <fill: who it belongs to> | <fill: who may read it. Never shown to the model> | <fill: number and unit> after the run | system record: the app | confirmed | <fill: number> steps per run, then stop the run |
| <fill: kind of item> | <fill: a memory type, Audit log, or Side effect protection> | <fill: who it belongs to> | <fill: where it may be used> | <fill: one of the four expiry forms> | <fill: user stated, agent worked out, outside content, or system record: a trusted system> | <fill: confirmed or unconfirmed> | <fill: number and what, then refuse, retire the oldest, replace the old one, stop the run or shorten> |
- Run log holds content: <fill: yes or no>
- Trusted systems: <fill: only if a row says system record with a system other than the app. Names separated by semicolons>
- Kinds an owner can set for themselves: <fill: only if a row is user stated. Each as: exact item name (allowed: values, else refused or else unconfirmed), separated by semicolons>
- Kinds that hold a list: <fill: only if a new item of some kind is added beside the old ones. Exact item names>
- Who may confirm an unconfirmed item: <fill: only if a row enters as unconfirmed. A role and a screen, or no one: why>
- Expired rows are removed by: <fill: only if anything besides the run log is saved. Procedure names from section 4, joined by semicolons>
- Audit log kept in: <fill: only if the record of actions taken is the one thing saved besides the run log and its kept history is the audit log. Then: the record of actions taken>

## 4. Procedures
| Procedure | Rule | If skipped once | Lives in | Where | Guards | Test |
|---|---|---|---|---|---|---|
| <fill: a short name, used everywhere else in this file> | <fill: person: or design:, then the rule in one sentence, saying exactly what it catches> | <fill: harmless, costs money, sends something out, cannot be undone, leaks data, corrupts memory or misses a promised action> | <fill: code or instructions> | <fill: file and function, or part of the instructions> | <fill: action names from section 5, or none> | <fill: test name in file, or none for instructions> |
- Episodes before a procedure is suggested: <fill: only if section 3 has a Procedural memory row. A number of episodes, like 3 episodes, or none: why>
- What wakes the app: <fill: only if A3 names a schedule or an event, or prospective memory is build. The timer job, queue or listener, and how often it runs>
- Missed firings are caught up by: <fill: only if A3 names a schedule or an event. A procedure name from this table>

## 5. Actions with side effects
| Action | Can be undone | Idempotency key | Key parts | Needs approval | Content it carries | Guarded by |
|---|---|---|---|---|---|---|
| <fill: action> | <fill: yes or no> | <fill: like task-{task_id}-send> | <fill: each part in braces and where it comes from: stored id, step name, scheduled time, event id or item id, like task_id: stored id> | <fill: yes or no> | <fill: none, fixed or templated, outside content or agent worked out, several joined by semicolons> | <fill: procedure names from section 4> |
- Repeats are stopped by: <fill: the procedure every action passes through>
- Actions taken are recorded in: <fill: exact item name from section 3. A draft waiting for approval is a row there too>
- Unfinished actions are picked up by: <fill: the stuck task job, a job over the actions record, or a person. Several joined by semicolons>
- Content checked before sending by: <fill: only if an action carries outside content or agent worked out and needs no approval. A procedure name from section 4>
- Approval is checked by: <fill: only if an action needs approval. The procedure that checks it>
- Approvals are saved in: <fill: only if an action needs approval. Exact item name from section 3>
- Who may approve: <fill: only if an action needs approval. A role, or a person outside the system who replies with a one-time code>
- An approval lasts: <fill: only if an action needs approval. Number and unit, until the scheduled time plus number and unit, or when an event happens, told or asked>
- A claimed action is held for: <fill: number and unit, longer than one action can take>

## 6. Retrieval
| What it looks for | Where it lives | Method | Filters | Checks on results |
|---|---|---|---|---|
| <fill: thing> | <fill: where it lives> | <fill: exact lookup, filtered query, keyword search, embedding search, no search or new items> | <fill: this user, this team, this time period, or none when every user may see the whole source> | <fill: right thing, current version, allowed to see it> |
- Retrieval test set: <fill: only if a row uses keyword search or embedding search. Where the questions with known right answers live>
- Settings a person keeps current: <fill: only if a row reads a setting a person keeps that changes over time, where a stale value would cause a wrong action. The row's exact name: checked by a procedure name from section 4>

## 7. Future tasks
| Task | Trigger | Holds | Checks again on waking | Statuses |
|---|---|---|---|---|
| <fill: task> | <fill: time, event or condition, then the detail> | <fill: what to do, ids needed to carry on, approval needed or not> | <fill: what it looks at before acting> | <fill: pending, running, done and any others> |
- A running task goes back to pending after: <fill: number and unit>

## 8. Who can read and write
| Agent | Store | Read | Write |
|---|---|---|---|
| <fill: agent> | <fill: exact item name from section 3> | <fill: yes or no> | <fill: yes or no> |

## 9. Tests
| Test | Where |
|---|---|
| Every run is logged | <fill: test names in file, one per case> |
| <fill: each standing test the checker says this design needs> | <fill: test names in file, one per case> |

## 10. Open questions and arbitrary numbers
- <fill: each assumed answer, starting with its number and ending (told) or (not told yet: how and when), like A5 assumed: no outcome signal. (not told yet: in the build summary)>
- <fill: every number in an expiry, a size limit, an approval lifetime, the stuck task time, the lease on a claimed action, the episode count, how often the app is woken or how far the catch-up looks back, with the word that follows it, like 30 days, and whether the person chose it or it is a starting value>
