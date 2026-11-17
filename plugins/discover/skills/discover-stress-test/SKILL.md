---
name: discover-stress-test
description: This skill should be used when a student types "/discover-stress-test", or says "stress-test my assumptions", "poke holes in this", "challenge my assumptions", "what am I missing" or "pressure-test my idea". Part of the discover kit (Berkley Center for Entrepreneurship, NYU Stern). It has four critics (skeptic, outsider, first-principles, practical) read the assumptions and the checked web findings in parallel, turns their grounded points into suggested changes, asks the student three forcing questions one at a time, and stops for the student to accept or reject every change. There is no verdict and no ranking of the idea.
---

# /discover-stress-test: four critics, three questions, the student's decisions

Four critics read the student's assumptions and the checked web findings, each from a different angle. Their points become suggested changes to the assumptions. The student answers three forcing questions and then accepts or rejects each change. Nobody gives a verdict.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, and `shared/data.md` before you write `discovery.json`. The critic briefs are in `<this skill's base directory>/references/`. Read `references/change-rules.md` before step 4.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

## 1. Check the file

Follow "Before a command starts" in `rules.md`. It runs Frame first if Frame isn't done. Evidence is optional:

- `steps.evidence` is `"not_run"` (the student jumped ahead): run without it. Tell each critic that no web search has run, so every point is grounded in the student's own words (`grounded_in`: `no evidence either way`). When you save in step 5, set `steps.evidence` to `"skipped"` and `stress_test.written_before_search` to `true`. In the forcing questions, every lead-in says plainly that no web search has run yet.

Then:

- `steps.stress_test` is `"waiting"`: the critics have run. Don't run them again. Pick up at the first open part: the next unanswered forcing question (step 5), the changes still `pending` (step 6), or, when every change is decided, the unanswered "which three matter most" question (step 7).
- `steps.stress_test` is `"done"`: one line and the card pointing to `/discover-interview-plan`.

## 2. Four critics, in parallel

Tell the student one line: "Four critics are reading your assumptions and what the web showed. This takes a minute or two." Without a web search, leave out "and what the web showed".

Launch four general sub-agents in one message. Give each:

- the shared critic rules, `<this skill's base directory>/references/critic-rules.md`, and its own brief, to read first and follow exactly:
  1. `references/critic-skeptic.md` (what in the findings cuts against this)
  2. `references/critic-outsider.md` (what a newcomer wouldn't understand or believe)
  3. `references/critic-first-principles.md` (the right problem, or a solution in disguise)
  4. `references/critic-practical.md` (can the student reach these people and learn this in two weeks)
- the full path of `discovery.json`;
- its output file: `discover-work/critic-skeptic.json`, `critic-outsider.json`, `critic-first-principles.json`, `critic-practical.json`;
- the instruction to reply with the number of points only.

**No sub-agent tool:** follow the four briefs yourself, one at a time, writing each file before reading the next brief.

## 3. Check the points

Read the four files. For every point:

- `hits` must be an assumption id in the file.
- `grounded_in` must be exactly `no evidence either way`, or a link that appears in `evidence` (an item's or a product's link) or among the picked problem's counted items. If it is a link, open the item in `discovery.json` and make sure the item says what the point claims. If not, change `grounded_in` to `no evidence either way` only if the point stands on reasoning alone; otherwise drop the point.
- Drop any point that states a fact about the world not found in the evidence, gives a verdict, recommends pivoting or stopping, or plays the customer.
- A point that says something is missing must say what the report's items don't state ("none of the counted items says where the owner is"), never what a page or a person doesn't give: the items are trimmed. Reword it that way, or drop it.
- At most 3 points per critic.
- You may reword a point only to remove something the page doesn't show, such as a gender ("his clients" becomes "their clients"), or to call a set-aside item "set aside" where the point calls it supporting, keeping its content.

Note any dropped or reworded point and why in `discover-work/stress-notes.md`. Never add points of your own.

## 4. Turn points into suggested changes

Write the changes the points support, usually 2 to 5. Each change is exactly one of:

- **split** an assumption that holds two claims;
- **reword** an assumption;
- **change a rating** (importance or evidence now);
- **move one to interviews only**;
- **add** an assumption.

Each change has an id (`C1`, `C2`, ...), `assumption`, the change in one plain sentence, and `why`: which critic raised it and the point, in a few plain words. `assumption` is the id of the assumption the change edits itself (a rating, a move to interviews only, a reword in place), or `"new"` for every change that adds an assumption (a split, a narrower or reworded copy, a fresh one). Every sentence in `change` and `why` is under 25 words. In `change` and `why`, name any other assumption by a few words of its statement, never "number n" or its id: the page shows ids, the chat shows numbers, and neither reads well inside the other. Never say "the web check found none" about an assumption the web search never ran on; say "the web search hasn't looked at it". Every change starts as `"pending"`. No change about the product, the business or whether to continue. No verdict, no ranking, no summary of "what the critics agree on".

Word every change by `<this skill's base directory>/references/change-rules.md`. In short: never reword a searched assumption in place; a searchable statement stays its core claim plus at most one situation a page can show; a narrowing change says whether a page could show it; a change that adds an assumption states its kind and ratings; and a change that adds a would-claim adds or names its own same-action nearest version.

## 5. Save, then three forcing questions

Write the `stress_test` section: `critics` (all four, even one with no points), `changes` (all `pending`), `forcing: []`. Set `steps.stress_test` to `"waiting"` and `waiting_on_student` to "Answer three questions, then accept or reject each suggested change." Add a `log` entry. Rebuild the page.

Then send one short line and the first question. Ask the three questions **one per message, in this order**. Tie each one to what the page shows, in a short lead-in that names something from the counted findings (or says plainly that nothing was counted on it). Add no facts. Each lead-in is one sentence under 25 words.

1. **Wanting it, shown by doing.** "The page shows <one counted item on the `for` side where someone did something, in a few words>. What is the strongest sign that someone already wants this, from what they did, not what they said?" Lead only with a counted `for` item. Never present an `against` item as a sign someone wants this. When there is none, the lead-in says so plainly:
   - nothing on the page was counted, on any side: "Nothing on your page was counted for your assumptions."
   - items were counted, but no `for` item shows someone doing something: "None of the counted items backing your assumptions shows someone doing something about this."
2. **Today and its cost.** "On the page, people handle this today by <what counted items and current existing options show>. What does the way people handle this today cost them?" One question. Use only counted items and options whose pages are current; leave out an option the page marks as resting on an old page. When nothing counted shows it, the lead-in is "Nothing counted on your page shows how people handle this today."
3. **One person.** "The web findings talk about <who_counts, or the people in the counted items>. Who is the one person who needs this most? Their role, their situation, and what's at stake for them. A group like "students" isn't a person."

**Push once if vague.** An answer is vague when it names a group instead of a person, says what people "would" do, says "everyone" or "lots of people", or gives no example. Then ask once: "Can you make that specific? One real case: who, what they did, and when." Whatever the second answer is, move on. Never push twice. Never answer for them, and never suggest an answer.

After each answer, append to `forcing`: `question` (the question as you asked it), `answer` (their words; if you pushed, both answers: "<first> | More detail: <second>"), `pushed_once`. If an answer names another private person (a classmate, a relative), save it with a role in place of the name ("a classmate") and drop details that identify them (their town, employer or business size); say so in one line. After the third answer, set `waiting_on_student` to "Accept or reject each suggested change." Save and rebuild.

The answers are the student's words. They are not evidence, and they never change a label.

If an answer itself names something that sharpens an assumption (for example a narrower person), you may add one more change for it, with `why` saying it comes from their answer.

## 6. The stop: the student decides each change

Show the changes, numbered, in plain words:

```
The critics' points suggest these changes. Each one is your call.

1. <change, 20 words or fewer> (about: <n>, "<a few words of it>")
2. <change that adds one, 20 words or fewer> (new assumption)
   If it's wrong, it hurts <a lot | some | a little>. Evidence you have now: <none | some | good>. <A search can check it. | Interviews only.>
3. ...

Why each was suggested, and the pages behind it, is on your page.
```

One change per numbered line. `<n>` is the assumption's number; never write its id alone or its full statement here. When you shorten a change, keep the few words that name any other assumption ("takes the riskiest mark from 6, roofers would use a drone"); never write "number n" without them. For a change that adds an assumption (`assumption` is `"new"`), end the line with "(new assumption)" instead of "(about: ...)", and add the indented rating line for each assumption it would add, in the same words as at `/discover-frame`. The student accepts those ratings with the change, so they must see them here. If accepting a change would move the riskiest mark, add one line after the list: `Riskiest mark: accepting <change number> moves it from <n> ("<a few words>") to <n or the new assumption> ("<a few words>").`

The stop comes before the card. End the message with this one question, and wait:

```
Which changes do you accept? Reply accept or reject for each, for example: 1 accept, 2 reject.
```

If the reply leaves some changes undecided, ask one question about those only. If the student says "you decide", say the changes are their call, and ask again once.

## 7. Apply only accepted changes

For each change set `decision` to `accepted` or `rejected`, as the student said. Then update `assumptions` from accepted changes only, by "Applying accepted changes" in `references/change-rules.md` (reword, split, rating, interviews only, add, `source`, `confirmed_by_student`), and recompute `riskiest` by the rule in `data.md`. If a `future` assumption pointed to one moved to interviews only, tell the student in one line which searchable one it points to now.

**Riskiest re-pick.** Ask only when both are true: the accepted changes add, remove or re-rate a riskiest candidate (high importance with weak or no evidence), and more than 3 now qualify without the accepted changes saying which 3. Then first save the decisions (`stress_test.changes`) with the step still `"waiting"` and `waiting_on_student` set to "Pick the three assumptions that matter most.", rebuild, and ask one question. List only the candidates the student may pick: the ones a search can check, and interview-only ones only when fewer than 3 searchable ones qualify. Say which the web search has already looked at, and list them in number order:

```
More than 3 assumptions now hurt a lot if wrong and have little evidence. Only 3 can be marked riskiest.
1. <a few words> (already searched)
4. <a few words> (not searched yet)
9. <a few words> (not searched yet)
11. <a few words> (not searched yet)
Which three matter most?
```

The pick is the student's. Apply the accepted changes and the student's pick together.

Never change an assumption because of a rejected change, or because of a point the student didn't accept.

Set `steps.stress_test` to `"done"` and `waiting_on_student` to `""`. Add a `log` entry listing what was accepted and rejected, and the pick if there was one. Rebuild.

**Not searched yet.** If assumptions a search can check are now riskiest but not in `evidence.run_on`, leaving out any the renderer lists as checked in Find problems, tell the student in one line, naming each by number and a few words: "The web search hasn't looked at these yet: 2 (sitter they trust in time), 11 (a fee for short-notice bookings)." The page marks them "Not searched yet".

Now, with the stop answered and the page rebuilt, show the card: step name "Stress test", produced line with counts ("4 critics, 7 points, 3 questions answered. 3 changes accepted, 1 rejected. Your assumptions on the page are updated."), and "When you're ready: /discover-interview-plan". Zero counts read naturally (`card.md`): "none accepted", "No changes were suggested.", and "Your assumptions are unchanged." when none was accepted.

- **Step by step:** "Your call: nothing to decide here", or, when assumptions are riskiest but not searched yet, "Your call: optional: run /discover-evidence again to search 2 (sitter they trust in time) and 11 (short-notice fee)." Same short form as the line above.
- **Whole-path run:** the top-up will run on its own, so "Your call: nothing to decide here", and the produced line names what the web search will look at next: "Next, the web search looks at 2 (sitter they trust in time) and 11 (short-notice fee)." The last line is "Next: a short search for those, then Interview plan, starting now."; the run then does that top-up.

## Never

- No chairman, no overall verdict, no "the critics agree the idea is ...".
- Never rank the idea or the critics.
- Never accept or reject a change for the student.
- Never add facts about the world, in a question or a change.
