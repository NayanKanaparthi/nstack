# Prospective memory

**In plain words:** remembering to do something in the future. The agent says "I'll check again on Friday". Friday arrives, the model is not running, and nothing happens, unless something was saved and something wakes the app. Prospective memory is a saved future task plus a trigger. (video)

Example: "If Maya has not replied by Friday 9am, draft a follow-up for staff to approve."

**When to skip** (you decided this in step 2): when every run ends completely before the next begins and the agent never promises anything for later. Something the agent merely waits on a person for (an approval, a flag on a screen) needs a future task only if the agent must act when no answer comes. (ours)

Two problems make this harder than it looks. The world changes between saving the task and waking up. And schedulers fire the same task more than once, or the app crashes halfway through one. (An agent with no future tasks whose runs start on a timer has the second problem too. `reference/side-effects.md` covers it.)

What a task does when it wakes is often an action with a side effect. The protection for that action (idempotency keys, approvals) is in `reference/side-effects.md`, which you read whenever the agent has such an action. This file covers the task itself.

## Questions

- T1. What wakes it: a time, an event, or a condition?
- T2. What does the saved task hold?
- T3. When it wakes, what does it check again before acting?
- T4. Which of its steps have side effects? (Each one is a row in section 5 of the design.)
- T5. What are the statuses, and who can cancel a task? Write who may cancel as a note in the Statuses cell, such as `cancelled (by staff)`.
- T6. How long may a task sit in `running` before it is assumed to have crashed?

## Defaults

- **What the task holds:** what must happen, the context needed to carry on (ids to look things up again, not copies of the data), its status, whether a person must approve, the trigger, and how many times it has been tried. (video for the first four; the last two are ours)
- **On waking, look at the world again before doing anything.** Has the user already replied? Was the task cancelled? Is the approval still missing? Has the thing it was waiting for changed? Then decide. (video) Store ids and look the data up fresh, so the task acts on today's facts, not last week's. (ours)
- **Clear statuses.** `pending`, `running`, `waiting for approval`, `done`, `cancelled`, `failed`. Leave out `waiting for approval` if no task needs one. A task that is not `pending` does nothing when the scheduler fires it. (video for pending and done; the rest is ours)
- **Claim before acting.** Moving a task from `pending` to `running` is a single step in the database that either happens fully or not at all, so two firings cannot both take it and draft twice. The idempotency key on the action, not the claim, is what stops a second send if a task is ever run twice, so each has its own test. The same goes for a task that was approved: it moves from `waiting for approval` to `running` in one step, with the approval saved, before anything is sent. (ours)
- **A task stuck in `running` goes back to `pending`.** If the app crashes after claiming a task, the task would sit in `running` forever and the follow-up would never happen. A timer job returns any task that has been `running` longer than a set time to `pending` and adds one to its count of tries. After a set number of tries it becomes `failed` and a person is told. Both numbers are arbitrary. Going round again is safe because every side effect is behind an idempotency key, and an approval that was already saved still counts. (ours)
- **An approval given ahead of time.** When a task is approved now and acts later (a payment approved today and made on its due date), the approval lasts until the scheduled time plus a margin, and on waking the task checks that what was approved is unchanged. If it changed, it asks again. The margin is arbitrary. (ours)
- **The scheduler is whatever the project has.** A tasks table and a timer job that checks it each minute is enough for many agents. A queue or a durable execution product does the same job with more guarantees. It is named on the section 4 line `What wakes the app`. (ours)

## Code to build

- **A tasks table.** Id, what to do, the ids it needs to carry on, the trigger (a time, an event name, or a condition to test), status, whether approval is needed, how many tries, owner and scope, created and updated times.
- **A scheduler.** Wakes the app when a trigger fires. For conditions ("no reply by Friday"), a time trigger plus a check on waking.
- **`on_wake(task_id)`.** Claims the task, looks at the world again, then acts, asks for approval, or closes the task.
- **A timer job for stuck tasks.**
- **Cancel.** A way for a person, and for the app when the reason for the task has gone, to cancel it.

Sketch, to adapt. `approve`, `check_approval` and `run_action` are the functions from `reference/side-effects.md`.

