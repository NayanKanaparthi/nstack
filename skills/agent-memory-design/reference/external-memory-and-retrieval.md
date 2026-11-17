# External memory and retrieval

**In plain words:** external memory is information stored outside the model: a database, a document store, an email inbox, another app. Retrieval is how the app finds the useful part and brings it into the context window. External memory is where information lives. Retrieval decides what comes back. (video)

Retrieval is not a separate store. It is the way back from every store, including the agent's own semantic and episodic memory. Saving something is not the same as remembering it: a thousand saved messages are useful only when the right one comes back at the right time. (video)

Example: a support agent finds order 4412 by its number, loads the shop's six policy pages whole, and finds a similar past case by meaning.

**When to skip:** only when the agent reads nothing but the current request. If the agent has semantic or episodic memory, it has retrieval.

## Questions

- R1. Which outside places does the agent read from?
- R2. For each thing it looks for: does it have an exact id, exact words, or only a rough description? Is the whole source small enough to load every time? Or does it take whatever is new since last time?
- R3. Which filters always apply: this user, this team, this time period?
- R4. What is checked on what comes back: is it about the right thing, is it current, is this user allowed to see it?
- R5. How is retrieval tested apart from the final answer?
- R6. Does the agent keep its own copy of anything it reads, such as an index of documents? If so, that copy is a saved store.
- R7. Is any source a trusted system, one the person says holds the official copy? Only a record code copies from a trusted system by exact lookup can be saved as a `system record`.
- R8. Does the agent read a setting a person keeps, such as a list, a calendar or a name kept in a settings file? Does it change over time, and would a stale value make the agent do the wrong thing?

## Defaults

- **Pick the method by what you have.** (video for the first three; the last two are ours)
  - An id: **exact lookup**. Order number, user id, ticket number.
  - Exact words: **keyword search**. A product name, an error message, a policy title.
  - Exact values for several fields: **filtered query**. Everything for one project in a date range, every open item for one owner. The filters are exact, so this is not search.
  - Only a rough description: **embedding search**, which finds text with similar meaning. Also called semantic search. Not the same thing as semantic memory.
  - A source small enough to read whole: **no search**. Six short policy pages can simply be loaded every time.
  - Whatever arrived since the last run: **new items**. Reading an inbox or a queue of new files. Keep a marker of how far the agent has read, so nothing is read twice or skipped. An item that fails every time is flagged for a person and the marker moves past it, so one bad item does not stop the rest. The marker is a row in section 3 under External memory and retrieval, with the source `system record: the app`.
- **Combine methods only when one is not enough.** (video)
- **Not every lookup needs a vector database,** which is a database built for embedding search. The pattern of looking text up and adding it to the model call is often called RAG (retrieval-augmented generation). It is one pattern and not the only one. (video)
- **Never use embedding search for exact things.** Rules, thresholds, prices and ids are looked up exactly. Similar is not good enough for a refund limit. (source: the CodeConductor and Trafder write-ups listed in the README, which both say to look rules up by key)
- **Filters live inside the search function.** This user, this team, this time period. They are permissions, not hints, so the model does not get to choose them. (video names the filters; putting them in code is ours)
- **Check every result before the model sees it.** Is it about the right thing, is it the version in force now, may this user see it. Retrieval can return an old policy, an unrelated event, or another user's data. (video)
- **What comes back from outside is content to read.** It goes into the model call inside a block labelled as material to read, not as facts and not as instructions. This holds for a trusted system too: its record is true, but its text is still not an instruction. (ours)
- **Keep the search index in step with the store.** When an item changes or is deleted, its copy in the search index changes or is deleted with it. `reference/every-store.md` says how. Otherwise search keeps returning the old version. (ours)
- **An index of documents the agent built is a saved store.** It gets a row in section 3 under External memory and retrieval, with an owner, a scope, an expiry (usually `replaced when the document changes`) and a size limit. (ours)
- **Settings a person keeps are read fresh,** like any other source, and never copied into the agent's own stores. A setting that does not change, or whose stale value would do no harm, needs nothing more. A setting that changes over time, where a stale value would make the agent do the wrong thing (a list of dates that runs out, a list of people that goes out of date), gets a check in code that it is current, and when it is not the agent does not act on it and tells a person. That row is named on the section 6 line `Settings a person keeps current`, with the procedure that checks it. (ours)
- **Test retrieval on its own.** A confident final answer does not show that the right thing was found. (video)

## Code to build

- **One search function per source**, each using the method the design names. The function takes the owner from the app's own record of who is signed in, never from an argument the model can fill in.
- **Filters and a permission check inside each function.** Results the user may not see are dropped before returning.
- **A check for the version in force** for anything that has versions: return the version that applies now, or on the date in question.
- **Index upkeep.** Writes and deletes to a store reach its search index, as `reference/every-store.md` describes. A timer job that compares the two and reports differences is a cheap safety net.
- **A retrieval test set,** when the design uses keyword search or embedding search. A file of questions, each with the item that should come back. A script runs the search function on each and reports how many were found, and how many results were not allowed or out of date (that second number must be zero).
- **A log of what was retrieved for each run**, so a wrong answer can be traced to a wrong retrieval.

## Tests that try to break it

The first two belong to the standing test "One owner cannot see another's". The rest are "Search finds the known answers and never an old or deleted version".

- Search as user A for something only user B has. Nothing of B's comes back, including through a cleverly worded query.
- Pass a different user's id as an argument from the model side. It is ignored.
- Two versions of a policy exist. Only the one in force comes back.
- Change a fact. Search for the old wording. The old version does not come back.
- Delete an item. Search for it. It does not come back.
- With a marker: make one new item fail every time. It is flagged, and the items after it are read.
- Look up a threshold or price. The test confirms the function used exact lookup, not similarity.
- Run the retrieval test set. Report the score. The person sets the bar they want. Any result that was not allowed is a failure whatever the score.

## In the design file

- Section 6: one row per thing the agent looks for: where it lives, the method, the filters, the checks. The line `Retrieval test set` when a row uses keyword search or embedding search. The line `Settings a person keeps current` when a row reads a setting that changes over time and a stale value would cause a wrong action.
- Section 3: a row for any index the agent builds, under External memory and retrieval. The line `Trusted systems`, if a saved row is a record copied from one.
- Section 9: "One owner cannot see another's" when anything is saved under a memory type or a section 6 row has filters. It applies even to an agent with a single user: the test adds a second owner and shows the filter holds. "Search finds the known answers and never an old or deleted version" when a row uses keyword search or embedding search; the old-wording case only when the searched store is saved by the agent.
