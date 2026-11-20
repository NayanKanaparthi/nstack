# Facts with no end, conflicts, and what the model extracts

**In plain words:** some facts are never ended by anything the app hears about. An expiry date invented for such a fact would either delete facts that are still true or keep facts that have become false. So the fact is kept, and code counts the confirmations and corrections it gets, to tell how sure the agent can still be. (ours)

Example: "Dana is the team lead." "Sam wants reminders by email, not chat." Nothing tells the app the day either stops being true, and people rely on both.

**When to read:** a section 3 row has the expiry `no end, checked by evidence`, or A9 names `several routes change a fact`, or A9 names `a model turns text into facts`. The first part of this file is for facts with no end, the second for a fact more than one route can change, the third for a model that turns text into facts. Read the parts the agent needs.

## Questions

- E1. Which kinds of fact have no end? Nothing tells the app when they stop being true, and people rely on them or an action is decided by them.
- E2. For each, how soon should it be looked at again, and what is the longest it may go without being confirmed?
- E3. Does the owner see what the agent does with the fact, and where?
- E4. Which routes can change the same fact (the person in chat, a screen, the agent, an import), and can more than one copy of the agent run at once? Can two people set the same fact?
- E5. Does a model turn text into facts? Is the project in Python, and does it already use DSPy?
- E6. Who may approve a change to the extraction prompt?

## Defaults

**Facts with no end.**

- **Only a fact has no end.** Only a Semantic memory row may have the expiry `no end, checked by evidence`. It may be joined with `replaced when <what>` and with nothing else. (ours)
- **A fixed list of kinds.** Each row with no end is one kind, and the kinds are fixed when the design is written. A model that proposes a fact picks a kind from the list. Code saves anything else under the one row the design names for it, with that row's values, and never invents a kind. When that row has no end too, its review age and cap are the shortest. A fact saved under that row by a model enters unconfirmed, like any fact a model proposes, and is shown as a fact only once a person confirms it; that confirmation is its first `confirmed` event. This list is not the line `Kinds an owner can set for themselves`: a kind can be on either, both or neither. (ours)
- **A review age and a cap per kind.** Each kind has a starting review age and a cap, each a number with its source in section 10. (ours)
- **The wait grows with each confirmation.** Each fact keeps the time it was last confirmed and its current wait. A new version starts with the kind's review age as its wait, and its last confirmed time is the time it was saved; no `confirmed` event is written for that. The yes that turns a waiting copy into a fact is its first `confirmed` event and sets its last confirmed time, but does not multiply the wait: a new version starts at the review age whichever route made it. A confirmation multiplies the wait (starting value 2 times) up to the cap, and sets the last confirmed time to now. A correction makes a new version, which starts again at the kind's review age. `save_fact` (`reference/semantic-memory.md`) is the one function that writes a fact, whatever the route: when it replaces a fact with no end, it records a `corrected` event on the old version, with its reason, in the same transaction. (ours)
- **Due is worked out on every read.** A fact is due when now is later than its last confirmed time plus its wait. The read function works this out each time it runs. No job marks facts as due. (ours)
- **A due fact is still shown.** It reaches the model with when it was last confirmed ("last confirmed 14 months ago"), so the model can hedge and the person can see it. It is never dropped for being due, and never shown as fresh. A due fact is not an expired one: an expired fact is left out by the read function, a due one is returned with its label. The label is part of the fact's own line in the facts part of the model call, which keeps its place in the fixed order (`reference/working-memory.md`), and counts against that part's budget. (ours)
- **One question, at a natural moment.** When the owner of the fact sees what the agent does with it, the agent asks about a due fact when the fact is about to be used in a reply to that person. One open question per fact, not one per turn. (ours)

**Evidence, counters and trust.**

