---
name: discover-find-problems
description: This skill should be used when a student who has an area of interest but no idea yet types "/discover-find-problems", or says "find problems in this area", "what problems do people have with...", "I don't have an idea yet", "help me find a problem to work on" or "none of these fit, try another area". Part of the discover kit (Berkley Center for Entrepreneurship, NYU Stern). It searches forums, low-star reviews, job posts and organisations' own counts for problems people describe first-hand, has a separate checker re-open every link, and lists 5 to 8 checked problems for the student to pick from. It never picks for the student.
---

# /discover-find-problems: from an area to checked problems

The student has an area, not an idea. Find problems that people describe first-hand, check them in a separate context, and let the student pick one.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, `shared/data.md` before you write `discovery.json`, and `shared/evidence-log.md` before step 3. This skill's briefs are in `<this skill's base directory>/references/`. The rules every check applies are in `shared/checking-rules.md`, with worked examples in `shared/calibration.md`, and the audit's brief is `shared/audit.md`: hand them over, don't apply them yourself.

**The log script.** Every `log_tool.py` command below runs as `PYTHONDONTWRITEBYTECODE=1 python3 <plugin root>/shared/log_tool.py <command> --folder "<student folder>" --step find-problems`, as `shared/evidence-log.md` shows. Run it only as a command, never import it. Give every sub-agent its full path.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

## 1. Check the file

Follow "Before a command starts" in `rules.md`. Also:

- `entry` is `"idea"` and `steps.frame` is still `"not_run"`: the student wants to explore an area after all. Set `entry` to `"area"` and `steps.find_problems` to `"not_run"`, add a `log` entry ("Switched to exploring an area."), and carry on.
- `entry` is `"idea"` and Frame has started: say "Your later steps are built on your idea, so this step is skipped. To explore an area, start a new folder." and show the status card pointing to the next step.
- `steps.find_problems` is `"waiting"`: don't search again. Go to step 7 and ask the open question.
- `steps.find_problems` is `"running"`: a run was stopped or cut short. Pick up from the log in `discover-work/log/find-problems/`, without searching again:
  - no `shard-summary.json` yet: the search stopped early. Say one line: "Checking what was found before the stop." Go to step 5.
  - `shard-summary.json` exists but `checked-all.json` doesn't: some checks didn't finish. Go to step 5 and launch checkers only for shards whose `check-<n>.jsonl` has no done line. A checker skips items its shard already has verdicts for.
  - `checked-all.json` exists but `discover-work/problems-audited.json` doesn't: go to step 5b.
  - `problems-audited.json` exists: go to step 5c. It decides whether the extra round runs, and picks up an extra round that was cut short.
  - If this conversation did the searching or the checking and there is no sub-agent tool, show the matching new-chat card instead (step 3 or step 5).
- `steps.find_problems` is `"not_run"` but the log already holds searchers' files from an interrupted run: treat it as `"running"`.

## 2. Get the area

Use `area.text` from the file, or what the student typed with the command. If neither exists, ask one question:

```
Which area are you curious about? A few words is enough.
```

**A technology is not an area of people.** If the area names a technology or a method rather than people or a part of life (for example blockchain, AI, machine learning, computer vision, crypto, web3, AR or VR, drones, robotics, quantum, an app, a platform), ask one question, with the area in the student's own words:

```
Who would you like to help, or which part of life or work, within <the area, in their words>?
```

Record the area as they said it in `area.text` and their answer in `area.people`. Search for the people and the part of life, not the technology. If the answer still names only a technology, ask the same question once more in simpler words, with two or three example answers of a different kind ("people who rent", "small restaurant owners", "commuting").

Save `area` and add a `log` entry with the student's answer. Rebuild the page.

## 3. Search: three searchers in parallel, about 4 minutes

Tell the student one line: "Searching three ways now: complaints, workarounds and spending, and organisations' own numbers. This takes about 4 minutes."

Save first, so a stop can resume: set `steps.find_problems` to `"running"` (the `problems` list stays empty), add a `log` entry and rebuild. Then start the clock: `log_tool.py clock --phase search`.

Launch three general sub-agents in one message. Give each:

- its brief, to read first and follow exactly:
  1. `<this skill's base directory>/references/miner-complaints.md` (source name `complaints`)
  2. `<this skill's base directory>/references/miner-workarounds.md` (source name `workarounds`)
  3. `<this skill's base directory>/references/miner-counts.md` (source name `counts`)
