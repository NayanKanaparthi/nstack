# Final independent review (2026-11-17)

Verdict: NOT READY, 4 blocking, all small. R3, R5, R7, R9, R10 pass. Round 3: B1 fixed, B3 fixed, B2 partly (outside-content route remains).

Blocking:
1. Firing-key rule refuses an honest per-item key (an order id saved before the firing) and its message steers to a slot-based key that double-posts when a catch-up overlaps. Fix: add an `item id` key part.
2. The record of actions can expire before a repeat arrives (kept 2 days, catch-up looks back 30). Fix: keep it longer than the catch-up and any retry window; checker compares the two.
3. A3 (how runs start) never goes to the reviewer, though a false "a person" switches off catch-up and the event tests. Fix: one reviewer question.
4. A store shown to the model can be filed as the Audit log with no flag. Fix: audit log never goes into a model call; flag those rows.

22 minor items (see the reviewer's report in final-review/). Dry runs: E (GitHub issue labeler) 79 lines, F (saves nothing) 40 lines, both clean first try.