- **Fact events are the record.** A fact events table holds one row per event: the fact id, what happened (`confirmed`, `corrected`, `used and seen`, `contradicted`), when, who, and the action or reply it belongs to. Rows are added and never changed, which makes it an append-only log: a table that only ever gains rows. The facts live on after the retention rule removes their older events, so when it removes a fact's events it writes, in the same transaction, that fact's totals up to then into one carried-forward row for the fact. The counters, and the recompute job's counts, are that row plus the events kept. In section 3 it is one row with the memory type `Fact events`. It is not the audit log. The audit log says who changed memory; fact events say what was learned about a fact. A correction writes to both. (ours)
- **Counters are written with their event.** Each fact carries counters: confirmations, corrections, times used and seen. A counter is written in the same transaction as the event it counts, and all counters can be rebuilt from the events alone. When A9 names `high volume`, a timer job rolls the counters up from the events instead, and they lag the events by at most its interval; a confirmation still sets the last confirmed time and the wait when it is recorded (`reference/production.md`). (ours)
- **Trust starts from the source.** Trust in a fact is `(confirmations + prior confirmations) / (confirmations + corrections + prior total)`. The prior is two numbers that stand in for evidence the fact does not have yet. Adding them is called smoothing: a few made-up answers added to a count, so that one or two real answers cannot swing it. The prior starts from the fact's source: the design gives each source a prior written `<a> of <b> answers`, such as `9 of 10 answers` for `user stated`. (ours)
- **Then from the kind's own rate.** Once a kind has enough events of its own, its measured rate replaces the source's prior: prior confirmations become `rate x prior total`. "Enough" is a stated rule: the interval that holds the kind's true rate at a set confidence (starting value 95 percent) is narrower than a set width (starting value 20 points). The sketch uses the Wilson interval, a range for a rate worked out from the count of yes answers and the count of all answers, which stays close to its stated confidence even with few answers, less so when the rate is near 0 or 1. Both numbers are `default`. (ours for using it here; the interval and how it behaves: Agresti and Coull, "Approximate is better than 'exact' for interval estimation of binomial proportions", The American Statistician 52(2), 1998, pages 119 to 126)
- **A job learns each kind's numbers.** A job recomputes, for each kind, its measured rate (confirmations over confirmations plus corrections, from the events) and its learned review age: the age by which a set share of the kind's facts had been corrected (starting value 10 percent). A fact not corrected so far counts as "still true up to its present age", not as "never wrong". Working out how long things last from records where many have not ended yet is called survival analysis. The learned review age is offered as a `data` number for section 10. It never replaces a number by itself. (ours)
- **An alert on a sharp drop.** The same job alerts when a kind's rate falls by more than a set amount between two runs (starting value 15 points). (ours)

**What counts as evidence.**

- **Every output records its facts.** Every reply and every action records the ids of the facts it used. (ours)
- **Three levels of evidence.** Explicit: the person says yes to a read-back of the fact. That is a `confirmed` event. Seen: output the fact drove was shown to the person, they had a way to object, and no correction came within a window (starting value 7 days). That is a `used and seen` event, and it counts as one confirmation only once the window has passed: then the recompute job records a `confirmed` event from `seen, no correction`, so every counter stays a count of events. Unseen: output nobody looked at, or looked at with no way to object. It counts for nothing. (ours)
- **Output says what drove it.** Output that a fact drove says so, in words the person can act on ("in Spanish, as you asked"). (ours)
- **The person sees, fixes and deletes.** The person can see, fix and delete their own facts. A fix is a correction, which makes a new version. A delete removes the fact everywhere, its versions and its events included, and the audit log keeps the record that a delete happened. (ours)
- **An undo is a contradiction.** When the person undoes something the agent did, code records a `contradicted` event on each fact that action used. A contradiction counts as a correction in the trust formula, and makes the fact due at once. (ours)

**When several routes change a fact.**

- **Find the slot first.** When a fact arrives, code finds the current fact in its slot (owner, kind, subject: `reference/semantic-memory.md`). When the kind has no subject to match on, code finds the current facts of that kind for the owner that are similar. (ours)
- **The model answers one of three words.** Where a model is in the path, it is shown the new fact and the current one and answers `same`, `update` or `contradiction`. Code applies the answer. `same` counts as a confirmation only when the new fact is the person's own words (`user stated`); the same value inferred again is no evidence. Any other answer changes nothing. The model never deletes and never picks the winner. (ours)
- **Code decides who wins.** The person's own words (`user stated`) beat an inferred value (`agent worked out`, `outside content`), whichever came last. From one source, newer beats older. When two people may both set the fact and they disagree, the fact is marked `disputed`, neither value is used as settled, and the agent asks. The person's own words also stay current when a system record that disagrees arrives later: the record is saved unconfirmed and the agent asks the person which is true, unless the design names that system as the one that owns that kind of fact. Then the record wins. This comes before the default that a system record enters confirmed (`reference/semantic-memory.md`). The other way round, the person's own words replace a current system record, unless the design names that system as the one that owns that kind of fact: then their words are saved unconfirmed and the agent asks them. Either way one question is asked: while it is open, the same disagreement arriving again only updates the waiting copy, and `save_fact` writes that update, so the secret check and the audit line run for it as for any write. (ours)
- **The person's words correct a model's reading.** A model's reading waits unconfirmed. When the person's own words fill its slot and disagree with it, `save_fact` closes the reading as replaced, reason `saved wrong`, keeping its prompt version. Their answer "no, it is X" to code's read-back of the reading does the same through the confirm step (`confirm_fact`, `reference/semantic-memory.md`), and X is saved as their own words. These are the corrections the extraction test set is built from. A reading saved longer ago than a set window (starting value 14 days, a `default` in section 10 measured by the share of test set rows a person rejects on review) may have been right when it was read, so when only their later words disagree with it, it is closed as `world changed` and makes no row; a reading whose read-back they answer is `saved wrong` at any age. The test set grows only from a one-value kind the owner may set, with the value on its allowed list: a free-text kind, a list kind, or a reading someone other than its owner confirms makes no row. This version has no route for those. (ours)
- **Replace only what you read.** Replacement is compare-and-swap: replace version N only if N is still the current version. If someone changed it in between, the change is refused, and code reads the current version again and decides again. With the database's one-current-fact rule, two replacements at the same moment leave one current fact, and both are in the history. (ours)

