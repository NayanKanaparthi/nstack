# discover

A Claude plugin for session 1 of the Berkley Center for Entrepreneurship (NYU Stern) workshop series "AI Build Lab for Founders".

It takes you from a vague idea, or just an area you care about, to a checked report of what the web says about your riskiest assumptions and a plan to interview real people. It does the searching and the checking. It never tells you whether your idea is good. The people you talk to give the verdict, and you make every call.

Version 2.3.0. Part of Leverage by BCE.

Designed and built by Nayan Kanaparthi, AI Graduate Assistant at the Berkley Center for Entrepreneurship, NYU Stern.

## What you need

- Claude Pro or higher.
- Cowork (Claude desktop app) with a folder open, or Claude Code in a folder. The kit uses sub-agents, web search, file writing and Python 3, which both provide.
- An empty folder for your project is best. Everything the kit writes goes there.

## Install

**Cowork:** add the `discover.plugin` file through the app's plugin settings (Customize, then Plugins, then upload a plugin file). Then open your project folder in a Cowork task. The exact menu names can differ between app versions.

**Claude Code:** start Claude Code in your project folder with `claude --plugin-dir <path to the plugin folder>`. The plugin folder is a new, empty folder you unzip the `.zip` file into. Its files sit at the top level, so never unzip it straight into your project folder. If your instructor set up a plugin marketplace for the course, install it in one step instead, with the marketplace name your instructor gives you: `/plugin install discover --marketplace <owner>/<repo>`.

Type `/discover` to start. It opens with a short welcome that explains the kit and its steps, then asks whether you have an idea or an area.

## The commands

Every step's command starts with `/discover-`, so it doesn't share a name with Claude's own commands or other common plugins' commands (changed in 2.3.0; `/discover` itself is unchanged).

