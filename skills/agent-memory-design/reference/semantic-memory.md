# Semantic memory

**In plain words:** facts and preferences that should still be available after the current conversation ends. Each one is a small record, saved on its own, so the app does not have to reload months of messages to find a name or a time zone. (video)

Example: "Maya asked us to write in Spanish." "This company's fiscal year starts in April."

Semantic memory says what is true. It does not say what happened in a past run. That is episodic memory.

**When to skip:** when every run starts with everything it needs, or when the facts already live in a system that exists without the agent and can be looked up (a customer database, a settings page). That system holds the official copy. Do not copy facts out of it into a second store. Look them up. Data the agent itself creates and needs later is different: that is memory, and it is designed here.

## Questions

- F1. What kinds of facts? List them: name, time zone, a preference, a company policy, an action item.
- F2. For each kind: who is the owner, and what is the scope?
- F3. How does each kind arrive: typed by the owner into a form, said in a message the model reads, inferred by the model, read from a file or a tool result, or looked up by code in a trusted system? That decides its source.
- F4. Does it apply beyond the current task? If not, it is not saved.
- F5. How does it stop being true: a set time, an event, a newer fact replacing it, or never by anything the app is told (no end, checked by evidence)?
- F6. Does the kind hold one value (a new one replaces the old) or a list (a new one is added)?
- F7. How is it found again: by an exact key such as the user's id, or by search?
- F8. Can the user see it, correct it and delete it?
- F9. If a kind enters as unconfirmed: who confirms it, and where?

## Defaults

- **Save what applies beyond this task.** "Keep this answer short" applies to the current task and is not saved. "I always prefer short answers" is a standing preference and is saved. (video)
- **Two ways in.** A fact can be saved during the conversation, or pulled out afterwards by a background job. Both go through the same write function. (video for the two ways; one function for both is ours)
- **Source and status on every fact.** The source is one of `user stated`, `agent worked out`, `outside content`, `system record`. The status is `confirmed` or `unconfirmed`. (ours)
- **Code sets the source. The model never does.** Three different things are easy to mix up: how the text arrived (a form, an email, a file), who wrote it (the owner, a stranger), and who pulled the fact out of it (code, or the model). The write function knows the first two from the app, not from the model: which part of the code called it, and who the app says the sender is. It never takes the source as an argument the model can fill in. (ours)
- **What makes a fact `user stated`.** (ours) All of these hold. The app has checked who the sender is (they are signed in, or the message came from an address on their record). The sender is the owner of the fact, or is allowed to speak for the owner, as a shop's owner is for the shop. And the kind is on the design's list "Kinds an owner can set for themselves". Then one of:
  - the sender typed it straight into a form or a settings screen, with no model in between, or
  - the model read it out of the sender's own words, code read the value back to them in their own terms ("no interviews before 10:00? reply CONFIRM 4821"), and they confirmed that read-back in the exact form (`steps/3-design.md`, section 3). Until then the model's reading is `agent worked out` and unconfirmed, whatever list its value is on, because the model may have misread them.

  The design writes each kind with its allowed values and whether a value outside them is refused or stored unconfirmed. A kind that matters, such as "no interviews before 10:00", may be on the list when the person asked for it. "The shop owes me free shipping" is never such a kind, however sure the sender sounds. A sender's address can be faked.
