# discovery.json: the data format

This file is the single source of truth for every field in `discovery.json`. `render_page.py` checks the file against these rules every time it builds the page. If it finds a problem it writes nothing, lists every problem and exits with an error. Fix the data and run it again. Never edit or weaken `render_page.py` or `page-template.html` to get past a problem. Before writing any section, read "The renderer also refuses" at the end of this file: it lists the checks that go beyond the field shapes, so a run doesn't loop.

Every key below is required unless marked optional. Unknown keys are rejected, at the top level and inside every section. Text fields are strings (use `""` for empty), lists are lists (use `[]` for empty), true/false fields are JSON `true`/`false`, whole numbers are numbers, not strings.

## Who writes what

| Section | Written by |
|---|---|
| `kit_version`, `created`, `entry`, `mode` | `/discover` (once, when it creates the file) |
| `area`, `problems`, `problems_note` | `/discover-find-problems` (`/discover` may put the student's area in `area.text`) |
| `idea`, `fill_in_sentence`, `solution_words`, `who_counts`, `assumptions`, `kill_criteria` | `/discover-frame` |
| `evidence` | `/discover-evidence` |
| `stress_test`, plus accepted changes to `assumptions` | `/discover-stress-test` |
| `interview_plan` | `/discover-interview-plan` |
| `interviews`, plus an assumption the student asks to add from what people raised (`source: "interviews"`) | `/discover-interview-sort` |
| `steps`, `waiting_on_student`, `log`, `updated` | every command, for its own step |

## The starting file

`/discover` writes exactly this, with today's date, the student's `entry` and `mode`, and `find_problems` set to `"skipped"` when `entry` is `"idea"` (leave it `"not_run"` for `"area"`). It adds one `log` entry.

```json
{
  "kit_version": "2.3.0",
  "created": "YYYY-MM-DD",
  "updated": "YYYY-MM-DD",
  "entry": "idea",
  "mode": "step",
  "steps": {
    "find_problems": "skipped",
    "frame": "not_run",
    "evidence": "not_run",
    "stress_test": "not_run",
    "interview_plan": "not_run",
    "interview_sort": "not_run"
  },
  "waiting_on_student": "",
  "area": { "text": "", "people": "" },
  "problems": [],
  "idea": { "sentence": "", "who": "", "problem": "", "today": "", "who_pays": "", "why_believe": "", "from_problem": "" },
  "fill_in_sentence": "[who] struggles with [problem] when [situation], handles it today by [workaround], and would pay [amount or way] for a better option",
  "solution_words": [],
  "who_counts": "",
  "assumptions": [],
  "kill_criteria": "",
  "evidence": {
    "run_on": [],
    "results": [],
    "products": [],
    "language": [],
    "unread_pages": { "count": 0, "wouldnt_open": [] },
    "checked": { "searches": 0, "pages_read": 0 },
    "suggested_checks": [],
    "checked_in_fresh_context": false
  },
  "stress_test": { "critics": [], "forcing": [], "changes": [] },
  "interview_plan": {
    "talk_to": "",
    "reach": "",
    "where": [],
    "big_questions": [],
    "guide": [],
    "money": [],
    "commitment_ask": "",
    "pass_marks": [],
    "question_check": [],
    "outreach": [],
    "notes_fields": ["pain", "workaround", "money", "goal", "obstacle", "people mentioned", "follow-up"],
    "approved_by_student": false
  },
  "interviews": [],
  "log": [
    { "date": "YYYY-MM-DD", "step": "discover", "student_decision": "Came with an idea, in their words: \"...\". Chose step by step." }
  ]
}
```

## Top level

- `kit_version`: `"2.3.0"`, the kit that last wrote the file. The renderer accepts any version written as three numbers (`2.1.1`), so a file started with an earlier kit still builds; write `"2.3.0"` whenever you write the file.
- `created`, `updated`: dates written `YYYY-MM-DD`. `updated` is today whenever you write the file.
- `entry`: `"idea"` or `"area"`.
- `mode`: `"step"` (step by step) or `"path"` (whole-path run).
- `waiting_on_student`: one plain sentence naming the open decision, for example `"Pick one problem to work on."`. It must be filled while any step is `"waiting"` and while `interview_sort` is `"running"` (the student owes an answer about names in the notes), and empty when no step is waiting. While `find_problems` or `evidence` is `"running"` it may be filled (for example when the student has to open a new chat for the check) or empty.
- `problems_note` (optional): an honest note when fewer than 5 problems survived the check.

## steps

| Key | Allowed values |
|---|---|
| `find_problems` | `not_run`, `running`, `waiting`, `done`, `skipped` |
| `frame` | `not_run`, `waiting`, `done` |
| `evidence` | `not_run`, `running`, `done`, `skipped` |
| `stress_test` | `not_run`, `waiting`, `done`, `skipped` |
| `interview_plan` | `not_run`, `waiting`, `done`, `skipped` |
| `interview_sort` | `not_run`, `running`, `done` |

- `waiting`: the step's work is saved and it waits on a stop (a student decision).
- `running` (`find_problems` and `evidence`): the search results are saved in `discover-work/` and the separate check hasn't run yet. The step's section stays empty until the check has run.
- `running` (`interview_sort`): a question in the sort is open, and `waiting_on_student` names it. Either the privacy question about names and contact details in the notes (the student hasn't answered, or chose to clean the notes themselves; interviews from an earlier batch stay in `interviews`, none from this batch are added yet), or, after this batch is saved, whether to add anything people raised on their own as a new assumption. The page shows the section as "Your turn".
- `skipped` (`find_problems`): only when `entry` is `"idea"`. With `"area"` it is never skipped.
- `skipped` (`evidence`, `stress_test`, `interview_plan`): a later command ran without this step, because the student jumped ahead. It is allowed only while a later step has started. A skipped step can be run any time later with its command; it then becomes `running`, `waiting` or `done` as usual. `frame` and `interview_sort` are never skipped.
- What each step needs (the page checks these, not a strict order):
  - `frame` may leave `not_run` only when `find_problems` is `done` (a picked problem) or `skipped` (an idea).
  - `evidence`, `stress_test`, `interview_plan` and `interview_sort` may leave `not_run` (other than to `skipped`) only when `frame` is `done`.
  - Among those four, a step left `not_run` while a later one has started is refused: mark it `skipped`.
- While a step is `not_run` or `skipped`, its section stays exactly as in the starting file.

## area and problems (`/discover-find-problems`)

- `area.text`: the area as the student said it, for example `"blockchain"`.
- `area.people`: the student's answer when asked who they'd like to help, or which part of life or work (asked when the area names a technology). Empty when not asked.
- `problems`: 0 to 8 problems, in order: most independent voices first, then most pages. Ids `P1`, `P2`, ... in that order.

Each problem:

```json
{ "id": "P1", "statement": "plain sentence", "who": "who has it, as the pages show",
  "signals": ["complaint", "time spent"], "items": [ <item>, <item> ], "picked": false }
```

- `items`: only items whose `result` is `"counts"`. At least 2 items with side `"for"`, from at least 2 different pages. One page: two links that differ only after `#` or `?`, in letter case, or by a trailing `/` are one page (the evidence check v6 rule).
- `signals`: the signals its counted `for` items show, never `"none"`. Every signal listed must appear on at least one of its items. `[]` is allowed only when every counted `for` item's signal is `none`; the page then says "No signal beyond the statement itself". Never stretch an item's signal to fill the list.
- `picked`: `true` on the one problem the student picked. At most one. Exactly one once `find_problems` is `done`.
- `about_one` (optional): `{ "voices": ["Sample renter 1", "Sample reviewer 2"], "what": "property management company" }`, set by the find-problems checker when 2 or more of the problem's counted `for` voices are about one organisation or one place, on any pages. `voices` lists those voices, each exactly as an item's `voice` (letter case and spaces at the ends ignored), at least 2, none twice, and each the voice of a counted `for` item on this problem. `what` names the kind of organisation or place, and may add its name. The page shows "<number of voices> of these are about one <what>." After an audit drops an item, drop its voice from the list, and drop `about_one` if fewer than 2 remain.
- **On one page (worked out by the page, not written in the data).** When 2 or more of a problem's counted `for` voices sit on one page, the page adds "<n> of these are on one page." Nobody writes this; the script counts it.
- With fewer than 5 problems, `problems_note` must say so honestly. Never pad.

## Frame (`/discover-frame`)

`idea`: `sentence` (one neutral sentence from the student's words and, for an area entry, the picked problem; no guesses, no pitch words), `who`, `problem`, `today`, `who_pays` (each drafted: the student's words, the checked sources, or the AI's guess), `why_believe` (the student's own words, `"nothing yet"` if they said so, or `""` for an area entry that wasn't asked), `from_problem` (the picked problem's id when entry is area, otherwise `""`), and `sources` (optional).

`idea.sources` (optional; Frame always writes it from version 2.1): where each drafted part came from, `{ "who": "student", "problem": "checked sources", "today": "ai guess", "who_pays": "ai guess" }`. Each value is `student` (the student said it), `checked sources` (the picked problem or its counted items; area entry only) or `ai guess` (the AI's best guess, to test). The page shows "Your words", "From the checked sources" or "AI's guess, to test" next to each part. A part with a source must not be empty.

`fill_in_sentence`: the template `[who] struggles with [problem] when [situation], handles it today by [workaround], and would pay [amount or way] for a better option`, every slot filled. A part that is the AI's guess is written `[guess: <words>]`, so the page can say which parts nobody has checked. Never leave a slot as `[not said yet]`.

`solution_words`: short phrases where the student described a solution instead of a problem, copied from what they said.

`who_counts`: one sentence naming whose words count as evidence (the v6 "who counts" rule, in the discover-frame skill's references).

`kill_criteria`: the student's own words for what would make them drop the idea, or `""`.

`assumptions`: each one:

```json
{ "id": "A1", "statement": "one claim", "kind": "problem", "searchable": true,
  "importance": "high", "evidence_now": "none", "riskiest": true,
  "if_true": "what we'd expect to find if true", "if_false": "the plain opposite",
  "needs_number": false, "nearest_searchable": "", "source": "ai guess",
  "confirmed_by_student": false }
```

- `source` (optional; Frame always writes it from version 2.1): where the claim came from: `student`, `checked sources` (area entry only), `ai guess`, or `interviews` (added at `/discover-interview-sort` from something people raised on their own; its evidence now is `weak` or `none`). An `ai guess` always has `evidence_now: "none"`: nobody has evidence for a guess yet.
- **Checked in Find problems (worked out by the page, not written in the data).** For an area entry, an assumption whose `statement` is the picked problem's `statement` (ignoring letter case, spaces and a final full stop) was already checked in Find problems. The page shows the problem's counts under it, and `/discover-evidence` researches it only when fewer than 3 other assumptions qualify. When it isn't researched, the page never lists it as "not searched yet". The renderer prints these lines after building.

- `id`: `A1`, `A2`, ... unique. Never reuse an id for a different statement.
- An assumption listed in `evidence.run_on` is never reworded in place. A reworded version is added as a new assumption with the next free id, so the web findings always show under the words they were gathered for.
- `kind`: `problem` (the problem exists and costs something), `people` (who has it, how many), `today` (what they do about it now and what it costs), `future` (they would want, use, pay for or switch to something).
- `searchable`: `false` for every `future` one, and for any other that only interviews can answer.
- `nearest_searchable`: for a `future` assumption, the id of the searchable assumption that is its nearest searchable version (required). Empty for searchable ones. Optional for other non-searchable ones.
- `if_true`, `if_false`: required for searchable ones. `if_false` is the plain opposite, not a neighbouring claim.
- `needs_number`: `true` when the statement is about how many or how often ("most", "often", "a lot").
- `importance`: `high`, `medium`, `low` (how much it hurts the idea if this is wrong).
- `evidence_now`: `strong`, `weak`, `none` (what the student already has).
- `riskiest`: an assumption with `high` importance and `weak` or `none` evidence is a candidate. If there are 3 candidates or fewer, every candidate is riskiest. If there are more, exactly 3 are riskiest, searchable ones first. Nothing else is riskiest.
- `confirmed_by_student`: `true` only after the student confirmed or changed it. All must be `true` before `frame` is `done`.

## evidence (`/discover-evidence`)

```json
{
  "run_on": ["A1", "A2"],
  "results": [ { "assumption": "A1", "still_open": "", "not_found": [""], "unread": {"for": 0, "against": 0}, "items": [ <item> ] } ],
  "products": [ { "name": "", "link": "https://", "fact": "", "kind": "competitor" } ],
  "language": ["exact short phrase"],
  "unread_pages": { "count": 0, "wouldnt_open": [ {"site": "", "link": "https://"} ] },
  "checked": { "searches": 0, "pages_read": 0 },
  "suggested_checks": ["https://"],
  "checked_in_fresh_context": true
}
```

- `run_on`: the assumption ids the research ran on. One run covers at most 3. A top-up after the stress test (when an assumption a search can check became riskiest without being searched) appends those ids, so `run_on` may then hold up to 6; every id after the third must be riskiest and searchable.
- `results`: one per id in `run_on` once `evidence` is `done`; empty while it is `running`. Every item from the check goes in: counted, set aside and removed.
- `still_open`: one plain sentence on what is still missing. `not_found`: one sentence per thing the search looked for and didn't find. Never call something "not found" if it was found and set aside.
- `unread`: per side, how many found-but-unread pages (over the page limit, blocked or refused) seemed to hold own-words items or counts for that side of this assumption, from the ledger's "Not opened" list. Each number is at most `unread_pages.count`. The page shows it on each side next to what was found ("2 more pages seemed to back it up, but weren't read."). Optional `unclear`: unread pages whose side wasn't clear from their search result, counted in neither side, so `unclear` plus the larger of `for` and `against` is at most `unread_pages.count`. The page then adds "<n> pages found and not read; which side they lean wasn't clear.", and while `unclear` is above 0 it never says no unread page leaned a side.
- **Gaps are honest about unread pages.** When either side's `unread`, or `unclear`, is above 0, every `not_found` line of that result says "in the pages read": "No count of parents paying booking fees turned up in the pages read." The renderer can't tell which side a line is about, so it asks this of every line of that result. It is true of every line.
- `products`: at most 4. `kind`: `competitor`, `workaround`, `general AI assistant`, `person or agency`, `do nothing`. The fact is one its own page states. Use `general AI assistant` or `do nothing` only when a page shows people doing it.
- `language`: short phrases (12 words or fewer) people use for the problem, each copied exactly, in whole words, from an `own words` quote counted on the `for` or `against` side. Never from background, a number or an organisation fact, and never words about a vendor or product. The renderer checks this.
- `unread_pages`: total found-but-unread pages, and up to 3 that wouldn't open.
- `checked`: research and check together. `pages_read` counts every time a page was opened (the same page opened by the research and again by the check counts twice), so the page shows it as "pages opened".
- `suggested_checks`: up to 5 links, each the link of a counted item.
- `checked_in_fresh_context`: `true` only when a sub-agent or a new chat that never saw the searching did the check. Must be `true` for `done`.

The script works out each assumption's label from its items with the evidence check v6 rules. Never write a label into the data.

## The item shape

Used in `problems[].items` and `evidence.results[].items`. The evidence check v6 item, plus `signal`:

```json
{ "side": "for", "result": "counts", "reason": "", "kind": "own words",
  "quote": "exact words from the page, no quotation marks around them",
  "who": "name as the page shows it", "when": "date on the page, or: no date shown",
  "where": "site and kind of page, e.g. Trustpilot review", "did": "what they did, or empty",
  "note": "a caveat, or empty", "link": "https://...", "voice": "short name for the person or study",
  "found_in_check": false, "signal": "complaint" }
```

- `side`: `for`, `against`, `context`. `result`: `counts`, `set aside`, `removed`. A context item that passed the check has side `context` and result `counts`.
- `reason`: empty for an item that counts on a side. For `set aside` or `removed`, one of: `second_hand`, `stake`, `not_original`, `vague_amount`, `indirect`, `group_not_shown`, `old`, `could_not_open`, `pasted`, `not_on_page`, `off_target`, `author_not_shown`. The page turns each code into a plain sentence. `author_not_shown` (added by this kit) is for a post on a forum run by a company that sells a related product, when the page shows no author or no date.
- `kind`: `own words`, `number`, `organisation fact`. For a number or organisation fact, `who` is who counted or who states it, and `did` is what exactly was counted or stated.
- `did`: for own words, the action in a few plain words, or `""` if they only gave an opinion. Plans and "I would" are not actions.
- `who`, `where`, `did` and `note` are shown on the page: every sentence in them is under 25 words (the renderer checks all four, on problems and on evidence items).
- `voice`: the same short name for two items by the same person or study (they are one voice).
- `signal`: `complaint`, `money spent`, `time spent`, `workaround`, `switched`, `asked for recommendations`, `none`. Set it from what the quote itself shows. Numbers and organisation facts usually take `none`.
- `link`: http or https only, everywhere in the file.

## stress_test (`/discover-stress-test`)

```json
{
  "critics": [ { "role": "skeptic", "points": [ { "text": "", "hits": "A1", "grounded_in": "https://... or: no evidence either way", "would_settle": "" } ] } ],
  "forcing": [ { "question": "", "answer": "student's words", "pushed_once": false } ],
  "changes": [ { "id": "C1", "assumption": "A2", "change": "", "why": "", "decision": "pending" } ]
}
```

- `critics`: four, one per `role`: `skeptic`, `outsider`, `first-principles`, `practical`. At most 3 points each.
- `hits`: an assumption id. `grounded_in`: a link that already appears in `evidence` (an item or a product) or among the counted items of the problem the student picked, or exactly `no evidence either way`. `would_settle`: what would settle the point.
- `forcing`: the three forcing questions in order, as asked, with the student's answers. All three answered before `done`.
- `written_before_search` (optional): `true` when the critics ran while `evidence` was not `done` (the student jumped ahead). The page then says the points were written before any web search. Keep it `true` if `/discover-evidence` runs later.
- `changes`: ids `C1`, `C2`, ... `assumption` is the id of the assumption the change edits itself (a new rating, a move to interviews only, a reword in place), or `"new"` for every change that adds an assumption (a split, a narrower or reworded copy, a fresh one). The `change` text names what a new one builds on, in a few words. The page shows "Changes: <statement>" for an id and "Adds a new assumption." for `"new"`. `decision`: `pending`, `accepted`, `rejected`, set only by the student. None `pending` before `done`.

## interview_plan (`/discover-interview-plan`)

- `talk_to`: who to talk to, one sentence. `reach`: the student's answer about who they can reach and how.
- `where`: places to find them, each `{ "place": "", "why": "", "link": "https:// or empty" }`. Places only, never individuals.
- `big_questions`: exactly 3, each `{ "text": "", "tests": "A1" }`.
- `guide`: sections, each `{ "section": "...", "questions": [ { "text": "", "tests": "A1", "probes": ["", ""] } ] }`. Sections: `warm-up`, `last time`, `how important`, `how costly`, `how they chose`, `wrap-up`, `commitment`, each at most once. `tests` may be `""` only in `warm-up`, `wrap-up` and `commitment`. 1 to 3 probes per question.
- `money`: at least one, each `{ "text": "", "tests": "A1" }`.
- `commitment_ask`: one ask (a follow-up, an introduction, a pilot sign-up).
- `pass_marks`: each `{ "assumption": "A3", "measure": "described paying for a stock tool in the past year", "out_of": 10, "mark": null, "stands_in_for": ["A5"] }`.
  - `assumption`: never a `future` (would) assumption. A pass mark counts past actions, and no past action shows a would-claim. For a riskiest `future` assumption, put the pass mark on its `nearest_searchable` (or another past-behaviour assumption) and list the would-claim in `stands_in_for`.
  - `stands_in_for` (optional): the `future` assumption ids this mark stands in for. Every id must exist and be `future`.
  - `measure`: a short phrase (15 words or fewer) about something people did, which the student counts from their notes.
  - `out_of` defaults to 10; the student may change it. `mark` is always the student's number, at least 1, and stays `null` until they give it. One pass mark per assumption.
- `question_check`: each flag the separate question check raised: `{ "original": "", "problem": "...", "rewrite": "" }`. `problem`: `yes/no`, `future`, `hypothetical`, `leading`, `pitch`, `two questions`. `original` is the question as first written. Two ways to record a question that was dropped instead of rewritten:
  - `"rewrite": "dropped"`: it failed two check rounds. The page shows "Dropped after two checks." Use it only when that is true.
  - `"rewrite": "dropped: main question changed"`: a probe dropped because its main question was rewritten and the probe no longer fits. `problem` is its own flag, or `""` if it had none. The page shows "Dropped because its main question changed."
  The page shows `pitch` as "named a solution before the person did".
- `outreach`: at least two, for two different channels, each `{ "channel": "", "text": "" }`. Every message asks for the person's advice in so many words ("I'd value your advice"; "and experience" may be added). The renderer refuses a message without the word "advice".
- `notes_fields`: the fields on the printable notes sheet.
- `approved_by_student`: `true` only after the student approved the script. `done` needs it, and every `mark` set.

The renderer refuses any question (big questions, guide questions and probes, money questions, the commitment ask, rewrites) that uses a word from the published list under "The renderer also refuses", or that holds more than one question mark. The list is a backstop. The separate question check is the main guard.

## interviews (`/discover-interview-sort`)

```json
{ "id": "I1", "date": "", "who": "role only, no name",
  "facts": [ { "assumption": "A1", "side": "for", "kind": "did", "quote": "as written in the notes", "tag": "pain", "meets_measure": true },
             { "assumption": "A2", "side": "context", "kind": "opinion", "quote": "as written in the notes", "tag": "pain", "reply_to_flag": "leading" } ],
  "question_flags": [ { "question": "the question as written in the notes", "problem": "leading" } ],
  "new_findings": [ { "kind": "new problem", "about": "a few words naming it", "group": "N1", "quote": "as written in the notes" } ] }
```

- `new_findings` (optional; only when the interview holds one): something the person raised on their own that the assumptions don't cover. `kind`: `new problem`, `workaround` (one the frame doesn't name), `solution idea` (one the person voiced), `customer group` (another group that has the problem). `about`: what it is, 12 words or fewer, written the same, word for word, for every finding in its group. `group`: `N1`, `N2`, ...; the same thing raised in different interviews shares a group, and one group holds one kind. `quote`: the person's words exactly as in the cleaned notes, never the interviewer's and never from a summary. Leave `new_findings` out when nothing new came up: that is the normal result.
- **Counted by the page (worked out, not written in the data).** For each group, the page counts the interviews that raised it and lists the quotes. When a `new problem` group comes from 2 or more interviews, the page adds the line "Came up in <n> interviews without being asked: <about>." with the state of the pass marks. The renderer prints these counts after building.

- `question_flags` (optional): questions the student asked that should be asked differently next time, written only when the notes include the questions asked. `problem` uses the same values as `question_check`: `yes/no`, `future`, `hypothetical`, `leading`, `pitch`, `two questions`. The page shows them under that interview.
- `reply_to_flag` (optional, on a fact): the flag of the question this fact answers, when that question is in the interview's `question_flags`. A reply to a flagged question is never counted, for every flag type: its `side` must be `context` (background), and the page shows it as a reply to a flagged question. The flag must appear in that interview's `question_flags`.

- `side`: `for`, `against`, `context`, judged against the assumption's statement only. `kind`: `did`, `said would`, `opinion`. `tag`: `pain`, `workaround`, `money`, `goal`, `obstacle`.
- A fact on a `future` assumption is never `did` + `for`. A past action that resembles a would-claim goes on the past-behaviour assumption, or is `context`.
- `meets_measure` (true or false): required on every `did` + `for` fact whose assumption has a pass mark, ignored elsewhere. `true` only when the notes show every condition the measure names (time, place, size). If one is missing from the notes, `false`.
- The renderer refuses email addresses and phone numbers in any text field of an interview (`date`, `who`, quotes, flagged questions, new findings).
- Tallies: for each pass mark, the page counts the interviews holding at least one fact on that assumption with side `for`, kind `did` and `meets_measure: true`. It shows the measure, then "So far: n of N interviews. Your mark: m of out_of people." ("1 of 1 interview" and "1 of 1 person" for one; "So far: no interviews sorted yet." before any) and "met" or "not met yet" ("no mark set" while `mark` is null), plus "Stands in for: ..." when the mark has `stands_in_for`. `said would`, `opinion`, and facts that don't meet the measure never count.

## log

Each entry: `{ "date": "YYYY-MM-DD", "step": "frame", "student_decision": "what the student decided, in a few words" }`. `step` is the step's short name, its command without the slash and without the `discover-` prefix (the values didn't change when the commands were renamed in 2.3.0): `discover`, `find-problems`, `frame`, `evidence`, `stress-test`, `interview-plan`, `interview-sort`. Add one entry each time a command finishes or the student answers a stop. A `/discover` status check (on an existing file) writes no entry. Never remove entries.

## The renderer also refuses

Beyond the field shapes above, `render_page.py` refuses the data, writes nothing and lists the problem when any of these is true. Check them before you write, so the run doesn't loop. Fix the data; never edit the script or the template.

**Whole file**
- A sentence of 25 words or more ("under 25 words" means 24 at most), outside quotation marks, in a field the kit writes: problem `statement`, `who` and `about_one.what`; every item's `who`, `where`, `did` and `note` (problems and evidence); `problems_note`; `idea.sentence`; an assumption's `if_true` and `if_false`; `still_open`; each `not_found` line; a product's `fact`; a critic point's `text` and `would_settle`; a forcing `question`; a change's `change` and `why`; `talk_to`; a place's `why`; and each outreach `text`. Split long sentences. A word, here and in every word limit (12-word phrases and `about`s), is a run of characters between spaces that holds a letter or a digit, so a lone dash is not a word. Words inside double quotation marks (straight or curly; verbatim quotes) don't count, and the fill-in sentence is exempt. Single quotation marks don't exempt anything. The message names the field and how the sentence starts. When the renderer can't tell where a sentence ends, it doesn't end it there, so a wrong guess costs a rewrite, never a long sentence on the page. The rules:
  - **Quotation marks first.** In these fields the renderer refuses, before counting anything: a straight " right after a digit (write "10-inch" for a measure, or use curly quotation marks “ ” for a quotation that ends in a number); an odd number of straight " marks; a curly “ that is never closed, a ” with no “ before it, or a “ inside another curly quotation; and a single quotation of 25 words or more (long quotes belong in an item's `quote`). Each refusal names the field and says what to change. Then quotation marks are paired left to right: an opening " is closed by the next ", an opening “ by the next ”, and the words inside don't count.
  - **What ends a sentence:** ".", "!" or "?" (a closing quote or bracket may follow) when the next word starts with a capital letter or a digit, or with "(" or "[" and then a capital letter or a digit. A quotation that ends in one of these ends the sentence too, under the same rule for the next word, keeping its own mark: a quotation ending in "?" or "!" ends the sentence before a digit, one ending in "." doesn't. Nothing else ends a sentence: not a colon, a semicolon or an opening quotation mark.
  - **A full stop never ends a sentence** when the next word starts with a digit, or with "(" or "[" and then a digit ("approx. 40", "Jan. 2024", "end. (40 of them)"); after a word of five letters or fewer (apostrophes, as listed below, aside), in any alphabet, that starts with a capital letter and goes on in lower case (Jan., Sept., Calif., Prof., Corp., Dr., Mt., Lee., Paris., Köln., José., Joe's.), or a single capital initial (J., É.); after any run of single letters with full stops (U.S., e.g., a.m.); or after a lower-case short form on this list, in any letter case: approx., e.g., i.e., etc., vs., incl., esp., min., mins., hr., hrs., no., nos., est., ca., cf., fig., p., pp., vol., dept., wk., wks., mo., mos., yr., yrs., a.m., p.m., avg., sec., secs., ft., sq., lb., lbs., oz., misc., govt., al. So don't end a sentence on such a word, or just before a number: reword it ("... in Paris. Most ..." becomes "... in France. Most ...", and "... in 2024. 40 people ..." becomes "... in 2024. Forty people ..."), or keep both parts in one sentence under 25 words. A word written in capitals (NYU., UK., AI.) can end a sentence. The message names each mark it didn't read as a sentence end, and why ("Calif.": a short word with a capital; "2024. 40": a number follows).
  - **A line break** ends a sentence only when the line ends in ".", "!" or "?", under the same rules for full stops: a short form at the end of the line, or a next line that starts with a digit (or "(" or "[" and then a digit), keeps the sentence open. A greeting ("Hi Sam,") or a line ending in ":" runs on into the next line, so count it with that line.
- A broken character that can't be saved as text (often from copying a web page).
- Unknown keys anywhere, at the top level or inside any section or list entry.
- A step that has left `not_run` while the step before it is not `done` (or `skipped`).
- A step that is `not_run` (or `skipped`, or `running` for `find_problems`) whose section is not empty: for `not_run` and `skipped`, not exactly as in the starting file (an area entry's `area.text`, a key the starting file leaves out such as `problems_note` or `idea.sources`, all included). While `evidence` is `running`, `run_on` is filled and `results` stays empty.
- `waiting_on_student` empty while a step is `waiting` or `interview_sort` is `running`, or filled while no step is `waiting` or `running`.
- `find_problems` other than `skipped` for an idea entry, or `skipped` for an area entry.
- Any link that is not `http://` or `https://` (the scheme may be in any letter case, as the page's own link check allows).

**Problems**
- More than 8 problems, or problems not in order (most different voices among counted `for` items first, then most pages).
- A problem without counted `for` items on at least 2 different pages, or with an item whose `result` is not `counts`.
- A signal listed on a problem that none of its items shows, or a repeated signal. An empty `signals` list while a counted `for` item shows a signal other than `none`.
- Fewer than 5 problems with no `problems_note`. More than one picked problem; not exactly one once `find_problems` is `done`.
- An `about_one` whose `voices` names fewer than 2 voices, names one twice, or names one that is not the voice of a counted `for` item on that problem, or whose `what` is empty.

**Assumptions**
- A `future` assumption that is searchable, or without a `nearest_searchable` pointing to a searchable, non-future assumption.
- A searchable assumption with a `nearest_searchable`, or without `if_true` and `if_false`.
- A riskiest mark that breaks the rule in "Frame" above (candidates are high importance with weak or no evidence; 3 or fewer candidates are all riskiest; more than 3 means exactly 3, searchable ones first).
- `frame` `done` with any assumption not confirmed by the student. For an area entry, `idea.from_problem` empty, or naming a problem the student didn't pick.
- An assumption with `source: "ai guess"` and `evidence_now` other than `"none"`, or `source: "interviews"` with `evidence_now` `"strong"` or while no interview has `new_findings`.
- `fill_in_sentence` still holding "[not said yet]" or a slot name ("[who]", "[problem]", "[situation]", "[workaround]", "[amount or way]", spaces inside the brackets aside) once `frame` has left `not_run`, or anything but the starting file's template while `frame` is `not_run`.
- A `source` or an `idea.sources` value of `"checked sources"` on an idea entry. An `idea.sources` part whose `idea` field is empty.

**Evidence**
- More than 6 ids in `run_on`, any id after the third that is not both riskiest and searchable (only a top-up adds more than 3), or `evidence` `done` without one result per id in `run_on`, or without `checked_in_fresh_context: true`.
- A `language` phrase longer than 12 words, or not found word for word, in whole words, in an `own words` quote counted for or against (case, spacing and curly quotes ignored; background quotes don't qualify).
- A `suggested_checks` link that is not the link of a counted item, more than 5 of them, or a repeated one.
- More than 4 products, or more than 3 pages in `wouldnt_open`.
- A counted item on a side carrying a `reason`; a set aside or removed item without a valid reason code.
- A result's `unread.for`, `unread.against` or `unread.unclear` above `unread_pages.count`, or `unread.unclear` plus the larger side count above it. A result with any of them above 0 whose `not_found` lines don't each say "in the pages read".

**Stress test**
- Not exactly the four critic roles once the step has run; more than 3 points for a critic.
- A point whose `grounded_in` is neither exactly `no evidence either way` nor a link already in `evidence` (an item's or a product's) or among the picked problem's counted items.
- `stress_test` `done` with fewer than 3 answered forcing questions, or with any change still `pending`.

**Interview plan**
- Any question (big questions, guide questions, probes, money questions, the commitment ask, rewrites in `question_check`) that contains any of these, in any letter case. This is the full, fixed list:
  - "would", "wouldn't", "wouldnt", "wouldn’t" (any apostrophe)
  - "will you", "will your", "will they", "will people"
  - "who will", "what will", "which will"
  - "will" followed within three words by buy, pay, use, switch, try, sign or subscribe ("will anyone use it", "will the whole team pay", "will the in-house team pay"). Here and below, a word is any run of characters between spaces, punctuation included ("in-house", "company's", "team,", "Dr.", "R&D").
  - "won't you", "won't your", "won't they", "won't people" (also "wont")
  - "you'd", "they'd", and any word with "'ll" ("you'll", "they'll", "who'll", "it'll")
  - "might you", "might they"
  - "how much could you", "how much could they"
  - "how likely", "likely to buy / pay / use / switch / try", "likely are" or "likely is" followed by you, they, it, he, she or we and then "to", and "are", "is" or "am", then you, they, it, he, she, we, I or people (punctuation may follow it), then up to three words, then "likely to" ("are you likely to recommend it", "are they really very likely to")
  - "want to", "wants to" or "wanna" followed by buy, pay, use, switch, try, sign or subscribe, after any subject ("does your partner want to pay"), except "did you / they / we / he / she want to" or "... wanna" (past)
  - "what if"
  - "if such", followed by anything ("if such tools existed")
  - "say there was", "say there were", "say there is", "say there's"
  - "if there", "if it", "if this", "if that" or "if such", followed by was, were or existed
  - "if there is", "if there's" ("If there's an app that did this, what did you pay?")
  - "if a ..." or "if an ..." followed by one or two words and then "existed", "did", "was" or "were" (for example "if an app existed", "if a client was late")
  - "if" followed within four words by "existed" ("if a tool like that existed", "if something like this existed")
  - "should" followed within four words by "exist", including "should exist" ("should a tool like this exist")
  - "assuming" at the start of a question, or after ".", "!", "?", a comma, semicolon, colon, "(" or "[" ("Assuming a tool existed, ...", "Okay. Assuming it worked, ...", "(assuming it worked)", "e.g. assuming it worked")
  - "if we / I / someone / somebody / a company / an app" followed by built, made, offered, launched, created, had or could
  - "if you could", "if you had", "if you were", "if you got"
  - "imagine", "suppose", "supposing", "hypothetical", "hypothetically"
  - "in the future", "willing to", "see yourself"
  - "going to", "plan to" or "planning to" followed by buy, pay, use, switch, try, sign or subscribe

  "If" may be followed by a comma ("If, such a tool existed"). "What, if anything, did you pay?" is fine: with the commas it is not "what if". Without them it is refused. These, and only these, count as an apostrophe: ’ ‘ ‛ ʼ ʻ ʹ ׳ ՚ ꞌ Ꞌ ＇ ′ ‵ ´ ｀ and the backtick. Invisible characters (zero-width spaces, soft hyphens, word joiners, direction marks: every Unicode format character, plus the combining grapheme joiner and the variation selectors U+FE00 to U+FE0F and U+E0100 to U+E01EF) are ignored, and text is read in Unicode NFC form (a letter followed by a separately typed accent is the accented letter, and an accent with no composed form belongs to its letter), here and in every other check that reads text (`language` phrases, contact details, the fill-in sentence, the length rules). Any kind of space, a no-break space too, counts as one space, and quotation marks are ignored: every double one (" “ ” „ ‟ « » ＂ ″ 〝 〞) and a single one at the start or end of a word ("will the team “pay”" and "will the team ‘pay’" read "will the team pay"). Phrase the commitment ask as "Can I ...?" or "Could you introduce me to ...?". Ask about the past: "What happened the last time a client paid late, if it has happened?", not "What happens if a client was late?".
- Any of those questions holding more than one question mark (?, the fullwidth ？ or the small ﹖).
- A `question_check` entry whose `problem` is not one of the six flags. Only an entry with `"rewrite": "dropped: main question changed"` may leave `problem` empty.
- A guide question with an empty `tests` outside `warm-up`, `wrap-up` and `commitment`, or with no probes or more than 3.
- Once the step has run: not exactly 3 big questions, no money question, no pass mark, fewer than two outreach channels, no place, or an empty `talk_to`, `reach` or `commitment_ask`.
- An outreach `text` without the word "advice".
- A `mark` below 1 or above `out_of`, two pass marks for one assumption, a pass mark on a `future` assumption, an empty `stands_in_for` or one naming an assumption that is missing or not `future`, or `interview_plan` `done` with a `mark` still `null` or the interview guide not approved.

**Interviews**
- An email address or phone number in any text field of an interview. A phone number here is 10 or more digits in one run, with spaces, dashes, dots or brackets between them, so a shorter local number isn't caught: the privacy check at `/discover-interview-sort` removes those. Not phone numbers: a run of years ("2023 2024 2025"), dates written with dashes or dots, with a two- or four-digit year, alone or joined by spaces or a dash ("2026-03-01 - 2026-05-01", "01.03.2026 01.05.2026", "01.03.26"), and a number grouped in threes by spaces or dots ("1 200 000 000"). An email address is any text@text.letters, in any alphabet.
- A fact marked `did` + `for` on a `future` assumption.
- A `did` + `for` fact on an assumption with a pass mark, without `meets_measure` set to true or false.
- A fact with `reply_to_flag` whose `side` is not `context`, whose flag is not one of the six, or whose flag isn't on a question in that interview's `question_flags`.
- A new finding without a quote, with an `about` over 12 words or a group that isn't `N1`, `N2`, ...; two findings in one group with different kinds or different `about` wording; the same kind and `about` in two groups. `about` is compared with letter case, spacing, apostrophe style and a final full stop aside.
- A fact's or a new finding's `quote` that is one of that interview's `question_flags` questions (the interviewer's words), or a new finding's `quote` that is also a fact's `quote` in the same interview (what an assumption covers is a fact).
- `interview_sort` `done` with no interviews. (While it is `running`, interviews from an earlier batch may be there.)
