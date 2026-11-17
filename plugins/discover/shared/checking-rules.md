# Checking rules: one standard for every check

Every check in this kit applies these rules, in these words: the `/discover-find-problems` check, the `/discover-evidence` check, every evidence top-up check, and the audit that follows each of them (`audit.md`). Each checker brief adds only what is specific to its step. If a brief and this file seem to differ, this file wins. Worked examples of every rule are in `calibration.md`, next to this file: read them before you start, and calibrate on them, not on adjectives.

## The standard: a careful, fair reader

Judge every item the way a careful, fair reader would. An item counts when such a reader would say the quote shows the statement's core claim true for this writer, or plainly false, using only the ordinary inferences anyone would make from the words and the page. Someone who enters the beans they picked from their allotment plot into a garden app is logging their harvest in an app; nobody needs that spelled out.

**Fair, not just even.** Even-handedness means the same fair standard on both sides. It never means the same excessive strictness on both sides. A check that sets aside everything is as useless to the student as one that lets everything through: both hide what people actually wrote.

"The statement" below means the statement under test: a candidate problem's statement in `/discover-find-problems`, an assumption's statement in `/discover-evidence`. An item is **for** when it shows the statement's core claim true for this writer, and **against** when it shows the core claim plainly false for this writer. For an assumption, the statement is the test; its "if true" and "if false" lines are only examples.

**Core claim and details.** A statement is tested on its core claim: who, and what happens to them or what they do, plus the one situation it names as essential, if any. Details that are not the core claim (an exact amount, a frequency word such as "every week", a sub-condition such as "partly shared", the exact way something is done) are noted, never grounds to set an item aside. The exception: a statement that is specifically about that detail (how many, how often, how much), where `needs_number` or a separate assumption carries it.

## Words

- **Own words:** a person describing their own experience. A named person's own experience in a news article counts too, quoted or reported; it is labelled as reported by that outlet. A professional writer's own experience counts only when the piece is not reviewing or recommending a product.
- **Action:** what the person did beyond an opinion. Plans and intentions are not actions.
- **Number:** a figure from whoever counted it, with who counted and what was counted.
- **Organisation fact:** something an organisation states about itself in a sentence: what it does, charges, is hiring for or counted. A button, label or link is not a statement.
- **The group:** the people in `who_counts` (in `/discover-evidence`) or the people the candidate problem names (in `/discover-find-problems`).
- **Background** (side `context`): a number or fact that measures the very thing the statement is about but doesn't settle it. Shown, counted for neither side. A figure about a wider group or a neighbouring measure is indirect, not background.

## A result for every item

Every item gets exactly one result, and you keep it as you go:

- `counts`
- `set aside`, with one reason code from the tables below
- `removed`, with one reason code from the tables below

## The four questions

Ask them in order. The first answer that sets an item aside decides its result. Be exact about question 1. Judge the other three as a careful, fair reader would, not as a lawyer would: whether someone belongs to the group, whether a quote speaks to the core claim, whether a gain is shown.

### 1. Is it real?

Open the link. Find the quote by its distinctive words, then compare word for word. Check the name and date too.

| What you find | Result |
|---|---|
| The quote is there | Go on. If the wording, name or date differs slightly from the page, fix it to match the page |
| The page opens but the quote isn't there, or means something different in context | removed: `not_on_page` |
| The page won't open | set aside: `could_not_open` |
| The student pasted it | set aside: `pasted` |

**A quote's link shows the quote** (v1.7 point 2). Link a review's or post's own page (its permalink) when the site has one. A paginated listing is a last resort, and the note then says so. For listings that hide most reviews behind a "see all" view, open the full view. If the quote isn't on its linked page, find its own page and link that, or set it aside as `not_on_page`. Never keep a link that doesn't show its quote, with or without a note.

**Never open a copy of another site.** Never open a site that mirrors, archives or scrapes another site's posts (a Reddit mirror, an archive snapshot, a "sentiment" or monitoring site). Only the original page may be linked. If an item points to such a copy, don't open the copy: open the original. If the original holds the quote, use its link. If it won't open, the item is set aside as `could_not_open` with the original's link, and the page lists it as one that wouldn't open.

