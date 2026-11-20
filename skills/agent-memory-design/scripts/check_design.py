#!/usr/bin/env python3
"""Check that a MEMORY-DESIGN.md file is complete and agrees with itself.

Usage:
    python3 -B check_design.py MEMORY-DESIGN.md
    python3 -B check_design.py MEMORY-DESIGN.md --project <path to the project>
    python3 -B check_design.py MEMORY-DESIGN.md --as-built [--project <path to the project>]

What it does
    It reads the ten sections of the design file, and sections 11 to 13 of a
    design with the line A9, and checks fixed things:
    that every required cell is filled, that every fixed choice is one of the
    allowed values, and that the sections agree with each other.

    It does not read meaning out of free text. Where a rule needs a judgment,
    the design file states it as a fixed choice, and this script enforces the
    rule from that choice. What a script cannot know is printed under
    "FOR THE REVIEWER TO JUDGE" and never counts as passed.

    It reports every line it did not read.

    With --project it also checks that each test file named in the design
    exists in the project and defines a test with that name, and, for Python
    files, that the test asserts something. Without it, it says so.

    A design whose section 1 has the line A9 is also checked against the lines
    CHECKLIST.md added in v0.2.

    With --as-built the file is read as a description of what existing code
    does. Missing things are listed and are not a failure of the file.

Exit codes
    0  no problems found
    1  problems found
    2  the file could not be read, or the command was wrong

Python standard library only.
"""

import ast
import os
import re
import sys

TITLES = {
    1: "About the agent",
    2: "Memory types",
    3: "What is saved",
    4: "Procedures",
    5: "Actions with side effects",
    6: "Retrieval",
    7: "Future tasks",
    8: "Who can read and write",
    9: "Tests",
    10: "Open questions and arbitrary numbers",
}

A_LABELS = {
    "A1": "What the agent is for",
    "A2": "Agents and users",
    "A3": "How runs start, and how long work lasts",
    "A4": "Actions with side effects",
    "A5": "Outcome signal",
    "A6": "What it reads that nobody checked",
    "A7": "What goes wrong if it forgets or misremembers",
    "A8": "Model, and what it cannot know",
    "A9": "Also true of this agent",     # optional: it switches on the lines CHECKLIST.md added in v0.2
}
A9_VALUES = ["someone waits live", "several routes change a fact", "a model turns text into facts", "high volume"]
HOW = ["worked out", "asked", "assumed"]

MEMORY_TYPES = [
    "Working memory",
    "Semantic memory",
    "Episodic memory",
    "Procedural memory",
    "External memory and retrieval",
    "Prospective memory",
]
OTHER_TYPES = ["Run log", "Audit log", "Side effect protection"]
OTHER_TYPES_V2 = OTHER_TYPES + ["Fact events"]
BOOKKEEPING_TYPES = ["Run log", "Audit log", "Side effect protection", "Prospective memory",
                     "External memory and retrieval", "Fact events"]
SOURCES = ["user stated", "agent worked out", "outside content", "system record"]
IF_SKIPPED = ["harmless", "costs money", "sends something out", "cannot be undone",
              "leaks data", "corrupts memory", "misses a promised action"]
KEY_ORIGINS = ["stored id", "step name", "scheduled time", "event id", "item id"]
IDENTIFYING = ["stored id", "scheduled time", "event id", "item id"]
RUN_STARTS = ["a person", "a schedule", "an event"]
METHODS = ["exact lookup", "filtered query", "keyword search", "embedding search", "no search", "new items"]
SEARCH_METHODS = ["keyword search", "embedding search"]
TRIGGERS = ["time", "event", "condition"]
NEEDED_STATUSES = ["pending", "running", "done"]
AT_LIMIT = ["refuse", "retire the oldest", "replace the old one", "stop the run", "shorten"]
PICKED_UP_BY = ["the stuck task job", "a job over the actions record", "a person"]
CONTENTS = ["none", "fixed or templated", "outside content", "agent worked out"]
RISKY_CONTENT = ["outside content", "agent worked out"]
WHO_ASKED = ["person", "design"]
NUMBER_SOURCES = ["policy", "requirement", "data", "default"]
# A number written with a word after it, in sections 1 to 8 (CHECKLIST line 25). Digits joined to a word, a path, a
# time's colon or a dash are part of a name, not a number of the design.
RE_WORD_NUMBER = re.compile(r"(?<![\w.,:/\\#@\-])(\d+(?:,\d{3})*(?:\.\d+)?(?::\d\d)?%?)\s+([^\W\d_]+)")
# The same, with no word after it: the number is followed by punctuation, a cell's bar or the end ("above 25.", "$25,").
RE_BARE_NUMBER = re.compile(r"(?<![\w.,:/\\#@\-])(\d+(?:,\d{3})*(?:\.\d+)?(?::\d\d)?%?)(?![\w.,:%]?\d)"
                            r"(?=\s*(?:[.,;:!?)\]|]|$))")
RE_SQUARE = re.compile(r"\[([^\[\]]*)\]")
SOURCE_FORMS = ("`[policy]`, `[policy, not told yet]`, `[requirement: <the arithmetic, with an = sign>]`, "
                "`[data: <the query or test>]`, `[data: <the query or test>, interim]` or "
                "`[default: <the measure that would show it is wrong>]`")

H2 = ["Memory type", "Decision", "Reason"]
H3 = ["Item", "Memory type", "Owner", "Scope", "Expiry", "Source", "Enters as", "Size limit"]
H4 = ["Procedure", "Rule", "If skipped once", "Lives in", "Where", "Guards", "Test"]
H5 = ["Action", "Can be undone", "Idempotency key", "Key parts", "Needs approval", "Content it carries", "Guarded by"]
H6 = ["What it looks for", "Where it lives", "Method", "Filters", "Checks on results"]
H7 = ["Task", "Trigger", "Holds", "Checks again on waking", "Statuses"]
H8 = ["Agent", "Store", "Read", "Write"]
H9 = ["Test", "Where"]

DASH_KEYS = {
    4: ["Episodes before a procedure is suggested", "What wakes the app", "Missed firings are caught up by"],
    3: ["Run log holds content", "Trusted systems", "Kinds an owner can set for themselves",
        "Kinds that hold a list", "Who may confirm an unconfirmed item", "Expired rows are removed by",
        "Audit log kept in"],
    5: ["Repeats are stopped by", "Actions taken are recorded in",
        "Unfinished actions are picked up by", "Content checked before sending by", "Approval is checked by",
        "Approvals are saved in", "Who may approve", "An approval lasts", "A claimed action is held for"],
    6: ["Retrieval test set", "Settings a person keeps current"],
    7: ["A running task goes back to pending after"],
}
# Lines read only in a design whose section 1 has the line A9 (CHECKLIST.md lines 26 on).
V2_DASH_KEYS = {
    3: ["Facts with no end are reviewed", "A fact of no listed kind is saved as", "Review numbers",
        "The owner sees what their facts drive", "Rates and review ages are recomputed by",
        "Conflicts between facts are settled by", "Extraction output is checked by", "Extraction test set",
        "Extraction prompt is improved by"],
}
# v0.2 slice S3 (CHECKLIST 31 to 33): the lines under the tables of sections 5 and 7.
V2_DASH_KEYS[5] = ["Risk of each action", "Limits", "Open-ended tools", "Before a risky action these facts are fresh"]
V2_DASH_KEYS[7] = ["Premise of each task", "A changed record cancels or replaces its tasks through",
                   "A wait for confirmation ends after"]
# One part of a freshness entry: `<a no-end row's exact name> within <number> <unit>`, then a comma or the end.
RE_FRESH_PART = re.compile(r"\s*(.+?)\s+within\s+(\d[\d,]*)\s+((?:minute|hour|day|week|month|year)s?)(?![A-Za-z0-9])\s*(?:,|$)",
                           re.I)
REVIEW_EXAMPLE = ("each confirmation multiplies the wait by 2 times; prior for user stated: 9 of 10 answers; a kind's "
                  "own rate replaces the prior once its 95 percent interval is narrower than 20 points; the learned "
                  "review age is the age by which 10 percent of a kind's facts were corrected; alert when a kind's rate "
                  "drops by 15 points")
# The lines a design needs when a section 3 row has the expiry `no end, checked by evidence` (CHECKLIST 26 to 28):
# key, tag, and what the message says after "so it needs the line ".
T1_LINES = [
    ("Facts with no end are reviewed", "check 26",
     "`- Facts with no end are reviewed: <the row's exact name>: after <number> <unit>, at most <number> <unit>`, "
     "one part per row with no end, joined by semicolons."),
    ("A fact of no listed kind is saved as", "check 26",
     "`- A fact of no listed kind is saved as: <the exact name of a Semantic memory row>`, or `none: <why>` when no "
     "model writes facts."),
    ("Review numbers", "check 27",
     "`- Review numbers: " + REVIEW_EXAMPLE + "`, with one prior for each source a row with no end has, and `; seen "
     "with no correction counts after 7 days` when the owner sees what their facts drive."),
    ("The owner sees what their facts drive", "check 28",
     "`- The owner sees what their facts drive: yes, <where they see it>` or `no: <why>`."),
    ("Rates and review ages are recomputed by", "check 27",
     "`- Rates and review ages are recomputed by: <a procedure name from section 4>`."),
]
REVIEW_PARTS = ["each confirmation multiplies the wait by", "prior for user stated:", "prior for agent worked out:",
                "prior for outside content:", "prior for system record:",
                "a kind's own rate replaces the prior once its", "the learned review age is the age by which",
                "alert when a kind's rate drops by", "seen with no correction counts after"]
REVIEW_STARTING = {"each confirmation multiplies the wait by": "2 times",
                   "prior for user stated:": "9 of 10 answers", "prior for system record:": "9 of 10 answers",
                   "prior for agent worked out:": "5 of 10 answers", "prior for outside content:": "5 of 10 answers",
                   "a kind's own rate replaces the prior once its": "95 percent interval is narrower than 20 points",
                   "the learned review age is the age by which": "10 percent of a kind's facts were corrected",
                   "alert when a kind's rate drops by": "15 points",
                   "seen with no correction counts after": "7 days"}

UNIT = r"(?:minute|hour|day|week|month|year)s?"
RE_PERIOD_AFTER = re.compile(r"^\d[\d,]*\s+(?:working\s+)?" + UNIT + r"\s+after\s+\S", re.I)
RE_WHEN = re.compile(r"^when\s+\S", re.I)
RE_WHEN_HOW = re.compile(r"^when\s+\S.*,\s*(told|asked)(?![A-Za-z])", re.I)
RE_REPLACED = re.compile(r"^replaced\b", re.I)
RE_PERMANENT = re.compile(r"^permanent:\s*(\S.*)$", re.I)
RE_NO_END = re.compile(r"^no end, checked by evidence(?![A-Za-z0-9])", re.I)
DAYS = {"minute": 1 / 1440.0, "hour": 1 / 24.0, "day": 1, "week": 7, "month": 30, "year": 365}
RE_LIMIT = re.compile(r"^\d[\d,.]*\s+\S.*,\s*then\s+(.+)$", re.I)
RE_BOUNDED = re.compile(r"^bounded by retention(?![A-Za-z0-9])", re.I)
RE_SAME_AS = re.compile(r"^same as\s+(.+)$", re.I)
RE_LASTS = re.compile(r"^(?:until the scheduled time plus\s+)?\d[\d,]*\s+" + UNIT + r"(?![A-Za-z0-9])", re.I)
RE_SPAN = re.compile(r"^\d[\d,]*\s+" + UNIT + r"(?![A-Za-z0-9])", re.I)
RE_TEST = re.compile(r'^("[^"]+"|\S+) in (\S+)$')
RE_BRACKETS = re.compile(r"\s*\([^()]*\)")
RE_NUMBER = re.compile(r"(?<![\w.,])(\d[\d,]*)(?![\w])")
RE_NUMUNIT = re.compile(r"(?<![\w.,])(\d[\d,]*)\s+([A-Za-z]+)")
# S2 fix round 1 (review finding 2): what the free part of a new line may not be.
HOLLOW_NOTE = "A part in angle brackets is a blank to fill in, and a mark with no letter or digit names nothing."


def whole(text):
    """A whole number written with digits and commas, like 2,000."""
    return int(text.replace(",", ""))


# S2 fix round 1 (review finding 4): the form of each part of "Review numbers" after its fixed start, the form as the
# message writes it, and the range its numbers must be in. Nothing may follow the form in the part.
_PRIOR_FORM = (r"(\d[\d,]*) of (\d[\d,]*) answers", "<a> of <b> answers`, with a not above b and b at least 1",
               lambda g: whole(g[1]) >= 1 and whole(g[0]) <= whole(g[1]))
REVIEW_FORMS = {
    "each confirmation multiplies the wait by": (r"(\d[\d,]*(?:\.\d+)?) times", "<n> times`, with n above 1, like 2 or 1.5",
                                                 lambda g: float(g[0].replace(",", "")) > 1),
    "prior for user stated:": _PRIOR_FORM, "prior for agent worked out:": _PRIOR_FORM,
    "prior for outside content:": _PRIOR_FORM, "prior for system record:": _PRIOR_FORM,
    "a kind's own rate replaces the prior once its": (
        r"(\d[\d,]*) percent interval is narrower than (\d[\d,]*) points",
        "<n> percent interval is narrower than <m> points`, with n and m each from 1 to 99",
        lambda g: 1 <= whole(g[0]) <= 99 and 1 <= whole(g[1]) <= 99),
    "the learned review age is the age by which": (r"(\d[\d,]*) percent of a kind's facts were corrected",
                                                   "<n> percent of a kind's facts were corrected`, with n from 1 to 99",
                                                   lambda g: 1 <= whole(g[0]) <= 99),
    "alert when a kind's rate drops by": (r"(\d[\d,]*) points", "<n> points`, with n from 1 to 99",
                                          lambda g: 1 <= whole(g[0]) <= 99),
    "seen with no correction counts after": (r"(\d[\d,]*) " + UNIT, "<n> <minutes, hours, days, weeks, months or "
                                             "years>`, with n at least 1", lambda g: whole(g[0]) >= 1),
}

# Standing tests: name, checklist line, key into the facts that make it required.
TESTS = [
    ("Every run is logged", 8, "always",
     "every agent keeps a run log"),
    ("Expired items never come back", 10, "stored",
     "section 3 saves something besides the run log"),
    ("A repeat, a contradiction or two saves at once leave one current item", 11, "memory_rows",
     "section 3 has a row under a memory type"),
    ("Outside content stays unconfirmed and the model cannot set the source", 12, "model_fed",
     "a row in section 3 has the source user stated, outside content or agent worked out, or an action "
     "carries outside content or agent worked out"),
    ("Delete removes everywhere", 13, "content",
     "section 3 saves something besides the run log, or the run log holds content"),
    ("Secrets are never saved or sent out", 14, "content",
     "section 3 saves something besides the run log, or the run log holds content"),
    ("One owner cannot see another's", 15, "owners",
     "something is saved or looked up, or several agents share memory"),
    ("Size limits hold, cleanup runs, and every write is in the audit log", 16, "stored",
     "section 3 saves something besides the run log"),
    ("Search finds the known answers and never an old or deleted version", 17, "search",
     "section 6 uses keyword search or embedding search"),
    ("An action happens exactly once", 18, "actions",
     "section 5 lists an action"),
    ("A wrong or expired approval is refused", 19, "approvals",
     "an action in section 5 needs approval"),
    ("A task fired twice acts once and a stuck task runs again", 20, "tasks",
     "there is a future task"),
    ("An episode is written only after the outcome, only when it teaches, and carries no outside text",
     21, "episodes", "section 3 has an Episodic memory row"),
    ("A procedure is suggested only at the set count and is not live before approval", 22,
     "suggestions", "section 3 has a Procedural memory row"),
    # v0.2: required only in a design whose section 1 has the line A9
    ("A fact with no end is checked on every read", 26, "t1", "a section 3 row has no end"),
    ("Fact events are the record and the counters can be rebuilt", 27, "t1", "a section 3 row has no end"),
    ("What a fact drove is recorded, and silence counts only when it was seen", 28, "t1_seen",
     "a row has no end and the owner sees what their facts drive"),
    ("Two changes to one fact leave one current version, and code decides which", 29, "t4",
     "A9 says several routes change a fact"),
    ("Extraction output is checked, versioned and scored", 30, "t5", "A9 says a model turns text into facts"),
]
# v0.2 slice S3 (G2): T2, T7, and T1 with T7
TESTS += [
    ("A task whose reason changed does nothing", 31, "t2", "a task in section 7 has a premise"),
    ("Risk is fixed in code and limits hold", 32, "t7", "section 5 lists an action, in a design with A9"),
    ("A risky action waits when a fact it rests on is stale", 33, "fresh", "a risky action rests on a fact with no end"),
]


def cases_for(line_no, f):
    """The cases a standing test needs, one test each, as steps/3-design.md section 9 lists them."""
    c = []
    if line_no == 8:
        c = ["a run is logged and nothing from the log reaches a model call",
             "a log entry past its expiry is gone once the cleanup has run",
             "a run that reaches the run log's size limit does what the design says"]
        if f["trig"]:
            c.append("a firing that does nothing is logged as a run")
    elif line_no == 10:
        c = ["an item past its date is not returned by any read function, without cleanup"]
        if f["event_expiry"]:
            c.append("an item whose event has happened is not returned")
    elif line_no == 11:
        c = ["a repeat and a contradiction leave one current item", "two saves started together lose nothing"]
        if f["v2"]:
            c += ["the database itself refuses a second current item in one slot",
                  "a replaced version is still in the history with the times it was true from and until"]
    elif line_no == 12:
        if f["row_fed"]:
            c += ["text from outside stays unconfirmed", "the model passing `user stated` is ignored"]
        if f["owner_set"]:
            c += ["a value an owner sets outside the allowed list is refused or unconfirmed, as the design says",
                  "the same statement from a sender the app has not checked, or from someone who may not speak for "
                  "the owner, is refused or stays unconfirmed"]
        if f["confirmable"]:
            c.append("an attempt to confirm that is not the exact confirm form (a reply with a negation or a quote, or one that only contains the code) confirms nothing")
        if f["action_content"]:
            c.append("the record of actions never reaches a model call")
    elif line_no == 14:
        c = ["a secret is refused by every store, the run log and the audit log"]
        if f["action_content"]:
            c.append("a secret in outside or model-written text an action carries is not sent")
    elif line_no == 15:
        c = ["owner A never gets B's item, through every read function and every job that works by owner"]
        if f["several"]:
            c.append("an agent writing a store it may not is refused")
    elif line_no == 16:
        c = ["a write is in the audit log", "the cleanup removes expired rows and the removal is in the audit log"]
        c += ["a full store does what the design says: %s" % x for x in f["full_stores"]]
    elif line_no == 17:
        c = ["the scored test set"]
        if f["indexed"]:
            c.append("a changed or deleted item is not found by its old wording")
    elif line_no == 18:
        c = ["crash after the action", "crash before the action", "unknown result", "two at the same moment"]
        if "scheduled time" in f["trig"]:
            c.append("a late second firing")
        if "event id" in f["trig"]:
            c.append("the same event again")
        if f["content"]:
            c.append("delete, then the same action again")
        if f["approvals"]:
            c.append("crash after the approval, before the action")
    elif line_no == 19:
        c = ["wrong approval", "expired approval", "changed after approval", "not allowed to approve"]
    elif line_no == 20:
        c = ["fire twice at once", "crash after the claim"]
        if f["approval_tasks"]:
            c.append("crash after the approval")
        if f["actions"]:
            c.append("an action held by another run's claim leaves the task open, and it runs again")
    elif line_no == 21:
        c = ["no outcome, no episode", "an ordinary success writes nothing",
             "a sentence planted in outside content is in no episode"]
    elif line_no == 22:
        c = ["one episode short of the count gives no suggestion",
             "a suggestion is absent from the model call before approval and after switching off"]
        if f["episode_count"]:
            c += ["the set number of episodes from one run gives no suggestion",
                  "one episode against the lesson stops the suggestion"]
    elif line_no == 26:
        c = ["a fact past its review time still reaches the model call, shown with when it was last confirmed",
             "a confirmation multiplies the wait and stops at the cap",
             "a correction starts a new version at the kind's review age"]
        if f["catchall"]:
            c.append("a kind off the list is saved under the row the design names")
        if f["sees"]:
            c.append("a due fact puts one question to its owner and no second while the first is open")
    elif line_no == 27:
        c = ["an event cannot be changed after it is written",
             "counters rebuilt from the events equal the counters on the facts",
             "trust uses the source's prior on one side of the interval width and the kind's own rate on the other",
             "the recompute job sets a kind's rate and learned review age and alerts on a drop"]
    elif line_no == 28:
        c = ["a reply or action built from a fact records its id",
             "a yes to a read-back is a confirmation",
             "output seen with no correction counts after the window and not before",
             "output nobody saw counts for nothing",
             "output a fact drove says so",
             "a fix by the owner is recorded as a correction",
             "undoing what the agent did records a contradiction on the facts behind it"]
    elif line_no == 29:
        c = ["two replacements of one version at the same moment leave one current fact and both in the history",
             "the person's own words beat an inferred value, whichever came last",
             "from one source, the newer wins",
             "a model answer that is not `same`, `update` or `contradiction` changes nothing"]
        if f["several_people"]:
            c.append("two people who disagree leave the fact disputed and the agent asks")
    elif line_no == 30:
        c = ["broken output is retried once, then nothing is saved",
             "the extraction job run twice on one input saves once",
             "each fact carries the version of the prompt that made it, and one version's facts can be listed and "
             "marked for review",
             "a correction's reason is set by code, `saved wrong` on one side and `world changed` on the other",
             "the test set gives the same score twice, and a prompt that scores lower is refused"]
        if f["optimizer"]:
            c += ["the optimizer refuses below its minimum of examples",
                  "with a stub model the optimizer runs end to end, writes a candidate and leaves the live prompt as it was",
                  "an approved candidate becomes a new prompt version, and one not approved is never loaded"]
    elif line_no == 31:
        for task, values in f["premises"]:
            c += ["%s: %s changes and the old task fires: nothing is done and it is closed as `no longer valid`"
                  % (task, value) for value in values]
        c += ["the task written after the change still acts, once",
              "changing a value the premise names closes or replaces its open tasks in the same transaction",
              "the record changes while the task runs, after its check on waking and before its send: nothing is sent "
              "and it is closed as `no longer valid`"]
    elif line_no == 32:
        c = ["the model naming a lower risk for its own action changes nothing",
             "a tool with no risk label cannot be offered to the model"]
        c += ["one past the limit is refused: %s" % action for action in f["limits"]]
        c += ["a recipient not on the list is refused: %s" % action for action in f["list_limits"]]
        for tool in f["open_tools"]:
            c += ["%s: a command a code rule forbids is refused" % tool,
                  "%s: a command no rule covers is treated as risky" % tool]
    elif line_no == 33:
        c = ["a fact last confirmed outside its window: the action waits and the agent confirms first",
             "the same fact confirmed inside the window: the action goes ahead without asking"]
        if f["confirm_tasks"]:
            c += ["a task whose action waits is `waiting for confirmation`, counts no try, and acts once after the "
                  "confirmation",
                  "a wait with no answer ends after the set time: the task is `failed` and a person is told"]
    elif line_no == 34:
        c = ["a memory read slower than its time allowed is cut off and the reply is built without it"]
        if f["model_work"]:
            c.append("memory work a model does is queued and runs after the reply is returned")
    elif line_no == 35:
        if f["embed_saved"]:
            c.append("saving an item makes its embedding, and a search makes none for stored items")
        if f["rerank"]:
            c.append("what reaches the model scores no lower on the test set with the reranker than without")
    elif line_no == 36:
        c = ["a turn that would make more extra model calls than the cap makes exactly the cap"]
        if f["rollup_time"]:
            c.append("a use of a fact writes no counter on the fact's row, and after the roll-up the counters equal the "
                     "events")
        if f["move_time"]:
            c.append("a moved version is still found in the history")
    else:
        c = ["the case the checklist names"]
    return c


WHO_ASKS = ("Is it taken from who is signed in, and never from the model? When it is a person outside the system "
            "who replies to a message, does a reply count only when the sender matches the person on record, quoted "
            "text is stripped before it is read, and what is left is exactly the one-time code saved before the "
            "request was sent and a fixed word (or a button carrying the code), so a reply that only contains them, "
            "a negation or a quote, never counts?")
CHECK_NAMES = {
    1: "memory types decided", 2: "owner, scope, expiry, size limit", 3: "source and confirmed",
    4: "skipped once, code", 5: "actions, keys, guards", 6: "episodes need an outcome signal",
    7: "worked out, asked, assumed, numbers", 8: "every run is logged", 9: "procedures tested",
    10: "expired items", 11: "one current item", 12: "outside content unconfirmed", 13: "delete everywhere",
    14: "no secrets", 15: "one owner only", 16: "size, cleanup, audit", 17: "search", 18: "exactly once",
    19: "approvals", 20: "tasks", 21: "episodes", 22: "suggested procedures", 23: "nothing for skipped types",
    24: "the review", 25: "where numbers come from", 26: "facts with no end", 27: "fact events and trust",
    28: "what a fact drove", 29: "conflicts between facts", 30: "extraction"}
CHECK_NAMES.update({31: "premise of a task", 32: "risk and limits", 33: "fresh facts before a risky action"})


def tag_text(tag):
    m = re.match(r"^check (\d+)$", tag)
    return "%s, %s" % (tag, CHECK_NAMES[int(m.group(1))]) if m and int(m.group(1)) in CHECK_NAMES else tag


NOT_NEEDED_BECAUSE = {
    "memory_rows": "nothing is saved under a memory type",
    "model_fed": "no saved row has the source user stated, outside content or agent worked out, and no action "
                 "carries outside content or model-written text",
    "content": "the run log is the only thing saved, and it holds no content",
    "stored": "the run log is the only thing saved, and its expiry and cleanup are tested under line 8",
    "owners": "nothing is saved under a memory type, no row in section 6 filters by anything, and one agent uses "
              "the memory",
    "search": "nothing is found by keyword search or embedding search",
    "actions": "A4 says the agent has no action with a side effect",
    "approvals": "no action needs approval",
    "tasks": "there is no future task",
    "episodes": "there is no Episodic memory row, no row outside procedural memory is written by the model, and "
                "no Semantic memory row holds outside content",
    "suggestions": "there is no Procedural memory row in section 3, and no row outside episodic memory is written "
                   "by the model",
    "t1": "no row in section 3 has the expiry `no end, checked by evidence`",
    "t1_seen": "no row has no end, or the design says the owner does not see what their facts drive",
    "t4": "A9 does not say several routes change a fact",
    "t5": "A9 does not say a model turns text into facts",
}
NOT_NEEDED_BECAUSE.update({
    "t2": "no task in section 7 has a premise",
    "t7": "A4 says the agent has no action with a side effect",
    "fresh": "no risky action rests on a fact with no end",
})


