# Production: speed, volume, failures, measurements, storage

**In plain words:** memory that works in a test still has to be fast enough that nobody waits for it, keep working when a part of it is down, and show in numbers whether it is going wrong. This file says how, and what the design writes down for each. (ours)

**When to read:** the design has the line A9. Sections 11 to 13 of the design come from here: section 11 and section 12 when the agent saves anything besides the run log, section 13 when A9 also names `high volume`.

## Questions

- P1. Does someone wait live for the agent's answer, and how long may an answer take?
- P2. Which memory work needs a model (pulling facts out of a message, comparing a new fact with the current one, writing a summary), and does any of it have to finish before the reply?
- P3. What volume is expected: how many users, how many facts each, how many runs a day?
- P4. What happens to an answer, and to an action, when each part is down?
- P5. Which numbers would show memory going wrong, and where is each kept?
- P6. Do the agent's questions follow links several steps away, or does one person appear under many names across sources?

## Defaults

**Nobody waits for memory.** These apply when A9 names `someone waits live` and the agent reads memory.

- **Model work for memory runs after the reply.** Pulling facts out of a message, comparing a new fact with the current one and writing a summary all run after the reply has been returned, from a queue. A queue is a waiting line of jobs: one part of the app adds a job, a worker does it later, so the person is not kept waiting. (ours)
- **What must run first is listed.** Anything that has to finish before the reply is written in the design with its reason. The usual honest entry is the read-back of a fact the reply itself depends on. Everything else waits for the worker. (ours)
- **Reads have one time allowed per turn.** All the memory reads before the model call share one time allowed, the one the design's line states: each read gets what is left of it, and a timeout enforces it. When a read does not finish in time, its part of the call is left empty and the turn is marked as run without memory. The time allowed is a `requirement` worked out from the response time the person states (their time, less what the model call needs), or a `default`. When the person was not asked, because step 1's four questions were used up, it is a `default`. It is at most a minute: nobody waits live longer, so a longer time allowed cuts nothing off. The design line ends `then the reply goes on without them`. (ours)

**Search.**

- **Embeddings are made when an item is saved.** An embedding is a list of numbers that stands for the meaning of a piece of text, so texts with close meanings get close numbers. It is made once, when the item is saved. A search then makes one embedding, for the question. This applies when the agent saves what it searches by embedding. (ours)
- **A reranker only when the test set calls for it.** A reranker is a second step that re-orders the first results of a search, so the best few are the ones that reach the model. Add one only when the retrieval test set shows two things: the right item is usually somewhere in a wide first pass (for more than half the questions), and often missing from the few that reach the model (it reaches the model for fewer questions than the wide pass finds it). The design says which it is, with the two counts, and, when there is a reranker, how many results it takes and how many of them it keeps. This applies when the agent uses keyword or embedding search. (ours)

**Volume.** These apply when A9 names `high volume`, which it does only once the person has stated a volume, and the agent saves something besides the run log.

- **Counters are a recount on a timer.** With a fact with no end, recording an event writes no counter on the fact's row: it adds the event and a row saying which fact was touched, in the same transaction. A timer job recounts each touched fact from all its events, with the `rebuild_counters` of `reference/feedback-and-improvement.md`, and sets its counters to that count. The repair for drift is the same recount over every fact. Because the counters are set, never added to, a second run, a run after a repair, or an event that commits late cannot count anything twice. A confirmation still sets the fact's last confirmed time and its wait when it is recorded, and a contradiction still makes the fact due at once, because every read needs those at once. The counters lag the events by at most the interval. The design gives the interval. (ours)
- **Large tables are planned.** The design names the partition key: the column large tables are split by, usually the owner, so a query for one owner reads one part of the table. It says when replaced versions move to cheaper storage (a slower, cheaper table or store that the history read still reaches), and which columns are indexed. An index is a structure the database keeps so it can find rows by a column without reading them all. (ours)
- **Extra model calls are capped.** Every model call in a turn beyond the one that writes the reply is counted on the turn, and a turn makes at most the cap. Work past the cap is kept on the turn and written as a job row once the reply has gone, so a slow store does not hold the turn. Work the design lists under "Memory work before the reply" is never pushed back: it runs first and counts toward the cap, and the cap is at least the number of listed items. The design gives the cap. If the process stops between the reply and `end_turn`, the work kept on the turn and the turn's measure row are lost: the price of writing after the reply, and a small one. (ours)
- **Queue lag is measured.** How long a job waits before a worker takes it is measured, with an alert line (see Measurements). (ours)

