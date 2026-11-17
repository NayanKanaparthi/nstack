# Rules for sorting interview notes

How to turn the student's notes into facts on the page. The notes are the only source. Nothing is added, guessed or smoothed.

## 1. Privacy check, before anything else

Read every note and look for:

- people's names (the interviewee, and anyone they mention by name);
- email addresses, phone numbers, street addresses;
- social media handles or profile links;
- anything else that would identify a private person (an employer plus a job title plus a town, together).

Company and product names are fine, unless they identify the person (their own small business, say). When you clean a street address, replace it with its neighbourhood or borough rather than deleting it, so a place-based assumption can still be sorted.

If you find any, don't analyse yet. Ask the student one question, naming where you found them but not repeating them. Name the notes by date or number ("the Oct 22 note", "interview 2"), never by file name: file names often hold names.

```
Your notes include names or contact details (in <the date or number of the note>). Can I replace each person with a role, like "Person 1" or "their manager", in a cleaned copy before I sort them?
```

- **Yes:** write the cleaned copies (below), replacing each name with a role and deleting contact details. Work only from the cleaned copies. Don't change the student's original files.
- **No, I'll do it myself:** stop without sorting. Show the card: step name "Interview sort", produced line "Nothing sorted yet. Remove the names and contact details from your notes first.", "Your call: nothing to decide here", "When you're ready: /discover-interview-sort".

**The originals stay.** Every note has an original in `interviews/`: the student's file (text, Markdown or Word `.docx`), a Wispr Flow transcript saved there, or notes pasted into the chat, saved there word for word first as `<YYYY-MM-DD>-pasted-<n>.md`. Never change an original. Read a Word file's text the way the quote check reads it, one paragraph per line, and write its copy from that: `PYTHONDONTWRITEBYTECODE=1 python3 <plugin root>/shared/check_interview_quotes.py --text "interviews/<file>.docx"`. A file in any other format (an old `.doc`, a PDF): ask the student to save it as `.docx` or text.

**A cleaned copy is always written, one per interview,** whether or not names were found, to `discover-work/interviews-clean/<id>.md`, named after the interview's id (`I3.md`, the id it will get in section 2). Nothing else goes in that folder except `replacements.json`. When one file holds several interviews, each gets its own copy of its own lines (`"lines"` below).

**The copy is the original with who speaks in front of every line.** Take the original line by line, make the listed changes (names, contact details), and put "Interviewer: " or "Person: " ("Person 2: " when two people speak) in front of each line. Change nothing else. For example, the original

```
Priya Shah (00:00:04): How long did the deposit take?
Dana Reyes (00:00:09): No. Seven weeks. I emailed sam@example.org every week.
```

with `"Priya Shah": "Interviewer"`, `"Dana Reyes": "Person"` and `"sam@example.org": ""` becomes

```
Interviewer: Interviewer (00:00:04): How long did the deposit take?
Person: Person (00:00:09): No. Seven weeks. I emailed  every week.
```