# v0.2 slice 4 (G3, production): CHECKLIST lines 34 to 39. Sections 11 to 13 exist only in a design with A9, after
# section 10 in the file. Added here as one block so the tables above keep their v0.1 and S2 text.
TITLES.update({11: "Failures", 12: "Measurements", 13: "Volume"})
H11 = ["What fails", "Answers", "Actions", "Test"]
H12 = ["Measure", "Recorded in", "Alert line"]
# The fixed names of section 11 and section 12, in order, each with the fact that makes it needed and the reason the
# message gives (reference/production.md, the "Needed when" column).
FAILURES_WHEN = [
    ("memory store slow or down", "always", "every design that saves something besides the run log can lose its store"),
    ("search or embedding service down", "search", "section 6 uses keyword search or embedding search"),
    ("broken model output", "model_work", "a model writes memory (A9 names `a model turns text into facts`, or a section 3 "
                                          "row has the source `agent worked out`)"),
    ("a background job crashes partway", "always", "every design that saves something besides the run log runs at least "
                                                   "its cleanup as a background job"),
    ("the queue down", "live_model", "A9 says someone waits live and a model writes memory, so that work runs from a queue"),
    ("counters drifting", "t1", "a section 3 row has no end, so it has counters kept from the fact events"),
    ("a bad extraction prompt shipped", "extracts", "A9 says a model turns text into facts"),
    ("the scheduler down", "wake", "something wakes the app: A3 says runs start on a schedule or an event, or "
                                   "prospective memory is `build`"),
    ("cleanup not running", "always", "every design that saves something besides the run log has expired rows to remove"),
]
FAILURES = [f[0] for f in FAILURES_WHEN]
MEASURES_WHEN = [
    ("correction rate per kind", "t1", "a section 3 row has no end"),
    ("share of facts past review", "t1", "a section 3 row has no end"),
    ("saved wrong vs world changed", "extracts", "A9 says a model turns text into facts"),
    ("memory read time for the slowest 5%", "live_reads", "A9 says someone waits live and the agent reads memory"),
    ("extra model calls per turn", "model_work", "a model writes memory (A9 names `a model turns text into facts`, or a "
                                                 "section 3 row has the source `agent worked out`)"),
    ("queue lag", "queue", "A9 says someone waits live and a model writes memory, or A9 says high volume"),
    ("share of turns run without memory", "reads", "the agent reads memory (a row under a memory type, or a row in section 6)"),
    ("facts saved per run", "semantic", "section 3 has a Semantic memory row"),
    ("tasks closed as no longer valid", "t2", "a task in section 7 has a premise"),
    ("risky actions waiting for confirmation", "fresh", "a risky action rests on a fact with no end"),
    ("writes dropped", "model_work", "a model writes memory (A9 names `a model turns text into facts`, or a section 3 row "
                                     "has the source `agent worked out`), so the saves that carry its work go through the spool"),
    ("jobs set to failed", "model_work", "a model writes memory (A9 names `a model turns text into facts`, or a section 3 "
                                         "row has the source `agent worked out`), so its work runs as job rows that can fail"),
]
MEASURES = [m[0] for m in MEASURES_WHEN]
ANSWERS = ["without memory", "as usual", "none"]
ACTIONS_WHEN = ["blocked", "as usual", "none"]
STORAGE = ["tables and an edges table", "a graph database", "tables"]
VOLUME_LINES = [
    ("Expected volume", "<how many users, facts and runs, and whose figures they are>"),
    ("Counters are rolled up every", "<number> <minutes, hours, days, weeks, months or years>`, or `none: <why>` when no "
                                     "row has no end"),
    ("Partition key", "<the column large tables are split by>`, or `none: <why>"),
    ("Replaced versions move to cheaper storage after", "<number> <minutes, hours, days, weeks, months or years>`, or "
                                                        "`never: <why>"),
    ("Indexed columns", "<each table: its indexed columns>"),
    ("Extra model calls per turn", "at most <number> calls"),
]
# The units "Memory reads before the model call" reads, in seconds. Units above a minute are read only to say the
# time allowed is too long for someone who waits live.
READ_UNIT_SECONDS = {"ms": 0.001, "millisecond": 0.001, "second": 1, "minute": 60, "hour": 3600, "day": 86400}
V2_DASH_KEYS[3] = V2_DASH_KEYS.get(3, []) + ["Storage"]
V2_DASH_KEYS[4] = V2_DASH_KEYS.get(4, []) + ["Memory work before the reply", "Memory reads before the model call"]
V2_DASH_KEYS[6] = V2_DASH_KEYS.get(6, []) + ["Reranker"]
V2_DASH_KEYS[12] = ["A measure is read back by"]
V2_DASH_KEYS[13] = [k for k, _ in VOLUME_LINES]
CHECK_NAMES.update({34: "nobody waits for memory", 35: "embeddings and reranker", 36: "volume", 37: "failures",
                    38: "measurements", 39: "storage"})
TESTS += [
    ("Memory never makes the person wait", 34, "t3", "A9 says someone waits live and the agent reads memory"),
    ("Embeddings are made on save, and a reranker earns its place", 35, "t35",
     "the agent saves what it searches by embedding, or section 6 has a reranker"),
    ("Volume: counters roll up and extra model calls are capped", 36, "t8",
     "A9 says high volume and something besides the run log is saved"),
]
NOT_NEEDED_BECAUSE.update({
    "t3": "A9 does not say someone waits live, or the agent reads no memory",
    "t35": "the agent does not save what it searches by embedding, and has no reranker",
    "t8": "A9 does not say high volume, or the run log is the only thing saved",
})


class Section(object):
    def __init__(self, num, line):
        self.num = num
        self.line = line
        self.table = []          # (line number, text)
        self.table_closed = False
        self.second_table = None
        self.dash = []           # (line number, text)
        self.none = None         # (line number, reason)


class Checker(object):
    def __init__(self):
        self.problems = []       # (line, tag, text)
        self.reviewer = []
        self.not_checked = []
        self.sections = {}
        self.title = None

    def bad(self, line, tag, text):
        self.problems.append((line or 0, tag, text))

    def judge(self, text):
        self.reviewer.append(text)


def short(text, n=48):
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 3] + "..."


def choice(text, options):
    """Return the option the text starts with, as a whole word or phrase, or None."""
    t = text.strip().lower()
    for o in sorted(options, key=len, reverse=True):
        lo = o.lower()
        if t.startswith(lo) and (len(t) == len(lo) or not t[len(lo)].isalnum()):
            return o
    return None


def hollow(text):
    """True when the text of a number's source, after its colon, is a blank to fill in (it starts with `<`) or names
    nothing (it holds no letter or digit, like `-` or `?`)."""
    t = text.strip()
    return t.startswith("<") or not re.search(r"[^\W_]", t)


def names(text):
    """Split on semicolons that are not inside brackets."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        if ch == ";" and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [p.strip() for p in out if p.strip()]


def by_name(text, known):
    """For a line of the form `<exact name>: <value>; ...`: split it with names(), and for each part find the known
    name (longest first, case ignored) that the part starts with, followed by a colon. Returns a list of
    (the known name or None, the rest after the colon, the part). A name that holds a colon still works."""
    out = []
    for part in names(text):
        hit = None
        for k in sorted(known, key=len, reverse=True):
            after = part[len(k):].lstrip()
            if part[:len(k)].lower() == k.lower() and after.startswith(":"):
                hit = (k, after[1:].strip(), part)
                break
        out.append(hit or (None, "", part))
    return out


def is_none(text):
    return text.strip().lower() == "none"


def find(name, pool):
    """Exact match on a name, ignoring case and outer spaces."""
    want = name.strip().lower()
    for p in pool:
        if p.strip().lower() == want:
            return p
    return None


def split_cells(text):
    t = text.strip()
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|") and not t.endswith("\\|"):
        t = t[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", t)]


def is_separator(text):
    cells = split_cells(text)
    return bool(cells) and all(re.match(r"^:?-{3,}:?$", c) for c in cells)


def read_file(path, ck):
    with open(path, "rb") as f:
        raw = f.read()
    if b"\x00" in raw:
        raise ValueError("it is not a text file")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        ck.not_checked.append("The file is not saved as UTF-8. It was read as Latin-1, so letters "
                              "outside plain English may be wrong. Save it as UTF-8.")
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def parse(lines, ck):
    cur = None          # None before section 1, a Section, or "unknown"
    notes = 0
    unread = 0
    blanks = []
    for n, line in enumerate(lines, 1):
        st = line.strip()
        if not st:
            if isinstance(cur, Section) and cur.table:
                cur.table_closed = True
            continue
        if "<fill" in st:
            blanks.append(n)
        if st.startswith(">"):
            notes += 1
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", st)
        if hm:
            level, htxt = len(hm.group(1)), hm.group(2).strip()
            if level == 1 and cur is None and ck.title is None:
                tm = re.match(r"^Memory design:\s*(\S.*)$", htxt)
                if tm:
                    ck.title = tm.group(1)
                    continue
            sm = re.match(r"^(\d+)\.\s+(.*)$", htxt) if level == 2 else None
            if sm and int(sm.group(1)) in TITLES and TITLES[int(sm.group(1))] == sm.group(2).strip():
                num = int(sm.group(1))
                if num in ck.sections:
                    ck.bad(n, "structure", "Section %d appears twice. The second one was not read." % num)
                    cur = "unknown"
                else:
                    cur = Section(num, n)
                    ck.sections[num] = cur
                continue
            ck.bad(n, "structure", "The heading \"%s\" is not one of the sections this script reads: the ten from "
                   "\"## 1. About the agent\" to \"## 10. Open questions and arbitrary numbers\", and in a design with the "
                   "line A9 also \"## 11. Failures\", \"## 12. Measurements\" and \"## 13. Volume\". Nothing under it "
                   "was read. Put its content in the section it belongs to." % short(htxt))
            cur = "unknown"
            continue
        if cur == "unknown":
            unread += 1
            continue
        if cur is None:
            ck.bad(n, "structure", "This line comes before section 1 and was not read: \"%s\"" % short(st))
            continue
        if st.startswith("|"):
            if cur.table_closed:
                if cur.second_table is None:
                    cur.second_table = n
                    ck.bad(n, "structure", "Section %d has a second table. Only the first was read. "
                           "Put every row in the one table." % cur.num)
            else:
                cur.table.append((n, st))
            continue
        if cur.table:
            cur.table_closed = True
        if st.startswith("- "):
            cur.dash.append((n, st))
            continue
        nm = re.match(r"^None:\s*(.*)$", st, re.I)
        if nm:
            cur.none = (n, nm.group(1).strip())
            continue
        ck.bad(n, "structure", "This line is not a table row, a line starting with a dash, or a note "
               "starting with >. It was not read: \"%s\"" % short(st))
    if blanks:
        shown = ", ".join(str(b) for b in blanks[:12])
        more = "" if len(blanks) <= 12 else " and %d more" % (len(blanks) - 12)
        ck.bad(blanks[0], "structure", "%d line(s) still hold a blank marked <fill: ...>: line %s%s."
               % (len(blanks), shown, more))
    if notes:
        ck.not_checked.append("%d note line(s) starting with > were not checked." % notes)
    if unread:
        ck.not_checked.append("%d line(s) under a heading this script does not know were not read. "
                              "Each such heading is listed as a problem." % unread)


def table(ck, sec, headers):
    """Return the rows of a section's table as (line, dict), or None if there is no usable table."""
    if not sec.table:
        return None
    n0, first = sec.table[0]
    if split_cells(first) != headers:
        ck.bad(n0, "structure", "Section %d: the table headings must be exactly: | %s |"
               % (sec.num, " | ".join(headers)))
        return None
    start = 1
    if len(sec.table) > 1 and is_separator(sec.table[1][1]):
        start = 2
    else:
        ck.bad(n0, "structure", "Section %d: the line of dashes under the table headings is missing." % sec.num)
    rows = []
    for n, text in sec.table[start:]:
        cells = split_cells(text)
        if len(cells) != len(headers):
            ck.bad(n, "structure", "Section %d: this row has %d cells and needs %d. It was not read."
                   % (sec.num, len(cells), len(headers)))
            continue
        rows.append((n, dict(zip(headers, cells))))
    return rows


V2_ONLY = ("\"%s\" is read only in a design that has the line \"- A9 Also true of this agent: ...\" in section 1. "
           "Add A9, or delete this.")


def dash_values(ck, sec, v2=False):
    """Return {key: (line, value)} for a section whose dash lines are 'Key: value'."""
    out = {}
    allowed = DASH_KEYS.get(sec.num, []) + (V2_DASH_KEYS.get(sec.num, []) if v2 else [])
    for n, text in sec.dash:
        m = re.match(r"^- ([^:]+):\s*(.*)$", text)
        key = find(m.group(1), allowed) if m else None
        if not key and m and not v2 and find(m.group(1), V2_DASH_KEYS.get(sec.num, [])):
            ck.bad(n, "structure", V2_ONLY % short(text))
            continue
        if not key:
            want = ("one of: " + "; ".join(allowed)) if allowed else "none (this section has no dash lines)"
            ck.bad(n, "structure", "Section %d: the line \"%s\" is not one this script reads. Allowed: %s."
                   % (sec.num, short(text), want))
            continue
        if key in out:
            ck.bad(n, "structure", "Section %d: the line \"%s:\" appears twice." % (sec.num, key))
            continue
        out[key] = (n, m.group(2).strip())
    return out


def unique(ck, rows, column, secnum):
    seen = {}
    for n, r in rows:
        name = r[column].strip()
        if not name:
            ck.bad(n, "structure", "Section %d: the \"%s\" cell is empty." % (secnum, column))
            continue
        low = name.lower()
        if low in seen:
            ck.bad(n, "structure", "Section %d: \"%s\" appears in two rows (lines %d and %d). Every name "
                   "must be unique, or checks on one row hide the other." % (secnum, short(name), seen[low], n))
        else:
            seen[low] = n
    return [r[column].strip() for _, r in rows if r[column].strip()]


def test_entries(text):
    """Return the list of (name, file) in a test cell, or None if any entry has the wrong form."""
    out = []
    for part in names(text):
        m = RE_TEST.match(RE_BRACKETS.sub("", part).strip())
        if not m or not ("/" in m.group(2) or "." in m.group(2)):
            return None
        out.append((m.group(1), m.group(2)))
    return out or None


DEFINE_PATTERNS = {
    ".py": [r"^[ \t]*(?:async[ \t]+)?def[ \t]+{n}[ \t]*\("],
    ".js": [r"\b(?:test|it)(?:\.\w+)?[ \t]*\([ \t]*['\"`]{n}['\"`]", r"\bfunction[ \t]+{n}[ \t]*\("],
    ".go": [r"^func[ \t]+(?:\([^)]*\)[ \t]*)?{n}[ \t]*\("],
    ".rs": [r"\bfn[ \t]+{n}[ \t]*\("],
    ".rb": [r"\bdef[ \t]+{n}\b", r"\b(?:test|it)[ \t]+['\"]{n}['\"]"],
    ".java": [r"\b(?:void|fun)[ \t]+{n}[ \t]*\("],
    ".cs": [r"\b(?:void|Task)[ \t]+{n}[ \t]*\("],
}
for _same, _as in ((".ts", ".js"), (".tsx", ".js"), (".jsx", ".js"), (".mjs", ".js"), (".cjs", ".js"),
                   (".kt", ".java")):
    DEFINE_PATTERNS[_same] = DEFINE_PATTERNS[_as]


def strip_comments(body, ext):
    """The body with its comments blanked, strings kept, so a test that is commented out does not count.
    Line comments are # in Ruby and // elsewhere; block comments are =begin/=end in Ruby and /* */ elsewhere."""
    line, start, end = ("#", "\n=begin", "\n=end") if ext == ".rb" else ("//", "/*", "*/")
    quotes = "\"`" if ext == ".rs" else "'\"`"       # in Rust a ' starts a lifetime, not a string
    text = "\n" + body                               # so a Ruby =begin on the first line is found
    out, i, quote = [], 1, None
    while i < len(text):
        c = text[i]
        if quote:                                    # inside a string: keep it, end at its quote or the line end
            out.append(text[i:i + 2] if c == "\\" else c)
            if c != "\\" and (c == quote or (c == "\n" and quote != "`")):
                quote = None
            i += 2 if c == "\\" else 1
        elif c in quotes:
            quote = c
            out.append(c)
            i += 1
        elif text.startswith(line, i):
            j = text.find("\n", i)
            i = len(text) if j < 0 else j
        elif text.startswith(start, i - 1 if start[0] == "\n" else i):
            j = text.find(end, i + 1)
            j = len(text) if j < 0 else j + len(end)
            out.append("\n" * text.count("\n", i, j))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def defined_in(name, body, filename):
    """True if the file defines a test with this name, False if it does not, None if the kind is unknown."""
    ext = os.path.splitext(filename)[1].lower()
    pats = DEFINE_PATTERNS.get(ext)
    if pats is None:
        return None
    if ext != ".py":                              # Python is read with its parser, which skips comments
        body = strip_comments(body, ext)
    for p in pats:
        if re.search(p.replace("{n}", re.escape(name)), body, re.M):
            return True
    return False


def _py_calls(node):
    out = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            out.add(f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else ""))
    return out


def _py_asserting(tree, seed=(), strict=False):
    """Names of the functions in tree that assert, directly or through another asserting function. strict (for
    files a test imports, often app code): a raise counts only when it raises AssertionError."""
    funcs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.setdefault(node.name, node)

    def direct(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assert):
                return True
            if isinstance(sub, ast.Raise) and (not strict or "AssertionError" in ast.dump(sub)):
                return True
        return any(c.startswith("assert") or c in ("fail", "raises") for c in _py_calls(node))

    asserting = set(seed) | set(n for n, f in funcs.items() if direct(f))
    changed = True
    while changed:
        changed = False
        for n, f in funcs.items():
            if n not in asserting and _py_calls(f) & asserting:
                asserting.add(n)
                changed = True
    return funcs, asserting


def _py_imported(tree, file_dir, project):
    """Asserting function names from Python files inside the project that this file imports."""
    found = set()
    root = os.path.realpath(project)
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = file_dir
            for _ in range(max(node.level - 1, 0)):
                base = os.path.dirname(base)
            starts = [base] if node.level else [project, file_dir]
            mod = (node.module or "").split(".") if node.module else []
            mods += [(st, mod) for st in starts]
            mods += [(st, mod + [a.name]) for st in starts for a in node.names]
        elif isinstance(node, ast.Import):
            mods += [(st, a.name.split(".")) for a in node.names for st in (project, file_dir)]
    for st, parts in mods:
        if not parts:
            continue
        for cand in (os.path.join(st, *parts) + ".py", os.path.join(st, *parts, "__init__.py")):
            real = os.path.realpath(cand)
            if not real.startswith(root + os.sep) or not os.path.isfile(real):
                continue
            try:
                with open(real, "rb") as f:
                    sub = ast.parse(f.read().decode("utf-8", "replace"))
            except (OSError, SyntaxError, ValueError):
                continue
            found |= _py_asserting(sub, strict=True)[1]
    return found


def py_test_asserts(name, body, file_dir=None, project=None):
    """For a Python file: True if the test function asserts something, directly or through a function of the
    same file, or of a project file it imports, that does; False if it does not; None if the file cannot be
    parsed; "missing" if it parses and defines no function with that name."""
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError):
        return None
    seed = _py_imported(tree, file_dir, project) if project and file_dir else set()
    funcs, asserting = _py_asserting(tree, seed)
    if name not in funcs:
        return "missing"
    return name in asserting


TEST_FORM = ("Write the test's name and its file, like `test_expired_fact_is_not_returned in "
             "tests/test_facts.py`. Several are joined with a semicolon. A note may follow in brackets.")


