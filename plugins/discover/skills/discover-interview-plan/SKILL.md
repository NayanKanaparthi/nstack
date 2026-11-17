---
name: discover-interview-plan
description: This skill should be used when a student types "/discover-interview-plan", or says "plan my interviews", "write my interview questions", "who should I talk to", "help me reach out to people" or "make an interview script". Part of the discover kit (Berkley Center for Entrepreneurship, NYU Stern). It asks who the student can reach, then drafts who and where to talk to, three big questions, a guide by section based on the Berkley Center interview guide, money questions, a commitment ask, pass marks, outreach messages in two channels and a printable notes sheet. A separate checker flags future, hypothetical, leading, pitch, yes/no and two-in-one questions. The student sets every pass mark and approves the interview guide.
---

# /discover-interview-plan: who to talk to, what to ask, and what would count

Build the plan the student takes to real people. Everything here asks about what people did, never what they would do. The student sets the numbers and approves the interview guide.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, and `shared/data.md` before you write `discovery.json`. Read `<this skill's base directory>/references/interview-guide.md` before step 3. The question checker's brief is `references/question-checker.md`.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

## 1. Check the file

Follow "Before a command starts" in `rules.md`. It runs Frame first if Frame isn't done. Evidence and Stress test are optional: any still `"not_run"` become `"skipped"` when you save in step 4. Then:

- `steps.interview_plan` is `"waiting"`: the plan is drafted. Don't redraft it. Go to step 6 and pick up at the first open part: pass marks still `null`, otherwise approval.
- `steps.interview_plan` is `"done"`: one line and the special card from `card.md`.

Read what the plan builds on: the riskiest assumptions, the interview-only assumptions, `who_counts`, the counted items (their `where` and links), `evidence.language`, `evidence.products`, and the student's answers to the stress test's forcing questions. After a skipped step some of these are empty: build on what is there, and take places from the student's answer and your own place searches.

## 2. One question

```
Who can you reach, and how? For example campus groups, LinkedIn, people you meet in person, or online communities.
```

Keep the answer, in their words, in the draft (`discover-work/interview-plan-draft.json`) until step 5. Don't write it into `discovery.json` yet: a section stays as in the starting file while its step is `not_run`. If they say they can't reach anyone, don't push: draft from the places the web findings show, and say so in one line.

## 3. Draft the plan

Follow `references/interview-guide.md`. Draft all of these, in plain words:

- `talk_to`: who to talk to, one sentence under 25 words, from `who_counts`, the riskiest assumptions and the kind of person the student named in the stress test. Describe a kind of person, never a specific one: no name, town, employer, crew or business size, or relation ("roofers who quote from measurement reports", not "your uncle's four-person crew"). Place `why` lines and every outreach sentence are under 25 words too; the renderer refuses longer ones.
- `where`: places to find them. From the places where counted voices were found, the student's answer, and at most 2 searches of your own for communities or events. Places only, never individuals or their contact details. Never open a mirror, archive or scraper copy of another site; link only the original. A place's `why` repeats only what the student said or what the place's page visibly shows a reader (not its hidden description text). Otherwise it says what the place is, with no claim, and adds nothing the student didn't say ("in person", "members only").
- `big_questions`: exactly 3, each tagged to an assumption, at least one uncomfortable to ask.
- `guide`: the sections `warm-up`, `last time`, `how important`, `how costly`, `how they chose`, `wrap-up`, `commitment`. One to three questions each, every question tagged to an assumption (warm-up and wrap-up may be untagged), with 1 to 3 probes. The wrap-up always asks who else to talk to.
- `money`: three questions: current spend, who holds the budget, what they tried and stopped paying for.
- `commitment_ask`: one direct ask: a follow-up, an introduction or a pilot sign-up.
- `pass_marks`: one per riskiest assumption, counting what people did, `out_of: 10`, `mark: null`. Never on a `future` (would) assumption: a riskiest would-claim gets its pass mark on its nearest searchable assumption, listed in `stands_in_for`. Each `measure` is a short phrase, 15 words or fewer (see the guide).
- `outreach`: two messages for two different channels the student can use. Each asks for the person's advice in so many words ("I'd value your advice"; "and experience" may be added), says they are an NYU student, offers to share what they learn, and doesn't pitch. A message without the word "advice" is redrafted before saving; the renderer refuses it.
- `notes_fields`: keep the defaults.

Never write "would", "will you", "you'd", "if there was", "what if", "imagine" or "if you could" in a question. The renderer refuses every word on the fixed list in `shared/data.md` ("The renderer also refuses"), so read that list in `data.md` before drafting (never import the renderer to check it). The list is only a backstop: the separate question check (step 4) is the main guard.

Save the draft questions as a list in `discover-work/question-check-1-questions.json`: `[{"id": "b1", "where": "big", "text": "...", "tests": "A1", "tests_statement": "<that assumption's statement>"}, ...]`, with every big question, guide question, probe (with the id of its main question in `"after"`), money question and the commitment ask. Main questions carry their tag and its statement, so the checker can flag a wrong tag. Add each pass-mark measure too, with `"where": "measure"`, so the checker can flag a measure that counts words instead of actions.

