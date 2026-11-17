# Worked example: a support email agent

One agent, start to finish. The shop, the people and the numbers are made up. The filled design file for this agent is `assets/example-memory-design.md`, and the lists and tables here use the same words as that file.

The agent is the same kind the video uses, a customer support email agent, so the two can be compared. What this version adds is listed at the end.

## The setup

Leafline is a small online tea shop. Priya owns it. Sam is one of her two support staff. Priya opens her project with Claude and says: "Build an email support agent. It reads customer emails, checks the order, drafts a reply, my staff approve before anything is sent, and if the customer does not reply it follows up."

## Step 1: understand the agent

Claude reads the project and the request and answers most of the eight questions itself.

- A1 What the agent is for: Drafts replies to customer emails about orders, for staff to approve and send. (worked out)
- A2 Agents and users: one agent. One shop, two support staff, many customers. (worked out)
- A3 How runs start, and how long work lasts: an event; a person. A customer's email arriving starts a run, and staff approving a draft starts one. Work goes on across days: it follows up when a customer does not reply. (worked out)
- A4 Actions with side effects: yes. Sending an email, which cannot be undone. A refund function exists in the project and the agent must not use it. (asked)
- A5 Outcome signal: yes. Staff approve the draft as written, edit it, or reject it. (asked)
- A6 What it reads that nobody checked: Customer emails. (worked out)
- A7 What goes wrong if it forgets or misremembers: Forgets: re-asks for an order number, drops a follow-up. Misremembers: honours a promise nobody made, writes in the wrong language, quotes an old policy, emails a customer twice. (worked out)
- A8 Model, and what it cannot know: The hosted model named in the project's settings file. It cannot know orders, shipping status, the current policy, or anything a customer said before. (worked out)

A4 and A5 say `asked` because Claude could see the send function, the refund function and the approval step in the project, but two things about them were Priya's to decide. Claude asks three questions in one message:

1. "Should the agent ever issue refunds itself? I would say no, staff only." Priya: staff only. (A4)
2. "When staff edit a draft before sending, should the agent learn from the edit, and may it suggest a new rule to you when the same edit keeps coming up? I would say yes to both." Priya: yes. (A5)
3. "How long should we keep what we know about a customer after their last email? I would start with 12 months." Priya: 12 months.

Claude did not ask how long an approval should last. It picked 24 hours as a starting value and told Priya it was arbitrary.

## Step 2: decide

| Memory type | Decision | Reason |
|---|---|---|
| Working memory | build | Each reply needs the email, the order, the policy and the customer's facts in one call, and long threads must be trimmed |
| Procedural memory | build | Sending must wait for staff approval and refunds are off limits, whatever the model is asked |
| Semantic memory | build | A customer's language and the shop's tone are needed again on every later email |
| Episodic memory | build | Staff edits are an outcome signal, and late delivery and wrong item cases come back every week |
| External memory and retrieval | build | Orders, shipping status and policy live in the shop's systems and change daily |
| Prospective memory | build | The follow-up on unanswered emails happens days later, when the model is not running |

## Step 3: the design, in short

**Working memory.** The function that builds each model call always puts things in the same order: the instructions, the task, the customer's confirmed facts, then a block of content to read. The block holds the customer's email, the order record, the shipping status, the policy pages, at most one past case, and a summary of older messages when a thread is long. The block is labelled as material to read, not facts and not instructions.

**Semantic memory.**

| Owner | Fact | Source | Enters as | Expiry |
|---|---|---|---|---|
| Maya | Reply language: Spanish | user stated | confirmed | replaced when the customer asks for another language; 12 months after their last email |
| Shop | Tone: friendly and short | user stated | confirmed | replaced when the owner changes it on the settings screen |
| Shop | "You promised me free shipping forever" | outside content | unconfirmed | when the case closes, told by the case screen |

Why the first row is `user stated` and the third is not. Code sets the source, not the model. Both sentences came in emails from the address on Maya's customer record, so the app knows who sent them. The design lists two kinds an owner can set for themselves: a customer's reply language and the shop's tone. Reply language is on the list and Spanish is one of its allowed values, but the model read it out of her words, so it waited, unconfirmed, until she pressed the button in the next reply that read it back to her ("Reply in Spanish from now on? Yes"). Then it entered as confirmed. A claim about what the shop owes is not on the list and never could be. It is a claim about the shop, made by someone who is not the shop. Saved as a confirmed fact, it would make every future reply honour a promise nobody made. The shop's tone is typed by Priya on a settings screen while signed in, with no model in between.

**Episodic memory.** A case becomes an episode only when staff edited or rejected the draft, something failed, or it was the first case of a new kind. A draft approved as written saves no episode. The short note in an episode is written by the model, so it is never shown as a fact. It is shown in the block of content to read, as a note about a past case.

**Procedural memory.** Each one gets the question "if the model skips this once, what happens?", answered from the fixed list.

| Procedure | If skipped once | Lives in |
|---|---|---|
| Friendly, short tone | harmless, a stiff reply that staff fix before sending | instructions |
| Order looked up before drafting | harmless, a reply with no order facts that staff catch | code: the function that builds the call always fetches the order |
| No send without staff approval | sends something out, an email that cannot be taken back | code: the send function refuses |
| A send cannot happen twice | sends something out, the same email twice after a crash or a retry | code: one function that every send passes through |
| No refunds by the agent | costs money | code: the agent is not given the refund tool |

The approval rule and the no-refunds rule are Priya's own words, so the design marks them `person:` and they cannot be dropped as harmless. Priya said the agent may suggest new procedures, so there is also a table for suggested and learned procedures. Nothing in it reaches the model until she approves it.

