# Prospective memory

**In plain words:** remembering to do something in the future. The agent says "I'll check again on Friday". Friday arrives, the model is not running, and nothing happens, unless something was saved and something wakes the app. Prospective memory is a saved future task plus a trigger. (video)

Example: "If Maya has not replied by Friday 9am, draft a follow-up for staff to approve."

**When to skip** (you decided this in step 2): when every run ends completely before the next begins and the agent never promises anything for later. Something the agent merely waits on a person for (an approval, a flag on a screen) needs a future task only if the agent must act when no answer comes. (ours)

Two problems make this harder than it looks. The world changes between saving the task and waking up. And schedulers fire the same task more than once, or the app crashes halfway through one. (An agent with no future tasks whose runs start on a timer has the second problem too. `reference/side-effects.md` covers it.)

What a task does when it wakes is often an action with a side effect. The protection for that action (idempotency keys, approvals) is in `reference/side-effects.md`, which you read whenever the agent has such an action. This file covers the task itself.

## Questions

- T1. What wakes it: a time, an event, or a condition?
- T2. What does the saved task hold?
- T3. What was true when the task was scheduled that must still be true when it wakes (its premise)? What else does it look at again before acting?
- T4. Which of its steps have side effects? (Each one is a row in section 5 of the design.)
- T5. What are the statuses, and who can cancel a task? Write who may cancel as a note in the Statuses cell, such as `cancelled (by staff)`.
- T6. How long may a task sit in `running` before it is assumed to have crashed?

## Defaults

- **What the task holds:** what must happen, the context needed to carry on (ids to look things up again, not copies of the data), its status, whether a person must approve, the trigger, and how many times it has been tried. (video for the first four; the last two are ours)
- **On waking, look at the world again before doing anything.** Has the user already replied? Was the task cancelled? Is the approval still missing? Has the thing it was waiting for changed? Then decide. (video) Store ids and look the data up fresh, so the task acts on today's facts, not last week's. (ours)
- **A task saves its premise and checks it first.** The premise is the record's version, or the values the task depends on, saved with the task in the same transaction. On waking, after the claim and before anything else, code compares it with the record now. Any difference closes the task as `no longer valid`, with the reason, and nothing is done. If the record still calls for the action, the replacement is written from the record now, in the same transaction, so a change written past the change function (an import, a second copy of the app) does not lose the action. The step that does the side effect compares it once more right before acting, in the same transaction as the action's claim where the store allows, so a change made while the task runs also closes it as `no longer valid` and nothing is sent. Looking the data up fresh is not enough by itself: a reminder for an item that moved to next week would fetch the new date and still go out today. (ours)
- **A changed record closes or replaces its tasks, in the same transaction.** A change to a value a task's premise names (a new date, a new owner, the record closed) closes the task and, when the record still calls for the action, writes its replacement. A change to anything else leaves the task, and any approval it holds, alone. When a value the premise names changes and no task of that kind is open (the last one finished, or the record was closed and opened again), the change writes a new one if the record calls for the action. With a version premise every edit counts, so after the send any edit writes a new task, and a comment on an item sends its reminder again: name the values in the premise when that matters. The replacement is a new task with a new id and its own premise. Never edit a task's time in place: a timer already set for the old time would find the edited task pending with a matching premise. The check on waking stays, because a timer already delivered, a catch-up and a second copy of the app can each wake a task after the change. (ours)
- **Clear statuses.** `pending`, `running`, `waiting for approval`, `done`, `cancelled`, `no longer valid`, `failed`. Leave out `waiting for approval` if no task needs one. `waiting for confirmation` when an action rests on a fact with no end (`reference/side-effects.md`). `cancelled` is a person's or the app's decision to stop a task. `no longer valid` is the premise check finding the reason gone. A task that is not `pending` does nothing when the scheduler fires it. (video for pending and done; the rest is ours)
- **Claim before acting.** Moving a task from `pending` to `running` is a single step in the database that either happens fully or not at all, so two firings cannot both take it and draft twice. The idempotency key on the action, not the claim, is what stops a second send if a task is ever run twice, so each has its own test. The same goes for a task that was approved: it moves from `waiting for approval` to `running` in one step, with the approval saved, before anything is sent. (ours)
- **A task stuck in `running` goes back to `pending`.** If the app crashes after claiming a task, the task would sit in `running` forever and the follow-up would never happen. A timer job returns any task that has been `running` longer than a set time to `pending` and adds one to its count of tries. After a set number of tries it becomes `failed` and a person is told. Both numbers are arbitrary. Going round again is safe because every side effect is behind an idempotency key, and an approval that was already saved still counts. (ours)
- **An approval given ahead of time.** When a task is approved now and acts later (a payment approved today and made on its due date), the approval lasts until the scheduled time plus a margin, and on waking the task checks that what was approved is unchanged. If it changed, it asks again. The premise check comes first: an approval applies only to the premise it was given on, so if a value the premise names changed, the task is closed as `no longer valid` and nothing is asked or sent; its replacement asks when it fires. Asking again on the same task is for a change the premise does not name. The margin is arbitrary. (ours)
- **The scheduler is whatever the project has.** A tasks table and a timer job that checks it each minute is enough for many agents. A queue or a durable execution product does the same job with more guarantees. It is named on the section 4 line `What wakes the app`. (ours)

