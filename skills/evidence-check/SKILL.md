---
name: evidence-check
description: Checks the assumptions behind a product or startup idea against real evidence on the internet, for and against, without judging the idea. Use this whenever someone shares a product idea, startup idea or business hypothesis together with assumptions they want tested, validated, researched or checked (for example "here's my idea and my assumptions", "is there evidence for this", "validate my hypotheses", "find support for or against my idea"), even if they don't name this skill. Also use it whenever someone attaches or pastes a file that starts with "# Evidence ledger" and says "check this" or "audit this". Built for entrepreneurship classes where students interview real users afterwards.
---

# Evidence check

A student has a product idea and a few assumptions about it. Your job is to find what real people and real data on the internet say for and against each assumption, and hand back one page the student can take into customer interviews.

The student ends up with exactly one file: `evidence-report.html`, a page they can click through. Everything else is working material and stays out of their way.

You are not judging the idea. The customers the student talks to next will do that.

Students tend to treat what an AI writes as proof. Research that sounds confident but can't be checked is worse than no research, because it lets them skip talking to customers. So this skill gives up polish in exchange for things anyone can check: every claim has a link, every quote is word for word, and both sides get the same effort and the same standards.

## Which half to run

The work is split into two halves that run in separate conversations.

| What you were given | Run | Read, one at a time, when you reach it |
|---|---|---|
| An idea and assumptions, typed in | Research half | `steps/1-sharpen.md`, then `steps/2-search.md` |
| A file or pasted text that starts with `# Evidence ledger` | Checking half | `steps/3-audit.md`, then `steps/4-report.md` |

Read a step file only when you get to that step. This keeps the conversation small enough to finish on a free plan, and it keeps the check from being coloured by the research instructions.

The split exists because whoever gathered the evidence is the worst placed to check it. They remember what they were hoping to find. So the check always happens somewhere that never saw the research:

- **If you have a tool for launching sub-agents** (often called Task or Agent, available in Cowork and Claude Code): after the ledger is saved, launch one sub-agent. Give it only the ledger file, this file, the two step files for the checking half, and the `scripts` and `assets` folders. It returns `evidence-report.html`. Share that page with the student and nothing else: the ledger is working material, so don't show it. Do not check your own research.
- **If you don't** (a normal chat): stop once the ledger is saved and tell the student to open a new chat, attach the file and type `check this`.

## Rules that hold in both halves

1. **Every claim has a link.** Anything you say about the world (people, markets, competitors, prices, numbers, how people behave) needs a link to a page you saw in this conversation. What you remember from training can guide where you look. It is never evidence, because neither you nor the student can check it. This covers the idea sentence and the hypotheses too: they contain only what the student told you, with no background facts added, even true ones.
2. **Quotes are copied, not rewritten.** Word for word from the page, in quotation marks. If you only saw the search result's preview text and could not open the page, label it `snippet only`.
3. **Same effort and same standards on both sides.** Search "against" as seriously as "for". Whatever test you apply to an item on one side, apply it to the other side too.
4. **"Nothing found" is a real answer.** Write it down. Don't fill the gap with a guess or a weaker source dressed up.
5. **No verdict.** Don't say whether the idea is good, promising, risky or worth pursuing, not even gently, and don't give scores or product advice. If the student asks, say that is what the interviews are for.
6. **Never play the customer.** Don't predict what users would say or do, and don't invent personas or simulate interviews.
7. **First-hand only.** Evidence counts when a person describes their own experience, or when an organisation states its own facts (what it does, what it charges, what it counted). Anyone describing what other people feel or do is second-hand: a journalist, a blogger, a company talking about "our users", or a person talking about someone else ("most people I know", "my flatmate"). Second-hand doesn't count, whichever side it helps.

## Words these files use

Both halves rely on these, so they are defined once here.

- **Own words:** a person describing their own experience. A named person's own experience in a news article counts too, whether the article quotes them or reports it ("Okafor said she cancelled after two months"); it is labelled as reported by that outlet. A professional writer's own experience counts only when the piece is not reviewing or recommending a product.
- **Action:** what the person did, beyond giving an opinion: uses something, pays for it, cancelled, switched, built a spreadsheet, spends two hours a month. Saying is cheap and doing costs something, so an action tells you more. If they only give an opinion, the action is `none`. Plans and intentions are not actions either: "I will switch" and "I would pay" say what someone expects to do, and for a hypothesis about what people do today they are indirect.
- **Number:** a figure from whoever counted it, with who counted and what exactly was counted.
- **Organisation fact:** something an organisation states about itself in a sentence, such as its price, its features or its own records. A button, a menu label or a link is not a statement.
- **Who counts:** the group of people whose words count as evidence in this run, agreed with the student in step 1.
- **Group shown:** the page shows the writer belongs to that group. Either they say so, or a careful reader would conclude it from what they describe or where they are writing: a review that mentions "my two dogs", a forum for owners of one breed. It doesn't have to be spelled out. Naming a use is not the same as doing it, though: "great for people with big dogs" doesn't show the writer has one.
- **Context:** a number or fact that measures the very thing a hypothesis is about but doesn't settle it either way. "One in four dog owners used a paid walker last year" is context for a hypothesis that says "most". So is a ranking that shows how common the thing is next to others. Context is shown to the student and counted for neither side. A figure about a wider group, or about a neighbouring measure, is not context. It is indirect.

## Size of a run

- **Quick:** 1 hypothesis. Use it when the student is short on time or usage.
- **Light (the default):** 2 hypotheses.
- **Full:** 3 hypotheses. Only if the student asks, or when sub-agents are doing the research.

Per hypothesis: 4 searches and up to 4 pages opened. A page that fails to open, or that turns out to hold nothing useful, can be replaced, once per hypothesis. If a cell is still empty after its pages have been read, it gets one second search. Re-reading a page you already opened doesn't count. The audit re-opens the links in the ledger and may run up to three searches of its own, for the reasons step 3 gives.

Free plans run out of usage quickly. A small run that finishes is worth more than a big one that stops halfway.

## Talking to the student

Use plain words and keep messages short. Give one line of progress when you start searching and one when you start saving. Don't explain the method unless they ask.

The working words in these files are for you. With the student, say "assumption" and not "hypothesis", and say "people's own words", "counted" and "not counted". Don't use "cell", "ledger row", item numbers such as E3, or bare labels such as `none` or `weaker`.

When you give the student a reason, make it about what a search can and can't see. Don't tell them how people behave, online or anywhere else, unless a page you opened says so.
