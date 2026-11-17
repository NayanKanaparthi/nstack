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
  - `a job over the actions record`, when there is no future task. A timer job, or the start of each run when the agent has no timer, finds rows that have been `started` for longer than a set time and passes each one through the same function again. For this the row must hold what is needed to redo the action.
  - `a person`. The row is shown to someone who presses the button again. Acceptable when a person started the action in the first place.

  Going round again is safe in all three, because the key is the same.
- **An approval covers one exact action.** It records the action, its exact content, the version of the record the approver saw, and when it stops counting. Before acting, the code checks the content still matches and the approval has not run out. If either fails, it asks again. (source: Let's Data Science write-up)
- **How long an approval lasts.** A set time, such as 24 hours. Or until an event code can test, written like an expiry by event: `when the conversation ends, told`. For an action approved now and done at a set time later (a payment approved today and paid on its due date), it lasts `until the scheduled time plus` a margin, and when the task wakes it checks again that the content is unchanged. The numbers are arbitrary and are the person's call. (ours)
- **Who approved comes from the app, not from the model.** The approver is whoever is signed in and pressed the button, or a person outside the system the design names, by a verified reply (`steps/3-design.md`, section 3: the sender, quoted text stripped, then exactly the one-time code and a fixed word, or a button). The design names who may approve. (ours)
- **An approval can confirm what it shows.** When the approver saw the content the action is built from, approving the action confirms that content for that one action. It does not turn the underlying record into a confirmed fact for later runs. See `steps/3-design.md`, section 3. (ours)
- **Every action has a guard in code.** A guard is the procedure that stands between the model and the action. For an action that needs approval, there are two: the check for the approval, and the one function above. For an action that needs no approval, the guard is the one function, plus any condition that must hold first (for example: a reminder is sent only for a confirmed item, and only to the person it is assigned to). An action is never unguarded. (ours)
- **The strongest guard is not giving the model the tool.** If the agent must never issue refunds, leave the refund tool out of its list. (ours)
- **What an action carries is stated, and outside or model-written text is checked before it goes out.** Section 5 says for each action one or more of: `none`; `fixed or templated` (fixed text with only the app's own values filled in, such as an id or a date); `outside content` (text read from outside and passed on, such as a quoted message); `agent worked out` (text the model wrote). The record of actions holds what its actions carry, and is never put in a model call. When an action carries `outside content` or `agent worked out` and no person approves each one, a procedure in code checks the content before it is sent. It is named on the line `Content checked before sending by` (several names joined by semicolons when the checks are split) and guards those actions. What it checks fits where the content goes. Always secrets, and who it reaches. Then whatever inside the content could act on its own once it arrives: in a message, for example, a mention that notifies people or a link; in a spreadsheet, a formula; in a field another system acts on, a command. Its Rule cell in section 4 says exactly what it catches. A rule that promises more than the code catches ("any number", "every secret") is a design error: write what the check really catches, and if the person accepts a limit, write it in section 10. With approval, the person sees the content, and the secret check still runs. (ours)
- **A request for approval or confirmation that goes out as a message is itself a side effect.** It gets its own key and goes only to the people who may approve or confirm. (ours)

## Code to build

- **An actions table.** One row per idempotency key: the key, status (`waiting for approval`, `started`, `done`), when it started, the result, and what is needed to redo the action if a job picks it up. A draft waiting for a person's approval is a row here with its draft. The table is read by `run_action` and the screens people use, and never put in a model call. Secrets are removed before a row is written, as for every store.
- **`run_action`.** The one function every outside action passes through.
- **An approvals table.** The action, the ids it is about, a fingerprint of the exact content (a hash, not the content itself), the version of the record the approver saw, who approved, when it runs out.
- **`approve` and `check_approval`.** Used by every action that needs approval.
- **The pick-up for unfinished actions,** as the design names it.
- **The tool list,** with any tool the agent must not have left out.

Sketch, to adapt:

```python
LEASE = timedelta(minutes=15)     # arbitrary: longer than one action can take
HELD = object()                   # what run_action returns when another run holds the action

def claim_action(key, payload):
    """One transaction (in SQLite: BEGIN IMMEDIATE). The key column is unique."""
    with db.transaction():
        row = db.action(key)
        if row is None:
            db.insert_action(key, payload, status="started", lease_until=now() + LEASE)
            return "new", None
        if row.status == "done":
            return "done", row
        if row.status == "started" and row.lease_until > now():
            return "held", row                    # another run is acting right now
        db.update_action(key, status="started", lease_until=now() + LEASE, tries=row.tries + 1)
        return "taken over", row                  # an earlier try stopped, or an approved draft is going out

def run_action(key, service, payload):
    """Every side effect goes through here. The key is the same on every try."""
    state, row = claim_action(key, payload)
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
    return run_action(key, mail_service, draft)

def run_for_slot(owner_id, slot):                # started by a timer; slot is the time the trigger was set for
    key = f"report-{owner_id}-{slot}-send"        # a late or second firing of the same slot makes the same key
    return run_action(key, mail_service, build_report(owner_id, slot))

def pick_up_unfinished(owner):                    # timer job, when the design says a job does this
    for row in db.actions(owner=owner, status="started", lease_ended_before=now()):
        run_action(row.key, service_for(row), row.payload)   # each pick-up is a run, and is logged as one

def forget_owner_actions(owner):                  # part of the delete function in reference/every-store.md
    db.clear_action_content(owner)                # keeps key, status and times; drops payload and result
```

## Tests that try to break it

Use two fake outside services that count calls. One honours idempotency keys the way the real service does. The other ignores them and does every call it gets, so a test can show that your own code stops the repeat. Assert on the count. Run the tests below against the second one unless a case says otherwise.

These are the standing test "An action happens exactly once". Each is its own test. `steps/3-design.md` says which apply to this design.

- **Crash after the action.** Make the app fail right after the service accepts the action and before the result is saved. Run it again. The count is exactly one. (Every agent with an action.)
- **Crash before the action.** Make the app fail after the action is claimed and before the service is called. Let whatever picks up unfinished actions run. The count is exactly one, not zero. The first test alone cannot tell a retry that works from a retry that does nothing. (Every agent with an action.)
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

These belong with the tests of the guard procedures in section 4:

- **No way to know.** With a fake service that accepts no keys and cannot be asked, fail in the middle. The app stops and asks a person.
- **Around the function.** Search the code for calls to the outside service. The only one is inside `run_action`.
- **The model asks for it.** In a test conversation, tell the model to send without approval, or to issue a refund it has no tool for. The action does not happen, because code stops it, not because the model declined.

## In the design file

Section 5 and its lines, the guard procedures in section 4 (marked `code`, each naming its actions), the rows `Side effect protection` in section 3 for the record of actions and the approvals, and the tests in section 9, as `steps/3-design.md` says. If an outside service accepts no keys and cannot be asked what happened, say so in section 10: its guard stops and asks a person, with the test "No way to know".