**Failures.**

- **Fail open for reading, fail closed for acting.** When memory cannot be read, the agent still answers, without memory, and says so when the answer depends on it. When memory cannot be read, an action that needs a confirmed fact, an approval or its own record of actions does not happen: a turn whose reads did not arrive blocks the actions it would take, and with the store down there is no claim, no approval and no fresh fact to check. Each row of the failures table below says what happens to answers and to actions, and names the test that shows it. (ours)
- **The memory store** is whatever holds the rows of section 3: facts, summaries, episodes, tasks, the record of actions taken, approvals, the run log and the audit log. When some of them live in another database, the design's row says which part is down and what still works. (ours)
- **Counting never touches the store.** A measure is kept in the process and written by a timer job, so counting never needs the store and never fails. When the store is down the numbers wait in the process and are written once it is back. The buffer has a size limit, and when it is full the oldest numbers go first; how many went is counted apart (`numbers_dropped`) and written with the rest. A process that stops before then loses those numbers: a measure is a sample of what happened, not a record of it. (ours)
- **A write the turn makes never fails the turn.** A save after the reply, or a job queued in the turn, that meets a store that is down goes to a small local spool, and a timer job writes it once the store is back. Each such write changes nothing the second time: it inserts, or does nothing when the row is already there. So a write the store did keep, whose answer was lost with the connection, drains clean. An entry that fails for any other reason is set aside for a person and counted (`writes_set_aside`), and the drain goes on with the entries behind it. When the spool is full, the write is dropped and counted (`writes_dropped`). A write that fails for another reason while the turn runs is an error and reaches the caller: only a store that is down is spooled. The three counts are the measure `writes dropped`. (ours)
- **The spool, the set-aside file, job rows and measure rows follow the every-store rules.** They are not rows of section 3: they hold writes on their way to the store, and ids and counts about the work, nothing the agent reads back as memory. The secret check runs before a write is spooled, so a secret never reaches the local file. `drain_spool` skips a write whose owner was deleted while it waited, and the delete function clears that owner's entries from the set-aside file. The set-aside file has a size limit and an expiry, and job rows and measure rows hold ids, counts and an error message, never the content of a write (`reference/every-store.md`, sections 5 and 10). (ours)
- **A job ends.** Each job row counts its tries, and each claim adds one. A job that fails is taken again once its hold has passed. A last try that fails sets it to `failed` with its error. A claim that finds the tries used up sets it to `failed` too, so a worker killed on every try, with no error to catch, cannot pass the last try. A failed job waits for a person, and the measure `jobs set to failed` counts it. The hold is longer than the longest a job may take, like the lease on a claimed action: a job still running when its hold passes can be taken by a second worker, and the first worker's finish is then refused. (ours)

**Storage.**

- **Tables first.** Tables by default. One simple edges table (from, to, kind of link) when the agent needs simple relationships, such as who reports to whom, read one step at a time. A graph database, a separate database built around links between things, only when both hold: the questions follow links several steps away, or one person appears under many names across sources; and the team accepts a separate database and a model call on every save. The design states the choice and the reason. This skill writes no code that builds a graph. (ours)

**Tools.**

