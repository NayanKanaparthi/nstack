# Step 2: Decide which memory types this agent needs

Most agents do not need all seven. Each one you build is code to write, test and keep working, and each one puts more text in front of the model, which costs money and time and makes the important details harder to find. So the default is skip, and building needs a reason.

## 1. The four questions

Answer these for this agent, in your own notes. They come from the video and they sort everything that follows.

1. What information should survive after this run ends?
2. How should it come back when it is needed?
3. When should it be updated or forgotten?
4. Does anything need to wake the system up later?

Sort what must survive:

- Something true that stays true until it is changed goes to semantic memory. If nothing will ever tell the app that it changed (a person's role, where they want to be reached) and people rely on it, it is a fact with no end, and step 3 has you say how it is kept true.
- What happened in one past run goes to episodic memory.
- How to work goes to procedural memory.
- Something to do at a later time goes to prospective memory.
- Something that already lives in another system, and changes there, is not saved at all. It is looked up fresh each time (external memory and retrieval).

**Data the agent itself creates counts as memory.** If the agent produces something it needs again later (a list of action items it pulled from meeting notes, a profile it built up), that is memory, and it is filed by what it is. An action item with its assignee and due date is something true until changed: semantic memory. The reminder two days before the due date is something to do later: prospective memory. The rule "do not save what already lives in a system the agent can look up" is about systems that exist without the agent, such as a customer database. It does not mean the agent's own data needs no design.

## 2. Decide each type

For each type, answer its question below, then write `build` or `skip` and a one-line reason into section 2 of the design file. You answer these before reading any reference file. Types that share a decision and a reason can share one row, with their names separated by semicolons. Parametric memory needs no row: there is nothing to build, and A8 names the model.

| Memory type | The question | Build when | Skip when |
|---|---|---|---|
| Working memory | None. Every agent has a context window that fills up. | Always | Never |
| Procedural memory | None. Every agent has instructions, and most have at least one rule that must be code. | Always | Never |
| Semantic memory | Is there anything true about a user, the company or the world, or anything the agent itself creates, that is needed again in a new conversation? | Yes | Each run starts with everything it needs, or the facts already live in a system that exists without the agent and can be looked up |
| Episodic memory | Does A5 say `yes`, and does the same kind of task come back? | Both are yes | A5 says `no`. Or every task is one of a kind. |
| External memory and retrieval | Does the agent read from any store outside the model: a database, documents, an inbox, another app, or its own semantic and episodic memory? | Yes | The agent reads nothing but the current request |
| Prospective memory | Does the agent ever promise to do something later, or have to act when something it is waiting for does not happen? | Yes | Every run ends completely before the next begins, and nothing is promised for later. An agent whose runs start on a timer is in this case unless it promises later work. Its timer is still built (below) |

Fixed by step 1:

- **If A5 says `no`, episodic memory is `skip`.** No exceptions. In the reason, say what would have to exist to turn it on: an approval step, a test, a check against a trusted number. Say the same to the person in chat.
- **Side effects but nothing later.** If A4 says `yes` and every run ends completely, prospective memory is `skip` and the side effects are still protected. Idempotency keys and approvals do not belong to prospective memory. They belong to every agent that has a side effect, and step 3 has you read `reference/side-effects.md` for them whatever you decide here. That includes an agent whose runs start on a timer or an event: a trigger can fire twice, and that file has you tie each key to the firing.
- **Runs that start on a schedule or an event.** If A3 names `a schedule` or `an event`, something must wake the app (a timer job, a queue, a listener for the event) and something must catch up on firings it missed while it was down. Both are built whatever you decide about prospective memory, and both go in section 4 of the design (step 3). Prospective memory is about tasks the agent saves for later. A fixed timer is not a saved task.
- **Waiting on a person.** Something the agent waits on a person for (an approval, a confirmation, a flag on a screen) needs a future task only if the agent must do something when no answer comes: remind, pass it to someone else, cancel. If nothing happens when nobody answers, it is a row with a status and prospective memory is not needed for it.
- **Every agent keeps a run log,** a short-lived record of each run, whatever you decide about episodic memory. It is a log, not a memory type, and it goes in the design in step 3.

## 3. The smallest agent

Some agents answer one request, save nothing, look nothing up and do nothing outside the system. A4 is `none`, and semantic, episodic, external and prospective memory are all `skip`. For such an agent:

- The design has six sections: 1, 2, 3, 4, 9 and 10. Sections 5 to 8 are left out. It fits on about one screen.
- Section 3 has one row, the run log, and the line `Run log holds content: no`. The log then holds step names, sizes and errors only, and none of the request or the output.
- There is no audit log. It is built only when the agent saves something besides the run log.
- Section 9 has one standing test, "Every run is logged", with one test per case.
- The build is the function that puts the model call together, the run log, and their tests.

If the person said "save nothing" and you are keeping a run log, tell them in chat: what it holds, that it holds no content, and how long it is kept. Write that in section 10 too.

## 4. Write reasons that are about this agent

A reason names something this agent does. A reason that would fit any agent is not a reason.

> Good: "build: staff ask the agent about the same customers for months, and the customer's language and plan must not be re-asked every time."
> Bad: "build: makes the agent more personal."
> Good: "skip: each invoice is checked on its own and nothing about one invoice applies to the next."
> Bad: "skip: not needed."

## 5. If the person wants less

Some types only make the agent better: episodic memory, procedures learned from past runs, a search over past cases. The person may choose to leave one of these out even when the table above says `build`. Others protect, and are never offered as optional: the run log, the protection on side effects, the rules on where a saved item came from, expiry, and the audit log once anything is saved.

Offer the choice once, in the message of section 6 below: name the type in plain words, what it buys this agent, what it costs to build and run, and your recommendation. If they leave it out, the reason in section 2 starts `skip: the person chose to leave this out`, says what it would have bought, and the choice goes in section 10.

Design every needed type now. If they want to build in stages, an order that works is: working memory, then semantic memory, then episodic memory, then procedural memory beyond plain instructions, then retrieval, and prospective memory last. (ours. It loosely follows the CodeConductor write-up, which starts with working memory and adds prospective memory last. The order of the middle is our pick, and the Trafder write-up orders it differently. Neither order has been tested.) Protection for side effects is not on that list because it cannot wait: it is built with the first action that can reach outside the system.

## 6. Before moving on

All six types have a decision and a reason. Tell the person in two or three lines what you are skipping and why, because a skip is the decision they are most likely to want to change. For each type from section 5 that you are building, offer the lighter choice in the same message. Now read `steps/3-design.md`.
