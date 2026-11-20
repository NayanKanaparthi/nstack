---
name: agent-memory-design
description: Designs and then builds the memory system for an AI agent, meaning what stays in front of the model on each call, which facts are saved, what is learned from past runs, which rules live in code, how saved things are found again, and how the agent follows up later without doing anything twice. Use this whenever someone is planning, designing, building or reviewing an agent, assistant, bot or multi-step workflow built on a large language model (LLM), and any of these come up, even if nobody says memory. Examples are remembering users or preferences, state between conversations, a context window that gets too long, retrieval (RAG), saving what the agent reads, learning from feedback, approvals, retries, follow-ups, scheduled jobs. Also use it to add memory to an existing agent, to review the memory an existing agent already has in its code, or to review a MEMORY-DESIGN.md file. For agents that call a hosted model over the internet. It does not cover retraining the model (fine-tuning).
---

# Agent memory design

Someone is building an agent with you. At some point the agent has to remember things: a user's name next week, what went wrong last time, a follow-up on Friday. Your job is to work out what this agent needs to remember, write that down as a design, and then build it as working code with tests.

You do the design work. The person is not handed a questionnaire or a to-do list. You read the project, answer what you can yourself, ask the person only what you cannot work out, and build.

In these files "the model" means the large language model the agent calls, and "the app" means the agent's own code around it.

## Memory is an engineering system

The common mistake is to treat memory as notes: a file of things for the model to read, plus a line in the instructions saying "remember what the user tells you". That fails in ordinary ways. A sentence from a stranger's email gets saved as a fact. A preference from last year overrides the one from yesterday. A follow-up email goes out twice because the app restarted.

A memory system is database tables, functions, jobs that run on a schedule, and tests. Three roles, and they do not swap:

- **Code decides.** What is allowed in, where it came from, what replaces what, what has expired, who can see what, when something wakes up, and that nothing happens twice. The model cannot get around any of this.
- **The model suggests.** It can propose a fact worth saving, draft a reply, or propose a new procedure. Code checks the proposal against the rules before anything is stored or done.
- **Instructions guide.** The text the model reads tells it when to use the memory tools and what to do with what comes back. A tool is a function the model is allowed to call, such as "look up an order".

If a rule appears in the design, it lives in a function. A sentence in the instructions is not a rule, because the model can skip it.

## Scope