- the shared rules for all three: `<this skill's base directory>/references/mining-rules.md`, and `<plugin root>/shared/evidence-log.md`;
- the full paths of `log_tool.py` and the student's folder, its source name, the area (`area.text`) and the people (`area.people`) word for word, and today's date;
- the instruction to reply with counts only.

Each searcher logs as it goes and stops when its budget is used, when the clock runs out, or when the log says there is enough. Don't read the log. You are about to hand it to the checkers, and you should not form a view first.

**No sub-agent tool:** follow the three briefs yourself, one after another, in this chat, logging the same way. Then stop. This chat gathered the evidence, so it must not check it. Set `waiting_on_student` to "Open a new chat in this folder and type /discover-find-problems, so a fresh chat can check what was found." Rebuild. Show the new-chat card (`card.md`): step name "Find problems", produced line with the counts and "collected, not checked yet. Open a new chat in this same folder for the check.", "Your call: nothing to decide here", "When you're ready: /discover-find-problems, typed in a new chat in this same folder".

## 4. When the searchers reply

Go on when all three have replied, or when the student stopped them. Don't relaunch a searcher that failed: its time has run, and the log keeps what it found. If one found nothing at all, say so in `problems_note` later.

## 5. Check: up to four checkers in parallel, with fresh context

Run `log_tool.py shard`. It splits the candidates that can still reach the bar into 1 to 4 shards, and prints which candidates can't (they had fewer than 2 `for` items, or all on one page). Then start the clock: `log_tool.py clock --phase check`.

Launch one general sub-agent per shard, in one message. None may be one that searched. Give each:

- its brief: `<this skill's base directory>/references/checker.md`, to read first and follow exactly;
- the rules it checks by: `<plugin root>/shared/checking-rules.md` and its worked examples, `<plugin root>/shared/calibration.md`, and `<plugin root>/shared/evidence-log.md` (full paths);
- the full paths of `log_tool.py` and the student's folder, its shard number and file (`discover-work/log/find-problems/shard-<n>.md`), the area and people, and today's date;
- its notes file: `discover-work/problems-checked-<n>.md`;
- the instruction to reply with counts only.

When they all reply, run `log_tool.py merge`. Then join the checkers' notes into one file, in shard order, with a short command (`cat discover-work/problems-checked-[0-9]*.md > discover-work/problems-checked.md`): the `/discover-evidence` check reads it later. Then run `log_tool.py pairs`.

**No sub-agent tool, in a new chat that did not search:** check every shard yourself, one after another, by `references/checker.md`, with `shared/checking-rules.md` and `shared/calibration.md`. Then merge, join the notes and run `pairs`, and stop: this chat made the judgements, so it must not build the list. Set `waiting_on_student` to "Open a new chat in this folder and type /discover-find-problems, so a fresh chat can check every item was judged the same way." Rebuild. Show the new-chat card: step name "Find problems", produced line "Checked. One more fresh chat compares how every item was judged. Open a new chat in this same folder.", "Your call: nothing to decide here", "When you're ready: /discover-find-problems, typed in a new chat in this same folder".

## 5b. Build: the audit and the list, one more fresh sub-agent

Start the clock: `log_tool.py clock --phase build`. Launch one more general sub-agent. It must not be one that searched or checked. Give it:

- its brief: `<this skill's base directory>/references/build.md`, to read first and follow exactly, and the audit's duties in `<plugin root>/shared/audit.md`;
- `<plugin root>/shared/checking-rules.md`, `<plugin root>/shared/calibration.md`, `<plugin root>/shared/evidence-log.md` and `log_tool.py` (full paths);
- `discover-work/log/find-problems/checked-all.json`, `pairs.json`, `discover-work/problems-checked.md`, the area and people, and today's date;
- its output files: `discover-work/audit-find-problems-1.md`, `discover-work/audit-find-problems-1.json` and `discover-work/problems-audited.json`;
- the instruction to reply with counts only.

It audits first, applies its corrections with `log_tool.py apply` (the find-problems form of "Applying the corrections" in `audit.md`), then builds the list into `problems-audited.json`. Then go to step 5c.

