# Reviewing an agent that already exists

Here the agent is already built, by someone else, without this skill or before it. Your job is to find out what memory it actually has, check that against `CHECKLIST.md`, and tell the person what is missing, worst first. You read and you report. You change nothing in the project except the two files this step writes.

## 1. When this is the path

Take this path when all three hold: the agent already exists, its code already saves or reads memory, and the person asked you to review, audit or check that memory. They did not ask you to add memory or change it.

- If they ask you to review, audit or check the memory of an agent that already exists, that is this path.
- If they hand you a `MEMORY-DESIGN.md` written with this skill and ask you to check it, that is `steps/5-review.md`, not this path.
- If they ask you to add memory to an existing agent, or to change the memory it has, that is steps 1 to 5.

One rule carries over from step 5. If this conversation designed or built the agent's memory, you are the wrong reviewer: say that a fresh chat has to do the review, and stop.

The project may already hold a file called `MEMORY-DESIGN.md` or `MEMORY-GAPS.md`. Do not write over it. Ask the person where to write instead, and use that name in every command below.

## 2. Read the code

Read before you write anything. Look at:

- The README, any spec or plan, and the conversation so far.
- The main instructions the model is given (often called the system prompt), and the list of tools the model may call.
- Every table and every file the agent writes, with their columns (the schema), and anything else that keeps state between runs.
- Every function that writes one of them, and every function that reads one.
- The one place model calls are put together, or every place if there are several.
- Every call that reaches outside the system: send, pay, post, delete, write to another app.
- Everything that runs on a timer, from a queue or when a webhook arrives (another app calling the agent's web address).
- Where numbers live: in configuration (a settings file, a config module, a settings table), or written into the functions that use them.
- The tests, and how the project runs them.

Run the tests the way the project runs them and keep the output, because it is evidence. If running them writes files into the project (a test database, a cache), run them in a scratch copy of the project instead, outside it.

## 3. Write the design as built

Copy `assets/memory-design-template.md` into the project as `MEMORY-DESIGN.md`, with the title `# Memory design: <name of the agent> (as built)`. Every cell and every line says what the code does today. Not what it should do, and not what is usual.

Write a place in the code as the file and the line joined by a colon, like `agent/mail.py:88`. The checker does not read that as a number of the design. Written as "line 88" in a cell, it can.

**What the code does is written as it is, even when it is wrong.** A key with a random part is written with that part, and its Key parts cell says so.

> Good: `send-{attempt_uuid}` in the Idempotency key cell, and `attempt_uuid: random, made by uuid4() in send_email() on every try` in Key parts.
> Bad: `send-{message_id}` with `message_id: stored id`, because that is what the key should be.

**Something the code does not have is written `not in the code: <what you searched for>`.** A procedure with no test has that in its Test cell. A store nothing ever empties has it in its Expiry cell. A row in section 9 lists the tests that exist; when a case has none, the checker counts the shortfall and lists it.

> Good: Expiry: `not in the code: searched every write to the notes table and the nightly job for a delete or an end date, found none.`
> Bad: Expiry: `90 days after the run.` (when nothing in the code says so)

**Something you cannot tell from the code is written `unknown: <what you looked for and where>`.** Never fill it in with a guess, with what is usual, or with what it should be.

> Good: `- An approval lasts: unknown: read from APPROVAL_TTL, which is set outside the repo; searched the repo and its config files.`
> Bad: `- An approval lasts: 24 hours` (a common value, when nothing in the project gives one)

**A1 to A8 end `(worked out)`** when the code or the project's own documents show the answer. They never end `(assumed)`, and the checker refuses it here: an answer nobody can read from the project is `unknown: ...` and ends `(worked out)`. A2, A3, A4 and A5 start with their fixed value (`steps/1-understand.md`, section 2), the one the code shows, because the rest of the file is switched on or off by them. What is unclear about them goes after the full stop, and into the gap report's list of what is not known (section 6 below). The same holds for each Decision in section 2, each row's Memory type, Source and Enters as in section 3, each procedure's If skipped once and Lives in in section 4, each action's Needs approval and Content it carries in section 5, and each Method in section 6: the code always shows them, so none of these is `unknown`, and the checker refuses it there.

> Good: `- A5 Outcome signal: no. The code records no approve, edit or reject on anything the agent writes. (worked out)`
> Bad: `- A5 Outcome signal: yes. Users would complain if it were wrong. (assumed)`

**The file always has the line A9,** with `none` when none of the four holds, so the lines added in v0.2 are checked. Like A2 to A5, it starts with what the code shows.

> Good: `- A9 Also true of this agent: none. Nobody waits on a reply, one function writes facts, no model writes facts, and no volume is stated. (worked out)`
> Bad: no A9 line, because the agent was built before v0.2.

**Section 10 lists every number found in the code or its configuration,** each with its source by the table in `reference/every-store.md`. A number written into code and not read from configuration gets `[default: not in the code: no measure is recorded]` or `[policy, not told yet]` by that table, and the line says "written into the code at <file>:<line>". A policy number read from configuration, where nothing in the project records who chose it, is written `[policy: unknown: <where it is set, and that nothing records who chose it>]`, and goes in the list of what is not known. In the same way, when the code does not show whether a default's measure is recorded, or which query a data number comes from, write `[default: unknown: <why>]` or `[data: unknown: <why>]`: the checker lists it as could not be checked.

> Good: `- 15 minutes for which a claimed send is held, written into the code at agent/mail.py:88. [default: not in the code: no measure is recorded]`
> Bad: `- 15 minutes for which a claimed send is held. [default: sends taken over while the first run was still working]` (when the code records no such measure)

## 4. Run the checker in as-built mode

From the project folder:

```
python3 -B <path to this skill>/scripts/check_design.py MEMORY-DESIGN.md --as-built --project .
```

The script is in the skill's folder, not in the project. It reads no code: it checks the file. Only the two files may be written in the project, so keep what it prints in the gap report, under its heading "The checker's output": the command, the RESULT line and the lists. What it prints:

- **PROBLEMS**: faults in the file itself, such as a heading it does not know, a missing A9, a title without "(as built)", an answer ending `(assumed)`, an `unknown` or a `not in the code` with no reason, an `unknown` in a cell the code always shows, or a test the file names that the project does not define. Fix the file, not the code, and run it again. Only these make it exit with 1.
- **WHAT THE FILE SHOWS IS MISSING OR DOES NOT AGREE**: what the file, read as the code today, lacks or gets wrong. A number written into the code with no measure is listed here too, under line 25. Each item under WHAT THE FILE SHOWS is a candidate gap. Confirm it in the code before you list it. When the code does what the checklist line asks and only the file's wording was off, fix the file and run the checker again.
- **COULD NOT BE CHECKED**: a problem on a line that holds a value marked unknown. The script files a whole line together, so the problem may come from another cell on that line: read the rest of the line yourself.
- **MARKED UNKNOWN**: every line with an `unknown:` value. Each goes in the list of what is not known.
- **CHECKLIST LINES THAT CANNOT APPLY** and **FOR THE REVIEWER TO JUDGE**: as in step 5. Confirm each n/a reason against the project, and answer each item against the code.

## 5. Answer every checklist line

Each line of `CHECKLIST.md` gets `yes`, `no`, `unknown` or `n/a`, with evidence: a file and line, or a test name and what it showed when you ran it.

- `n/a` comes from the checker's list, as in step 5, once you have confirmed the reason against the project.
- `unknown` is for a line the code does not settle either way. Say what would settle it.
- Line 24 is `n/a` in this path: nobody built from this design.

Do for the code what the reviewer in `steps/5-review.md` Part B does, with two differences: you answer `unknown` when the code does not settle a line, and you add no tests to the project. Where Part B runs the command on the first line of `_run/tests.txt`, run the tests the way the project runs them. You may run a check in a scratch copy of the project to see what happens, such as firing a timer twice. Say in the evidence that you did. When you remove a rule the code enforces and no test fails, line 9 is `no` for that rule, but the code works today: section 6 lists that gap as "works today, untested".

## 6. Write the gap report

Copy `assets/gap-report-template.md` into the project as `MEMORY-GAPS.md`. It has two tables, a list, and the checker's output from section 4.

The first table is the checklist, one row per line, as section 5 answered it.

The second table lists the gaps. A gap is one thing the code does or lacks that makes a checklist line `no`. Each has:

- **Gap**: one sentence saying what happens, in plain words.
- **Line**: the checklist line or lines.
- **Applies because**: the property of the agent that makes the line apply. The trigger in words (someone waits live for the answer; it schedules work for later from saved state; and so on), or the v0.1 condition, such as "it has an action with a side effect".
- **If it bites once**: one of the "if skipped once" values, then what that means here.
- **Where**: the file and line that show it. For something missing: what you searched for and where, with the result.
- **Fix**: the smallest change that closes it, and the test that would show it closed.

Order the gaps by the "If it bites once" value, in this order: `cannot be undone`, `costs money`, `leaks data`, `sends something out`, `corrupts memory`, `misses a promised action`, `harmless`. Within one value, by checklist line. The order of the values is our own choice (ours), and the person may reorder it.

A rule the code enforces today, with no test that fails when it is removed, is a gap too, but it comes after every gap the code has today, whatever its value. Its "If it bites once" cell starts `works today, untested:`, then the value its rule would have. These are ordered among themselves the same way.

What may be listed:

1. A gap needs a place. No file and line, and no search that came back empty, means no gap.
2. One cause is one gap, even when it breaks several lines. All the lines go in its Line cell.
3. An `unknown` is not a gap. Unknowns go in the list under the table, each with what would settle it.
4. A difference from this skill's defaults that breaks no checklist line is not a gap: a different starting value, a different name, another way to do the same job.
5. Nothing is changed in the project besides the two files, unless the person asks. No test is added and no code is touched.

## 7. Tell the person, and what happens next

Tell them in chat: how many gaps you found, the worst three in a line each, taken from the gaps the code has today before any marked works today, untested, and ask which they want fixed. Change nothing until they say.

The fixes they pick go through steps 3 and 4. The design file is changed to say what the code should do for those parts, and it loses "(as built)" in its title once it is the design being built from. Then the code and its tests are built, and step 5's separate reviewer checks the result. Gaps they leave open stay in the file as they are, so the checker still lists them and step 5's review answers those lines `no`. An as-built design with open gaps is an honest record of the code, not a passed design. Tell them that before they choose.
