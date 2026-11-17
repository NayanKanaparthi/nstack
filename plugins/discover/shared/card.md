# The end card

Every command ends with this card and nothing after it. Put it in a fenced `text` code block so the line breaks survive in chat.

```text
✓ <Step name> done
  <What this step produced, one or two lines, with counts.>
  Full results: open discovery.html, section "<page section>".

  Your call: <anything still optional, or "nothing to decide here">

  When you're ready: /<next command>
```

Rules:

- **Point to the page.** The chat only summarises; the page holds everything. Every step card has the "Full results" line, with the section the step fills: Find problems "Problems found", Frame "Your assumptions", Evidence "What the web says", Stress test "Stress test", Interview plan "Interview plan", Interview sort "What people said". The Start card, the status card, a new-chat card, and a card shown before the step has any results (such as interview sort's "Nothing sorted yet") leave it out.

- **Stops come before the card.** At a stop, ask the decision first, one question per message, and wait for the answer. A message that asks a question ends with that question, never with a card. Only after the student's answers are recorded and the page is rebuilt does the card appear.
- **"Your call" never asks a question.** It names something still optional (for example "open the 5 suggested links while you read, or trust the check"), or says "nothing to decide here".
- **"When you're ready"** names the next command from the flow below. After a command that jumped ahead, it names the step after this one, never a skipped step.
- **Skipped steps.** When Evidence, Stress test or Interview plan is `"skipped"`, "Your call" names them as optional, for example "optional: you skipped Evidence and Stress test. Run /discover-evidence or /discover-stress-test any time."
- Nothing after the closing fence. No sign-off, no extra tip, no question.
- Counts, not judgements. "6 problems, 2 to 5 sources each", never "6 strong problems".
- **Zero counts read naturally.** Never fill a count line with 0 ("0 links you can check"). Write the zero as a word ("none rejected", "no links were suggested"), or leave that part out. Each skill gives the zero form of its own count lines. One of something is singular ("the 1 suggested link").
- Plain words, sentences under 25 words, no em dashes (verbatim quotes keep their own), no internal words (see `rules.md`). An assumption id never appears without its statement.

## Step names and the flow

| Command | Step name in the card | Next command |
|---|---|---|
| `/discover` (new file) | Start | `/discover-find-problems` for an area, `/discover-frame` for an idea |
| `/discover` (file exists) | Status check | the command that resolves what's waiting, or the first step not done |
| `/discover-find-problems` | Find problems | `/discover-frame` |
| `/discover-frame` | Frame | `/discover-evidence` |
| `/discover-evidence` | Evidence | `/discover-stress-test` |
| `/discover-stress-test` | Stress test | `/discover-interview-plan` |
| `/discover-interview-plan` | Interview plan | special last line, below |
| `/discover-interview-sort` | Interview sort | no command, below |

Flow: `/discover` → (area only: `/discover-find-problems` → pick) → `/discover-frame` → `/discover-evidence` → read the page → `/discover-stress-test` → `/discover-interview-plan` → send messages → interviews → `/discover-interview-sort`.

## A step with a stop

1. Do the step's work. Save it with the step set to `"waiting"` and `waiting_on_student` naming the decision. Rebuild the page.
2. Ask the decision: one question per message, and wait. If the stop needs several answers (for example `/discover-frame`: first the assumptions, then the kill criteria), ask them one after another, each in its own message.
3. Record each answer as it comes. When the last one is in, set the step to `"done"`, empty `waiting_on_student`, rebuild.
4. Show the card.

If the student leaves in the middle of a stop, the saved `"waiting"` state lets `/discover` report it and the step's command pick up at the open question.

## A step without a stop

Do the work, save, rebuild, show the card.

## A step that must finish in a new chat

When there is no sub-agent tool, the check for `/discover-find-problems` and `/discover-evidence` must run in a new chat, and so must the audit of that check. Save the step as `"running"` (an evidence top-up keeps `"done"`) and show the card: the produced line says what was collected and that it is not checked yet, or that it is checked and one more fresh chat compares how every item was judged; "Your call: nothing to decide here"; "When you're ready: /<same command>, typed in a new chat in this same folder".

## Special last lines

After `/discover-interview-plan`:

```text
✓ Interview plan done
  <what was produced, with counts>
  Full results: open discovery.html, section "Interview plan".

  Your call: nothing to decide here

  When you're ready: send your first five messages now. After your interviews, run /discover-interview-sort
```

After `/discover-interview-sort` (no next command):

```text
✓ Interview sort done
  <interviews sorted, facts found, pass marks met and not met yet, as the renderer printed them>
  Full results: open discovery.html, section "What people said".

  Your call: nothing to decide here

  When you're ready: bring your page (discovery.html) to Session 2
```

## The status card

Used by `/discover` when the file exists, and by `/discover-find-problems` when it can't run on an idea entry:

```text
✓ Status check done
  Done: <steps done, by name, or "nothing yet">. Skipped: <skipped steps, or leave this part out>. Waiting on you: <waiting_on_student, or "nothing">.

  Your call: nothing to decide here

  When you're ready: /<command that resolves what's waiting, or the next step>
```

The waiting decision is asked by that command when the student runs it, one question at a time, not in this card.

## In a whole-path run

- Between steps: one short progress line, such as "Evidence done. Starting the stress test." No card.
- A step with a stop: ask the stop's questions as above. After the answers are recorded and the page is rebuilt, show that step's full card, with the last line `Next: <next step name>, starting now.` in place of "When you're ready". It names no command: there is nothing to type, because the run starts that step itself. The card ends that message. Then go straight on: the next step starts in a new message, with its progress line.
- A step without a stop shows no card: only the progress line.
- The run ends after `/discover-interview-plan` with that step's normal card.

## Examples

After the student picked a problem:

```text
✓ Find problems done
  6 problems found and checked, from 3 to 7 people or sources each. You picked: "Renters wait weeks to get their deposit back."
  Full results: open discovery.html, section "Problems found".

  Your call: nothing to decide here

  When you're ready: /discover-frame
```

The same card in a whole-path run:

```text
✓ Find problems done
  6 problems found and checked, from 3 to 7 people or sources each. You picked: "Renters wait weeks to get their deposit back."
  Full results: open discovery.html, section "Problems found".

  Your call: nothing to decide here

  Next: Frame, starting now.
```

A step with no stop:

```text
✓ Evidence done
  3 assumptions checked: "Too little to tell" for 2, "People are split" for 1.
  Full results: open discovery.html, section "What the web says".

  Your call: optional: open the 5 suggested links on your page while you read, or trust the check.

  When you're ready: /discover-stress-test
```
