# agent-memory-design

A Claude skill. When you are building an AI agent with Claude and the agent needs to remember things, Claude uses this skill to work out what the agent should remember, write that down as a design, and build it as code with tests.

**Status: v0.1.** Built twice end to end on sample agents made from scratch (a weekly status poster and an interview scheduler), each checked by a separate reviewer, plus seven rounds of independent review of the skill itself. Not yet used on an agent in production. Expect the defaults to change after that. The review record is in [notes/agent-memory-design](../../notes/agent-memory-design).

## What it does

Memory for an agent is more than a notes file the model reads. It is database tables, functions, jobs that run on a schedule, and tests. This skill makes Claude treat it that way:

- **Code decides** what gets saved, where it came from, what replaces what, what has expired, who can see what, when something wakes up, and that nothing happens twice.
- **The model suggests** facts worth saving and new procedures. Code checks each suggestion.
- **Instructions guide** the model on when to use memory and what to do with what comes back.

It covers seven memory types: working memory (what is in front of the model now), semantic memory (facts), episodic memory (notes on past runs), procedural memory (how to work), external memory and retrieval (finding things), parametric memory (what the model already knows), and prospective memory (things to do later). Most agents need only some of them. The skill's default is to skip a type unless the agent gives a reason to build it.

What is built besides the memory types depends on the agent too:

- A short-lived log of each run: always. For an agent that saves nothing else it holds no content, only step names, sizes and errors.
- Protection on any action that reaches outside the agent, such as sending an email: when the agent has such an action. When runs start on a schedule or an event, also what wakes the app and a catch-up for missed firings.
- An audit log, a record of who changed memory and when: when the agent saves anything besides the run log.

The design is as small as the agent. An agent that answers one request and saves nothing gets a design of about 40 lines and one standing test.

## Who it is for

Anyone building an agent, assistant, bot or multi-step workflow on a large language model with Claude, where the model is one that another company runs and your code calls over the internet. You do not need to know the names of the memory types. Claude explains each one in plain words when it comes up.

## Install

**Claude Code.** Copy the `agent-memory-design` folder into `~/.claude/skills/` (all projects) or `.claude/skills/` inside a project.

**Claude.ai.** Zip the `agent-memory-design` folder and upload it in Settings, under Capabilities, then Skills.

## How a run goes

1. **Understand.** Claude reads your project and answers eight questions about the agent: what it is for, who uses it, which actions change the outside world, how it knows a run went well. It asks you only what it cannot work out, in one short message.
2. **Decide.** For each memory type, build or skip, with a reason that is about your agent.
3. **Design.** Claude writes `MEMORY-DESIGN.md` into your project: what is saved and who owns it, when it expires, which rules live in code, how each action is protected from running twice, how things are found again, and the names of the tests that must try to break it. A script checks the file is complete.
4. **Build.** Claude builds it in your project's own programming language and database, starting with the simplest thing that works, and writes a test that tries to break every rule that lives in code. It saves the test output, with the command that ran it, and a check that removing each rule makes a test fail, under `_run/` in your project.
5. **Review.** A separate Claude that never saw the work goes through the 24 lines in `CHECKLIST.md`, runs the tests itself, removes each rule in a copy to see a test fail, and answers yes, no or not applicable for each. Failures are fixed and checked again.

`reference/example-email-agent.md` walks one agent through all of this.

## What it will not do

- **Pick products.** It uses the database and scheduler your project has. It does not choose a search product or a memory library for you.
- **Cover fine-tuning,** which means retraining the model on your own data. It is for hosted models you cannot change.
- **Tell you the design is right because a script passed.** See "Known limits" below.
- **Let the builder grade its own work.** Claude does not say the memory system is done until a separate reviewer has passed every line.
- **Switch on rules by itself.** An agent built this way can suggest a new procedure from past runs, if you allow it. A person approves it before it is used.
- **Promise that secrets never slip through.** The write functions refuse common shapes of passwords, keys and card numbers. Pattern checks miss things.

## Known limits

- **Not tested on a real agent.** See the status line at the top.
- **The checker checks form, not truth.** `scripts/check_design.py` makes the design state its judgments as fixed choices (is this procedure harmless if skipped, is this key part saved before the first try, is there an outcome signal) and enforces the rules that follow from each choice. It cannot tell whether a choice is honest. It cannot tell whether a row called a summary is really a fact, whether an item marked permanent should be, whether one agent is really one, whether every action that reaches outside is listed, whether every rule you stated made it into the design, or whether a content check catches what its rule promises. It prints each of these under "FOR THE REVIEWER TO JUDGE". A clean run means the file is complete and agrees with itself, and nothing more.
- **The checker reads no code.** With `--project` it confirms that each test file named in the design exists and defines a test with that name, for Python, JavaScript and TypeScript, Go, Rust, Ruby, Java, Kotlin and C# files. For other files it only checks that the name appears, and says so. For Python it also fails a named test that asserts nothing, directly or through a function in the same file. It does not run tests or read functions. The reviewer does.
- **The review path through a second chat is unverified.** In a tool that cannot start a second Claude, the skill tells you to open a new chat for the review. We have not confirmed that a second chat on Claude.ai can see the same project files. If it cannot, paste the reviewer's table back by hand.
- **Planning modes are untested.** The skill says what to do when Claude may not write files yet. We have not run it in such a mode.
- **Several defaults are arbitrary numbers.** Every one is marked, in the skill and in each design.
- **Section 10 is matched by number and word, not by item.** The checker looks for each number with the word that follows it (`90 days`). If two items share the same number and word, one line in section 10 covers both.