def check(lines, ck, project=None, as_built=False):
    parse(lines, ck)
    S = ck.sections
    if ck.title is None:
        ck.bad(1, "structure", "The file has no first line of the form `# Memory design: name of the agent`.")
    for num in (1, 2, 3, 4, 9, 10):
        if num not in S:
            ck.bad(0, "structure", "Section %d (\"## %d. %s\") is missing." % (num, num, TITLES[num]))

    # ---------------------------------------------------------------- section 1
    answers = {}
    how = {}
    if 1 in S:
        for n, text in S[1].dash:
            m = re.match(r"^- (A\d+)\s+([^:]+):\s*(.*)$", text)
            if not m or m.group(1) not in A_LABELS:
                ck.bad(n, "structure", "Section 1: the line \"%s\" is not one of A1 to A9." % short(text))
                continue
            q, label, rest = m.group(1), m.group(2).strip(), m.group(3)
            if label != A_LABELS[q]:
                ck.bad(n, "structure", "Section 1, %s: the label must be \"%s\"." % (q, A_LABELS[q]))
            if q in answers:
                ck.bad(n, "structure", "Section 1: %s appears twice." % q)
                continue
            hm = re.search(r"\(([^()]*)\)\s*$", rest)
            h = find(hm.group(1), HOW) if hm else None
            if not h:
                ck.bad(n, "check 7", "Section 1, %s: the line must end with %s." % (q, "(worked out) or (asked): an "
                       "as-built design assumes nothing" if as_built else "(worked out), (asked) or (assumed)"))
                answer = rest.strip()
            else:
                answer = rest[: hm.start()].strip()
                how[q] = (n, h)
            if not answer:
                ck.bad(n, "check 7", "Section 1, %s has no answer." % q)
            answers[q] = (n, answer)
        for q in sorted(A_LABELS):
            if q not in answers and q != "A9":          # A9 is optional
                ck.bad(S[1].line, "structure", "Section 1: %s (%s) is missing." % (q, A_LABELS[q]))
        if S[1].table:
            ck.bad(S[1].table[0][0], "structure", "Section 1 has no table. Its lines, A1 to A9, start with a dash.")

    def fixed(q, options, what):
        if q not in answers:
            return None
        n, a = answers[q]
        c = choice(a, options)
        if c is None:
            ck.bad(n, "structure", "Section 1, %s: the answer must start with %s, then a full stop and "
                   "the detail. %s" % (q, " or ".join("`%s`" % o for o in options), what))
        return c

    agents = fixed("A2", ["one agent", "several agents"], "This is the one place the number of agents is stated.")
    side = fixed("A4", ["none", "yes"], "This is the one place the design says whether the agent has side effects.")
    signal = fixed("A5", ["yes", "no"], "This is the one place the outcome signal is stated.")
    several = agents == "several agents"
    has_actions = side == "yes"
    starts = set()
    if "A3" in answers:
        n3, a3 = answers["A3"]
        head = re.split(r"\.(?:\s|$)", a3, maxsplit=1)[0]
        got3 = []
        ok3 = True
        for part in names(head):
            c = choice(part, RUN_STARTS)
            if not c or part.strip().lower() != c:
                ok3 = False
            else:
                got3.append(c)
        if not ok3 or not got3:
            ck.bad(n3, "structure", "Section 1, A3: the answer must start with how runs start: `a person`, "
                   "`a schedule` or `an event`, several joined by semicolons, then a full stop and the detail. "
                   "This is the one place the design says how runs start.")
        starts = set(got3)
    trig = [o for o, w in (("scheduled time", "a schedule"), ("event id", "an event")) if w in starts]
    # A9 switches on the lines CHECKLIST.md added in v0.2 (26 on) and states what a script cannot read elsewhere.
    v2 = "A9" in answers
    got9 = []
    if v2:
        n9, a9 = answers["A9"]
        head9 = re.split(r"\.(?:\s|$)", a9, maxsplit=1)[0]
        parts9 = names(head9)
        ok9 = bool(parts9)
        for part in parts9:
            c = find(part, A9_VALUES + ["none"])
            if not c or c in got9:
                ok9 = False
            else:
                got9.append(c)
        if "none" in got9 and len(parts9) > 1:
            ok9 = False
        if not ok9:
            ck.bad(n9, "structure", "Section 1, A9: the answer must start with `none`, or one or more of "
                   "`someone waits live`, `several routes change a fact`, `a model turns text into facts`, "
                   "`high volume`, joined by semicolons, then a full stop and the detail. This is the one place the "
                   "design says which of these hold.")
    live = "someone waits live" in got9
    routes = "several routes change a fact" in got9
    extracts = "a model turns text into facts" in got9
    volume = "high volume" in got9

    # ---------------------------------------------------------------- section 2
    decision = {}
    if 2 in S:
        rows = table(ck, S[2], H2)
        if rows is None and not S[2].table:
            ck.bad(S[2].line, "check 1", "Section 2 has no table.")
        for n, r in rows or []:
            types = names(r["Memory type"])
            d = choice(r["Decision"], ["build", "skip", "nothing to build"])
            for t in types:
                if find(t, ["Parametric memory"]):
                    if d != "nothing to build":
                        ck.bad(n, "check 1", "Section 2: Parametric memory is always `nothing to build`. "
                               "The row may be left out, since A8 names the model.")
                    continue
                mt = find(t, MEMORY_TYPES)
                if not mt:
                    ck.bad(n, "check 1", "Section 2: \"%s\" is not a memory type. Use: %s."
                           % (short(t), "; ".join(MEMORY_TYPES)))
                    continue
                if mt in decision:
                    ck.bad(n, "check 1", "Section 2: %s is decided twice." % mt)
                    continue
                if d not in ("build", "skip"):
                    ck.bad(n, "check 1", "Section 2, %s: the decision must start with `build` or `skip`." % mt)
                    continue
                decision[mt] = (n, d)
            if not types:
                ck.bad(n, "check 1", "Section 2: a row has no memory type.")
            if not r["Reason"].strip():
                ck.bad(n, "check 1", "Section 2: the row for \"%s\" has no reason." % short(r["Memory type"]))
        if rows is not None:
            for mt in MEMORY_TYPES:
                if mt not in decision:
                    ck.bad(S[2].line, "check 1", "Section 2: %s has no decision. One row may name several "
                           "types that share a decision and a reason, separated by semicolons." % mt)
        for mt in ("Working memory", "Procedural memory"):
            if mt in decision and decision[mt][1] != "build":
                ck.bad(decision[mt][0], "check 1", "Section 2: %s is always `build`. Every agent has it." % mt)
        if S[2].dash:
            dash_values(ck, S[2], v2)

    def built(mt):
        return mt in decision and decision[mt][1] == "build"

    if signal == "no" and built("Episodic memory"):
        ck.bad(decision["Episodic memory"][0], "check 6", "A5 says there is no outcome signal, so Episodic "
               "memory must be `skip`. Saved runs that nobody checked would teach the agent unchecked behaviour.")
    if decision.get("External memory and retrieval", (0, ""))[1] == "skip" and (
            built("Semantic memory") or built("Episodic memory")):
        ck.bad(decision["External memory and retrieval"][0], "check 1", "External memory and retrieval is "
               "`skip`, but semantic or episodic memory is `build`. Reading those back is retrieval, so it is `build`.")

    # ---------------------------------------------------------------- section 3
    items = []
    rows3 = []
    d3 = {}
    if 3 in S:
        rows3 = table(ck, S[3], H3)
        if rows3 is None:
            if not S[3].table:
                ck.bad(S[3].line, "check 2", "Section 3 has no table. Every agent has at least the run log row.")
            rows3 = []
        items = unique(ck, rows3, "Item", 3)
        d3 = dash_values(ck, S[3], v2)

    def listed(key):
        if key not in d3:
            return None, []
        n, v = d3[key]
        return n, ([] if is_none(v) else names(v))

    trusted_n, trusted = listed("Trusted systems")
    ownlist_n, ownlist = listed("Kinds an owner can set for themselves")
    own_else = {}
    for i, v in enumerate(ownlist):
        om = re.match(r"^(.+?)\s*\(allowed:\s*\S.*,\s*else\s+(refused|unconfirmed)\)\s*$", v, re.I)
        if not om:
            ck.bad(ownlist_n, "check 3", "\"Kinds an owner can set for themselves\": write each as `<exact item name> "
                   "(allowed: <the values accepted>, else refused)` or `..., else unconfirmed)`, saying what a "
                   "value outside the allowed list does. \"%s\" is not in that form." % short(v))
            ownlist[i] = re.split(r"\s*\(", v, maxsplit=1)[0].strip()   # the name alone, so the form error is reported once
        else:
            ownlist[i] = om.group(1).strip()
            own_else[ownlist[i].lower()] = om.group(2).lower()
    listkind_n, listkinds = listed("Kinds that hold a list")
    for key, (ln, vals) in (("Kinds an owner can set for themselves", (ownlist_n, ownlist)),
                            ("Kinds that hold a list", (listkind_n, listkinds))):
        for v in vals:
            if not find(v, items):
                ck.bad(ln, "check 3", "Section 3, \"%s\": \"%s\" is not the exact name of a row in the table."
                       % (key, short(v)))

    a6q = (" A6 says the agent reads, unchecked: \"%s\". Can a value from that, or the model's reading of it, enter "
           "this row as confirmed?" % short(answers["A6"][1], 80)) if "A6" in answers else ""
    rowinfo = {}     # item name lower -> dict
    numbers = []     # (line, number text, where)
    source_rules = []    # (line, number, unit, kinds allowed, tag, message): checked once section 10 is read
    catchup = []     # (number, unit) in the catch-up's Rule
    runlogs, auditlogs = [], []
    for n, r in rows3:
        item = r["Item"].strip()
        where = "Section 3, row \"%s\"" % short(item)
        mt = find(r["Memory type"], MEMORY_TYPES + (OTHER_TYPES_V2 if v2 else OTHER_TYPES))
        if not mt and not v2 and find(r["Memory type"], ["Fact events"]):
            ck.bad(n, "structure", V2_ONLY % short(r["Memory type"]))
        elif not mt:
            ck.bad(n, "check 2", "%s: Memory type must be one of: %s." % (
                where, "; ".join(MEMORY_TYPES + (OTHER_TYPES_V2 if v2 else OTHER_TYPES))))
        elif mt in MEMORY_TYPES and mt in decision and decision[mt][1] == "skip":
            ck.bad(n, "check 1", "%s: it is saved under %s, which section 2 marks `skip`. Either the type "
                   "is needed, or this row belongs under another type." % (where, mt))
        if mt == "Run log":
            runlogs.append((n, r))
        if mt == "Audit log":
            auditlogs.append((n, r))
        if mt in ("Audit log", "Side effect protection", "Fact events"):
            ck.judge("%s is filed as %s, which never goes into a model call. Check in the code that nothing puts "
                     "it into one. If the model reads it, it is memory and belongs under a memory type." % (where, mt))
        for col in ("Owner", "Scope"):
            if not r[col].strip():
                ck.bad(n, "check 2", "%s: \"%s\" is empty." % (where, col))
        # expiry
        parts = names(r["Expiry"])
        forms = []
        if not parts:
            ck.bad(n, "check 2", "%s: \"Expiry\" is empty." % where)
        for p in parts:
            if RE_PERIOD_AFTER.match(p):
                forms.append("period")
            elif RE_WHEN.match(p):
                forms.append("event")
                if not RE_WHEN_HOW.match(p):
                    ck.bad(n, "check 2", "%s: the expiry `%s` must end with `, told` (the app is told when the "
                           "event happens and stamps an end time) or `, asked` (the read function asks before "
                           "it returns the item). A note may follow. See reference/every-store.md." % (where, short(p, 60)))
                ck.judge("%s expires `%s`. Can code test for that event, and does the app learn of it the way "
                         "the design says?" % (where, short(p, 60)))
            elif RE_REPLACED.match(p):
                forms.append("replaced")
            elif RE_PERMANENT.match(p):
                forms.append("permanent")
                ck.judge("%s is marked `%s`. Is it really permanent, and is the reason a real one?"
                         % (where, short(p, 70)))
            elif RE_NO_END.match(p):
                forms.append("no end")
                if not v2:
                    ck.bad(n, "structure", V2_ONLY % short(p))
            else:
                ck.bad(n, "check 2", "%s: the expiry part \"%s\" is not in one of the %s forms: "
                       "`<number> <minutes, hours, days, working days, weeks, months or years> after <what>`, "
                       "`when <an event code can test>`, `replaced when <what>`, %s`permanent: <reason>`%s. "
                       "Join two forms with a semicolon."
                       % (where, short(p), "five" if v2 else "four", "" if v2 else "or ",
                          ", or `no end, checked by evidence` (Semantic memory only)" if v2 else ""))
            for num, unit in RE_NUMUNIT.findall(p):
                numbers.append((n, num, unit, where + ", expiry"))
        if v2 and "no end" in forms:                          # CHECKLIST line 26
            if mt and mt != "Semantic memory":
                ck.bad(n, "check 26", "%s: only a fact, a row under Semantic memory, can have the expiry `no end, "
                       "checked by evidence`. Give this row one of the other four forms." % where)
            if set(forms) - {"no end", "replaced"}:
                ck.bad(n, "check 26", "%s: `no end, checked by evidence` may be joined only with `replaced when "
                       "<what>`. A set time, an event or `permanent` says the opposite. Keep one." % where)
        if forms and set(forms) <= {"replaced", "event"}:     # no set time: something must end it
            if "event" not in forms:
                ends, ask = "when it is replaced", ("What replaces it, and does code check that? Being replaced is "
                                                    "enough when something will replace it.")
            else:
                ends = "when it is replaced or on an event" if "replaced" in forms else "on an event"
                ask = "What removes it if the event never comes%s?" % (
                    " and nothing replaces it" if "replaced" in forms else "")
            ck.judge("%s stops only %s (`%s`). %s If nothing ever would, it lives forever: give it a set time as "
                     "well, as for `permanent`.%s" % (where, ends, short(r["Expiry"], 60), ask,
                                                      " If people rely on it and nothing ever ends it, its expiry is "
                                                      "`no end, checked by evidence` and line 26 applies."
                                                      if v2 and "event" not in forms else ""))
        # source
        src = choice(r["Source"], SOURCES)
        system = None
        if not src:
            ck.bad(n, "check 3", "%s: Source must start with one of: %s." % (where, "; ".join(SOURCES)))
        elif src == "system record":
            sm = re.match(r"^system record:\s*(\S.*)$", r["Source"].strip(), re.I)
            if not sm:
                ck.bad(n, "check 3", "%s: write `system record: <the trusted system>`. Use `the app` for "
                       "bookkeeping the agent's own code writes." % where)
            else:
                system = sm.group(1).strip()
                if system.lower() == "the app":
                    if mt and mt not in BOOKKEEPING_TYPES:
                        ck.bad(n, "check 3", "%s: `system record: the app` is only for the run log, the audit "
                               "log, side effect records, future tasks and a marker of how far a source was read. A row under %s that is shown to the "
                               "model must name a trusted system from the \"Trusted systems\" line, or use "
                               "another source." % (where, mt))
                elif not find(system, trusted):
                    ck.bad(n, "check 3", "%s: \"%s\" is not on the \"Trusted systems\" line under the table."
                           % (where, short(system)))
        if mt == "Fact events" and not (src == "system record" and system and system.lower() == "the app"):
            ck.bad(n, "check 27", "%s: fact events are written by the app's own code, so the source is "
                   "`system record: the app`." % where)
        if mt == "Audit log" and not (src == "system record" and system and system.lower() == "the app"):
            ck.bad(n, "check 3", "%s: the audit log is written by the app's own code, so its source is "
                   "`system record: the app`." % where)
        # enters as
        ent = choice(r["Enters as"], ["confirmed", "unconfirmed"])
        if not ent:
            ck.bad(n, "check 3", "%s: \"Enters as\" must start with `confirmed` or `unconfirmed`." % where)
        if src in ("agent worked out", "outside content") and ent == "confirmed":
            ck.bad(n, "check 3", "%s: the source is `%s`, so it enters as `unconfirmed`. To let it in as "
                   "confirmed, change how it gets in, not the label." % (where, src))
        if src == "user stated":
            if ent != "confirmed":
                ck.bad(n, "check 3", "%s: a `user stated` row enters as `confirmed`. If it should wait for a "
                       "person, its source is `outside content`." % where)
            if not find(item, ownlist):
                ck.bad(n, "check 3", "%s: it is `user stated`, so its exact name must be on the line "
                       "\"Kinds an owner can set for themselves\"." % where)
        if src == "system record" and ent == "unconfirmed":
            ck.bad(n, "check 3", "%s: a `system record` enters as `confirmed`. If it is not trusted, it is "
                   "not a system record." % where)
        if ent == "confirmed" and src == "system record" and system and system.lower() != "the app":
            ck.judge("%s enters as confirmed from the trusted system \"%s\". Check in the code that it is "
                     "written by an exact lookup with no model in between.%s" % (where, short(system), a6q))
        if mt == "Semantic memory" and src in ("agent worked out", "outside content"):
            ck.judge("%s is `%s` and filed as Semantic memory. Is each item a fact about the owner? A note "
                     "about what happened in a past run is episodic memory, A5 decides whether it may exist, and "
                     "line 21 applies. A suggested rule is procedural memory." % (where, src))
        if src == "user stated":
            ck.judge("%s is something an owner can set for themselves. Does code check who the sender is, %s a "
                     "value outside the allowed list as the design says, and, for a value the model read out of the "
                     "owner's words, read the saved value back to the owner in their own terms and keep it `agent "
                     "worked out` and unconfirmed until they confirm that read-back?%s"
                     % (where, {"unconfirmed": "store unconfirmed"}.get(own_else.get(item.lower()), "refuse"), a6q))
        # size limit
        lim = r["Size limit"].strip()
        numeric = False
        same = RE_SAME_AS.match(lim)
        lm = RE_LIMIT.match(lim)
        if same:
            pass
        elif RE_BOUNDED.match(lim):
            pass
        elif lm and choice(lm.group(1), AT_LIMIT):
            num = RE_NUMUNIT.match(lim)
            # each limit given as a number has its own full-store case; 1 value that replaces the old one is the
            # one-value kind, whose case is under line 11
            numeric = not (num and num.group(1) == "1" and choice(lm.group(1), AT_LIMIT) == "replace the old one")
            if num:
                numbers.append((n, num.group(1), num.group(2), where + ", size limit"))
        else:
            ck.bad(n, "check 2", "%s: Size limit must be `<number> <of what>, then <%s>`, or "
                   "`bounded by retention`, or `same as <another row's exact name>`."
                   % (where, " | ".join(AT_LIMIT)))
        if item.lower() not in rowinfo:     # a repeated name is reported by unique(); the first row counts
            rowinfo[item.lower()] = {"line": n, "type": mt, "source": src, "enters": ent, "numeric": numeric,
                                     "expiry": r["Expiry"],
                                     "same": same.group(1).strip() if same else None, "forms": forms, "item": item}
    for key, info in rowinfo.items():
        if info["same"]:
            target = rowinfo.get(info["same"].lower())
            if not target:
                ck.bad(info["line"], "check 2", "Section 3, row \"%s\": `same as %s` does not name a row in "
                       "the table." % (short(info["item"]), short(info["same"])))
            elif target["same"]:
                ck.bad(info["line"], "check 2", "Section 3, row \"%s\": `same as` points at a row that also "
                       "says `same as`. Point at the row that holds the limit." % short(info["item"]))

    # the run log and the audit log
    holds_content = None
    if 3 in S:
        if len(runlogs) != 1:
            ck.bad(S[3].line, "check 8", "Section 3 must have exactly one row with the memory type `Run log`. "
                   "It has %d. Every agent keeps a run log for a short time, whatever else is skipped. "
                   "An audit log is not a run log." % len(runlogs))
        for n, r in runlogs:
            if not re.match(r"^system record:\s*the app\s*$", r["Source"].strip(), re.I):
                ck.bad(n, "check 8", "Section 3, the run log: its source is `system record: the app`.")
            info = rowinfo.get(r["Item"].strip().lower())
            if info and info["type"] == "Run log" and "period" not in info["forms"]:
                ck.bad(n, "check 8", "Section 3, the run log: it is kept for a short time, so its expiry "
                       "needs a part of the form `<number> <unit> after <what>`.")
            ck.judge("The run log is kept `%s`. The starting value is 30 days, and it is arbitrary. Is this "
                     "as short as finding out what happened needs? A script cannot tell short from long for this "
                     "agent." % short(r["Expiry"], 60))
        if "Run log holds content" not in d3:
            ck.bad(S[3].line, "check 8", "Section 3 needs the line `- Run log holds content: yes` or `no`. "
                   "`no` means it holds step names, sizes and errors only.")
        else:
            n, v = d3["Run log holds content"]
            holds_content = choice(v, ["yes", "no"])
            if holds_content is None:
                ck.bad(n, "check 8", "\"Run log holds content\" must start with `yes` or `no`.")
            elif holds_content == "no":
                ck.judge("The run log is said to hold no content. Check that no request text, tool result "
                         "or model output is written to it.")
                if built("Episodic memory"):
                    ck.bad(n, "check 8", "Episodic memory is `build`, and the episode writer works from the run "
                           "log (reference/episodic-memory.md), so the run log holds content. Write `yes`, or "
                           "skip episodic memory.")
        others = [i for i in rowinfo.values() if i["type"] not in ("Run log", "Audit log")]
        if len(auditlogs) > 1:
            ck.bad(auditlogs[1][0], "check 16", "Section 3 has more than one `Audit log` row.")
        if auditlogs and not others:
            ck.bad(auditlogs[0][0], "check 16", "Section 3 has an `Audit log` row but saves nothing besides the "
                   "run log, so there is nothing to audit. If the row holds something else, file it under the "
                   "memory type it belongs to.")
        for mt in ("Semantic memory", "Episodic memory", "Prospective memory"):
            if built(mt) and not any(i["type"] == mt for i in rowinfo.values()):
                ck.bad(decision[mt][0], "check 1", "Section 2 marks %s `build`, but section 3 has no row under "
                       "it. Something of that type is saved, so it needs a row." % mt)

    app_tasks = [i["item"] for i in rowinfo.values()
                 if i["type"] == "Prospective memory" and i["source"] == "system record"]
    if app_tasks:
        ck.judge("These rows are future tasks the app's own code writes, entering as confirmed: %s. Check "
                 "that each holds ids and what to do, and no text from outside or from the model that is "
                 "later shown to the model as a fact.%s" % ("; ".join(short(x, 40) for x in app_tasks), a6q))
    unconfirmed = [i for i in rowinfo.values() if i["enters"] == "unconfirmed"]
    user_rows = [i for i in rowinfo.values() if i["source"] == "user stated"]
    if 3 in S:
        if user_rows and ownlist_n is None:
            ck.bad(S[3].line, "check 3", "Section 3 has a `user stated` row, so it needs the line "
                   "`- Kinds an owner can set for themselves: ...`.")
        for v in ownlist:
            hit = rowinfo.get(v.lower())
            if hit and hit["source"] != "user stated":
                ck.bad(ownlist_n, "check 3", "\"%s\" is on the owner list but its source is not `user stated`. "
                       "Take it off the list, or change how it gets in." % short(v))
        if unconfirmed:
            if "Who may confirm an unconfirmed item" not in d3:
                ck.bad(S[3].line, "check 3", "Section 3 has rows that enter as unconfirmed, so it needs the line "
                       "`- Who may confirm an unconfirmed item: <who and where>`, or `no one: <why>` if these "
                       "rows are only ever shown as content to read.")
            else:
                n, v = d3["Who may confirm an unconfirmed item"]
                if not v:
                    ck.bad(n, "check 3", "\"Who may confirm an unconfirmed item\" is empty.")
                elif re.match(r"^no one\s*(:|$)", v, re.I):
                    if not re.match(r"^no one\s*:\s*\S", v, re.I):
                        ck.bad(n, "check 3", "Write `no one: <why>`.")
                    ck.judge("No one may confirm an unconfirmed item, and %d kind(s) enter as unconfirmed (%s). "
                             "Is each one only ever shown to the model as content to read, never used as a fact?"
                             % (len(unconfirmed), "; ".join(short(i["item"], 30) for i in unconfirmed)))
                else:
                    ck.judge("Who may confirm an unconfirmed item: `%s`. %s" % (short(v, 70), WHO_ASKS))
        relabel = [i["item"] for i in rowinfo.values()
                   if i["type"] in ("Working memory", "External memory and retrieval")]
        if relabel:
            ck.judge("These rows are filed under Working memory or External memory and retrieval: %s. "
                     "Are they really kept messages, summaries, an index or a read marker, and not facts, notes "
                   "about past runs or rules under another name?"
                     % "; ".join(short(x, 40) for x in relabel))

    # ---------------------------------------------------------------- section 4
    procs = {}
    rows4 = []
    d4 = {}
    if 4 in S:
        rows4 = table(ck, S[4], H4)
        if rows4 is None:
            if not S[4].table:
                ck.bad(S[4].line, "check 4", "Section 4 has no table. Every agent has at least one procedure.")
            rows4 = []
        elif not rows4:
            ck.bad(S[4].line, "check 4", "Section 4 has no rows. Every agent has at least one procedure.")
        unique(ck, rows4, "Procedure", 4)
        d4 = dash_values(ck, S[4], v2) if S[4].dash else {}
    all_tests = []   # (line, where, name, file)
    harmless_instr = []
    person_rules = []
    for n, r in rows4:
        name = r["Procedure"].strip()
        where = "Section 4, row \"%s\"" % short(name)
        rm = re.match(r"^(person|design):\s*(\S.*)$", r["Rule"].strip(), re.I)
        if not rm:
            ck.bad(n, "check 9", "%s: \"Rule\" must start with `person:` (the person asked for this rule) or "
                   "`design:` (the design added it), then the rule in one sentence." % where)
        elif rm.group(1).lower() == "person":
            person_rules.append(name)
        sk = choice(r["If skipped once"], IF_SKIPPED)
        lives = choice(r["Lives in"], ["code", "instructions"])
        if not sk:
            ck.bad(n, "check 4", "%s: \"If skipped once\" must start with one of: %s. A note may follow "
                   "after a comma." % (where, "; ".join(IF_SKIPPED)))
        if not lives:
            ck.bad(n, "check 4", "%s: \"Lives in\" must start with `code` or `instructions`." % where)
        if sk and sk != "harmless" and lives == "instructions":
            ck.bad(n, "check 4", "%s: skipping it once `%s`, so it lives in `code`. A sentence in the "
                   "instructions is not a rule, because the model can skip it." % (where, sk))
        if sk == "harmless" and lives == "instructions":
            harmless_instr.append(name)
        if not r["Where"].strip():
            ck.bad(n, "check 4", "%s: \"Where\" is empty." % where)
        guards = [] if is_none(r["Guards"]) else names(r["Guards"])
        if not r["Guards"].strip():
            ck.bad(n, "check 5", "%s: \"Guards\" is empty. Write the action names from section 5, or `none`." % where)
        if guards and lives == "instructions":
            ck.bad(n, "check 5", "%s: only a procedure in code can guard an action." % where)
        tests = None
        if is_none(r["Test"]):
            if lives == "code":
                ck.bad(n, "check 9", "%s: it lives in code, so it needs a test that tries to break it. %s"
                       % (where, TEST_FORM))
        else:
            tests = test_entries(r["Test"])
            if tests is None:
                ck.bad(n, "check 9", "%s: the Test cell is not in the form this script reads. %s Write `none` "
                       "for a procedure in instructions." % (where, TEST_FORM))
            else:
                for tn, tf in tests:
                    all_tests.append((n, where, tn, tf))
        procs[name.lower()] = {"line": n, "name": name, "lives": lives, "guards": guards, "skipped": sk,
                               "rule": rm.group(2).strip() if rm else ""}
    proc_rows = [i["item"] for i in rowinfo.values() if i["type"] == "Procedural memory"]
    key4 = "Episodes before a procedure is suggested"
    episode_count = False
    if proc_rows:
        if key4 not in d4 or not d4[key4][1]:
            ck.bad(S[4].line if 4 in S else 0, "check 22", "Section 3 saves procedures (%s), so section 4 needs "
                   "the line `- %s: <number> episodes`, or `none: <why no procedure is learned from past runs>`."
                   % ("; ".join(short(x, 40) for x in proc_rows), key4))
        else:
            n4, v4 = d4[key4]
            cm = re.match(r"^(\d+)\s+(episodes?)(?![A-Za-z])", v4, re.I)
            if cm:
                episode_count = True
                numbers.append((n4, cm.group(1), cm.group(2), "Section 4, episodes before a procedure is suggested"))
                if int(cm.group(1)) < 2:
                    ck.bad(n4, "check 22", "Section 4, \"%s\": one episode is not a pattern. The count is at "
                           "least 2." % key4)
                if not built("Episodic memory"):
                    ck.bad(n4, "check 22", "Section 4: procedures are suggested from episodes, but section 2 "
                           "marks Episodic memory `skip`. With no episodes, nothing can be counted: write `none: "
                           "<why>` and have a person write each procedure, or build episodic memory.")
            elif re.match(r"^none\s*:\s*\S", v4, re.I):
                ck.judge("Section 3 saves procedures (%s), and none is learned from past runs. Who writes each "
                         "one, and is it off until a person approves it?" % "; ".join(short(x, 40) for x in proc_rows))
            else:
                ck.bad(n4, "check 22", "Section 4, \"%s\" must be `<number> episodes` or `none: <why>`." % key4)
    elif key4 in d4:
        ck.bad(d4[key4][0], "structure", "Section 4 has the line \"%s\", but section 3 saves no procedures. "
               "Delete the line, or add the Procedural memory row." % key4)
    if 4 in S and rows4:
        ck.judge("Rules the person asked for, marked `person:` in section 4: %s. Check the request and the "
                 "conversation: is every rule the person stated a row there, in their meaning, in code unless "
                 "skipping it once is harmless, with a Rule that says exactly what it catches?"
                 % ("; ".join(short(x, 40) for x in person_rules) or "none"))

    def code_proc(line, label, value):
        p = procs.get(value.strip().lower())
        if not p:
            ck.bad(line, label[0], "%s: \"%s\" is not the exact name of a procedure in section 4." % (label[1], short(value)))
        elif p["lives"] != "code":
            ck.bad(line, label[0], "%s: \"%s\" lives in instructions. It must be code." % (label[1], short(value)))
        return p

    needs_wake = bool(trig) or built("Prospective memory")
    why_wake = ("A3 says runs start on %s" % " and on ".join(sorted(w for w in starts if w != "a person"))
                if trig else "prospective memory is `build`")
    gw = d4.get("What wakes the app")
    if needs_wake and (not gw or not gw[1]):
        ck.bad(gw[0] if gw else (S[4].line if 4 in S else 0), "check 8", "Section 4 needs the line `- What wakes "
               "the app: <the timer job, queue or listener, and how often it runs>`, because %s." % why_wake)
    if gw and gw[1]:
        for m in re.finditer(r"(?<![\w.,])(\d[\d,]*)\s+(%s)(?![A-Za-z])" % UNIT, gw[1], re.I):
            numbers.append((gw[0], m.group(1), m.group(2), "Section 4, how often the app is woken"))
    if gw and not needs_wake:
        ck.bad(gw[0], "structure", "Section 4 has the line \"What wakes the app\", but A3 says only a person "
               "starts runs and prospective memory is `skip`. Delete the line.")
    gc = d4.get("Missed firings are caught up by")
    if trig:
        if not gc or not gc[1]:
            ck.bad(gc[0] if gc else (S[4].line if 4 in S else 0), "check 8", "Section 4 needs the line `- Missed "
                   "firings are caught up by: <a procedure name from section 4>`, because %s, and the app may be "
                   "down when one fires." % why_wake)
        else:
            pcu = code_proc(gc[0], ("check 8", "Section 4, \"Missed firings are caught up by\""), gc[1])
            if pcu:
                for m in re.finditer(r"(?<![\w.,])(\d[\d,]*)\s+(%s)(?![A-Za-z])" % UNIT, pcu["rule"], re.I):
                    numbers.append((pcu["line"], m.group(1), m.group(2), "Section 4, how far the catch-up looks back"))
                    catchup.append((m.group(1).replace(",", ""), m.group(2).lower().rstrip("s")))
    elif gc:
        ck.bad(gc[0], "structure", "Section 4 has the line \"Missed firings are caught up by\", but A3 does not "
               "say runs start on a schedule or an event. Delete the line.")
    if harmless_instr:
        ck.judge("These procedures live in instructions and are marked harmless if skipped once: %s. "
                 "Would each really be harmless? If one costs money, sends something out, cannot be undone, "
                 "leaks data or puts something false into memory, it is code."
                 % "; ".join(short(x, 40) for x in harmless_instr))

    # ---------------------------------------------------------------- section 3, v0.2 lines (CHECKLIST 26 to 30)
    # Read after section 4, because some of them name a procedure.
    t1 = sees = catchall = owner_no = several_people = optimizer = False
    if v2 and 3 in S:
        noend = [i for i in rowinfo.values() if "no end" in i["forms"]]
        t1 = bool(noend)
        noend_names = "; ".join(short(i["item"], 40) for i in noend)
        fe_rows = [i for i in rowinfo.values() if i["type"] == "Fact events"]
        if t1:
            for key, tag, form in T1_LINES:
                if key not in d3 or not d3[key][1]:
                    ck.bad(d3[key][0] if key in d3 else S[3].line, tag, "Section 3 has a row with no end (%s), so it "
                           "needs the line %s" % (noend_names, form))
            ck.judge("These rows have no end and are kept true by evidence: %s. Is each a fact people rely on that "
                     "nothing the app hears about ever ends? A fact that costs little when wrong and that its owner "
                     "sees in use every time can be `replaced when ...` alone." % noend_names)
            if len(fe_rows) != 1:
                ck.bad(S[3].line, "check 27", "Section 3 has a row with no end, so it needs exactly one row with the "
                       "memory type `Fact events`: the record of each confirmation, correction, use and contradiction. "
                       "It has %d." % len(fe_rows))
        else:
            for key, _, _ in T1_LINES:
                if key in d3:
                    ck.bad(d3[key][0], "structure", "Section 3 has the line \"%s\", but no row has the expiry `no end, "
                           "checked by evidence`. Delete it." % key)
            for i in fe_rows:
                ck.bad(i["line"], "structure", "Section 3 has the row \"%s\", but no row has the expiry `no end, "
                       "checked by evidence`. Delete it." % short(i["item"]))
        # Facts with no end are reviewed: each row's review age and cap
        review = {}                                  # row name lower -> (age in days, cap in days)
        review_caps = {}                             # row name lower -> (cap in days, the cap as written, the row's name)
        if t1 and d3.get("Facts with no end are reviewed", (0, ""))[1]:
            nr, vr = d3["Facts with no end are reviewed"]
            noend_by = dict((i["item"].lower(), i["item"]) for i in noend)
            for part in names(vr):
                rm4 = re.match(r"^(.+?):\s*after\s+(\d[\d,]*)\s+(%s),\s*at most\s+(\d[\d,]*)\s+(%s)\s*$" % (UNIT, UNIT),
                               part, re.I)
                if not rm4:
                    ck.bad(nr, "check 26", "\"Facts with no end are reviewed\": write each as `<the row's exact name>: "
                           "after <number> <unit>, at most <number> <unit>`. \"%s\" is not in that form." % short(part))
                    continue
                rname = rm4.group(1).strip()
                if rname.lower() not in noend_by:
                    ck.bad(nr, "check 26", "\"%s\" is not the exact name of a row whose expiry is `no end, checked by "
                           "evidence`." % short(rname))
                    continue
                if rname.lower() in review:
                    ck.bad(nr, "check 26", "\"Facts with no end are reviewed\" names \"%s\" twice." % short(rname))
                    continue
                age = int(rm4.group(2).replace(",", "")) * DAYS[rm4.group(3).lower().rstrip("s")]
                cap = int(rm4.group(4).replace(",", "")) * DAYS[rm4.group(5).lower().rstrip("s")]
                review[rname.lower()] = (age, cap)
                review_caps[rname.lower()] = (cap, "%s %s" % (rm4.group(4), rm4.group(5)), rname)
                if whole(rm4.group(2)) < 1 or whole(rm4.group(4)) < 1:
                    ck.bad(nr, "check 26", "\"%s\": the review age and the cap are each at least 1 of their unit. A wait "
                           "of 0 makes every fact of this kind due at once." % short(rname))
                if age > cap:
                    ck.bad(nr, "check 26", "\"%s\": the review age (%s %s) is longer than the cap (%s %s). The cap is the "
                           "longest a fact of this kind may go without being confirmed."
                           % (short(rname), rm4.group(2), rm4.group(3), rm4.group(4), rm4.group(5)))
                numbers.append((nr, rm4.group(2), rm4.group(3), "Section 3, review age of \"%s\"" % short(rname)))
                numbers.append((nr, rm4.group(4), rm4.group(5), "Section 3, review cap of \"%s\"" % short(rname)))
            for low, item in noend_by.items():
                if low not in review and not any(low == re.split(r"\s*:", x, maxsplit=1)[0].strip().lower()
                                                 for x in names(vr)):
                    ck.bad(nr, "check 26", "The row \"%s\" has no end and is not on the line \"Facts with no end are "
                           "reviewed\"." % short(item))
        # A fact of no listed kind is saved as
        gk = d3.get("A fact of no listed kind is saved as")
        if t1 and gk and gk[1]:
            nk, vk = gk
            if re.match(r"^none\s*(:|$)", vk, re.I):
                if not re.match(r"^none\s*:\s*\S", vk, re.I):
                    ck.bad(nk, "check 26", "\"A fact of no listed kind is saved as\": write `none: <why>`.")
                elif hollow(vk.split(":", 1)[1]):
                    ck.bad(nk, "check 26", "\"A fact of no listed kind is saved as\": write `none: <why>`, with the reason "
                           "in words. " + HOLLOW_NOTE)
                elif extracts:
                    ck.bad(nk, "check 26", "A9 says a model turns text into facts, so a fact of no listed kind needs a "
                           "row to go to. Name a Semantic memory row.")
                else:
                    ck.judge("No row takes a fact of no listed kind: `%s`. Check that nothing but a form with fixed "
                             "choices can write a fact." % short(vk, 80))
            else:
                target = rowinfo.get(vk.strip().lower())
                if not target or target["type"] != "Semantic memory":
                    ck.bad(nk, "check 26", "Section 3, \"A fact of no listed kind is saved as\": \"%s\" is not the exact "
                           "name of a row under Semantic memory in the table." % short(vk))
                else:
                    catchall = True
                    if extracts and target["enters"] != "unconfirmed":     # R1.3's cautious values (review finding 6)
                        ck.bad(nk, "check 26", "\"%s\" takes facts of no listed kind, and A9 says a model turns text into "
                               "facts, so a fact filed there comes from the model and waits for a person: its \"Enters as\" "
                               "is `unconfirmed`." % short(target["item"]))
                    if "period" in target["forms"]:
                        ck.judge("Facts of no listed kind are saved under \"%s\", which is kept `%s`. The rows with no end "
                                 "are looked at again: %s. Is that time no longer than theirs, so a fact nobody listed does "
                                 "not outlive the listed ones?" % (short(target["item"]), short(target["expiry"], 60),
                                                                    short(d3.get("Facts with no end are reviewed",
                                                                                 (0, ""))[1] or "none given", 120)))
                    mine = review.get(target["item"].lower())
                    if mine and any(o[0] < mine[0] or o[1] < mine[1] for k, o in review.items()
                                    if k != target["item"].lower()):
                        ck.bad(nk, "check 26", "\"%s\" takes facts of no listed kind, so its review age and cap are the "
                               "shortest on the line \"Facts with no end are reviewed\"." % short(target["item"]))
        # The owner sees what their facts drive
        go = d3.get("The owner sees what their facts drive")
        if t1 and go and go[1]:
            no_, vo = go
            c = choice(vo, ["yes", "no"])
            if not c:
                ck.bad(no_, "check 28", "\"The owner sees what their facts drive\" must be `yes, <where they see it>` "
                       "or `no: <why>`.")
            elif c == "no":
                owner_no = True
                if not re.match(r"^no\s*:\s*\S", vo, re.I):
                    ck.bad(no_, "check 28", "\"The owner sees what their facts drive\": write `no: <why>`.")
                elif hollow(vo.split(":", 1)[1]):
                    ck.bad(no_, "check 28", "\"The owner sees what their facts drive\": write `no: <why>`, with the reason "
                           "in words. " + HOLLOW_NOTE)
                ck.judge("The owner does not see what their facts drive: `%s`. Is that true of the product? If they see "
                         "replies or actions built from a fact, line 28 applies." % short(vo, 80))
            else:
                sees = True
                if not re.match(r"^yes\s*,", vo, re.I) or hollow(vo.split(",", 1)[1]):
                    ck.bad(no_, "check 28", "\"The owner sees what their facts drive\": write `yes, <where they see it>`, "
                           "naming the place in words, like `yes, in the chat reply and on the settings screen`. \"%s\" does "
                           "not. %s" % (short(vo), HOLLOW_NOTE))
        # Review numbers
        gn = d3.get("Review numbers")
        seen_days = None                             # the seen window in days, when the part is in its form
        if t1 and gn and gn[1]:
            nn, vn = gn
            used = {}
            for part in names(vn):
                start = choice(part, REVIEW_PARTS)
                rest = part.strip()[len(start):] if start else ""
                for num, unit in RE_NUMUNIT.findall(part):
                    numbers.append((nn, num, unit, "Section 3, review numbers"))
                if start and start in used:
                    ck.bad(nn, "check 27", "\"Review numbers\" has the part `%s` twice. Keep one." % start)
                    continue
                if not start or not re.search(r"(?<![\w.,])\d[\d,]*(?:\.\d+)?\s+[A-Za-z]", rest):   # a number with its word
                    ck.bad(nn, "check 27", "\"Review numbers\": \"%s\" must start with one of the fixed parts and hold "
                           "its number with the word after it, like `each confirmation multiplies the wait by 2 times`. "
                           "The parts: %s." % (short(part), "; ".join("`%s`" % x for x in REVIEW_PARTS)))
                    continue
                used[start] = part
                rx, form, in_range = REVIEW_FORMS[start]
                fm = re.match(r"^\s*%s\s*$" % rx.replace(" ", r"\s+"), rest, re.I)
                if not fm or not in_range(fm.groups()):
                    ck.bad(nn, "check 27", "\"Review numbers\": write this part as `%s %s. \"%s\" is not in that form."
                           % (start, form, short(part)))
                elif start == "seen with no correction counts after":
                    seen_days = whole(fm.group(1)) * DAYS[rest.split()[-1].lower().rstrip("s")]
                elif "." in fm.group(1):                      # a decimal multiplier, which RE_NUMUNIT does not read
                    numbers.append((nn, fm.group(1), "times", "Section 3, review numbers"))
            for start in used:                                # a prior for a source no row with no end has
                if start.startswith("prior for ") and not any(i["source"] == start[10:-1] for i in noend):
                    ck.bad(nn, "structure", "\"Review numbers\" has the part `%s`, but no row with no end has the source "
                           "%s. Delete the part." % (start, start[10:-1]))
            needed = [("each confirmation multiplies the wait by", "check 27", ""),
                      ("a kind's own rate replaces the prior once its", "check 27", ""),
                      ("the learned review age is the age by which", "check 27", ""),
                      ("alert when a kind's rate drops by", "check 27", "")]
            for src_ in SOURCES:
                rows_ = [i["item"] for i in noend if i["source"] == src_]
                if rows_:
                    needed.append(("prior for %s:" % src_, "check 27", ", because the row \"%s\" has no end and the "
                                   "source %s" % (short(rows_[0], 40), src_)))
            if sees:
                needed.append(("seen with no correction counts after", "check 28", ", because the owner sees what "
                               "their facts drive"))
            for start, tag, why in needed:
                if start not in used:
                    ck.bad(nn, tag, "\"Review numbers\" needs the part `%s %s`%s." % (start, REVIEW_STARTING[start], why))
            if "seen with no correction counts after" in used and owner_no:
                ck.bad(nn, "structure", "\"Review numbers\" has the part \"seen with no correction counts after\", but "
                       "the line \"The owner sees what their facts drive\" does not start with `yes`. Delete the part.")
        # Fact events are kept at least as long as the seen window; their retention is listed beside the longest cap
        # (review finding 5). A row's set times are its parts `<number> <unit> after <what>`.
        if t1 and len(fe_rows) == 1:
            fe = fe_rows[0]
            kept = [whole(m.group(1)) * DAYS[m.group(2).lower()] for m in
                    (re.match(r"^(\d[\d,]*)\s+(?:working\s+)?(minute|hour|day|week|month|year)s?\s+after\s", p, re.I)
                     for p in names(fe["expiry"])) if m]
            if kept and seen_days is not None and min(kept) < seen_days:
                ck.bad(fe["line"], "check 27", "Section 3, row \"%s\": fact events are kept `%s`, which is shorter than the "
                       "window after which seen output counts (`%s`). A `used and seen` event removed before its window "
                       "passes never counts. Keep fact events at least as long as the window."
                       % (short(fe["item"]), short(fe["expiry"], 60), short(used["seen with no correction counts after"], 60)))
            if review_caps:                           # any expiry form: a set time, an event, permanent (fix round 2, N5)
                cap_days, cap_text, cap_row = max(review_caps.values())
                ck.judge("Fact events are kept `%s`, and the longest cap on the line \"Facts with no end are reviewed\" is "
                         "%s (\"%s\"). A fact can outlive its events. When cleanup removes a fact's events, does it write that "
                         "fact's totals up to then in the same transaction, so the counters can still be rebuilt? Is the time "
                         "long enough for the recompute job to measure each kind's rate?"
                         % (short(fe["expiry"], 60), cap_text, short(cap_row, 40)))
        # Rates and review ages are recomputed by
        grc = d3.get("Rates and review ages are recomputed by")
        if t1 and grc and grc[1]:
            code_proc(grc[0], ("check 27", "Section 3, \"Rates and review ages are recomputed by\""), grc[1])
        # Conflicts between facts are settled by (CHECKLIST 29)
        key29 = "Conflicts between facts are settled by"
        form29 = "`<a procedure name from section 4>; several people can set one fact: yes` or `no`"
        g29 = d3.get(key29)
        if routes:
            if not g29 or not g29[1]:
                ck.bad(g29[0] if g29 else S[3].line, "check 29", "A9 says several routes change a fact, so section 3 "
                       "needs the line `- %s: <a procedure name from section 4>; several people can set one fact: yes` "
                       "or `no`." % key29)
            else:
                parts29 = names(g29[1]) or [g29[1]]      # only semicolons: one part, which fails both checks below
                p29 = code_proc(g29[0], ("check 29", "Section 3, \"%s\"" % key29), parts29[0])
                sm29 = re.match(r"^several people can set one fact:\s*(yes|no)(?![A-Za-z])", parts29[1], re.I) \
                    if len(parts29) == 2 else None
                if not sm29:
                    ck.bad(g29[0], "check 29", "\"%s\": write %s." % (key29, form29))
                else:
                    several_people = sm29.group(1).lower() == "yes"
                detail9 = (re.split(r"\.(?:\s|$)", answers["A9"][1], maxsplit=1) + [""])[1]
                ck.judge("A9 says several routes change a fact: \"%s\". Search the code for every writer of the facts "
                         "table. Is each one a route named there, and does each go through the procedure \"%s\"?"
                         % (short(detail9, 90), short(p29["name"] if p29 else parts29[0], 60)))
        else:
            if g29:
                ck.bad(g29[0], "structure", "Section 3 has the line \"%s\", but A9 does not say several routes change a "
                       "fact. Add that to A9, or delete the line." % key29)
            if any(i["type"] == "Semantic memory" for i in rowinfo.values()):
                ck.judge("A9 does not say several routes change a fact. Search the code for a second writer of the facts "
                         "table (a screen, an import, a background job), and for more than one copy of the agent running.")
        # What a model extracts (CHECKLIST 30)
        t5_lines = [("Extraction output is checked by", "<a procedure name from section 4>"),
                    ("Extraction test set", "<where the examples live, and the script that scores a prompt against them>"),
                    ("Extraction prompt is improved by", "the optimizer script <path>, at most <number> metric calls, "
                     "at least <number> examples` or `by hand: <why>")]
        if extracts:
            for key, form in t5_lines:
                if key not in d3 or not d3[key][1]:
                    ck.bad(d3[key][0] if key in d3 else S[3].line, "check 30", "A9 says a model turns text into facts, so "
                           "section 3 needs the line `- %s: %s`." % (key, form))
            gt = d3.get("Extraction test set")
            if gt and gt[1] and (gt[1].startswith("<") or not re.search(r"[A-Za-z0-9]", gt[1])):
                ck.bad(gt[0], "check 30", "\"Extraction test set\" must say where the examples live and the script that "
                       "scores a prompt against them, like `tests/extraction_cases.json, scored by "
                       "tests/score_extraction.py`. \"%s\" does not." % short(gt[1]))
            gx = d3.get("Extraction output is checked by")
            if gx and gx[1]:
                code_proc(gx[0], ("check 30", "Section 3, \"Extraction output is checked by\""), gx[1])
            gi = d3.get("Extraction prompt is improved by")
            if gi and gi[1]:
                om5 = re.match(r"^the optimizer script\s+(\S+),\s*at most\s+(\d[\d,]*)\s+metric calls,\s*at least\s+"
                               r"(\d[\d,]*)\s+examples(?![A-Za-z])", gi[1], re.I)
                if om5 and hollow(om5.group(1)):
                    ck.bad(gi[0], "check 30", "\"Extraction prompt is improved by\": \"%s\" is not a path. Write where the "
                           "optimizer script is, like `scripts/optimize_extraction.py`. %s" % (short(om5.group(1)), HOLLOW_NOTE))
                if om5 and (whole(om5.group(2)) < 1 or whole(om5.group(3)) < 1):
                    ck.bad(gi[0], "check 30", "\"Extraction prompt is improved by\": the budget and the minimum are each at "
                           "least 1. With a budget of 0 the script can do nothing, and with a minimum of 0 it can never refuse.")
                if om5:
                    optimizer = True
                    numbers.append((gi[0], om5.group(2), "metric", "Section 3, the optimizer's budget"))
                    numbers.append((gi[0], om5.group(3), "examples", "Section 3, the optimizer's minimum"))
                    source_rules.append((gi[0], om5.group(2), "metric", ("policy",), "check 30",
                                         "`%s metric` (the optimizer's budget) is what one run may spend, which is the "
                                         "person's to set. Its source in section 10 is `[policy]` or `[policy, not told "
                                         "yet]`." % om5.group(2)))
                elif re.match(r"^by hand:\s*\S", gi[1], re.I) and hollow(gi[1].split(":", 1)[1]):
                    ck.bad(gi[0], "check 30", "\"Extraction prompt is improved by\": write `by hand: <why>`, with the reason "
                           "in words. " + HOLLOW_NOTE)
                elif re.match(r"^by hand:\s*\S", gi[1], re.I):
                    ck.judge("The extraction prompt is improved by hand: `%s`. Is the project in Python? Then the skill "
                             "sets up the optimizer script unless the person declined the package, and section 10 says "
                             "so." % short(gi[1], 80))
                else:
                    ck.bad(gi[0], "check 30", "\"Extraction prompt is improved by\" must be `the optimizer script <path>, "
                           "at most <number> metric calls, at least <number> examples`, or `by hand: <why>`.")
            nofeed = [i["item"] for i in rowinfo.values() if i["type"] == "Semantic memory"
                      and i["source"] != "system record" and (find(i["item"], listkinds) or not find(i["item"], ownlist))]
            if nofeed:      # the test set's coverage limit (Nayan's decisions on S2 re-check 2, item 2)
                ck.judge("A9 says a model turns text into facts. The extraction test set grows only from a kind that holds "
                         "one value and is on \"Kinds an owner can set for themselves\": the owner's own words that "
                         "disagree with the model's reading, or their answer to its read-back. These Semantic memory rows "
                         "are a list kind or are off that line, so a reading of the model's in them gives the test set no "
                         "row: %s. If the model extracts only into these, the test set never reaches the optimizer's "
                         "minimum. Does the person know?" % "; ".join(short(x, 40) for x in nofeed))
        else:
            for key, _ in t5_lines:
                if key in d3:
                    ck.bad(d3[key][0], "structure", "Section 3 has the line \"%s\", but A9 does not say a model turns "
                           "text into facts. Add that to A9, or delete the line." % key)
            fromtext = [i["item"] for i in rowinfo.values() if i["type"] == "Semantic memory"
                        and i["source"] in ("agent worked out", "outside content")]
            if fromtext:
                ck.judge("A9 does not say a model turns text into facts, and these Semantic memory rows are written from "
                         "text or by the model: %s. Does a model propose any of them? Then A9 names `a model turns text "
                         "into facts` and line 30 applies." % "; ".join(short(x, 40) for x in fromtext))

    # ---------------------------------------------------------------- section 5
    actions = {}
    d5 = {}
    any_approval = False
    risk = {}            # action name lower -> its risk label (CHECKLIST 32)
    risky_actions = []   # the actions whose label is not `harmless`
    risk_ok = False      # the risk line is there and every action has one label
    limited = []         # the action of each limit, in order (CHECKLIST 32)
    open_tools = []      # each open-ended tool (CHECKLIST 32)
    listed_limits = []   # the action of each limit that is a list in configuration (CHECKLIST 32)
    name_checks = []     # (line, a list's name, how to show it, function of the kinds): read with section 10
    fresh = False        # a risky action rests on a fact with no end (CHECKLIST 33)
    source_checks = []   # (line, number, unit, function of the kinds -> (tag, message) or None): read with section 10

    def section_switch(num, on, why_on, why_off):
        """Return True when the section should be read as holding rows."""
        if num not in S:
            if on:
                ck.bad(0, "structure", "Section %d (\"## %d. %s\") is missing. It is needed because %s."
                       % (num, num, TITLES[num], why_on))
            return False
        sec = S[num]
        if on is None:
            return bool(sec.table or sec.dash)      # the switch itself is broken and already reported
        if on and sec.none:
            ck.bad(sec.none[0], "structure", "Section %d says `None:`, but %s." % (num, why_on))
            return False
        if not on:
            if sec.table or sec.dash:
                ck.bad(sec.line, "structure", "Section %d has content, but %s. Leave the section out, or "
                       "change the line that says so." % (num, why_off))
            return False
        return True

    if section_switch(5, None if side is None else has_actions, "A4 says the agent has actions with side effects",
                      "A4 says the agent has no action with a side effect"):
        rows5 = table(ck, S[5], H5)
        if not rows5:
            if rows5 is not None or not S[5].table:
                ck.bad(S[5].line, "check 5", "Section 5 has no rows. A4 says the agent has actions with side effects.")
            rows5 = []
        unique(ck, rows5, "Action", 5)
        d5 = dash_values(ck, S[5], v2)
        firing_rule = bool(trig) and "a person" not in starts and not built("Prospective memory")
        seen_keys = {}
        for n, r in rows5:
            name = r["Action"].strip()
            where = "Section 5, row \"%s\"" % short(name)
            undo = choice(r["Can be undone"], ["yes", "no"])
            if not undo:
                ck.bad(n, "check 5", "%s: \"Can be undone\" must start with `yes` or `no`." % where)
            appr = choice(r["Needs approval"], ["yes", "no"])
            if not appr:
                ck.bad(n, "check 5", "%s: \"Needs approval\" must start with `yes` or `no`." % where)
            any_approval = any_approval or appr == "yes"
            contents = []
            if not names(r["Content it carries"]):
                ck.bad(n, "check 5", "%s: \"Content it carries\" is empty. Write one or more of: %s."
                       % (where, "; ".join(CONTENTS)))
            for part in names(r["Content it carries"]):
                c = choice(part, CONTENTS)
                if not c:
                    ck.bad(n, "check 5", "%s: \"Content it carries\": \"%s\" must start with one of: %s. Join "
                           "several with semicolons." % (where, short(part), "; ".join(CONTENTS)))
                else:
                    contents.append(c)
            risky = any(c in RISKY_CONTENT for c in contents)
            key = r["Idempotency key"].strip()
            in_key = re.findall(r"\{([^{}]*)\}", key)
            declared = {}
            parts_ok = True
            for p in names(r["Key parts"]):
                pm = re.match(r"^([^:]+):\s*(.*)$", p)
                origin = choice(pm.group(2), KEY_ORIGINS) if pm else None
                if not pm or not origin:
                    parts_ok = False
                    ck.bad(n, "check 5", "%s: the key part \"%s\" must be written `<part>: stored id`, "
                           "`<part>: step name`, `<part>: scheduled time`, `<part>: event id` or `<part>: item id`. "
                           "Each is the same on every try: a stored id is saved before the first try, a scheduled "
                           "time is the time the trigger was set for, an event id comes with the event, an item id "
                           "is the id of the thing acted on, saved before the firing by something other than the "
                           "run. Nothing else may go in a key: not the time a run started, not an id the run made "
                           "for itself, not a random value, not a count of tries."
                           % (where, short(p)))
                else:
                    declared[pm.group(1).strip()] = origin
                    need_start = {"scheduled time": "a schedule", "event id": "an event"}.get(origin)
                    if need_start and starts and need_start not in starts and not (
                            origin == "scheduled time" and built("Prospective memory")):
                        ck.bad(n, "check 5", "%s: the key part `%s` is marked `%s`, but A3 does not say runs start "
                               "on %s%s. Use the kind of part that matches how this action's runs start."
                               % (where, pm.group(1).strip(), origin, need_start,
                                  " and there are no future tasks" if origin == "scheduled time" else ""))
            if not key:
                ck.bad(n, "check 5", "%s: \"Idempotency key\" is empty." % where)
            elif not in_key or any(not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", k.strip()) for k in in_key):
                ck.bad(n, "check 5", "%s: the key needs at least one named part in curly braces, like "
                       "`task-{task_id}-send`. A part is a plain name (letters, digits, underscores), not "
                       "code. Without a part, every action of this kind shares one key." % where)
            else:
                for k in in_key:
                    if k.strip() not in declared:
                        ck.bad(n, "check 5", "%s: the key part {%s} is not listed in \"Key parts\"." % (where, k.strip()))
                for k in declared:
                    if k not in [x.strip() for x in in_key]:
                        ck.bad(n, "check 5", "%s: \"Key parts\" lists `%s`, which is not in the key." % (where, k))
                if parts_ok and declared and not any(v in IDENTIFYING for v in declared.values()):
                    ck.bad(n, "check 5", "%s: no part of the key names one action (a stored id, a scheduled "
                           "time, an event id or an item id), so two different actions of this kind would share one "
                           "key." % where)
                if parts_ok and declared and firing_rule and not any(
                        v in trig or v == "item id" for v in declared.values()):
                    ck.bad(n, "check 18", "%s: runs start only on %s, and nothing is written ahead for each "
                           "firing (prospective memory is `skip`). A trigger that fires twice starts two runs, "
                           "and an id made by each run, such as a run id, differs between them. Put a part in the "
                           "key that is the same across firings for the same thing: %s, or `<part>: item id` (the "
                           "id of the thing acted on, saved before the firing by something other than the run)."
                           % (where, " or ".join(sorted(starts)), " or ".join("`<part>: %s`" % t for t in trig)))
                tkey = re.sub(r"\s+", "", key.lower())
                if tkey in seen_keys:
                    ck.bad(n, "check 5", "%s: its key `%s` is the same as the key of \"%s\". The second action "
                           "would be taken for a repeat of the first and dropped. Put a step name in each key."
                           % (where, key, short(seen_keys[tkey])))
                else:
                    seen_keys[tkey] = name
                asks = {"stored id": "each stored id is saved before the first try and never made fresh on a retry "
                                     "or by each run (a run id)",
                        "item id": "each item id is saved before the firing by something other than the run, so "
                                   "every firing about the same thing makes the same key",
                        "event id": "each event id is the id the event carries, the same when the event is "
                                    "delivered again or run by the catch-up"}
                kinds = [asks[k] for k in ("stored id", "item id", "event id") if k in declared.values()]
                if parts_ok and kinds:
                    again = (" Does the same item need this action again on a later firing? If yes, the key needs "
                             "a part that changes per occurrence." if "item id" in declared.values() else "")
                    ck.judge("%s: key `%s`, parts %s. Check in the code that %s.%s"
                             % (where, key, "; ".join("%s is %s %s" % (k, "an" if v[:1] in "aeiou" else "a", v)
                                                      for k, v in sorted(declared.items())),
                                "; and that ".join(kinds), again))
                    sched = sorted(k for k, v in declared.items() if v == "scheduled time")
                    if sched:
                        ck.judge("%s: %s marked `scheduled time`. Check in the code that each is the time the "
                                 "trigger was set for, fixed before the first try, and not the time the run began, and that one "
                                 "thing is never acted on in two slots (a catch-up overlapping the next run). If it can "
                                 "be, key it by an item id. The test for a late second firing shows the first part." % (where, ", ".join("`%s`" % k for k in sched)))
            guards = names(r["Guarded by"])
            if not guards or is_none(r["Guarded by"]):
                ck.bad(n, "check 5", "%s: \"Guarded by\" names at least one procedure from section 4. An action "
                       "is never unguarded: the procedure that stops a repeat always guards it." % where)
                guards = []
            for g in guards:
                p = procs.get(g.lower())
                if not p:
                    ck.bad(n, "check 5", "%s: the guard \"%s\" is not the exact name of a procedure in section 4."
                           % (where, short(g)))
                elif p["lives"] != "code":
                    ck.bad(n, "check 5", "%s: the guard \"%s\" lives in instructions. A guard lives in code."
                           % (where, short(g)))
                elif not find(name, p["guards"]):
                    ck.bad(n, "check 5", "%s: the guard \"%s\" does not list this action in its Guards cell in "
                           "section 4." % (where, short(g)))
            if undo == "no" and appr == "no":
                ck.judge("%s cannot be undone and needs no approval. Is that intended?" % where)
            if contents and not risky:
                ck.judge("%s says it carries only `%s`. Check in the code that nothing read from outside or "
                         "written by the model goes into what it sends. If anything does, the cell is wrong, and "
                         "the content check and its tests are missing." % (where, "; ".join(contents)))
            actions[name.lower()] = {"line": n, "name": name, "approval": appr == "yes", "risky": risky,
                                     "guards": [g.lower() for g in guards]}
        # the lines under the table
        def need(key, what):
            if key not in d5 or not d5[key][1]:
                ck.bad(S[5].line, "check 5", "Section 5 needs the line `- %s: %s`." % (key, what))
                return None
            return d5[key]

        def role(key, what, only=None, many=False):
            got = need(key, what)
            if not got:
                return
            n, whole = got
            for v in (names(whole) if many else [whole]):
                p = procs.get(v.lower())
                if not p:
                    ck.bad(n, "check 5", "Section 5, \"%s\": \"%s\" is not the exact name of a procedure in "
                           "section 4." % (key, short(v)))
                    continue
                if p["lives"] != "code":
                    ck.bad(n, "check 5", "Section 5, \"%s\": \"%s\" lives in instructions. It must be code."
                           % (key, short(v)))
                for a in actions.values():
                    if only and not only(a):
                        continue
                    if v.lower() not in a["guards"]:
                        ck.bad(a["line"], "check 5", "Section 5, row \"%s\": \"Guarded by\" must include \"%s\", "
                               "the procedure named on the line \"%s\"." % (short(a["name"]), short(p["name"]), key))

        def store(key, what):
            got = need(key, what)
            if not got:
                return
            n, v = got
            info = rowinfo.get(v.lower())
            if not info:
                ck.bad(n, "check 5", "Section 5, \"%s\": \"%s\" is not the exact name of a row in section 3."
                       % (key, short(v)))
            elif info["type"] != "Side effect protection":
                ck.bad(n, "check 5", "Section 5, \"%s\": that row in section 3 must have the memory type "
                       "`Side effect protection`." % key)
            elif key == "Actions taken are recorded in":
                kept = [(a.replace(",", ""), b.lower().rstrip("s")) for a, b in
                        re.findall(r"(?<![\w.,])(\d[\d,]*)\s+(%s)\s+after" % UNIT, info["expiry"], re.I)]
                for cn, cu in catchup:
                    for kn, ku in kept:
                        if ku == cu and int(kn) <= int(cn):
                            ck.bad(info["line"], "check 18", "Section 3, row \"%s\": it is kept %s %s(s), and the "
                                   "catch-up looks back %s %s(s). Keep the record of actions longer than the "
                                   "catch-up, or a missed firing caught up late finds no key and acts twice."
                                   % (short(info["item"]), kn, ku, cn, cu))
                        elif ku != cu:
                            ck.judge("The record of actions is kept %s %s(s) and the catch-up looks back %s %s(s). "
                                     "Is the first longer?" % (kn, ku, cn, cu))
                ck.judge("The record of actions expires `%s`. Is that longer than any window in which an event can "
                         "be delivered again or a service retries, so a late repeat still finds its key?"
                         % short(info["expiry"], 60))

        if actions:
            role("Repeats are stopped by", "<the procedure in section 4 that every action passes through>")
            store("Actions taken are recorded in", "<the exact name of a row in section 3>")
            got = need("Unfinished actions are picked up by", " | ".join(PICKED_UP_BY))
            for c in ([choice(x, PICKED_UP_BY) for x in names(got[1])] if got else []):
                if not c:
                    ck.bad(got[0], "check 5", "\"Unfinished actions are picked up by\": each value starts with one "
                           "of: %s. Several are joined by semicolons." % "; ".join(PICKED_UP_BY))
                elif c == "a person" and starts and "a person" not in starts:
                    ck.bad(got[0], "check 5", "\"Unfinished actions are picked up by: a person\" fits only when a "
                           "person starts the runs, and A3 says runs start on %s. Use `a job over the "
                           "actions record`, or `the stuck task job` when future tasks start the actions."
                           % "; ".join(sorted(starts)))
                elif c == "the stuck task job" and not built("Prospective memory"):
                    ck.bad(got[0], "check 5", "\"Unfinished actions are picked up by: the stuck task job\" needs "
                           "prospective memory, which section 2 marks `skip`. Use `a job over the actions "
                           "record` or `a person`.")
            got = need("A claimed action is held for", "<number> <minutes, hours, days, weeks, months or years>, "
                       "longer than one action can take")
            if got:
                if not RE_SPAN.match(got[1]):
                    ck.bad(got[0], "check 5", "\"A claimed action is held for\" must start with `<number> <minutes, "
                           "hours, days, weeks, months or years>`: how long a run that claimed an action holds it "
                           "before another run may take it over.")
                for num, unit in RE_NUMUNIT.findall(got[1]):
                    numbers.append((got[0], num, unit, "Section 5, how long a claimed action is held"))
            if any(a["risky"] and not a["approval"] for a in actions.values()):
                role("Content checked before sending by", "<the procedure or procedures in section 4 that check "
                     "outside or model-written content before it is sent, joined by semicolons>",
                     only=lambda a: a["risky"] and not a["approval"], many=True)
                got_c = d5.get("Content checked before sending by")
                pcs = [procs[x.lower()] for x in names(got_c[1])
                       if x.lower() in procs] if got_c and got_c[1] else []
                if pcs:
                    ck.judge("Content checked before sending by %s, for %s. Rules: %s. Together, do they check what "
                             "fits where the content goes (secrets, who it reaches, and whatever inside the content "
                             "could act on its own there), and does the code catch every case the rules promise?"
                             % ("; ".join('"%s"' % short(pc["name"], 40) for pc in pcs),
                                "; ".join(a["name"] for a in actions.values() if a["risky"] and not a["approval"]),
                                "; ".join('"%s"' % short(pc["rule"], 100) for pc in pcs)))
            elif "Content checked before sending by" in d5:
                ck.bad(d5["Content checked before sending by"][0], "structure", "Section 5 has the line \"Content "
                       "checked before sending by\", but no action carries outside content or agent worked out "
                       "without approval. Delete the line.")
            if any_approval:
                role("Approval is checked by", "<the procedure in section 4 that checks the approval>",
                     only=lambda a: a["approval"])
                store("Approvals are saved in", "<the exact name of a row in section 3>")
                got_w = need("Who may approve", "<a role, as the app knows it>")
                if got_w:
                    ck.judge("Who may approve: `%s`. %s" % (short(got_w[1], 70), WHO_ASKS))
                got = need("An approval lasts", "<number> <unit>, `until the scheduled time plus <number> <unit>`, "
                           "or `when <event>, told` or `, asked`")
                if got:
                    if RE_WHEN_HOW.match(got[1]):
                        ck.judge("An approval lasts `%s`. Does code end it when that happens, and can it happen at "
                                 "all if the person walks away?" % short(got[1], 60))
                    elif not RE_LASTS.match(got[1]):
                        ck.bad(got[0], "check 5", "\"An approval lasts\" must start with `<number> <minutes, "
                               "hours, days, weeks, months or years>`, `until the scheduled time plus "
                               "<number> <unit>`, or be `when <an event code can test>, told` or `, asked`.")
                    for num, unit in RE_NUMUNIT.findall(got[1]):
                        numbers.append((got[0], num, unit, "Section 5, how long an approval lasts"))
        # Risk labels, limits and open-ended tools (CHECKLIST 32, T7). v0.2 only.
        if v2 and actions:
            act_names = [a["name"] for a in actions.values()]
            undo_of = dict((r5["Action"].strip().lower(), choice(r5["Can be undone"], ["yes", "no"])) for _, r5 in rows5)
            key_r = "Risk of each action"
            gr = d5.get(key_r)
            if not gr or not gr[1]:
                ck.bad(gr[0] if gr else S[5].line, "check 32", "Section 5 needs the line `- %s: <the action's exact name>: "
                       "<one of the \"if skipped once\" values>; ...`." % key_r)
            else:
                nr5, vr5 = gr
                risk_ok = True
                count32 = dict((a.lower(), 0) for a in act_names)
                for name, rest, part in by_name(vr5, act_names):
                    if name is None:
                        risk_ok = False
                        ck.bad(nr5, "check 32", "\"%s\": \"%s\" does not start with the exact name of an action in section "
                               "5 and a colon." % (key_r, short(part)))
                        continue
                    count32[name.lower()] += 1
                    if count32[name.lower()] > 1:
                        continue
                    label = choice(rest, IF_SKIPPED)
                    if not label:
                        risk_ok = False
                        ck.bad(nr5, "check 32", "\"%s\", \"%s\": the label must start with one of: %s."
                               % (key_r, short(name), "; ".join(IF_SKIPPED)))
                        continue
                    risk[name.lower()] = label
                    if label == "harmless" and undo_of.get(name.lower()) == "no":
                        ck.bad(actions[name.lower()]["line"], "check 32", "Section 5, row \"%s\": it cannot be undone, so its "
                               "risk is not `harmless`. Use the label that says what goes wrong." % short(name))
                for a in act_names:
                    if count32[a.lower()] != 1:
                        risk_ok = False
                        ck.bad(nr5, "check 32", "\"%s\": the action \"%s\" is named %d times. Each action has one label."
                               % (key_r, short(a), count32[a.lower()]))
                if risk:
                    ck.judge("Risk of each action: %s. Open the risk table in the code: does it hold these labels and one "
                             "for every other tool the model is given, and does nothing the model passes change one?"
                             % "; ".join("%s: %s" % (actions[k]["name"], v) for k, v in risk.items()))
            risky_actions = [actions[k]["name"] for k in actions if risk.get(k) not in (None, "harmless")]
            # Limits on an amount or on who is reached: the business's numbers (R2.4, R4.4)
            key_l = "Limits"
            form_l = ("`<the action's exact name>: at most <a whole number> <of what, per what>` or `<the action's exact "
                      "name>: only to <the name of a list in configuration>`")
            gl = d5.get(key_l)
            if not gl or not gl[1]:
                ck.bad(gl[0] if gl else S[5].line, "check 32", "Section 5 needs the line `- %s: <the action's exact name>: "
                       "at most <a whole number> <of what, per what>` or `- %s: <the action's exact name>: only to <the name "
                       "of a list in configuration>`, several joined by semicolons, or `- %s: none: <why>`."
                       % (key_l, key_l, key_l))
            elif re.match(r"^none\s*(:|$)", gl[1], re.I):
                nm5 = re.match(r"^none\s*:\s*(\S.*)$", gl[1], re.I)
                if not nm5 or hollow(nm5.group(1)):
                    ck.bad(gl[0], "check 32", "\"%s\": write `none: <why>`, with the reason no action needs a cap. A part in "
                           "angle brackets is a blank to fill in, and a mark with no letter or digit names nothing." % key_l)
                else:
                    ck.judge("Limits: `%s`. Can any action pay an amount, or reach people, that the person would want "
                             "capped?" % short(gl[1], 80))
            else:
                nl5, vl5 = gl

                def cap_rule(shown, name, what):
                    """The source rule of one limit: policy wherever it is written, and approval while not told yet."""
                    def rule(kinds):
                        if kinds - set(["policy", "not told yet"]):
                            return ("check 32", "%s is a limit the business sets. Its source in section 10 is `[policy]` or "
                                    "`[policy, not told yet]`, wherever the %s is written." % (shown, what))
                        if "not told yet" in kinds and not actions[name.lower()]["approval"]:
                            return ("check 25", "%s is marked `[policy, not told yet]`, so \"%s\" needs approval until the "
                                    "person gives the %s. Its \"Needs approval\" cell must start with `yes`."
                                    % (shown, short(name), what))
                        return None
                    return rule
                if not names(vl5):
                    ck.bad(nl5, "check 32", "\"%s\": write each as %s, or the whole line as `none: <why>`. \"%s\" names "
                           "nothing." % (key_l, form_l, short(vl5)))
                for name, rest, part in by_name(vl5, act_names):
                    lm5 = re.match(r"^at most\s+(\d[\d,]*)\s+[A-Za-z]", rest, re.I)
                    om5 = re.match(r"^only to\s+(\S.*)$", rest, re.I)
                    if om5 and not hollow(om5.group(1)):  # a list of who may be reached, kept in configuration
                        lname5 = om5.group(1).strip()
                        listed_limits.append(name)
                        name_checks.append((nl5, lname5, "`%s` (the list on \"%s\")" % (short(lname5, 40), short(name)),
                                            cap_rule("The list `%s` (limit on \"%s\")" % (short(lname5, 40), short(name)),
                                                     name, "list")))
                        continue
                    if not lm5:                           # an unknown name leaves nothing after it, so it lands here
                        ck.bad(nl5, "check 32", "\"%s\": write each as %s, or the whole line as `none: <why>`. \"%s\" is "
                               "not in that form." % (key_l, form_l, short(part)))
                        continue
                    pairs5 = RE_NUMUNIT.findall(rest)   # every number in the part is a limit (a second cap, a period)
                    if len(RE_NUMBER.findall(rest)) != len(pairs5):
                        ck.bad(nl5, "check 32", "\"%s\", \"%s\": every number in a limit has its word after it, like "
                               "`at most 500 dollars per day`. \"%s\" has a number with none." % (key_l, short(name), short(rest)))
                        continue
                    if any(int(x.replace(",", "")) == 0 for x, _ in pairs5):
                        ck.bad(nl5, "check 32", "\"%s\", \"%s\": a limit of 0 means the action can never run. An action that "
                               "must never run is not given to the model: take it out of section 5." % (key_l, short(name)))
                        continue
                    limited.append(name)
                    for num5, unit5 in pairs5:
                        numbers.append((nl5, num5, unit5, "Section 5, limit on \"%s\"" % short(name)))
                        source_checks.append((nl5, num5, unit5, cap_rule("`%s %s` (limit on \"%s\")" % (num5, unit5, short(name)),
                                                                         name, "number")))
            # Open-ended tools: their effect depends on what the model passes them
            key_o = "Open-ended tools"
            form_o = "`none`, or `<the action's exact name>: checked by <a procedure name from section 4>`"
            go5 = d5.get(key_o)
            if not go5 or not go5[1]:
                ck.bad(go5[0] if go5 else S[5].line, "check 32", "Section 5 needs the line `- %s: none`, or `- %s: <the "
                       "action's exact name>: checked by <a procedure name from section 4>`, several joined by semicolons."
                       % (key_o, key_o))
            elif is_none(go5[1]):
                ck.judge("Open-ended tools: none. Search the tools for one that takes a command, an address or a query "
                         "from the model.")
            else:
                no5, vo5 = go5
                if not names(vo5):
                    ck.bad(no5, "check 32", "\"%s\": write %s, several joined by semicolons. \"%s\" names nothing."
                           % (key_o, form_o, short(vo5)))
                for name, rest, part in by_name(vo5, act_names):
                    om5 = re.match(r"^checked by\s+(\S.*)$", rest, re.I)
                    if not om5:                           # an unknown name leaves nothing after it, so it lands here
                        ck.bad(no5, "check 32", "\"%s\": write %s, several joined by semicolons. \"%s\" is not in that form."
                               % (key_o, form_o, short(part)))
                        continue
                    if name in open_tools:
                        ck.bad(no5, "check 32", "\"%s\" names \"%s\" twice." % (key_o, short(name)))
                        continue
                    open_tools.append(name)
                    if risk.get(name.lower()) == "harmless":
                        ck.bad(no5, "check 32", "\"%s\": \"%s\" is labelled `harmless` on the line \"Risk of each action\". "
                               "An open-ended tool's label is the worst a command no rule covers could do, so it is never "
                               "`harmless`." % (key_o, short(name)))
                    p5 = code_proc(no5, ("check 32", "Section 5, \"%s\"" % key_o), om5.group(1))
                    if p5:
                        ck.judge("Open-ended tools: \"%s\" is checked by \"%s\". Open its function: does it refuse a "
                                 "command a code rule forbids, and treat a command no rule covers as risky, so it runs only "
                                 "with an approval for that exact command?" % (short(name), short(p5["name"], 60)))
                    if p5 and (not find(name, p5["guards"]) or p5["name"].lower() not in actions[name.lower()]["guards"]):
                        ck.bad(no5, "check 32", "\"%s\": the procedure \"%s\" must list \"%s\" in its Guards cell, and the "
                               "action must name it under \"Guarded by\"." % (key_o, short(p5["name"]), short(name)))
            # Facts with no end that a risky action rests on are confirmed lately (CHECKLIST 33, T1 and T7)
            key_f = "Before a risky action these facts are fresh"
            gf = d5.get(key_f)
            noend_rows = dict((i["item"].lower(), i["item"]) for i in rowinfo.values() if "no end" in i["forms"])
            ages = review if 3 in S else {}          # row name lower -> (review age in days, cap in days), section 3
            if t1 and risky_actions:
                if not gf or not gf[1]:
                    ck.bad(gf[0] if gf else S[5].line, "check 33", "Section 3 has a fact with no end and these actions are "
                           "risky: %s. Section 5 needs the line `- %s: <the action's exact name>: <a no-end row's exact "
                           "name> within <number> <unit>; ...`, with `<the action's exact name>: none` for an action no such "
                           "fact decides." % ("; ".join(risky_actions), key_f))
                else:
                    nf5, vf5 = gf
                    count33 = dict((a.lower(), 0) for a in risky_actions)
                    for name, rest, part in by_name(vf5, risky_actions):
                        if name is None:
                            ck.bad(nf5, "check 33", "\"%s\": \"%s\" does not start with the exact name of a risky action in "
                                   "section 5 and a colon." % (key_f, short(part)))
                            continue
                        count33[name.lower()] += 1
                        if count33[name.lower()] > 1:
                            continue
                        if is_none(rest):
                            ck.judge("\"%s\" is risky and the design says no fact with no end decides it. Read its code: "
                                     "does such a fact decide who it reaches, how much, or whether it happens?" % short(name))
                            continue
                        got33, pos33 = [], 0
                        while pos33 < len(rest):
                            m33 = RE_FRESH_PART.match(rest, pos33)
                            if not m33:
                                break
                            got33.append(m33)
                            pos33 = m33.end()
                        if not got33 or pos33 < len(rest):
                            what33 = ("\"%s\" is not in that form" % short(rest)) if rest.strip() else "Nothing follows the colon"
                            ck.bad(nf5, "check 33", "\"%s\", \"%s\": write `<a no-end row's exact name> within <number> "
                                   "<unit>`, several joined by commas, or `none`. %s." % (key_f, short(name), what33))
                            continue
                        rows33 = set()
                        for m33 in got33:
                            rn33 = m33.group(1).strip()
                            row33 = noend_rows.get(rn33.lower())
                            if not row33:
                                ck.bad(nf5, "check 33", "\"%s\", \"%s\": \"%s\" is not the exact name of a row whose expiry "
                                       "is `no end, checked by evidence`." % (key_f, short(name), short(rn33)))
                                continue
                            if row33.lower() in rows33:
                                ck.bad(nf5, "check 33", "\"%s\", \"%s\" names \"%s\" twice." % (key_f, short(name), short(row33)))
                                continue
                            rows33.add(row33.lower())
                            fresh = True
                            numbers.append((nf5, m33.group(2), m33.group(3), "Section 5, freshness of \"%s\" before \"%s\""
                                            % (short(row33), short(name))))
                            win = int(m33.group(2).replace(",", "")) * DAYS[m33.group(3).lower().rstrip("s")]
                            if win == 0:
                                ck.bad(nf5, "check 33", "\"%s\", \"%s\": a freshness window of 0 means the fact is stale a "
                                       "moment after it is confirmed, so the action never runs." % (short(name), short(row33)))
                            elif row33.lower() in ages and win >= ages[row33.lower()][0]:
                                ck.bad(nf5, "check 33", "\"%s\", \"%s\": the freshness window (%s %s) is not shorter than "
                                       "the row's review age (%s days). A fact inside its review age would otherwise never "
                                       "be asked about before a risky action." % (short(name), short(row33), m33.group(2),
                                                                                  m33.group(3), "%g" % ages[row33.lower()][0]))
                    for a in risky_actions:
                        if count33[a.lower()] != 1:
                            ck.bad(nf5, "check 33", "\"%s\": the risky action \"%s\" is named %d times. Each risky action is "
                                   "named once." % (key_f, short(a), count33[a.lower()]))
            elif gf and (not t1 or risk_ok):
                ck.bad(gf[0], "structure", "Section 5 has the line \"%s\", but %s. Delete it."
                       % (key_f, "no row in section 3 has the expiry `no end, checked by evidence`" if not t1
                          else "no action is risky: every label is `harmless`"))
    # Side effect protection holds only the two records section 5 names. Anything else filed there
    # would escape the tests that saved memory needs.
    protection_names = set()
    for key in ("Actions taken are recorded in", "Approvals are saved in"):
        if key in d5 and d5[key][1]:
            protection_names.add(d5[key][1].strip().lower())
    for info in rowinfo.values():
        if info["type"] == "Side effect protection" and info["item"].lower() not in protection_names:
            ck.bad(info["line"], "check 3", "Section 3, row \"%s\": `Side effect protection` is only for the "
                   "record of actions taken and the approvals, each named on its line in section 5. Anything "
                   "else is saved under the memory type it belongs to." % short(info["item"]))
    for p in procs.values():
        for g in p["guards"]:
            a = actions.get(g.lower())
            if not a:
                ck.bad(p["line"], "check 5", "Section 4, row \"%s\": it guards \"%s\", which is not the exact "
                       "name of an action in section 5." % (short(p["name"]), short(g)))
            elif p["name"].lower() not in a["guards"]:
                ck.bad(p["line"], "check 5", "Section 4, row \"%s\": it says it guards \"%s\", but that action's "
                       "\"Guarded by\" cell does not name it." % (short(p["name"]), short(g)))

    # ---------------------------------------------------------------- section 3 lines that name other sections
    if 3 in S:
        others = [i for i in rowinfo.values() if i["type"] not in ("Run log", "Audit log")]
        audit_in = d3.get("Audit log kept in")
        actions_record = d5.get("Actions taken are recorded in", (0, ""))[1].strip().lower()
        if audit_in:
            n_ai, v_ai = audit_in
            if not re.match(r"^the record of actions taken\s*\.?\s*$", v_ai, re.I):
                ck.bad(n_ai, "check 16", "\"Audit log kept in\" must be `the record of actions taken`. Otherwise "
                       "leave the line out and add an `Audit log` row.")
            elif auditlogs:
                ck.bad(n_ai, "check 16", "Section 3 has an `Audit log` row and the line \"Audit log kept in\". "
                       "Keep one.")
            elif not (len(others) == 1 and others[0]["item"].lower() == actions_record):
                ck.bad(n_ai, "check 16", "\"Audit log kept in: the record of actions taken\" fits only when the "
                       "record of actions taken, named in section 5, is the one thing saved besides the run log. "
                       "Here other rows are saved too, so add an `Audit log` row.")
        elif others and not auditlogs:
            ck.bad(S[3].line, "check 16", "Section 3 saves something besides the run log, so it needs one row with "
                   "the memory type `Audit log`: the record of every write, change, delete and approval. (When "
                   "the record of actions taken is the one thing saved, its kept history may be the audit log: the "
                   "line `- Audit log kept in: the record of actions taken`.)")
        ge = d3.get("Expired rows are removed by")
        if others:
            if not ge or not ge[1]:
                ck.bad(ge[0] if ge else S[3].line, "check 16", "Section 3 saves something besides the run log, so "
                       "it needs the line `- Expired rows are removed by: <a procedure name from section 4>`, the "
                       "code that removes expired rows on a timer or at the start of each run.")
            else:
                code_proc(ge[0], ("check 16", "Section 3, \"Expired rows are removed by\""), ge[1])
        elif ge:
            ck.bad(ge[0], "structure", "Section 3 has the line \"Expired rows are removed by\", but the run log is "
                   "the only thing saved. Its cleanup is tested under \"Every run is logged\". Delete the line.")

    # ---------------------------------------------------------------- section 6
    retrieval_rows = 0
    filtered_rows = 0
    search_where = []
    search_used = False
    rerank, embed_where = False, []      # v0.2 slice 4: a reranker in use; where the embedding search rows look
    if section_switch(6, built("External memory and retrieval") if "External memory and retrieval" in decision else None,
                      "section 2 marks External memory and retrieval `build`",
                      "section 2 marks External memory and retrieval `skip`"):
        rows6 = table(ck, S[6], H6)
        if not rows6:
            if rows6 is not None or not S[6].table:
                ck.bad(S[6].line, "check 17", "Section 6 has no rows. Section 2 marks retrieval `build`.")
            rows6 = []
        unique(ck, rows6, "What it looks for", 6)
        d6 = dash_values(ck, S[6], v2)
        for n, r in rows6:
            where = "Section 6, row \"%s\"" % short(r["What it looks for"])
            retrieval_rows += 1
            if is_none(r["Filters"]):
                ck.judge("%s has no filters. Does its source hold only items every user may see? If it holds "
                         "items that belong to different owners, it needs an owner filter, and line 15 applies."
                         % where)
            elif r["Filters"].strip():
                filtered_rows += 1
            for part in r["Method"].split("+"):
                m = choice(part, METHODS)
                if not m:
                    ck.bad(n, "check 17", "%s: Method must be one of: %s. Join two with a plus sign."
                           % (where, "; ".join(METHODS)))
                elif m in SEARCH_METHODS:
                    search_used = True
                    search_where.append(r["Where it lives"].strip().lower())
                elif m == "new items":
                    ck.judge("%s reads new items with a marker. Does the code flag an item that fails every time, "
                             "move the marker past it so the rest are read, and test that?" % where)
                elif m == "no search":
                    ck.judge("%s is loaded whole on every call (`no search`). Is the source small, and will it "
                             "stay small?" % where)
            for col in ("Where it lives", "Filters", "Checks on results"):
                if not r[col].strip():
                    ck.bad(n, "check 17", "%s: \"%s\" is empty. Write `none` if there truly is none." % (where, col))
        names6 = [r6["What it looks for"].strip().lower() for _, r6 in rows6]
        gs = d6.get("Settings a person keeps current")
        if gs:
            for part in names(gs[1]):
                pm = re.match(r"^(.+?):\s*checked by\s+(.+)$", part, re.I)
                if not pm:
                    ck.bad(gs[0], "check 17", "\"Settings a person keeps current\": write `<the row's exact name>: "
                           "checked by <a procedure name from section 4>`, several joined by semicolons.")
                    continue
                if pm.group(1).strip().lower() not in names6:
                    ck.bad(gs[0], "check 17", "\"Settings a person keeps current\": \"%s\" is not the exact name "
                           "of a row in section 6." % short(pm.group(1)))
                code_proc(gs[0], ("check 17", "Section 6, \"Settings a person keeps current\""), pm.group(2))
        if rows6:
            ck.judge("Section 6: does any row read a setting a person keeps that changes over time, where a stale "
                     "value would make the agent do the wrong thing? Each such row is on the line `Settings a "
                     "person keeps current`, with the procedure in code that checks it is current. A setting that "
                     "does not change needs nothing beyond being read fresh.")
        if search_used and ("Retrieval test set" not in d6 or not d6["Retrieval test set"][1]):
            ck.bad(S[6].line, "check 17", "Section 6 uses keyword search or embedding search, so it needs the "
                   "line `- Retrieval test set: <where the questions with known right answers live>`.")
        # v0.2, CHECKLIST 35 (slice 4): the reranker line. The line itself is read only with A9 (dash_values).
        for _, r6 in rows6:
            if any(choice(part, METHODS) == "embedding search" for part in r6["Method"].split("+")):
                embed_where.append(r6["Where it lives"].strip().lower())
        rr_form = ("\"Reranker\": write `none: <why>`, or `yes: wide pass <n> of <m>, reaches the model <k> of <m>; reranks "
                   "<c> candidates and keeps <j> results`: the two counts from the same retrieval test set, then how many "
                   "results the reranker takes and how many of them it keeps.")
        grr = d6.get("Reranker")
        if v2 and search_used and (not grr or not grr[1]):
            ck.bad(grr[0] if grr else S[6].line, "check 35", "Section 6 uses keyword search or embedding search, so it "
                   "needs the line `- Reranker: none: <why, or not measured yet>`, or `- Reranker: yes: wide pass <n> of "
                   "<m>, reaches the model <k> of <m>; reranks <c> candidates and keeps <j> results`, the two counts from the "
                   "retrieval test set and the reranker's two settings.")
        elif grr and not search_used:
            ck.bad(grr[0], "structure", "Section 6 has the line \"Reranker\", but no row uses keyword search or embedding "
                   "search, so there is nothing to re-order. Delete it.")
        elif grr:
            nrr, vrr = grr
            mrn = re.match(r"^none\s*:\s*(\S.*)$", vrr, re.I)
            mry = re.match(r"^yes:\s*wide pass\s+(\d[\d,]*)\s+of\s+(\d[\d,]*),\s*reaches the model\s+(\d[\d,]*)\s+of\s+"
                           r"(\d[\d,]*);\s*reranks\s+(\d[\d,]*)\s+(candidates?)\s+and keeps\s+(\d[\d,]*)\s+(results?)(?!\w)",
                           vrr, re.I)
            if mrn and not hollow(mrn.group(1)):
                ck.judge("No reranker: `%s`. Run the retrieval test set: is the right item usually in a wide first pass "
                         "and often missing from what reaches the model? Then one is needed." % short(vrr, 90))
            elif mry:
                wn, wm, kn, km, rc, rj = [int(mry.group(g).replace(",", "")) for g in (1, 2, 3, 4, 5, 7)]
                if wm != km or wm < 1 or wn > wm or kn > km:
                    ck.bad(nrr, "check 35", rr_form)
                elif rj < 1 or rj >= rc:
                    ck.bad(nrr, "check 35", "\"Reranker\": it keeps %d of the %d candidates it reranks. It keeps at least 1 "
                           "and fewer than it takes, or the same results reach the model as without it." % (rj, rc))
                elif kn >= wn:
                    ck.bad(nrr, "check 35", "\"Reranker\": the right item reaches the model for %d of %d questions and is "
                           "in the wide pass for %d. A reranker can only move up what the wide pass found, so it is worth "
                           "adding only when the first is lower." % (kn, km, wn))
                elif 2 * wn <= wm:
                    ck.bad(nrr, "check 35", "\"Reranker\": the right item is in the wide pass for %d of %d questions, not "
                           "more than half, so it is not usually there. A reranker only re-orders what the wide pass "
                           "found: the search itself needs work first. Write `none: <why>`." % (wn, wm))
                else:
                    rerank = True
                    ck.judge("Reranker: it takes the first %d results and keeps %d. On the test set the right item is in the "
                             "wide pass for %d of %d questions and reaches the model for %d of %d. Is it usually in the wide "
                             "pass, and often missing from what reaches the model, so the reranker has something to bring "
                             "up? Run the retrieval test set with these settings: does it give these counts?"
                             % (rc, rj, wn, wm, kn, km))
                    # Every number on the line is in section 10 (coordinator Q8 and QS4-1): the two test-set counts, with the
                    # word after them (`46 of`, `28 of`), measured; the two settings, tuning values.
                    for g, what in ((1, "the reranker's count for the wide pass"),
                                    (3, "the reranker's count for what reaches the model")):
                        numbers.append((nrr, mry.group(g), "of", "Section 6, %s" % what))
                        source_rules.append((nrr, mry.group(g), "of", ("data",), "check 35",
                                             "`%s of` (%s) is a result of the retrieval test set. Its source in section 10 "
                                             "is `[data: <the test>]`." % (mry.group(g), what)))
                    for g, what in ((5, "how many candidates the reranker takes"), (7, "how many results the reranker keeps")):
                        numbers.append((nrr, mry.group(g), mry.group(g + 1), "Section 6, %s" % what))
                        source_rules.append((nrr, mry.group(g), mry.group(g + 1), ("default", "data", "requirement"), "check 35",
                                             "`%s %s` (%s) is a tuning value, not the business's to set. Its source in section "
                                             "10 is `[default: <the measure that would show it is wrong>]`, or `[data: <the "
                                             "test>]` once it is measured." % (mry.group(g), mry.group(g + 1), what)))
            else:
                ck.bad(nrr, "check 35", rr_form)

    # ---------------------------------------------------------------- section 7
    task_rows = 0
    approval_tasks = False
    premises = []        # (task, the values its premise names), for each task with a premise (CHECKLIST 31)
    t2 = False
    confirm_tasks = False    # a task can wait for confirmation of a fact a risky action rests on (CHECKLIST 33)
    if section_switch(7,built("Prospective memory") if "Prospective memory" in decision else None, "section 2 marks Prospective memory `build`",
                      "section 2 marks Prospective memory `skip`"):
        rows7 = table(ck, S[7], H7)
        if not rows7:
            if rows7 is not None or not S[7].table:
                ck.bad(S[7].line, "check 20", "Section 7 has no rows. Section 2 marks prospective memory `build`.")
            rows7 = []
        unique(ck, rows7, "Task", 7)
        d7 = dash_values(ck, S[7], v2)
        for n, r in rows7:
            where = "Section 7, row \"%s\"" % short(r["Task"])
            task_rows += 1
            if not choice(r["Trigger"], TRIGGERS):
                ck.bad(n, "check 20", "%s: Trigger must start with `time`, `event` or `condition`, then the "
                       "detail." % where)
            have = [s.strip().lower() for s in re.split(r"[;,]", r["Statuses"])]
            if any(h.startswith("waiting for approval") for h in have):
                approval_tasks = True
            missing = [s for s in NEEDED_STATUSES if s not in have]
            if missing:
                ck.bad(n, "check 20", "%s: Statuses must include %s, separated by commas. `running` is what "
                       "lets a crashed task be found." % (where, ", ".join("`%s`" % s for s in missing)))
            for col in ("Holds", "Checks again on waking"):
                if not r[col].strip():
                    ck.bad(n, "check 20", "%s: \"%s\" is empty." % (where, col))
        key = "A running task goes back to pending after"
        if key not in d7 or not RE_SPAN.match(d7[key][1]):
            ck.bad(d7[key][0] if key in d7 else S[7].line, "check 20", "Section 7 needs the line `- %s: <number> "
                   "<minutes, hours, days, weeks, months or years>`." % key)
        else:
            for num, unit in RE_NUMUNIT.findall(d7[key][1]):
                numbers.append((d7[key][0], num, unit, "Section 7, the stuck task time"))
        # The premise of each task, and what closes a task whose record changed (CHECKLIST 31, T2). v0.2 only.
        tasks7 = [r["Task"].strip() for _, r in rows7 if r["Task"].strip()]
        key31 = "Premise of each task"
        key31c = "A changed record cancels or replaces its tasks through"
        form31 = "`version of <the record>`, `values of <the record>: <value>, <value>` or `none: <why>`"
        premise_ok = False                            # the line is there and every part of it was read
        if v2 and tasks7:
            statuses7 = {}
            for n7, r7 in rows7:
                statuses7.setdefault(r7["Task"].strip().lower(),
                                     (n7, [s.strip().lower() for s in re.split(r"[;,]", r7["Statuses"])]))
            gp = d7.get(key31)
            if not gp or not gp[1]:
                ck.bad(gp[0] if gp else S[7].line, "check 31", "Section 7 needs the line `- %s: <the task's exact name>: "
                       "version of <the record>`, or `...: values of <the record>: <value>, <value>`, or `...: none: "
                       "<why>`, one per task, joined by semicolons." % key31)
            else:
                np7, vp7 = gp
                premise_ok = True
                count31 = dict((t.lower(), 0) for t in tasks7)
                for name, rest, part in by_name(vp7, tasks7):
                    if name is None:
                        premise_ok = False
                        ck.bad(np7, "check 31", "\"%s\": \"%s\" does not start with the exact name of a task in section 7 "
                               "and a colon." % (key31, short(part)))
                        continue
                    count31[name.lower()] += 1
                    if count31[name.lower()] > 1:
                        continue
                    vm = re.match(r"^version of\s+(\S.*)$", rest, re.I)
                    lm = re.match(r"^values of\s+([^:]+):\s*(\S.*)$", rest, re.I)
                    nm = re.match(r"^none\s*:\s*(\S.*)$", rest, re.I)
                    vals = [x.strip() for x in lm.group(2).split(",") if x.strip()] if lm else []
                    if vm and not hollow(vm.group(1)):
                        premises.append((name, ["the record's version"]))
                    elif lm and vals and not hollow(lm.group(1)) and not any(hollow(x) for x in vals):
                        premises.append((name, vals))
                    elif nm and not hollow(nm.group(1)):
                        ck.judge("The task \"%s\" has no premise: `%s`. What was it scheduled on? If a record's date, "
                                 "owner or status, that is its premise." % (short(name), short(nm.group(1), 80)))
                    else:
                        premise_ok = False
                        what31 = ("\"%s\" is not in that form" % short(rest)) if rest.strip() else "Nothing follows the colon"
                        ck.bad(np7, "check 31", "\"%s\", \"%s\": write %s. %s. A part in angle brackets is a blank to fill "
                               "in, and a mark with no letter or digit names nothing." % (key31, short(name), form31, what31))
                for t in tasks7:
                    if count31[t.lower()] != 1:
                        premise_ok = False
                        ck.bad(np7, "check 31", "\"%s\": the task \"%s\" is named %d times. Each task has one premise."
                               % (key31, short(t), count31[t.lower()]))
            for task, _ in premises:
                ln7, have7 = statuses7[task.lower()]
                if not any(choice(h, ["no longer valid"]) for h in have7):
                    ck.bad(ln7, "check 31", "Section 7, row \"%s\": it has a premise, so its statuses include `no longer "
                           "valid`, the status of a task that woke to find its premise changed." % short(task))
            t2 = bool(premises)
            gc31 = d7.get(key31c)
            if t2:
                if not gc31 or not gc31[1]:
                    ck.bad(gc31[0] if gc31 else S[7].line, "check 31", "Section 7 needs the line `- %s: <a procedure name "
                           "from section 4>`, because a task has a premise: changing its record closes or replaces its "
                           "open tasks in the same transaction." % key31c)
                else:
                    p31 = code_proc(gc31[0], ("check 31", "Section 7, \"%s\"" % key31c), gc31[1])
                    if p31:
                        ck.judge("%s: \"%s\". Open its function: does it close or replace the record's open tasks whose "
                                 "premise the change touches, in the same transaction as the change?"
                                 % (key31c, short(p31["name"], 60)))
            elif gc31 and premise_ok:
                ck.bad(gc31[0], "structure", "Section 7 has the line \"%s\", but no task has a premise. Delete it."
                       % key31c)
            # A task that can wait for confirmation of a fact a risky action rests on (CHECKLIST 33, T1 and T7 with a task)
            key33w = "A wait for confirmation ends after"
            gw33 = d7.get(key33w)
            waiters = [t7 for t7 in tasks7 if any(choice(h, ["waiting for confirmation"]) for h in statuses7[t7.lower()][1])]
            confirm_tasks = bool(fresh and waiters)
            if confirm_tasks:
                mw33 = re.match(r"^(\d[\d,]*)\s+(%s)(?![A-Za-z0-9])" % UNIT, gw33[1], re.I) if gw33 else None
                if not gw33 or not gw33[1]:
                    ck.bad(gw33[0] if gw33 else S[7].line, "check 33", "Section 7 needs the line `- %s: <number> <minutes, "
                           "hours, days, weeks, months or years>`, because a task can wait for confirmation (%s): with no "
                           "answer, the wait ends and a person is told." % (key33w, "; ".join(short(w, 40) for w in waiters)))
                elif not mw33:
                    ck.bad(gw33[0], "check 33", "\"%s\" must start with `<number> <minutes, hours, days, weeks, months or "
                           "years>`. \"%s\" does not." % (key33w, short(gw33[1])))
                elif int(mw33.group(1).replace(",", "")) == 0:
                    ck.bad(gw33[0], "check 33", "\"%s\": a wait of 0 ends before anyone can answer, so the task always fails."
                           % key33w)
                else:
                    numbers.append((gw33[0], mw33.group(1), mw33.group(2), "Section 7, how long a wait for confirmation lasts"))
            elif gw33:
                why33 = ("no risky action rests on a fact with no end, so nothing waits for confirmation" if waiters
                         else "no task lists `waiting for confirmation`")
                ck.bad(gw33[0], "structure", "Section 7 has the line \"%s\", but %s. Delete it." % (key33w, why33))
            if fresh and not waiters:
                ck.judge("A risky action rests on a fact with no end, and section 7 has tasks (%s), none with the status "
                         "`waiting for confirmation`. Does a task start one of those risky actions? Then that task lists "
                         "`waiting for confirmation`, section 7 has the line `%s`, and line 33 asks for two more tests."
                         % ("; ".join(short(t7, 40) for t7 in tasks7), key33w))

    # ---------------------------------------------------------------- section 8
    if section_switch(8, None if agents is None else several, "A2 says several agents share memory", "A2 says one agent uses the memory"):
        rows8 = table(ck, S[8], H8) or []
        writers = {}
        seen_agents = set()
        for n, r in rows8:
            seen_agents.add(r["Agent"].strip().lower())
            st = find(r["Store"], items)
            if not st:
                ck.bad(n, "check 15", "Section 8: \"%s\" is not the exact name of a row in section 3. "
                       "Name each store, one row per agent and store." % short(r["Store"]))
            rd, wr = choice(r["Read"], ["yes", "no"]), choice(r["Write"], ["yes", "no"])
            if not rd or not wr:
                ck.bad(n, "check 15", "Section 8: Read and Write must each start with `yes` or `no`.")
            if st and wr == "yes":
                writers.setdefault(st, []).append(r["Agent"].strip())
        if len(seen_agents) < 2:
            ck.bad(S[8].line, "check 15", "Section 8 must list at least two agents, since A2 says several "
                   "share memory.")
        if S[8].dash:
            dash_values(ck, S[8], v2)
        for st, who in sorted(writers.items()):
            if len(who) > 1:
                ck.judge("Section 8: %d agents may write \"%s\" (%s). Does each one need to?"
                         % (len(who), short(st, 40), "; ".join(who)))

    # ---------------------------------------------------------------- section 9
    types_saved = [i["type"] for i in rowinfo.values()]
    sources_saved = [i["source"] for i in rowinfo.values()]
    memory_rows = any(t in MEMORY_TYPES for t in types_saved)
    stored = any(t != "Run log" for t in types_saved)
    model_written = [i["item"] for i in rowinfo.values() if i["source"] == "agent worked out"
                     and i["type"] not in ("Episodic memory", "Procedural memory")]
    semantic_outside = [i["item"] for i in rowinfo.values() if i["source"] == "outside content"
                        and i["type"] == "Semantic memory"]
    episodes_maybe = "Episodic memory" not in types_saved and bool(model_written or semantic_outside)
    suggestions_maybe = "Procedural memory" not in types_saved and bool(model_written)
    if episodes_maybe or suggestions_maybe:
        parts = []
        if episodes_maybe:
            parts.append("If any holds notes about what happened in past runs, it is episodic memory: A5 decides "
                         "whether it may exist, and line 21 applies.")
        if suggestions_maybe:
            parts.append("If any holds rules the model suggested, it is procedural memory, and line 22 applies.")
        segs = []
        if model_written:
            segs.append("These rows are written by the model and filed outside episodic and procedural memory: %s."
                        % "; ".join(short(x, 40) for x in model_written))
        if episodes_maybe and semantic_outside:
            segs.append("These rows hold outside content and are filed as Semantic memory: %s."
                        % "; ".join(short(x, 40) for x in semantic_outside))
        ck.judge("%s %s" % (" ".join(segs), " ".join(parts)))
    rows_fed = any(s in ("user stated", "outside content", "agent worked out") for s in sources_saved)
    action_content = any(a["risky"] for a in actions.values())
    facts = {
        "always": True,
        "memory_rows": memory_rows,
        "model_fed": rows_fed or action_content,
        "content": stored or holds_content == "yes",
        "stored": stored,
        "episodes_maybe": episodes_maybe,
        "suggestions_maybe": suggestions_maybe,
        "owners": memory_rows or filtered_rows > 0 or several,
        "search": search_used,
        "actions": bool(actions),
        "approvals": any_approval,
        "tasks": task_rows > 0 or "Prospective memory" in types_saved,
        "episodes": "Episodic memory" in types_saved,
        "suggestions": "Procedural memory" in types_saved,
        "v2": v2,
        "t1": v2 and t1,
        "t1_seen": v2 and t1 and sees,
        "t4": v2 and routes,
        "t5": v2 and extracts,
    }
    cf = {"trig": trig, "v2": v2, "catchall": catchall, "sees": sees, "several_people": several_people,
          "optimizer": optimizer,
          "indexed": any(i["type"] == "External memory and retrieval" or i["item"].lower() in search_where
                         for i in rowinfo.values()),
          "event_expiry": any("event" in i["forms"] for i in rowinfo.values() if i["type"] != "Run log"),
          "row_fed": rows_fed, "owner_set": any(i["source"] == "user stated" for i in rowinfo.values()),
          "action_content": action_content, "several": several,
          "full_stores": [i["item"] for i in rowinfo.values() if i["numeric"] and i["type"] != "Run log"],
          "content": facts["content"], "approval_tasks": approval_tasks, "episode_count": episode_count,
          "actions": bool(actions), "approvals": any_approval,
          "confirmable": bool(unconfirmed) and "Who may confirm an unconfirmed item" in d3
          and not re.match(r"^no one\s*(:|$)", d3["Who may confirm an unconfirmed item"][1] or "no one", re.I)}
    # v0.2 slice S3 (CHECKLIST 31 to 33)
    facts.update({"t2": v2 and t2, "t7": v2 and bool(actions), "fresh": v2 and fresh})
    cf.update({"premises": premises, "limits": limited, "open_tools": open_tools, "list_limits": listed_limits,
               "confirm_tasks": confirm_tasks})
    if not v2 and (stored or actions or task_rows > 0):
        ck.not_checked.append("The lines CHECKLIST.md added in v0.2 (26 on) were not checked, because section 1 has "
                              "no A9 line. A design written or reviewed with v0.2 has one whenever the agent saves "
                              "anything besides the run log, has an action or has a future task.")
    if search_used and not cf["indexed"]:
        ck.judge("Section 6 searches a source that section 3 does not save, so the case of an old or deleted item "
                 "found by its old wording is not asked for. Does the agent really keep no copy or index of it?")
    check_production(ck, S, v2, live, volume, extracts, t1, d3, d4, rowinfo, actions, needs_wake, search_used,
                     retrieval_rows, rerank, embed_where, numbers, source_rules, all_tests, facts, cf)
    listed_tests = {}
    if 9 in S:
        rows9 = table(ck, S[9], H9)
        if rows9 is None:
            if not S[9].table:
                ck.bad(S[9].line, "check 8", "Section 9 has no table.")
            rows9 = []
        unique(ck, rows9, "Test", 9)
        if S[9].dash:
            dash_values(ck, S[9], v2)
        known = [t[0] for t in TESTS]
        for n, r in rows9:
            t = find(r["Test"], known)
            if not t:
                ck.bad(n, "structure", "Section 9: \"%s\" is not one of the standing tests. The test for a "
                       "procedure goes in that procedure's row in section 4." % short(r["Test"]))
                continue
            entries = test_entries(r["Where"])
            line_no = [x[1] for x in TESTS if x[0] == t][0]
            if entries is None:
                ck.bad(n, "check %d" % line_no,
                       "Section 9, \"%s\": the Where cell is not in the form this script reads. %s"
                       % (short(t), TEST_FORM))
            else:
                for tn, tf in entries:
                    all_tests.append((n, "Section 9, \"%s\"" % short(t), tn, tf))
                cs = cases_for(line_no, cf)
                distinct = len(set((a, os.path.normpath(b)) for a, b in entries))
                if distinct < len(cs):
                    ck.bad(n, "check %d" % line_no, "Section 9, \"%s\" names %d test(s) and needs %d, one per "
                           "case: %s." % (short(t), distinct, len(cs), "; ".join(cs)))
            listed_tests[t] = n
        for name, line_no, needs, why in TESTS:
            if facts[needs] and name not in listed_tests:
                ck.bad(S[9].line, "check %d" % line_no, "Section 9 has no row for the test \"%s\". It is "
                       "required because %s. Changing a row's label does not remove it." % (name, why))

    # ---------------------------------------------------------------- section 10
    if as_built:                              # S5: as built, a file and line like store.py:55 is no number
        numbers[:] = [x for x in numbers
                      if not (0 < x[0] <= len(lines) and from_file_line(lines[x[0] - 1], x[1], x[2]))]
    if 10 in S:
        sec = S[10]
        if sec.table:
            ck.bad(sec.table[0][0], "structure", "Section 10 has no table. Each item is a line starting with a dash.")
        if not sec.dash:
            ck.bad(sec.line, "check 7", "Section 10 is empty. It lists every assumed answer and every number "
                   "in the design, each with its source.")
        for q in sorted(how):
            n, h = how[q]
            if h != "assumed":
                continue
            hits = [(ln, t) for ln, t in sec.dash
                    if re.search(r"(?<![A-Za-z0-9])%s(?![0-9])[^.]*\bassumed\b" % q, t)]
            if not hits:
                ck.bad(n, "check 7", "Section 1, %s is marked assumed, so section 10 needs a line that starts "
                       "`- %s assumed: ...` and ends `(told)` or `(not told yet: <how and when>)`, so the person "
                       "sees it." % (q, q))
            elif not any(re.search(r"\((told|not told yet:\s*\S[^()]*)\)\.?\s*$", t, re.I) for _, t in hits):
                ck.bad(hits[0][0], "check 7", "Section 10, %s assumed: the line must end `(told)`, or `(not told "
                       "yet: <how and when the person will be told>)`." % q)
        # Where each number comes from (CHECKLIST line 25). Spans are found on the line with its commas removed,
        # the same string numbers are matched on. A source's own text is read from the line as written.
        lines10 = []                                  # (line, text without commas, [(start, end, kind or None)])
        notold10 = set()                              # (line, start) of each [policy, not told yet]
        not_told, interim, measured, no_source = [], [], [], []
        given, worked = [], []                        # lines with [policy], lines with a requirement
        for ln, t in sec.dash:
            p = t.replace(",", "")
            spans = []
            flags = set()
            results = []                              # (start in p, result after the last =, shown) per requirement
            for mp, mt in zip(RE_SQUARE.finditer(p), RE_SQUARE.finditer(t)):
                inner = mt.group(1).strip()
                kind = choice(inner, NUMBER_SOURCES)
                spans.append((mp.start(), mp.end(), kind))
                shown = short(inner, 60)
                if kind is None:
                    ck.bad(ln, "check 25", "Section 10: \"[%s]\" is not a source. Square brackets in section 10 hold "
                           "a source and nothing else: %s." % (shown, SOURCE_FORMS))
                elif kind == "policy":
                    form = " ".join(inner.split()).lower()
                    if form == "policy, not told yet":
                        flags.add("not told")
                        notold10.add((ln, mp.start()))
                    elif as_built and re.match(r"^policy:\s*unknown\b", inner, re.I):
                        pass                  # as built, who chose it is not in the code: marked unknown (S5)
                    elif form != "policy":
                        ck.bad(ln, "check 25", "Section 10: write \"[policy]\" when the person gave the number, or "
                               "\"[policy, not told yet]\" when they have not. \"[%s]\" is neither." % shown)
                    else:
                        flags.add("given")
                elif kind == "requirement":
                    after = inner[len("requirement"):].lstrip()
                    rest = after[1:].strip() if after.startswith(":") else after
                    res = re.match(r"\s*(\d[\d,]*(?:\.\d+)?)", rest.rsplit("=", 1)[-1])     # the result
                    why = None
                    if not after.startswith(":"):
                        why = "write a colon after the word requirement, then the arithmetic"
                    elif hollow(rest):
                        why = ("after the colon comes the real arithmetic, not a blank in angle brackets or a mark "
                               "with no letter or digit")
                    elif "=" not in rest:
                        why = "it has no = sign"
                    elif not re.search(r"\d", rest):
                        why = "it holds no digit, and the numbers of the arithmetic are written in digits"
                    if why:
                        ck.bad(ln, "check 25", "Section 10: \"[%s]\" must show the arithmetic the number is worked "
                               "out from, with an = sign, like \"[requirement: 2 seconds for the reply - 1.5 seconds "
                               "for the model = 500 ms]\": %s." % (shown, why))
                    else:
                        flags.add("worked out")
                        results.append((mp.start(), res.group(1).replace(",", "") if res else None, shown))
                elif kind == "data":
                    dm = re.match(r"^data:\s*(.*?)(,\s*interim)?\s*$", inner, re.I)
                    name = dm.group(1).strip() if dm else ""
                    if not name or hollow(name) or name.lower() == "interim":
                        ck.bad(ln, "check 25", "Section 10: \"[%s]\" must name the query or the test the number "
                               "comes from, like \"[data: count of facts per owner in the facts table]\", or "
                               "\"[data: <the query or test>, interim]\" while it has not been run. The part in angle "
                               "brackets is a blank to fill in, and a mark with no letter or digit names nothing."
                               % shown)
                    else:
                        flags.add("interim" if dm.group(2) else "measured")
                elif not re.match(r"^default:\s*\S", inner, re.I) or hollow(inner.split(":", 1)[1]):
                    ck.bad(ln, "check 25", "Section 10: \"[%s]\" must name the measure that would show the number "
                           "is wrong, like \"[default: how often the limit is reached]\". The part in angle brackets "
                           "of \"[default: <the measure that would show it is wrong>]\" is a blank to fill in, and a "
                           "mark with no letter or digit names nothing." % shown)
            left = RE_SQUARE.sub("", t)
            if "[" in left or "]" in left:
                ck.bad(ln, "check 25", "Section 10: the line \"%s\" has a square bracket that is not part of a "
                       "source. Square brackets in section 10 hold a source and nothing else: %s."
                       % (short(t), SOURCE_FORMS))
            if "not told" in flags:
                not_told.append(t)
            if "interim" in flags:
                interim.append(t)
            if "measured" in flags:
                measured.append(t)
            if "given" in flags:
                given.append(t)
            if "worked out" in flags:
                worked.append(t)
            # A requirement's result, the number right after its last = sign, is one of the numbers the source covers:
            # those before it on the line, back to the previous source.
            for start, result, shown in results:
                prev = max([e for s, e, k in spans if k and e <= start] or [0])
                covers = re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?![\w])", p[prev:start])
                if result is None or not any(float(c) == float(result) for c in covers):
                    ck.bad(ln, "check 25", "Section 10: \"[%s]\" %s, and %s. The result, a number in digits right "
                           "after the last = sign, is the number the source is for. The source covers the numbers "
                           "before it on its line, back to the previous source. Write the result in the number's own "
                           "unit: for `500 ms` the arithmetic ends `= 500 ms`, not `= 0.5 seconds`." % (
                               shown, "works out %s" % result if result else "has no number right after its last = sign",
                               ("the numbers it covers are " + ", ".join(covers)) if covers else "it covers no number"))
            outside = [m for m in RE_NUMBER.finditer(p) if not any(s < m.start() < e for s, e, _ in spans)]
            last_source = max([e for s, e, k in spans if k] or [0])    # 0 when the line has no source
            if (any(m.start() >= last_source for m in outside)
                    and not re.search(r"(?<![A-Za-z0-9])A\d+(?![0-9])[^.]*\bassumed\b", t)):
                no_source.append(ln)
            lines10.append((ln, p, spans))
        missing, unsourced = [], []
        for n, num, unit, where in numbers:
            val = num.replace(",", "")
            if val == "1" and where.endswith("size limit"):
                continue
            stem = unit.lower()
            if len(stem) > 3 and stem.endswith("s"):
                stem = stem[:-1]
            if (val, stem) in [(m[0], m[1]) for m in missing + unsourced]:
                continue
            pat = re.compile(r"(?<![\d.])%s\s+(?:[A-Za-z]+\s+){0,2}?%s" % (re.escape(val), re.escape(stem)), re.I)
            found = covered = False
            for ln, p, spans in lines10:
                for m in pat.finditer(p):
                    if any(s < m.start() < e for s, e, _ in spans):
                        continue                      # a number inside a source's brackets is not listed
                    found = True
                    if any(k and s >= m.end() for s, e, k in spans):
                        covered = True
            if not found:
                missing.append((val, stem, unit, n, where))
            elif not covered:
                unsourced.append((val, stem, unit, n, where))
        for val, stem, unit, n, where in missing:
            ck.bad(n, "check 7", "`%s %s` (%s) is not in section 10. Every number in an expiry, a size limit, an "
                   "approval lifetime, the stuck task time, the lease on a claimed action, the episode count, how "
                   "often the app is woken or how far "
                   "the catch-up looks back is listed there with the word "
                   "that follows it in the design, and its source in square brackets after it."
                   % (val, unit, where))
        for val, stem, unit, n, where in unsourced:
            ck.bad(n, "check 25", "`%s %s` (%s) is in section 10 with no source after it on its line. After the "
                   "number, on the same line, write one of: %s. A source covers every number before it on the "
                   "line, back to the previous source." % (val, unit, where, SOURCE_FORMS))

        def source_kinds(val, stem):
            """The kinds (policy, requirement, data, default) of the sources that cover this number in section 10.
            A number's source is the nearest source after it on its line (S1's covering rule), one per place the
            number is written; "not told yet" is added when that source is [policy, not told yet]."""
            pat = re.compile(r"(?<![\d.])%s\s+(?:[A-Za-z]+\s+){0,2}?%s" % (re.escape(val), re.escape(stem)), re.I)
            kinds = set()
            for ln, p, spans in lines10:
                for m in pat.finditer(p):
                    if any(s < m.start() < e for s, e, _ in spans):
                        continue
                    after = [(s, k) for s, e, k in spans if k and s >= m.end()]
                    if after:
                        s, k = min(after)
                        kinds.add(k)
                        if (ln, s) in notold10:
                            kinds.add("not told yet")
            return kinds

        # Rules on a number's source that other sections asked for (spec S2 section 0.6). A number missing from
        # section 10, or there with no source, already has its check 7 or check 25 problem, so the rule stays silent.
        for n, num, unit, allowed, tag, text in source_rules:
            val = num.replace(",", "")
            stem = unit.lower()
            if len(stem) > 3 and stem.endswith("s"):
                stem = stem[:-1]
            kinds = source_kinds(val, stem)
            if kinds and kinds - set(allowed) - {"not told yet"}:    # every place the number is written (review finding 15)
                ck.bad(n, tag, text)
        # The same for rules written as a function of the kinds (S3): each returns (tag, message) or None, and None
        # for no kinds, so it is silent when the number is missing from section 10 or has no source there, as above.
        for n, num, unit, rule in source_checks:
            val = num.replace(",", "")
            stem = unit.lower()
            if len(stem) > 3 and stem.endswith("s"):
                stem = stem[:-1]
            kinds = source_kinds(val, stem)
            got = rule(kinds)
            if got:
                ck.bad(n, got[0], got[1])
        # A limit that is a list (S3): the list's name is on a section 10 line, with its source after it on that line.
        for n, lname, shown, rule in name_checks:
            want = lname.replace(",", "").lower()
            found, kinds = False, set()
            for ln, p, spans in lines10:
                pos = p.lower().find(want)
                while pos >= 0:
                    if not any(s < pos < e for s, e, _ in spans):
                        found = True
                        after = [(s, k) for s, e, k in spans if k and s >= pos + len(want)]
                        if after:
                            s, k = min(after)
                            kinds.add(k)
                            if (ln, s) in notold10:
                                kinds.add("not told yet")
                    pos = p.lower().find(want, pos + 1)
            if not found:
                ck.bad(n, "check 32", "%s is not in section 10. Name the list on a line there, with its source after it: "
                       "`[policy]` or `[policy, not told yet]`." % shown)
            elif not kinds:
                ck.bad(n, "check 25", "%s is in section 10 with no source after it on its line. Write `[policy]` or "
                       "`[policy, not told yet]` after it." % shown)
            else:
                got = rule(kinds)
                if got:
                    ck.bad(n, got[0], got[1])
        # How long anything is kept, and how long an approval lasts, are the business's to set (the table of sources
        # in reference/every-store.md), so the nearest source after each in section 10 is policy (CHECKLIST line 25).
        # A number missing from section 10, or there with no source, already has its check 7 or check 25 problem.
        policy_seen = set()
        for n, num, unit, where in numbers:
            if not (where.endswith(", expiry") or where.endswith("how long an approval lasts")):
                continue
            val = num.replace(",", "")
            stem = unit.lower()
            if len(stem) > 3 and stem.endswith("s"):
                stem = stem[:-1]
            if (val, stem) in policy_seen:
                continue
            policy_seen.add((val, stem))
            kinds = source_kinds(val, stem)
            if kinds and "policy" not in kinds:
                ck.bad(n, "check 25", "`%s %s` (%s) is the business's to set, like every expiry and every approval "
                       "lifetime. Its source in section 10 is `[policy]` when the person gave it, or `[policy, not told "
                       "yet]` until they do. Section 10 gives it %s. See the table of sources in "
                       "reference/every-store.md."
                       % (val, unit, where, " and ".join("a `%s` source" % k for k in sorted(kinds))))
            elif "policy" in kinds and kinds - {"policy", "not told yet"}:     # S1 re-check N3: the any-place rule stays
                ck.judge("`%s %s` (%s) has a policy source on one section 10 line and %s on another. Which line is this "
                         "number's? An expiry or an approval lifetime is the business's to set, so its own line says "
                         "`[policy]` or `[policy, not told yet]`. If the same number and word stand for two things, say "
                         "so on each line." % (val, unit, where, " and ".join(
                             "a `%s` source" % k for k in sorted(kinds - {"policy", "not told yet"}))))
        if not_told:
            ck.judge("Section 10 marks these as [policy, not told yet]: %s. Has the person been asked for each? Does "
                     "any action depend on one? If so, that action needs approval until the number is given."
                     % "; ".join(short(t[2:], 60) for t in not_told))
        if interim:
            ck.judge("Section 10 marks these as interim: %s. Does each named query or test exist, and is it written "
                     "down when it will be run?" % "; ".join(short(t[2:], 60) for t in interim))
        if not_told:
            free = [a["name"] for a in actions.values() if not a["approval"]]
            if free:
                ck.judge("Section 10 marks numbers as [policy, not told yet], and section 5 has actions that run "
                         "without approval: %s. Does any of them depend on one of those numbers, that is, does the "
                         "number decide whether it runs, when, for whom or how much? If so, it waits for approval "
                         "until the person gives the number, and its \"Needs approval\" is `yes` "
                         "(steps/1-understand.md, section 4)." % "; ".join(free))
        if measured:
            ck.judge("Section 10 gives these as measured: %s. Open the query or test each one names. Does it give "
                     "that number?" % "; ".join(short(t[2:], 60) for t in measured))
        if given:
            ck.judge("Section 10 says the person gave these: %s. Find where they gave each (an `(asked)` answer in "
                     "section 1, or section 10 says so). A number they did not give is `[policy, not told yet]`."
                     % "; ".join(short(t[2:], 60) for t in given))
        if worked:
            ck.judge("Section 10 works these out by arithmetic: %s. Redo each one, and find where what it starts from "
                     "was stated: by the person, or by the outside system or standard it names."
                     % "; ".join(short(t[2:], 60) for t in worked))
        if no_source:
            ck.judge("These section 10 lines hold a number and no source after it: %s. Is each a number in the "
                     "design? If so it needs a source after it." % ", ".join("line %d" % x for x in no_source))
        # Numbers in sections 1 to 8 that the script does not track and that section 10 does not hold with the word
        # after them, for the reviewer. Skipped by structure: digits inside a word, a code name in backticks or a
        # key in braces, and a number the script tracks (it has its own check). No word list (P4): a reference like
        # "line 25" is listed too, and the reviewer discards it.
        tracked = set((n, num.replace(",", "")) for n, num, unit, where in numbers)
        untracked, seen_nw, seen_bare = [], set(), set()
        for num_s in range(1, 9):
            if num_s not in S:
                continue
            for n, text in sorted(S[num_s].table + S[num_s].dash):
                plain = re.sub(r"`[^`]*`|\{[^{}]*\}", " ", text)
                for m in RE_BARE_NUMBER.finditer(plain):          # no word after it: shown with the word before it
                    val = m.group(1).replace(",", "")
                    if val in seen_bare:                          # a tracked number is in section 10: held below
                        continue
                    seen_bare.add(val)
                    held = re.compile(r"(?<![\d.])%s(?![\d])" % re.escape(val))
                    if not any(not any(s < mm.start() < e for s, e, _ in sp) for _, pp, sp in lines10
                               for mm in held.finditer(pp)):
                        shown = re.findall(r"[^\s|]+", plain[:m.end()])[-2:]     # the word before it, and it
                        untracked.append("`%s` (line %d, no word after it)" % (" ".join(shown), n))
                for m in RE_WORD_NUMBER.finditer(plain):
                    val = m.group(1).replace(",", "")
                    if (n, val) in tracked:
                        continue
                    stem = m.group(2).lower()
                    if len(stem) > 3 and stem.endswith("s"):
                        stem = stem[:-1]
                    if (val, stem) in seen_nw:
                        continue
                    seen_nw.add((val, stem))
                    pat = re.compile(r"(?<![\d.])%s\s+(?:[^\W\d_]+\s+){0,2}?%s" % (re.escape(val), re.escape(stem)),
                                     re.I)
                    if not any(not any(s < mm.start() < e for s, e, _ in sp) for _, pp, sp in lines10
                               for mm in pat.finditer(pp)):
                        untracked.append("`%s %s` (line %d)" % (m.group(1), m.group(2), n))
        if untracked:
            ck.judge("Sections 1 to 8 hold numbers that section 10 does not list with the word after them: %s%s. Is "
                     "each a number of the design, like a limit in a Rule, an allowed length or a time of day? If so "
                     "it goes in section 10 with its source." % ("; ".join(untracked[:10]), (
                         "; and %d more" % (len(untracked) - 10)) if len(untracked) > 10 else ""))

    # ---------------------------------------------------------------- the project
    if project is None:
        ck.not_checked.append("Whether the test files exist. Run again with --project <path> after the build.")
    else:
        unknown_kinds = set()
        for n, where, tn, tf in all_tests:
            full = os.path.join(project, tf)
            if not os.path.isfile(full):
                ck.bad(n, "project", "%s: the file %s does not exist in the project." % (where, tf))
                continue
            try:
                with open(full, "rb") as f:
                    body = f.read().decode("utf-8", "replace")
            except OSError:
                ck.bad(n, "project", "%s: the file %s could not be read." % (where, tf))
                continue
            last = tn[1:-1] if tn.startswith('"') else re.split(r"::|\.|#", tn)[-1]
            found = defined_in(last, body, tf)
            if found is None:
                if last not in body:
                    ck.bad(n, "project", "%s: the name %s is not in %s." % (where, last, tf))
                unknown_kinds.add(os.path.splitext(tf)[1] or tf)
            elif not found:
                ck.bad(n, "project", "%s: %s does not define a test named %s. Mentioning the name is not "
                       "enough: it must be a test function or test case." % (where, tf, last))
            elif tf.lower().endswith(".py") and py_test_asserts(last, body, os.path.dirname(full),
                                                                 project) == "missing":
                ck.bad(n, "project", "%s: %s in %s is not a test function. A name in a docstring or a comment does "
                       "not count." % (where, last, tf))
            elif tf.lower().endswith(".py") and py_test_asserts(last, body, os.path.dirname(full),
                                                                 project) is False:
                ck.bad(n, "project", "%s: the test %s in %s asserts nothing, directly or through a function in "
                       "the same file or in a project file it imports. A test that cannot fail tests nothing."
                       % (where, last, tf))
        if unknown_kinds:
            ck.not_checked.append("For files ending %s this script does not know how tests are defined, so it "
                                  "only checked that each name appears." % ", ".join(sorted(unknown_kinds)))
        if any(not tf.lower().endswith(".py") for _, _, _, tf in all_tests):
            ck.not_checked.append("Whether tests in files other than Python ones assert anything.")
        ck.not_checked.append("Whether the tests pass, and whether each would fail if its rule were removed. "
                              "The reviewer runs them.")

    # ---------------------------------------------------------------- for the reviewer
    if "A5" in answers and signal == "yes":
        ck.judge("A5 says there is an outcome signal: \"%s\". Is it a real signal about what the agent "
                 "produced? Nobody complaining is not one." % short(answers["A5"][1], 90))
    if "A2" in answers and several:
        ck.judge("A2 says several agents share memory: \"%s\". Is each one a separate agent with its own "
                 "instructions, acting for users? The agent's own memory jobs (the episode writer, the job that "
                 "groups episodes, a summarizer) are part of the one agent." % short(answers["A2"][1], 90))
    if "A2" in answers and agents == "one agent":
        ck.judge("A2 says one agent uses the memory. Check the project for a second agent or a background "
                 "job that writes memory on its own.")
    if starts:
        ck.judge("A3 says runs start on %s. Search the project for timers, queues, webhooks or listeners that start "
                 "runs without a person. A wrong A3 switches off the catch-up and the tests for a second firing."
                 % " and ".join(sorted(starts)))
    if "A4" in answers:
        if has_actions:
            ck.judge("A4 says the agent has side effects, and section 5 lists: %s. Is every function that "
                     "sends, pays, posts, deletes or changes another app listed?"
                     % ("; ".join(a["name"] for a in actions.values()) or "nothing"))
        elif side == "none":
            ck.judge("A4 says the agent has no side effects. Search the code for anything that sends, pays, "
                     "posts, deletes or changes another app.")
    if as_built:
        as_built_scan(ck, v2)
        as_built_premises(ck, facts)
    as_built_marks(ck, as_built)
    return facts, listed_tests


