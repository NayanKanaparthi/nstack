# Rules for turning an idea into assumptions

These are the evidence check v6 sharpening rules, adapted for `/discover-frame`. Follow them exactly. The wording the student confirms is the wording that gets tested later, so get it right before any search.

From version 2.1, `/discover-frame` drafts every part the student hasn't said (contract v2.1 point 1). A draft is never a fact: every part and every assumption says where it came from (section 1b).

## 1. The idea sentence and the fill-in sentence

- `idea.sentence`: one neutral sentence, under 25 words, describing the idea, using only what the student said and, for an area entry, the picked problem. No guesses. No pitch words such as "innovative", "seamless", "easy", "revolutionary", "AI-powered". No background facts, even true ones.
- Keep the student's hedges ("maybe", "some", "sometimes", "probably") in the idea sentence and the fill-in sentence. "Maybe a small fee" stays "maybe a small fee"; "some just wait" stays "some just wait". Don't firm them up.
- `fill_in_sentence`: fill every slot of the template `[who] struggles with [problem] when [situation], handles it today by [workaround], and would pay [amount or way] for a better option`, each from the first source that has it (section 1b). You may add small joining words ("by", "is", "a") so it reads as a sentence. A slot that is your guess is written `[guess: <words>]`, so the page can show which parts nobody has checked. Never leave `[not said yet]`.
- **One problem, one sentence.** Every slot is about the same problem as [problem]. Words the student said about a different harm, or in describing their solution, don't go in a slot: draft that slot as a guess about the same problem, and say so in "What I reworded" in one line ("The situation is a guess: what you said was about a different problem."). The sentence must not join two problems into one, or state a link between them the student never made.

## 1b. Drafting what the student didn't say

