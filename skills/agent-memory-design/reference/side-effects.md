# Actions with side effects

**In plain words:** a side effect is anything the agent does that changes the world outside the system. The system is the agent's own code and its own database. Sending an email, posting a message, paying a refund, changing a record in another app: all side effects. Writing a row in the agent's own table is not one.

Read this whenever A4 says `yes`. It does not depend on prospective memory. An agent that sends one approved reply per run, or posts a report on a schedule, and never saves a task for later still needs everything here.

Two things go wrong with side effects. The action happens when nobody agreed to it. Or it happens twice, because something crashed or retried in the middle.

Example: the app sends an email and crashes one second later, before it writes down "sent". It restarts, sees no record of sending, and sends again. The customer gets two emails. If it were a refund, they would be paid twice.

## Questions

- S1. Which actions reach outside the system? (From A4.)
- S2. Can each one be undone?
- S3. Does a person have to agree first? Who, and for how long does their yes count?
- S4. Does the outside service accept an idempotency key? Can it be asked whether an action already happened?
- S5. What stops the model from reaching the action without passing the checks?
- S6. If the app stops halfway through an action, what picks it up again?
- S7. What is the worst result of each action, and what are its limits: the most it may pay, who it may reach?
- S8. Is any tool open-ended, so that its effect depends on what the model passes it?
- S9. Which facts with no end decide who a risky action reaches, how much, or whether it happens?

## Defaults