# A count written with the word after it. Unlike RE_NUMUNIT, a comma belongs to the number only before three digits,
# so "50, reaches" is not read as a number with a word.
RE_COUNT = re.compile(r"(?<![\w.,])(\d+(?:,\d{3})*(?:\.\d+)?)\s+([A-Za-z]+)")


def check_production(ck, S, v2, live, volume, extracts, t1, d3, d4, rowinfo, actions, needs_wake, search_used,
                     retrieval_rows, rerank, embed_where, numbers, source_rules, all_tests, facts, cf):
    """CHECKLIST lines 34 to 39 (v0.2 slice 4, G3): the Storage line of section 3, the two lines of section 4, and
    sections 11 to 13. Called by check() after sections 1 to 8 are read and before section 9, so the tests named here
    are found by --project and their numbers reach section 10. Sets the facts and case keys lines 34 to 39 need."""
    types = [i["type"] for i in rowinfo.values()]
    memory_rows = any(t in MEMORY_TYPES for t in types)
    stored = any(t != "Run log" for t in types)
    reads = memory_rows or retrieval_rows > 0
    model_work = extracts or any(i["source"] == "agent worked out" for i in rowinfo.values())
    t3 = v2 and live and reads
    vol = v2 and volume and stored
    embed_saved = bool(embed_where) and any(i["type"] == "External memory and retrieval" or i["item"].lower() in embed_where
                                            for i in rowinfo.values())
    on = {"always": True, "search": search_used, "model_work": model_work, "live_model": live and model_work, "t1": t1,
          "extracts": extracts, "wake": needs_wake, "live_reads": live and reads, "reads": reads,
          "semantic": "Semantic memory" in types,
          "t2": bool(facts.get("t2")), "fresh": bool(facts.get("fresh")),     # t2 and fresh are set by slice 3
          "queue": (live and model_work) or vol}
    rollup_time = move_time = False
    listed_before = 0                     # things section 4 lists to run before the reply; each counts toward the cap
    fail_needed = [(name, why) for name, key, why in FAILURES_WHEN if on[key]]
    meas_needed = [(name, why) for name, key, why in MEASURES_WHEN if on[key]]

    def done():
        facts.update({"t3": t3, "t35": v2 and (embed_saved or rerank), "t8": vol,
                      "measures_fit": bool(meas_needed) or 12 in S})
        cf.update({"model_work": model_work, "embed_saved": embed_saved, "rerank": rerank,
                   "rollup_time": rollup_time, "move_time": move_time})

    if not v2:
        for num in (11, 12, 13):
            if num in S:
                ck.bad(S[num].line, "structure", V2_ONLY % ("## %d. %s" % (num, TITLES[num])))
        done()
        return

    # ---- section 3: Storage (line 39)
    if 3 in S:
        gst = d3.get("Storage")
        if memory_rows and (not gst or not gst[1]):
            ck.bad(gst[0] if gst else S[3].line, "check 39", "Section 3 needs the line `- Storage: tables. <the reason>`, "
                   "or `tables and an edges table. <the reason>`, or `a graph database. <the reason>`.")
        elif gst and not memory_rows:
            ck.bad(gst[0], "structure", "Section 3 has the line \"Storage\", but no row is under a memory type, so "
                   "nothing is stored that it could be about. Delete it.")
        elif gst:
            nst, vst = gst
            cst = choice(vst, STORAGE)
            mst = re.match(r"^%s\s*[.:,]\s*(\S.*)$" % re.escape(cst), vst.strip(), re.I) if cst else None
            if not mst or hollow(mst.group(1)):
                ck.bad(nst, "check 39", "\"Storage\" must start with `tables`, `tables and an edges table` or `a graph "
                       "database`, then a full stop and the reason. \"%s\" does not." % short(vst))
            elif cst == "tables and an edges table":
                ck.judge("Storage is tables and an edges table: \"%s\". Are the links simple, read one step at a time?"
                         % short(vst, 90))
            elif cst == "a graph database":
                ck.judge("Storage is a graph database: \"%s\". Do the agent's questions follow links several steps away, "
                         "or does one person appear under many names across sources? Has the team accepted a separate "
                         "database and a model call on every save? If not, it is tables." % short(vst, 90))

    # ---- section 4: nobody waits for memory (line 34)
    if 4 in S:
        gr = d4.get("Memory reads before the model call")
        if t3 and (not gr or not gr[1]):
            ck.bad(gr[0] if gr else S[4].line, "check 34", "A9 says someone waits live and the agent reads memory, so "
                   "section 4 needs the line `- Memory reads before the model call: at most <number> <ms or seconds>, then "
                   "the reply goes on without them`.")
        elif gr and not t3:
            ck.bad(gr[0], "structure", "Section 4 has the line \"Memory reads before the model call\", but %s. Delete it."
                   % ("A9 does not say someone waits live" if not live else "the agent reads no memory"))
        elif gr:
            mr = re.match(r"^at most\s+(\d[\d,]*)\s+([A-Za-z]+)\s*,\s*then the reply goes on without them\.?\s*$",
                          gr[1], re.I)
            unit = mr.group(2).lower() if mr else ""
            if unit.endswith("s") and unit[:-1] in READ_UNIT_SECONDS:
                unit = unit[:-1]
            if not mr or unit not in READ_UNIT_SECONDS:
                ck.bad(gr[0], "check 34", "\"Memory reads before the model call\" must be `at most <number> <ms or "
                       "seconds>, then the reply goes on without them`. \"%s\" is not." % short(gr[1]))
            elif int(mr.group(1).replace(",", "")) < 1:
                ck.bad(gr[0], "check 34", "\"Memory reads before the model call\": a time allowed of 0 cuts off every "
                       "read, so the agent never has its memory. Give at least 1.")
            elif int(mr.group(1).replace(",", "")) * READ_UNIT_SECONDS[unit] > 60:
                ck.bad(gr[0], "check 34", "\"Memory reads before the model call\": `%s %s` is more than a minute. Nobody "
                       "waits live that long, so a time allowed this long cuts nothing off. Give the time the person "
                       "can wait, less what the model call needs." % (mr.group(1), mr.group(2)))
            else:
                numbers.append((gr[0], mr.group(1), mr.group(2), "Section 4, time allowed for memory reads"))
                source_rules.append((gr[0], mr.group(1), mr.group(2), ("requirement", "default"), "check 34",
                                     "`%s %s` (time allowed for memory reads) is worked out from the response time the "
                                     "person stated, or is a starting value. Its source in section 10 is "
                                     "`[requirement: ...]` or `[default: ...]`." % (mr.group(1), mr.group(2))))
        gw = d4.get("Memory work before the reply")
        if t3 and model_work and (not gw or not gw[1]):
            ck.bad(gw[0] if gw else S[4].line, "check 34", "A9 says someone waits live and a model writes memory, so "
                   "section 4 needs the line `- Memory work before the reply: none`, or each thing that must run before "
                   "the reply as `<what>: <why>`, joined by semicolons.")
        elif gw and not (t3 and model_work):
            ck.bad(gw[0], "structure", "Section 4 has the line \"Memory work before the reply\", but %s. Delete it."
                   % ("A9 does not say someone waits live" if not live else
                      "the agent reads no memory" if not reads else "no model writes memory"))
        elif gw and not is_none(gw[1]):
            parts = names(gw[1])
            okw = bool(parts)
            for p in parts:
                pm = re.match(r"^([^:]+):\s*(\S.*)$", p)
                if not pm or hollow(pm.group(1)) or hollow(pm.group(2)) or is_none(pm.group(1)):
                    okw = False
            if not okw:
                ck.bad(gw[0], "check 34", "\"Memory work before the reply\": write `none`, or each thing that must run "
                       "before the reply as `<what>: <why>`, joined by semicolons.")
            else:
                listed_before = len(parts)
                ck.judge("Memory work before the reply: `%s`. Does each have to finish before the person sees the "
                         "answer? Everything else a model does for memory runs after the reply." % short(gw[1], 120))

    def rows_of(num, headers, tag):
        sec = S[num]
        rows = table(ck, sec, headers)
        if rows is None and not sec.table:
            ck.bad(sec.line, tag, "Section %d has no table. Its headings are: | %s |" % (num, " | ".join(headers)))
        return rows or []

    # ---- section 11: failures (line 37)
    tests11 = {}                          # each test section 11 names, with the rows that name it
    if 11 in S and not stored:
        ck.bad(S[11].line, "structure", "Section 11 is here, but the run log is the only thing saved, and its expiry and "
               "cleanup are tested under line 8. Leave the section out.")
    elif stored and 11 not in S:
        ck.bad(0, "structure", "Section 11 (\"## 11. Failures\") is missing. It is needed because the design has the "
               "line A9 and saves something besides the run log.")
    elif 11 in S:
        if S[11].dash:
            dash_values(ck, S[11], v2)
        rows11 = rows_of(11, H11, "check 37")
        unique(ck, rows11, "What fails", 11)
        seen11 = set()
        for n, r in rows11:
            if not r["What fails"].strip():
                continue                                  # unique() has reported the empty cell
            name = find(r["What fails"], FAILURES)
            if not name:
                ck.bad(n, "check 37", "Section 11: \"%s\" is not on the list of failures. Use: %s."
                       % (short(r["What fails"]), "; ".join(FAILURES)))
                continue
            seen11.add(name)
            where = "Section 11, row \"%s\"" % name
            ans = choice(r["Answers"], ANSWERS)
            act = choice(r["Actions"], ACTIONS_WHEN)
            for col, val in (("Answers", ans), ("Actions", act)):
                note = r[col].strip()[len(val):].strip().lstrip(",;:.").strip() if val else ""
                if note and hollow(note):
                    ck.bad(n, "check 37", "%s: \"%s\" is `%s` with \"%s\" after it, a blank to fill in. Write the note, "
                           "or leave only the value." % (where, col, val, short(note)))
            if not ans:
                ck.bad(n, "check 37", "%s: \"Answers\" must start with `without memory`, `as usual` or `none`. There is no "
                       "value for an agent that stops answering: it fails open for reading." % where)
            elif ans == "none" and live:
                ck.bad(n, "check 37", "%s: \"Answers\" is `none` (nobody waits for an answer), but A9 says someone waits "
                       "live. Write `without memory` or `as usual`." % where)
            elif ans == "none":
                ck.judge("%s: nobody waits for an answer. Is that so?" % where)
            elif ans == "as usual" and name == "memory store slow or down" and reads:
                ck.judge("%s: answers are `as usual` with the memory store down, and the agent reads memory. Does no "
                         "answer depend on what it reads?" % where)
            if not act:
                ck.bad(n, "check 37", "%s: \"Actions\" must start with `blocked`, `as usual` or `none`." % where)
            elif act == "none" and actions:
                ck.bad(n, "check 37", "%s: \"Actions\" is `none` only when the agent has no action in section 5." % where)
            elif act != "none" and not actions:
                ck.bad(n, "check 37", "%s: the agent has no action in section 5, so \"Actions\" is `none`." % where)
            elif name == "memory store slow or down" and actions and act != "blocked":
                ck.bad(n, "check 37", "Section 11, row \"memory store slow or down\": with memory gone, no action can be "
                       "claimed, approved or checked against a fresh fact, so \"Actions\" starts with `blocked`. The agent "
                       "fails closed for acting.")
            tests = test_entries(r["Test"])
            if tests is None:
                ck.bad(n, "check 37", "%s: the Test cell is not in the form this script reads. %s" % (where, TEST_FORM))
            else:
                for tn, tf in tests:
                    all_tests.append((n, where, tn, tf))
                    tests11.setdefault(tn, [])
                    if name not in tests11[tn]:
                        tests11[tn].append(name)
        for tn, rows in sorted(tests11.items()):
            if len(rows) > 1:
                ck.bad(S[11].line, "check 37", "Section 11: the test `%s` is named by %d rows (%s). Each row names its own "
                       "test, the one that shows what happens when that part fails." % (tn, len(rows), "; ".join(rows)))
        for name, why in fail_needed:
            if name not in seen11:
                ck.bad(S[11].line, "check 37", "Section 11 has no row for \"%s\". It is needed because %s." % (name, why))

    # ---- section 12: measurements (line 38)
    if 12 in S and not stored:
        ck.bad(S[12].line, "structure", "Section 12 is here, but the run log is the only thing saved. Leave the section "
               "out.")
    elif stored and meas_needed and 12 not in S:
        ck.bad(0, "structure", "Section 12 (\"## 12. Measurements\") is missing. It is needed because the design has the "
               "line A9, saves something besides the run log, and these measures fit it: %s."
               % "; ".join(name for name, _ in meas_needed))
    elif 12 in S:
        d12 = dash_values(ck, S[12], v2)
        rows12 = rows_of(12, H12, "check 38")
        unique(ck, rows12, "Measure", 12)
        seen12, no_alert = set(), []
        for n, r in rows12:
            if not r["Measure"].strip():
                continue
            name = find(r["Measure"], MEASURES)
            if not name:
                ck.bad(n, "check 38", "Section 12: \"%s\" is not on the list of measures. Use: %s."
                       % (short(r["Measure"]), "; ".join(MEASURES)))
                continue
            seen12.add(name)
            where = "Section 12, row \"%s\"" % name
            if hollow(r["Recorded in"]) or choice(r["Recorded in"], ["none", "nowhere"]):
                ck.bad(n, "check 38", "%s: \"Recorded in\" says where the number is kept, like `the run log, one number "
                       "per run`. A number kept nowhere cannot be read back." % where)
            al = r["Alert line"].strip()
            ma = re.match(r"^(above|below)\s+(\d[\d,]*(?:\.\d+)?)\s+([A-Za-z]+)", al, re.I)
            mn = re.match(r"^none\s*:\s*(\S.*)$", al, re.I)
            if ma:
                if ma.group(1).lower() == "below" and float(ma.group(2).replace(",", "")) == 0:
                    ck.bad(n, "check 38", "%s: an alert line `below 0` never fires. Give a number above 0, or write "
                           "`none: <why>`." % where)
                elif (name.startswith("share of") and ma.group(1).lower() == "above" and ma.group(3).lower() == "percent"
                      and float(ma.group(2).replace(",", "")) >= 100):
                    ck.bad(n, "check 38", "%s: a share is at most 100 percent, so an alert line `above %s percent` never "
                           "fires. Give a number below 100, or write `none: <why>`." % (where, ma.group(2)))
                numbers.append((n, ma.group(2), ma.group(3), "Section 12, alert line for \"%s\"" % name))
            elif mn and not hollow(mn.group(1)):
                no_alert.append("%s: %s" % (name, short(mn.group(1), 60)))
            else:
                ck.bad(n, "check 38", "%s: the alert line must be `above <number> <of what>`, `below <number> <of what>` "
                       "or `none: <why>`." % where)
        for name, why in meas_needed:
            if name not in seen12:
                ck.bad(S[12].line, "check 38", "Section 12 has no row for \"%s\". It is needed because %s." % (name, why))
        if no_alert:
            ck.judge("These measures have no alert line: %s. Is each reason one the person accepted?" % "; ".join(no_alert))
        grb = d12.get("A measure is read back by")
        if rows12 and (not grb or not grb[1]):
            ck.bad(grb[0] if grb else S[12].line, "check 38", "Section 12 needs the line `- A measure is read back by: "
                   "<test name> in <file>`, the test that reads one measure back from where its row says it is recorded.")
        elif grb and grb[1]:
            tests = test_entries(grb[1])
            if tests is None:
                ck.bad(grb[0], "check 38", "Section 12, \"A measure is read back by\": %s" % TEST_FORM)
            else:
                for tn, tf in tests:
                    all_tests.append((grb[0], "Section 12, \"A measure is read back by\"", tn, tf))
                    if tn in tests11:
                        ck.bad(grb[0], "check 38", "Section 12, \"A measure is read back by\": `%s` is the test of section "
                               "11's row \"%s\". The read-back is a test of its own: it reads a measure back from where "
                               "its row says it is recorded." % (tn, "; ".join(tests11[tn])))

    # ---- section 13: volume (line 36)
    if 13 in S and not vol:
        ck.bad(S[13].line, "structure", "Section 13 is here, but %s. Leave the section out."
               % ("A9 does not say high volume" if not volume else "the run log is the only thing saved"))
    elif vol and 13 not in S:
        ck.bad(0, "structure", "Section 13 (\"## 13. Volume\") is missing. It is needed because A9 says high volume and "
               "the design saves something besides the run log.")
    elif vol:
        sec = S[13]
        if sec.table:
            ck.bad(sec.table[0][0], "structure", "Section 13 has no table. Its six lines start with a dash.")
        d13 = dash_values(ck, sec, v2)
        for key, form in VOLUME_LINES:
            if key not in d13 or not d13[key][1]:
                ck.bad(d13[key][0] if key in d13 else sec.line, "check 36", "Section 13 needs the line `- %s: %s`."
                       % (key, form))
        n, v = d13.get("Expected volume", (0, ""))
        if v and hollow(v):
            ck.bad(n, "check 36", "\"Expected volume\" says how many users, facts and runs to plan for, and whose figures "
                   "they are. \"%s\" does not." % short(v))
        elif v:
            figures = RE_COUNT.findall(v)
            glued = [m.group(0).rstrip(",.") for m in re.finditer(r"(?<![\w.,])\d[\w,./]*", v)
                     if not RE_COUNT.match(v, m.start())]
            zero = [(num, word) for num, word in figures if float(num.replace(",", "")) == 0]
            vol_form = ("\"Expected volume\" gives its figures in digits, each with the word after it, like `2,000 people, "
                        "about 30 facts each, 20,000 runs a day (the person's figures)`.")
            if not figures:
                ck.bad(n, "check 36", "%s \"%s\" has no figure in that form." % (vol_form, short(v)))
            elif glued:
                ck.bad(n, "check 36", "%s `%s` is not in that form: write the figure in digits, a space, then the word."
                       % (vol_form, glued[0]))
            elif zero:
                ck.bad(n, "check 36", "\"Expected volume\": a figure of `0 %s` plans for nothing. Give the figures the "
                       "person stated." % zero[0][1])
            for num, word in figures:
                numbers.append((n, num, word, "Section 13, expected volume"))
                source_rules.append((n, num, word, ("requirement", "data"), "check 36",
                                     "`%s %s` (expected volume) is a figure the person stated or one measured from "
                                     "records. Its source in section 10 is `[requirement: ...]` when the person stated it, "
                                     "or `[data: <the query>]` when it was measured." % (num, word)))
            ck.judge("Expected volume: `%s`. Did the person state it? Do the partition key and the indexed columns fit "
                     "the queries the read functions make?" % short(v, 120))
        n, v = d13.get("Counters are rolled up every", (0, ""))
        if v:
            mnone = re.match(r"^none\s*:\s*(\S.*)$", v, re.I)
            if RE_SPAN.match(v):
                num = RE_NUMUNIT.match(v)
                if int(num.group(1).replace(",", "")) < 1:
                    ck.bad(n, "check 36", "\"Counters are rolled up every\": an interval of 0 is the same as writing the "
                           "counters on every use. Give at least 1.")
                else:
                    rollup_time = True
                    numbers.append((n, num.group(1), num.group(2), "Section 13, counter roll-up"))
            elif mnone and not hollow(mnone.group(1)):
                if t1:
                    ck.bad(n, "check 36", "Section 13: a fact has no end, so its counters are rolled up on a timer. Give "
                           "the interval.")
            else:
                ck.bad(n, "check 36", "\"Counters are rolled up every\" must be `<number> <minutes, hours, days, weeks, "
                       "months or years>`, or `none: <why>` when no row has no end. \"%s\" is not." % short(v))
        n, v = d13.get("Partition key", (0, ""))
        if v:
            if re.match(r"^none\s*(:|$)", v, re.I):
                mnone = re.match(r"^none\s*:\s*(\S.*)$", v, re.I)
                if not mnone or hollow(mnone.group(1)):
                    ck.bad(n, "check 36", "\"Partition key\": write the column large tables are split by, or `none: "
                           "<why>`.")
                else:
                    ck.judge("No partition key: `%s`. At the expected volume, does every large table stay fast without "
                             "one?" % short(v, 90))
            elif hollow(v):
                ck.bad(n, "check 36", "\"Partition key\": write the column large tables are split by, or `none: <why>`.")
        n, v = d13.get("Replaced versions move to cheaper storage after", (0, ""))
        if v:
            mnever = re.match(r"^never\s*:\s*(\S.*)$", v, re.I)
            if RE_SPAN.match(v):
                num = RE_NUMUNIT.match(v)
                move_time = True
                numbers.append((n, num.group(1), num.group(2), "Section 13, when replaced versions move"))
            elif not mnever or hollow(mnever.group(1)):
                ck.bad(n, "check 36", "\"Replaced versions move to cheaper storage after\" must be `<number> <minutes, "
                       "hours, days, weeks, months or years>`, or `never: <why>`. \"%s\" is not." % short(v))
        n, v = d13.get("Indexed columns", (0, ""))
        if v and hollow(v):
            ck.bad(n, "check 36", "\"Indexed columns\": name each table and its indexed columns, like `facts: owner, kind, "
                   "subject`.")
        n, v = d13.get("Extra model calls per turn", (0, ""))
        if v:
            mx = re.match(r"^at most\s+(\d[\d,]*)\s+(calls?)(?![A-Za-z])", v, re.I)
            if not mx:
                ck.bad(n, "check 36", "\"Extra model calls per turn\" must be `at most <number> calls`. \"%s\" is not."
                       % short(v))
            elif int(mx.group(1).replace(",", "")) < listed_before:
                ck.bad(n, "check 36", "\"Extra model calls per turn\" is `%s`, but section 4 lists %d thing(s) under "
                       "\"Memory work before the reply\". Listed work is never pushed back to after the reply, and it "
                       "counts toward the cap, so the cap is at least %d." % (short(v), listed_before, listed_before))
            else:
                numbers.append((n, mx.group(1), mx.group(2), "Section 13, the cap on extra model calls"))
    done()