**What the model extracts.**

- **Each fact carries its prompt version.** Every fact a model proposed records the version of the extraction prompt that made it. (ours)
- **Checked against a schema.** What the model proposes is checked in code against a schema before anything is saved: the fields, their types, a kind from the list. Broken output gets one retry. If the retry is broken too, nothing is saved and the run log says so. (ours)
- **Safe to run twice.** The extraction job run twice on the same input saves nothing new the second time. (ours)
- **Code sets the reason for a correction.** Every correction records a reason on the version it replaces, whatever the kind, set by a rule in code and never by the model: `saved wrong` when the corrected version was never confirmed after it was saved, `world changed` when it was confirmed at least once, and for a model's reading older than the window above that only the person's later words disagree with. (ours)
- **A test set from what was saved wrong.** The extraction test set is built from the `saved wrong` corrections of facts a model proposed, the ones with a prompt version (the person's words correcting a model's reading, above): the text the fact was read from, and the corrected kind, subject and value. A fact the person typed is not an extraction error, so its corrections stay out. A script scores a prompt against it. The score is plain code with no model in it. It first runs the app's own extraction check on the output: output the app would refuse scores 0. Otherwise an example scores the share of the output's items for the expected kind and subject that hold the expected value: 1 needs the right value and no other value for that slot, so extra values and a spray of guesses score lower. (ours)
- **Improved offline, approved by a person.** Improving the prompt happens offline. A person approves every change, and a change whose score is lower than the live prompt's is refused. (ours)
- **A bad version can be found.** Facts can be listed by extraction prompt version, and every fact of one version can be marked for review in one step: each becomes due at once. (ours)
- **An optimizer in Python, the same loop by hand elsewhere.** In a Python project the skill sets up an optimizer script for this prompt (below). In any other project it sets up the same loop by hand: the test set, the scoring script, a place for candidate prompts and the approval step, and it names the options once (see Tools). (ours)

**The optimizer script.** Checked against `gepa` 0.1.4 and `dspy` 3.5.0, as installed.

- **Which package.** `gepa` is a Python package that improves a prompt by having a model read how the prompt scored and propose new versions, keeping the ones that score best (its own description, version 0.1.4). DSPy is a Python framework for programming model calls, and it carries its own GEPA. When the project already imports `dspy`, use DSPy's GEPA (`dspy.GEPA`). Otherwise use the `gepa` package. If neither is installed, suggest `gepa` once, say what it is for, and install it only when the person agrees. If they decline, the design says `by hand` and section 10 records the choice. (ours)
- **Offline only.** The script runs when a person runs it, never from a run of the agent. (ours)
- **A budget the person sets.** The budget is the most metric calls one run may make. It is a `policy` number, because each metric call is a paid model call. GEPA checks the budget only between its rounds, and one round can spend more than is left, so a run can pass the budget: with 7 scoring rows, a budget of 10 made 20 calls and a budget of 60 made 62. The script writes the real count into the candidate file and prints it after every run, so set the budget knowing a run can pass it. It refuses, before any model call, a budget not above its number of scoring rows (a third of the test set): scoring the live prompt alone would spend it, and nothing would be proposed. (ours; the counts were measured on gepa 0.1.4 with stub models)
- **A minimum of examples.** The script refuses to run when the test set has fewer examples than a minimum (`default`, starting value 20), before any model call. (ours)
- **A candidate, never the live prompt.** It writes its best candidate to a file with the status `waiting for approval`, the version it was made from, and both scores. When no prompt scores above the live one, it writes no candidate. It never writes the live prompt. (ours)
- **A person approves.** A person the design names approves a candidate. Approval is refused when the live prompt has changed since the candidate was made, or when the candidate scores lower. An approved candidate becomes a new prompt version, and the facts it writes carry that version. (ours)
- **Tests with stub models.** Its tests use stub models: plain functions. No network and no model call. (ours)

## Code to build