## Code to build

- **A tasks table.** Id, what to do, the ids it needs to carry on, the premise it was scheduled on, the trigger (a time, an event name, or a condition to test), status, whether approval is needed, how many tries, owner and scope, created and updated times.
- **A scheduler.** Wakes the app when a trigger fires. For conditions ("no reply by Friday"), a time trigger plus a check on waking.
- **`on_wake(task_id)`.** Claims the task, looks at the world again, then acts, asks for approval, or closes the task.
- **A timer job for stuck tasks,** and one that ends long waits for confirmation.
- **Cancel.** A way for a person, and for the app when the reason for the task has gone, to cancel it.

Sketch, to adapt. `approve`, `check_approval` and `run_action` are the functions from `reference/side-effects.md`.

```python
def on_wake(task_id):
    task = db.claim(task_id, from_status="pending", to_status="running")  # one step: only one firing wins
    if task is None:
        return                                    # already taken, done, waiting or closed
    on_wake_claimed(task)

def on_wake_claimed(task):                        # everything after the claim, also for a task just approved
    if task.due_at > now():                       # a firing that came early does nothing
        return db.set_status(task.id, "pending")
    world = look_again(task)                      # fresh lookups by id
    changed = premise_changed(task.premise, world.record)   # before anything else is decided
    if changed:
        with db.transaction():                    # the task ends and its replacement is written together
            return close_and_replace(task, world.record, changed)
    if world.no_longer_needed:
        return db.close(task.id, "cancelled", reason=world.why)
    if task.approved_draft and task.approved_version == world.record_version:
        draft = task.approved_draft               # approved, and the record has not changed since
    else:
        draft = make_draft(task, world)           # nothing approved yet, or the record moved on: draft again
    if task.needs_approval and not approval_still_counts(task.id, draft, world.record_version):
        return db.set_status(task.id, "waiting for approval", draft=draft,
                             draft_version=world.record_version)
    try:
        sent = send_follow_up(task.id, draft, world.record_version)
    except WaitsForConfirmation as wait:          # a fact the send rests on is stale: one request went out
        return db.set_status(task.id, "waiting for confirmation", waiting_on=wait.fact_id)   # no try is counted
    if sent is HELD:
        return db.set_status(task.id, "pending")  # another run holds the send: not done, so it runs again later
    if sent is NO_LONGER_VALID:
        return                                    # closed by the check right before the send
    db.close(task.id, "done")

def on_approved(task_id, person):                 # called when a person presses approve
    task = db.task(task_id)
    approve(person, "send_follow_up", {"task": task_id}, task.draft, task.draft_version,
            lasts_until=approval_lasts_until(task))   # a set time from now, or the due time plus a margin if approved ahead
    task = db.claim(task_id, from_status="waiting for approval", to_status="running",
                    approved_draft=task.draft, approved_version=task.draft_version)
    if task is None:                              # one step. From here the stuck task job covers a crash
        return
    on_wake_claimed(task)                         # the same path as a firing: the premise is checked first

def on_confirm_reply(fact_id, reply, person, now):   # the handler for the answer to a request to confirm
    if reply.confirms:                            # the exact confirm form (steps/3-design.md, section 3)
        record_event(fact_id, "confirmed", person, None, now)   # reference/feedback-and-improvement.md
    else:
        save_correction(fact_id, reply.value, person)           # a new version of the fact, through save_fact
    on_confirmed(fact_id)                         # either way the waiting tasks run their checks again

def on_confirmed(fact_id):                        # called by on_confirm_reply, for a yes and for a correction
    for task in db.tasks(status=("waiting for confirmation",), waiting_on=fact_id):
        db.set_status(task.id, "pending")         # fired again as soon as it is due; no try was counted

def end_long_waits():                             # timer job: a wait for confirmation does not last for ever
    for task in db.tasks(status=("waiting for confirmation",), updated_before=now() - CONFIRM_WAIT):
        db.close(task.id, "failed", reason="no answer to the request to confirm")
        tell_a_person(task)                       # the promised action did not happen: a person decides

NO_LONGER_VALID = object()                        # what send_follow_up returns when the premise changed mid-run

def send_follow_up(task_id, draft, record_version):
    task = db.task(task_id)
    record = db.record(task.record)
    changed = premise_changed(task.premise, record)   # once more, right before the side effect
    if changed:                                   # the record changed while the task was running
        with db.transaction():
            close_and_replace(task, record, changed)
        return NO_LONGER_VALID                    # nothing is sent
    if task.needs_approval:
        check_approval("send_follow_up", {"task": task_id}, draft, record_version)
    return run_action(f"task-{task_id}-send", mail_service, draft, memory_ok=True,   # the same key on every try
                      action="send_follow_up", facts=facts_for("send_follow_up", task))   # checked there

def return_stuck_tasks():                         # timer job
    for task in db.tasks(status="running", updated_before=now() - STUCK_AFTER):
        if task.tries >= MAX_TRIES:
            db.close(task.id, "failed"); tell_a_person(task)
        else:
            db.set_status(task.id, "pending", tries=task.tries + 1)

PREMISE_VALUES = {"remind the owner": ("due_on", "owner_id", "status")}   # from the design. None: the version

def premise_of(record, kind):                     # saved on the task when the task is written
    names = PREMISE_VALUES[kind]
    return {"version": record.version} if names is None else {n: getattr(record, n) for n in names}

def premise_changed(premise, record):
    if record is None:
        return "the record is gone"
    diff = ["%s was %r and is %r" % (k, v, getattr(record, k)) for k, v in premise.items() if getattr(record, k) != v]
    return "; ".join(diff) or None

def close_and_replace(task, record, reason):      # inside the caller's transaction
    db.close(task.id, "no longer valid", reason=reason)
    if record is not None and needs_a_task(record):    # the record still calls for the action
        db.insert_task(kind=task.kind, record=record.id, due_at=when_for(record),
                       premise=premise_of(record, task.kind))   # a new row from the record now, never an edited time

def change_record(record_id, **new_values):       # the one function that moves, hands over or closes a record
    with db.transaction():
        old = {n: getattr(db.record(record_id), n) for n in new_values}   # the values before the change
        record = db.update_record(record_id, **new_values)        # the version goes up by one
        open_ = ("pending", "waiting for approval", "waiting for confirmation")
        for task in db.tasks(record=record_id, status=open_):
            changed = premise_changed(task.premise, record)
            if changed:                           # only a change to a value the premise names ends the task
                close_and_replace(task, record, changed)
        for kind, names in PREMISE_VALUES.items():   # a premise value changed and no task of this kind is open or running
            touched = names is None or any(old[n] != getattr(record, n) for n in new_values if n in names)
            busy = db.tasks(record=record_id, status=open_ + ("running",), kind=kind)   # a running one replaces itself
            if touched and needs_a_task(record) and not busy:
                db.insert_task(kind=kind, record=record_id, due_at=when_for(record),
                               premise=premise_of(record, kind))   # the last one finished, or the record reopened
```

