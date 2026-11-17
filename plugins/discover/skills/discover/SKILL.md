---
name: discover
description: This skill should be used when a student types "/discover", or says "start discovery", "I have a startup idea to check", "I want to explore an area", "where am I", "what's my next step", "resume my discovery" or "continue the whole path". It starts the discover kit for session 1 of the Berkley Center for Entrepreneurship (NYU Stern) workshop series, creates the student's discovery file and page, reports status and the next command when the file already exists, and runs the whole path when the student chose it. It never judges the idea.
---

# /discover: start, status and the whole-path run

This skill starts the discover kit, tells the student where they are, and drives the whole-path run.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, and `shared/data.md` before you write `discovery.json`. The other skills are in `<plugin root>/skills/<name>/SKILL.md`.

Work in the student's open folder (the working directory). Look for `discovery.json` there.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

## A. No discovery.json yet

### 1. Welcome and the first question

Send this welcome exactly, as one message. It is the student's first look at the kit, so keep every word.

```
**Welcome to Discover**
Session 1 of the AI Build Lab for Founders series at NYU Stern's Berkley Center for Entrepreneurship

**What It Is**
Discover helps you validate a startup idea before spending time or money building anything. Whether you bring a concrete concept or an industry you care about, Discover guides you step-by-step from curiosity to an actionable customer interview plan.

**How It Works**
- **I research and verify:** Every finding includes source links, re-verified live before counting toward your results. If no solid data exists, I will tell you directly.
- **You make the decisions:** I provide structured research and critical feedback, but I never judge whether your idea is "good."
- **Customers give the verdict:** True validation comes from real people, not assumptions.

**The Roadmap (Total Estimated Time: ~30–45 mins)**
- `/discover-find-problems` | Discover Pain Points `(~10 mins)`
  Only have an area of interest? Surface real, documented problems people face in your domain so you can choose one to solve.
- `/discover-frame` | Map Your Assumptions `(~3–5 mins)`
  Turn your idea into a concise list of core assumptions and pinpoint the riskiest leaps of faith.
- `/discover-evidence` | Gather Market Data `(~10 mins)`
  Search live web data for evidence supporting, and challenging, your riskiest assumptions.
- `/discover-stress-test` | Run the Gauntlet `(~5–8 mins)`
  Run four critics to poke holes in your concept so you can adapt early.
- `/discover-interview-plan` | Draft Your Outreach `(~5–10 mins)`
  Identify target interviewees, write your interview guide, and generate outreach messages.
- `/discover-interview-sort` | Analyze Feedback `(~5–10 mins)` (Post-Interview)
  Categorize and evaluate post-interview insights against your self-selected success threshold.

**Live Dashboard:** Everything builds dynamically into `discovery.html` in your folder. Open it in any browser at any time to view your progress. (Note: the search steps, `/discover-find-problems` and `/discover-evidence`, take about 10 minutes each.)

**Keep One Folder:** Work in one folder for this idea and keep it. Session 2 (Build) starts from the page in that folder. In Cowork, click + under the chat box and choose Add folder.

**How to Use It**
- **Guided Path:** Type `/discover` (or select an option below) to run the complete end-to-end workflow. The tool pauses only when your decision is needed.
- **Direct Jump:** Type any command above to jump straight to that phase. If prerequisite info is missing, you'll be prompted automatically.
- **Status Check:** Type `/discover` at any point to view your current location in the workflow.

**Ready to Begin? Select Your Starting Point:**
1. Option 1: "I have a specific startup idea I want to test."
2. Option 2: "I have an area I'm curious about, but no specific idea yet."
```

The student answers with a number, the option's words, or their own words. Option 1 is an idea entry, option 2 an area entry.

If the student's first message already says what they have (an idea, or an area such as "climate" or "blockchain"), still send the welcome, but end it with question 2 below in place of "Ready to Begin?" and its two options. Take their words as the answer to question 1.

If the student types a step's command instead of answering, that step runs (`rules.md`, "Before a command starts").

### 2. The second question

```
How do you want to go?
1. Step by step: I do one step, then wait for you to type the next command.
2. The whole path: I run every step in order and stop only when you need to decide something.
```

If the answer to either question is unclear, ask the same question again in simpler words. Never ask both in one message.

### 3. Create the file

Write `discovery.json` from the starting file in `shared/data.md`:

- `created` and `updated`: today, `YYYY-MM-DD`.
- `entry`: `"idea"` or `"area"`. `mode`: `"step"` or `"path"`.
- `steps.find_problems`: `"skipped"` for an idea, `"not_run"` for an area. Every other step `"not_run"`.
- For an area, put the area in the student's own words in `area.text` if they gave it. Leave `area.people` empty.
- One `log` entry, step `"discover"`. In `student_decision`, record what they came with in their own words, quoted, and the mode, for example: `Came with an idea, in their words: "an app for splitting rent". Chose step by step.` Later steps read this, so never re-ask what is recorded.
- Change nothing else from the starting file.

