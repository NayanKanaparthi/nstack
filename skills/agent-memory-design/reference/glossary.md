# Words added in v0.2

Plain-words meanings for the terms the v0.2 parts use. `SKILL.md` has the list for everything else.

- **Version chain:** the versions of one fact in order, each pointing at the one it replaced and the one that replaced it. "Lead" then "Manager" for the same person is a chain of two.
- **Index:** a second structure the database keeps so it can find rows by a column quickly, like the index of a book.
- **Partial unique index:** a rule in the database that a value may appear once among some of the rows only. Here: one current fact per slot, while old versions of the same slot are left alone.
- **Append-only log:** a table that only ever gains rows. Nothing in it is changed or removed by the app. The fact events table is one.
- **Compare-and-swap:** change a row only if it is still the version you read. If someone changed it in between, the change is refused, and you read again and decide again.
- **Smoothing:** adding a few made-up answers to a count so that one or two real answers cannot swing it. "9 of 10 answers" as a prior is smoothing.
- **Survival analysis:** working out how long things last from records where many have not ended yet. Used here for how long a kind of fact usually stays true, when most facts have not been corrected so far.
- **Premise check:** on waking, a saved task compares what was true when it was scheduled with what is true now, and does nothing if they differ. A reminder for the 14th does nothing once the item has moved to the 21st.
- **Queue:** a waiting line of jobs. One part of the app adds a job, a worker does it later, so the person is not kept waiting.
- **Outbox:** a queue kept as rows in the app's own database. The job row is written in the same transaction as the record that needs it, so the job cannot be lost when the queue product is down.
- **Spool:** a small local file where the app keeps the writes it could not make while its store was down. A timer job writes them once the store answers again.
- **Vector index:** the structure a database keeps so it can find the stored embeddings nearest to a question's embedding without comparing every one.
- **Reranker:** a second step that takes the first results of a search and re-orders them, so the best few are the ones that reach the model.
- **Partition key:** the column a large table is split by, usually the owner, so a query for one owner reads one part of the table.
- **Edges table:** a table of links between things, one row per link: from, to, and the kind of link, such as who reports to whom.
- **Tracing:** a record of each step of a run with its timing, kept so a slow or wrong run can be followed afterwards.
- **As built:** a design written from the code of an agent that already exists, saying what the code does today, wrong parts included, rather than what it should do. Its title ends `(as built)`. See `steps/review-existing-agent.md`.
- **Gap:** one thing the code of an existing agent does or lacks that makes a checklist line `no`, with the file and line that show it. A different name or starting value that breaks no line is not a gap.
- **Candidate gap:** an item the checker lists under "WHAT THE FILE SHOWS IS MISSING OR DOES NOT AGREE" for an as-built design. It becomes a gap only once the code confirms it.
- **Gap report:** `MEMORY-GAPS.md`, written beside the as-built design: every checklist line answered, the gaps ordered by what each would cost if it went wrong once (the ones the code has today first, then rules that work but no test would catch), what could not be told from the code, and the checker's output.
