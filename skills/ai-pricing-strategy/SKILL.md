---
name: ai-pricing-strategy
description: Run a structured, economics-grounded pricing strategy session for an AI product, feature, or service. Use whenever the user asks about pricing an AI product, setting tiers, choosing a pricing model (seat / usage / hybrid / outcome-based), repricing an existing offering, monetizing a new feature, or asks "what should I charge for this." Also use when the user mentions willingness to pay, value capture, pricing power, total value created, or wants a pricing recommendation defended on first principles instead of vibes. Don't just give pricing advice off the top — run this skill to do it properly, even if the user asks casually.
---

# AI Pricing Strategy

A structured 12-stage process to produce a defensible pricing recommendation for an AI product or feature. Built on microeconomics (Total Value Created, consumer-firm surplus parity, Porter's differentiation logic) and value-based pricing literature (Monetizing Innovation, Ulwick's Jobs-To-Be-Done), operationalized into actual decision steps with Claude's tool capabilities woven in where they earn their keep.

## Honest framing — say this to the user before starting

Before running any stage, surface this to the user explicitly:

> This skill produces a defensible pricing *range and model*, plus a list of risks and what to validate first. It cannot output a confident single dollar number — that requires real customer data (interviews, WTP surveys, beta pricing tests). The job here is to make the pricing decision defensible, not to replace the decision. Expect 30–60 minutes for a full session; we can break across stages if needed.

Get explicit acknowledgment, then proceed.

## When to invoke

Trigger when the user:
- Asks how to price a new AI product, feature, or service
- Is choosing between pricing models (seat, usage, hybrid, outcome-based)
- Wants to reprice an existing offering
- Asks about willingness to pay, value capture, surplus split, or pricing power
- Says something like "I have this AI thing — what should I charge?"
- References any concept from value-based pricing (TVC, WTP, surplus parity, broad-scope differentiation)

Do **not** trigger for:
- Generic "what is good SaaS pricing" educational questions
- Questions purely about pricing psychology / charm pricing / $9.99 vs $10
- Discount or sales-process questions (sales motion, not pricing strategy)

## Operating principles

These govern the whole session — re-read them between stages.

1. **Force quantification.** Vague answers like "high WTP" or "differentiated" don't count. Push for numbers, even rough ones. Surface assumptions explicitly.
2. **Push back on aspirational claims.** When the user says they're differentiated, ask for evidence. "3% more accurate" is not differentiation, it is decoration.
3. **Refuse to skip stages.** Especially Stage 4 (Effective WTP). The temptation to jump from "we create $10k of value" to "charge $10k" is exactly what this skill exists to prevent.
4. **Use Claude's capabilities aggressively where they help, sparingly where they don't.** Web search is high-leverage for alternatives, wage benchmarks, and competitive landscapes. It is poor for inferring real WTP. Be honest about which is which.
5. **Never output a single dollar number with confidence.** Output ranges, with reasoning. The user can narrow with real data.

## Pre-flight: Context load (silent)

Before Stage 1, silently check for context about the product being priced:

1. Is there a current chat or attached files about this product? Use them.
2. Does memory contain product context (e.g., the user has been working on a specific product for months)? Use it.
3. Use `conversation_search` if the user references something from a past chat ("my AIGIS pricing", "for Provenance", "the tool I was building last month"). Pull the relevant prior context before asking the user to re-explain.

If rich context exists, ground the session in it and *do not* make the user re-describe the product from scratch. Confirm the framing with them and move on.

If context is thin, ask a scoping question covering:
- What is the product/feature being priced?
- Is it standalone or a feature within an existing product?
- Customer type: B2C, SMB, mid-market, enterprise?
- Company stage: pre-launch, early traction, scaling, or mature?

---

## The 12-stage flow

Walk through stages in order. After each stage, briefly summarize what was decided before moving to the next. Maintain a running working document (in chat) so the final synthesis in Stage 12 has all the inputs.

### Stage 1 — Jobs To Be Done (JTBD)

**Goal:** Define what the customer is actually trying to get done, not what the product does.

Ask:
- What struggle is the customer resolving?
- Functional dimension: practical outcome they need
- Emotional dimension: anxiety reduced, confidence gained, reputation protected
- Social dimension: how they want to be perceived
- Buyer vs user vs value-receiver: are these the same person? If not, flag the split-incentive problem now — it will compress effective WTP in Stage 4.

