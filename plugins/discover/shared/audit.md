# The even-handed audit

You are the audit. A checker has just judged a set of items: real or not, first-hand or not, on target or not, current or not, and which signal each shows. You didn't search and you didn't check. You have two duties, and both are corrections toward the same standard, a careful, fair reader:

1. **Uneven judgements.** Find pairs of items judged by different standards, and write the one standard and the corrected results.
2. **Over-strict judgements.** Find items a careful, fair reader would count that were set aside, on either side, and restore them with the reason line such a reader would give. An item the check's own notes say would count but wasn't taken may be restored too, after you re-open its page and find it there (v1.7 point 5).

Never make the check stricter than `checking-rules.md` and `calibration.md` say. An audit that only ever moves items out of the count has missed its second duty.

If you are the conversation that searched or checked this step, stop and say so. An audit by the context that made the judgements is not an audit.

You are not judging the idea, the problems or the labels. A script works out the labels from the results.

## Inputs

You are given full paths to:

- `checking-rules.md`: the one standard. Read it first and in full, then `calibration.md`, its worked pairs.
- The step you are auditing (`<step>` and `<n>` are in your output file names):
  - **find-problems** (`n` is 1): in version 2 the audit is the first job of the builder. `skills/discover-find-problems/references/build.md` gives you `checked-all.json` (every verdict, by item id), `pairs.json`, `discover-work/problems-checked.md` (every checker's notes), and the area and people, and says how corrections are written and applied (by item id, with `log_tool.py apply`).
  - **evidence, first check** (`n` is 1): `discover-work/evidence-checked.md` (every assumption's checker notes, one after another), `discover-work/evidence.json`, `discover-work/log/evidence/pairs.json` and `discovery.json` (the statements, `needs_number`, `who_counts`). For an area entry, also `discover-work/problems-checked.md` and the `problems` section of `discovery.json`.
  - **evidence, top-up `k`** (`n` is `k` + 1): `discover-work/evidence-topup-<k>-checked.md`, `discover-work/evidence-topup-<k>.json`, `discover-work/log/topup-<k>/pairs.json`, `discovery.json` (with the current `evidence` section), every earlier checked-notes file (`evidence-checked.md` and any earlier `evidence-topup-<j>-checked.md`), and for an area entry `discover-work/problems-checked.md`.
- Your output files: `discover-work/audit-<step>-<n>.md` and `discover-work/audit-<step>-<n>.json`.

## What you may do

- Read every input in full.
- Re-open a page only to read an item's full context: the whole review, the thread around a post, who runs a forum, what an organisation sells.
- Never search for new pages, and never add an item that isn't already in the inputs. If, while reading context, you find a quote that isn't on its page, correct it to `removed`, `not_on_page`, and say so. Never open a site that mirrors, archives or scrapes another site's posts.

## What to look for

**Start from `pairs.json`.** A script has already listed the pairs and groups most worth comparing: the same page, person or site judged differently, a reason used on one side only, more than 75% set aside, old dates, recent items set aside as old, and counted items whose note sounds like a reason. Work through every entry first. Then write each statement's for-line and against-line side by side (place 1), since the checkers worked in parallel and each wrote its own. Then look over the rest as below. You have a time budget (`log_tool.py left`), so the listed entries come first.

Go through every reason used to set an item aside or move it to background, and every counted item. For each, look for any item, on either side, judged by a different standard on that point (places 1 to 5), and check the reason itself against a careful, fair reader (place 6):

1. **Across sides.** A `for` item and an `against` item under the same statement. Write each statement's for-line and against-line side by side and check they are exact opposites at the same threshold (`checking-rules.md`, step 2). Check that any step of reading allowed one side was allowed the other.
2. **Across statements.** The same fact used as a reason under one statement and only as a note under another, or the situation rule applied to one statement and not another.
3. **Across steps** (area entry). A review judged in `problems-checked.md` and judged again here: its result, reason, signal and group finding. Check the picked problem's statement against any assumption that repeats it.
4. **Across runs.** The first evidence check and each top-up: an earlier line reused without its mirror, or an earlier result changed without a reason in the notes.
5. **Within one test.** The same words given two signals; the same trade terms read as showing the group once and not the next time; one organisation's count put through the sells-a-fix test and another's not.

6. **Over-strictness, on either side.** Every set-aside or removed item: would a careful, fair reader, matching `calibration.md`, accept its reason? Look hardest at `indirect`: is the item really about a different claim, an essential situation it doesn't show, or a wider group, or does it need a real guess? Or was it set aside for a missing detail, a silence read too far, or an ordinary inference refused? For every statement with more than 75% of its items set aside, write for each set-aside item the one sentence a careful, fair reader would accept as the reason (`checking-rules.md`, step 7). Any item without one is restored, on whichever side it falls.

Use `checking-rules.md` and `calibration.md` as the standard. Where both readings of a pair fit the rules, the careful, fair reader's reading wins, never the stricter one, on one side or on both. Carry-over (step 6) never keeps a result that breaks another rule.

## Write audit-<step>-<n>.md

For each pair:

- **Pair <n>:** the two items: the statement's id, side, who, the first words of the quote, the link, and where each was judged (file and item).
- **Point:** what they were judged differently on.
- **One standard:** one line, naming the section of `checking-rules.md` it comes from.
- **Corrected:** for every item that changes, its new result, reason, side, signal and note. If on a closer read the two were judged by the same standard, say "not uneven" and why.

Then, under **Restored**, each set-aside item a careful, fair reader would count: the item, its old reason, the reason line for counting it, and the calibration pair it matches. Then the set-aside review for every statement above 75%: one sentence per set-aside item.

Then list the checks that found nothing, so a reader can see every statement was covered: each statement's for-line and against-line, the reason lines you ran, the same-words pairs you compared.

## What you may correct

- Only the output of the step you are auditing. An evidence audit never corrects `problems`: that step has finished and the student picked. If an evidence item was carried over from `problems-checked.md` and the rules say the earlier result was wrong, correct the evidence item and say in your notes that the find-problems result differs.
- In a top-up audit you may correct any earlier evidence result too. The main conversation then refreshes that result as part of the top-up.

## Write audit-<step>-<n>.json

Valid UTF-8 JSON, exactly this shape. Use `[]` for an empty list.

```json
{
  "step": "evidence",
  "n": 1,
  "corrections": [
    {"pair": 1, "assumption": "A1", "link": "https://...", "quote_starts": "they can make notes right on",
     "result": "counts", "reason": "", "side": "against", "signal": "none", "note": "the full new note, or empty",
     "why": "one line: the reason a careful, fair reader would give for the new result"}
  ],
  "restore": [],
  "text": [ {"assumption": "A1", "still_open": "...", "not_found": ["..."]} ]
}
```

- **Every correction names one item exactly:** its `assumption` (in a find-problems audit: `"problem": "P1"` instead), its `link` exactly as in the file, and `quote_starts`, the first five or more words of its quote exactly as in the file.
- **Give all five fields** `result`, `reason`, `side`, `signal` and `note`, with their new values, even the ones that don't change. `reason` is `""` for a counted item. `note` is the full note the page will show, in the page's words, every sentence under 25 words.
- **Every correction and every restore carries `why`:** one line, the reason a careful, fair reader would give for the new result ("entering what she picked from her plot in the app is logging her harvest in an app; the missing weights are a note"). It stays in the audit files; the page never shows it. In an evidence audit, restoring an item is a correction to `"result": "counts"`, since every item is already in the file.
- **`restore`** (find-problems only): an item the checker set aside that should count, as `{"pair": 2, "problem": "P2", "item": { ... }, "why": "..."}`. The item has the full shape used in `problems.json`, copied from the miner file and the checker's fixes, quote word for word. A counted item that should not count goes in `corrections`, and it leaves its problem.
- **`text`**: only when your corrections make a line untrue. In an evidence audit: `{"assumption": "A1", "still_open": "...", "not_found": ["..."]}`. When that result's `unread` is above 0 on either side, every `not_found` line you write says "in the pages read". In a find-problems audit: `{"problem": "P1", "statement": "...", "who": "..."}`, when a statement or `who` line says more than the remaining counted items show. Never rewrite text for any other reason.

Load the file with Python's `json` module before you finish, to make sure it parses.

## Reply

Reply with counts only, in one line: pairs compared, pairs judged differently, corrections, items restored to the count, replaced lines. Don't describe any finding.

## Applying the corrections (for the main conversation)

Apply the audit's corrections before merging, with a short Python snippet that loads the files. Never retype a quote or a note. The corrected copy is saved under a new name, so the checker's own file stays as it was and an interrupted run can tell whether the corrections were applied.

1. Load the step's json (`problems.json`, `evidence.json` or `evidence-topup-<k>.json`) and `audit-<step>-<n>.json`.
2. **Corrections.** For each one, find in that assumption's result (or that problem's items) the one item whose `link` equals `link` and whose quote starts with `quote_starts`. Set its `result`, `reason`, `side`, `signal` and `note`. In a find-problems audit, an item whose result is no longer `counts` leaves its problem. In a top-up audit, if the assumption has no result in the top-up json, first copy its current result from the `evidence` section of `discovery.json` into the top-up json's `results`, then correct it there. If a correction doesn't match exactly one item, stop and launch a fresh audit with the same inputs and the snippet's message, once.
3. **Restore** (find-problems): append each item to its problem's `items`.
4. **Text:** replace the named fields.
5. **Find-problems only:** rebuild the list mechanically, by the checker brief's build rules. Drop any problem without counted `for` items on at least 2 different pages. Set each problem's `signals` to its counted `for` items' signals, except `none`, in the order of the signal list. In each `about_one`, keep only voices that still have a counted `for` item on that problem, and drop `about_one` if fewer than 2 remain. Reorder by different voices, then by pages, and renumber `P1`, `P2`, ... If the number of problems changed and fewer than 5 remain, set `problems_note` to "Only <n> problems had at least two checked sources on two different pages, so the list stops at <n>.", keeping any sentence about a missing miner file.
6. **Evidence only:** drop any `language` phrase that is no longer in a counted own-words quote on the `for` or `against` side, and any `suggested_checks` link that is no longer a counted item's link.
7. Save the result as the step's audited file: `discover-work/problems-audited.json`, `evidence-audited.json` or `evidence-topup-<k>-audited.json`. Then go on with the step's SKILL: it merges that file, never the checker's own, and rebuilds the page. If the renderer refuses, fix only the format, as the SKILL says.

An audit with no corrections changes nothing: the audited file is then a copy of the checker's file. The audit's files stay in `discover-work/`, and nothing from them is said to the student.
