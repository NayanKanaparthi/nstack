# Rules for the wording of a suggested change

This file is for the main conversation running `/discover-stress-test` (step 4). It is not a sub-agent brief. The rules for writing assumptions are in `<plugin root>/skills/discover-frame/references/assumption-rules.md`; a change that adds or rewords an assumption follows them too.

## Which assumption a change names

- `assumption` is the id of the assumption the change edits itself: a new rating, a move to interviews only, or a reword in place of one the web search never ran on.
- `assumption` is `"new"` for every change that adds an assumption: a split, a narrower or reworded copy, or a fresh one. The `change` text names what the new one builds on, in a few words of its statement ("Add a narrower version of sitters at short notice: ...").
- The page shows "Changes: <statement>" for an id and "Adds a new assumption." for `"new"`, so the two never mix.

## The wording

- **Never change the statement of an assumption the web check ran on** (in `evidence.run_on`). Its findings must keep matching its words. To reword or split one, the change adds the new wording as a new assumption and leaves the old one as it is. Say so in the change: "Add a narrower version: ... The checked one stays as it was."
- When a change would move the riskiest mark (by changing a rating or adding a high-importance assumption), say so in the change, so the student's decision covers it.
- **A searchable statement stays broad enough to find:** its core claim plus at most one situation a page can show (`assumption-rules.md` section 4a). The kind of thing the action is done to counts as that situation. A change that adds a qualifier (an amount, how often, a sub-condition, the form of payment) adds it to an interview-only assumption pointing to the searchable one, never to the searchable statement itself.
- **A narrowing change says whether a web page could show the new wording.** A page can show a situation like "at short notice", but rarely the student's exact trigger ("when their usual sitter cancels"). If a page couldn't show it, the new assumption is interview-only (`searchable: false`, kind unchanged) and points to the wider searchable one as `nearest_searchable`. Say which in the change: "Add, for interviews only: ..." (`assumption-rules.md` section 4b).
- **A change that adds an assumption states its kind and its two ratings**: how much it hurts if wrong, and the evidence the student has now. The student sees them at the stop and accepts them with the change.
- **A change that adds a would-claim also gives it its own nearest version.** The would-claim is `future` and interview-only. Its nearest searchable version states the same action by the same people, today, and drops amounts and the form of payment (`assumption-rules.md` section 3): "would hire a sitter through an app" needs "hire sitters through an app today", never a different action such as paying a fee. If an assumption already states that action, name it in the change. If none does, the same change adds it too, and says so: "Add, for interviews only: ... Also add the version a search can check: ..."
- A point that doesn't call for a change stays a point on the page. Don't force it into a change.

## Applying accepted changes

At step 7, after the student's decisions, update `assumptions` from accepted changes only:

- reword or split: in place, unless the assumption is in `evidence.run_on`; then add new assumption(s) with the next free ids and keep the old one unchanged.
- change a rating: set it.
- move to interviews only: set `searchable: false`. If a `future` assumption pointed to it as `nearest_searchable`, point that one to another searchable assumption (the skill tells the student in one line).
- add: a new assumption with the next free id, following `<plugin root>/skills/discover-frame/references/assumption-rules.md` (kind, if-true and if-false, `needs_number`, nearest searchable for a future one), with the ratings the change stated.
- New and changed assumptions get `confirmed_by_student: true`: the student accepted them.
- `source`: a reword or split keeps its assumption's source; a new one is `student` when it comes from the student's answer, otherwise `ai guess`, which always has `evidence_now: "none"`.