**Claude does:**
- If rich product context exists, propose a JTBD framing for the user to refine rather than asking from scratch.
- If thin, ask the questions above one at a time.

**Output:** A single sentence: "Customer is trying to [job] in order to [outcome], without [pain]."

### Stage 2 — Next-best alternatives

**Goal:** Map what the customer would do if your product did not exist. Alternatives bound Effective WTP downstream. This stage is high-leverage because most users skip it or under-research it.

For each of six categories, identify what exists and what it costs the customer in money + time + friction:

1. **Direct competitors** — products doing the same thing
2. **Indirect substitutes** — different products solving the same job differently
3. **DIY with raw LLMs** — could a customer replicate 60–80% of this with $20 of ChatGPT Plus or API credit? Be honest. This is the "GPT wrapper problem" stated as a pricing problem.
4. **Hire labor** — paralegal, junior analyst, offshore contractor, virtual assistant
5. **Open-source / self-hosted** — including open-source AI models
6. **Do nothing / status quo** — the customer keeps doing what they do. Almost always underweighted. Include it.

**Claude does:**
- Run `web_search` for each of the first five categories. Queries like: "[product category] competitors 2026", "[customer role] hourly rate", "open source [JTBD]".
- For DIY-with-raw-LLMs, honestly assess: how good a job could a generic frontier LLM at $20/month do here? State it plainly.
- For "do nothing," estimate the customer's current cost of the status quo.
- Present findings as a structured table for user validation.

**Output:** Table — alternative, cost to customer, quality vs your product. Star the most threatening one.

### Stage 3 — Total Value Created (TVC)

**Goal:** Quantify the value gap your product creates *relative to the next-best alternative*, not in a vacuum.

Conceptually: TVC = (Customer WTP for your product) − (Customer cost of next-best alternative) − (Your cost to serve)

In practice, work with value drivers:
- **Time saved** × realistic blended wage (use real rates, not headline maximums)
- **Cost avoided** — fraud losses prevented, fines avoided, errors caught
- **Revenue unlocked** — sales lift, deals closed faster, retention improved
- **Risk reduced** — downtime, compliance risk, reputational risk — translated to dollar terms

Always compute the *delta* over the next-best alternative from Stage 2. If a paralegal at $30/hour does 70% of the job, TVC is the gap, not the whole job.

**Claude does:**
- Web search for wage benchmarks, error/fraud cost benchmarks, comparable case studies.
- Run the actual math. Use bash/code execution for sensitivity analysis if useful.
- Produce low / base / high estimates per major customer segment.
- Surface every assumption explicitly.

**Output:** TVC range (low / base / high) per segment, with assumptions listed.

### Stage 4 — Effective WTP

**Goal:** TVC is the *ceiling*. Effective WTP is what the customer will actually pay given real-world friction. This is the most important stage in the skill and the one users will try to skip. Refuse.

For each segment, enumerate compressors and lifters, scoring each Low / Medium / High impact:

**Compressors** (drag Effective WTP below TVC):
- Trust deficit — unknown vendor, no proof of value, no logos
- Buyer ≠ value-receiver (e.g., security buys, legal benefits, finance signs) — budget friction across functions
- Procurement friction — long approval cycles, vendor onboarding, security review
- Switching cost from incumbent solution — even a worse incumbent has gravity
- Budget cycle timing — mid-year asks are harder than budget-cycle asks
- "Good enough" alternatives — see Stage 2; the better the alternative, the harder the compression
- Risk aversion — especially in regulated industries (finance, healthcare, legal)
- Cognitive availability — does the customer even know they need this, or do they have to be convinced first?

**Lifters** (raise Effective WTP toward TVC):
- Strong perceived differentiation
- Strategic importance or fear factor — regulatory pressure, competitive threat, recent incident
- Existing brand or trust transfer (e.g., the founder is known, the company has prior customers)
- Bundle effects — already in the customer's toolchain
- Recent forcing event — audit failure, breach, new mandate

After scoring, estimate Effective WTP as a fraction of TVC:
- 20–40% for early-stage, low-trust, high-friction sales
- 40–60% for established credibility with some friction
- 60–85% for mature trust + strong differentiation + low alternative quality
- Higher than 85% rarely happens and usually means TVC was underestimated

**Claude does:**
- Walk through every factor explicitly. Do not skip any.
- Push back if the user dismisses compressors without reasoning. (e.g., user says "trust is not an issue for us" → ask why specifically.)
- For the user's specific product/category, suggest factors they may have missed.