For each part of the idea (who it's for, the problem, how they handle it today, who pays) and each slot of the fill-in sentence, use the first source that has it:

1. **The student's words** (`student`). Anything they said, in this step or earlier, as recorded in the `log`.
2. **The checked sources** (`checked sources`, area entry only). The picked problem's `statement` for the problem, its `who` line for who it's for, and its counted items for how they handle it today or who pays, only when a counted item shows that, in a few words of its own.
3. **Your best guess** (`ai guess`). The most likely answer you know of for these people and this problem, not the most interesting one.

A good guess:

- is one plain, specific claim a real person could prove wrong: it names the people and one thing they do, use or pay for ("equity analysts copy figures from several data terminals into spreadsheets by hand");
- is about the same people and the same problem as the rest of the draft;
- has no "or", no amount and no product name;
- is never written as a known fact ("most analysts use Excel"). It is a bet about what these people do, to be tested.

"I don't know", "no idea", "not sure" or "you tell me" from the student never leaves a blank and never earns another question: draft that part as a guess.

**Each assumption's `source`** is where its core claim came from:

- `student`: the claim is in the student's words, or follows from them by the rules here (a split, a nearest searchable version, a narrower or wider version, "people would use it at all" for an idea they described);
- `checked sources`: the claim comes from the picked problem's statement or its counted items, including versions made from those (area entry only);
- `ai guess`: every other claim you drafted, including versions made from a guess.

**For an area entry, the problem assumption is the picked problem's statement, word for word,** with source `checked sources`. Don't polish it: Find problems checked that exact statement, so `/discover-evidence` can spend its time on the other bets. If the student rewords or narrows it, that is a new statement in their words (`student`), and it gets searched like any other.

## 2. One claim per assumption

A good assumption:

- makes one claim. Split "owners struggle with this and would pay for a fix" into two. "Or" joins two claims too: two actions or two harms joined by "or" are two assumptions ("climb up to check the roof, or add a waste percentage" becomes two; "run short on shingles or lose working time" becomes two). A would-claim that names the student's solution and also a behaviour (paying up front, switching, paying a fee) is two claims too: split the behaviour from the solution. "Clients would agree to pay into a blockchain escrow before work starts" becomes "Clients would pay before work starts" and "Clients would use a blockchain escrow".
- names who it is about.
- could turn out false. "People like convenience" can't be wrong, so it can't be tested.
- keeps the student's meaning. Sharpen the wording; don't improve the idea and don't add facts. Anything you add is a guess (`ai guess`), never a fact.

## 3. The kind of each assumption

| Kind | What it claims | Where the answer is |
|---|---|---|
| `problem` | The problem exists and costs people something | Online |
| `people` | Who has it, and how many | Online |
| `today` | What they do about it today, and what they spend on it in money or time | Online |
| `future` | They would want, use, pay for or switch to something | Interviews only |

**Anything about the future is `future`.** If an assumption says people will or would want, use, pay or switch, it is interview-only (`searchable: false`), even when it names a kind of product and not the student's own. No page online is about a product that doesn't exist yet.

Keep it in the student's own words. Then add the nearest thing a search can answer as its own assumption (usually kind `today`, `searchable: true`), and point to it with `nearest_searchable`. Say what you changed.

**Every would-claim gets its own nearest version.** It states the same action by the same people, in the past or present. For "parents would use a text-message service to book a sitter", that is "parents book sitters by text message today", not some other claim about parents. Two would-claims share a nearest version only when it states both actions.

**Write it with one formula, before saving.** Turn "<people> would <verb> <object>" into "<people> <verb> <object> today", same people, same verb, same object. Then look for an assumption that states exactly that. If none does, add one. "Roofing companies would pay for roof measuring done on site" needs "Roofing companies pay for roof measuring done on site today".

**The nearest version keeps who acts, the action and what it is done to, and nothing more.** It drops amounts and the form of payment ("$20", "a monthly fee", "per roof", "per location", "a subscription"). Those stay in the would-claim, or go to an interview-only assumption pointing to the nearest version (section 4a). A page rarely shows how someone pays, and the check tests a statement on its core claim. "Roofing companies would pay per roof instead of per report" needs "Roofing companies pay for roof measuring today"; "per roof" stays in the would-claim. Never write "pay per report today", which is the thing it would replace.

> Student: "dog owners will pay a monthly fee for a walking app"
> Interviews only (`future`): "Dog owners will pay a monthly fee for a walking app."
> Nearest searchable (`today`): "Dog owners pay for dog walking today."
> What changed: "will pay a monthly fee for an app" became "pay for walking today". The monthly fee stays in the would-claim.

**The idea itself nearly always carries one the student didn't list:** that people would use the thing at all. Add it as a `future` assumption too, with its own nearest version like any other would-claim, and say it comes from the idea, not from their list, so the interview plan covers it.

**"Nothing good exists" can't be shown by a search**, because you can't search everything. Rewrite it as a claim about what people use today: "Dog owners who use a walking service are unhappy with it today."

An assumption that is not about the future can still be interview-only (`searchable: false`) when a page can't show it, for example a narrower group (see 4). Its `nearest_searchable` may point to the wider version.

## 4. Who counts

A page often doesn't show whether its writer is in a narrow group. A review of a walking service may not say whether the writer lives in a city flat. If only provably-in-group writers counted, most real accounts would be set aside.

So name the group whose words will count (`who_counts`), in one short phrase (15 words or fewer). Use the student's group when a page can show that someone belongs to it. Otherwise use the nearest wider group, such as "dog owners" for "dog owners in city flats". Whether the narrower group differs is a question for interviews: add it as an interview-only assumption.

## 4a. A searchable statement is broad enough to find

A searchable statement is its core claim (who, and what happens to them or what they do) plus at most one situation a page can show. Every other qualifier (an amount, how often, a sub-condition, the exact way something is done) goes into an interview-only assumption (`searchable: false`, same kind) whose `nearest_searchable` points to the searchable one. The checkers test a searchable statement on its core claim, and treat details as notes, so a qualifier left inside it only makes the search harder to find.

The kind of thing the action is done to counts as that one situation ("pay a designer for their book covers", "have their boilers serviced"). The checkers set aside a quote about a wider kind ("everything around my books"), so name the kind only when the idea depends on it, and then add no other situation.

> Student: "My plot neighbours and I argue about whose turn it is to water whenever one of us is away and the plot is only partly shared."
> Searchable: "Allotment neighbours argue about whose turn it is to water a shared plot."
> Interviews only: "Allotment neighbours argue about whose turn it is to water when one of them is away and the plot is only partly shared."

> Student: "Freelance designers spend hours every month chasing agency clients for invoices more than 60 days late."
> Searchable: "Freelance designers chase clients for late invoice payments."
> Interviews only: "Freelance designers spend hours every month chasing agency clients for invoices more than 60 days late."

## 4b. A situation that counts

The same holds for the situation a statement names. People rarely write "when my usual sitter cancelled" and the outcome in the same post, so a searchable statement tied to the student's exact trigger can almost never be shown.

So a searchable assumption names a situation a web page can show, the way `who_counts` widens the group: "parents who need a sitter at short notice", not "when their usual sitter cancels". Keep the student's narrower trigger as its own interview-only assumption (`searchable: false`, same kind), with `nearest_searchable` pointing to the wider searchable one, and say what you widened in "What I reworded".

**Details from one story are the narrow trigger.** When a detail comes from one story the student told (when in the job it happened, which material, which client), it belongs in the interview-only assumption. The searchable one is wider: "run short on materials or lose time on the job" stays searchable (split at the "or"), while "run short on shingles mid-job", from the student's uncle's story, is interview-only.

**Keep the link between a situation and its harm.** When the student's situation becomes its own assumption ("clients send notes by email, text and voice memo"), the harm it causes must still be stated somewhere: in a page-showable form ("editors lose time finding which note goes where when notes arrive in several places"), or as an interview-only assumption. Otherwise no assumption tests the link the student cares about.

## 5. If true, if not

For each searchable assumption write:

- `if_true`: what we'd expect to find if it is true.
- `if_false`: what we'd expect to find if it is not.

Make both concrete and observable: reviews complaining about a specific thing, people describing a workaround, a survey figure, people paying for a tool. Each line is one sentence under 25 words; the student reads them on the page.

If the statement has a loose word in it ("often", "a lot", "most", "rarely", "unhappy"), say in `if_true` what would count as it. For "most", "often", "rarely" or "a lot", only a count can settle it: set `needs_number: true`. Single accounts show that it happens, not how often.

Never invent a cutoff the student didn't give. Don't turn "rarely" into "fewer than 1 in 4". Word the test without a number ("a count showing it happens to a small share"), or use the student's own number if they gave one.

`if_false` is the plain opposite of the statement, not a neighbouring claim. For "dog owners often skip walks because of work", the opposite is "dog owners say work doesn't make them skip walks", not "they skip walks more because of weather". Check that no single finding could fit both lines.

## 6. The map

Propose two ratings for every assumption. The student confirms or changes them.

- `importance`, how much of the idea falls if this is wrong:
  - `high`: the idea doesn't work without it.
  - `medium`: it changes the idea's shape, but something is left.
  - `low`: a detail.
- `evidence_now`, what the student already has, judged only from what they told you (mostly "why they believe it") and, for an area entry, the checked sources:
  - `strong`: they have counted something themselves, or watched many people act on it.
  - `weak`: a few stories, friends, their own experience. A bet from the checked sources is `weak`, unless the student told you of more of their own.
  - `none`: nothing yet, or they didn't say. **Every `ai guess` is `none`**, always: nobody has evidence for a guess yet. The renderer refuses anything else.

Never rate evidence from what you know about the world, and never from how likely a guess seems. That is not the student's evidence. Never rate it from a detail taken from a web page the student cited, either (v1.7 point 10): a page they mention is something to search, not evidence they have. The checked sources from Find problems are the one kind of web evidence that counts here, and only for an area entry.

**Riskiest.** Candidates are assumptions with `high` importance and `weak` or `none` evidence. If there are 3 or fewer, every candidate is riskiest. If there are more, mark exactly 3, searchable ones first; among those, the ones the rest of the idea depends on most. Nothing else is riskiest. Recompute this every time a rating changes. The script checks it.

## 7. Solution words

List the places where the student described a solution instead of a problem: "an app", "a platform", "an AI tool that", "a marketplace", "a subscription", a feature list. Copy their words exactly, a few words each, into `solution_words`. Don't lecture: the page simply shows them. If there are none, leave the list empty.

## 8. Ids and order

Number assumptions `A1`, `A2`, ... in the order you show them at `/discover-frame`: searchable ones first, riskiest first among them, then interview-only ones. Ids are set once. Later changes add new ids at the end and never renumber, even when ratings change. Never reuse an id for a different statement.