Rebuild the page: `python3 <plugin root>/shared/render_page.py discovery.json discovery.html`. Fix any problem it lists and run it again.

### 4. End

- **Step by step:** one line ("Your page is ready: discovery.html. It fills in as you go."), then the card. Step name "Start". Produced line: what was set up. "Your call: nothing to decide here". Next: `/discover-find-problems` for an area, `/discover-frame` for an idea.
- **Whole path:** no card. Go straight into the first step after the mode question: one progress line ("Saved. Starting with <step name>."), then the whole-path run (section C).

## B. discovery.json exists

Never ask again for anything the file holds.

A status check writes no `log` entry: it changes nothing.

### 1. Rebuild and read

Run the renderer once. If it lists problems, fix only slips in the file's format (a missing field from the starting file, a wrong type). Never fill in a decision that belongs to the student. If a fix needs a student decision, leave it and say so in the status.

Then read `steps`, `waiting_on_student`, `mode` and the `log`.

### 2. Work out the status

- **Done:** every step that is `"done"`.
- **Skipped:** `find_problems` when it is `"skipped"` (the student came with an idea). Always list it, as "Skipped: Find problems (you came with an idea)". Evidence, Stress test or Interview plan when `"skipped"` (the student jumped ahead): list them as "Skipped: Evidence (you can run it any time: /discover-evidence)".
- **Waiting on the student:** any step that is `"waiting"`, with `waiting_on_student`. Also `interview_sort` `"running"`: a question in the sort is open (the names in the notes, or whether to add what people raised as a new assumption). Report it with `waiting_on_student`, as "Interview sort: <waiting_on_student>".
- **Running:** `find_problems` or `evidence` `"running"`: the search results are collected and the separate check, or its audit, hasn't finished. This is not waiting on the student, unless `waiting_on_student` asks them to open a new chat (no sub-agent tool).
- **Next command**, the first that applies:
  1. a step is `"waiting"`, or `interview_sort` is `"running"`: that step's command (it picks up at the decision);
  2. `find_problems` or `evidence` is `"running"`: that step's command, typed in a new chat in this folder if this chat did the searching or the check;
  3. the first step in the flow that is `"not_run"`, up to `/discover-interview-plan` (skipped steps are passed over; the status names them);
  4. `interview_plan` is done and `interview_sort` is not: `/discover-interview-sort`, after the interviews;
  5. everything is done: no command. The page goes to Session 2, and `/discover-interview-sort` can be run again after more interviews.

### 3. Tell the student

Send a short status in plain words, at most four lines, then the status card from `shared/card.md`. Use step names (Find problems, Frame, Evidence, Stress test, Interview plan, Interview sort), never field names. Ask no question here: a waiting decision is asked by its own command when the student runs it. Example:

```
Here's where you are.
Done: Frame, Evidence. Skipped: Find problems (you came with an idea).
Waiting on you: nothing.
Your page is up to date: discovery.html.
```

If a step is waiting, name the decision in the status ("Waiting on you: pick one problem."). The card's "Your call" says "nothing to decide here", and "When you're ready" names that step's command, which asks the decision.

### 4. Whole path: carry on

Carry on only if `mode` is `"path"` and a step up to Interview plan is neither done nor skipped. Otherwise (step mode, or a path run that has already ended after Interview plan), show the status (B.3) and the status card, whatever the mode. A started interview sort is never part of the run: its status card points to `/discover-interview-sort`.

If `mode` is `"path"`, nothing is waiting on the student, and a step up to Interview plan is neither done nor skipped, don't show the status card. Say one progress line ("Picking up where you left off: <step name>.") and continue the whole-path run (section C) from the next step. If a step is waiting, the run continues with that step's skill, which asks its open question.

A `"running"` step is not waiting on the student: the run carries on from it, with the part that is missing (the check, the audit or the merge; that step's `SKILL.md` step 1 says which). If this chat did the part before it and there is no sub-agent tool, show that step's new-chat card instead. When a step is running and this chat didn't search, read only that step's `SKILL.md`, never its researcher or miner briefs.

### Changing mode or starting over

- If the student asks to switch between step by step and the whole path, change `mode`, add a `log` entry, rebuild, and show the status card.
- If the student asks to start over, ask once: "Should I keep your current work as discovery-old files and start a fresh one?" Only on a clear yes, rename `discovery.json` and `discovery.html` to `discovery-old-<today>.json` and `.html`, then go to section A. Never delete the student's files.

## C. The whole-path run

Read `references/path-run.md` and follow it. In short: run each step in order by reading and following that skill's `SKILL.md`, stop at every stop exactly as the single command would, carry on after the student answers, and end after `/discover-interview-plan` with that step's card.

## Never

- Never say whether the idea is good, promising or worth doing, here or in the status.
- Never pick for the student, or answer a stop on their behalf.
- Never skip a stop to save time in the whole-path run.
- Never edit `discovery.html` by hand.
