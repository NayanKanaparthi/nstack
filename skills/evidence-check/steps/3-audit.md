# Step 3: Check the evidence

You are the checker. Treat nothing in the ledger as right until you have seen it yourself. The ledger was put together by a researcher who wanted to find things. Your job is to make sure the student never repeats a quote that isn't real, and never counts something as evidence that doesn't hold up.

If this conversation is the one that did the searching, stop and ask the student to open a new chat with the file. A check by the same conversation that gathered the evidence is not a check.

You re-open every evidence link, and every link in the existing products list. Beyond that you may run up to three searches, only for the reasons given under "Check the balance", or to find out who a source is.

Keep a result for every item as you go. You will enter them into the report in step 4. A result is one of:

- `counts`
- `set aside`, with one reason code from the tables below
- `removed`, with one reason code from the tables below

## Four questions for every item

Ask them in order, and hold every item on both sides to the same standard. The first answer that sets an item aside decides its result.

Be exact about question 1 and reasonable about the other three. A quote is either on the page or it isn't. Whether someone belongs to the group, or whether a quote speaks to the hypothesis, is judged the way a careful reader would judge it, not the way a lawyer would. A check that sets aside everything is as useless to the student as one that lets everything through.

**1. Is it real?** Open the link. Find the quote by looking for its distinctive words on the page, then compare word for word. Check the name and date too.

| What you find | Result |
|---|---|
| The quote is there | Go on to question 2. If the wording, name or date differs slightly from the page, fix it to match the page |
| The page opens but the quote isn't there, or means something different in context | removed: `not_on_page` |
| The page won't open | set aside: `could_not_open` |
| The student pasted it | set aside: `pasted` |

**2. Is it first-hand?**

| What it is | Result |
|---|---|
| A person describing their own experience. That includes a named person's own experience in an article, quoted or reported | Go on |
| An organisation stating in a sentence what it does, charges or counted | Go on, with the kind set to organisation fact. It counts only for that fact. A button, label or link whose target you can't read is set aside: `indirect` |
| Anyone describing what other people feel or do: a writer, an organisation talking about its users, a person talking about "most people I know" or about one other person | set aside: `second_hand` |
| The page itself shows the writer gains from the reader's choice: their own referral or affiliate link, a job at the company, a sponsored review, a seller describing what they are selling, a customer quote on the seller's own page, a professional writer reviewing or recommending a product | set aside: `stake` |
| A number repeated from somewhere else, or one that doesn't say who counted or what was counted | set aside: `not_original` |
| A rough amount with no count behind it: "thousands", "many", "a large number" | set aside: `vague_amount` |

The stake row is about people's words. An organisation's own count is different: if the organisation also sells a fix for the thing it measured, its number can be background (side `context`) at most, never for or against, and the note says what it sells.

A stake has to be shown, not suspected. If other people on the page only suspect the writer of advertising, and nothing on the page or in one search of your own confirms it, the item still counts. Put the suspicion in the item's note so the student can weigh it. A public discount code that anyone can use is not a stake either.

**3. Is it on target?** Cover the `Side` label. Read the quote against the hypothesis statement. The statement is the test; the "if true" and "if false" lines are only examples.

| What you find | Result |
|---|---|
| A careful reader would take it as showing the hypothesis is true for this writer, or as showing the opposite | Go on, and set the side yourself |
| It measures the very thing the hypothesis is about but doesn't settle it either way (see "Context" in `SKILL.md`) | Set the side to `context` and go on |
| It only connects through a step of your own reasoning. A long waiting list is not proof that people are unhappy. A plan, an expectation or "I would pay for that" is not doing it. A different problem ranking higher is not the opposite of this one. A figure about a wider group is not a figure about this one | set aside: `indirect` |
| For own words: the group isn't shown (see "Group shown" in `SKILL.md`) | set aside: `group_not_shown` |
| It is about something else | removed: `off_target` |

A quote that says both things ("it's exhausting, but I love it") is background: set its side to `context`.

A test for question 3: for each item you let through, say in one line how the quote itself shows the hypothesis true or false for this writer. If the line needs "which suggests" or "so probably", the item is indirect. Use the same test on both sides.

**4. Is it current?** If the page shows it is more than five years old, set aside: `old`. An item with no date is not set aside for that. Record "no date shown" and carry on.

An item that passes all four counts. Check the action while you are there: it is an action only if the person describes something they did (see `SKILL.md`).

**One voice.** Two items by the same author, or from the same study, are one voice. Different people on the same page are different voices. If a page doesn't show names, treat the items as different voices and say in a note that you couldn't tell.

**Something the ledger missed.** If a page you re-open plainly holds a first-hand account or an original number that speaks more directly to the hypothesis than what was taken, on either side, add it and put it through the four questions. Only add something that would count or be background. Two of these is the limit for the whole check.

**The existing products list.** Check each fact against its page in the same way. Correct it, or drop the line if the page doesn't say it.

## Check you were even-handed

Before moving on, list the reasons you used to set items aside or to move them to context. For each reason, look at the items still counting, on the other side and under the other hypothesis, and ask whether the same reason applies to any of them. If it does, apply it.

This is where checks go wrong. It is easy to be strict with one side and generous with the other without noticing, and the result looks like a finding.

## Check the balance

There is a gap to fill when:

- a cell in the Searches table was never searched, or
- one side of a hypothesis has nothing that counts, and either its items were all set aside or the ledger's "Not opened" list has pages for that side.

Fill at most one gap per hypothesis. If both sides are empty, that is one gap: give each side one page. First look at the "Not opened" list and open up to two pages that belong to the gap. If nothing there fits, run one search and open up to two pages. Take up to three items per side from what you open, the most direct first, put them through the four questions, and remember which items you added. Three searches is the limit for the whole check.

Don't add evidence for any other reason. You are not here to rescue a hypothesis or to sink it.

Then read `steps/4-report.md`.
