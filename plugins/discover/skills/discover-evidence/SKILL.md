---
name: discover-evidence
description: This skill should be used when a student types "/discover-evidence", or says "check my assumptions against the web", "find evidence for and against", "is there evidence for this", "research my riskiest assumptions" or "check what was collected". Part of the discover kit (Berkley Center for Entrepreneurship, NYU Stern), built on the evidence check v6. It runs the riskiest searchable assumptions through a web search for and against, has a separate checker in a fresh context re-open every link and quote, and rebuilds the student's page with mechanical labels. It never says whether the idea is good.
---

# /discover-evidence: what the web says, checked separately

Find what real people and real data say for and against the student's riskiest assumptions, have it checked by a context that never saw the searching, and put the result on the page. This is the evidence check v6, steps 2 to 4, run by sub-agents.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, and `shared/data.md` before you write `discovery.json`. This skill's briefs are `<this skill's base directory>/references/researcher.md` and `references/checker.md`, and the top-up after the stress test is in `references/top-up.md` (for you, not a sub-agent); the rules every check applies are in `shared/checking-rules.md`, with its worked examples in `shared/calibration.md`, and the audit's brief is `shared/audit.md`. Hand those over, don't apply them yourself. Don't read the researcher brief yourself unless you have to run it (no sub-agent tool), and never read it in a chat that will run the check or the audit.

**The log script.** Every `log_tool.py` command below runs as `PYTHONDONTWRITEBYTECODE=1 python3 <plugin root>/shared/log_tool.py <command> --folder "<student folder>" --step evidence`, as `shared/evidence-log.md` shows (read it before step 3). Run it only as a command, never import it. Give every sub-agent its full path.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

The whole point: whoever gathered the evidence is the worst placed to check it. They remember what they hoped to find. So the check always runs somewhere that never saw the research.

## 1. Check the file

Follow "Before a command starts" in `rules.md`. It runs Frame first if Frame isn't done. If Stress test or Interview plan already ran without this step, the hand-over adds one line: "Your stress test was written before this search." (or "Your interview plan", or both). Then:

- `steps.evidence` is `"done"`:
  - if an assumption is riskiest and searchable but not in `evidence.run_on` (the stress test made it riskiest), and not checked in Find problems (step 2), run a top-up on those only: see "Top-up after the stress test" below. If a top-up log exists (`discover-work/log/topup-<n>/`) and its audited file doesn't, resume that top-up instead (`references/top-up.md`, "Resume");
  - otherwise one line and the card pointing to the next command.
- `steps.evidence` is `"running"`: a run was stopped or cut short. Pick up from the log in `discover-work/log/evidence/`, without searching again:
  - no `discover-work/evidence.json` yet: the research is over (finished or stopped). Go to step 4. Launch checkers only for assumptions whose `check-<id>.jsonl` has no done line; a checker skips items it already has verdicts for. If this conversation did the research and there is no sub-agent tool, show the new-chat card from step 3 again.
  - `evidence.json` exists but `discover-work/audit-evidence-1.json` doesn't: if this conversation ran the check, show the new-chat card from step 4 again. Otherwise go to step 4b and run only the audit.
  - Both exist: if `discover-work/evidence-audited.json` doesn't exist yet, apply the audit's corrections (step 4b); then go to step 5.

## 2. Pick what to research

`run_on`, up to 3 in total, in this order:

1. the riskiest assumptions a search can check (`riskiest: true` and `searchable: true`), in id order, leaving out any checked in Find problems (below);
2. if that gives fewer than 3: the nearest searchable version (`nearest_searchable`) of each riskiest interview-only assumption, in id order, skipping any already on the list or checked in Find problems, until there are 3;
3. if that still gives fewer than 3: the ones left out because Find problems checked them, in id order.

**Checked in Find problems.** For an area entry, an assumption whose statement is the picked problem's statement, word for word, already has checked quotes on the page. The renderer lists it after every build ("Checked in Find problems, not searched again"). A reworded or narrowed version is a new statement, searched as usual.

- If no assumption is marked riskiest (the student already has good evidence for every high-importance one), use the searchable assumptions with `high` importance, up to 3, and say so in one line.
- If there is still nothing searchable to run on, don't fake a run. Say in one line that a web search can't check any of these assumptions, and show the status card pointing to `/discover-frame`, so the student can add a searchable one.

`/discover-frame` told the student this list by the same rule. Don't ask them to confirm it.