- **Name a tool only when the project has it.** A tool or product is named only when the project already uses it. When the design needs something the project has none of (a check of model output against a schema, tracing, which is a record of each step of a run with its timing, or versions of a prompt), say what is needed and name options once, with the simplest version in the project's own code always among them. Never require one. (ours)

## Failures

Section 11 of the design has one row for each of these that applies. Each row names its own test: a test named by one row is not named by another, and the test that reads a measure back is not one of them.

| What fails | Needed when | What the build does |
|---|---|---|
| `memory store slow or down` | always | Reads are cut off at the turn's time allowed and the reply is built without memory. The turn's actions are blocked, and with the store down nothing can be claimed, checked or confirmed. Writes the turn makes wait in the spool, and counting goes on in the process. Whatever the agent shows about the outage comes from the app's own state, not from the store. |
| `search or embedding service down` | the agent uses keyword or embedding search | The search returns nothing, the reply is built without it, saves queue their embedding for later. A search service is not the memory store: the turn's memory is not marked missing, so its actions follow the row. |
| `broken model output` | a model writes memory | The schema check drops it after one retry (`reference/feedback-and-improvement.md`). Nothing is saved. |
| `a background job crashes partway` | always | Each job is safe to run again: it works in transactions and marks what it finished. It is taken again after its hold, and after its last try it is set to `failed` for a person. |
| `the queue down` | someone waits live and a model writes memory | Jobs are rows written in the same transaction as the record that needs them (called an outbox), so none is lost, and they run when the queue is back. |
| `counters drifting` | a fact has no end | The counters are recounted from the fact events, on a timer and on demand, by the same function as the roll-up. |
| `a bad extraction prompt shipped` | a model turns text into facts | Its facts are listed by prompt version and marked for review, and the earlier version is made live again (`reference/feedback-and-improvement.md`). |
| `the scheduler down` | something wakes the app | v0.1's catch-up runs the missed firings, each stopped by its key or its premise if it should not act. |
| `cleanup not running` | always | v0.1's expiry on read keeps expired items out, and the age of the oldest expired row is watched. |

"A model writes memory" means A9 names `a model turns text into facts`, or a section 3 row has the source `agent worked out`. "Always" means every design that saves something besides the run log. In section 11, **Answers** starts with `without memory`, `as usual` or `none` (nobody waits for an answer). **Actions** starts with `blocked`, `as usual` or `none` (the agent has no actions). A note may follow the value; it is not a blank. There is no value for an agent that stops answering. When the memory store is down, actions are `blocked`.

## Measurements

Section 12 of the design has one row for each of these that applies: where the number is recorded, and its alert line. An alert line is `above <number> <of what>`, `below <number> <of what>`, or `none: <why>`. Its number is a `default` like any other, and is in section 10. A share is at most 100 percent, so an alert above 100 percent on a share never fires. The build stores what the last column says, records each measure where its row says, and a test reads at least one back.