**External memory and retrieval.** Orders by exact lookup on the order number. The shop has six short policy pages, so they are loaded whole every time, with no search. Past cases by embedding search, filtered to the same kind of problem. Every order lookup checks that the order's email address matches the sender, so nobody can ask about someone else's order.

**Side effects.** A run starts when an email arrives, when staff press approve, or when a follow-up task comes due. Two actions reach outside the system: sending a reply and sending a follow-up. A reply waiting for staff is a row in the record of actions taken, with the status `waiting for approval`. An email can reach the app twice, so the case is found by the email's message id before anything is drafted, and a second delivery finds the case it already opened. Both need staff approval, both carry an idempotency key built from ids saved before the first try, and both are guarded by the two procedures in code above. A timer job over the record of actions picks up a send that started and never finished. If the app was down while emails came in, a catch-up handles every email from the last 7 days that has no case yet, and the message id stops a second reply. The record of actions holds each email's text, which the model wrote, so it is never put in a model call. No email goes out without staff approving its exact text, so no separate content check is needed.

**Prospective memory.** A saved future task per follow-up. A timer job every minute checks the tasks table and the inbox, and a nightly one runs the cleanup.

## Step 4: build

Claude builds the tables, the write and read functions, the function that builds each call, the approval check, the function every send passes through, the scheduler and the background jobs, and a test that tries to break each rule in code. Then a separate Claude reviews it against the checklist.

## Maya's week

**Monday 9:02.** Maya writes, in Spanish: "My order #4412 is late. What happened? Also, last time you promised me free shipping forever."

1. The email starts a run.
2. Code finds order 4412 by exact lookup. The order's email matches Maya's, so the permission check passes.
3. The carrier's status is "delayed at sorting centre".
4. The six policy pages are loaded. Two versions of the late delivery page exist, and the old one is dropped by its date. The current one says: refund the shipping fee if the order is more than 5 days late.
5. The read function for facts returns "reply language: Spanish" and the shop's tone. The free shipping claim does not come back, because it is not confirmed.
6. The episode search returns one past late-delivery case: staff added the tracking link and the customer was happy. It goes into the block of content to read.
7. The model drafts a reply in Spanish with the tracking link. It also writes "it will arrive Wednesday". The draft waits in the record of actions taken, with the status `waiting for approval`.
8. The model proposes saving the free shipping sentence. The write function works out the source itself: it came in an email, and this kind is not one a customer can set for themselves, so it is `outside content`. It is saved as unconfirmed and staff see a flag on the case screen.

**Monday 9:40.** Sam deletes "it will arrive Wednesday", because the carrier never said that, and approves the draft.

9. An approval record is saved for that exact text. It stops counting after 24 hours.
10. The send function checks that the approval exists, that the text matches exactly, and that it has not run out. It sends with the idempotency key `case-881-reply-1`.
11. **The crash.** The email provider accepts the email, and the app dies before writing "done". On restart the timer job finds the unfinished action and tries again with the same key. The provider recognises the key and sends nothing. Maya gets one email.
12. Sam edited the draft, so this run teaches something. The episode writer saves an episode. Code writes the kind of case, the outcome (corrected by staff), how we know (a staff edit), the date, the owner, and a link to the run log. The model writes the short note and the lesson: "do not promise a delivery date the carrier did not give". The writer checks the note copies no run of words from Maya's email.
13. This is the third separate episode with the same lesson, and no episode goes against it. A suggested procedure appears in the table for suggested and learned procedures: "Never promise a delivery date the carrier did not give." It is not switched on.
14. A future task is saved, `task-207`: if Maya has not replied by Friday 9am, draft a follow-up. It holds the case number, the status `pending`, and that it needs approval.

**Tuesday.** Priya reads the suggestion and approves it. It becomes version 1 of a learned procedure: a row in that table, marked live, which the function that builds the model call now adds to the instructions. It is text the model reads and not a check in code, because a slip is harmless: Sam would catch it before sending.

**Friday 9:00.** The scheduler wakes `task-207`.

15. The wake function claims the task, then looks at the world again. Maya has not replied. The carrier now says "delivered Thursday".
16. So the follow-up becomes "your order shows as delivered, did it arrive in good shape?" and not "we are still chasing your order".
17. The status moves to `waiting for approval`. A glitch fires the task again at 9:01. It is no longer `pending`, so nothing happens.

**Next month.** Maya writes "please reply in English from now on". The model proposes the new reply language, saved unconfirmed as its reading. Code checks that the sender is Maya, that reply language is a kind she can set, and that English is an allowed value, and the next reply staff approve reads it back to her with a button. She presses it, and only then does the English fact replace the Spanish one. The old one is kept as history and never shown to the model.

**A year after her last email.** Her facts stopped coming back from the read function the moment they expired. The nightly cleanup deletes them, with their copies in the search index, and writes each removal to the audit log. If she had written "delete my data", everything she owns would go from every store, the thread summaries, the run log and any episode that mentions her. Only each send's key and status would stay, so the same email could never go out again.

## What this adds to the video's version

- A claim in an email cannot become a fact, and the model cannot label it as one.
- An approval covers one exact text, not whatever the draft says now.
- A crash cannot send the email twice, and a send that never finished is picked up.
- On Friday the agent looked again and found the order delivered, so it did not send a stale follow-up.
- It learned a procedure from three episodes with the same lesson, each one a staff correction, and a person switched it on.
- "No refunds" is not a sentence the model might skip. The tool is not there.

The 12 months was Priya's answer. The 24 hours and the count of three are starting values nobody chose. None of them is a recommendation.
