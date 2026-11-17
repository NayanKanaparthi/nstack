# Agent memory design: research notes

Working notes for the agent-memory-design skill. Not a skill yet: no SKILL.md until the questions at the bottom have answers.

## The seven types that keep getting cited

The "seven types" list going around in 2026 (CodeConductor, a widely shared dev.to/Medium piece, several others) extends the CoALA paper's split (working memory plus episodic, semantic and procedural long-term memory) with three more.

| # | Type | Timescale | Holds | Usually lives in | Read by |
|---|---|---|---|---|---|
| 1 | Working | Session | Prompt, recent turns, tool outputs, in-progress reasoning | The context window | Always in view, paid for on every call |
| 2 | Semantic | Long | Stable facts and preferences (the "know-what") | Structured store for clean fields, vector store for fuzzy recall | Key lookup or similarity |
| 3 | Episodic | Long | Specific past events, decisions and their outcomes | Event log plus an index | Similar-case search, time range |
| 4 | Procedural | Long | Workflows, tool sequences, operating rules (the "know-how") | System prompt, rules store, skills | Exact key, never similarity |
| 5 | Retrieval (RAG) | Depends on source | External knowledge pulled in at query time | Vector or lexical index | Search |
| 6 | Parametric | Frozen | What the model learned in training | Weights | Implicit |
| 7 | Prospective | Short and long | Intentions and scheduled actions | Scheduler or job queue | A clock or an event fires it, not a query |

## The argument worth stealing

Two of the seven aren't things you design as stores:

- **Retrieval is the pipe, not the water.** It's how semantic and episodic content reaches working memory. Design it as the read path of the other stores.
- **Parametric memory is a model choice.** You don't build it. You pick a model, or fine-tune one.

So the design surface is really five stores (working, semantic, episodic, procedural, prospective) plus one read path (retrieval) plus one upstream decision (the model).

The piece almost nobody builds is **consolidation**: promoting repeated episodes into durable semantic facts or procedural rules. Without it, episodic logs pile up unused.

## Practical rules from the sources

- Keep facts, event logs and rules in separate stores, even when they share a database.
- Never use similarity search for exact rules or thresholds.
- Plan how working memory gets evicted or summarized early. It drives cost.
- Add types in order of need: working, then semantic, then episodic, procedural, retrieval, and prospective last.

## Where this already shows up in my own work

- Orivra / MailWeave: retrieval as a read path, bounded context, permission-aware caching, freshness and invalidation.
- JAS and my context layer: semantic memory (facts with private, profile and public levels), episodic (meeting notes, chats), procedural (learned_principles, skills).
- TRACE: procedural rules done in deterministic code, the model only for ambiguous cases.

## Questions to answer before writing SKILL.md

1. What does the skill take in? A one-paragraph use case, or a structured intake?
2. For each store, what questions does it ask? Draft them for the write side (what gets written, when, by whom) and the read side (key, similarity or trigger), plus update and forget (staleness, conflicts, deletion, privacy).
3. What does it hand back? A design doc, a schema, starter code, or all three?
4. How will I know it works? Pick 3 real agents (TRACE, Orivra, JAS) and check whether its design matches what I'd build by hand.

## Sources

- Sumers, Yao, Narasimhan, Griffiths. Cognitive Architectures for Language Agents (CoALA), 2023. arxiv.org/abs/2309.02427
- A Survey of Agent Memory in the Second Half, 2026. arxiv.org/abs/2602.06052 (uses five cognitive types: sensory, working, episodic, semantic, procedural)
- CodeConductor, 7 Types of AI Agent Memory Every AI Engineer Should Know. codeconductor.ai/blog/types-of-ai-agent-memory/
- Shudipto Trafder, Agent memory: 7 types, and 2 of them aren't memory. dev.to/shudiptotrafder/agent-memory-7-types-and-2-of-them-arent-memory-6oi
