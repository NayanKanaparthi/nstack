# Step 4: Build it

Build what the design says, in the project's own programming language and database, with tests. The design is the plan. If building shows the design is wrong, change the design file first and then the code, so the two never disagree.

## 1. Use what the project has

- The database the project already uses. If there is none, the simplest one that fits. For many small agents that is SQLite, a database that lives in one file, or Postgres, a common database server, if the project already planned to use it.
- The scheduler the project already uses, if the design needs one (section 4 has the line `What wakes the app`). If there is none, a timer job: cron, or the platform's own. With future tasks, the same timer job checks the tasks table every minute. (Every minute is an arbitrary starting value.)
- No new product unless the simple version cannot do the job. A durable execution product (Temporal, Restate, DBOS, Inngest) starts to earn its place when one task has many steps spread over days, or many side effects that each need to survive a crash. That threshold is our judgment. Tell the person before adding one.

The function names in the reference files (`save_fact`, `get_facts`, `build_context`, `write_episode`, `find_episode`, `on_wake`, `run_action`) are examples. Use names that fit the project. The code sketches there are patterns to adapt, not a library to copy in.

## 2. Build only what the design has

Build each layer below only if the design has it. Each layer rests on the one before it.

1. **Stores.** One table or file for each row in section 3 of the design, with every column the design names: owner, scope, expiry, source, status. A value that is the same for every row of a store (every row of the run log has the source `system record: the app`) may be a constant in the code instead of a column. A value that can differ between rows is a column. The run log is always there. The audit log is there when anything besides the run log is saved, and it comes first, because every later function writes to it.
2. **Write functions.** One function per store that everything goes through, such as `save_fact`. The entry rules live here: refuse items with no owner or scope, refuse secrets, set the source from how the text arrived and never from what the model says, save outside content as unconfirmed, replace or merge instead of storing twice, enforce the size limit.
3. **Read functions.** One per store, such as `get_facts`. They filter on every call: this owner, this scope, confirmed only, not expired, not replaced. Nothing else reads the tables directly.
4. **The context builder.** One function that puts each model call together in a fixed order and trims it when it is too big. Every agent has this one.
5. **Protection on side effects.** Only if section 5 has an action. The approvals table and the check for an approval, the function every action is passed through (it attaches the idempotency key and stops a repeat), the job or the person that picks up an unfinished action, and the tool list with any tool the agent must not have left out. Build this before the first action can reach outside the system.
6. **What wakes the app.** Only if section 4 has the line `What wakes the app`: the timer job, queue or listener it names, and the catch-up for missed firings when the design has one. With prospective memory, also the wake function for tasks.
7. **Background jobs.** Only the ones the design needs: the episode writer that runs after the outcome is known, the cleanup job, the job that groups episodes with the same lesson and suggests procedures, the job that returns stuck tasks to `pending`.
8. **Instructions.** Now write the text the model reads: when to call the memory tools, how to treat what comes back, and the procedures that passed as instructions. Written last, because by now you know what the code already enforces and the instructions do not need to repeat it as a plea.
9. **Tests.** See below. Write each test right after the piece it attacks if that suits the project. They are listed last here only because they depend on everything above.

Build nothing for a memory type marked `skip`, and nothing for a section the design leaves out. No empty tables "for later". For the smallest agent (see `steps/2-decide.md`) the whole build is layer 4, a run log that holds no content, and their tests.

## 3. Tests that try to break it

Every procedure marked `code` in section 4 and every row in section 9 of the design gets a test, under the name the design gives. A test here is an attempt to get past the rule, not a demonstration that the normal case works.

> Weak: "save a fact, read it back, it is there."
> Strong: "save a fact that expired yesterday, do not run cleanup, read facts: it must not come back."
> Strong: "approve email A, then try to send email B with A's approval: it must be refused."
> Strong: "send an email, stop the app dead before it records that it sent, start it again: exactly one email was sent."
> Strong: "stop the app dead after it claims the task and before it calls the mail service, wait, start it again: exactly one email was sent, not zero."

Rules for the tests (read `CHECKLIST.md` first: it is what the reviewer checks):

- Use the real functions. Do not test a copy of the logic. A test that goes around the function a procedure names does not test that procedure.
- For side effects, use two fake outside services that count calls: one that honours idempotency keys the way the real one does, and one that ignores them and does every call it gets. Most tests run against the second, so they show that your own code stops a repeat, not the service. Assert on the count.
- When two guards stop the same harm (a task claim and an idempotency key), each needs a test that fails when only that guard is removed, such as counting drafts for the claim and sends for the key. If no such test exists, the design names them as one guard.
- Give each rule data that only that rule would stop. If something earlier already drops it (a fake that filters by status, a fixture with no second owner), the test passes with the rule gone. To test an owner filter, the other owner's item must match every other condition.
- If a test fails, fix the code. Never loosen the test, never make the code treat the test's input as a special case, never skip it. Tests in `tests/review/` are the reviewer's: never delete or edit them.
- Retrieval gets its own test set: a list of questions where the right result is known in advance, scored on whether the search function returned it. This runs apart from any check of the agent's final answer, because a confident answer does not show that the right thing was found. (video)

Run the whole set of tests and save the output as `_run/tests.txt` in the project, with the exact command on its first line. The reviewer runs the same command.

**The rule-removal check.** For every procedure marked `code` in section 4, and every owner or scope filter in a read function: in a copy of the project, remove the rule from its function (delete the check, return early), run the tests, and note which test failed. A Rule cell that names several things it catches is several rules: remove each clause on its own. A removal that another check in the code still covers counts only if some input then behaves differently; if none does, write the input you tried. Save one line per removal in `_run/rule-removal.txt`: the procedure, the clause, what you removed, the test that failed. A rule whose removal no test catches is a failed build: write the test that catches it, then check again. The reviewer repeats this for real.

## 4. Keep the design file true

When a piece is built, replace its planned place in the design file with the real one: file and function for each procedure in code, test name and file for each test. Then run the checker with the project, which confirms that every test file named in the design exists and holds that test name:

```
python3 -B <path to this skill>/scripts/check_design.py MEMORY-DESIGN.md --project .
```

## 5. What you say when you finish building

Say what was built and that it is ready for review. Do not say it is done, correct or complete. That is the reviewer's call. Now read `steps/5-review.md`.