**No sub-agent tool, in a new chat that neither searched nor checked:** follow `references/build.md` yourself, here.

## 5c. A thin list: one more round, once

Read `problems-audited.json`. With 3 or more problems, or with no sub-agent tool, go to step 6. (With no sub-agent tool, the extra round would need three more new chats, so it is skipped: the builder's `problems_note` already says how many held up.)

With fewer than 3 problems, the student would get almost nothing to pick from. Read `<this skill's base directory>/references/extra-round.md` (for you, not a sub-agent) and follow it: `log_tool.py thin` lists the candidates that sit on one page, up to 2 searchers look for a second page for them (`clock --phase extra-search`, about 3 minutes, brief `references/second-pages.md`), fresh checkers check only the new items (`shard --extra`), and a fresh builder audits those and rebuilds the list with `"extra_round": true`. It also says how to pick up a round that was cut short. The round runs once. Then go to step 6, whatever the count.

## 6. Save and show the problems

Merge `discover-work/problems-audited.json` into `discovery.json` with a short Python snippet (see `rules.md`): copy its `problems` list and, if present, its `problems_note`. Set `steps.find_problems` to `"waiting"` and `waiting_on_student` to "Pick one problem to work on, or say none fit." Add a `log` entry. Rebuild the page.

If the renderer lists problems with the problems data, fix them by the rules, never by changing a quote or a result: drop a problem that has fewer than 2 counted items on 2 different pages, reorder the list, renumber `P1`, `P2`, ... in order, add an honest `problems_note`, split any sentence of 25 words or more (keeping its content). Then rebuild again.

Show the list in chat, one line per problem, in the page's order, with no judgement words:

```
Here's what people describe, ordered by how many different people or sources mention each one.

1. <statement>
   Who: <who> · <n> people or sources on <m> pages
   <only when the page notes it:> <k> of these are on one page. | <k> of these are about one <what>.
   <only when who names the organisations, not the people the student named:> About the <organisations>, not the <people> themselves.
2. ...

<problems_note, if any, in plain words>
The quotes and links for each are on your page: discovery.html.
```

Spell out an organisation's short name the first time it appears in chat ("IPSE, a UK association for the self-employed"). The renderer prints each problem's counts, and the "on one page" and "about one" notes. Repeat them exactly, singular for one ("1 person or source on 1 page").

No card yet. Go to step 7 and ask the pick question.

## 7. The stop: the student picks

The stop comes before the card. End the message with this one question and wait:

```
Which problem do you want to work on? Reply with its number, or say none fit. You can add a rough idea in your own words too.
```

If no problem survived, say so plainly and ask instead: "Which other area would you like to try?"

When the student answers:

- **They pick a number:** set `picked: true` on that problem only. Set `find_problems` to `"done"` and `waiting_on_student` to `""`. Add a `log` entry with the pick, and their rough idea in their own words if they gave one, quoted. Rebuild. Then show the card: step name "Find problems", produced line with the counts and "You picked: <statement>", "Your call: nothing to decide here", "When you're ready: /discover-frame" (in the whole-path run, the path-run last line from `card.md`).
- **They say none fit:** ask one question: "Which other area would you like to try?" Then go back to step 2 with the new area. The new run replaces the problems list. Add a `log` entry for the switch. Before the new search, move the earlier run's working files (the `discover-work/log/find-problems/` folder, every `problems-checked*.md` file, `problems-audited.json` and every `audit-find-problems-*` file) into `discover-work/area-<n>/` (n = 1, 2, ...), so the new run starts clean.
- **They ask you to choose, or ask which is best:** don't. Say the order only shows how many people mention each one, not which is better, and that the pick is theirs. Ask the pick question again.
- **They ask for more detail on one:** point them to that problem's quotes on the page. Don't add views on it.

## Never

- Never pad the list. Fewer than 5 is fine with an honest note. The extra round (step 5c) looks for second pages for real candidates; it never adds new ones.
- Never swap the people the student named for the organisations they work in. A problem about the organisations says so in its `who`.
- Never describe a problem as big, promising, underserved or an opportunity.
- Never show quotes in chat before the check has run.
- Never check in the chat that searched, and never audit in the chat that checked.
- Never collect people's contact details from the web.