## What is ours and what is from sources

The seven types, the four starting questions (what should survive, how does it come back, when is it updated or forgotten, does anything need to wake the system later) and much of the detail on each type come from the video below. In the reference files, each default is marked with where it comes from: the video, a named source, or our own judgment. Several rules are our own judgment and no source backs them. The main ones:

- Keep a past run as an episode only when it teaches something.
- No outcome signal, no episodic memory.
- Code sets where a saved item came from, the model never does, and what an owner can confirm by their own words is a short written list.
- Deciding instructions or code by asking what happens if the model skips the rule once.
- A procedure is suggested when three separate episodes carry the same lesson. The three is arbitrary.
- A person approves every suggested procedure. The guide we drew on accepts other checks too. Requiring a person every time is our choice.
- When runs start on a schedule or an event, each action's key carries the planned time of the firing, the event's own id or the id of the item acted on, because a trigger can fire twice.
- Deleting an owner's data keeps each action's key and status, so a repeat after the delete is still stopped.
- An action that sends outside or model-written text without approval of that exact text passes a content check in code fitted to where the text goes.

## Files

```
SKILL.md                      when to use it, the stance, the rules, the words
steps/                        five step files, read one at a time
reference/                    one file per memory type, one for every store and the run log,
                              one for actions with side effects, one worked example
assets/                       the design file template and a filled example
scripts/check_design.py       completeness check for the design file (Python standard library)
CHECKLIST.md                  the 24 checks the reviewer uses
```

To see the checker run: `python3 -B scripts/check_design.py assets/example-memory-design.md`

## Sources

- Jam With AI (Shirin Khosravi Jam), "AI Agent Memory: 7 Types Explained in 12 Minutes", 2026. youtube.com/watch?v=bK1clrG-boc
- Sumers, Yao, Narasimhan, Griffiths, "Cognitive Architectures for Language Agents" (CoALA), 2023. arxiv.org/abs/2309.02427
- Hidekazu Konishi, "AI Agent Memory Design Guide". hidekazu-konishi.com/entry/ai_agent_memory_design_guide.html
- Let's Data Science, "Durable AI agent workflows". letsdatascience.com/blog/durable-ai-agent-workflows
- Neo4j, "Modeling Agent Memory". medium.com/neo4j/modeling-agent-memory-d3b6bc3bb9c4
- LangChain docs, long-term memory. docs.langchain.com/oss/python/langchain-long-term-memory
- Bean Labs research log on Voyager. beancount-cms-v2.onrender.com/bean-labs/research-logs/2026/05/08/voyager-open-ended-embodied-agent-lifelong-learning
- arXiv 2605.22148, a 2026 paper on self-improving agents known as Ratchet. arxiv.org/abs/2605.22148
- "Library Drift: Diagnosing and Fixing a Silent Failure Mode in Self-Evolving LLM Skill Libraries", 2026. arxiv.org/abs/2605.19576
- "Always-On Agents: A Survey of Persistent Memory, State, and Governance in LLM Agents", 2026. arxiv.org/abs/2606.30306
- Wang, Mao, Fried, Neubig, "Agent Workflow Memory", 2024. arxiv.org/abs/2409.07429
- Zhao and others, "ExpeL: LLM Agents Are Experiential Learners", 2023. arxiv.org/abs/2308.10144
- CodeConductor, "7 Types of AI Agent Memory Every AI Engineer Should Know". codeconductor.ai/blog/types-of-ai-agent-memory/
- Shudipto Trafder, "Agent memory: 7 types, and 2 of them aren't memory". dev.to/shudiptotrafder/agent-memory-7-types-and-2-of-them-arent-memory-6oi
- Temporal, "LangGraph in production: Temporal's LangGraph Plugin adds Durable Execution" (a vendor's post). temporal.io/blog/temporal-langgraph-plugin-durable-execution
- Tian Pan, "Durable Agents: Why Async Queues Break for Long-Running AI Workflows". tianpan.co/blog/2026-04-23-durable-agents-async-queue-workflow-checkpoint

Some of these are background reading only. No rule in the skill files is tagged to the LangChain docs, the Always-On survey, Agent Workflow Memory, ExpeL, or the Temporal and Tian Pan posts.

Built by [Nayan Kanaparthi](https://nayankanaparthi.dev).
