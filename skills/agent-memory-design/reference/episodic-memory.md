# Episodic memory

**In plain words:** a store of short notes about specific past runs. One note, called an episode, covers one run: the task, what the agent did, how it ended. When a similar task comes in, the app finds the most relevant episode and shows it to the model. (video)

Example: semantic memory holds "this customer prefers email". Episodic memory holds "in the last late-delivery case the agent promised a delivery date, staff removed it because the carrier had not given one, and the customer was fine with the corrected reply".

An episode is a short note, not the whole record. The whole record is the run log, which every agent keeps and which `reference/every-store.md` describes. (video says a short episode; calling the full record a log is ours)

**When to skip** (you decided this in step 2):

- **No outcome signal.** If the agent cannot tell whether a run went well, skip episodic memory. A saved run that nobody checked teaches the agent to repeat whatever it did, good or bad. This is a hard rule. (ours)
- **Tasks do not repeat.** If each task is one of a kind, there is nothing similar to find later. (ours)

A weak outcome signal is close to none. An agent grading its own run works where success is obvious, like a test that passes or fails. It is not enough where being right is a matter of judgment, such as whether an audit finding was correct. There, use a person's decision or a check against a trusted record. (source: Bean Labs log on Voyager)

## Questions

- E1. What counts as one run?
- E2. Which runs are kept as episodes?
- E3. What goes in the episode, and which parts does code write?
- E4. What makes a new task "the same kind" as an old one, so the right episode is found?
- E5. How long are episodes kept?
- E6. How many episodes are shown to the model at once?
- E7. May the agent suggest new procedures from its episodes? Only if the person said yes. See `reference/procedural-memory.md`.

## Defaults

- **Write the episode after the run ends, once the outcome is known.** A background job does it. Never in the middle of a run. (source: Neo4j write-up, which writes episodes in the background once feedback has arrived)
- **Keep a run as an episode only if it teaches something.** One of: it failed, a person corrected it, it hit an error and recovered, or it was the first run of a new kind of task. An ordinary success saves no episode. If it followed a live learned procedure, it adds one to that procedure's count of successes. (ours, not yet tested on a real agent)
- **What an episode holds, and who writes each part.** (ours)
  - Written by code, from the run log and the outcome signal: the kind of task, the outcome, how the outcome is known, whether a person corrected it, the date, the owner and scope, a link to the run log, a link to the previous episode of the same kind.
  - Written by the model: a one-line description of the task, a short list of what was done, and the lesson in one sentence ("do not promise a delivery date the carrier did not give").
- **The episode writer is the one job that reads the run log.** It hands the run to the model to write the note. So when episodic memory is built, the run log holds content: `Run log holds content: yes`. The note is then checked and saved under the rules below. The run log itself never goes into a later model call. (ours)
- **The model-written part is treated as unconfirmed.** Its source is `agent worked out`. It is never shown to the model as a fact or as an instruction. It is shown as content to read, inside a block labelled as a note about a past run. (ours)
- **An episode carries no text copied from outside content.** A run reads emails, web pages and tool results. If a sentence from one of them rides into the episode, text nobody checked reaches every later run. So the episode writer compares the model-written part with the outside content logged for that run and refuses a note that copies a run of words from it. Default: 8 words in a row. The 8 is arbitrary, and a shorter planted phrase can still get through, which is why the note is only ever shown as content to read. On a refusal, ask for the note once more, and if it still copies, save the episode with the parts code wrote and no note. (ours)
- **Show one episode.** The most similar one, of the same kind, for the same owner or a shared scope. (video shows one; making it the default is ours)
- **An episode is evidence, not an instruction.** Present it to the model as "here is what happened last time", not "do this". One past success is not a rule. (ours)
- **Episodes expire.** Longer than the run log, but not forever. The number is arbitrary. (ours)
- **Do not copy private details across owners.** If episodes are shared across users (one shop's support cases), the episode holds the lesson and leaves out the other person's details. (ours)

## Code to build

- **`write_episode(run_id)`.** Runs after the outcome is recorded. Decides whether the run is kept, by the rule above. If it is, writes the episode. If not, and the run followed a live learned procedure, adds one to that procedure's count of successes.
- **An episodes table.** The fields above, with the kind of task and the lesson, used for finding and for grouping.
- **`find_episode(request, owner)`.** Returns the most similar episode of the same kind that this owner is allowed to see, not expired. One by default. It filters first (kind, owner, scope, date) and ranks by similarity second.
- **A cleanup timer job** for expired episodes and their copies in the search index.

Sketch, to adapt:

```python
def write_episode(run_id):
    run = run_log.load(run_id)
    if run.outcome is None:
        return                                   # outcome not known yet: do nothing
    teaches = (run.outcome == "failed" or run.corrected_by_person
               or run.recovered_from_error or not episodes.exists(kind=run.kind))
    if not teaches:
        if run.procedure_id:
            procedures.add_success(run.procedure_id)   # ordinary success: just count it
        return
    note = model_writes_note(run)                # task in one line, what was done, the lesson
    if copies_outside_text(note, run.outside_content, words_in_a_row=8):
        note = model_writes_note(run, warn=True)
        if copies_outside_text(note, run.outside_content, words_in_a_row=8):
            note = None                          # keep the parts code wrote, drop the note
    episodes.insert(kind=run.kind, outcome=run.outcome, outcome_source=run.outcome_source,
                    corrected=run.corrected_by_person, owner=run.owner, scope=run.scope,
                    log_ref=run_id, previous=episodes.latest(kind=run.kind),
                    note=note, expires=now() + EPISODE_RETENTION)
```

## Tests that try to break it

The first five belong to the standing test "An episode is written only after the outcome, only when it teaches, and carries no outside text". Its counted cases are the first, second and fourth.

- A run with no outcome yet. No episode is written.
- An ordinary success. No episode is written. If it followed a live learned procedure, that procedure's success count goes up by one.
- A run a person corrected. An episode is written and it records the correction.
- Put an unusual sentence of ten words in an email the run reads, and have a person correct the run. Search episodes. The sentence is in none of them.
- Build a model call that includes an episode. The episode sits inside the block for content to read, not among the facts or the instructions.
- A new request from user A. `find_episode` never returns an episode that only user B may see.
- An expired episode. It never comes back, cleanup or no cleanup.
- Delete a user's data. Their episodes are gone, and shared episodes no longer contain their details.

## In the design file

- Section 3: a row for episodes under Episodic memory, with the source `agent worked out`, entering as `unconfirmed`, and a scope that says they are shown only as a note about a past run.
- Section 4: a procedure row, marked `code`, for writing an episode only after the outcome, with its test.
- Section 6: a row for finding a similar past episode.
- Section 9: "An episode is written only after the outcome, only when it teaches, and carries no outside text".