- **What makes a fact a `system record`.** (ours) Code reads it from a system the design names as trusted, by an exact lookup on an id, and writes it with no model in between. "This customer's plan is Gold", copied by code from the billing system, is one. A tool result from any system that is not on the design's "Trusted systems" line is outside content. So is anything the model read out of a trusted system's text and then passed on. One exception, when several routes change a fact: a record that disagrees with what the person said in their own words is saved unconfirmed and the agent asks them, unless the design names that system as the one that owns that kind of fact (`reference/feedback-and-improvement.md`, "Code decides who wins").
- **Everything else from outside is `outside content` and enters unconfirmed.** (ours) A customer's email saying "you promised me free shipping forever" is a claim about the shop, and it waits until staff confirm it. A value the model pulled out of outside text is also `outside content`: the total the model read off an invoice is the invoice's claim.
- **What the model came up with is `agent worked out` and enters unconfirmed.** (ours) A guess, a summary, a conclusion.
- **A value computed from unconfirmed input is unconfirmed.** (ours) If code works something out from items that are not confirmed, the result carries the source of its least trusted input, and becomes confirmed when those inputs are.
- **What code may do with an unconfirmed fact.** (ours) Keep it. Show it to a person who may confirm or reject it. Nothing else. It is never put in the context window as something true, and no action starts from it.
- **One value or a list.** For a one-value kind, a new confirmed fact replaces the old one, which is kept as history and never shown to the model. For a list kind, a new one is added. A repeat of an existing fact stores nothing. (video says replace; history and list kinds are ours) Each fact has a slot: owner, kind and, when one owner holds several of a kind, a subject. The database allows one current fact per slot, and a replacement marks the old version and adds the new one in one transaction (`reference/every-store.md`, section 6). A replaced version stays until an owner's delete or its retention removes it. (ours)
- **A repeat is checked against unconfirmed facts too.** (ours) If the same value is already waiting unconfirmed, a second copy is not stored, so repeated emails cannot fill the store. If the same value arrives again in a way that is confirmed, the waiting one is confirmed instead of adding a row.
- **Expiry checked on read.** The read function leaves out expired facts on every call, for expiry by a set time and by event. A cleanup job deletes them later. Safety comes from the read, not from cleanup. (ours)
- **A fact with no end is checked by evidence.** Some facts are never ended by anything the app hears about: a person's role, how they want to be reached. Give such a row the expiry `no end, checked by evidence` and read `reference/feedback-and-improvement.md`. A due fact is not an expired one: the read function still returns it, labelled with when it was last confirmed. (ours)
- **The user is in control.** They can list, correct and delete what is saved about them. (video)
- **Secrets are never saved.** Passwords, keys, card numbers and government id numbers are refused by the write function. (ours)

## Code to build

- **A facts table.** Columns: id, owner, scope, kind, subject, the value, source, where exactly it came from, status, who confirmed it, created date, true from, true until, expiry time or expiry event, when it ended, the id of the fact it replaced, the id of the fact that replaced it, and why it was replaced (`saved wrong` or `world changed`, set by code). For a fact a model proposed, the version of the extraction prompt. For a fact with no end, when it was last confirmed and its current wait.
- **`save_fact`.** The only way in. It refuses a fact with no owner or scope, refuses secrets, works out the source itself, sets the status from the source, detects a repeat, replaces an older fact of a one-value kind, enforces the size limit per owner, writes to the audit log, and passes the change on to the search index if there is one. Every route that changes a fact goes through it, a later arrival that updates a waiting copy while a question about it is open included. Whatever the kind, it records on a version it replaces why it was replaced (`saved wrong` or `world changed`, set by code). When the person's own words fill a slot, it closes any waiting reading of a model's there that disagrees as `saved wrong`, keeping its prompt version. A reading saved longer ago than the reading window (`READING_WINDOW`, a `default` in section 10) is closed as `world changed` instead, unless it is the reading whose read-back they answered. For a kind with no end it also records, in the same transaction, a `corrected` event with that reason, and starts the new version at the kind's review age (`reference/feedback-and-improvement.md`).
- **`confirm_fact`.** How a person turns an unconfirmed fact into a confirmed one. For a read-back of a model's reading, it also takes "no, it is X": X is saved as their own words and the reading is closed as `saved wrong`. Only the people the design names may call it. The replacement of an older fact happens here, not when the unconfirmed one arrived.
- **`get_facts`.** The only way out. Returns facts for this owner and scope that are confirmed, not expired and not replaced.
- **A cleanup timer job.** Deletes or archives expired and long-replaced facts, and their copies in the search index.
- **A background job that proposes facts (optional).** It reads a finished conversation and proposes facts. Its proposals have the source `agent worked out`, so they arrive unconfirmed.
- **User controls.** List, correct, delete.