- **Columns on the facts table** (`reference/semantic-memory.md` has the rest): subject, true from, true until, and the database's rule of one current fact per slot. For a fact with no end: last confirmed, the current wait, and the counters (confirmations, corrections, times used and seen). For a fact a model proposed: the extraction prompt version. When several people can set one fact: a disputed mark.
- **The fact events table.** Append-only: the app's functions add rows and never change or delete one. Only an owner's delete and the retention rule remove rows. The retention rule (`remove_old_events`) first adds the totals of what it removes to the fact's carried-forward row, in the same transaction.
- **`is_due`.** Called inside the read function on every read.
- **`record_event`.** The one way an event is written, with its counters, in one transaction. Called inside another transaction (`save_fact` records a correction this way), it joins that one.
- **`trust`.** The formula above, with the switch from the source's prior to the kind's own rate.
- **`recompute_kinds`.** The job that sets each kind's rate and learned review age and alerts on a drop. It also calls `confirm_seen_past_window` for each fact with a `used and seen` event. It is a procedure in section 4, in code.
- **`settle`.** Where several routes change a fact: finds the slot, asks the model for one of three words if a model is in the path, decides who wins in code, and writes through `save_fact` with compare-and-swap (`if_current`). When a value waits for the person, one question is asked while it is open (`wait_and_ask`). For a kind with one value per slot. A procedure in section 4, in code.
- **`check_extraction` and `extract_facts`.** The schema check, the one retry, the prompt version on each fact, and the mark that makes a second run save nothing. A procedure in section 4, in code.
- **The test set and the scoring script.** Rows built from `saved wrong` corrections of facts with a prompt version (`extraction_test_set`), and a script that scores a prompt against them with no model in the score and the app's own `check_extraction` first.
- **The optimizer script and `approve`.** The script beside the tests, never imported by the app, and the one function that turns an approved candidate into a new prompt version.

Sketch 1 (evidence and due), to adapt:

```python
def is_due(fact, now):
    """Worked out on every read. No job marks facts as due."""
    return now > fact.last_confirmed_at + fact.wait

def get_facts(owner, scope, now):                    # v0.1's read function, with one more field on each fact
    for f in current_confirmed_facts(owner, scope, now):
        f.due = f.no_end and is_due(f, now)          # a due fact is still returned, labelled, never dropped
        yield f

def record_event(fact_id, what, who, action_id, now, reason=None, grow=True):
    """what is confirmed, corrected, used and seen, or contradicted. Events are only ever added. reason is set on a
    `corrected` event (correction_reason, sketch 3). grow=False for a version's first confirmation, the yes that makes
    a waiting copy a fact: it starts at the review age. Called inside another transaction, it joins that one."""
    with db.transaction():
        db.insert_fact_event(fact_id, what, when=now, who=who, action_id=action_id, reason=reason)
        if what == "confirmed":
            f = db.fact(fact_id)
            db.update_fact(fact_id, confirmations=f.confirmations + 1, last_confirmed_at=now,
                           wait=min(f.wait * WAIT_MULTIPLIER, KIND[f.kind].cap) if grow else f.wait)
        elif what in ("corrected", "contradicted"):
            f = db.fact(fact_id)
            db.update_fact(fact_id, corrections=f.corrections + 1,
                           wait=timedelta(0) if what == "contradicted" else f.wait)   # contradicted: due at once
        elif what == "used and seen":
            f = db.fact(fact_id)
            db.update_fact(fact_id, times_seen=f.times_seen + 1)       # a confirmation only once its window passes

def confirm_seen_past_window(fact_id, now):
    """Run by the recompute job. A `used and seen` event whose window passed with no correction becomes, once,
    a `confirmed` event from `seen, no correction`, so every counter stays a count of events."""
    events = db.fact_events(fact_id)
    done = {e.action_id for e in events if e.what == "confirmed" and e.who == "seen, no correction"}
    for e in events:
        if e.what != "used and seen" or e.action_id in done or now < e.when + SEEN_WINDOW:
            continue
        if any(c.what in ("corrected", "contradicted") and e.when <= c.when <= e.when + SEEN_WINDOW for c in events):
            continue                                                    # corrected inside the window: no evidence
        record_event(fact_id, "confirmed", "seen, no correction", e.action_id, now)
        done.add(e.action_id)

def interval_width(confirmed, total, z=Z_FOR_95_PERCENT):
    """Width of the Wilson interval on a rate, as a share between 0 and 1."""
    if total == 0:
        return 1.0
    p = confirmed / total
    return 2 * z * ((p * (1 - p) / total + z * z / (4 * total * total)) ** 0.5) / (1 + z * z / total)

def trust(fact, kind_stats):
    a, b = PRIOR[fact.source]                         # like 9 of 10 answers
    k = kind_stats[fact.kind]
    if interval_width(k.confirmed, k.confirmed + k.corrected) < SWITCH_WIDTH:
        a = b * k.confirmed / (k.confirmed + k.corrected)   # the kind's own rate replaces the source's prior
    return (fact.confirmations + a) / (fact.confirmations + fact.corrections + b)

def counts(events):
    """(confirmations, corrections, times used and seen) in a list of events."""
    return (sum(e.what == "confirmed" for e in events),
            sum(e.what in ("corrected", "contradicted") for e in events),
            sum(e.what == "used and seen" for e in events))

def rebuild_counters(fact_id):
    """The events are the record. This must give what the fact row already holds: the totals the retention rule
    carried forward, plus the events kept."""
    carried = db.carried_forward(fact_id)             # (0, 0, 0) until the retention rule removes some of its events
    return tuple(a + b for a, b in zip(carried, counts(db.fact_events(fact_id))))

def remove_old_events(fact_id, before):
    """The retention rule, run by cleanup. In the same transaction it adds the totals of the events it removes to the
    fact's one carried-forward row, so the counters can still be rebuilt after the events are gone."""
    with db.transaction():
        gone = [e for e in db.fact_events(fact_id) if e.when < before]
        db.carry_forward(fact_id, tuple(a + b for a, b in zip(db.carried_forward(fact_id), counts(gone))))
        db.delete_fact_events(fact_id, before)
```