**The same review on two sites is one item.** A review shown on two country versions of a site, or on a review site and its partner site, is one voice and one page: keep one item, with the link you opened first.

### 2. Is it first-hand?

| What it is | Result |
|---|---|
| A person describing their own experience, including a named person's own experience in an article, quoted or reported | Go on |
| An organisation stating in a sentence what it does, charges, is hiring for or counted | Go on, with the kind set to `organisation fact` or `number`. It counts only for that fact. A button, label or link is set aside: `indirect` |
| Anyone describing what other people feel or do: a writer, an organisation talking about its users, a person talking about "most people I know" or about one other person | set aside: `second_hand` |
| The page itself shows the writer gains from the reader's choice: their own referral or affiliate link, a job at the company, a sponsored review, a seller describing what it sells, a customer quote on the seller's own page, a professional writer reviewing or recommending a product | set aside: `stake` |
| A number repeated from somewhere else, or one that doesn't say who counted or what was counted | set aside: `not_original` |
| A rough amount with no count behind it: "thousands", "many", "a large number" | set aside: `vague_amount` |
| A post on a forum run by a company that sells a related product, where the page doesn't show who wrote it and when | set aside: `author_not_shown`. Say in the note which company runs the forum and what it sells |

**What a stake needs.** The page must show the writer gains from the reader's choice: a price, a fee, a commission, a sale, a job or a sponsor. Promoting something the writer runs, with none of these shown (a free network, a newsletter), is not a stake. Count the item and say in the note what the page promotes. A personal account that names the tool the writer uses is not a product review or recommendation; a piece whose purpose, or one of whose sections, is reviewing or recommending products is. A public discount code that anyone can use is not a stake. A review site's own reward for writing reviews ("incentivized") is not a stake either, because it doesn't depend on what the reader chooses; say so in the note.

**A stake is shown, not suspected.** If other people on the page only suspect the writer of advertising, and nothing on the page or in one search of your own confirms it, the item still counts. Put the suspicion in the note so the student can weigh it.

**An organisation that sells a fix.** An organisation sells a fix if it offers anything paid that deals with the measured problem: a membership benefit, insurance, a service, a tool. If it does, its own count is background (side `context`) at most, never for or against, and the note says what it sells. Judge the organisation, not the page: don't ask only whether this page promotes it. Run this test for every organisation's count, on both sides, before question 3, even if you expect to set the item aside. **Lookup searches:** at most one search per organisation, only to find what it offers. These lookups don't count toward a brief's search limit, and the cap of one per organisation holds for the whole check: if one search doesn't show what it sells, judge from what that search and the item's own page show, and say so in your notes. Once you find an organisation sells a fix, its count's side is `context` for the rest of the check, even if a later question sets the item aside. **The same test for every organisation** (v1.7 point 4): a link or menu on the item's own page offering a paid service (advertising, classifieds, a career centre, a shop, member discounts) shows what the organisation sells. The one lookup names the measured problem. The same kind of paid offer gives the same result for every organisation in the check.

### 3. Is it on target?

Cover the side label. Read the quote against the statement.

| What you find | Result |
|---|---|
| A careful, fair reader would take the quote, with ordinary inference, as showing the core claim true for this writer, or plainly false | Go on, and set the side yourself |
| It measures the very thing the statement is about but doesn't settle it either way | Set the side to `context` and go on |
| It is about a different claim, a different situation the statement names as essential, or a wider group; or getting from the quote to the claim needs a guess about something the page doesn't say. A long waiting list is not proof people are unhappy. A plan, an expectation or "I would pay for that" is not doing it. A different problem ranking higher is not the opposite of this one. A figure about a wider group is not a figure about this one | set aside: `indirect` |
| For own words: the page doesn't show the writer is one of the group | set aside: `group_not_shown` |
| It is about something else | removed: `off_target` |