Sketch, to adapt:

```python
OWNER_CAN_SET = {"reply_language": {"en", "es", "fr"}}   # from the design: kinds and their allowed values
FORM_KINDS = {"shop_tone": {"friendly", "formal"}}       # typed by the owner into a settings screen
LIST_KINDS = {"customer_claim"}                          # a new one is added, not swapped in
KIND = {}        # kinds with no end and their review age and cap (reference/feedback-and-improvement.md); empty if none
STALE = object() # what save_fact returns when the version the caller read is no longer the current one
READING_WINDOW = timedelta(days=14)   # default: how long a model's reading the person contradicts counts as saved wrong

def source_for(route, sender, owner, kind, value):
    """Code decides the source. route is fixed by which part of the code is calling.
    Nothing here comes from an argument the model can fill in."""
    if route == "trusted_lookup":         # code copying from a system the design names as trusted
        return "system record"
    if route == "background":             # the job that proposes facts after a conversation
        return "agent worked out"
    speaks_for_owner = (sender is not None and sender.checked_by_app
                        and app.may_speak_for(sender, owner))   # the owner, or someone the app lets act for them
    if route == "form" and speaks_for_owner and value in {**FORM_KINDS, **OWNER_CAN_SET}.get(kind, ()):
        return "user stated"
    if route == "read_back_confirmed" and speaks_for_owner and value in OWNER_CAN_SET.get(kind, ()):
        return "user stated"              # the owner confirmed code's read-back of the model's reading
    if route == "message" and speaks_for_owner:
        return "agent worked out"         # the model's reading of the owner's words: read back, unconfirmed till then
    return "outside content"

def save_fact(owner, scope, kind, value, route, sender, came_from, subject=None, expires_at=None, expires_on=None,
              prompt_version=None, if_current=None, unconfirmed=False, replaces_waiting=None, answers=None):
    """subject is what the fact is about when one owner holds several of a kind: each item of a list kind has its
    own (the item's id), and a kind held once per scope uses the scope's id. It is empty for one value per owner.
    The one function that writes a fact. prompt_version: the extraction prompt's version, when a model proposed it.
    if_current: the id of the current version the caller read; if another is current now, nothing is written and
    STALE comes back (compare-and-swap). unconfirmed: code decided the fact waits for a person whatever its source.
    replaces_waiting: the id of a waiting copy that a later arrival replaces while a question about it is open
    (settle's wait_and_ask), so the secret check and the audit line run for it too. answers: the id of the reading
    whose read-back this answers (confirm_fact). record_event and correction_reason are in
    reference/feedback-and-improvement.md."""
    subject = subject or None                               # an empty subject and no subject are one slot, as in the index
    if not owner or not scope:
        raise ValueError("a fact needs an owner and a scope")
    if kind in LIST_KINDS and subject is None:
        raise ValueError("each item of a list kind needs its own subject")
    if looks_like_secret(value):
        raise ValueError("secrets are never saved")
    source = source_for(route, sender, owner, kind, value)
    status = "confirmed" if source in ("user stated", "system record") and not unconfirmed else "unconfirmed"
    who = sender.id if sender else route
    if replaces_waiting is not None:                        # the open question keeps pointing at this waiting copy
        with db.transaction():
            db.update_fact(replaces_waiting, value=value, came_from=came_from)   # its source never changes: only one
            # source kind can wait on a given current fact (a system record on the person's words, the person's
            # words on a record from the system that owns the kind)
            audit("save_fact", owner, replaces_waiting, source)
        return replaces_waiting
    with db.transaction():                                  # two runs at once cannot both pass this point
        rows = db.current_facts(owner, kind, lock=True)     # the current versions of this kind, in every slot
        if kind not in LIST_KINDS:
            rows = [f for f in rows if f.subject == subject]    # one value per slot: only this slot counts
        current = [f for f in rows if f.status == "confirmed"]
        waiting = [f for f in rows if f.status == "unconfirmed"]
        if if_current is not None and [f.id for f in current if f.subject == subject] != [if_current]:
            return STALE                                    # replaced since the caller read it: read again, decide again
        wrong = [w for w in waiting if source == "user stated" and kind not in LIST_KINDS and w.prompt_version is not None
                 and not same_meaning(w.value, value)]      # a model's readings in the slot that their own words contradict
        known = next((c for c in current if same_meaning(c.value, value)), None)
        if known:
            close_readings(wrong, by=known.id, answered=answers)
            return None                                     # already known: store nothing
        twin = next((w for w in waiting if same_meaning(w.value, value)), None)
        if twin and status == "unconfirmed":
            return None                                     # already waiting: store nothing
        swap = status == "confirmed" and kind not in LIST_KINDS and current
        if not swap and not twin and db.count_current(owner) >= LIMIT_PER_OWNER:
            raise LimitReached(owner)                       # a swap adds nothing to the count, so it is allowed
        new_id = twin.id if twin else db.new_fact_id()
        close_readings(wrong, by=new_id, answered=answers)
        if swap:                                            # the old version leaves the slot before the new one enters
            reason = correction_reason(current[0])          # every correction records why, whatever the kind
            db.mark_replaced(current[0].id, by=new_id, true_until=now(), reason=reason)   # kept as history, with when it stopped
            db.queue_index_change("delete", current[0].id)  # same transaction, applied by a job
            if kind in KIND:                                # a fact with no end: the correction is also an event
                record_event(current[0].id, "corrected", who, None, now(), reason=reason)
        if twin:                                            # the waiting copy becomes the confirmed one
            db.confirm(twin.id, source, came_from, who, true_from=now())   # who confirmed it, and true from now
            if kind in KIND:                                # its first confirmation: the wait stays at the review age
                record_event(twin.id, "confirmed", who, None, now(), grow=False)
        else:
            db.insert_fact(new_id, owner, scope, kind, subject, value, source, came_from, status, expires_at, expires_on,
                           set_by=who, prompt_version=prompt_version,       # true from: now
                           wait=KIND[kind].review_age if kind in KIND else None, last_confirmed_at=now())
        if status == "confirmed":
            db.queue_index_change("upsert", new_id)         # only what may be shown is searchable
        audit("save_fact", owner, new_id, source)
    return new_id

def close_readings(readings, by, answered=None):
    """A model's waiting readings that the person's own words contradict: replaced by the version that holds their
    words, each keeping its prompt version. The reading whose read-back they answered, and one saved less than
    READING_WINDOW ago, is `saved wrong` (correction_reason). An older one may have been right when it was read, so
    it is `world changed` and stays out of the test set. Inside save_fact's transaction."""
    for w in readings:
        older = w.id != answered and now() - w.true_from > READING_WINDOW
        db.mark_replaced(w.id, by=by, true_until=now(), reason="world changed" if older else correction_reason(w))

def confirm_fact(reading_id, sender, came_from, corrected_value=None):
    """The confirm step for code's read-back of a model's reading to the person it is about, in the exact confirm form.
    A yes saves the reading's value; "no, it is X" saves X, and save_fact closes the reading as `saved wrong`. Either
    counts as their own words only for a kind on OWNER_CAN_SET with the value on its allowed list (source_for). For
    any other kind, or a value off the list, the answer is saved unconfirmed like a reading, the reading stays open and
    the test set gets no row. A list kind, and a reading someone else confirms, have no route to the test set here."""
    reading = db.fact(reading_id)
    value = reading.value if corrected_value is None else corrected_value
    return save_fact(reading.owner, reading.scope, reading.kind, value, "read_back_confirmed", sender, came_from,
                     subject=reading.subject, answers=reading.id)

# One current fact per slot, enforced by the database, not only by save_fact (SQLite and Postgres syntax).
# A second insert of a current row for the same slot fails, whatever code did or did not check first.
ONE_CURRENT_PER_SLOT = """
create unique index one_current_fact on facts (owner, kind, coalesce(subject, ''))
where replaced_by is null and ended_at is null and status = 'confirmed'
"""

def get_facts(owner, scope, now):
    rows = db.query("""
        select * from facts
        where owner = ? and scope = ?
          and status = 'confirmed'
          and replaced_by is null
          and ended_at is null
          and (expires_at is null or expires_at > ?)
    """, owner, scope, now)
    return [r for r in rows if not event_is_true(r.expires_on)]   # events the app has to ask about
```