Sketch 2 (several routes), to adapt. `record_event` is from sketch 1. `save_fact`, `source_for`, `KIND` and `STALE` are in `reference/semantic-memory.md`: `settle` decides, and `save_fact` is the one function that writes a fact.

```python
RANK = {"user stated": 2, "system record": 2, "agent worked out": 1, "outside content": 1}
OWNED_BY = {}    # from the design: a kind whose official copy is in a named trusted system, and that system

def save(new, **how):
    return save_fact(new.owner, new.scope, new.kind, new.value, new.route, new.sender, new.came_from,
                     subject=new.subject, prompt_version=new.prompt_version, **how)

def wait_and_ask(new, current, person):
    """The arriving value waits unconfirmed and one question goes to the person. While a question about this fact is
    open, another arrival only updates the waiting copy: one open question per fact, not one per arrival."""
    waiting = db.open_question_about(current.id)          # the waiting copy an open question holds, or None
    if waiting is not None:                               # the question shows the newest arrival, written by save_fact
        return save(new, replaces_waiting=waiting)      # it stays unconfirmed: only its value and where it came from change
    got = save(new, unconfirmed=True)
    if got is not None:                                   # None: the same value already waits, there is nothing to ask
        ask_which_is_true(person, current.id, got)        # opens a question about the fact until the person answers
    return got

def settle(new, verdict_from_model=None):
    """Code decides. The model may only say same, update or contradiction about a pair it is shown.
    new holds what save_fact takes. Its source is worked out by code from the route, as save_fact does.
    For a kind with one value per slot: a list kind's items each carry their own subject, and are added, not replaced."""
    source = source_for(new.route, new.sender, new.owner, new.kind, new.value)
    who = new.sender.id if new.sender else new.route
    while True:
        current = db.current_fact(new.owner, new.kind, new.subject or None)  # the slot
        if current is None:
            return save(new)
        verdict = verdict_from_model(new, current) if verdict_from_model else compare_values(new, current)
        if verdict == "same":
            if source == "user stated" and new.kind in KIND:              # only the person's own words confirm,
                return record_event(current.id, "confirmed", who, None, now())   # counted for a kind with no end
            return None                                                   # the same value inferred again is no evidence
        if verdict not in ("update", "contradiction"):
            return None                                                   # anything else changes nothing
        # An inferred value goes on to save_fact below, which saves it unconfirmed: it never beats their words.
        if source == "system record" and current.source == "user stated":
            if OWNED_BY.get(new.kind) != new.came_from:                   # their own words stay current
                return wait_and_ask(new, current, current.set_by)         # the record waits for them
            # the design names this system as the owner of this kind of fact: the record wins
        elif source == "user stated" and current.source == "system record":
            if OWNED_BY.get(new.kind) == current.came_from:               # the owning system's record stays current
                return wait_and_ask(new, current, who)                    # their words wait
            # no design names that system as the owner of this kind: their own words replace the record
        elif RANK[source] == RANK[current.source] and who != current.set_by and both_may_set(new, current):
            return db.mark_disputed(current.id, new)                      # two people disagree: ask, use neither
        got = save(new, if_current=current.id)                            # compare-and-swap, inside save_fact
        if got is not STALE:
            return got
        # someone else replaced it first: read the slot again and decide again
```

Sketch 3 (the extraction check), to adapt:

```python
def check_extraction(raw):
    """Returns the proposed facts, or None when the output does not fit the schema."""
    try:
        items = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(items, list):
        return None
    for it in items:
        if not isinstance(it, dict) or set(it) != {"kind", "subject", "value"}:
            return None
        if not all(isinstance(it[k], str) for k in it):
            return None
        if it["kind"] not in KINDS:
            it["kind"] = CATCH_ALL_KIND                                   # code, not the model, files it there
    return items

def extract_facts(message, call_model):
    if db.extraction_done(message.id, PROMPTS.live_version()):            # run twice, saved once
        return []
    for attempt in (1, 2):                                                # one retry, then nothing
        items = check_extraction(call_model(PROMPTS.live(), message.text))
        if items is not None:
            break
    else:
        log_step("extraction", "broken output twice, nothing saved")
        items = []
    with db.transaction():
        for it in items:                                                  # the model's reading: saved unconfirmed
            save_fact(message.owner, message.scope, it["kind"], it["value"], "message", message.sender, message.id,
                      subject=it["subject"], prompt_version=PROMPTS.live_version())
        db.mark_extraction_done(message.id, PROMPTS.live_version())
    return items

def correction_reason(old_version):
    """Set by code. Never taken from the model. A fact with no end counts its confirmations; any fact records who
    confirmed it (reference/semantic-memory.md), which is set when a waiting copy is confirmed."""
    return "world changed" if old_version.confirmations > 0 or old_version.confirmed_by else "saved wrong"

def extraction_test_set():
    """Rows of the extraction test set: the `saved wrong` corrections of facts a model proposed, each with the text the
    fact was read from and the corrected kind, subject and value. A typed fact has no prompt version and stays out."""
    rows = []
    for old in db.replaced_versions(reason="saved wrong"):   # each version replaced with that reason, whatever its kind
        if old.prompt_version is not None:
            new = db.fact(old.replaced_by)
            rows.append({"text": db.message_text(old.came_from), "kind": new.kind, "subject": new.subject,
                         "value": new.value, "prompt_version": old.prompt_version})
    return rows
```

Sketch 4 (the optimizer script), to adapt. It lives beside the tests, as `scripts/optimize_extraction.py` or the project's equivalent, and nothing the app imports may import it:

```python
"""Offline script. Proposes a better extraction prompt from the extraction test set.
It writes a candidate file for a person to approve. It never changes the live prompt.
Sketch for reference/feedback-and-improvement.md. Checked against gepa 0.1.4."""
import json
import os

import gepa
from gepa.adapters.default_adapter.default_adapter import EvaluationResult

BUDGET_METRIC_CALLS = 150      # policy: the person sets how much one run may spend. Read from configuration.
MINIMUM_EXAMPLES = 20          # default: below this the score moves too much from one example to the next


class TooFewExamples(Exception):
    pass


class BudgetTooSmall(Exception):
    pass


def same_text(text):
    return " ".join(str(text or "").lower().split())


def score_one(expected, response, check):
    """Deterministic code, no model. check is the app's own extraction check (sketch 3): output the app would refuse
    scores 0.0. Else the score is the share of the items for the expected kind and subject that hold the expected
    value: 1.0 needs the right value and no other value for that slot, and a spray of guesses scores low. Items for
    other slots are left alone, since the row does not know them."""
    items = check(response)
    if items is None:
        return 0.0, "the app's extraction check refuses this output"
    slot = [it for it in items if it["kind"] == expected["kind"]
            and same_text(it["subject"]) == same_text(expected["subject"])]
    if not slot:
        return 0.0, "no item for kind %r and subject %r" % (expected["kind"], expected["subject"])
    right = sum(same_text(it["value"]) == same_text(expected["value"]) for it in slot)
    return right / len(slot), "%d of %d items for kind %r and subject %r hold the value %r" % (
        right, len(slot), expected["kind"], expected["subject"], expected["value"])


def to_gepa(example):                              # one test set row -> gepa's default data item
    return {"input": example["text"], "additional_context": {},
            "answer": json.dumps({"kind": example["kind"], "subject": example["subject"], "value": example["value"]})}


def optimize(examples, live_prompt, live_version, task_lm, reflection_lm, check, out_dir,
             budget=BUDGET_METRIC_CALLS, minimum=MINIMUM_EXAMPLES, seed=0):
    """examples: rows of the extraction test set, each {"text", "kind", "subject", "value"}.
    task_lm(messages) -> str runs the extraction the way the app does. reflection_lm(prompt) -> str proposes.
    check(raw) is the app's own extraction check, the one extract_facts calls."""
    if len(examples) < minimum:
        raise TooFewExamples("%d examples, and the minimum is %d. Nothing was run." % (len(examples), minimum))
    data = [to_gepa(e) for e in examples]
    val = data[::3]                                # every third row scores candidates; the rest are learned from
    train = [d for i, d in enumerate(data) if i % 3]
    if budget <= len(val):                         # scoring the live prompt alone would spend it all
        raise BudgetTooSmall("a budget of %d metric calls is not above the %d scoring rows. Nothing was run."
                             % (budget, len(val)))

    def evaluator(item, response):                 # the form gepa's default adapter calls
        score, why = score_one(json.loads(item["answer"]), response, check)
        return EvaluationResult(score=score, feedback=why)

    result = gepa.optimize(
        seed_candidate={"extraction_prompt": live_prompt},
        trainset=train, valset=val,
        task_lm=task_lm, evaluator=evaluator, reflection_lm=reflection_lm,
        max_metric_calls=budget, seed=seed, display_progress_bar=False)
    scores = result.val_aggregate_scores           # index 0 is the seed, which is the live prompt
    best = result.best_idx                         # the first of the best, so a tie goes to the live prompt
    print("%d metric calls made, budget %d. A run can pass its budget." % (result.total_metric_calls, budget))
    if result.candidates[best]["extraction_prompt"] == live_prompt:
        print("No candidate written: no prompt scored above the live one.")
        return None
    candidate = {
        "status": "waiting for approval",
        "based_on_version": live_version,
        "prompt": result.candidates[best]["extraction_prompt"],
        "score_live": scores[0],
        "score_candidate": scores[best],
        "examples": len(examples),
        "metric_calls": result.total_metric_calls,
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "candidate-from-v%s.json" % live_version)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(candidate, f, indent=2)
    return path


def approve(candidate_path, person, prompts, may_approve):
    """The only way a candidate becomes live. prompts is the app's store of prompt versions."""
    if not may_approve(person):
        raise PermissionError(person)
    with open(candidate_path, encoding="utf-8") as f:
        c = json.load(f)
    if c["based_on_version"] != prompts.live_version():
        raise ValueError("the live prompt changed after this candidate was made. Run the script again.")
    if c["score_candidate"] < c["score_live"]:
        raise ValueError("the candidate scores lower than the live prompt")
    return prompts.add_version(c["prompt"], approved_by=person, score=c["score_candidate"])   # the new live version
```