# ---------------------------------------------------------------- a design read as built (--as-built)
# steps/review-existing-agent.md: the file describes code that already exists. A value the code does not settle is
# written `unknown: <what was looked for and where>`. Problems on such a line are listed apart from the candidate
# gaps, and only a fault in the file itself (tag structure or project) decides the exit code.
RE_UNKNOWN = re.compile(r"^unknown:(.*)$", re.I)
RE_BARE_UNKNOWN = re.compile(r"^unknown(?!\w)", re.I)      # the word unknown, read when it has no colon after it
UNKNOWN_FORM = "Write `unknown: <what you looked for and where>`."
RE_NOT_IN_CODE = re.compile(r"^not in the code:(.*)$", re.I)
RE_BARE_NOT_IN_CODE = re.compile(r"^not in the code(?!\w)", re.I)
NOT_IN_CODE_FORM = "Write `not in the code: <what you searched for>`."
RE_AS_BUILT_TITLE = re.compile(r"\(as built\)\s*$", re.I)
RE_FILE_LINE = re.compile(r"([\w./\\-]*\w\.[A-Za-z0-9]+):\d+(?:-\d+)?")   # a file and line, like agent/store.py:55
SWITCH_CELLS = {(2, "Decision"), (3, "Memory type"), (3, "Source"), (3, "Enters as"), (4, "Lives in"),
                (4, "If skipped once"), (5, "Needs approval"), (5, "Content it carries"), (6, "Method")}
                                                                                 # cells other checks are switched by
