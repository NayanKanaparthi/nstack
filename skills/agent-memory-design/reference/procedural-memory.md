# Procedural memory

**In plain words:** the method the agent follows. The steps, rules and habits for doing a task. It is called memory because it keeps how the agent should work, as opposed to what it knows about a user. (video)

Examples: "Search internal documents before searching the web." "Check a database query before running it." "Ask a person before issuing a refund."

Procedures can live in four places: the main instructions, the text that describes a tool to the model, a reusable skill (a file of instructions the model loads when one kind of task comes up), or the code of the workflow. (video) The design question is which place, for each one.

**When to skip:** never. Every agent has instructions. What varies is how many procedures must be code, and whether the agent may suggest new ones.

## Questions

- P1. Which steps must happen, and in what order?
- P2. For each procedure: if the model skips it once, what happens?
- P3. Where does each one live: the main instructions, a tool's description, a skill, or code?
- P4. Who may add or change a procedure, and how are old versions kept?
- P5. May the agent suggest new procedures from past runs? Only if episodic memory is `build` and the person said yes. If nobody answered, no. If yes: how many episodes with the same lesson first, who approves, and how is a bad one switched off?

## Defaults

### Instructions or code

For every procedure, ask P2 and pick one answer from this list. (ours)

- `harmless`: the worst result is a poorer answer that stays inside the system. It can be **instructions**: text the model reads and usually follows.
- `costs money`, `sends something out`, `cannot be undone`, `leaks data`, `corrupts memory` (something false or unchecked gets saved, or shown to the model as true), or `misses a promised action` (something a person relies on silently does not happen): it is **code**. The function refuses, whatever the model asks for.

Three ways to put a procedure in code, strongest first: (ours)

1. **Take the tool away.** If the agent must never issue refunds, do not give it a refund tool. Nothing to skip.
2. **Do the step in code, before the model runs.** If the order must always be looked up first, the function that builds the model call looks it up. The model never has to remember to.
3. **Put a check inside the function.** `send_email` refuses unless an approval exists for that exact email.

> "Use a friendly tone." Skipped once: a slightly stiff reply. `harmless`, so instructions.
> "Do not send until staff approve." Skipped once: an email goes out that cannot be taken back. `sends something out`, so code.

A procedure in code that protects an action with a side effect is that action's guard. `reference/side-effects.md` covers guards.

### New procedures from past runs

Only if P5 is yes. Turning a note about one run into a rule for every run is the riskiest step in a memory system, because a rule changes every future run.

- **What is counted.** A procedure is suggested when 3 separate saved episodes carry the same lesson, and no saved episode goes against it. Separate means different runs on different inputs. Episodes are only saved when a run teaches something, so in practice this counts corrections and failures that point the same way. The 3 is arbitrary and no source we read gives a number of episodes. Tell the person and let them set it. (ours)
- **Who says two lessons are the same.** A background job has the model group episodes whose lessons mean the same thing, and code counts the separate runs in each group. The model suggests the grouping. The count, and the rule that a suggestion is only a suggestion, are code. (ours)
- **Never automatic.** Suggestions are kept apart from live procedures and are never loaded as procedures. (source: Konishi guide, which keeps drafted procedures apart from live ones and lets them go live only through a check)
- **A person switches it on.** They read the suggested text, or the change to the existing text, and approve it. (ours. The Konishi guide accepts any one of three checks: running the procedure again in a safe setting, seeing it work on several separate occasions, or a person's review. We require the person every time, because of a result reported in arXiv 2605.22148: procedures curated by people helped, and ones the model wrote for itself with no check did not.)
- **For a procedure that will be code or that guards a side effect:** a count is not enough. It is run again against saved episodes or tests in a safe setting, and then a person approves it. (source: Konishi guide for that check; requiring it here is ours)
- **After it is live, its own results decide whether it stays.** Every live procedure has a version number and keeps a count of the runs that followed it and ended well, and the runs that followed it and failed or were corrected. It can be switched off, and old versions are kept. (source: Konishi guide for versions; arXiv 2605.22148 for retiring a procedure by its results)
- **A limit on how many are live.** A growing library of self-written procedures can stall the agent or make it worse. (source: Library Drift paper, arXiv 2605.19576) The limit is arbitrary.

### Where each kind is kept

- **Instructions and tool descriptions you write** live in files in the project, under version control (git or whatever the project uses to keep the history of its files), so every change has a history. A person saves each change to that history. (ours)
- **Procedures learned from episodes** live in a table: the text, a version number, live or switched off, the counts. The approve step writes a new row. It does not edit files. The function that builds the model call loads the live rows and adds them to the instructions. (ours)

## Code to build

- **The instructions and tool descriptions**, holding the procedures that passed as instructions.
- **The checks inside functions**, for procedures that are code. Each one is a named function a reviewer can point to.
- **The tool list**, with tools the agent must not have left out.
- If the agent may suggest procedures:
  - a table for suggested and learned procedures: the text, the episodes behind it, the count of separate episodes, any episode against it, status (`suggested`, `live`, `switched off`, `rejected`), a version number, and the success and failure counts;
  - a timer job that reads new episodes, groups those with the same lesson, and creates or updates suggestions;
  - an approve step for a person, which writes a new version of the live procedure and keeps the old one;
  - a switch-off.

## Tests that try to break it

- For every procedure in code: call the function in a way that breaks the rule. It must refuse. Then remove the check from the function, for real in a copy, and run the test: it must fail. If it does not, the test is not testing the rule. When two procedures stop the same harm, each needs a test that fails with only that one removed; if none can, the design names them as one guard. `steps/4-build.md` says how to record this.
- Ask the model, in a test conversation, to do the forbidden thing (send without approval, issue a refund). The action must not happen, because the code stops it, not because the model declined.

The rest are the standing test "A procedure is suggested only at the set count and is not live before approval":

- Create a suggestion backed by 2 episodes when the count is 3. It must not be offered for approval.
- Create a suggestion backed by 3 episodes, with 1 episode against it. It must not be offered.
- Back a suggestion with 3 episodes from the same run, or the same input. It must not be offered.
- Approve a suggestion. The live procedure gets a new version and the old version still exists.
- A suggested but unapproved procedure must never appear in a model call. Approve it: it appears. Switch it off: it is gone.

## In the design file

- Section 4: one row per procedure you write, with what happens if the model skips it once (one of the seven fixed answers), `instructions` or `code`, where it lives, which actions it guards, and its test.
- Section 3, only if the agent may suggest procedures: one row under Procedural memory for suggested and learned procedures, with the source `agent worked out`, entering as `unconfirmed`. A procedure learned from episodes is a row in that table, not a row in section 4.
- Section 4, then: the line `- Episodes before a procedure is suggested: 3 episodes`. The number is the one the person set, or the starting value. With no episodic memory there is nothing to count: write `none: <why>`, and a person writes each procedure.
- Section 9, only then: "A procedure is suggested only at the set count and is not live before approval".
- Section 10: the count of episodes and the limit on live procedures, each with its source in square brackets. Both are starting values: `[default: the share of suggested procedures the person rejects]` for the count, `[default: how often the limit is reached]` for the limit (`reference/every-store.md`).
