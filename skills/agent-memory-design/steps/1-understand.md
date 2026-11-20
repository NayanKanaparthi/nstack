# Step 1: Understand the agent

Before deciding anything about memory, find out what this agent is for and what can go wrong. Every later decision hangs on these nine answers. The questions come first because once you have picked a database or a memory library, it is very hard not to design around it.

## 1. Read before you ask

Look at what already exists. Most of the nine answers are in the project or in what the person has already said.

- The README, any spec or plan, and the conversation so far.
- The main instructions the model is given (often called the system prompt), and the list of tools the model may call.
- The functions that change something outside the system: send, pay, post, delete, write to another app.
- The database's tables and columns (its schema), and anything else that already stores state between runs.
- Anything that runs on a schedule or in the background.
- Tests, if there are any. They show what the builder already cares about.

If the agent does not exist yet, use the person's description and the plan you have made together.

## 2. Answer the nine questions

Copy `assets/memory-design-template.md` into the project root as `MEMORY-DESIGN.md` and write each answer into section 1. If you may not write files yet, keep the same sections in your plan and write the file when the build starts.

Each answer is one line that starts with a dash and ends with how you know, in brackets:

- `(worked out)`: it came from the project or the conversation.
- `(asked)`: the person answered. Use this too when you worked something out and the person then confirmed it.
- `(assumed)`: nobody could answer, so you picked the safer option. Every assumed answer is repeated in section 10 of the design file, starting with its number and ending with whether the person has been told, such as `A5 assumed: no outcome signal. (not told yet: in the design summary)`, saying how and when they will be told. When you tell them, change it to `(told)`.

| | Question | What the answer decides |
|---|---|---|
| A1 | What is the agent for, in one sentence? | Whether a memory type has any reason to exist |
| A2 | Is it one agent or several sharing memory? Who uses it: one person, many separate people, teams? | The owner and scope of everything saved, and who may read or write which store |
| A3 | What starts a run: a person, a schedule, an event? Does a piece of work finish in one conversation, or carry on across days? | Whether something must wake the app and catch up on missed firings, how idempotency keys are built, whether anything must survive between runs, and whether the agent needs prospective memory |
| A4 | Does it have actions with side effects (send, pay, post, delete, change another app)? Which cannot be undone? | Which procedures must be code, and which actions need an idempotency key and an approval |
| A5 | Is there an outcome signal: a test, a number that matches, a person saying yes or no to what the agent produced? | Whether it can have episodic memory at all |
| A6 | What does it read that nobody checked (emails, web pages, files, tool results)? | What can never be saved as confirmed |
| A7 | What goes wrong if it forgets something? What goes wrong if it remembers something false or out of date? | Which mistakes the tests must try to cause |
| A8 | Which model does it use, and what does it need to know that the model cannot know (private, recent or exact)? | What has to come from semantic memory or retrieval, never from the model's own knowledge |
| A9 | Also true of this agent: does someone wait live for its answer, can the same fact be changed by more than one route, does a model turn text into facts, is high volume expected? | Which of the v0.2 rules apply: speed, conflicts between facts, checks on what the model extracts, planning for volume |

Five answers start with a fixed value, because the rest of the design is switched on or off by them. They are stated here once and nowhere else.

- **A2 starts with `one agent` or `several agents`.** Several means two or more agents, each with its own instructions and acting for users, read or write the same store. The agent's own memory jobs (the episode writer, the job that groups episodes, a summarizer) are part of that one agent, even though they call the model. People who use the agent are not agents: "12 support staff" is still `one agent`.
- **A3 starts with how runs start:** `a person`, `a schedule` or `an event`, or several joined by semicolons, such as `a person; a schedule`. A schedule is any timer: every night, every hour, a set day. An event is something arriving that starts a run without a person: a new email, a webhook, a message on a queue. Then a full stop and the detail, including whether work finishes in one conversation or carries on across days.
- **A4 starts with `none` or `yes`.** The system is the agent's own code and its own database. Writing a row into the agent's own table is not a side effect. Anything that reaches outside is: an email, a chat message, a notification on someone's phone, a payment, marking an email as read in an inbox, writing a status back to another app. A message to a colleague inside the same company is still a side effect, because once it is delivered the agent cannot take it back. Flagging something for a person is a side effect only if the flag leaves the system. A row on the agent's own screen is not one.
- **A5 starts with `yes` or `no`.** Be strict. "The user did not complain" is not an outcome signal. A person approving, editing or rejecting what the agent produced is one. So is a test, or a total that has to match a trusted record of amounts. A person's decision about the business matter itself counts only if a no would mean the agent got something wrong. Approving the payment of an invoice says the invoice should be paid. It says the agent matched it correctly only if a wrong match would have been rejected at that step.
- **A9 starts with `none`, or one or more of `someone waits live`, `several routes change a fact`, `a model turns text into facts`, `high volume`, joined by semicolons.** Then a full stop and the detail. Write the line for every design: `none` is the answer when none of the four holds. `someone waits live`: a person is waiting while the agent runs. `several routes change a fact`: the same fact can be changed by the person in chat, by a screen, by the agent or by an import, or more than one copy of the agent runs at once. `a model turns text into facts`: a model reads text and proposes facts to save. `high volume`: the person stated a volume to plan for; ask when the project hints at one.

