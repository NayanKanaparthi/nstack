---
name: discover-frame
description: This skill should be used when a student types "/discover-frame", or says "frame my idea", "turn my idea into assumptions", "what am I assuming", "what are my riskiest assumptions" or "help me write my kill criteria". Part of the discover kit (Berkley Center for Entrepreneurship, NYU Stern). It takes a typed idea or a picked problem and drafts every part the student hasn't said with AI, each part labelled "your words", "from the checked sources" or "AI's guess, to test". It splits the draft into one-claim assumptions with if-true and if-false lines, proposes an importance and evidence map with the riskiest marked, and stops for the student to confirm or edit the draft and fill in what would make them drop it.
---

# /discover-frame: from an idea to confirmed assumptions

Turn the student's idea into assumptions that real people could prove wrong: the bets that have to be true for it to work. Get the student to confirm or edit them before any search. The test is written first because once you've seen search results it is very hard not to bend an assumption toward what you found.

A student often doesn't know who pays, or how people cope today. That's normal at this stage, and it's exactly what the search and the interviews are for. So never stop on a blank and never quiz the student: draft every part yourself, say where each part came from, and let them confirm or change it.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, and `shared/data.md` before you write `discovery.json`. Read `<this skill's base directory>/references/assumption-rules.md` before step 4.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

No searching in this step. Everything comes from what the student said, the checked sources from Find problems (area entry), and your own best guesses, each one labelled.

## 1. Check the file

Follow "Before a command starts" in `rules.md`. For an area entry, Frame needs a picked problem:

- `find_problems` is `"waiting"` (problems listed, none picked): ask the pick question first (`<plugin root>/skills/discover-find-problems/SKILL.md` step 7), then carry on here.
- `find_problems` is `"running"`: finish it first (`rules.md`, point 3).
- `find_problems` is `"not_run"`: the student jumped to Frame with no problem. Set `entry` to `"idea"` and `find_problems` to `"skipped"`, keep `area.text`, add a `log` entry ("Jumped to Frame with their own idea."), and gather the idea in step 2.

Then:

- `steps.frame` is `"waiting"`: the work is saved. Don't redo it. Go to step 6 and pick up at the first open part: confirming the draft (if any assumption has `confirmed_by_student: false`), otherwise what would make them drop it.
- `steps.frame` is `"done"`: one line and the card pointing to `/discover-evidence`.

## 2. Gather what you have

Start from what you already have. Never re-ask anything recorded.

- **Idea entry:** the idea typed with this command, or the student's words recorded in the `log` by `/discover`.
- **Area entry:** the picked problem (its `statement`, its `who` line and its counted items), and any rough idea the student gave when picking, recorded in the `log`, plus anything they said later.

If an idea entry has no idea at all, ask: "What's your idea? A sentence or two in your own words is enough." If they say they don't have one, ask: "Which area are you curious about? I'll find problems people describe there first." Then set `entry` to `"area"` and `steps.find_problems` to `"not_run"`, record the area in `area.text`, add a `log` entry ("No idea yet; switched to exploring an area."), rebuild, and run `<plugin root>/skills/discover-find-problems/SKILL.md` from its step 2. Come back here once a problem is picked.

## 3. One question, for an idea entry only

For an idea entry, ask one question, unless the student already said why:

```
What makes you believe this is a real problem? Something you saw, did or heard is enough. "Nothing yet" is a fine answer too.
```

Record their words in `idea.why_believe`. "I don't know", "no idea" and the like are recorded as `"nothing yet"`. Never ask a follow-up.

For an area entry, don't ask it. Their reason is the checked sources from Find problems; leave `why_believe` as `""` unless they said something themselves.

Ask nothing else before the draft. Who it's for, the problem, how they handle it today and who pays are drafted in step 4, not asked.

## 4. Draft the bets

Follow `references/assumption-rules.md` exactly. In short:

- **Every part is filled.** For who it's for, the problem, how they handle it today and who pays, use the first that exists: the student's words (`student`); for an area entry, the picked problem's statement, its `who` line or its counted items (`checked sources`); otherwise your best guess (`ai guess`). Record each in `idea` and its source in `idea.sources`. "I don't know" from the student is never a blank: draft that part as a guess.
- **The picked problem stays as it is.** For an area entry, the problem assumption is the picked problem's statement word for word, with source `checked sources`, unless the student reworded it (then it's their words, a new statement). Find problems already checked that exact statement, so `/discover-evidence` spends its time on the other bets. If the student's rough idea is about a different harm, keep the picked problem and say so in one line in step 6.
- `idea.sentence`: one neutral sentence from the student's words and the picked problem. No guesses in it.
- `fill_in_sentence`: every slot filled, from the same sources. A guessed part is written `[guess: <words>]`. Never `[not said yet]`.
- Split into assumptions, one claim each ("or" joins two claims), kinds `problem`, `people`, `today`, `future`. Every would/will claim is `future`, not searchable, with its own nearest searchable version, written with the formula in the rules (section 3): "would <verb> <object>" becomes "<verb> <object> today", same people. The nearest version drops amounts and the form of payment. Add "people would use it at all" as `future` when there is an idea. Rewrite "nothing good exists" as a claim about what people use today. Details from one story the student told stay in an interview-only assumption (section 4b). A searchable statement is its core claim plus at most one situation a page can show (section 4a).
- Each assumption's `source`: `student`, `checked sources` or `ai guess` (rules, section 1b).
- `who_counts`.
- `if_true`, `if_false` (the plain opposite) and `needs_number` for each searchable one.
- The map: `importance` and `evidence_now` for every assumption, then `riskiest` by the rule. An AI guess always starts at no evidence (`none`). A bet from the checked sources starts at some evidence (`weak`), unless the student told you of more of their own.
- `solution_words`.

Usually 4 to 8 assumptions in total. Don't pad, and don't cut one the idea depends on.

## 5. Save

Write the `frame` section of `discovery.json` (see `data.md`): `idea` (with `sources`), `fill_in_sentence`, `solution_words`, `who_counts`, `assumptions` (each with its `source`, all `confirmed_by_student: false`), `kill_criteria: ""`. Set `steps.frame` to `"waiting"` and `waiting_on_student` to "Check the draft of your assumptions, then fill in what would make you drop this." Add a `log` entry. Rebuild the page and fix anything the script lists.

## 6. The stop: the student confirms or edits

Show the draft in plain words. Use numbers, not ids. Label every part and every assumption with where it came from: "your words", "from the checked sources" or "AI's guess, to test". Keep it short:

```
Here's a first draft of the bets your idea rests on: what has to be true for it to work. I filled in what you haven't said yet, and marked where each part came from. Nothing here has been checked yet.