| Measure | Needed when | What it tells you | What to record |
|---|---|---|---|
| `correction rate per kind` | a fact has no end | A kind whose rate climbs is being saved wrong, or going stale faster than its review age allows. | The fact events (`confirmed`, `corrected`, `contradicted`) with each fact's kind. |
| `share of facts past review` | a fact has no end | A share that keeps growing means the agent asks too rarely for the review ages set. | Each fact's last confirmed time and wait. |
| `saved wrong vs world changed` | a model turns text into facts | Many `saved wrong` means the extraction prompt is the problem. Many `world changed` means the review ages are too long. | Each correction event with its reason. |
| `memory read time for the slowest 5%` | someone waits live and the agent reads memory | The time that 95 of every 100 turns' reads finish within. When it comes near the time allowed, more turns are about to run without memory. | The read time of each turn, on the turn's row. |
| `extra model calls per turn` | a model writes memory | Calls creeping up toward the cap mean memory work is moving back in front of the reply, and each one costs time and money. | The extra calls each turn made, on the turn's row. A call queued past the cap is not one. |
| `queue lag` | someone waits live and a model writes memory, or A9 says high volume | How long a job waits for the worker. A growing lag means what the person said in one turn is not there for the next. | Each job's time written and time claimed, and the oldest job still waiting. |
| `share of turns run without memory` | the agent reads memory | Reads timing out and a store going down show up here first. | Whether each turn's memory arrived, on the turn's row. |
| `facts saved per run` | section 3 has a Semantic memory row | A sudden rise often means the extraction step is saving noise. A drop to nothing means it stopped. | The number of facts each extraction job saved, on its job row. |
| `tasks closed as no longer valid` | a task has a premise | How often records change under a scheduled task. A sudden rise can mean records are being changed in bulk. | Each task's status and when it was set. |
| `writes dropped` | a model writes memory | A write the app could not make: a turn's save or queued job lost while the store was down, or numbers of the measures lost. Any one is an alert. | Each write dropped because the spool was full (`writes_dropped`), each spool entry set aside because it could not be written (`writes_set_aside`), and the count of numbers a full buffer pushed out (`numbers_dropped`). |
| `jobs set to failed` | a model writes memory | Work the person expects done that never was: an extraction not saved, a summary not written. Each waits for a person. Any one is an alert. | Each job's status and its last error, on its job row. |
| `risky actions waiting for confirmation` | a risky action rests on a fact with no end | A long list means the facts behind risky actions go stale before they are used: the freshness window or the review ages need a look. | Each risky action's status while it waits. |

## Code to build

- **One time allowed per turn.** When someone waits live, the turn starts with a deadline, and every memory read before the model call gets what is left of it. Use the database client's own time limit where it has one: a read left running in the background still holds a connection. A store that is down is the same case as a slow one. The turn remembers whether its memory arrived.
- **The guard.** The function every action passes through (`run_action` in `reference/side-effects.md`) calls the guard first. The guard refuses the action when this turn's memory did not arrive, or when the store does not answer a quick check.
- **The job rows and the worker.** A job is a row in the app's own database, written in the same transaction as the record that needs it. That is an outbox: a queue kept as rows in the app's own database, so a queue product that is down loses nothing. A worker claims each waiting job in one transaction, with a hold like a task's claim, runs it and marks it finished. The claim adds one to the job's tries, and sets a job whose tries are used up to `failed`. A job that crashed is taken again once its hold has passed, and does only the part it had not finished. A finish is refused once another worker holds the job.
- **The spool.** A small local file for the writes a turn makes while the store is down, written by a timer job once the store answers. Each write in it inserts or does nothing, and an entry that cannot be written goes to a second file, set aside for a person.
- **The recount** (when the design has a roll-up). One function sets a fact's counters from all its events. The roll-up runs it for the facts touched since its last run, the repair for every fact.
- **The measures.** Each measure is kept in the process and written by a timer job where its row in section 12 says, from what the last column of the table above stores, with the count of numbers a full buffer pushed out. Its alert line is read from configuration.

Sketch, to adapt:

```python
BUFFER = deque(maxlen=MEASURE_BUFFER)        # in the process: counting never touches the store and never fails
DROPPED = {"numbers": 0}                     # how many numbers a full buffer pushed out, kept apart from it
SPOOL = deque()                              # in the build, a small local file kept across restarts
SET_ASIDE = []                               # spool entries that can never be written, kept for a person (a file too)

def keep(row):
    if len(BUFFER) == BUFFER.maxlen:
        DROPPED["numbers"] += 1              # the oldest number goes out, and is counted
    BUFFER.append(row)

def count(name):
    keep(("count", name, 1, now()))

def flush_measures():                        # timer job: writes the buffer where section 12 says
    rows, dropped = list(BUFFER), DROPPED["numbers"]
    extra = [("count", "numbers_dropped", dropped, now())] if dropped else []
    try:
        db.insert_measure_rows(rows + extra)
    except StoreDown:
        return                               # kept in the process, written by a later run
    for _ in rows:
        BUFFER.popleft()
    DROPPED["numbers"] -= dropped

def start_turn(turn_id, allowed_ms):         # one time allowed for all the turn's reads
    return Turn(id=turn_id, deadline=clock_ms() + allowed_ms, memory_ok=True, read_ms=0, extra_calls=0, queued=[])

def read_memory(turn, read):
    """Fail open. Each read gets what is left of the turn's time allowed, and a store that is down is the same case.
    Called by the turn for each read before the model call, such as lambda: list(get_facts(owner, scope, now()))."""
    started = clock_ms()
    try:
        if turn.deadline <= started:
            raise TimedOut()
        return run_with_timeout(read, turn.deadline - started)
    except (TimedOut, StoreDown):
        turn.memory_ok = False               # this part of the call is left empty in its place, and the call says so
        return []
    finally:
        turn.read_ms += clock_ms() - started

def end_turn(turn):                          # once the reply has gone
    for kind, record_id in turn.queued:      # work past the cap, written now so a slow store never held the turn
        write_or_spool("queue_for_later", kind, record_id)
    keep(("turn", turn.id, {"memory_ok": turn.memory_ok, "read_ms": turn.read_ms, "extra_calls": turn.extra_calls}, now()))

def store_is_up():
    try:
        run_with_timeout(db.ping, PING_MS)
        return True
    except (TimedOut, StoreDown):
        return False

def guard_action(action, memory_ok):
    """Fail closed. run_action (reference/side-effects.md) calls this first. A turn whose memory did not arrive, or a
    store that is not up, has no confirmed fact, approval or claim to stand on, so the action does not happen."""
    if not memory_ok or not store_is_up():
        raise Blocked(action, "memory could not be read")

def save_message(message):                   # the outbox: the job row is written with the record that needs it
    with db.transaction():                   # each write inserts, or does nothing when the row is there, so a write
        db.insert_message_if_new(message)    # the store already holds, sent again from the spool, changes nothing
        db.insert_job_if_new("extract_facts", message.id, created_at=now())

def queue_for_later(kind, record_id):        # a job row like any other, done by the worker after the reply
    db.insert_job_if_new(kind, record_id, created_at=now())

WRITERS = {"save_message": save_message, "queue_for_later": queue_for_later}

def write_or_spool(name, *args):             # a write the turn makes never fails the turn
    try:
        WRITERS[name](*args)
    except StoreDown:                        # only a store that is down: any other error reaches the caller
        check_secrets(args)                  # the secret check runs before a write reaches the local file
        if len(SPOOL) < SPOOL_MAX:
            SPOOL.append((name, args))       # written by drain_spool once the store is back
        else:
            count("writes_dropped")          # the spool is full: dropped and counted

def drain_spool():                           # timer job
    while SPOOL:
        name, args = SPOOL[0]
        if owner_was_deleted(args):          # its owner was deleted while it waited: it is never written back
            SPOOL.popleft()
            continue
        try:
            WRITERS[name](*args)
        except StoreDown:
            return                           # still down: the next run tries again
        except Exception as error:           # an entry that can never be written is set aside for a person and
            SET_ASIDE.append((name, args, str(error)))   # counted, and the entries behind it are still written
            count("writes_set_aside")
        SPOOL.popleft()

def claim_job(job_id):
    """One transaction, like claim_action in reference/side-effects.md. Adds 1 to the job's tries. A job whose tries are
    used up is set to failed here, so a worker killed without an exception cannot pass the last try. Its claim is left
    as it is, so a last try that is still running can still end the job (end_job)."""
    with db.transaction():
        job = db.job(job_id)
        if job.status not in ("waiting", "running") or (job.status == "running" and job.held_until > now()):
            return None                      # finished, failed, or held by another worker
        if job.tries >= MAX_JOB_TRIES:
            db.update_job(job_id, status="failed", error=job.error or "no tries left")
            return None
        claim = Claim(id=new_id(), tries=job.tries + 1)
        db.update_job(job_id, status="running", claim=claim.id, tries=claim.tries, held_until=now() + JOB_HOLD,
                      claimed_at=job.claimed_at or now())   # the first claim ends the wait queue lag measures
        return claim

def end_job(job_id, claim, **fields):
    """Refused once the hold passed and another worker took the job: its claim is then no longer this one. A last try
    that finishes after another worker found no tries left and set the job to failed still ends it: the work is done
    and saved once, so the job is done, with no error left on it."""
    with db.transaction():
        if db.job(job_id).claim != claim.id:
            return False
        if fields.get("status") == "done":
            fields["error"] = None           # clears "no tries left" set by a second worker while this try ran
        db.update_job(job_id, **fields)
        return True

def run_waiting_jobs():                      # the worker, after the reply. Safe to run twice and after a crash
    for job in db.jobs_to_run(now()):        # waiting, or running with its hold passed
        claim = claim_job(job.id)
        if claim is None:
            continue                         # another worker has it, it is finished, or its tries are used up
        try:
            saved = JOBS[job.kind](job.record_id)   # marks what it finished, each part in its own transaction
        except Exception as error:
            last = claim.tries >= MAX_JOB_TRIES
            end_job(job.id, claim, status="failed" if last else "running", error=str(error))
            continue                         # not the last try: taken again once its hold has passed
        end_job(job.id, claim, status="done", saved=saved)

def set_counts(fact_id):                     # one recount for the roll-up and the repair
    confirmations, corrections, times_seen = rebuild_counters(fact_id)   # reference/feedback-and-improvement.md
    db.update_fact(fact_id, confirmations=confirmations, corrections=corrections, times_seen=times_seen)

def record_event_rolled_up(fact_id, what, who, action_id, now, reason=None, grow=True):
    """record_event of reference/feedback-and-improvement.md when A9 names high volume, with the same arguments. It
    writes no counter. It still sets what every read needs at once: the last confirmed time and the wait (a version's
    first confirmation, grow=False, keeps the review age), and the zero wait of a contradiction."""
    with db.transaction():
        db.insert_fact_event(fact_id, what, when=now, who=who, action_id=action_id, reason=reason)
        db.insert_touched(fact_id)           # the roll-up recounts this fact
        if what == "confirmed":
            f = db.fact(fact_id)
            db.update_fact(fact_id, last_confirmed_at=now,
                           wait=min(f.wait * WAIT_MULTIPLIER, KIND[f.kind].cap) if grow else f.wait)
        elif what == "contradicted":
            db.update_fact(fact_id, wait=timedelta(0))   # due at once

def roll_up_counters():                      # timer job, when the design has a roll-up
    with db.transaction():
        touched = db.touched_rows()
        for fact_id in sorted({t.fact_id for t in touched}):
            set_counts(fact_id)
        db.delete_touched([t.id for t in touched])   # only the rows read: one written meanwhile waits for the next run

def repair_counters():                       # the failure row `counters drifting`, on a timer and on demand
    with db.transaction():
        for fact_id in db.all_fact_ids():
            set_counts(fact_id)

def extra_model_call(turn, kind, record_id, make_call, listed=False):
    """listed: the design lists this work under "Memory work before the reply". It runs in the turn and counts
    toward the cap; the checker holds the cap at least the number of listed items, so it is never pushed back."""
    if not listed and turn.extra_calls >= MAX_EXTRA_CALLS:
        turn.queued.append((kind, record_id))    # over the cap: a job row, written by end_turn after the reply
        return None
    turn.extra_calls += 1
    return make_call()
```

