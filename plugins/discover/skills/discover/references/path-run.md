# The whole-path run

The student chose to run every step in order and be stopped only when they need to decide something (`mode: "path"` in `discovery.json`). This file tells the main conversation how to drive that run. Read `shared/rules.md` and `shared/card.md` first if you haven't.

## Order

| Step | Skill file | Runs when |
|---|---|---|
| Find problems | `<plugin root>/skills/discover-find-problems/SKILL.md` | `entry` is `"area"` |
| Frame | `<plugin root>/skills/discover-frame/SKILL.md` | always |
| Evidence | `<plugin root>/skills/discover-evidence/SKILL.md` | always |
| Stress test | `<plugin root>/skills/discover-stress-test/SKILL.md` | always |
| Interview plan | `<plugin root>/skills/discover-interview-plan/SKILL.md` | always |

`/discover-interview-sort` is not part of the run. It comes after the student's interviews.

## How to run a step

1. Re-read `discovery.json`. Find the first step in the order above that is neither `"done"` nor `"skipped"`. A step the student skipped by jumping ahead stays skipped in the run; the status names it, and they can run it any time. If that is Interview plan, first check point 6 (the evidence top-up).
2. Read that step's `SKILL.md` in full and follow it exactly, as if the student had typed its command. Each step still uses its own sub-agents and its own brief files, still checks evidence in a separate context, and still has each check audited by a fresh sub-agent (`<plugin root>/shared/audit.md`) before merging. When a step is `"running"` and this chat didn't search, read only that step's `SKILL.md`, never its researcher or miner briefs.
3. Every stop in that skill happens exactly as in the single command: ask its questions one per message, and wait for each answer. Never answer a stop for the student, never pick a default, never skip one to save time.
4. When the step finishes:
   - **It had a stop:** after the answers are recorded and the page is rebuilt, show that step's full card, with the last line `Next: <next step name>, starting now.` (no command to type; see `card.md`). The card ends that message. Then go straight on to the next step, starting a new message with its progress line.
   - **It had no stop** (Evidence): show no card. Evidence shows its short hand-over instead (one line per label, in a few words, and "The report and <n> links you can check are on your page.", or its zero form "The report is on your page. No links were suggested, because nothing was counted."; see `discover-evidence/SKILL.md` step 6), then the run goes on.
5. A progress line is one short sentence, such as "Starting the stress test." No quotes and no view on the idea. The Evidence hand-over is the only place in the run that repeats labels, in the renderer's words.
6. **After the stress test:** if an assumption a search can check is now riskiest but not in `evidence.run_on`, and not one the renderer lists as checked in Find problems, run the evidence top-up (`<plugin root>/skills/discover-evidence/references/top-up.md`) automatically, before the interview plan: research, a fresh check, a fresh audit of that check, then the merge. Its short hand-over gives the label of each new assumption, plus one line for each refreshed earlier assumption whose label changed (`"<a few words>": was <old label>, now <new label>.`). If any label changed, it adds: "The stress-test points on your page were written before this search." Then the run goes on.

## What to keep in the main conversation

Keep it short. Sub-agents write their full output to `discover-work/` and reply with counts. In the main conversation keep only: the student's answers, the counts each step reports, the progress lines and the cards. Don't paste sub-agent output, evidence or quotes into the chat. Before the separate check has run, never describe findings at all.

## When the run must pause for a new chat

If there is no tool for launching sub-agents, a step that gathers evidence (Find problems, Evidence, an evidence top-up) must be checked in a new chat, and the check must be audited in another new chat: the chat that searched never checks, and the chat that checked never audits. The step saves itself (as `"running"`, except a top-up, which leaves `steps.evidence` at `"done"`) and shows its new-chat card (see `card.md`). The run pauses there. In the new chat the student types `/discover`; the run sees the saved files and continues with the part that is missing: the check, the audit or the merge.

## The end

The run ends after Interview plan, with that step's normal card (send your first five messages now; after your interviews, run /discover-interview-sort). Nothing after it.

After that, there is nothing left to carry on with. If the student types `/discover` again, show the status and the status card (`discover/SKILL.md` B.3), exactly as in step mode. `/discover-interview-sort` is run by the student after the interviews.

## If the student types a command during the run

A command typed directly runs on its own, with its own card (`rules.md`, "Before a command starts", point 8). The run carries on from the first step neither done nor skipped the next time the student types `/discover`.

## If the run is interrupted

Nothing extra to do. Every step saves to `discovery.json` as it goes. When the student types `/discover` again, the run continues from the first step not done, as long as a step up to Interview plan is left. A step that was `"waiting"` picks up at its open question, without redoing its work.

## Never

- Never ask two questions in one message, or a stop question together with anything else.
- Never carry on past a stop because the answer "seems obvious".
- Never show a full card for a step that finished without a stop, except the last one.