- **Every outside action goes through one function.** Nothing else in the code calls the mail service or the payment service. That one function attaches the key, records the action, and stops a repeat. (ours)
- **The function claims the action before it acts.** In one transaction it inserts the action's row as `started`, with a lease: a time until which this run holds it. The key column is unique, so a second run that arrives at the same moment finds the row. If the row is `done`, it does nothing. If the row is `started` and the lease has not run out, another run is acting right now, so it does nothing either. Only when the lease has run out does it take the row over, and then it first looks up whether the action already happened (below). A run that finds the row held tells its caller the action was held, not done: a task or a job that started it stays open and runs again later, because the run holding it may have stopped. A check that only asks "is there a `done` row?" lets two runs that start together both send, because neither has finished. The lease is longer than one action can take. Its length is arbitrary, and it is written on the section 5 line `A claimed action is held for`. (ours)
- **Every action carries an idempotency key.** Idempotent means doing it twice has the same result as doing it once, like pressing an elevator button five times. The key is a label sent with the action so the receiving service can recognise a repeat and not do it again. A note saying "I got this far" is not enough, because it records what the app saw, not what happened in the world: the email can be out while the note was never written. (source: Let's Data Science write-up)
  - The key is built from parts that are the same on every try: fixed text, the name of the step, and ids that were saved before the first try, such as `task-207-send-followup`. Not a random value, not the time a run started, not a count of tries. It is saved, in the claimed row, before the action runs. (source: Let's Data Science write-up)
  - Two actions never share a key. The second would be taken for a repeat of the first and dropped. The step name in the key keeps them apart. (ours)
  - The key is sent with the action, and also as a reference the service keeps on the thing it made (a field on the payment, a header on the email, which is a hidden line of data the email carries), so the action can be found again later. (ours)
- **A trigger can fire twice, late, or not at all.** A scheduler fires the same slot again after a restart, or fires it late. A webhook delivers the same event again when the first answer was slow. And when the app was down, a firing is missed, so a catch-up runs it later (`steps/3-design.md`, section 4). Each firing starts its own run, so an id a run makes for itself, such as a run id, differs between the two and stops nothing. When a person starts the runs, ids saved before the first try are enough. When runs start on a schedule or an event and nothing is written ahead for each firing (no future task), the key carries a part tied to the firing: the `scheduled time`, which is the time the trigger was set for (the 09:00 slot of 20 November, whether the run began at 09:00 or at 09:40 after a restart), or the `event id`, the id the event carries (an email's message id), or the `item id`, the id of the thing acted on, saved before the firing by something other than the run (the order id the shop wrote when the order came in). Then an on-time run, a late run and a catch-up run about the same thing all make the same key, and only the first acts. With future tasks, the task row is written ahead and claimed before acting (`reference/prospective-memory.md`), and its id does the same job. (ours)
- **After a long gap or an unknown result, look before retrying.** Services forget idempotency keys after a while (one payment service keeps them about a day). When it is unclear whether an action happened, ask the outside service first, by the reference that was sent with the action, and retry only if it did not happen. (source: Let's Data Science write-up for looking up before a retry; finding it by a kept reference is ours)
- **If the outside service supports neither keys nor a way to ask what happened,** the app cannot be sure. Record the action as started before sending, and on an unknown result stop and ask a person. Do not guess. (ours)
- **A delete keeps the key.** When an owner's data is deleted, each action row loses its content (what was sent, what is needed to redo it) but keeps its key, its status and its times, for as long as the same action could be started again: a trigger could fire again, an event could be delivered again, or the service could see a retry. Otherwise a delete followed by a repeat of the trigger does the action a second time. (ours)
- **Something picks up an unfinished action.** A row in the record of actions that says `started` and never became `done` means the app stopped in the middle. The design says what picks it up, one or more of three: (ours)
  - `the stuck task job`, when the action was started by a future task. The task goes back to `pending` and runs again. See `reference/prospective-memory.md`.
  - `a job over the actions record`, when there is no future task. A timer job, or the start of each run when the agent has no timer, finds rows that have been `started` for longer than a set time and passes each one through the same function again. For this the row must hold what is needed to redo the action. A row that waits for a fact stays `started` and is tried again next time. A row the checks now refuse (a limit lowered since it was claimed) is held for a person. Either way the job goes on to the next row.
  - `a person`. The row is shown to someone who presses the button again. Acceptable when a person started the action in the first place.

  Going round again is safe in all three, because the key is the same.
- **A record change that calls for an action writes the action with it.** When committing a change to a record means an action must follow (a reply to send once a case is approved, a notice once a status changes), the action's row, or the task that will do it, is written in the same transaction as the change, the way a task is saved with its premise (`reference/prospective-memory.md`) and a job row with the record that needs it (`reference/production.md`). A crash between the change and the claim then leaves a row the pick-up finds, and the action happens once. (ours)
- **An approval covers one exact action.** It records the action, its exact content, the version of the record the approver saw, and when it stops counting. Before acting, the code checks the content still matches and the approval has not run out. If either fails, it asks again. (source: Let's Data Science write-up)
- **How long an approval lasts.** A set time, such as 24 hours. Or until an event code can test, written like an expiry by event: `when the conversation ends, told`. For an action approved now and done at a set time later (a payment approved today and paid on its due date), it lasts `until the scheduled time plus` a margin, and when the task wakes it checks again that the content is unchanged. The numbers are arbitrary and are the person's call. (ours)
- **Who approved comes from the app, not from the model.** The approver is whoever is signed in and pressed the button, or a person outside the system the design names, by a verified reply (`steps/3-design.md`, section 3: the sender, quoted text stripped, then exactly the one-time code and a fixed word, or a button). The design names who may approve. (ours)
- **An approval can confirm what it shows.** When the approver saw the content the action is built from, approving the action confirms that content for that one action. It does not turn the underlying record into a confirmed fact for later runs. See `steps/3-design.md`, section 3. (ours)
- **Every action has a guard in code.** A guard is the procedure that stands between the model and the action. For an action that needs approval, there are two: the check for the approval, and the one function above. For an action that needs no approval, the guard is the one function, plus any condition that must hold first (for example: a reminder is sent only for a confirmed item, and only to the person it is assigned to). An action is never unguarded. (ours)
- **The strongest guard is not giving the model the tool.** If the agent must never issue refunds, leave the refund tool out of its list. (ours)
- **Every tool has a risk label fixed in code.** The table of labels is keyed by the action's name and covers every action, whoever starts it: a tool the model calls, a task, a timer. Its values are the "if skipped once" values: `harmless`, `costs money`, `sends something out`, `cannot be undone`, `leaks data`, `corrupts memory`, `misses a promised action`. The label says what the action's worst result is. A tool that only reads is `harmless`. A tool with no label cannot be offered to the model: the app refuses to start. The design lists the label of each action on the section 5 line `Risk of each action`. A tool that is not in section 5 has no side effect, so its label is `harmless`. (ours)
- **The model never classifies its own action.** No argument the model fills in, and nothing it writes, changes the label. An action is risky when its label is anything but `harmless`. (ours)
- **Limits are the business's numbers.** A limit on an amount or on who is reached (the most a refund may be, the most recipients one message may have, the addresses it may go to) is a number, or a list kept in configuration, that the business sets, so its source is `policy`. Code enforces it inside the action's guard. A limit the person has not given yet is `[policy, not told yet]`, and the action it limits needs approval until they give it. (ours)
- **An open-ended tool gets its own check.** An open-ended tool is one whose effect depends on what the model passes it: run a command, call any address, run a query. One label cannot describe it. It gets its own check, a procedure in code that runs before the tool. Rules in code come first: commands known to be safe, and commands always refused. For what no rule covers, a separate check that did not write the command decides: a person, or a second model call that sees only the command. Anything no rule covers that the separate check is not sure about is risky. With no separate check, everything no rule covers is risky. A command judged risky runs only with an approval for that exact command in that one request, whether or not any fact is involved. The approval is found by the request's id, which the app saves before the first try and puts in the action's key, so one approval lets the command run once, and the tool's label in the table is never `harmless`. (ours)
- **A risky action rests only on fresh facts.** For each risky action the design names the facts with no end it rests on: the ones that decide who it reaches, how much, or whether it happens. Each such fact has a freshness window for that action, shorter than the fact's review age. Before the action, code checks that the fact was last confirmed within the window. If it was not, the action waits and the agent confirms the fact first, with the person who may confirm it. The request to confirm is the one message that may be sent about an unconfirmed item (`steps/3-design.md`, section 3). The check sits in `run_action`, the one function every side effect passes through, so an action a task or a timer starts is checked like one the model asks for. The request goes out through `run_action` too, with its own key made from the fact and when it was last confirmed, so a retry does not ask again. A task whose action waits is set to `waiting for confirmation`: it has not failed, the try is not counted, and the stuck-task job leaves it alone. The handler that records the person's answer to the request (`on_confirm_reply` in `reference/prospective-memory.md`) puts it back to `pending`, for a yes and for a correction alike, and it runs its checks again against the fact as it is now. With no answer, a timer job ends the wait after a set time, the design's `A wait for confirmation ends after`: the task is `failed` and a person is told. A disputed fact is never fresh. (ours)
- **What an action carries is stated, and outside or model-written text is checked before it goes out.** Section 5 says for each action one or more of: `none`; `fixed or templated` (fixed text with only the app's own values filled in, such as an id or a date); `outside content` (text read from outside and passed on, such as a quoted message); `agent worked out` (text the model wrote). The record of actions holds what its actions carry, and is never put in a model call. When an action carries `outside content` or `agent worked out` and no person approves each one, a procedure in code checks the content before it is sent. It is named on the line `Content checked before sending by` (several names joined by semicolons when the checks are split) and guards those actions. What it checks fits where the content goes. Always secrets, and who it reaches. Then whatever inside the content could act on its own once it arrives: in a message, for example, a mention that notifies people or a link; in a spreadsheet, a formula; in a field another system acts on, a command. Its Rule cell in section 4 says exactly what it catches. A rule that promises more than the code catches ("any number", "every secret") is a design error: write what the check really catches, and if the person accepts a limit, write it in section 10. With approval, the person sees the content, and the secret check still runs. (ours)
- **A request for approval or confirmation that goes out as a message is itself a side effect.** It gets its own key and goes only to the people who may approve or confirm. (ours)

## Code to build

- **An actions table.** One row per idempotency key: the key, status (`waiting for approval`, `started`, `done`), when it started, the result, and what is needed to redo the action if a job picks it up. A draft waiting for a person's approval is a row here with its draft. The table is read by `run_action` and the screens people use, and never put in a model call. Secrets are removed before a row is written, as for every store.
- **`run_action`.** The one function every outside action passes through.
- **An approvals table.** The action, the ids it is about, a fingerprint of the exact content (a hash, not the content itself), the version of the record the approver saw, who approved, when it runs out.
- **`approve` and `check_approval`.** Used by every action that needs approval.
- **The pick-up for unfinished actions,** as the design names it.
- **The tool list,** with any tool the agent must not have left out.
- **A risk table** keyed by tool name, and a check at start-up that every tool has an entry. **Limits** read from configuration, enforced in the one function every side effect passes through. **The check for an open-ended tool,** when there is one. **`facts_are_fresh`,** called from `run_action`, when a risky action rests on a fact with no end.

Sketch, to adapt:

```python
LEASE = timedelta(minutes=15)     # arbitrary: longer than one action can take
HELD = object()                   # what run_action returns when another run holds the action

def claim_action(key, payload, action=None):      # action: the action's name, kept on the row for a pick-up
    """One transaction (in SQLite: BEGIN IMMEDIATE). The key column is unique."""
    with db.transaction():
        row = db.action(key)
        if row is None:
            db.insert_action(key, payload, status="started", lease_until=now() + LEASE,
                         action=action)
            return "new", None
        if row.status == "done":
            return "done", row
        if row.status == "started" and row.lease_until > now():
            return "held", row                    # another run is acting right now
        db.update_action(key, status="started", lease_until=now() + LEASE, tries=row.tries + 1)
        return "taken over", row                  # an earlier try stopped, or an approved draft is going out

def run_action(key, service, payload, memory_ok, action=None, facts=()):
    """Every side effect goes through here, whoever started it. The key is the same on every try. memory_ok has no
    default, so a caller that leaves it out fails: a turn passes whether its memory reads arrived, and a run that made
    no reads before a model call, such as a timer job, passes memory_ok=True in words. action is the action's name in
    RISK, and facts are the facts with no end the design names for it."""
    guard_action(key, memory_ok)                  # only in a design with section 11: reference/production.md
    earlier = db.action(key)
    if earlier is not None and earlier.status == "done":
        return earlier.result                     # already happened: nothing to check, nothing to do
    if action is not None and is_risky(action):
        before_risky_action(action, payload, facts, now())   # limits, then fresh facts, before the claim
    state, row = claim_action(key, payload,
                              action=action)
    if state == "done":
        return row.result                         # already happened: do nothing
    if state == "held":
        return HELD                               # another run holds it: nothing done here, not done either
    if state == "taken over" and row.status == "started":   # an earlier try started and we never heard back
        if service.can_be_asked:
            found = service.find_by_reference(key)    # asks the service itself, not its memory of keys
            if found is not None:
                return db.finish_action(key, found)
        elif not service.still_remembers_key(row.started_at):
            db.hold_for_a_person(key)
            raise NeedsAPerson(key)               # cannot know: stop and ask, do not guess
    result = service.send(payload, idempotency_key=key, reference=key)
    return db.finish_action(key, result)

def approve(person, action, ids, draft, record_version, lasts_until):   # called by the approve button
    if not may_approve(person):                   # person is who the app says is signed in
        raise NotAllowed(person)
    db.insert_approval(action, ids, content_hash=hash_of(draft), record_version=record_version,
                       approved_by=person, expires_at=lasts_until)
    audit("approve", person, action, ids)

def check_approval(action, ids, draft, record_version):
    approval = db.latest_approval(action, ids)
    if approval is None or approval.expires_at <= now():
        raise NotApproved("no approval that still counts")
    if approval.content_hash != hash_of(draft):
        raise NotApproved("this is not the text that was approved")
    if approval.record_version != record_version:
        raise NotApproved("the record changed after it was approved")

def send_reply(case_id, reply_number, draft):
    case = db.case(case_id)
    check_approval("send_reply", {"case": case_id, "reply": reply_number}, draft, case.version)
    key = f"case-{case_id}-reply-{reply_number}"
    return run_action(key, mail_service, draft, memory_ok=True,   # a person pressed approve: no reads before a model call
                      action="send_reply", facts=facts_for("send_reply", case))

def run_for_slot(owner_id, slot):                # started by a timer; slot is the time the trigger was set for
    key = f"report-{owner_id}-{slot}-send"        # a late or second firing of the same slot makes the same key
    return run_action(key, mail_service, build_report(owner_id, slot), memory_ok=True,   # a timer job
                      action="send_report", facts=facts_for("send_report", owner_id))

def pick_up_unfinished(owner):                    # timer job, when the design says a job does this
    for row in db.actions(owner=owner, status="started", lease_ended_before=now()):
        try:
            run_action(row.key, service_for(row), row.payload, memory_ok=True,   # each pick-up is a run, logged as one
                       action=row.action, facts=facts_for(row.action, row))
        except WaitsForConfirmation:
            continue                              # this one waits for its fact; the other rows still go
        except (OverLimit, NeedsAPerson):         # refused now, such as a limit lowered since the claim
            db.hold_for_a_person(row.key)         # a person decides; the job goes on to the next row

def forget_owner_actions(owner):                  # part of the delete function in reference/every-store.md
    db.clear_action_content(owner)                # keeps key, status and times; drops payload and result

RISK = {"look_up_order": "harmless", "send_reply": "sends something out", "pay_refund": "costs money",
        "send_report": "sends something out", "send_follow_up": "sends something out",
        "run_report_command": "cannot be undone"}  # every action, whoever starts it; an open-ended one never harmless

class WaitsForConfirmation(Exception):           # the action waits; a task that started it waits too
    def __init__(self, action_name, fact_id):
        super().__init__(action_name, fact_id)
        self.fact_id = fact_id

def offer_tools(tools):                           # at start-up, before the model sees any tool
    for t in tools:
        if t.name not in RISK:
            raise NoRiskLabel(t.name)             # a tool with no label is never offered
    return tools

def is_risky(action_name):
    return RISK[action_name] != "harmless"        # from the table. Nothing the model says is read here

def within_limits(action_name, payload):
    limit = LIMITS.get(action_name)               # from configuration: policy numbers
    if limit and limit.measure(payload) > limit.most:
        raise OverLimit(action_name, limit.most)

def classify_command(command):                    # the check for an open-ended tool: code rules first
    if any(rule.matches(command) for rule in ALWAYS_REFUSED):
        raise Refused(command)
    if any(rule.matches(command) for rule in KNOWN_SAFE):
        return "harmless"
    verdict = second_check(command) if second_check else None    # a person, or a model call that did not write it
    return "harmless" if verdict == "safe" else "cannot be undone"   # unsure, or no second check: risky

def facts_are_fresh(action_name, facts, now):
    for f in facts:                               # the facts the design names for this action
        window = FRESH_FOR[(action_name, f.kind)]
        if f.disputed or now - f.last_confirmed_at > window:
            return False, f
    return True, None

def before_risky_action(action_name, payload, facts, now):   # called by run_action, on every path
    within_limits(action_name, payload)           # first: an action past its limit is refused, not asked about
    ok, stale = facts_are_fresh(action_name, facts, now)
    if not ok:
        ask_to_confirm(stale)
        raise WaitsForConfirmation(action_name, stale.id)

def ask_to_confirm(fact):                         # the one message that may be sent about it
    key = f"confirm-{fact.id}-{fact.last_confirmed_at:%Y%m%d%H%M%S}"   # the same until the fact is confirmed again
    return run_action(key, message_service, confirm_request(fact),   # a retry finds the key and asks nothing
                      memory_ok=True)                 # called inside run_action, after its guard passed

def call_tool(tool, payload, request_id):         # every tool the model asks for runs through here
    if tool.name in OPEN_ENDED and classify_command(payload["command"]) != "harmless":
        check_approval(tool.name, {"request": request_id}, payload["command"], None)   # this command, this request
    return tool.run(payload, key=f"{tool.name}-{request_id}")   # the same request id keys the action: once
```

## Tests that try to break it

Use two fake outside services that count calls. One honours idempotency keys the way the real service does. The other ignores them and does every call it gets, so a test can show that your own code stops the repeat. Assert on the count. Run the tests below against the second one unless a case says otherwise.

These are the standing test "An action happens exactly once". Each is its own test. `steps/3-design.md` says which apply to this design.

- **Crash after the action.** Make the app fail right after the service accepts the action and before the result is saved. Run it again. The count is exactly one. (Every agent with an action.)
- **Crash before the action.** Make the app fail after the action is claimed and before the service is called. Let whatever picks up unfinished actions run. The count is exactly one, not zero. The first test alone cannot tell a retry that works from a retry that does nothing. (Every agent with an action.)
- **Crash between the change and the claim.** When a record change calls for an action: commit the change, stop the app before the action is claimed, start it again and let whatever picks up unfinished actions run. The count is exactly one, not zero. (Every agent where a committed change calls for an action.)
- **Unknown result.** With the fake that honours keys, tell it to forget the key, then retry after the gap. The app asks the service what happened, by the reference, and does not send again. (Every agent with an action.)
- **Two at the same moment.** Start the same action twice at the same moment, from two runs. The count is exactly one. (Every agent with an action. A person pressing a button twice does this too.)
- **A late second firing.** When runs start on a schedule: let the run for one slot finish, then fire the same slot again late, as a scheduler catching up after a restart would. The late run makes the same key as the on-time run, and the count stays one. (Runs start on a schedule.)
- **The same event again.** When runs start on an event: deliver the same event twice, the second after the first run finished. The count stays one. (Runs start on an event.)
- **Crash after the approval.** A person approves, and the app fails before the action. Let whatever picks up unfinished actions run. The count is exactly one, and nobody is asked to approve again. (An action needs approval. When a task starts it, this is the task test of the same name.)
- **Delete, then the same action again.** Finish the action, delete the owner's data, make true again whatever starts the action (re-open the item, put the request back), then start it the way it is normally started (fire the same slot, deliver the same event, or repeat the request). Without that step the run may stop for another reason, and the key is not what is tested. The count stays one. (The design deletes an owner's data.)

These are the standing test "A wrong or expired approval is refused". Each is its own test.

- **Wrong approval.** Approve text A. Try to send text B with it. Refused.
- **Expired approval.** Approve, let the approval run out, try to send. Refused.
- **Changed after approval.** Approve, change the record the action is built from, try to send. Refused.
- **Not allowed to approve.** Approve as someone the design does not name. Refused. For a person who approves by reply: a reply from another sender, one without the code, a "no" that quotes the request, and one that holds the code and the word inside a sentence ("sorry, I can't confirm 4821 yet") are each refused.

These are the standing tests "Risk is fixed in code and limits hold" and "A risky action waits when a fact it rests on is stale". Each is its own test.

- **The model names a lower risk.** Have the model pass `risk: harmless`, in every argument it can fill, for an action whose label is `sends something out`. The approval or the wait it needs is still asked for.
- **A tool with no label.** Give the app a tool that has no entry in the risk table and start it. It refuses to start, and the model is never offered the tool.
- **One past the limit.** For each limit, ask for one more than it allows (one more recipient, one more unit of money), or, for a list, a recipient not on it. The action is refused and nothing is sent or paid. Exactly the limit goes through.
- **A forbidden command.** For each open-ended tool, pass a command a code rule always refuses. It is refused before the tool runs.
- **A command no rule covers.** For each open-ended tool, pass a command no rule covers, with the separate check unsure or absent and every fact fresh. It does not run until a person approves that exact command, and with that approval it runs once. The same command in another request needs its own approval.
- **A stale fact.** Let a fact a risky action rests on go unconfirmed for longer than its window, and start the action, from a task or a timer as well as from the model. It waits, and the agent sends one request to confirm the fact; trying again while the fact is still stale sends no second request. The task that started it is `waiting for confirmation`, with no try counted, and sends once after the fact is confirmed. Answer with a correction instead: the task runs again on the new version. Give no answer: after the set time the task is `failed` and a person is told. A disputed fact does the same.
- **A fresh fact.** Confirm the same fact inside its window and start the action. It goes ahead without asking.

These belong with the tests of the guard procedures in section 4:

- **No way to know.** With a fake service that accepts no keys and cannot be asked, fail in the middle. The app stops and asks a person.
- **Around the function.** Search the code for calls to the outside service. The only one is inside `run_action`.
- **The model asks for it.** In a test conversation, tell the model to send without approval, or to issue a refund it has no tool for. The action does not happen, because code stops it, not because the model declined.

## In the design file

Section 5 and its lines, the guard procedures in section 4 (marked `code`, each naming its actions), the rows `Side effect protection` in section 3 for the record of actions and the approvals, and the tests in section 9, as `steps/3-design.md` says. In a design with A9: the lines `Risk of each action`, `Limits`, `Open-ended tools`, and `Before a risky action these facts are fresh` when a risky action rests on a fact with no end. If an outside service accepts no keys and cannot be asked what happened, say so in section 10: its guard stops and asks a person, with the test "No way to know".
