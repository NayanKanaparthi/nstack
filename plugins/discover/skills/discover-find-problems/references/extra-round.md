# The extra round for a thin list

This file is for the main conversation running `/discover-find-problems` (or the whole-path run). It is not a sub-agent brief. "SKILL.md" below means `discover-find-problems/SKILL.md` in this skill's folder. Every `log_tool.py` command runs exactly as SKILL.md shows, with `--step find-problems`.

Read it only when the built list (`discover-work/problems-audited.json`) holds fewer than 3 problems and there is a sub-agent tool (SKILL.md step 5c).

With fewer than 3 problems, the student would get almost nothing to pick from, so run one extra round, once. It looks only for a second page for candidates that sit on one page. Pick up where it stopped:

- `discover-work/problems-audited.json` holds `"extra_round": true`: the extra round is done. Go to SKILL.md step 6.
- `discover-work/audit-find-problems-2.json` exists: the extra build was cut short. Go to point 4; the builder keeps that audit and builds.
- The `extra` list in `shard-summary.json` is there: go to point 3, and launch checkers only for extra shards whose `check-<shard>.jsonl` has no done line.
- `extra-targets.json` exists: the extra search ran or was cut short. Go to point 3.
- Otherwise start at point 1.

1. **Targets.** Run `log_tool.py thin`. It lists up to 6 candidates that sit on one page, each with its searcher (`second-1` or `second-2`), in `extra-targets.json`. If it lists none, go to SKILL.md step 6.
2. **Search, about 3 minutes.** Tell the student one line: "Only <n> problem<s> held up so far. Looking once more for second sources, about 3 minutes, then a short check." Start the clock: `log_tool.py clock --phase extra-search`. Launch one general sub-agent per searcher named by `thin`, in one message. Give each its brief, `<this skill's base directory>/references/second-pages.md`, with `references/mining-rules.md` and `shared/evidence-log.md`; the full paths of `log_tool.py`, the student's folder and `extra-targets.json`; its source name; the area and people word for word; today's date; and the instruction to reply with counts only. None of them may be one that checked or built.
3. **Check only what's new, about 2.5 minutes.** Run `log_tool.py shard --extra`. It splits the items with no verdict yet into 1 or 2 shards (`x1`, `x2`), for candidates that can now reach 2 counted items on 2 pages. If it makes no shard, nothing new can join the list: with a short Python snippet, set `"extra_round": true` in `problems-audited.json` and add one sentence to its `problems_note` ("One more search for second sources added none."), then go to SKILL.md step 6. Otherwise start the clock (`clock --phase extra-check`) and launch one fresh checker per shard, as in SKILL.md step 5, with `discover-work/problems-checked.md` too (the first round's notes, so the same statement is tested by the same lines), and the notes file `discover-work/problems-checked-<shard>.md`. When they reply, run `merge`, join every checker's notes again in shard order (`cat discover-work/problems-checked-[0-9]*.md discover-work/problems-checked-x[0-9]*.md > discover-work/problems-checked.md`), then run `pairs`.
4. **Build again, about 2.5 minutes.** Start the clock: `clock --phase extra-build`. Launch one more fresh sub-agent, one that didn't search or check in this round, with the same inputs as SKILL.md step 5b, and tell it this is the extra round: it follows "The extra round" in `references/build.md`. It audits the new verdicts, writes `discover-work/audit-find-problems-2.md` and `.json`, applies both audits with `apply`, and rebuilds the whole list into `problems-audited.json` with `"extra_round": true`.

Then go to SKILL.md step 6, whatever the count. The extra round runs once; a list that is still short is shown with its honest note.