`MEASURE_BUFFER`, `SPOOL_MAX`, `PING_MS`, `JOB_HOLD`, `MAX_JOB_TRIES` and `MAX_EXTRA_CALLS` are read from configuration, like every number of the design (`reference/every-store.md` gives starting values). `JOB_HOLD` is longer than the longest a job may take. `clock_ms` is a clock in milliseconds that only moves forward, `Turn` and `Claim` are small records, and `new_id` makes an id no other claim has. `JOBS` maps each kind of job to a function that takes the record's id and returns how many facts it saved, such as `{"extract_facts": lambda message_id: len(extract_facts(db.message(message_id), call_model))}` for the extraction job of `reference/feedback-and-improvement.md`, which marks each message it has done. A save after the reply is `write_or_spool("save_message", message)`. `check_secrets` is the secret check the write functions make (`reference/every-store.md`, section 10), raising on a secret, and `owner_was_deleted` says whether the owner of a write was deleted after it was spooled. In a design with a roll-up, every caller of `record_event` uses `record_event_rolled_up`, `confirm_seen_past_window` included, and anything that must read a counter at once, such as the reason for a correction (`correction_reason`), counts that fact's events with `rebuild_counters` in place of the counter. At high volume the repair runs over the facts in batches, each batch in its own transaction. The function that handles a turn calls `start_turn` first, passes each read that `build_context` makes (`reference/working-memory.md`) through `read_memory`, gives `turn.memory_ok` to `run_action`, and calls `end_turn` once the reply has gone. When nobody waits live, the design has no time allowed: the turn starts with the database client's own time limit, so a read that hangs still ends. `run_action` takes `memory_ok` with no default, so a caller that leaves it out fails. A task woken by the scheduler, which made no reads before a model call, passes `memory_ok=True` and is still blocked when the store is not up. `flush_measures`, `drain_spool`, `run_waiting_jobs`, `roll_up_counters` and `repair_counters` are timer jobs.