**Output:** Effective WTP estimate per segment with factor analysis behind it.

### Stage 5 — WTP segmentation

**Goal:** Different customers have different Effective WTP. Identify 2–4 segments and the gap between them.

For each segment, name:
- Who they are (role, company size, urgency profile)
- Effective WTP from Stage 4
- Ability to pay (budget reality, not just willingness — these diverge for individuals and small businesses)
- Buying motion (self-serve, sales-assisted, sales-led)

**Claude does:**
- Search for typical customer segment patterns in the category.
- Pull tier structures from comparable products as analog reference.

**Output:** Segment table — name, effective WTP, ability to pay, buying motion.

### Stage 6 — Consumer-Firm Surplus Parity (the split decision)

**Goal:** Strategic decision on how aggressively to capture value.

Economic frame:
- Total Value = Consumer Surplus (WTP − Price) + Firm Surplus (Price − Cost)
- Early stage / low trust → leave more consumer surplus to accelerate adoption
- Mature / sticky / mission-critical → capture more firm surplus

Rule-of-thumb capture fractions for B2B:
- 10–20% of value created if pre-trust or cold start
- 20–30% if established with moderate differentiation
- 30%+ only if deeply defensible

These are rough — use them as sanity checks, not laws.

**Claude does:**
- Advise based on the company's stage and the differentiation map (which comes in Stage 7).
- Search for surplus-split norms in comparable companies if helpful.

**Output:** Target capture fraction with justification.

### Stage 7 — Broad-scope differentiation

**Goal:** Identify whether differentiation is broad (multiple reinforcing dimensions) or narrow (single feature). Broad differentiation defends pricing power; narrow does not — it gets copied.

Audit the product across these dimensions:
- Accuracy / reliability
- Data quality and learning over time
- Workflow integration depth
- UX
- Compliance / governance / explainability
- Ecosystem and tooling
- Trust and brand
- Switching cost depth

For each, mark: real today / aspirational / commoditized.

**Claude does:**
- Run competitive landscape across these dimensions via web search.
- Push back hard when a claimed differentiation is aspirational rather than real. "We'll have better data" is not a current differentiation. "Our model is 3% more accurate" is fragile.
- Be honest: if differentiation is narrow, say so. The pricing implications cascade.

**Output:** Differentiation map — what's real, what's aspirational, what's commoditized.

### Stage 8 — Pricing power

**Goal:** Pricing power is a function of differentiation breadth + switching costs + market structure. Assess the current state and trajectory.

Assess:
- Is the category commoditizing? Search for recent funding-round price compression, open-source models catching up, public price-cut news.
- Are switching costs structural or aspirational?
- Is there room to raise prices later, or does launch price set a hard ceiling?

**Claude does:**
- Web search for category signals — commoditization, M&A, open-source velocity, pricing trends.
- Forecast pricing power as low / medium / high with reasoning.

**Output:** Pricing power assessment with three pieces of evidence.

### Stage 9 — Porter's test (price premium > cost of differentiation)

**Goal:** Differentiation only matters economically if the price premium it commands exceeds the cost of maintaining it. Otherwise, the differentiation destroys value, however nice it sounds.

For each major differentiation from Stage 7:
- Estimate annual cost to maintain (engineering time, infra, data acquisition, compliance ops)
- Estimate price premium it justifies vs the next-best alternative

If cost > premium → cut, automate, or find a different way to monetize it.

**Claude does:**
- Estimate maintenance costs from public analogs where possible (engineering salaries, infra unit costs).
- Acknowledge openly that the user has better data on internal costs — pose this as a check, not a calculation.

**Output:** Pass / fail per differentiation, with action for any that fail.

### Stage 10 — Marginal cost + pricing model selection

**Goal:** Two things — gross-margin reality check and which pricing model to use. They are tightly linked because cost structure dictates which pricing models are viable.

**First, the cost reality check:**
- Marginal cost per unit of work — especially LLM inference for AI products
- Power-user worst case — what happens if a customer uses 10x the average?
- Gross-margin floor — at what price do unit economics invert?

**Then, pricing model selection.** Use this decision tree, not blind trend-following:

- **Seat-based** if value scales with users *and* marginal cost per user is low and predictable. Best for: collaboration tools, internal productivity AI.
- **Pure usage / consumption** if marginal cost is high and varies per use, *and* customers tolerate variable bills (typically self-serve, prosumer, mid-market). Risky for enterprise.
- **Hybrid (seat + usage credits)** if you need a predictable floor + variable upside on heavy users. Most enterprise AI is here in 2025–2026.
- **Outcome-based / agentic** if outcomes are *clearly measurable*, *cleanly attributable*, and the customer accepts the attribution. Works for: support deflection, sales lead conversion, fraud caught. Fails for: creative work, advisory work, anything where "outcome" is fuzzy.

Be skeptical of outcome-based pricing if the user is excited about it just because it's trending. The category fit matters more than the hype.

**Claude does:**
- Estimate inference cost per workload from public model pricing.
- Model power-user scenarios with bash/code execution if helpful.
- Recommend a pricing model with explicit reasoning tied to the cost structure and customer type.

**Output:** Pricing model recommendation + gross margin scenarios (base, power-user) + power-user pricing floor.

### Stage 11 — Switching costs / defensibility

**Goal:** Decide whether the initial price is a floor or a ceiling. Switching costs determine whether you can raise prices in year 2, 3, 5.

Real switching costs:
- Data accumulated in your system over time
- Workflows embedded across teams
- Integrations with the customer's stack
- Team training and muscle memory
- Compliance / audit history with your tool
- Regulatory approvals tied to your specific vendor

Aspirational switching costs (do not count):
- "They'll love it once they use it"
- "Our UX is sticky"
- General product affection

**Claude does:**
- Sort claimed switching costs into structural vs aspirational.
- Forecast pricing trajectory: realistic price increase in years 2, 3, 5.

**Output:** Defensibility verdict (low / medium / high) + 3-year pricing trajectory.

### Stage 12 — Stress test + Synthesis

**Goal:** Final scenario testing, then produce the deliverable.

**Stress tests** — run each one explicitly. If any fails, revise the relevant stage.
- **Margin floor:** What is the lowest profitable price per tier? Does the recommendation clear it on power users?
- **Power user:** Can the pricing absorb a customer who uses 10x average? What's the failure mode if not?
- **Adverse selection:** Who tries hardest to game this pricing? (Usage limits invite shaving. Free tiers invite abuse. Outcome pricing invites attribution disputes.)
- **Competitor undercut:** If a competitor prices 50% below, what's the response? Is the differentiation strong enough to hold, or is a price match forced?
- **Price increase path:** Can you raise 20% in 18 months without losing top accounts? If not, defensibility is weaker than claimed.

**Final synthesis document** — produce a markdown file at `/mnt/user-data/outputs/pricing-recommendation-[product].md` with these sections:

1. **Recommended pricing model** with reasoning
2. **Price levels per tier** — ranges, not single numbers
3. **Segment-pricing fit** — which segment each tier targets
4. **Top 3 risks** to the pricing
5. **What to validate first** — specific assumptions to test with real customers, in priority order
6. **30 / 60 / 90 day plan** — what to validate, what to launch, what to revisit
7. *(Optional)* A LinkedIn-shareable one-paragraph summary if the user wants the dual-use

Save the file and present it with `present_files`.

---

## Anti-patterns — refuse these even if the user asks

- **Outputting a single dollar number with confidence.** Output ranges with reasoning.
- **Skipping Stage 4 (Effective WTP).** Insist on this stage even under time pressure.
- **Accepting aspirational differentiation without pushback.** "Our model will be better" doesn't count.
- **Recommending outcome-based pricing for fuzzy outcomes** just because it's trending.
- **Anchoring price to competitors** instead of to value.
- **Cost-plus pricing.** Cost constrains feasibility, not pricing strategy.
- **Producing a pricing recommendation without naming the underlying assumptions.** Every number must trace to an assumption.
- **Letting the user shortcut to Stage 12** because they "already know what they want to charge." If they already know, this skill isn't doing its job — run the stages anyway and see if the conclusion holds up.

---

## What this skill deliberately does not do

These are absent on purpose:

- A WTP calculator that outputs a confident number — would create false rigor.
- Industry pricing benchmarks ("SaaS is typically $X per seat") — stale within months and substitute for thinking.
- Behavioral pricing tricks ($9.99, decoy framing) — noise relative to the structural decisions above.
- Competitor pricing scrapes as the primary anchor — anchoring to competitors is the trap value-pricing exists to break.
- Geographic / regional pricing strategy — separate decision, out of scope.

If the user asks for any of these, briefly explain why they're absent and redirect to the relevant stage.