```python
def on_wake(task_id):
    task = db.claim(task_id, from_status="pending", to_status="running")  # one step: only one firing wins
    if task is None:
        return                                    # already taken, done or cancelled
    world = look_again(task)                      # fresh lookups by id
    if world.no_longer_needed:
        return db.close(task_id, "cancelled", reason=world.why)
    if task.approved_draft and task.approved_version == world.record_version:
        draft = task.approved_draft               # approved, and the record has not changed since
    else:
        draft = make_draft(task, world)           # nothing approved yet, or the record moved on: draft again
    if task.needs_approval and not approval_still_counts(task_id, draft, world.record_version):
        return db.set_status(task_id, "waiting for approval", draft=draft,
                             draft_version=world.record_version)
    if send_follow_up(task_id, draft, world.record_version) is HELD:
        return db.set_status(task_id, "pending")  # another run holds the send: not done, so it runs again later
    db.close(task_id, "done")

def on_approved(task_id, person):                 # called when a person presses approve
    task = db.task(task_id)
    approve(person, "send_follow_up", {"task": task_id}, task.draft, task.draft_version,
            lasts_until=approval_lasts_until(task))   # a set time from now, or the due time plus a margin if approved ahead
    task = db.claim(task_id, from_status="waiting for approval", to_status="running",
                    approved_draft=task.draft, approved_version=task.draft_version)
    if task is None:                              # one step. From here the stuck task job covers a crash
        return
    on_wake_claimed(task)                         # the same path as on_wake after its claim: look again first

def send_follow_up(task_id, draft, record_version):
    task = db.task(task_id)
    if task.needs_approval:
        check_approval("send_follow_up", {"task": task_id}, draft, record_version)
    return run_action(f"task-{task_id}-send", mail_service, draft)   # the key is the same on every try

def return_stuck_tasks():                         # timer job
    for task in db.tasks(status="running", updated_before=now() - STUCK_AFTER):
        if task.tries >= MAX_TRIES:
            db.close(task.id, "failed"); tell_a_person(task)
        else:
            db.set_status(task.id, "pending", tries=task.tries + 1)
```

`on_wake_claimed` is `on_wake` from the line after its claim. A task that went back to `pending` after it was approved runs `on_wake` again. If the record has not changed, it finds the saved draft and the approval that still counts, so it sends without asking a second time. If the record changed, it drafts again and asks again.

## Tests that try to break it

The first two, the third when a task waits for approval, and the fourth when section 5 has an action, are the standing test "A task fired twice acts once and a stuck task runs again".

- **Fire twice.** Fire the same task twice at the same moment. One draft (this fails with the claim removed), one action.
- **Crash after the claim.** Make the app fail right after it claims the task and before it calls the outside service. Wait past the stuck time. The task runs again and the fake service counts exactly one action. A test that only crashes after the service accepted the action would pass even if stuck tasks were never picked up again.
- **Crash after the approval.** A person approves, and the app fails before it sends. Wait past the stuck time. The task runs again, does not ask for approval a second time, and the fake service counts exactly one action.
- **Held by another run.** Let a stuck task go back to `pending` while the run that claimed its action still holds it, and fire the task. It is not closed as `done`. Once the hold runs out it runs again, and the fake service counts exactly one action.
- **Crash after the action.** Make the app fail after the service accepts the action and before the task is closed. The task runs again and the count is still one.
- **The world changed.** Save "follow up if no reply". Record a reply. Fire the task. It closes without drafting anything.
- **The facts changed.** Save a follow-up about a late order. Mark the order delivered. Fire the task. The draft reflects delivered, or the task closes.
- **Approved ahead, then changed.** Approve a task that acts next week. Change the thing it was approved for. Fire the task. It asks again and does not act.
- **Cancelled.** Cancel a task, then fire it. Nothing happens.
- **Too many tries.** Make a task fail every time. After the set number of tries it is `failed` and a person has been told.

## In the design file

- Section 7: one row per kind of task, with a trigger that starts with `time`, `event` or `condition`, and statuses that include `pending`, `running` and `done`. The line `A running task goes back to pending after`.
- Section 4: the line `What wakes the app`.
- Section 3: a row for future tasks under Prospective memory. Code writes it, so its source is `system record: the app`.
- Section 4: a procedure row, marked `code`, for claiming a task before it acts, with its test.
- Section 5: the line `Unfinished actions are picked up by: the stuck task job`, when tasks start the actions.
- Section 9: "A task fired twice acts once and a stuck task runs again".