## Tests that try to break it

**Memory never makes the person wait.**

- A memory read slower than its time allowed is cut off and the reply is built without it. Give the read function a fake store whose reads sleep past the time allowed. The read returns within the time allowed, with no facts, and the turn is marked as run without memory. Then a fake store that raises: the same. Then two reads in one turn: together they take no longer than the one time allowed. Remove the timeout and the first test must fail. A read that raises any other error is not taken for a slow store: the error reaches the caller.
- Memory work a model does is queued and runs after the reply is returned. Count the model calls made before the reply is returned: the reply's own, and only what the design lists. When the reply returns, the job row exists and the facts it will save do not. Run the worker: they do.

**Embeddings are made on save, and a reranker earns its place.**

- Saving an item makes its embedding, and a search makes none for stored items. Count calls to a fake embedding service: saving makes one, a search makes one for the question.
- What reaches the model scores no lower on the test set with the reranker than without. Run the retrieval test set both ways.

**Volume: counters roll up and extra model calls are capped.**

- A turn that would make more extra model calls than the cap makes exactly the cap. The rest become job rows once the turn ends, and they add nothing to the turn's count. With a store slow to write, the calls past the cap do not hold the turn: the job rows appear when `end_turn` runs. Work the design lists before the reply runs even when the cap is reached.
- A use of a fact writes no counter on the fact's row, and after the roll-up the counters equal the events. Run the roll-up twice: nothing changes the second time. Repair, then roll up: nothing is counted twice. An event that commits after the roll-up read its rows is counted by the next run. Make the roll-up fail halfway: the counters are as they were.
- A moved version is still found in the history. Move a replaced version to cheaper storage and read the history: it is there, with its times.

**Failures, one per row of section 11.**

