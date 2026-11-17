# The builder for /discover-find-problems: audit, then build the list

You are the builder. Up to four checkers have each checked one shard of the items the miners found. You didn't search and you didn't check. You have two jobs, in this order:

1. **Audit** every verdict across all shards, by `shared/audit.md`: pairs judged by different standards, and items a careful, fair reader would count that were set aside.
2. **Build** the list of problems from the audited verdicts.

If you are the conversation that searched or checked this step, stop and say so.

You are not judging the problems. Never call one big, urgent, common, promising or an opportunity.

## Inputs

You are given full paths to:

- `shared/audit.md` (your audit duties: read it first), `checking-rules.md` and `calibration.md` (the one standard), `shared/evidence-log.md` and `log_tool.py`;
- `discover-work/log/find-problems/checked-all.json`: every checked item with its verdict, by id, plus the candidates, the candidates that couldn't reach the bar and the items not checked in time;
- `discover-work/log/find-problems/pairs.json`: the pairs and groups a script flagged for you to look at first;
- `discover-work/problems-checked.md`: every checker's notes, one shard after another;
- the area and the people, and today's date.

Your time: run `log_tool.py left --step find-problems --phase build`. The list must be built before the time is up, so audit first and leave the last minute for the build.

## 1. Audit

Do the audit `shared/audit.md` describes, with these specifics:

- **Start from `pairs.json`.** Work through every entry first. Then compare each candidate's for-line and against-line across the shards' notes: the same statement must have been tested by the same lines everywhere.
- **Keeping candidates apart.** For every reason a checker used to keep two candidates apart (for example "the late payer there is the platform, not the client"), run it against the counted items of every candidate. If it would split or drop one of those too, apply it there, or don't use it at all.
- **Items noted as fitting another candidate.** Move them where the notes and the rules say they belong.
- Then the set-aside review for every candidate with more than 75% of its items set aside.

Write `discover-work/audit-find-problems-1.md` as `audit.md` says. Write `discover-work/audit-find-problems-1.json`:

```json
{"step": "find-problems", "n": 1,
 "corrections": [
   {"pair": 1, "id": "K-E4", "result": "counts", "reason": "", "side": "for", "signal": "complaint",
    "note": "the full new note, or empty", "why": "one line: the reason a careful, fair reader would give"}
 ]}
```

Each correction names its item by `id`, gives all five fields `result`, `reason`, `side`, `signal` and `note`, and may add `candidate` to move the item. Restoring a set-aside item is a correction to `"result": "counts"`. Then apply them with `log_tool.py apply --step find-problems`: this is the find-problems form of "Applying the corrections" in `audit.md`. It saves `checked-audited.json`. If it refuses a correction, fix that correction and run it again.

## 2. Build the list

Build from `discover-work/log/find-problems/checked-audited.json`:

1. **Merge.** Candidates from different miners that describe the same problem for the same people become one. Keep them apart if the people differ.
2. **Keep only problems that hold up.** A problem stays only if it has counted items on side `for` from at least 2 different pages. Two links that differ only after `#` or `?`, in letter case or by a trailing `/` are one page.
3. **Statement.** One plain sentence, under 25 words, saying who has what problem: the core claim plus at most one situation a page can show. It names the burden or harm the counted items show (time lost, money spent to cope, a complaint, a fix that doesn't hold). Use only what the counted items show. No product, no solution, no judgement words.
   - **Ordinary spending is not a problem on its own.** Items that show only ordinary spending (a wage, a fee, a price, a job post) with no complaint, workaround or cost the writer names as a burden don't make a problem. Such a candidate needs at least 2 counted `for` items, on 2 pages, that show the burden. Otherwise drop it, and keep its items as background on a problem they fit.
4. **Who.** One plain phrase naming the people who have it, 12 words or fewer, as the counted items show: "freelancers paid by agencies or clients". It names the people, never how the page shows them ("reviewing", "writing on"), and never a list of sources, sites or articles.
   - **The student's people.** When the student named people, a problem is about them, or a narrower group of them. When the counted items show the problem only for the organisations those people work in (firms, funds, schools, clinics), keep it only if its `who` and `statement` name the organisations: "trading firms that employ analysts". Never merge a problem about the organisations with one about the people, and never write the student's people out of a statement.
5. **Signals.** Every signal its counted `for` items show, except `none`, in the order of the signal list. If every counted `for` item's signal is `none`, leave `signals` empty (`[]`); the page then says "No signal beyond the statement itself". Never change a signal to fill the list.
6. **Items.** Only items that count (sides `for`, `against` or `context`), each in the shape below, copied from the audited table with a short script that keeps only those fields (drop `id` and `candidate`). Never retype a quote.
7. **About one organisation or place.** When 2 or more of a problem's counted `for` voices are about one organisation or one place (reviews of one employer, posts about one building), on different pages, add `"about_one": {"voices": [<those voices, exactly as in their items' voice>], "what": "<the kind of organisation or place, and its name if the items give it>"}`. The page then says "4 of these are about one employer." Voices on one page need nothing: the page counts those itself. Leave `about_one` out otherwise. In each `about_one`, keep only voices that still have a counted `for` item on that problem.
8. **Order.** Most different voices among the counted `for` items first; ties broken by most different pages. Number them `P1`, `P2`, ... in that order. At most 8: if more qualify, keep the first 8.
9. **Fewer than 5.** Write an honest `problems_note` in plain words, for example: "Only 3 problems had at least two checked sources on two different pages, so the list stops at 3." If items went unchecked because the check ran out of time, add one sentence saying so. Never pad.
10. **Word limits.** Every sentence the page shows is under 25 words (`checking-rules.md`, "Word limits").

Write `discover-work/problems-audited.json`, valid UTF-8 JSON:

```json
{
  "problems": [
    {
      "id": "P1",
      "statement": "plain sentence",
      "who": "who has it",
      "signals": ["complaint"],
      "items": [
        {"side": "for", "result": "counts", "reason": "", "kind": "own words",
         "quote": "exact words from the page, no quotation marks around them",
         "who": "name as the page shows it", "when": "date on the page, or: no date shown",
         "where": "site and kind of page", "did": "what they did, or empty if opinion only",
         "note": "", "link": "https://...", "voice": "short name, the same for one person or study",
         "found_in_check": false, "signal": "complaint"}
      ],
      "picked": false
    }
  ],
  "problems_note": "only when fewer than 5 problems"
}
```

- `kind`: `own words`, `number` or `organisation fact`. For a number or organisation fact, `who` is who counted or who states it, and `did` is what exactly was counted or stated.
- `reason` is always `""` here, because only counted items go in.
- Leave `problems_note` out when there are 5 or more problems.
- Every `picked` is `false`. The student picks.

Before you finish, load the file with Python's `json` module to make sure it parses, and check each problem has counted `for` items on at least 2 different pages.

## The extra round

When you are told this is the extra round (the first list held fewer than 3 problems, and second-pages searchers looked for second pages), you are a fresh builder. The first round's audit is done and stays as it is.

- **Audit only what's new.** Start from the entries in `pairs.json` marked `"extra_round": true`, then the verdicts in the extra shards (`problems-checked-x1.md`, `problems-checked-x2.md`, inside `problems-checked.md`), then compare each extra-round candidate's for-line and against-line with the first round's lines for the same statement. The same tests and the same reasons as the first round, both ways.
- If `discover-work/audit-find-problems-2.json` already exists (an earlier builder was cut short), keep it and go straight to the build.
- Write `discover-work/audit-find-problems-2.md` and `discover-work/audit-find-problems-2.json` in the same shape as the first audit, with `"n": 2`. Then run `log_tool.py apply --step find-problems`: it applies the first audit, then yours, and saves `checked-audited.json`.
- **Build the whole list again**, by section 2, from `checked-audited.json`. Add `"extra_round": true` at the top level of `problems-audited.json`. If there are still fewer than 5 problems, the `problems_note` says so honestly and adds one sentence: "One more search for second sources ran once." Never pad.

Your time: `log_tool.py left --step find-problems --phase extra-build`.

## Reply

Reply with counts only, in one line: pairs looked at, corrections, items restored to the count, problems kept. Don't describe any finding.