FAULT_TAGS = ("structure", "project")


def from_file_line(text, num, unit):
    """True when the number and the word after it are on the line only as part of a file and line, like store.py:55."""
    plain = RE_FILE_LINE.sub(r"\1", text)
    return (num, unit) in RE_NUMUNIT.findall(text) and (num, unit) not in RE_NUMUNIT.findall(plain)


def as_built_values(ck):
    """Every value in the file as (line, where, value, section, column): each table cell below the headings, the text
    after the first colon of each dash line (in section 1, the answer without its bracket), and in section 10, whose
    lines have no key, the text after the dash and the part after `policy:`, `default:` or `data:` of each source as
    well."""
    out = []
    for num in sorted(ck.sections):
        sec = ck.sections[num]
        heads = split_cells(sec.table[0][1]) if sec.table else []
        for n, text in sec.table[1:]:
            if is_separator(text):
                continue
            cells = split_cells(text)
            for i, cell in enumerate(cells):
                col = heads[i] if i < len(heads) else "cell %d" % (i + 1)
                out.append((n, "Section %d, row \"%s\", %s" % (num, short(cells[0], 40), col), cell, num, col))
        for n, text in sec.dash:
            body = text[2:].strip()
            if num == 10:
                out.append((n, "Section 10", body, num, None))
                for mt in RE_SQUARE.finditer(body):
                    pm = re.match(r"^\s*(?:policy|default|data):(.*)$", mt.group(1), re.I | re.S)
                    if pm:
                        out.append((n, "Section 10, the source \"[%s]\"" % short(mt.group(1), 40), pm.group(1), num,
                                    None))
            if ":" not in body:
                continue
            key, value = body.split(":", 1)
            value = value.strip()
            if num == 1:
                hm = re.search(r"\(([^()]*)\)\s*$", value)
                if hm and find(hm.group(1), HOW):
                    value = value[: hm.start()].strip()
            out.append((n, "Section %d, \"%s\"" % (num, short(key, 40)), value, num, None))
    return out