`task_lm` is a function that takes the messages (a system message holding the prompt, a user message holding the text) and returns the model's text. Pass the same function the app uses for extraction, so the script measures what the app does. `check` is the app's own `check_extraction` (sketch 3): output the app would refuse scores 0, so the script never prefers a prompt the app cannot use. `reflection_lm` is a function that takes one prompt and returns text. Both may also be model names, which needs `pip install "gepa[full]"`. With `dspy.GEPA` the same loop is `dspy.GEPA(metric=..., max_metric_calls=..., reflection_lm=...)` and `.compile(student, trainset=..., valset=...)`, where the metric takes `(gold, pred, trace, pred_name, pred_trace)` and returns a score. Checked against gepa 0.1.4 and dspy 3.5.0. If the installed version differs, read its `optimize` signature before you write the script.

## Tests that try to break it

These are the tests behind the five standing tests `steps/3-design.md` adds for this file, in section 9's order. Each case is its own test.

"A fact with no end is checked on every read":

- Save a fact with no end and move the clock past its last confirmed time plus its wait. Read it with no job run. It reaches the model call, labelled with when it was last confirmed. With the due line taken out of the read function, the test fails.
- Confirm a fact again and again. The wait is multiplied each time and stops at the cap.
- Correct a fact whose wait has grown. The new version's wait is the kind's review age, its last confirmed time is when it was saved, and the old version has one `corrected` event with its reason, whichever route made the change (a form, `settle`, a confirmed read-back).
- When a row takes facts of no listed kind: have the model propose a kind that is not on the list. It is saved under that row, with that row's values.
- When the owner sees what their facts drive: use a due fact in two replies in a row. One question goes to its owner, and no second one while the first is open.

"Fact events are the record and the counters can be rebuilt":

- Try to change or delete a fact event through the app's own functions. Refused.
- After a mix of confirmations, corrections, uses and an undo, rebuild the counters from the events alone. They equal the counters on the facts. Remove the older events as the retention rule does: the rebuild still equals them.
- Give a kind events that leave its interval just wider than the set width, then add events until it is narrower. Trust uses the source's prior on the first side and the kind's own rate on the second.
- Run the recompute job: it sets each kind's rate and learned review age. Add corrections and run it again: it alerts when the rate drops by more than the set amount, and not when it drops by less.

"What a fact drove is recorded, and silence counts only when it was seen":

- Build a reply from a fact. The reply records the fact's id.
- Read a fact back to its owner and answer yes. A `confirmed` event is recorded.
- Show the owner output a fact drove and move the clock. Inside the window it counts for nothing. After the window, with no correction, it counts as one confirmation.
- Build output nobody sees, or that is seen with no way to object. Nothing is counted.
- Output a fact drove says so, in words the owner can act on.
- The owner fixes a fact on their screen. A correction is recorded and a new version made.
- Undo something the agent did. Each fact the action used has a `contradicted` event and is due at once.

"Two changes to one fact leave one current version, and code decides which":

