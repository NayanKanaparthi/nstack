---
name: discover-interview-sort
description: This skill should be used when a student types "/discover-interview-sort", or says "sort my interview notes", "I finished my interviews", "add my interview notes", "pull my Wispr Flow interviews", "what did people say" or "count my interviews against my pass marks". Part of the discover kit (Berkley Center for Entrepreneurship, NYU Stern). It takes the interviews from Wispr Flow, the interviews folder or pasted text, removes names and contact details with the student's OK first, tags each fact to an assumption as something the person did, said they would do, or an opinion, records what people raised on their own only when they did, and rebuilds the page, which counts the interviews against the student's pass marks. It gives no verdict.
---

# /discover-interview-sort: from notes to facts, counted against the student's marks

Sort what real people said into facts tied to the student's assumptions. The page counts them against the pass marks the student set. Only what people did counts. Nobody gives a verdict.

**Find the shared files first.** The plugin root is two folders up from this skill's base directory: `<this skill's base directory>/../../`. The shared files are in `<plugin root>/shared/`. Read `shared/rules.md` and `shared/card.md` now, and `shared/data.md` before you write `discovery.json`. Read `<this skill's base directory>/references/sorting-rules.md` before step 3.

**If the renderer refuses the data,** fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html`. Read "The renderer also refuses" in `shared/data.md` before writing, so the run doesn't loop. Run `render_page.py` only as a command, exactly as written. Never import it or load it into other Python code: to check questions, read the list in `data.md`.

## 1. Check the file

Follow "Before a command starts" in `rules.md`. It runs Frame first if Frame isn't done: facts are always tagged to assumptions. The interview plan is optional. If it is `"not_run"`, there are no pass marks: sort and tag the facts as usual, leave out `meets_measure`, and set Evidence, Stress test and Interview plan that are still `"not_run"` to `"skipped"` when you save.

If `interview_sort` is already `"done"`, this is a new batch: keep every interview already in the file, and add only notes not sorted before. Interviews already recorded are listed in the `log` by date or number, never by file name (file names often hold names); compare dates, and ask one question if you can't tell whether a note is new.

If `interview_sort` is `"running"`, a question is open; `waiting_on_student` says which.
- About names in the notes: if the student's answer is in this chat, act on it (step 3). Otherwise check the notes again from step 2: the student may have cleaned them.
- About adding what people raised as a new assumption: the sorting is saved. Go to step 7 and ask it again.
- About connecting Wispr Flow or adding notes: start again from step 2.

## 2. Get the interviews

Look in `interviews/` in the student's folder (text, Markdown or Word `.docx` files; ask for an old `.doc` or a PDF to be saved as `.docx` or text), and at anything pasted into this chat. If notes are there, use them and don't ask. If there is nothing, ask one question:

```
How did you capture your interviews?
1. Wispr Flow
2. Notes in a file: put them in the "interviews" folder in your project
3. I'll paste them here
```

For 2 or 3, wait for the files or the text. Save pasted notes word for word to `interviews/<YYYY-MM-DD>-pasted-<n>.md` before anything else. Don't open notes from anywhere else.

**Wispr Flow.** Look for the Wispr Flow connector's tools (a meeting search and a way to read one meeting's transcript). If they aren't there, save first: set `steps.interview_sort` to `"running"` and `waiting_on_student` to "Connect Wispr Flow, or put your transcripts in the interviews folder, then type /discover-interview-sort.", add a `log` entry ("waiting for the interviews") and rebuild, so `/discover` can report it. Then say in one line: "Connect Wispr Flow in your Claude settings, under connectors, then type /discover-interview-sort again. Or export each transcript from Wispr Flow into the interviews folder." Then stop, with no card.

If they are there:
1. List the student's meetings from the date the interview plan was made (its `log` entry) to today, or the last 30 days if there is no plan. The connector gives times in UTC: use each meeting's date in the student's own time zone. Show only that date and the title, numbered, one per line. Ask one question: "Which of these were your interviews? Reply with the numbers."
2. For each one picked, read the full transcript, page by page until it ends. Never use Wispr Flow's summary, notes or action items: they are written by an AI, not said by the person.
3. Save each transcript to `interviews/<YYYY-MM-DD>-interview-<n>.md` (n counts on from the files already there), word for word as the connector gives it, one turn per line written "<speaker>: <words>". Never put a name in a file name.

Then step 3 runs on these files like any other notes. Who is who is marked there, for every transcript: only the interviewee's lines are ever quoted as evidence.

## 3. Privacy first

Follow section 1 of `references/sorting-rules.md` before reading for content: find names, emails, phone numbers, addresses and handles, and ask the student's OK to replace them with roles in cleaned copies. This is a stop. Before asking, save: set `steps.interview_sort` to `"running"` and `waiting_on_student` to "Say whether the names and contact details in your notes can be replaced with roles." Add a `log` entry ("asked about names in the notes") and rebuild, so `/discover` can report it. Then ask the one question and wait, with no card. Don't analyse anything until the notes are clean. If the student would rather clean them, stop with the card the rules give, and leave the step `"running"` with `waiting_on_student` set to "Remove the names and contact details from your notes, then type /discover-interview-sort." When no names or contact details are found, there is no question: still write the cleaned copies, with who speaks in front of every line (sorting-rules section 1), then go to step 4.

## 4. Sort

Follow `references/sorting-rules.md`, sections 2 to 5:

- one record per interview, `who` as a role only;
- facts tied to assumptions, each with `side`, `kind` (`did`, `said would`, `opinion`) and `tag`;
- quotes exactly as written in the notes, checked mechanically against the cleaned notes;
- hypotheticals and compliments never counted as support;
- if the notes show the questions the student asked: leading, future, hypothetical, yes/no, pitching and two-in-one questions recorded in that interview's `question_flags`, so the page shows them under the interview;
- a reply to a flagged question never counted, whatever the flag: it is background (`side: "context"`) with `reply_to_flag` (sorting-rules section 5);
- what a person raised on their own that the assumptions don't cover, in `new_findings`, only when the notes hold it (sorting-rules section 6). Most interviews have none.

The facts are all the student's interviews hold. Don't add context from the web findings, and don't guess what a person meant.

## 5. Save and rebuild

Add this batch to the `interviews` list in `discovery.json`, keeping `steps.interview_sort` `"running"`. Then run the quote check (sorting-rules section 4): fix or drop what it lists, and run it again until it passes with this batch's quotes counted. Only then: if any interview in this batch holds `new_findings`, set `steps.interview_sort` to `"running"` and `waiting_on_student` to "Say whether to add anything people raised on their own as a new assumption." (step 7 asks it). Otherwise set it to `"done"` and `waiting_on_student` to `""`. Add a `log` entry naming the notes sorted, by date or number (never by file name), and that names were removed (or that none were found). Rebuild the page. Fix anything the script lists; it refuses email addresses and phone numbers in interviews.

The renderer also prints what people raised without being asked: each group, the number of interviews and their numbers, and a "Line on the page" for a new problem raised in 2 or more. Repeat those counts exactly.

The renderer prints the tally for each pass mark: its measure, "So far: n of N interviews. Your mark: m of out_of people." ("interview" and "person" for one) and "Met." or "Not met yet." ("No mark set." while a mark is null), plus a "Stands in for" line where there is one. It counts interviews with something the person did that meets the measure. Repeat those words and numbers exactly. Never round, reinterpret or add to them, and never label a count with the would-claim it stands in for.

## 6. Hand it over

Tell the student, in a few short lines:

- how many interviews were sorted and how many facts came out of them;
- with no pass marks set (no interview plan yet): "No pass marks are set yet, so nothing is counted against them. /discover-interview-plan sets them, and your page will count against them." Otherwise, for each pass mark, what was counted (its measure), then exactly what the renderer printed: "So far: n of N interviews. Your mark: m of out_of people. Met." or "... Not met yet.", capitals and all. Where the mark stands in for a would-claim, add: "Stands in for: <would-claim>. This counts past actions like it, not promises.";
- if a measure counts what people said, think or feel instead of what they did, say in one line that the page counts only what people did, so that mark can't move;
- how many facts back a statement but don't match its measure, so aren't counted (they're on the page). Leave this line out when there are none;
- each reading you had to make to decide a condition (sorting-rules section 3), one line each, ending "Change it if you meant something else.";
- how many questions were flagged to ask differently next time (they are on the page under each interview), and that replies to them are background, never counted. Leave this line out when none was flagged;
- that what people said they would do, and opinions, are on the page but never counted;
- only when any note is typed notes rather than a transcript: "Some of your notes are typed, so the check can't tell your words from theirs. Check each quote on the page is something the person said.";
- only when there are new findings: "People also raised <n> thing(s) you didn't ask about." Then, for each "Line on the page" the renderer printed, word for word: "<about> came up in <n> interviews without being asked." Then: "They're on your page under "What you didn't ask about". Check each one is something the person said, not a note of your own." When any finding comes from notes that don't show the questions you asked, add: "Your notes don't show the questions, so check you didn't ask about these first." Say nothing about what they mean. With no new findings, say nothing about them.

Every count line has a natural zero form, or is left out (`card.md`). In the card, "Pass marks: none met, 3 not met yet." is fine; "0 met" is not.

Say nothing about what the counts mean for the idea. If the student asks whether the idea works, say the counts are theirs to read against the marks they set, and Session 2 is where to take them.

With no new findings, show the card now (step 8). With new findings, go to step 7 first.

## 7. The stop: add any as a new assumption?

Only when there are new findings. List them by number, one line each: what it is, its kind in plain words, and how many interviews raised it. Then ask one question and wait:

```
Do you want to test any of these as a new assumption? Reply with the numbers, or "no".
```

- **Numbers:** for each, draft one assumption by `<plugin root>/skills/discover-frame/references/assumption-rules.md` (one claim, its kind, `if_true` and `if_false` when searchable, a nearest searchable version for a would-claim), with `source: "interviews"`, the next free id, `evidence_now` `"weak"` (the interviews are some evidence) and an importance you propose. Show each in one line with its ratings and ask: "Does this match what you mean? Reply "yes" or tell me what to change." Apply changes, set `confirmed_by_student: true`, save. Then recompute `riskiest` by the rule. If that changes which assumptions are marked riskiest, show the 3 now marked and ask one question: "These are now your riskiest 3. Keep them, or tell me which to swap; ones a search can check come first." The pick is the student's. Don't search the web and don't change the interview plan; the page shows a riskiest searchable one as not searched yet, and `/discover-evidence` can search it.
- **"no", "not now", "I don't know":** nothing is added.

Then set `steps.interview_sort` to `"done"` and `waiting_on_student` to `""`, add a `log` entry with what the student chose, rebuild.

## 8. The card

The card from `card.md` for this step: step name "Interview sort", produced line with counts ("5 interviews sorted, 23 facts. Pass marks: 1 met, 2 not met yet."), plus "1 new assumption added from your interviews." when one was, "Your call: nothing to decide here", and "When you're ready: bring your page (discovery.html) to Session 2". No next command. If they hold more interviews later, they can run `/discover-interview-sort` again; say so in the produced line only if they ask.

## Never

- Never analyse notes before names and contact details are out.
- Never invent, merge or polish a quote.
- Never record a new finding to fill the section. Nothing new is the normal result.
- Never quote the interviewer, or Wispr Flow's summary, as what a person said.
- Never count `said would` or `opinion` as support.
- Never say whether the idea is validated, proven, good or bad, and never recommend what to do next with it.
- Never play the customer, or fill a gap in the notes with what someone "probably" said.