**What `indirect` means.** An item is `indirect` only when it is about a different claim, a different situation the statement names as essential, or a wider group, or when getting from the quote to the claim needs a guess about something the page doesn't say. Ordinary inference is not a guess. A detail the quote doesn't mention (an amount, how often, a sub-condition) is not a reason: note it and go on.

**An essential situation.** When the statement names one situation as essential ("at short notice", "when quoting jobs from roof measurement reports"), an item in a different situation is `indirect`, on both sides and on every statement. An item a careful reader would place in that situation from the page counts as showing it: a plot the writer weeds with two neighbours is a shared plot. Never use a situation as a note on one item and as a reason on another.

**The kind of thing acted on is the situation.** When a `today` or past statement names the kind of thing its action is done to ("the book cover", "the boiler service", "winter tyres"), that kind is its one situation. A quote showing the same action on an unspecified or wider kind ("everything around my books", "all our upkeep") is `indirect`, on both sides. Its note names the gap in a few words: "Doesn't say a cover was among them." A quote a careful reader would place on that kind from the page counts. See `calibration.md`, pair 12.

**Silence is not the opposite.** A quote that says nothing about the core claim doesn't count against it, and one that says nothing about it doesn't count for it either. But a quote whose plain words settle the claim does count, even without the statement's own words: "the conductor emails the new scores the night before" is against "choir members wait weeks for new sheet music".

**Group shown.** The page shows the writer belongs to the group by saying so, or in a way a careful, fair reader would conclude from the words and the page. A trade unit or term used in a review of a product made for that trade shows the group: squares or pitch in a review of a roof-measurement product, timecodes in a review of a video-review tool. Naming a use is not doing it. Before you set an item aside as `group_not_shown`, open the reviewer's full review (its own page, or the page that shows it in full) and read all of it.

**Says both things.** Move an item to background (side `context`) for saying both things only when one part shows the statement true for this writer and another part shows its plain opposite for the same writer: "it's exhausting, but I love it". Wanting less of something, or skipping a kind of product the statement doesn't name, is not the opposite. A counted item whose own note concedes the fact another item counts for on the other side is background too: it says both.

**The on-target line.** For each item, write one line on how the quote shows the core claim true or false for this writer, using the quote, what the page shows about this writer, and ordinary inference. If the line needs a guess about something the page doesn't say, or another post by the writer, the item is `indirect`, on either side. A line that needs "so" or "which means" is a hint to look again, not a verdict: "she enters each week's picking from her plot, so she logs her harvest in the app" is ordinary inference and counts.

### 4. Is it current?