## 3. Ask only what you cannot work out

Put your questions in one message. Four at most (the four is arbitrary, the point is few). Use plain words, say why you are asking in half a line, and offer your best guess so the person can just say yes.

What usually cannot be worked out from a project:

- The outcome signal, when no approval step or test exists yet.
- Policy numbers: how long things are kept, how long an approval lasts, any limit on money or on who can be reached. These are business or legal choices. Ask for each one the agent needs. If the person cannot say yet, use a starting value, mark it `[policy, not told yet]` in section 10, and keep any action that depends on it behind approval until they give it. A policy number you do not ask about, because the questions are used up, is handled the same way: a starting value marked `[policy, not told yet]`, and it goes in the list of policy numbers the person still has to give when you tell them about the design (`steps/3-design.md`, section 6). `reference/every-store.md` gives starting values to offer.
- Who is allowed to approve a side effect, who may confirm something the agent read but nobody checked, and who may switch on a new procedure.
- Whether an action the code can do should be off limits to the agent altogether.
- Whether the agent may suggest new procedures from what it learns. If nobody answers, it may not.
- Limits on an action: the most it may pay, how many people one message may reach, which addresses it may go to. Policy numbers, like the others.
- When someone waits live: how long an answer may take. When high volume is expected: how many users, facts and runs to plan for. Past the four questions, the time allowed for memory reads is a starting value with a `default` source, and A9 names `high volume` only once the person has stated a volume (`reference/production.md`).

What you should not ask:

- Which database, search product or scheduler to use. Use what the project has.
- Anything you can read in the code.
- Whether they want "semantic memory" or "episodic memory". That is your decision in step 2, and those words mean nothing to someone who has not met them.

> Good: "When staff edit a draft before sending, should the agent learn from that edit for next time? I would say yes."
> Bad: "Do you want episodic memory enabled?"

## 4. When nobody can answer

What the person said comes first. The safer option fills only what they did not say. If they asked for something to happen on its own ("send it every morning"), it happens on its own, and you do not add an approval step they never asked for, except the one in the table below: an action that depends on a policy number they have not given yet waits for approval until they give it. If they asked for a limit ("never more than one a day"), the limit stays.

For the rest, pick the safer option, mark the answer `(assumed)`, list it in section 10, and carry on. The safer option is the one that saves less, shows the model less, and does less on its own. For each question:

| Question | The safer option |
|---|---|
| A2 | `one agent`, used by many separate people, so every saved item belongs to one user and is never shared |
| A3 | `a person`, unless the description names a time or an interval ("every night", "at 9am") or something arriving that starts the work. One conversation, unless it says "later", "follow up", "remind" or names a due date |
| A4 | When it is unclear whether something leaves the system (a "flag", a "notification"): it is a row on the agent's own screen and not a message. List the question in section 10. |
| A5 | `no` |
| A6 | Everything the agent reads from outside is unchecked |
| A8 | "The model named in the project's settings", and it knows nothing private, recent or exact |
| A9 | Leave a value out only when the project shows it does not hold. When unsure whether someone waits live, they do. When unsure whether a second route can change a fact, it can. |
| Approval before an action (section 5) | No approval when the person described the action as happening on its own, unless it depends on a number marked `[policy, not told yet]`: then it waits for approval until the person gives that number. Otherwise, approval for an action that costs money or cannot be undone. Either way, a line in section 10 |

A1 and A7 are never assumed. If you cannot say what the agent is for, ask.

## 5. Before moving on

All nine lines are filled and each ends with `(worked out)`, `(asked)` or `(assumed)`. A2, A3, A4, A5 and A9 start with their fixed value. Now read `steps/2-decide.md`.
