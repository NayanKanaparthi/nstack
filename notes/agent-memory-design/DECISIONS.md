# Design decisions the video does not answer

Status on 2026-11-16:

| Decision | Status |
|---|---|
| D1. Which runs are saved as episodes | DECIDED. Nayan handed this to Claude to settle. The "only keep runs that teach something" filter is Claude's judgment, not from a source. Check it on a real agent. |
| D2. A person approves a rule before it is switched on | ACCEPTED by Nayan |
| D2. Three separate successes before a rule is suggested | ACCEPTED as a starting default. The 3 is arbitrary. |
| D3. Rules that stop an action happening twice | ACCEPTED by Nayan |
| D4. Trust labels on facts | In the draft. Explained in plain words on 2026-11-16, waiting for Nayan to object or not. |
| D5. Text or code test for rules | In the draft. Same. |
Lines marked (mine) are Claude's judgment. Everything else has a source at the bottom.

## How the skill is used (corrected by Nayan, 2026-11-16)

The skill is not a questionnaire that ends in a document for a person to act on. Claude uses it while planning an agent build with someone. Claude works out the memory design itself from what the agent is for, asks the person only what it cannot figure out, writes the design into a plan file in the project, and then builds from that plan. The reader of the plan is Claude. The result is a built memory system.

Writing rule for the skill and the blog: plain words. Any term a beginner would not know gets explained the first time it shows up, with an example.

## Plain words

- **Episode:** a short note about one past run. What the task was, what the agent did, how it ended.
- **Procedure:** a rule the agent follows every time.
- **Promotion:** turning a note about one run into a rule for every run.
- **Candidate:** a rule the agent has suggested but nobody has switched on yet.
- **Gate:** a check that must pass before something is allowed. Here, before a suggested rule is switched on.
- **Replay:** trying the suggested rule again in a safe test setting to see that it works.
- **N:** how many separate times something has to work before we believe it. No source gives the number.
- **Baseline:** how well the agent does with no saved rules at all. A rule that does not beat this is not helping.
- **Outcome signal:** how the agent knows a run went well or badly. A test passing, a number matching, a person saying yes or no.
- **State manager / durable execution:** the part of the system that writes down how far each task has got, somewhere that survives a crash, so the app can pick up where it stopped. Temporal, Restate, DBOS and Inngest are ready-made versions.
- **Checkpoint:** one of those written-down "I got this far" notes.
- **Side effect:** anything the agent does that changes the outside world. Sending an email, issuing a refund.
- **Idempotent:** doing it twice has the same result as doing it once. An elevator button: press it five times, one elevator comes.
- **Idempotency key:** a label attached to an action so the receiving service can recognise a repeat and not do it again. Example: "task-42-send-followup". It is built from things that stay the same on every try (the task number and the step name). A fresh random label on each try would look like a new action.

## Scope (settled by Nayan)

The skill designs memory for agents built on closed models behind an API. Fine-tuning is out of scope. Parametric memory is a fixed input: the skill records which model, and designs nothing there.

The video is the starting point, not the limit. The skill can go past it where that makes the design more robust.

## D1. When does a run become an episode?

Three layers, not one:

1. **Log every run.** Raw events, cheap, short retention (days to a few months). This is a log, not memory. Nothing retrieves it into context.
2. **Write an episode in the background, after the run ends, and only once the outcome is known.** Never in the middle of the run.
3. **Only keep an episode that carries a lesson (mine).** One of: the run failed, a human corrected it, it recovered from an error, or it was the first run of a new kind of task. A routine success that matches an existing procedure adds one to that procedure's success count and stores nothing new.

Hard precondition (mine): **no outcome signal, no episodic memory.** If the agent cannot tell whether a run worked (a test, a ledger check, a human accept or reject), the skill must say skip episodic memory, because stored episodes would teach it unverified behavior.

Episode record: task, short list of actions, outcome, outcome source, date, owner and scope, link to the raw log, link to the previous episode of the same task kind.

## D2. When does an episode become a procedure?

ACCEPTED by Nayan, 2026-11-16: the agent may suggest a new rule, but a person has to approve it before it is switched on. The rest of D2 (the count, the replay check, retiring rules) is still PROPOSED.

No source gives a number. The field's answer is a gate, not a count.