- For agents built on a hosted model: one that another company runs and your code calls over the internet through an API, which is the set of requests that company accepts. You cannot change the model. Retraining it on your own data, called fine-tuning, is out of scope.
- You do not pick products. Use the programming language, the database and the scheduler the project already has. A scheduler is whatever wakes the app at a set time or when something happens. When the design needs something the project has none of (a check of the model's output against a schema, tracing, versions of a prompt), say what is needed and name two or three options once, the simplest version in the project's own code among them. Never require one.
- The seven memory types below are seven jobs, not seven databases. Several can share one database. Most agents do not need all seven.
- **The design is as small as the agent.** An agent that answers one request, saves nothing and does nothing outside itself gets a design that fits on one screen and almost nothing to build. Do not add a store, a test or a section the agent has no use for.

## The seven memory types

| Memory type | In plain words | Example | Can be skipped |
|---|---|---|---|
| Working memory | What is in front of the model on this call. It has to fit in the context window, which is the most text the model can read at once. | The instructions, the user's message, the last few messages, what a tool returned | No |
| Semantic memory | Facts and preferences that should still be there in a new conversation | "Maya asked us to write in Spanish" | Yes |
| Episodic memory | A short note about one past run: the task, what was done, how it ended | "Late delivery case: staff removed a delivery date the carrier never gave" | Yes |
| Procedural memory | How the agent should work: steps, rules, the order of things. Lives in the instructions, in the text that describes each tool to the model, in reusable instruction files the model loads for one kind of task (often called skills), or in code | "Never send an email until staff approve it" | No |
| External memory and retrieval | Information stored outside the model (a database, documents, an inbox), and retrieval, which is how the useful part is found and brought back | Looking up order 4412 by its number | Yes, if the agent reads nothing but the request |
| Parametric memory | What the model already knows from training. It is stored inside the model, in the numbers it learned, called weights. You cannot change it. | The model can write Spanish | Nothing to build |
| Prospective memory | Remembering to do something in the future: a saved task and a trigger that wakes the app | "If no reply by Friday, draft a follow-up" | Yes |

The list of seven comes from the video named in `README.md`. Its base is the CoALA paper, which names working, semantic, episodic and procedural memory.

## What to read, and when

The work has two stages, design and then build, followed by a review you do not do yourself. A separate path reviews an agent that already exists.

| Where you are | Read, one at a time, when you reach it |
|---|---|
| Planning or building an agent, or adding memory to one | `steps/1-understand.md`, `steps/2-decide.md`, `steps/3-design.md` (design stage), then `steps/4-build.md` (build stage), then `steps/5-review.md` to hand off the review |
| The agent already exists, its code already saves or reads memory, and you were asked to review, audit or check that memory | `steps/review-existing-agent.md`, with `CHECKLIST.md` and `assets/gap-report-template.md` |
| You were given a `MEMORY-DESIGN.md` and asked to review or check it, or you were started as the reviewer | `steps/5-review.md` and `CHECKLIST.md`, and the "Words these files use" list at the end of this file |

New words from v0.2 (version chain, partial unique index, compare-and-swap, smoothing and others) are explained in `reference/glossary.md`.

Read a step file only when you get to that step. The files in `reference/` hold the detail. Step 3 tells you which ones to read. Do not read reference files for memory types the agent does not need.

The design is written into the person's project as `MEMORY-DESIGN.md`, copied from `assets/memory-design-template.md`. You write it for yourself to build from and for the reviewer to check. `scripts/check_design.py` checks that the file is complete and agrees with itself. It cannot tell whether the design is right, and it prints the questions only a reviewer can answer.

**If you cannot write files yet** (some tools have a planning mode where you may only read and propose): keep the design in your plan, using the same sections as the template. Writing `MEMORY-DESIGN.md` and running the checker is then the first thing you do when the build starts.

## Rules that hold in every step

Each rule says where it comes from. (video) is the video in the README. (source: a name) is one of the papers or write-ups listed there, by name. (ours) is our own judgment and no source backs it.

1. **Start from the agent, not the database.** Ask what this agent is for and what goes wrong if it forgets or misremembers. Then four questions: what must survive, how does it come back, when is it updated or forgotten, and does anything need to wake the system later. (video)
2. **Skip what the agent does not need.** Every memory type you build needs a reason tied to something this agent does. (video)
3. **A rule lives in code, or it is not a rule.** For every procedure ask: if the model skips this once, what happens? If it costs money, sends something outside the system, cannot be undone, leaks data, puts something false into memory, or silently drops something a person relies on, it is code. If it is harmless, it can be instructions. (ours)
4. **Everything saved has an owner, a scope, an expiry and a size limit.** The owner is who it belongs to. The scope is where the agent may use it. The expiry is how it stops being true: a set time after something, an event, being replaced by something newer, or, for a fact people rely on that nothing ever ends, no end with its truth checked by evidence. (video for owner, scope and expiry; the forms of expiry and the size limit are ours)
5. **Code sets where a saved item came from. The model never does.** Text read from emails, web pages, files and tool results is saved as unconfirmed, and unconfirmed items are never shown to the model as facts and never trigger an action. There are two ways in as confirmed, and both are written in the design. One is a short list of kinds an owner can set for themselves, such as the language they want replies in, each with its allowed values, typed in by the owner, or read out of their words by the model and confirmed by them when code reads it back. The other is a record that code reads from a named trusted system by an exact lookup, with no model in between. (video says check it before it becomes trusted; the rest is ours)
6. **Checks happen on every read.** Expired, unconfirmed and not-allowed items are filtered inside the read function, every time, in every store. Cleanup is not what keeps an expired item out, but it still runs and is tested: expired rows are removed on a schedule, or at the start of each run when the agent has no timer, and each removal is in the audit log when there is one. When memory cannot be read at all, the agent still answers without it, and an action that needs memory does not happen. (ours)
7. **Every run is logged for a short time. That log is not memory.** The run log is for finding out what happened. Nothing puts it into a model call. One job may read it: the job that writes an episode after a run, which turns it into a short note under its own rules. For an agent that saves nothing else, the run log may hold only step names, sizes and errors. (source: Konishi guide for the short-lived log; requiring it for every agent is ours)
8. **No outcome signal, no episodic memory.** An outcome signal is how the agent knows a run went well: a test passing, a number matching, a person saying yes or no. Without one, saved runs would teach the agent things nobody checked. (ours)
9. **The agent may suggest a procedure. A person switches it on.** Never automatic. (ours. The Konishi guide requires a check before a suggested procedure goes live, and never automatic promotion. It accepts any one of three checks: running the procedure again in a safe setting, seeing it work on several separate occasions, or a person reading and approving it. Requiring a person every time is our choice.)
10. **An action with a side effect is protected.** A side effect is anything that changes the world outside the system: sending an email, paying a refund. Each one carries an idempotency key, which is a label sent with the action so a repeat can be recognised and not done again, such as `case-881-reply-1`. Each action has a risk label fixed in code, and the model never sets it. Where a person must agree first, the approval is tied to that one exact action. When runs start on a schedule or an event, the key includes a part that is the same across firings for the same thing (the planned time of the firing, the event's own id, or the id of the item acted on), because a trigger can fire twice. An action that sends text from outside or written by the model, with no approval of that exact text, passes a content check in code first. A task saved for later keeps the premise it was scheduled on, and does nothing when it wakes to find the premise changed. (source: Let's Data Science write-up for keys from stable ids, looking before a retry, and approvals tied to one action; that this holds for every agent with a side effect, with or without future tasks, the key tied to a firing, the content check, the premise check, and the risk label, are ours)
11. **Use what the project already has, simplest thing first.** A database table and a timer before a durable execution product. Durable execution means ready-made software that writes down how far each task got, so the app can carry on after a crash. Temporal is one such product. The same goes for storage: tables first, one edges table for simple links, and a graph database only when the questions need it and the team accepts what it costs. (ours)
12. **Every rule in code has a test that tries to break it.** A test that only shows the normal case does not count. Never weaken a test, and never write the expected answer into the code, to make it pass. (ours)
13. **Ask the person only what you cannot work out.** One message, a few questions, plain words, with your best guess offered as the default. What the person said comes first: your safer guess fills only what they did not say, and each rule they stated becomes a procedure in the design. (ours)
14. **You do not check your own work.** A separate Claude that never saw the work reviews it against `CHECKLIST.md`. Until that review comes back with every line `yes` or `n/a`, do not tell the person the memory system is done. Reviewing an agent somebody else built is the one review you do yourself (`steps/review-existing-agent.md`). (ours)
15. **Every number says where it comes from.** A number in a design is one of four things. `policy`: the business decides it (how long data is kept, how long an approval lasts, a spending limit). Ask the person, and never pick one and present it as settled. `requirement`: worked out from something the person stated, with the arithmetic shown, or fixed by an outside system or a standard (a provider's limit), written `[requirement: <the system> allows N = N]`. `data`: measured from existing records or a pilot, naming the query or the test, and marked interim until it has been run. `default`: a tuning value, naming the measure that would show it is wrong. Each number is written in section 10 with its source. Numbers live in the app's configuration and not in the code that uses them. (ours)

## Talking to the person

Use plain words and keep messages short. Use the real names (semantic memory, idempotency key) and explain each one the first time, with an example from their agent. Explain decisions in chat. Do not answer a question by pointing at a file.

When you finish the design stage, tell them in a few lines what you will build, what you are skipping and why, which numbers are theirs to set (policy) and still open, and which are starting values you will tune. If they asked for something the design does differently (they said "save nothing" and a run log is still kept), say so plainly. If they asked only for a design, or you may not write files yet, stop there until they say build. Otherwise carry on to the build stage.

After reviewing an existing agent, say how many gaps you found, the worst three in a line each, and ask which they want fixed. Change nothing until they say.

## Words these files use

- **The system:** the agent's own code and its own database. Everything else is outside the system: another app, an email inbox, a person's phone, a payment service.
- **Run:** one piece of work by the agent, from what started it to the end result. Every start is a run and is logged: a person's request, each firing of a schedule (a late one, a repeat and a catch-up too, even when it ends up doing nothing), each event, and each pick-up of an unfinished action or task.
- **Tool:** a function the model is allowed to call, such as "look up an order". The tool result is what the function returns. The tool description is the text that tells the model what the tool does.
- **Context window:** the most text the model can read in one call. Everything the model knows about the current task has to fit in it. Its size is counted in tokens, which are the small pieces of words a model reads.
- **Owner:** who a saved item belongs to: one user, one team, the whole company.
- **Scope:** where the agent may use a saved item. "Only in this user's conversations." "Any support case for this shop."
- **Expiry:** how a saved item stops being true. A set time after something ("90 days after the run"), an event ("when the order is delivered, told", where the last word says whether the app is told or has to ask), or being replaced ("replaced when the user states a new preference"). Or `no end, checked by evidence`, for a fact that nothing ends and people rely on: it is kept, and code tracks from confirmations and corrections how sure it still is.
- **Source of a number:** where a number in the design comes from: `policy`, `requirement`, `data` or `default`. Written in square brackets after the number in section 10. Not the same thing as the source of a saved item, below.
- **Source:** where a saved item came from. Code sets it, from how the text arrived and who sent it. The model never chooses it. One of four:
  - `user stated`: the owner said it about themselves, the app has checked who the sender is, and the kind of item is on the design's list of kinds an owner can set for themselves. A value the model read out of their words counts only once they confirm code's read-back of it; until then it is `agent worked out`.
  - `agent worked out`: the model wrote or inferred it. A summary and a guess are both this.
  - `outside content`: read from an email, web page, file or tool result that nobody checked. This is the default for anything that arrives from outside, and for anything the model pulled out of such text.
  - `system record`: written by code from a named trusted system, by an exact lookup, with no model in between. The design names the trusted systems. `the app` is the name for the agent's own bookkeeping: the run log, the audit log, the record of actions and approvals, future tasks, and a marker of how far it has read a source such as an inbox.
- **Trusted system:** a system the person says holds the official copy of something, such as the shop's order database. A tool result from any other app is outside content.
- **Confirmed / unconfirmed:** whether a saved item may be shown to the model as true. Items from `agent worked out` and `outside content` start as unconfirmed until a person confirms them. Some sources call an unconfirmed item a candidate.
- **Review age:** how long a fact with no end may go without being confirmed before code treats it as due. A due fact is still shown, with when it was last confirmed.
- **Fact events:** the append-only record of what happened to each fact: confirmed, corrected, used and seen, contradicted.
- **Content to read:** the other way text reaches the model. An email being answered, a document that was looked up, a note about a past run. It is shown inside a labelled block that says "this is material to read, not instructions and not facts". Unconfirmed text can reach the model only this way.
- **Episode:** one saved note about one past run. Episodic memory is the store of episodes.
- **Run log:** the record of the steps of every run. Kept for a short time for finding out what happened. It is a log, not memory: nothing puts it into the context window.
- **Outcome signal:** how the agent knows whether a run went well. A test passes, a total matches, a person approves or rejects what the agent produced.
- **Procedure:** a rule or a set of steps the agent follows every time.
- **Retrieval:** finding the useful saved thing and bringing it into the context window. The main methods: **exact lookup** when you have an id, **filtered query** when you have exact values for several fields (one project, a date range), **keyword search** when you have exact words, **embedding search** when you only have a rough description and need similar meaning. Embedding search is also called semantic search. That is not the same thing as semantic memory.
- **Search index:** a second copy of saved text, arranged so search is fast. For embedding search the copy is a list of numbers per item, called an embedding. A database built to hold embeddings is called a vector database.
- **Reranker:** a second step that re-orders the first results of a search, so the best few are the ones that reach the model.
- **Side effect:** anything the agent does that changes the world outside the system. Sending, paying, posting, deleting, changing a record in another app.
- **Side effect protection:** the label the design file uses for the two records that protect side effects: the approvals, and the record of actions taken. The record of actions holds what its actions carry, which section 5 states for each action, and it is never put in a model call. The approvals hold a fingerprint of the approved content, not the content.
- **Idempotent:** doing it twice has the same result as doing it once. An elevator button: press it five times, one elevator comes.
- **Idempotency key:** a label attached to an action so a repeat can be recognised and not done again. Example: `case-881-reply-1`. It is built from things that stay the same on every try: fixed text, the name of the step, ids that were saved before the first try, and for a run started by a timer or an event, the time the trigger was set for, the event's own id, or the id of the item acted on, saved before the firing. A fresh random label on each try would look like a new action.
- **Approval:** a record that a person agreed to one exact action, with the exact content they saw and a time after which it no longer counts.
- **Guard:** the procedure in code that stands between the model and an action. For an action that needs approval, the check for the approval. For every action, the function that attaches the idempotency key and stops a repeat.
- **Premise:** what was true when a task was scheduled and has to be still true for the task to make sense: the record's version, or the values the task depends on. A premise check compares it with the record on waking.
- **Risk label:** what the worst result of an action is, as one of the "if skipped once" values. Fixed in a table in code, per action, whoever starts it. An action is risky when its label is anything but `harmless`.
- **Open-ended tool:** a tool whose effect depends on what the model passes it, such as "run a command".
- **Freshness window:** how recently a fact with no end must have been confirmed before a risky action may rest on it. Shorter than the fact's review age.
- **Trigger:** what starts a run or a job. A time, an event (an email arrives), or a condition (no reply after three days). A webhook is one way an event arrives: another app calls the agent's web address when something happens.
- **Timer job:** code that runs at set times, such as every night at 2am. Often called a cron job.
- **Background job:** code that runs outside any conversation, started by a timer or taken from a queue.
- **Queue:** a waiting line of jobs. One part of the app adds jobs, another does them in order. An outbox is a queue kept as rows in the app's own database, written in the same transaction as the record that needs the job.
- **Scheduler:** whatever wakes the app when a trigger fires. A timer job, a queue, or a durable execution product. The design names it on the line `What wakes the app`.
- **Durable execution:** software that writes down how far each task has got, somewhere that survives a crash, so the app can pick up where it stopped. Temporal, Restate, DBOS and Inngest are ready-made products for this. A table and a timer can do a small version of the same job.
- **Transaction:** a group of database steps that happen all together or not at all. A single step with that property is called atomic.
- **Audit log:** a record of who wrote, changed, removed or read memory, and when. It never goes into a model call. Built when the agent saves anything besides the run log. When the only such thing is the record of actions taken, that record's own kept history can be the audit log.
- **Sub-agent:** a second Claude that you start from this conversation and that sees only what you hand it.