Your idea, filled in: <fill_in_sentence>
- Who it's for: <who> (<label>)
- The problem: <problem> (<label>)
- How they handle it today: <today> (<label>)
- Who pays: <who_pays> (<label>)
Whose words will count as evidence: <who_counts>

A web search can check these:
1. <statement> (<label>)
   If it's wrong, it hurts <a lot | some | a little>. Evidence you have now: <none | some | good>.<" Riskiest." if riskiest>
2. ...

Only interviews can check these:
5. <statement> (<label>)
   If it's wrong, it hurts <a lot | some | a little>. Evidence you have now: <none | some | good>.<" Riskiest." if riskiest>
   A search can check the nearest version, number <n>: <its verb and object, the same action done today>.
   <only where true:> This one comes from the idea itself.

Where you described a solution, not a problem: "<words>", "<words>"
What I reworded: <each change in a few words, or "nothing">
<only when the rough idea was about a different harm:> Your rough idea is about <their words>. I kept the problem you picked; tell me if you meant the other one.

Riskiest means it hurts a lot if wrong and has little evidence yet. An AI guess always starts with no evidence.
<only when more than 3 qualify:> Numbers <list> all qualify. Only 3 can be marked, and ones a search can check come first, so I marked <the 3>.
<when a tie between the same kind decided a mark:> I picked <n> over <m> because <one short reason>. You can swap them.
The web search will run on numbers <list>.
<only when a bet from Find problems is left out:> Number <n> was already checked in Find problems.
```

Leave out the "Where you described a solution" line when there are none. Every assumption, searchable or not, gets the same rating line: the student confirms every rating, so every rating must be shown.

When more than 3 qualify, you propose the 3; the student confirms or swaps them. Say the reason for every tie you broke between candidates of the same kind: "I picked 6 over 7 because paying depends on using. You can swap them." Use the rule in `references/assumption-rules.md` section 6 for the reason. If the student swaps, apply it and recompute nothing else.

The web search line follows the rule in `<plugin root>/skills/discover-evidence/SKILL.md` step 2: riskiest ones a search can check first, then the nearest searchable version of riskiest interview-only ones, up to 3 in total; an assumption that is the picked problem's statement word for word comes last. Name them by number.

The stop comes before the card. End the message with this one question, and wait:

```
Does this match what you think? Reply "yes", change anything in your own words, or say "I don't know" and we'll test it as it is.
```

### When the student replies

- **Changes:** apply exactly what they ask: reword, split, merge, change a rating, add, remove, swap a guess for what they know. A part or an assumption they rewrite in their own words becomes `student`. If a change would break a rule (two claims in one, a would/will claim marked searchable, evidence on a guess), say so in one sentence and show the fixed version. An assumption in `evidence.run_on` is never reworded in place (`data.md`). Recompute `riskiest`. Save and rebuild. Show only the changed lines, then ask one question: "Anything else to change, or is the list right now?"
- **"Yes", "I don't know", "you decide", "test it as it is", or the like:** that's a fine answer. The draft stays as it is, with every guess still labelled a guess. Set `confirmed_by_student: true` on every assumption, save, rebuild, and say in one line: "Kept as it is. The guesses stay marked as guesses; the search and your interviews will test them." Then go on.

### What would make them drop it

Then ask one question. Fill in the people and the riskiest bet, as something they did, in the past tense, in its own key words. Use the riskiest searchable assumption the idea depends on most; for a would-claim use its nearest searchable version, never the would-claim itself. Leave both numbers blank:

```
Last one for this step. What would make you drop this? Fill in the two numbers, or write it your own way:
"If fewer than __ of the __ <people> I talk to <the riskiest bet as a past action>, I will drop this."
```

Record what they send:

- **Only numbers** ("3 of 10", "3 and 10"): put them into the sentence you showed, in the order given, and record that sentence in `kill_criteria`. Show it back in one line.
- **Their own sentence:** record it word for word. Don't polish it or add numbers.
- **"I don't know":** ask once more, more simply: "How many of the people you talk to would need to have had this problem for you to keep going? Two numbers are enough: how many, out of how many." If they give two numbers, put them into the sentence. If they still don't want to, leave `kill_criteria` empty (the page shows "not written yet") and go on.

Never fill in a number for them.

**What their test depends on** (v1.7 point 9). If what they wrote names a cost, a time window or an amount ("in the last two months", "more than $50", "at least an hour a week"), and no assumption already asks it, add it as an interview-only assumption on the problem, in their words (kind `problem`, `searchable: false`, `source: "student"`, `confirmed_by_student: true`), so the interview guide asks it. Say so in one line: "I added one thing for the interviews to ask: <statement>."

## 7. Finish

Set `steps.frame` to `"done"` and `waiting_on_student` to `""`. Add a `log` entry with what the student decided (confirmed or kept as is, what they changed, whether they filled in what would make them drop it). Rebuild.

Now, with the stop answered and the page rebuilt, show the card: step name "Frame", produced line with counts ("6 assumptions confirmed, 3 riskiest, 2 for interviews only, 3 still AI guesses to test"; leave out a part whose count is 0), and, if they wrote it, "What would make you drop the idea is written in your words." Never say "kill criteria" to the student. "Your call: nothing to decide here", "When you're ready: /discover-evidence". In the whole-path run, use the path-run last line from `card.md`, then go on to Evidence.

## Never

- Never search. Guesses come from what you know, and every one is labelled "AI's guess, to test".
- Never present a guess as the student's words or as a checked fact, and never put a guess in `idea.sentence`.
- Never leave a part blank or ask the student a question they've already said they can't answer.
- Never fill in the numbers of what would make them drop it.
- Never rate an assumption as safe because you think it is true. A guess always has no evidence yet.
- Never call an assumption or the idea strong, weak, good or bad. Ratings describe the student's evidence and how much the idea leans on it, nothing else.
