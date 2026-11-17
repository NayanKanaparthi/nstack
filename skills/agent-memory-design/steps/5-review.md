# Step 5: Review by a Claude that did not do the work

Whoever designed and built the memory system is the worst placed to check it. They remember what they meant, so they read the code as doing it. The check is done by a Claude that never saw the design conversation or the build.

This file has two readers. Part A is for the builder. Part B is for the reviewer.

## Part A: if you are the builder

Do not review your own work, and do not tell the person the work passes.

**If you can start a sub-agent** (a second Claude that sees only what you hand it; the tool is often called Task or Agent): start one. Give it only:

- the path to the project, which holds `MEMORY-DESIGN.md`,
- the path to this skill's folder, with the instruction to read `steps/5-review.md` Part B, `CHECKLIST.md`, and the list "Words these files use" at the end of `SKILL.md`,
- permission to read any file in the skill's folder.

Do not give it a summary of what you built, your reasons, or which parts you are unsure about. It should find those itself.

**If you cannot** (a normal chat): tell the person, in these words or close to them: "Open a new chat in the same project and type `review the memory design`. The reviewer will write its result into a file called MEMORY-REVIEW.md. When it has finished, come back to this chat and say so." Then stop. When the person comes back, read `MEMORY-REVIEW.md` from the project and carry on below. This path needs both chats to see the same project files. If the second chat cannot, ask the person to paste the reviewer's table back here.

When the review comes back, fix every line marked `no`. Fix the code or the design, never the checklist and never a test's strictness. Then have a fresh reviewer check again, the whole list, not only the lines that failed, because a fix can break something that passed.

Repeat until every line is `yes` or `n/a`. Only then tell the person it passed review, and show them the reviewer's table.

## Part B: if you are the reviewer

You are checking a memory system someone else built. Treat nothing as true until you have seen it yourself. If this conversation is the one that designed or built it, stop and say a separate chat has to do the review.

Read `CHECKLIST.md` and the list "Words these files use" at the end of `SKILL.md` first. You may read any other file in the skill's folder when a line needs it. Then work through the checklist line by line. For each line give `yes`, `no` or `n/a`, and the evidence.

1. **Run the checker with the project.** From the project folder: `python3 -B <path to this skill>/scripts/check_design.py MEMORY-DESIGN.md --project .` The script is in the skill's folder, not in the project. If it reports problems, the lines its tags point to are `no`. A clean run is not a `yes` for any line. You still read the design and judge it.
2. **Take the `n/a` lines from the checker, and only from it.** It prints "CHECKLIST LINES THAT CANNOT APPLY to this design" with a reason for each. Confirm each reason against the project, then answer `n/a`. If a reason is false (the script says the agent has no side effects and you find a function that sends email), the line is `no`, and so is the design line that was wrong.
3. **Answer every item under "FOR THE REVIEWER TO JUDGE".** These are the choices a script cannot verify: whether the outcome signal is real, whether a procedure marked harmless is, whether each key part is stored before the first try, whether A3 is true (search the project for timers, queues, webhooks or listeners that start runs without a person), whether a store filed as Audit log or Side effect protection ever reaches a model call, whether every action is listed, and every item that enters as confirmed. Judge each one against the code. A wrong one makes its checklist line `no`.
4. **Lines 1 to 8, the design.** Read `MEMORY-DESIGN.md` against the project. Is each reason about this agent? Is anything saved that section 3 does not list? Does anything read from outside get in as confirmed by another route?
5. **Lines 9 to 23, the code.** Run the tests yourself with the command on the first line of `_run/tests.txt` and read the output. Do not accept a report that tests pass. For every procedure marked `code`, open the function and read it. Then remove the rule for real, in a copy of the project, one clause of its Rule cell at a time, and run the tests: one must fail. A removal that another check still covers counts only when some input behaves differently without it. Do the same for every owner or scope filter in a read function. The builder's `_run/rule-removal.txt` shows what they did; do your own. A test that goes around the named function does not count for it. A rule whose Rule cell promises more than the code catches ("any number" when only digits are caught) fails too: a limit is accepted only when section 10 says the person accepted it. Judge a `person:` rule against its text in the design and section 10, not against what you think the person meant.
6. **Try attacks of your own.** Pick the rules whose failure would hurt most. Usually these are: outside content saved as confirmed, a side effect happening twice (two at once, a late firing, a repeat after a delete), one owner seeing another's data. Write a new test for each that the builder did not write, in the project under `tests/review/` (or the project's own test folder, in a `review` subfolder), with an empty `__init__.py` there when the test runner needs one to find the folder (Python's unittest does), and list them in `MEMORY-REVIEW.md`. Adding these tests is not fixing: change no other file. If one fails, the line it belongs to is `no`. (How many rules you pick is your call. Two or three is an arbitrary starting point.)
7. **Which line fails.** A failure counts against every line it breaks. A missing owner filter is `no` on line 9 for its procedure and `no` on line 15.
8. **Line 24.** Yes only if you are a separate Claude, every other line is `yes` or `n/a`, this is a full pass made after the last fix, and your attack tests are in `tests/review/` and listed in `MEMORY-REVIEW.md`.

You do not fix anything. You report.

Write the result into the project as `MEMORY-REVIEW.md` and show the same table in chat:

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Every memory type is marked build or skip with a reason | yes | Section 2. Reasons name the approval step and the Friday follow-up. |
| 10 | Expired items never come back on read | no | `get_facts` filters on `expires_at`, but `find_episode` does not. `test_expired_episode` does not exist. |
| 18 | No action happens twice and none is lost | n/a | The checker lists it: A4 says no side effects. Searched the code for calls that send, pay or post. Found none. |

Evidence for a `yes` is a file and function, a test name and its output. Evidence for a `no` is what you looked for and did not find, or the test that failed. Evidence for an `n/a` is the checker's reason and what you did to confirm it.

Hold every line to the same standard. A review that passes everything is as useless as one that fails everything. Be exact about what the code does and reasonable about wording.

End with one line: how many of the 24 are `yes`, how many `n/a`, how many `no`. If any are `no`, say the work has not passed.