- Memory store slow or down: a fake store whose reads sleep past the time allowed, then one that raises. Ask a question: it is answered without memory, and says so when the answer depends on it. Ask for an action in that turn: it is refused. Call `run_action` without `memory_ok`: it fails, and nothing is sent. Remove the guard's check of the turn's memory: the action on the slow store must go ahead, so the test fails. Remove its check of the store: a task's action with the store down must then fail on its claim instead of being refused. Make the store that holds the measures down as well: the turn still answers, and the counts are written once it is back. Make the save after the reply meet the store down: the message waits in the spool and is written once the store is back; with the spool full it is dropped and counted. Spool a write the store did keep (its answer lost): the drain writes nothing twice and goes on. Put an entry that can never be written ahead of a good one: it is set aside and counted, and the good one is written. Make a write fail for another reason while the store is up: the error reaches the caller and nothing is spooled. Fill the buffer of measures past its size with the store down: the count of numbers it pushed out is written once the store is back.
- Search or embedding service down: a search client that raises. The reply is built with no search result, and a save puts its embedding in the job rows for later.
- Broken model output: the extraction test of `reference/feedback-and-improvement.md`. Broken output twice saves nothing.
- A background job crashes partway: a job stopped by an exception after its first item. Run the worker again once the hold has passed: it finishes the rest, and the first item is not done twice. A job that fails does not stop the jobs after it. A job that always fails is `failed` after its last try and is not taken again. A worker killed on every try, with no exception to catch, stops at the last try too: the next claim sets the job to `failed`. A job slower than its hold is taken by a second worker, and the first worker's finish is refused.
- The queue down: save a message and do not run the worker, or make the queue client raise. The job row is still there. Run the worker: the job runs once. Make the transaction fail after the message is written: no job row exists either.
- Counters drifting: change a counter by hand. The recount from the events puts it back, on its timer and when asked.
- A bad extraction prompt shipped: list the facts one prompt version made, mark them for review, and make the earlier version live. The next extraction uses the earlier version.
- The scheduler down: v0.1's missed-firing test. Start the app after a firing was missed: it runs once, and a firing whose key or premise says not to act does nothing.
- Cleanup not running: v0.1's expiry-on-read test. An expired item is not returned with the cleanup never run.

**Measurements.** Each measure on the list is worked out from what the build stored and nothing else: run turns, jobs and corrections, then compute each number from the stored rows alone, `writes dropped` and `jobs set to failed` included.

## In the design file

```
- Storage: tables. Roles and preferences are single facts looked up by person, and no question follows a link
- Memory work before the reply: the read-back of a contact preference the reply states: the person must see it in the same answer
- Memory reads before the model call: at most 300 ms, then the reply goes on without them
- Reranker: none: the right note is in the 5 results that reach the model for 46 of 50 test questions

## 11. Failures
| What fails | Answers | Actions | Test |
|---|---|---|---|
| memory store slow or down | without memory, and the reply says it could not check what it knows | blocked | test_store_down_answers_and_blocks_actions in tests/test_failures.py |
| cleanup not running | as usual, expired items are still left out on read | as usual | test_expired_item_not_returned_without_cleanup in tests/test_failures.py |

## 12. Measurements
| Measure | Recorded in | Alert line |
|---|---|---|
| share of turns run without memory | the measures table, one row per hour | above 5 percent |
| facts saved per run | the run log, one number per run | none: watched by hand in the first month |
- A measure is read back by: test_turns_without_memory_is_counted in tests/test_measures.py

## 13. Volume
- Expected volume: 2,000 people, about 30 facts each, 20,000 runs a day (the person's figures)
- Counters are rolled up every: 15 minutes
- Partition key: team
- Replaced versions move to cheaper storage after: 12 months
- Indexed columns: facts: team, kind, subject among current rows. fact events: fact id, time
- Extra model calls per turn: at most 2 calls
```

The `Storage` line is in section 3, the two `Memory ...` lines in section 4 and the `Reranker` line in section 6. Sections 11 to 13 come after section 10. Each number in these lines is in section 10 with its source: the time allowed is a `requirement` or a `default`, each alert line's number, the roll-up interval, the age at which replaced versions move, and the cap are `default`, the expected volume is a `requirement` (the person's figures) or `data` (measured), a reranker's two settings (how many results it takes and keeps) are `default`, and its two counts from the test set are `data`. The expected volume gives its figures in digits with the word after each.