| Command | What it does | Where it stops for you |
|---|---|---|
| `/discover` | Sets up your folder and page, or tells you where you are and what's next. Lets you choose step by step or the whole path. | Two questions: idea or area, and step by step or the whole path. |
| `/discover-find-problems` | Only if you came with an area. Three searches run in parallel (complaints, workarounds and spending, organisations' own numbers), then a separate check re-opens every page, and one more fresh check compares how every item was judged. You get 5 to 8 checked problems, or fewer with an honest note. | You pick one problem, or try another area. |
| `/discover-frame` | Drafts the bets your idea rests on, one claim each, with what you'd expect to find if each is true or not. Anything you haven't said yet is filled in as a marked guess ("AI's guess, to test"), so you never get stuck on a blank. Proposes how much each matters and how much evidence you have, and marks up to 3 riskiest. | You confirm or change the draft, and fill in two numbers for what would make you drop the idea. |
| `/discover-evidence` | Searches for and against your riskiest assumptions. A separate check, in a fresh context, re-opens every page and quote, and one more fresh check compares how every item was judged. The page works out each label. | Nothing to decide. Up to five links are suggested if you want to check some yourself. |
| `/discover-stress-test` | Four critics (skeptic, outsider, first-principles, practical) read your assumptions and the findings. Their points become suggested changes. You answer three forcing questions. | You accept or reject each change. |
| `/discover-interview-plan` | Who to talk to and where, three big questions, an interview guide, money questions, one ask for the end, pass marks, outreach messages for two channels, and a printable notes sheet. A separate check flags bad questions. | You set every pass mark number and approve your interview guide. |
| `/discover-interview-sort` | After your interviews: pulls them from Wispr Flow, or takes your notes; removes names and contact details (with your OK); sorts what people said into facts and counts them against your pass marks. Anything people raised on their own that you didn't ask about is shown separately, only when it's there. | Your OK to remove names, if needed, and whether to test anything people raised as a new assumption. |

Every command ends with a short card: what it produced, your call (if any), and the next command.

## The flow

```
/discover
   ├─ came with an area → /discover-find-problems → you pick a problem
   └─ came with an idea
/discover-frame → /discover-evidence → read your page → /discover-stress-test → /discover-interview-plan
   → send your first messages → interviews → /discover-interview-sort → bring your page to Session 2
```

**Step by step:** each command does its job and stops. You type the next one.

**Jump anywhere:** you can type any command at any time, even in an empty folder. If it needs something first, it asks for it. Every step after Frame needs your assumptions, so `/discover-frame` runs first if you haven't framed yet. Steps you jump past are marked "Skipped" on your page, and you can run them any time. For example, `/discover-interview-plan` straight after `/discover-frame` skips Evidence and Stress test.

**The whole path:** `/discover` runs every step in order and stops only when you need to decide something. It ends after the interview plan. If it's interrupted, type `/discover` and it picks up where it left off.

## Time

`/discover-find-problems` and `/discover-evidence` each take about 10 minutes at most: a few minutes of searching, a few of checking, and a short final comparison. Searchers stop early when they have enough. If fewer than 3 problems hold up, `/discover-find-problems` runs one more short round, about 8 minutes, looking for second sources. You can press stop at any time. Type the same command again and it carries on from what was saved, without searching again.

## Your folder

```
discovery.json   your saved work. Every command reads it and updates its own part.
discovery.html   your page. Rebuilt after every step. Open it in any browser.
discover-work/   working files: search notes, check notes. You don't need to read them.
interviews/      put your interview notes here for /discover-interview-sort.
```

Don't edit `discovery.html` by hand: it is rebuilt from your saved work every time.

## What the page shows

One page, in order:

1. **Header:** your idea in one sentence (or your area), the date, and a progress strip of the six steps.
2. **Problems found** (only if you came with an area): each problem, who has it, its signals and its quotes, ordered by how many different people or sources mention it. A note says when several of them are on one page, or about one organisation or place.
3. **Your assumptions:** the fill-in sentence, every assumption with its map position (how much it matters × evidence you have now), the riskiest marked, the ones only interviews can check, where you described a solution instead of a problem, and what would make you drop the idea.
4. **What the web says:** for each assumption checked, a label the page works out from what was counted, a for and against bar, and for each side what was found in the pages read and how many more pages seemed to hold something but weren't read. Then the quotes with links, what was not counted and why, what is still open and what wasn't found. Then the options people use today, words people use, up to five links to check yourself, and how this was checked.
5. **Stress test:** the critics' points with the assumption each one is about and what it rests on, the three questions and your answers, and each change with your decision.
6. **Interview plan:** who and where, three big questions, the guide, money questions, the ask for the end, your pass marks, the rewritten questions, the outreach messages, and a notes sheet with its own print button.
7. **What people said:** facts from each interview, and for each pass mark the count against your mark. Replies to questions that should be asked differently are shown as background, never counted. Then, only when your notes hold it, **What you didn't ask about:** things people raised on their own, as written in your notes, with how many interviews raised each, and a line for any new problem that came up in 2 or more.

A section that hasn't run yet says "Not run yet" and names the command that fills it. Nothing on the page says whether the idea is good, or whether to keep going.

## Rules the kit follows

- AI does the work; real people give the verdict.
- You make every call at every stop. The kit may propose; it never decides for you.
- Every claim about the world has a link a separate check re-opened. Quotes are word for word. Nothing is invented. "Nothing found" is a real answer.
- Same effort and the same standards for and against every assumption.
- Only first-hand evidence counts: what people did or experienced, or an organisation's own count or statement.
- The kit never plays the customer: no simulated interviews or invented answers.
- The step that gathers evidence never checks it.
- One question at a time, in plain words.
- Interview notes have names and contact details removed before analysis. The kit never collects people's contact details from the web.

## For instructors

- **The evidence log (version 2).** Searchers and checkers write each search, page, item and verdict to `discover-work/log/` as JSON Lines the moment it happens (`shared/evidence-log.md`). `shared/log_tool.py` counts the log: it keeps each step to a time budget, tells searchers when there is enough, splits the checking across parallel checkers, and lists the pairs the audit compares first. Nothing about what counts as evidence changed.
- **Labels are mechanical.** `shared/render_page.py` checks `discovery.json` and works out every evidence label and interview tally itself, using the rules of the evidence check v6. If the data breaks a rule, the page is not built and the problems are listed.
- **Checking is separate.** `/discover-find-problems` and `/discover-evidence` run their checks in a sub-agent that never saw the searching, by one rulebook (`shared/checking-rules.md`). A second fresh sub-agent then audits each check for pairs of items judged by different standards (`shared/audit.md`), and its corrections are applied before anything is merged. Without a sub-agent tool, the kit asks the student to open a new chat for the check, and another for the audit.
- **Briefs.** Each sub-agent's instructions are in the skill's `references/` folder. No plugin agents are used, so it runs in Cowork as well as Claude Code.
- **Sources.** The interview approach is based on Professor Cynthia Franklin's needs discovery materials for the Startup Lab, written in the kit's own words and credited on the page as the "Berkley Center interview guide". Ideas from *The Mom Test* (Rob Fitzpatrick) and *Talking to Humans* (Giff Constable) are written in our own words; nothing is quoted from them.
- **Files.** `shared/rules.md` (rules for every command), `shared/data.md` (the data format), `shared/card.md` (the end card), `shared/checking-rules.md` (the tests every check applies), `shared/calibration.md` (worked examples of those tests), `shared/audit.md` (the audit's brief), `shared/render_page.py` and `shared/page-template.html` (the page).
