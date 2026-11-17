# Miner 3: organisations' own numbers and recent changes

Read `mining-rules.md` in this same folder first. It holds the rules for what counts, your budget and how to log what you find. This brief tells you where to look. Your source name in the log is `counts`, so your ids start with `N`.

## Your job

Find what organisations themselves counted or announced about problems in the given area: how many people have a problem, how often, what it costs them, and recent changes that create or shift a problem (a new rule, a price rise, a service closing). The other two miners cover people's own words.

## Where to look

- Government statistics and public data from the agency that collected them.
- Surveys that state their method (who was asked, how many, when), from the organisation that ran them.
- Academic papers with their own data.
- Company filings.
- An organisation's own announcement of a change: a new rule, a policy change, a price change, a shutdown notice.

## Rules for numbers

- Use only the original. A news story, blog or statistics roundup that repeats a number is not the source, and you don't open it: search for the organisation that counted and the figure, as `mining-rules.md` says. If no search reaches the original, don't use the number.
- Record who counted, what exactly they counted, who was asked or measured, and when.
- A rough amount ("thousands", "many") is not a count. Skip it.
- If the organisation that counted also sells a fix for the thing it measured, record what it sells in the item's note. The checker treats such a number as background at most.
- A number that measures a wider group, or a neighbouring thing, is not about this group. You may record it, with a note saying how it differs; the checker decides.

## How to search

- Pair the people or the part of life with count words: "<people> survey", "<problem> statistics <agency>", "how many <people> <problem>", "<problem> report <year>".
- For changes: "<area> new rule <year>", "<service> price increase", "<service> closing".
- A second try on an empty search changes the approach (a different kind of source), not just the wording.

## What to record

Mostly `number` and `organisation fact` items. Their signal is usually `none`; use `money spent` or `time spent` when the count itself measures money or time people spent on the problem.

Follow `mining-rules.md` to log what you find as you go, with `--source counts`.