## 3. Research: one researcher per assumption, in parallel, about 4 minutes

Tell the student one line: "Searching for and against your riskiest assumptions now. This takes about 4 minutes."

Save first, so an interruption can resume: set `steps.evidence` to `"running"` and `evidence.run_on` to the ids. Add a `log` entry. Rebuild. Then start the clock: `log_tool.py clock --phase research`.

Launch one general sub-agent per id in `run_on`, in one message. Give each:

- its brief: `<this skill's base directory>/references/researcher.md`, to read first and follow exactly, and `<plugin root>/shared/evidence-log.md`;
- the full paths of `discovery.json`, the student's folder and `log_tool.py`;
- its assumption id, its source name (the id in lower case), the other ids in `run_on` (for filing only), whether it is the first researcher (the first id is: it also runs the two extra searches), the step name `evidence`, and today's date;
- the instruction to reply with counts only.

Each researcher logs as it goes and stops when its budget is used, when the clock runs out, or when the log says there is enough. Don't read the log. Go straight to step 4.

**No sub-agent tool:** follow `references/researcher.md` yourself in this chat, for each id in turn, logging the same way. Then stop: this chat gathered the evidence, so it must not check it. Set `waiting_on_student` to "Open a new chat in this folder and type /discover-evidence, so a fresh chat can check what was collected." Rebuild. Tell the student how much was collected, counts only, with no finding described:

```
Done collecting. Nothing here has been checked yet, so don't rely on it.
- <n> searches, <n> pages opened
- <first assumption in a few words>: <n> found for, <n> against
- <second assumption in a few words>: <n> found for, <n> against
- Nothing turned up for: <plain description>
```

Write a zero as "none" ("none found for, 2 against"), and leave out the last line when every search turned something up.

Then the new-chat card (`card.md`): step name "Evidence", produced line "Collected, not checked yet. Open a new chat in this same folder, so a fresh chat can check every quote.", "Your call: nothing to decide here", "When you're ready: /discover-evidence, typed in a new chat in this same folder".

## 4. Check: one checker per assumption, in parallel, with fresh context

Run `log_tool.py ledger --run-on <ids, comma-separated>`. It writes one ledger per assumption from the log: `discover-work/evidence-ledger-<id>.md`. Then start the clock: `log_tool.py clock --phase check`.

Launch one general sub-agent per id, in one message. None may be one that searched. Give each:

- its brief: `<this skill's base directory>/references/checker.md`, to read first and follow exactly;
- the rules it checks by: `<plugin root>/shared/checking-rules.md` and its worked examples, `<plugin root>/shared/calibration.md`, and `<plugin root>/shared/evidence-log.md` (full paths);
- the full paths of its ledger, `discovery.json`, the student's folder and `log_tool.py`;
- for an area entry, also `discover-work/problems-checked.md`: an item already judged there keeps its result and signal for the same reason, unless its note says why this assumption differs;
- its assumption id (its shard name), the step name `evidence`, whether it checks the existing options (only the first id's checker does), and today's date;
- its notes file: `discover-work/evidence-checked-<id>.md`;
- the instruction to reply with counts only.

When they all reply, run `log_tool.py assemble --run-on <ids>`: it builds `discover-work/evidence.json` from the verdicts. If it says a checker saved no summary, that assumption's lines say plainly that it wasn't fully checked in time. Join the checkers' notes, in `run_on` order, into `discover-work/evidence-checked.md` with a short command. Then run `log_tool.py pairs`.

**No sub-agent tool, in a new chat that did not search:** check every assumption yourself, one after another, by `references/checker.md`, with `shared/checking-rules.md` and `shared/calibration.md`. This chat never saw the searching, so it is a fresh context. Then assemble, join the notes and run `pairs`, and stop: this chat made the judgements, so it must not audit them. Set `waiting_on_student` to "Open a new chat in this folder and type /discover-evidence, so a fresh chat can check every item was judged the same way." Rebuild. Show the new-chat card: step name "Evidence", produced line "Checked. One more fresh chat compares how every item was judged. Open a new chat in this same folder.", "Your call: nothing to decide here", "When you're ready: /discover-evidence, typed in a new chat in this same folder".

## 4b. Audit: one more fresh sub-agent

Start the clock: `log_tool.py clock --phase audit`. Launch one more general sub-agent. It must not be one that searched or checked. Give it:

- its brief: `<plugin root>/shared/audit.md`, to read first and follow exactly;
- the full paths of `shared/checking-rules.md`, `shared/calibration.md`, `discover-work/evidence-checked.md`, `discover-work/evidence.json`, `discover-work/log/evidence/pairs.json`, `discovery.json` and `log_tool.py`, and for an area entry `discover-work/problems-checked.md`;
- its output files: `discover-work/audit-evidence-1.md` and `discover-work/audit-evidence-1.json`;
- the instruction to reply with counts only.

When it replies, apply its corrections to `evidence.json` exactly as `audit.md` says under "Applying the corrections", with a Python snippet, saving `discover-work/evidence-audited.json`. **No sub-agent tool, in a new chat that neither searched nor checked:** follow `shared/audit.md` yourself, here, then apply the corrections the same way.

## 5. Save and rebuild

Merge `discover-work/evidence-audited.json` (the check with the audit's corrections applied) into `discovery.json` as the `evidence` section, with a short Python snippet (see `rules.md`), so no quote is retyped. Set `steps.evidence` to `"done"`, `waiting_on_student` to `""`, `updated` to today. Add a `log` entry ("nothing to decide"). Rebuild the page.

If the script lists problems in the evidence data, fix only the format: a missing field, a wrong type, a `language` phrase that isn't in a counted quote (drop it), a suggested link that isn't a counted item's link (drop it), a sentence of 25 words or more (split it, keeping its content), a `not_found` line of a result with unread pages that lacks "in the pages read" (add those words). Never change a quote, a result, a reason code, a side or a signal to make the script pass. If one of those looks wrong, send that part back to a fresh checker sub-agent with the script's message, and then to a fresh audit.

The script prints the label it worked out for each assumption. Those are the only labels to repeat.

## 6. Hand it over

Tell the student, in up to five short lines:

- the page is updated: open discovery.html and click each assumption to see the quotes;
- the label for each assumption, in the words the renderer printed, with a few words of the statement and how many people and pages it rests on;
- for an assumption the renderer lists as checked in Find problems, one line: "<a few words>": checked in Find problems, <its counts as printed>;
- that the page doesn't say whether the idea is good, and the people they talk to will.

Don't repeat the evidence in chat, and don't add a view on the idea or on any label. If the student asks whether the idea is good, say the page can't answer that, and the interviews can.

Then the card: step name "Evidence", produced line with the counts and labels, "Your call: optional: open the 5 suggested links on your page while you read, or trust the check.", "When you're ready: /discover-stress-test". Use the number of `suggested_checks`, singular for one ("the 1 suggested link"). With none, "Your call: nothing to decide here". A label line resting on nothing counted says "nothing was counted", never "0 people on 0 pages".

**In the whole-path run** this step has no stop, so it shows no card. Instead it shows this short hand-over, then goes on to the stress test:

```
Evidence done.
- "<a few words of assumption>": <label>
- "<a few words of assumption>": <label>
- "<a few words of assumption>": checked in Find problems, <n> people or sources on <m> pages.
The report and <n> links you can check are on your page, section "What the web says".
```

The third line is only for an assumption the renderer lists that way, with its counts as printed.

The last line has a form for each count: "The report and 1 link you can check are on your page." With no suggested links because nothing was counted: "The report is on your page. No links were suggested, because nothing was counted."

## Top-up after the stress test

When step 1 calls for a top-up, or a top-up needs resuming, read `<this skill's base directory>/references/top-up.md` and follow it. In the whole-path run it runs automatically after the stress test, before the interview plan.

## Rules this step keeps from the evidence check v6

All of these live in the briefs and `shared/checking-rules.md`, and must hold. Don't relax any of them:

- Four cells per assumption (own words and numbers, for and against), searched with mirrored wording.
- Four questions for every item (real, first-hand, on target, current), with the reason codes.
- One voice: two items by the same person or study count once.
- Even-handed check and balance check by the checker, then an audit of the check by a fresh sub-agent.
- Labels worked out by the script, never by anyone's judgement.
- A stake must be shown on the page, not suspected.
- An organisation's own count that sells the fix is background at most.

Additions in this kit (see `data.md`): item signals, 1 to 3 star reviews of existing options and job posts, option kinds, `language` phrases from counted quotes, and up to 5 `suggested_checks`.

## Never

- Never check in the conversation that searched, and never audit in the conversation that checked.
- Never quote or describe a finding before the check has run.
- Never say an assumption is "proven", "confirmed", "likely" or "risky". Use only the script's label words.
- Never edit the page by hand.