## 4. Question check: a separate sub-agent

Launch one general sub-agent with:

- its brief: `<this skill's base directory>/references/question-checker.md`, to read first and follow exactly;
- the full path of `discover-work/question-check-1-questions.json`;
- its output file: `discover-work/question-check-1.json`;
- the instruction to reply with counts only.

The output has `flags` (what to rewrite), `checks` (one entry per question, saying what it takes for granted) and `sweep`. If `checks` is missing a question, or a probe's entry gives no `main_question_words` and no flag, send that round to a fresh question-check sub-agent again.

For every flagged question, write a rewrite that asks about the past or present, one thing at a time, without pointing to an answer. Replace the question in the plan. Add an entry to `question_check`: `original` (the question as first written), `problem` (the flag), `rewrite`. For a flagged measure, rewrite it to start with a past action (see the guide); measures aren't recorded in `question_check`. For a `tag` flag, change the question's `tests` to the assumption it does test (the flag's `fits`). If none fits, write a new question in its place that tests its tag, except for a question that asks a cost, time window or amount a pass mark or the kill criteria depend on: that one is always kept and re-tagged (v1.7 point 9). Tag fixes aren't recorded in `question_check`, which holds only the wording flags the page explains. Send every re-tagged or new question to the next round.

**Never rewrite a question that wasn't flagged**, probes included, between rounds. When a main question's rewrite makes one of its unflagged probes unfit, either keep the probe exactly as it is, or drop it and record `{"original": "<the probe>", "problem": "", "rewrite": "dropped: main question changed"}` in `question_check` (the page says "Dropped because its main question changed."). A probe can only be rewritten after the checker flags it.

Then send the rewritten questions, and the kept probes of every rewritten main question, to a new question-check sub-agent: round 2 reads `question-check-2-questions.json` and writes `question-check-2.json`. A rewrite flagged again has failed two checks: drop it and record `"rewrite": "dropped"` in its `question_check` entry (the page says "Dropped after two checks."). A question flagged for the first time in round 2 gets one rewrite and one more round. Use `"dropped"` only for a question that failed two checks. Every round, including checks of the student's edits later, gets the next number. Never overwrite an earlier round's files.

**No sub-agent tool:** run the question checker brief yourself as a separate pass over the saved list, reading only the list, and say in that round's output file that it ran in the same chat.

## 5. Save

Write the `interview_plan` section, including `reach` from the draft (`approved_by_student: false`, every `mark: null`). Set `steps.interview_plan` to `"waiting"` and `waiting_on_student` to "Set a number for each pass mark, then approve or edit your interview guide." Add a `log` entry. Rebuild. If the renderer refuses a question, rewrite it as in step 4, record it in `question_check`, and rebuild again.

## 6. The stop, part 1: pass marks

The stop comes before the card. Tell the student in a few lines what is ready (counts only: places, questions, messages) and that the full plan is on the page (discovery.html), in the Interview plan section. Then list the pass mark measures, numbered, each with a few words of its assumption, and end with one question:

```
Before you talk to anyone, decide what would count.

1. <measure, the short phrase>
2. <measure> (stands in for: "<a few words of the would-claim>")
3. ...

A rough guess is fine, from 1 to 10. Set it before the interviews, so you can't move it afterwards. Each line counts out of 10 people; you can change the 10 too. The full wording of each assumption is on your page.

What number out of 10 do you set for each line? Reply with one number per line, like this: 1: _, 2: _.
```

Wait. Record each number exactly as given in `mark`. `out_of` stays 10 unless the student changes it (say 8 people instead of 10); then record their number. If they ask you to suggest numbers, say the numbers are theirs, and a guess is fine. Never propose a number, not even a range. If some lines have no number, ask one question about those only. Save and rebuild.

## 7. The stop, part 2: approve the interview guide

Ask one question:

```
Last step. Read the interview guide on your page, in the Interview plan section. Reply "approved", or tell me which questions to change and how.
```

- **"Approved":** set `approved_by_student: true`.
- **Edits:** make exactly the edits they ask for. Put the edited questions through a fresh question check (step 4). If one is flagged, show the flag in one plain sentence and a rewrite, and ask one question: keep your rewrite or use theirs? A question that asks about the future or a hypothetical can't go on the page; explain that in one sentence and offer the past-behaviour version. Then ask the approve question again.

## 8. Finish

Set `steps.interview_plan` to `"done"` and `waiting_on_student` to `""`. Add a `log` entry with the marks and the approval. Rebuild.

Now, with both stops answered and the page rebuilt, end with the special card from `card.md`: step name "Interview plan", produced line with counts ("3 big questions, 12 guide questions, 2 messages, 4 pass marks set by you"), "Your call: nothing to decide here", and "When you're ready: send your first five messages now. After your interviews, run /discover-interview-sort". This is also the end of the whole-path run.

## Never

- Never ask the interviewee about the future or a hypothetical, and never pitch.
- Never set a pass mark number, or approve the interview guide, for the student.
- Never list individual people or their contact details.
- Never play the customer: no sample answers, no practice interview with you as the interviewee.
