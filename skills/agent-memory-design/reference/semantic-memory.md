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
- F5. How does it stop being true: a set time, an event, or a newer fact replacing it?
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
- **What makes a fact a `system record`.** (ours) Code reads it from a system the design names as trusted, by an exact lookup on an id, and writes it with no model in between. "This customer's plan is Gold", copied by code from the billing system, is one. A tool result from any system that is not on the design's "Trusted systems" line is outside content. So is anything the model read out of a trusted system's text and then passed on.
- **Everything else from outside is `outside content` and enters unconfirmed.** (ours) A customer's email saying "you promised me free shipping forever" is a claim about the shop, and it waits until staff confirm it. A value the model pulled out of outside text is also `outside content`: the total the model read off an invoice is the invoice's claim.
- **What the model came up with is `agent worked out` and enters unconfirmed.** (ours) A guess, a summary, a conclusion.
- **A value computed from unconfirmed input is unconfirmed.** (ours) If code works something out from items that are not confirmed, the result carries the source of its least trusted input, and becomes confirmed when those inputs are.
- **What code may do with an unconfirmed fact.** (ours) Keep it. Show it to a person who may confirm or reject it. Nothing else. It is never put in the context window as something true, and no action starts from it.
- **One value or a list.** For a one-value kind, a new confirmed fact replaces the old one, which is kept as history and never shown to the model. For a list kind, a new one is added. A repeat of an existing fact stores nothing. (video says replace; history and list kinds are ours)
- **A repeat is checked against unconfirmed facts too.** (ours) If the same value is already waiting unconfirmed, a second copy is not stored, so repeated emails cannot fill the store. If the same value arrives again in a way that is confirmed, the waiting one is confirmed instead of adding a row.
- **Expiry checked on read.** The read function leaves out expired facts on every call, for expiry by a set time and by event. A cleanup job deletes them later. Safety comes from the read, not from cleanup. (ours)
- **The user is in control.** They can list, correct and delete what is saved about them. (video)
- **Secrets are never saved.** Passwords, keys, card numbers and government id numbers are refused by the write function. (ours)

## Code to build

- **A facts table.** Columns: id, owner, scope, kind, the value, source, where exactly it came from, status, who confirmed it, created date, expiry time or expiry event, when it ended, the id of the fact it replaced, the id of the fact that replaced it.
- **`save_fact`.** The only way in. It refuses a fact with no owner or scope, refuses secrets, works out the source itself, sets the status from the source, detects a repeat, replaces an older fact of a one-value kind, enforces the size limit per owner, writes to the audit log, and passes the change on to the search index if there is one.
- **`confirm_fact`.** How a person turns an unconfirmed fact into a confirmed one. Only the people the design names may call it. The replacement of an older fact happens here, not when the unconfirmed one arrived.
- **`get_facts`.** The only way out. Returns facts for this owner and scope that are confirmed, not expired and not replaced.
- **A cleanup timer job.** Deletes or archives expired and long-replaced facts, and their copies in the search index.
- **A background job that proposes facts (optional).** It reads a finished conversation and proposes facts. Its proposals have the source `agent worked out`, so they arrive unconfirmed.
- **User controls.** List, correct, delete.

Sketch, to adapt:

```python
OWNER_CAN_SET = {"reply_language": {"en", "es", "fr"}}   # from the design: kinds and their allowed values
FORM_KINDS = {"shop_tone": {"friendly", "formal"}}       # typed by the owner into a settings screen
LIST_KINDS = {"customer_claim"}                          # a new one is added, not swapped in

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

def save_fact(owner, scope, kind, value, route, sender, came_from, expires_at=None, expires_on=None):
    if not owner or not scope:
        raise ValueError("a fact needs an owner and a scope")
    if looks_like_secret(value):
        raise ValueError("secrets are never saved")
    source = source_for(route, sender, owner, kind, value)
    status = "confirmed" if source in ("user stated", "system record") else "unconfirmed"
    with db.transaction():                                  # two runs at once cannot both pass this point
        current = db.current_facts(owner, scope, kind, status="confirmed", lock=True)
        waiting = db.current_facts(owner, scope, kind, status="unconfirmed", lock=True)
        if any(same_meaning(c.value, value) for c in current):
            return None                                     # already known: store nothing
        twin = next((w for w in waiting if same_meaning(w.value, value)), None)
        if twin and status == "unconfirmed":
            return None                                     # already waiting: store nothing
        swap = status == "confirmed" and kind not in LIST_KINDS and current
        if not swap and not twin and db.count_current(owner) >= LIMIT_PER_OWNER:
            raise LimitReached(owner)                       # a swap adds nothing to the count, so it is allowed
        if twin:                                            # the waiting copy becomes the confirmed one
            new_id = db.confirm(twin.id, source, came_from)
        else:
            new_id = db.insert_fact(owner, scope, kind, value, source, came_from, status,
                                    expires_at, expires_on)
        if swap:
            db.mark_replaced(current[0].id, by=new_id)      # old one kept as history
            db.queue_index_change("delete", current[0].id)  # same transaction, applied by a job
        if status == "confirmed":
            db.queue_index_change("upsert", new_id)         # only what may be shown is searchable
        audit("save_fact", owner, new_id, source)
    return new_id

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
- Try to confirm a fact as someone the design does not name. Refused.
- Reply "sorry, I can't confirm 4821 yet" to a read-back, then reply with a quote of the read-back, then reply with the code alone. None of them confirms the fact; only the exact confirm form does.

## In the design file

- Section 3: one row per kind of fact, under Semantic memory, with its source and whether it enters as confirmed. The lines under the table: the trusted systems, the kinds an owner can set for themselves, the kinds that hold a list, and who may confirm an unconfirmed item.
- Section 4: a procedure row for the entry rules, marked `code`, pointing at the write function, with its test.
- Section 9: the standing tests `steps/3-design.md` lists for a design that saves anything under a memory type.
