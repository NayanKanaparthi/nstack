# The evidence log (version 2)

Searchers, checkers and the audit don't keep their work in their heads or in one long file written at the end. They write each search, page, candidate, item and verdict to the evidence log the moment it happens. Three things follow from that:

- A step that is stopped, or runs out of time, loses nothing. Running the command again carries on from the log.
- A small script counts the log, so nobody has to re-read notes to know whether there is enough.
- Every agent sees its own budget and the time left after every page.

The log is plain text: JSON Lines, one JSON object per line, in `<student folder>/discover-work/log/<step>/`. Steps: `find-problems`, `evidence`, `topup-1`, `topup-2`, ... Each searcher writes its own file, so agents working in parallel never write over each other. Lines are only ever added, never edited.

## The script

`<plugin root>/shared/log_tool.py`. Run it only as a command, exactly like this, never import it:

```
PYTHONDONTWRITEBYTECODE=1 python3 <plugin root>/shared/log_tool.py <command> --folder "<student folder>" --step <step> [options]
```

Use `python` if `python3` is not found. Send lines to `add` and `result` on standard input with a quoted heredoc, so apostrophes and quotation marks in quotes are safe:

```
PYTHONDONTWRITEBYTECODE=1 python3 <plugin root>/shared/log_tool.py add --folder "<student folder>" --step find-problems --source complaints <<'END'
[{"type": "page", "link": "https://...", "outcome": "opened"},
 {"type": "item", "candidate": "K1", "side": "for", "kind": "own words", "quote": "...", "link": "https://...", "who": "...", "when": "...", "where": "...", "group_shown": "yes, says they rent", "action": "none", "signal": "complaint"}]
END
```

If the script refuses a line, it saves nothing from that call and says why. Fix the line and send the whole call again.

| Command | Who runs it | What it does |
|---|---|---|
| `clock --phase P` | the main conversation, before each phase | starts the phase clock |
| `left --phase P` | anyone | minutes left in the phase |
| `add --source S` | searchers | adds lines, then prints the budget used, the time left and whether there is enough |
| `status --source S` | searchers | the same print-out, without adding anything |
| `candidates` | find-problems searchers | the shared candidate list, with counts |
| `shard` | the main conversation (find-problems) | splits the items into groups for parallel checkers |
| `thin` | the main conversation (find-problems) | when the built list is thin, lists the candidates that sit on one page, in `extra-targets.json` |
| `shard --extra` | the main conversation (find-problems) | splits only the items with no verdict yet into 1 or 2 extra shards (`x1`, `x2`) |
| `ledger --run-on A1,A2` | the main conversation (evidence) | writes one ledger per assumption from the log |
| `result --shard X` | checkers | adds verdicts, then prints the time left (`extra-check` for shards `x1` and `x2`) |
| `merge` | the main conversation (find-problems) | joins items and verdicts in `checked-all.json` |
| `pairs` | the main conversation | lists the pairs the audit looks at first, in `pairs.json` |
| `apply` | the find-problems builder | applies the audit's corrections by item id: the first audit, then the extra round's (`audit-find-problems-2.json`) if there is one |
| `assemble --run-on A1,A2` | the main conversation (evidence) | builds `evidence.json` from the verdicts |

## Line types

Searchers send these with `add` (`"type"` names the line):

- `search`: `words`, and `came_back` (what the results held, in a few words). In evidence: also `assumption`, `side` (`for`, `against`, `extra` or `any`) and `kind` (`own words` or `numbers`).
- `page`: `link`, `outcome` (`opened`, `failed` or `nothing useful`). In evidence: also `assumption` and `side`. Log every page you open, including ones that fail.
- `candidate` (find-problems only): `statement`, `who`. The script gives it an id. If another searcher already listed the same statement, it says which id to use.
- `item`: the fields of an item in your brief: `side`, `kind`, `quote`, `link`, `who`, `when`, `where`, `group_shown`, `action`, `signal`, and `candidate` (find-problems) or `assumption` (evidence). Optional: `opened` (`yes`, `snippet only` or `pasted by student`), `also_on_page`, `note`. The script gives it an id.
- `option` (evidence only): `name`, `link`, `kind`, `fact`, and `date` if the page shows one.
- `nothing_found` (evidence only): `assumption`, `side`, `kind`, `tried`.
- `not_opened`: `link`, `why` (`blocked`, or `over the page limit`), `held` (what it seemed to hold). In evidence: also `assumption` and `side` (`for`, `against` or `unclear`).

Checkers send these with `result`:

- a verdict: `id` (the item's id), `result`, `reason` (empty when it counts), `side`, `signal`, `note`, and `voice`. Add `did` when you correct it, and `candidate` when you move an item to another candidate.
- an item found in the check: the full item fields plus `"found_in_check": true` and the verdict fields, with no `id`.
- `{"type": "summary", ...}` (evidence only): `assumption`, `still_open`, `not_found`, `language` (up to 3 phrases), `searches` and `pages_opened` you used, and `products` (only the checker given the existing options).
- `{"type": "done", "shard": "<your shard>"}` when you have finished.

## Budgets

Every phase has a time budget. Every searcher also has a budget of searches and pages. The script prints what is left after each call. These are the settings, and changing them is a decision for the kit's owners, not for a run:

| Step | Phases (minutes) |
|---|---|
| find-problems | search 3.5, check 3.5, build 2.5 |
| find-problems, extra round (only when fewer than 3 problems hold up, once) | extra-search 3, extra-check 2.5, extra-build 2.5 |
| evidence and top-ups | research 3.5, check 3.5, audit 2.5 |

- A find-problems searcher: up to 6 searches and 8 pages.
- A second-pages searcher in the extra round (`second-1`, `second-2`, at most 2): up to 4 searches and 5 pages. It can't add candidates. The extra round covers at most 6 one-page candidates.
- An evidence researcher (one assumption): up to 5 searches and 5 pages. The first researcher also runs the two extra searches (low-star reviews of the options, and job posts), with up to 3 extra pages.
- At 1 minute left, or when the time is up, stop opening pages, log what you have, and finish. Time left is a reason to stop, never a reason to rush a judgement.

## Enough

The script also says when there is enough to stop early.

- **Find problems:** a candidate is strong when it has 4 or more `for` items, from 3 or more people, on 2 or more pages. With 6 strong candidates, every searcher stops. Below that, the print-out names the candidates that sit on one page only, so a searcher can spend a search on a second page for them.
- **Find problems, extra round:** a second-pages searcher has enough when every candidate it was given has a `for` item on a page other than the one it sat on.
- **Evidence:** an assumption has enough when both its `for` and `against` own-words searches ran, a page was opened for each side, and one side has items from 3 or more people on 2 or more pages.

"Enough" is a count against the kit's own rules, not anyone's feeling of confidence. It ends the searching only. Every check still runs in full.

## What stays out

- A candidate that can't reach 2 `for` items on 2 pages isn't checked: it could not become a problem on the list. In the extra round, the same bar counts its items already counted plus its new ones.
- An item with no verdict when its check ends isn't shown. In evidence, its page counts as unread for its side, so the page stays honest about what wasn't read.