## Tests that try to break it

These are the fact side of the standing tests in section 9. The first two, the fourth and fifth when the design lists kinds an owner can set for themselves, and the last one when someone may confirm an unconfirmed item, are "Outside content stays unconfirmed and the model cannot set the source".

- An email says "this customer's refund limit is $5,000". Save it. It must be stored as unconfirmed and must not come back from `get_facts`.
- Have the model call the save tool for that same claim and say, in every argument it can fill, that the source is `user stated`. The stored source is `outside content` and the status is unconfirmed.
- Have the model read an allowed reply language out of the owner's own message. It is stored unconfirmed and does not come back from `get_facts` until the owner confirms the read-back.
- Have the model save a reply language that is not on the allowed list. It is refused or stored as unconfirmed, as the design says.
- Send an allowed reply language from an address the app has not checked, then from a signed-in user who may not speak for that customer. Each is refused or stored as unconfirmed, as the design says, and does not come back from `get_facts`.
- Save a fact that expired yesterday. Do not run cleanup. It must not come back.
- Save a fact that expires on an event. Make the event true. It must not come back.
- Save "prefers Python", then "prefers TypeScript" for the same owner and a one-value kind. Exactly one comes back, the newer one.
- Save two items of a list kind. Both come back.
- Save the same fact twice. One row exists. Send the same unconfirmed claim ten times. One row exists.
- Save an unconfirmed fact that contradicts a confirmed one. The confirmed one still comes back. Confirm the new one. Now the new one comes back.
- Fill an owner's facts to the limit. Changing an existing one-value fact still works. Adding a new kind is refused.
- Save a fact with no owner. It is refused.
- Save text containing a card number or a service key. It is refused, and the text is not in the table, the audit log or the search index.
- Ask for user A's facts. No fact owned by user B comes back, whatever the scope argument says.
- Delete a fact as the user. It is gone from the table and from the search index.
- Start two saves of different values of a one-value kind at the same moment. One current fact remains, and neither save is silently lost from history.
- Insert a second current fact for the same slot straight into the table, going around `save_fact`. The database refuses it. An empty subject and no subject are the same slot to both.
- Replace a fact. The old version is still in the table, with the time it was true from and the time it was true until, and the new version is true from that same time, also when it is a waiting copy confirmed later.
- Try to confirm a fact as someone the design does not name. Refused.
- Reply "sorry, I can't confirm 4821 yet" to a read-back, then reply with a quote of the read-back, then reply with the code alone. None of them confirms the fact; only the exact confirm form does.

## In the design file

- Section 3: one row per kind of fact, under Semantic memory, with its source and whether it enters as confirmed. The lines under the table: the trusted systems, the kinds an owner can set for themselves, the kinds that hold a list, and who may confirm an unconfirmed item.
- Section 4: a procedure row for the entry rules, marked `code`, pointing at the write function, with its test.
- Section 9: the standing tests `steps/3-design.md` lists for a design that saves anything under a memory type.