`on_wake_claimed` is everything `on_wake` does after its claim, so a task a person just approved takes the same path and its premise is checked first. A task that went back to `pending` after it was approved runs `on_wake` again. If the record has not changed, it finds the saved draft and the approval that still counts, so it sends without asking a second time. If a value its premise names changed, the task is closed and its replacement asks again when it fires. If only something else changed, the approval no longer matches the record's version, so the same task drafts again and asks again. `record_event` is the function in `reference/feedback-and-improvement.md` that writes a fact event, `save_correction` saves the corrected value as a new version through `save_fact`, and `CONFIRM_WAIT` is the design's `A wait for confirmation ends after`. `facts_for(action, thing)` returns the facts with no end the design names for the action (section 5, `Before a risky action these facts are fresh`), and `run_action` is the one in `reference/side-effects.md`.

## Tests that try to break it

The first two, the third when a task waits for approval, and the fourth when section 5 has an action, are the standing test "A task fired twice acts once and a stuck task runs again".

- **Fire twice.** Fire the same task twice at the same moment. One draft (this fails with the claim removed), one action.
- **Crash after the claim.** Make the app fail right after it claims the task and before it calls the outside service. Wait past the stuck time. The task runs again and the fake service counts exactly one action. A test that only crashes after the service accepted the action would pass even if stuck tasks were never picked up again.
- **Crash after the approval.** A person approves, and the app fails before it sends. Wait past the stuck time. The task runs again, does not ask for approval a second time, and the fake service counts exactly one action.
- **Held by another run.** Let a stuck task go back to `pending` while the run that claimed its action still holds it, and fire the task. It is not closed as `done`. Once the hold runs out it runs again, and the fake service counts exactly one action.
- **Crash after the action.** Make the app fail after the service accepts the action and before the task is closed. The task runs again and the count is still one.
- **The premise changed.** These are the standing test "A task whose reason changed does nothing". Schedule a task, change one value its premise names, and deliver the old firing anyway (call the wake function with the old task's id, as a timer set earlier would). Write that change straight to the record, past the change function, as an import or a second copy of the app would, so only the check on waking can stop the task. Nothing is drafted, asked or sent, the task is closed as `no longer valid` with the reason, and its replacement, written from the record now, is in the tasks table. One test per value. Then: the task written after the change fires and acts, once. Then: change a record and read the tasks table before any timer fires: the old task is closed and the new one is there. Then: change the record while a task is running, after its check on waking and before its send: nothing is sent and the task is closed as `no longer valid`. Then: let a task act, and change a value its premise names afterwards, or close the record and open it again: a new task is written. Remove the check on waking and the first test must fail. Remove the closing in the change function and the third must fail. Remove the check right before the send and the fourth must fail.
- **The world changed in a way the premise does not name.** Save "follow up if no reply". Record a reply. Fire the task. It closes as `cancelled` without drafting anything. Change a value the premise does not name through the change function instead (a note on the record): the task stays open and still acts, once.
- **Approved ahead, then changed.** Approve a task that acts next week. Change a value its premise names, past the change function, and fire the task: it is closed as `no longer valid`, nothing is asked or sent, and a replacement written from the record now asks for approval when it fires. Change something its premise does not name instead: the same task asks again and does not act.
- **Cancelled.** Cancel a task, then fire it. Nothing happens.
- **Too many tries.** Make a task fail every time. After the set number of tries it is `failed` and a person has been told.

## In the design file

- Section 7: one row per kind of task, with a trigger that starts with `time`, `event` or `condition`, and statuses that include `pending`, `running` and `done`. The line `A running task goes back to pending after`. In a design with A9, the lines `Premise of each task` and `A changed record cancels or replaces its tasks through`.
- Section 4: the line `What wakes the app`.
- Section 3: a row for future tasks under Prospective memory. Code writes it, so its source is `system record: the app`.
- Section 4: a procedure row, marked `code`, for claiming a task before it acts, with its test.
- Section 5: the line `Unfinished actions are picked up by: the stuck task job`, when tasks start the actions.
- Section 9: "A task fired twice acts once and a stuck task runs again".