def as_built_scan(ck, has_a9):
    """Collect the lines marked unknown into ck.unknown_lines, and add the faults this mode alone has."""
    ck.unknown_lines = {}
    for n, where, value, num, col in as_built_values(ck):
        v = value.strip()
        m, nm = RE_UNKNOWN.match(v), RE_NOT_IN_CODE.match(v)
        if m and not hollow(m.group(1)) and (num, col) in SWITCH_CELLS:
            ck.bad(n, "structure", "%s is marked unknown, but the code always shows it, and other checks are switched "
                   "on or off by it. Write what the code shows." % where)
        elif m and not hollow(m.group(1)):
            ck.unknown_lines.setdefault(n, []).append("%s: %s" % (where, v))
        elif RE_BARE_UNKNOWN.match(v):                      # the word unknown not followed by a colon and a reason
            ck.bad(n, "structure", "%s is `%s`, not in the form for a value the code does not settle. %s"
                   % (where, short(v, 30), UNKNOWN_FORM))
        elif (nm and hollow(nm.group(1))) or (not nm and RE_BARE_NOT_IN_CODE.match(v)):
            ck.bad(n, "structure", "%s is `%s`, not in the form for something the code does not have. %s"
                   % (where, short(v, 30), NOT_IN_CODE_FORM))
    for n, text in (ck.sections[1].dash if 1 in ck.sections else []):
        hm = re.match(r"^- (A\d+)\s+[^:]+:.*\(([^()]*)\)\s*$", text)
        if hm and find(hm.group(2), HOW) == "assumed":
            ck.bad(n, "structure", "Section 1, %s ends `(assumed)`. An as-built design assumes nothing: write what the "
                   "code shows, or `unknown: <what you looked for and where>`, and end the line `(worked out)`."
                   % hm.group(1))
    if not has_a9:
        ck.bad(ck.sections[1].line if 1 in ck.sections else 0, "structure", "An as-built design always has the line "
               "\"- A9 Also true of this agent: ...\" in section 1, with `none` when none of the four holds, so the "
               "lines added in v0.2 are checked.")