- Start two replacements of the same version at the same moment, many times. Each time there is exactly one current fact, and both values are in the history.
- An inferred value arrives after the person's own words, and the person's words after an inferred value. The person's words win both times. A system record that disagrees arrives after the person's words: their words stay current, the record waits unconfirmed and the agent asks, and when the design names that system as the owner of the kind, the record wins. The same record arriving three times while the question is open asks once, and its second arrival carrying a card number is refused and leaves the waiting copy as it was, while the third updates it and writes an audit line. The person's words arriving after a current record replace it, and wait unconfirmed while the agent asks when that record's system owns the kind.
- Two values from one source: the newer one wins.
- Have the model answer `delete`, or anything but the three words. Nothing changes.
- When several people can set one fact: two of them set different values. The fact is marked disputed, neither value is used as settled, and the agent asks.

"Extraction output is checked, versioned and scored":

- Have the fake model return output that does not fit the schema, twice. Nothing is saved, and the run log says why. Broken once and good on the retry: the facts are saved.
- Run the extraction job twice on one input. The second run saves nothing.
- Save facts under two prompt versions. List the facts of one version and mark them for review: each is due at once, and the other version's facts are not.
- Correct a fact that was never confirmed: the reason is `saved wrong`. Correct one that was confirmed: `world changed`. A reason the model passes is ignored. Only the `saved wrong` corrections of facts with a prompt version reach the test set. A model's reading the person corrects, by their own words in its slot or by "no, it is X" to its read-back, is closed as `saved wrong` with its prompt version and becomes one row of the test set, which the optimizer's minimum counts. Their words one day inside the reading window and at the window: `saved wrong`. One day past it: `world changed`, and no row. "No, it is X" to the read-back of a reading far past the window: `saved wrong`.
- Score the same prompt twice: the same score. Output that scores 1 passes the app's own extraction check, and output that check refuses scores 0. Output with the right value and another value for the same slot, or a list of guesses, scores below 1. Offer a prompt that scores lower than the live one: refused.
- With an optimizer script: with one example fewer than the minimum, it stops before any model call and writes nothing. At the minimum, it runs. A budget not above the number of scoring rows is refused the same way.
- With stub models and a small test set, the script runs to the end, writes a candidate file, and the live prompt and its version are exactly as before. When no prompt scores above the live one, it writes no candidate.
- Approve the candidate: it becomes a new prompt version, and a fact saved after that carries it. A candidate nobody approved is never loaded, and one made from an older version is refused.

## In the design file

- Section 1: the line A9, naming `several routes change a fact` and `a model turns text into facts` when they hold.
- Section 3: each kind with no end is a Semantic memory row with the expiry `no end, checked by evidence`; one row with the memory type `Fact events`; and the lines under the table that `steps/3-design.md` lists for each case.
- Section 4: the recompute job, the procedure that settles a changed fact, and the extraction check, each in code with a test.
- Section 9: the standing tests above, as `steps/3-design.md` lists them.
- Section 10: each review age and cap, each review number, and the optimizer's budget and minimum, each with its source.

Worked lines, for a team assistant that remembers people's roles. They show the form; the names and numbers are an example, not rules:

```
| Person's role | Semantic memory | The team | Any run for that team | replaced when the person or the team lead states a new one; no end, checked by evidence | user stated | confirmed | 200 roles per team, then refuse |
| Other facts about a person | Semantic memory | The team | Shown to the team lead only until confirmed | no end, checked by evidence | agent worked out | unconfirmed | same as Person's role |
| Fact events | Fact events | The team | Read by the trust function and the recompute job only, never shown to the model | 24 months after the event | system record: the app | confirmed | bounded by retention |
- Facts with no end are reviewed: Person's role: after 180 days, at most 2 years; Other facts about a person: after 30 days, at most 90 days
- A fact of no listed kind is saved as: Other facts about a person
- Review numbers: each confirmation multiplies the wait by 2 times; prior for user stated: 9 of 10 answers; prior for agent worked out: 5 of 10 answers; a kind's own rate replaces the prior once its 95 percent interval is narrower than 20 points; the learned review age is the age by which 10 percent of a kind's facts were corrected; alert when a kind's rate drops by 15 points; seen with no correction counts after 7 days
- The owner sees what their facts drive: yes, in the chat reply and on the settings screen
- Rates and review ages are recomputed by: Recompute kind rates
- Conflicts between facts are settled by: Settle a changed fact; several people can set one fact: yes
```

## Tools

In a Python project the script uses the `gepa` package, or `dspy.GEPA` when the project already uses DSPy. Suggest the package once and install it only when the person agrees. In another language, build the loop by hand: the test set, the scoring script, a folder of candidates, the approval step. Options to name once: write candidates yourself and score them; call a Python script as a separate step in the build; use a prompt tool the project already has. None is required. (ours)