Count from the date the page shows for this item (a review's own date, not the date of the page that lists it) to today's date. More than five years: set aside, `old`. Five years or less: go on. No date shown is not a reason to set an item aside: record "no date shown".

**A non-English quote** keeps its own words in `quote`. Put a short English gist in the note ("In English: ..."), so the student can read it.

## Action, signal and voice

**Action.** For each item that counts, check the action: it is an action only if the person describes something they did.

**Signal.** One per item: the strongest behaviour the quote's own words show, picked in this order:

1. `money spent`
2. `switched`
3. `workaround`
4. `time spent`
5. `asked for recommendations`
6. `complaint`
7. `none`

Use `asked for recommendations` whenever the quote asks others what to do or use. Use `complaint` only when the quote itself says it frustrates, annoys or bothers them; stating facts, or saying something "is a big deal", is not complaining. A pricing page or job post shows what an organisation charges or pays, not that people pay: `none`, unless the page shows more. Never change a signal to one the words don't show, and never stretch a signal to fill a list. If every counted item shows `none`, that is the finding.

**One voice.** Two items by the same author, or from the same study, are one voice: give them the same `voice`. Different people on the same page are different voices. If a page doesn't show names, treat the items as different voices and say in a note that you couldn't tell.

## One standard across sides, statements, steps and runs

It is easy to be strict with one side and generous with the other without noticing, and the result then looks like a finding. It is just as easy to be strict with both sides, and then nothing counts at all. Before you write your files, do all seven of these and write them down in your notes.

1. **Reason lines.** Write each reason you used to set an item aside or move it to background as a one-line test, for example "the page gives no agreed payment date, so lateness can't be shown". First ask whether a careful, fair reader would accept that line; if not, drop it and give the items it caught the result such a reader would. Then run each line you keep on every counted item on both sides of the same statement, and on every counted item, under any statement, whose note or on-target line states the same fact. Where it applies, give the same result.
2. **Mirrored for and against lines.** For each statement, write its for-line (what an item must show to count for) and its against-line (what it must show to count against) side by side, as exact opposites at the same threshold. Write both at the level of the core claim, with details left out of both, so each is a line a careful, fair reader would use. If the for-line leaves out part of the statement (an amount such as "hours"), the against-line leaves it out too, and asks only for the plain opposite of what the for-line asks: for "does work to find the moment", against "needs no work to find the moment". Both lines use the statement's own key words in their ordinary sense and add no condition the statement doesn't name (v1.7 point 3). A later remedy (a callback, a refund, a fix) is a detail, noted on either side, never a reason on one. Then run the mirror of each line that let an item through on every item set aside on the other side. A step of reading you allowed one side (a reason you read into a quote) is allowed the other side too, or neither.
3. **Read your own notes.** Read the note of every counted item. If it states a reason you used to set another item aside or move it ("leaves room for the odd error", "doesn't say whether she paid"), or says the item may not show the statement's essential situation ("so this may not be about ordered reports"), give it that same result. A note that only records a missing detail (no amount, no frequency) is not such a reason.
4. **Longer quotes.** If a quote contains a sentence you set aside elsewhere, the longer quote counts only if its other words remove that reason. Say in your notes which words remove it.
5. **Same words, same reading.** The same words get the same result, side, reason and signal wherever they appear: under two statements, in two checks, or on two sites.
6. **Carry-over.** An item already judged in an earlier check keeps its result, reason and signal, for the same reason, unless its note says why this statement differs. Earlier checks are the earlier evidence checks and, for an area entry, the find-problems check (`discover-work/problems-checked.md`). Read the earlier notes before you start, and use their reason lines and mirrored lines unless they fail point 2; if they fail it, fix both lines and re-run them on the earlier items too. Carry-over never keeps a result that breaks another rule in this file: if an earlier result does, give the right result and say in your notes why it differs from the earlier check.
7. **The set-aside review.** For each statement, count its items set aside or removed. If more than 75% of its items are, write for every set-aside item the one sentence a careful, fair reader would accept as the reason it doesn't count. Any item you can't write that sentence for gets the result such a reader would give it, on whichever side. This is a review trigger, not a quota: a statement whose items really are off target can stay at 100% set aside, as long as every sentence holds.

## Writing what the page shows

- **Notes** are shown on the student's page, so use the page's words: "background", "set aside", "counted". Never write "context", "ledger", "cell", "audit" or a reason code in a note. If the words are a reporter's and not a direct quote, say "As reported by <outlet>, in the reporter's words."
- **Short names.** Spell out an organisation's short name the first time it appears in a field the page shows (`who`, `where`, `note`, a statement, a product's fact): "IPSE (a UK association for the self-employed)".
- **Word limits.** Every sentence you write that the page shows is under 25 words, so 24 at most: notes, statements, `who`, `where` and `did` lines, `still_open`, `not_found` lines, `problems_note`. Split a longer one into two. The renderer refuses longer ones. Words inside double quotation marks don't count, but a quotation in these lines stays under 25 words (a longer one belongs in the item's `quote`). Close every quotation mark you open. Never put a straight " right after a digit: write "10-inch" for a measure, and use curly marks “ ” for a quotation that ends in a number (costs “up to $87”). A full stop before a number, or after a short form (Jan., Calif., Prof., approx., e.g., U.S.), doesn't end a sentence, and nor does a line break unless the line ends in a full stop, "!" or "?". Don't rely on them to keep a sentence short (`data.md`, "The renderer also refuses").
- **Unread pages.** When pages that seemed to hold items for a side of a statement went unread, every gap line of that result says "in the pages read".
- **Plain words.** No item numbers such as E3 or K-E9 in anything the page shows.
