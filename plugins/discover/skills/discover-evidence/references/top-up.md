# The evidence top-up, after the stress test

This file is for the main conversation running `/discover-evidence` (or the whole-path run). It is not a sub-agent brief. "SKILL.md" below means `discover-evidence/SKILL.md` in this skill's folder; read it first, because the top-up reuses its steps.

## When it runs

`steps.evidence` is `"done"`, and an assumption is riskiest and searchable but not in `evidence.run_on` (the stress test made it riskiest), and it is not one the renderer lists as checked in Find problems (SKILL.md step 2). The top-up searches those assumptions only. In the whole-path run it happens automatically after the stress test, before the interview plan.

The renderer allows `run_on` to grow past 3 only this way: every id after the third must be riskiest and searchable.

## Steps

1. One line to the student: "Searching for the assumptions the web search hasn't looked at yet."
2. **Research.** Run SKILL.md step 3 with the same researcher brief, with the step name `topup-<n>` (n = 1, 2, ...) everywhere, so the log goes to `discover-work/log/topup-<n>/`. Launch one researcher per **new id only**, and give each **every id already in `run_on` for filing only**: an item it reads that also speaks to an earlier assumption is logged under that one too, on its own side. Don't change `steps.evidence`; it stays `"done"`.
3. **Check, then audit.**
   - Run `ledger --step topup-<n> --run-on <ids>` with the new ids, plus every earlier id the log filed items under. Then run SKILL.md step 4 with one fresh checker per id on its ledger (`evidence-topup-<n>-ledger-<id>.md`), with the step name `topup-<n>`. Also give each `shared/checking-rules.md` and `shared/calibration.md`, the current `evidence` section (the full path of `discovery.json`), every earlier checked-notes file (`evidence-checked.md` and any `evidence-topup-<k>-checked.md`) and, for an area entry, `problems-checked.md`. Each follows "A top-up check" in its brief: the same tests and option decisions as the earlier checks, earlier results kept for the same reasons, reused lines re-tested against their mirrors, and an earlier assumption's `still_open` and `not_found` lines rewritten when the new items make them untrue. Their notes go to `evidence-topup-<n>-checked-<id>.md`; join them into `evidence-topup-<n>-checked.md`.
   - Then `assemble --step topup-<n> --run-on <the same ids>`. It writes `discover-work/evidence-topup-<n>.json`, holding only this top-up's own `checked` numbers, unread pages, and new products, phrases and links, plus its results. For an earlier assumption it starts from that assumption's current result, applies the changed verdicts, adds the new items and adds the new unread pages, so its result is complete. Then run `pairs --step topup-<n>`.
   - Then run SKILL.md step 4b with a fresh audit sub-agent on it (clock phase `audit`, step `topup-<n>`): inputs as `shared/audit.md` lists for a top-up, output `discover-work/audit-evidence-<n+1>.md` and `.json`. Apply its corrections to the top-up json before merging, saving `evidence-topup-<n>-audited.json`; step 4 merges that file.
   - With no sub-agent tool, the same new-chat rules apply: the chat that searched never checks, and the chat that checked never audits. In a top-up, leave `waiting_on_student` empty (the renderer allows it only while a step is waiting or running); the new-chat card says what to do.
4. **Merge.** Rebuild the page once before merging: the renderer prints each earlier assumption's label, so note them. Then merge with a Python snippet:
   - Append the new ids to `run_on`.
   - For each result: if its assumption already has a result, replace that result (same place in the list); otherwise append it. A replaced result keeps the `unread` numbers the checker wrote for it (the earlier ones plus this top-up's).
   - Add the top-up's `checked` numbers and `unread_pages.count` to the earlier ones.
   - Add its `wouldnt_open` entries not already listed, while there are fewer than 3.
   - Add new products only while there are fewer than 4 and the link isn't already listed.
   - Add new `language` phrases not already listed, and suggested links only while there are fewer than 5.
   - Keep `checked_in_fresh_context: true`.

   Add a `log` entry ("top-up search on <ids>; refreshed <ids>"). Rebuild.
5. **Hand over** as in SKILL.md step 6: the label of each new assumption, plus one line for each refreshed earlier assumption whose label changed: `"<a few words>": was <old label>, now <new label>.` If any label changed, add one line: "The stress-test points on your page were written before this search." Step mode: then the card ("When you're ready" names the next command not done, usually `/discover-interview-plan`). Whole-path run: the short hand-over, then go on:

   ```
   Evidence done for the new assumptions.
   - "<a few words of assumption>": <label>
   - "<a few words of an earlier assumption>": was <old label>, now <new label>.
   The stress-test points on your page were written before this search.
   ```

   The last two lines appear only when a label changed.

## Resume

If a top-up's log exists (`discover-work/log/topup-<n>/`) and `evidence-topup-<n>-audited.json` doesn't, use the same cases as SKILL.md step 1, with `evidence-topup-<n>.json`, `audit-evidence-<n+1>.json` and `evidence-topup-<n>-audited.json`. Run the check, the audit, the corrections or the merge that is missing, unless this chat did the part before it; then show the new-chat card again.
