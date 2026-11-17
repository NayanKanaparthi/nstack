# Second-pages searcher: the extra round for a thin list

Read `mining-rules.md` in this same folder first, then `shared/evidence-log.md` (you are given both full paths). They hold the rules for what counts, how to take an item and how to log it. This brief says what is different in the extra round. Your source name in the log is `second-1` or `second-2`, as you were told, so your ids start with `S1` or `S2`.

## Why you are here

The first search found candidate problems, but fewer than 3 held up: a problem needs counted items on at least 2 different pages, and most candidates sit on one page. You have one job: for each candidate you were given, find a **second, different page** where a person describes that same problem first-hand, or where an organisation states its own count of it.

You are not judging anything, and you are not looking for new problems. The script refuses new candidates from you.

## Your candidates

`extra-targets.json` (you are given its full path) lists the candidates, each with `searcher` (yours or the other one's), `statement`, `who` and `page` (the one page it sits on now). Work only on the ones whose `searcher` is your source name, in the order listed.

## How to search

- Search for the same problem, for the same people, in other words: the words these people use ("anyone else", "how do you deal with", "is it just me"), a place they write (a named forum or community, low-star reviews of a product they use), or a count of it (a survey, a regulator's figures).
- Keep the people the candidate names. A page about someone else (their employer, their customers) doesn't count as a second page for it.
- The page in `page` doesn't count again, nor does another link to the same page.
- A second try on an empty search changes the approach (a different place or kind of source), not just the wording.
- Never open a copy of another site: never open a site that mirrors, archives or scrapes another site's posts, even when a search returns it. The rules on Reddit, on pages that only repeat others, and on recency in `mining-rules.md` hold here too.

## Budget

Up to 4 searches and up to 5 pages opened, including pages that fail, in about 3 minutes (clock phase `extra-search`). Every `add` call prints your budget, the time left, and which of your candidates still sit on one page.

**Stop** when it says "ENOUGH: yes" (every candidate you were given has a second page), when your budget is used, or when it says to wrap up or that time is up. Log anything not yet logged, then reply. Time running out is a reason to stop, never a reason to copy less carefully.

## Logging

Exactly as `mining-rules.md` says, with `log_tool.py add --step find-problems --source <your source name>`: a `search` line for each search, then after each page one call with the `page` line and every item you took from it. Log each item under the candidate it fits, using its id from `extra-targets.json` or the `candidates` command. If a page you open also holds an item for another listed candidate, log it under that one too. Log `not_opened` lines at the end, as the rules say.

## Reply

Reply with counts only, in one line: searches run, pages opened, items logged, how many of your candidates now have a second page, and why you stopped. Don't describe any finding.