def as_built_premises(ck, facts):
    """As built, a task whose premise is `none` is a candidate gap for CHECKLIST line 31, and the line applies: the code
    saves nothing the task was scheduled on. Slice 3 reads the line `Premise of each task` in a design; this reads only
    that one case, and only as built. On a skill without that line the design already has a fault for it."""
    sec = ck.sections.get(7)
    if sec is None:
        return
    tasks = [split_cells(t)[0] for _, t in sec.table[1:] if not is_separator(t) and split_cells(t)[0]]
    for n, text in sec.dash:
        pm = re.match(r"^- Premise of each task:\s*(.*)$", text, re.I)
        if not pm:
            continue
        for part in names(pm.group(1)):
            for t in sorted(tasks, key=len, reverse=True):
                after = part[len(t):].lstrip()
                if part[:len(t)].lower() == t.lower() and after.startswith(":"):
                    if re.match(r"^none\s*:", after[1:].strip(), re.I):
                        facts["t2"] = True                      # line 31 applies: not on the n/a list
                        ck.bad(n, "check 31", "Section 7, \"Premise of each task\": the task \"%s\" has no premise. As "
                               "built, a task the code schedules saves what it was scheduled on (line 31): confirm in "
                               "the code that it rests on no record, or this is a gap." % short(t))
                    break


def as_built_marks(ck, as_built):
    """In both modes: the title says whether the file is read as built, and a section 10 source written `not in the
    code` is a number written into the code with no measure (a candidate gap as built, and no source otherwise)."""
    if ck.title is not None and bool(RE_AS_BUILT_TITLE.search(ck.title)) != as_built:
        if as_built:
            ck.bad(1, "structure", "A design read with --as-built has a title that ends \"(as built)\": `# Memory "
                   "design: <name of the agent> (as built)`. A design that is being built from is checked without "
                   "--as-built.")
        else:
            ck.bad(1, "structure", "The title ends \"(as built)\", so the file describes code that already exists: "
                   "check it with --as-built. Once it is the design being built from, take \"(as built)\" out of the "
                   "title.")
    for n, text in (ck.sections[10].dash if 10 in ck.sections else []):
        for mt in RE_SQUARE.finditer(text):
            inner = " ".join(mt.group(1).split())
            ku = re.match(r"^(default|data):\s*unknown\b", inner, re.I)
            if ku:
                what = "measure" if ku.group(1).lower() == "default" else "query or test"
                if as_built:
                    ck.bad(n, "check 25", "Section 10: \"[%s]\": the %s for this number could not be told from the "
                           "code." % (short(inner, 60), what))
                else:
                    ck.bad(n, "check 25", "Section 10: \"[%s]\": `unknown` is written only in a design read with "
                           "--as-built. A design has no unknown: a `%s` source names its %s."
                           % (short(inner, 60), ku.group(1).lower(), what))
                continue
            km = re.match(r"^(default|data):\s*not in the code\b", inner, re.I)
            if not km:
                continue
            kind = km.group(1).lower()
            names = ("the measure that would show the number is wrong", "[default: how often the limit is reached]") \
                if kind == "default" else ("the query or test the number comes from",
                                           "[data: count of facts per owner in the facts table]")
            if as_built:
                ck.bad(n, "check 25", "Section 10: \"[%s]\": the number is written into the code, and nothing names "
                       "%s. Line 25 asks that numbers are read from configuration and that a `%s` source names %s."
                       % (short(inner, 60), names[0], kind, names[0]))
            else:
                ck.bad(n, "check 25", "Section 10: \"[%s]\": `not in the code` is written only in a design read with "
                       "--as-built. A `%s` source names %s, like \"%s\"."
                       % (short(inner, 60), kind, names[0], names[1]))


def as_built_split(ck, probs):
    """Split the problems three ways. Return the faults in the file, and the lines of the blocks printed after them."""
    unknown = getattr(ck, "unknown_lines", {})
    faults = [p for p in probs if p[1] in FAULT_TAGS]
    unchecked = [p for p in probs if p[1] not in FAULT_TAGS and p[0] in unknown]
    gaps = [p for p in probs if p[1] not in FAULT_TAGS and p[0] not in unknown]
    lines = []
    for title, group in (("COULD NOT BE CHECKED because a value on the line is marked unknown (%d)", unchecked),
                         ("WHAT THE FILE SHOWS IS MISSING OR DOES NOT AGREE (%d) - each is a candidate gap to "
                          "confirm in the code", gaps)):
        if group:
            lines.append(title % len(group))
            for line, tag, text in group:
                lines.append("  [%s] %s%s" % (tag_text(tag), "line %d: " % line if line else "", text))
            lines.append("")
    if unknown:
        lines.append("MARKED UNKNOWN (%d)" % len(unknown))
        for n in sorted(unknown):
            lines.append("  line %d: %s" % (n, short("; ".join(unknown[n]), 100)))
        lines.append("")
    if faults:
        result = "RESULT: %d problem(s) in the file itself. Fix these first." % len(faults)
    else:
        result = ("RESULT: the file can be read. %d candidate gap(s), %d could not be checked, %d marked unknown."
                  % (len(gaps), len(unchecked), len(unknown)))
    return faults, lines, result


def report(path, ck, facts, listed_tests, as_built=False):
    out = ["check_design.py: %s" % path, ""]
    probs = sorted(set(ck.problems))
    if as_built:
        out[0] += " (read as built)"
        probs, found, result = as_built_split(ck, probs)
    if probs:
        out.append("PROBLEMS (%d)" % len(probs))
        for line, tag, text in probs:
            where = "line %d: " % line if line else ""
            out.append("  [%s] %s%s" % (tag_text(tag), where, text))
        out.append("")
    if as_built:
        out.extend(found)
    if ck.reviewer:
        out.append("FOR THE REVIEWER TO JUDGE (%d) - a script cannot decide these, and none counts as passed"
                   % len(ck.reviewer))
        for text in ck.reviewer:
            out.append("  - %s" % text)
        out.append("")
    left_out = [n for n in (5, 6, 7, 8) if n not in ck.sections]
    if facts is not None and facts.get("v2"):            # sections 11 to 13 (slice 4) exist only with A9
        left_out += [n for n in (11, 12, 13) if n not in ck.sections]
    if left_out and not probs:
        out.append("SECTIONS LEFT OUT because they do not apply: %s" % ", ".join(
            "%d (%s)" % (n, TITLES[n]) for n in left_out))
        out.append("")
    if facts is not None and not probs:
        na = [(line_no, NOT_NEEDED_BECAUSE[needs]) for name, line_no, needs, why in TESTS
              if not facts[needs] and name not in listed_tests
              and (line_no < 26 or facts.get("v2"))           # lines 26 on are shown only to a design with A9
              and not (needs == "episodes" and facts.get("episodes_maybe"))
              and not (needs == "suggestions" and facts.get("suggestions_maybe"))]
        if facts.get("v2"):                               # lines 37 to 39 have no section 9 row (slice 4)
            if not facts["stored"]:
                na += [(37, "the run log is the only thing saved"), (38, "the run log is the only thing saved")]
            elif not facts.get("measures_fit"):
                na.append((38, "no measure on the list fits this agent"))
            if not facts["memory_rows"]:
                na.append((39, "nothing is saved under a memory type"))
        if na:
            out.append("CHECKLIST LINES THAT CANNOT APPLY to this design (the reviewer answers n/a)")
            for line_no, why in na:
                out.append("  - line %d (%s): %s" % (line_no, CHECK_NAMES[line_no], why))
            out.append("")
    if ck.not_checked:
        out.append("NOT CHECKED")
        for text in ck.not_checked:
            out.append("  - %s" % text)
        out.append("")
    if probs:
        out.append("RESULT: %d problem(s). The design file is not complete." % len(probs))
    else:
        out.append("RESULT: no problems found. The design file is complete and agrees with itself.")
    if as_built:
        out[-1] = result
    out.append("")
    out.append("This script checks that the file is complete and agrees with itself. It cannot tell")
    out.append("whether the design is right for the agent, and it reads no code. Tags like [check 5]")
    out.append("point to lines in CHECKLIST.md. The review in steps/5-review.md is still needed.")
    if as_built:
        out[-1] = "point to lines in CHECKLIST.md. Confirm each candidate gap in the code before you list it."
    return "\n".join(out), (1 if probs else 0)


def main(argv):
    args = argv[1:]
    project = None
    as_built = False
    paths = []
    i = 0
    while i < len(args):
        if args[i] in ("-h", "--help"):
            print(__doc__)
            return 0
        if args[i] == "--as-built":
            if as_built:
                sys.stderr.write("check_design.py: --as-built is given twice. Give it once.\n")
                return 2
            as_built = True
            i += 1
            continue
        if args[i] == "--project":
            if i + 1 >= len(args):
                sys.stderr.write("check_design.py: --project needs a path\n")
                return 2
            project = args[i + 1]
            i += 2
            continue
        paths.append(args[i])
        i += 1
    if len(paths) != 1:
        sys.stderr.write("check_design.py: usage: python3 -B check_design.py MEMORY-DESIGN.md [--project <path>] [--as-built]\n")
        return 2
    if project is not None and not os.path.isdir(project):
        sys.stderr.write("check_design.py: the project folder %s does not exist\n" % project)
        return 2
    ck = Checker()
    try:
        lines = read_file(paths[0], ck)
    except (OSError, ValueError) as e:
        sys.stderr.write("check_design.py: cannot read %s: %s\n" % (paths[0], e))
        return 2
    facts, listed_tests = check(lines, ck, project, as_built)
    text, code = report(paths[0], ck, facts, listed_tests, as_built)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