- **Who speaks.** "Interviewer" is the student: their questions, comments, ideas, notes to self, a title or date line. "Person" is the interviewee. In a transcript, the interviewer is the speaker asking the questions from the interview guide; if you can't tell, ask one question: "Which speaker is you in the <date> interview?" In typed notes, a line that reports what the person said or did is "Person"; a question, or the student's own comment or idea ("Me:", "Q:", "Idea:", "Note to self:", "I think ..."), is "Interviewer".
- **What the check holds you to.** A line the original starts with "Me:", "Q:", "Idea:", "Note:" or "Note to self:" (after a bullet or not) is always "Interviewer". Every line with the same speaker label ("Dana Reyes", "Speaker 2", "Her") has the same speaker. In a transcript, a line with no speaker label continues the turn above it, so it keeps that speaker (or is the interviewer's), and a line before anyone speaks is the interviewer's. A transcript has both an interviewer and a person. The check calls notes a transcript when a speaker's label comes with a time ("[00:01:02] Dana:", "Dana Reyes  0:07", a `<v Dana>` tag, "[Dana] 14:02:15"), or when two or more speakers' labels sit on at least four lines in five; anything else is typed notes.
- **Lines the check reads as labels:** "Name: text", "**Name:** text", "[00:01:02] Name: text", "Name (00:00:06): text", "[Name] text", "[Name] 14:02:15" with the words on the next line, a Zoom or Teams `<v Name>` voice tag, and a name on a line of its own with a time ("Dana Reyes  0:07", "**Dana Reyes** 0:07", "Dana Reyes - 00:00:07", or the name, then the time on the next line). A label is a speaker's (a name in capitals, "Speaker 2", "Unknown speaker", "P1", "Her", "A"), one of the student's marks, or a notes-sheet field ("Pain:", "Workaround:"); any other "Word:" ("Honestly:") is part of the words. A label or a time on a line of its own, blank lines, cue numbers and "WEBVTT" may be kept (with who speaks in front) or left out. A line may also leave out its own label, bullet and timestamp: "Person: No. Seven weeks." is fine.
- **Changes.** Record each one in `discover-work/interviews-clean/replacements.json`: `{"I3": {"original": "interviews/2026-11-14-interview-1.md", "replaced": {"Priya Shah": "Interviewer", "Dana Reyes": "Person", "sam@example.org": ""}}}`. Only these are allowed, and the check refuses any other:
  - a name turned into a role: the name as written (one to four words, each starting with a capital, particles such as de, van or da allowed, never a single common word such as No, Never or Rarely), turned into "Person", "Person 2", "Interviewer" (the student's own name) or a role naming a relation after their, the, a, an, his, her, my, our or your, with at most one word between ("their landlord", "a close friend", "the management company"). The check knows common relations (family, friends, roommates, landlords, brokers, agents, companies, employers, colleagues, teachers and the like); if it refuses one, pick a nearby word it knows;
  - a contact detail removed (an email, an @handle, a link, a phone number, a street address with its street word, an apartment number, a ZIP code: `""`), or a street address turned into its neighbourhood ("40 Bergen Street": "Brooklyn");
  - a speaker label turned into "Person:", "Person N:" or "Interviewer:" ("Sam:": "Person:"), never needed but allowed; the student's own marks ("Me:", "Q:") only into "Interviewer:";
  - a line split where a sentence ends, when one line holds two turns ("Q: how long? A: 7 weeks."): `"A:": "\nA:"`; at a name ("Dana:"), only when that label also starts another line of the note.

  If a name is written in lower case in the notes, ask the student to fix it in their own file first.
- **`lines`** (only when one file holds several interviews): `"lines": [first, last]`, the line numbers of the original that hold this interview. Two interviews never share lines, and never share a file without `lines`. Together they cover every line of the file, so nothing that prompted a reply is left out. The same conversation saved twice is one interview.
- **No contact details stay.** The check refuses a copy that still holds an email address or a phone number.

The quote check compares each copy with its original, line by line, after these changes, and refuses any other difference: a line added, dropped, moved, split or polished.

Only "Person" turns are ever quoted as what someone said. The quote check refuses the interviewer's words.

## 2. One record per interview

- `id`: `I1`, `I2`, ... continuing after any already in the file.
- `date`: as the notes give it, or `""`.
- `who`: a role and situation only ("graduate student who moved out in May"). No name, ever.

## 3. Facts

A fact is one thing the person said, tied to one assumption. For each:

- `quote`: whole sentences from one "Person" turn, copied exactly as written in the cleaned notes, typos included. Never cut a sentence: a cut can change what the person meant ("I never paid a broker fee" is not "paid a broker fee"). The check reads sentences as data.md's length rules do, with one difference: a full stop after a title or abbreviation ("Dr.", "St.", "Jan.", "Calif."), a single initial, a run of single letters ("U.S.") or a lower-case short form ("e.g."), or before a word in lower case ("on time... until") or a digit, doesn't end a sentence, but any other word with a capital does ("Yes. It took weeks." and "No. They kept it." are two sentences), and so does a word in lower case such as "no." ("I said no. They kept it."). A number after a full stop starts a sentence ("They kept most of it. $150 was for cleaning."), unless the full stop ends a title or short form ("Jan. 5", "no. 5"). A line ends one only after ".", "!" or "?", or before a bulleted line. In a transcript, the lines of one speaker's turn are read together. In typed notes, each line stands alone, unless it is indented under the line above, has no label under a speaker's labelled line ("She: No. Seven weeks." then "They also kept $200."), or carries on a long line (60 characters or more) that doesn't end in ". ! ?" and starts in lower case. In typed notes, the whole of a quotation in double quotation marks ("she said "it took forever."") is whole too. Notes are often the student's paraphrase, not the person's exact words: copy whatever the notes say, never improve it, and never put words in quotation marks that the notes don't have.
- `assumption`: the id of the assumption it speaks to. A fact that speaks to no assumption is not recorded. A reply to a flagged question follows section 5, whatever its words.
- `side`, judged against the assumption's statement only, never against a pass mark's measure:
  - `for`: it shows the statement holds for this person;
  - `against`: it shows the statement's plain opposite for this person;
  - `context`: related, but settles nothing either way.
- **Never `did` + `for` on a `future` (would) assumption.** No past action shows what someone would do. A past action that resembles a would-claim ("I pay 10% to a platform that holds the money") goes on the past-behaviour assumption it does show, usually the would-claim's nearest searchable one, or is `context` on the would-claim. The renderer refuses `did` + `for` on a `future` assumption.
- `kind`:
  - `did`: something the person did or experienced in the past or does now: paid, switched, cancelled, built a workaround, spent time, had it happen. "Last month I paid a lawyer" is `did`. A person's own count of their own recent incidents with a time window is `did`: "We get a wrong size out at least twice a week, every week since September." Vague memory is an `opinion`: "That's the only time I can think of", "it happens a lot".
  - `said would`: what they say they would, will or might do: "I'd pay for that", "I'd definitely use it", "I'll try it". Plans and promises are not actions.
  - `opinion`: views, likes, compliments, general statements: "That's a great idea", "Most people hate this", "I think it's a problem".
- `tag`: `pain` (what hurts), `workaround` (how they cope), `money` (what they spend or pay), `goal` (what they are trying to get done), `obstacle` (what stands in the way).

- `meets_measure`: on every `did` + `for` fact whose assumption has a pass mark, set `true` only when the notes show every condition the measure names (a time such as "in the past year", a place, a size such as "small"). If any one isn't in the notes, set `false`, and write in `discover-work/interview-sort-notes.md` which condition is missing. Never guess a missing condition from how the student found the person. Leave `meets_measure` out on other facts.
- **A time window counts back from the interview's date**, as the note gives it. If that date has no year, use the most recent such date that isn't after today. If the note has no date at all, count from today and say so.
- **A reading.** When a condition needs a reading to decide (whether "an afternoon" counts as "hours", whether a vague time falls inside the window), write the reading and the words it rests on in the sort notes, and say it to the student in the hand-over, one line each: "I read 'an afternoon' as hours. Change it if you meant something else."
- **A quality in a measure** ("a sitter they trusted") is met only when the note shows what the person did that shows it ("turned down the two free sitters because they'd never met them"), or gives that reason in their own words. Write your reading, with the words it rests on, in the sort notes.

Compliments and hypotheticals are never support. "Great idea, I'd buy it" is `said would` and `opinion`, whatever side it leans. Only `did` facts on the `for` side that meet the measure count toward a pass mark, and the renderer does the counting. A `did` + `for` fact that doesn't meet the measure still shows on the page, as backing the statement but not counted toward the mark.

Same standard on both sides: a `did` fact against an assumption is recorded as carefully as one for it. Don't drop facts that cut against the idea.

## 4. Check the quotes mechanically

Before saving, write the interviews into `discovery.json` and run the check, only as a command, exactly like this:

```
PYTHONDONTWRITEBYTECODE=1 python3 <plugin root>/shared/check_interview_quotes.py discovery.json
```

It checks that each cleaned copy says what its original says apart from the listed changes, and that every `quote`, in `facts` and in `new_findings`, is whole sentences inside one "Person" turn of its own interview's copy, word for word (spacing and apostrophe style aside). It writes its result to `discover-work/interview-quote-check.json`. Fix or drop every quote it lists, then run it again. The sort is saved as done only when it passes. Never write a quote from memory.

## 5. Questions to ask differently next time

Only when the notes include the questions the student asked. Look for questions that were:

- `leading`: pointed to the hoped-for answer, or took for granted something the person hadn't said (that they use a tool, that they have a crew);
- `future`: asked what the person will or would do;
- `hypothetical`: asked about an imagined situation or product;
- `yes/no`: could be answered with one word;
- `pitch`: described the student's idea, or named a solution or technology before the person did;
- `two questions`: asked two things at once.

Add each to that interview's `question_flags`: `{ "question": "<the question exactly as written in the notes>", "problem": "<one of the six>" }`. One problem per question: if it has more than one, pick the first that applies in the question checker's order: `future`, `hypothetical`, `pitch`, `leading`, `two questions`, `yes/no`. The page shows them under the interview. Also list them in `discover-work/interview-sort-notes.md` with a better past-behaviour version. When the notes don't include the questions asked, leave `question_flags` out.

**A reply to a flagged question is never counted**, for every flag type, the same way. A leading question's "Of course, who doesn't." and a future question's "Maybe, depends." are handled alike. Record the reply as a fact on the assumption the question was about:

- `side`: `context` (background), whatever it leans;
- `kind`: what the reply itself is (`did`, `said would`, `opinion`);
- `reply_to_flag`: the question's flag, exactly as in that interview's `question_flags`.

The page shows it as "Reply to a question that ...: background, never counted", and the renderer refuses any other side. If the question was about no assumption, don't record the reply. Never leave out one reply and record another: one rule for every flagged question.

## 6. What people raised on their own

Sometimes a person raises something the student's assumptions don't cover. Record it only when the notes hold it. Most interviews hold nothing like this, and then `new_findings` is left out. Never stretch a fact to fill it.

Record it only when all of these hold:

- **The person raised it.** It is in their own words in the cleaned notes: a "Person" line in a transcript. Never the interviewer's words, a summary, or the student's paraphrase of a question.
- **They raised it on their own.** Not in reply to a question that named it. An open question ("Anything else that's hard about this?") is fine; "Do you also struggle with X?" is not. When the notes don't show the questions asked, record it only when the person's own words show they brought it up ("Honestly, what bugs me more is ..."), and say in the sort notes that the question wasn't recorded.
- **No assumption covers it.** If it speaks to an assumption, it is a fact on that assumption (section 3), not a finding.

The kinds:

- `new problem`: a problem, cost or frustration the assumptions don't name ("The deposit is fine, honestly. What kills me is the broker fee.").
- `workaround`: how they cope today, when the frame doesn't name that way of coping ("We just use a shared Notes page").
- `solution idea`: something the person said they wish existed or would build ("Someone should make an app that ..."). It is their idea, recorded as theirs; it is never evidence that it would work.
- `customer group`: another group they say has the problem ("My landlord friends complain about the same thing").

For each: `quote` (exactly as in the cleaned notes, one to three sentences), `about` (what it is, 12 words or fewer, plain words, no judgement), `kind`, and `group`.

**Groups.** The same thing raised in different interviews shares a group: `N1`, `N2`, ... in the order first seen. The same thing means the same harm or idea for the same kind of people; when in doubt, give it its own group. Every finding in a group has the same `kind` and the same `about`, word for word: write the `about` once and copy it. The page counts the interviews per group; nobody types a count.

Write each finding, with the line it came from, in `discover-work/interview-sort-notes.md` too, so a reader can check it.