1. **Never automatic.** A background job may draft a candidate procedure from episodes. Candidates live apart from live procedures and are never loaded as rules.
2. **The gate depends on what the procedure can break (mine):**
   - Guidance text the model reads (prompt rule, skill): N independent successes on different inputs, no contradicting failure in the same window, then a human approves the diff. Default N = 3. The 3 is arbitrary. It is a starting value the user of the skill must set, not a finding.
   - Anything that becomes a code gate or triggers a side effect: replay against saved episodes or tests, then human approval. No success count replaces this.
3. **Promotion is reversible.** Every live procedure keeps success and failure counts after promotion, has a version, and is retired when it stops beating the no-procedure baseline. Cap the number of live procedures.

## D3. State manager

What Nayan was recalling is durable execution: Temporal, Restate, DBOS, Inngest, LangGraph checkpointers. It is not an eighth memory type. It is the runtime that makes prospective memory reliable.

The skill does not pick a product. It writes the contract any of them must meet:

- Each step's result is saved outside the process.
- Each action with a side effect gets an idempotency key built from stable ids (task id plus step name), saved before the action runs.
- After a long gap or an unknown outcome, look up whether the action already happened before retrying.
- An approval is bound to the exact action, its parameters, the version of the record the approver saw, and an expiry.
- On wake, re-read the live state before acting.

## D4. Trust before save, in the schema (mine)

Add to every fact record: source, source_type (user stated / agent inferred / external content), status (candidate / confirmed), confirmed_by, created_at, supersedes.

Rule in the write function: user-stated facts can enter as confirmed. Inferred facts and anything from emails, web pages or tool results enter as candidate. Only confirmed facts are loaded into context as facts.

## D5. Guidance or gate (mine)

Per procedure, the skill asks one thing: if the model ignores this once, what happens? If it costs money, sends something outside the system, or cannot be undone, it is a code gate. Otherwise it is text the model reads.


## Form and architecture (2026-11-16)

ACCEPTED by Nayan: a skill, not a CLI or plugin.

The skill has two stages, design then build. Claude answers QUESTIONS.md, writes the design into the project, then builds the code pieces in BUILD-MAP.md using the project's own stack, with the tests that try to break each rule. The skill folder carries example code patterns in reference/patterns/ that Claude adapts to the project's language. They are examples, not a library to install.


## Changed after review 1 (2026-11-16), chosen by Claude to keep the fix moving, Nayan can overrule

- D2, what is counted before a procedure is suggested: 3 separate saved episodes that carry the same lesson. Not "3 successes", which means nothing for a procedure that does not exist yet. The 3 is still arbitrary. After a procedure is live, its own success and failure counts decide whether it stays.
- D4, who sets the source of a fact: code sets it, from the channel the text came through and the verified identity of the sender. The model can never pass the source. A verified sender's statement about themselves counts as confirmed only for kinds the design file names as safe for that (for example reply language). Everything else read from outside enters unconfirmed.
- The run log and the side effect protections (idempotency key, approvals) no longer belong to a memory type that can be skipped.

## Sources

- LangChain docs, long-term memory (hot path vs background writes): docs.langchain.com/oss/python/langchain-long-term-memory
- Neo4j, Modeling Agent Memory (episodes written in the background after feedback): medium.com/neo4j/modeling-agent-memory-d3b6bc3bb9c4
- Hidekazu Konishi, AI Agent Memory Design Guide (replay / repetition / review gate, candidates area, TTLs): hidekazu-konishi.com/entry/ai_agent_memory_design_guide.html
- Wang et al., Agent Workflow Memory, 2024 (workflows induced from successful runs): arxiv.org/abs/2409.07429
- Zhao et al., ExpeL, 2023 (insights from success and failure pairs, upvote and downvote): arxiv.org/abs/2308.10144
- Ratchet, 2026 (self-generated skills +0.0pp, human-curated +16.2pp over no-skill baseline): arxiv.org/abs/2605.22148
- Library Drift, 2026 (skill libraries degrading below the no-skill baseline): arxiv.org/abs/2605.19576
- Always-On Agents survey, 2026 (missing validation gate between storing and trusting a procedure): arxiv.org/abs/2606.30306
- Voyager notes, Bean Labs research log (self-verification ablation, limits outside binary success): beancount-cms-v2.onrender.com/bean-labs/research-logs/2026/05/08/voyager-open-ended-embodied-agent-lifelong-learning
- Let's Data Science, durable AI agent workflows (idempotency keys, look up before retry, approvals bound to actions): letsdatascience.com/blog/durable-ai-agent-workflows
- Temporal, LangGraph plugin post (vendor claim: checkpoints are not durable execution): temporal.io/blog/temporal-langgraph-plugin-durable-execution
