#!/usr/bin/env python3
"""Check that a MEMORY-DESIGN.md file is complete and agrees with itself.

Usage:
    python3 -B check_design.py MEMORY-DESIGN.md
    python3 -B check_design.py MEMORY-DESIGN.md --project <path to the project>

What it does
    It reads the ten sections of the design file and checks fixed things:
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
}
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
BOOKKEEPING_TYPES = ["Run log", "Audit log", "Side effect protection", "Prospective memory",
                     "External memory and retrieval"]
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

UNIT = r"(?:minute|hour|day|week|month|year)s?"
RE_PERIOD_AFTER = re.compile(r"^\d[\d,]*\s+(?:working\s+)?" + UNIT + r"\s+after\s+\S", re.I)
RE_WHEN = re.compile(r"^when\s+\S", re.I)
RE_WHEN_HOW = re.compile(r"^when\s+\S.*,\s*(told|asked)(?![A-Za-z])", re.I)
RE_REPLACED = re.compile(r"^replaced\b", re.I)
RE_PERMANENT = re.compile(r"^permanent:\s*(\S.*)$", re.I)
RE_LIMIT = re.compile(r"^\d[\d,.]*\s+\S.*,\s*then\s+(.+)$", re.I)
RE_BOUNDED = re.compile(r"^bounded by retention(?![A-Za-z0-9])", re.I)
RE_SAME_AS = re.compile(r"^same as\s+(.+)$", re.I)
RE_LASTS = re.compile(r"^(?:until the scheduled time plus\s+)?\d[\d,]*\s+" + UNIT + r"(?![A-Za-z0-9])", re.I)
RE_SPAN = re.compile(r"^\d[\d,]*\s+" + UNIT + r"(?![A-Za-z0-9])", re.I)
RE_TEST = re.compile(r'^("[^"]+"|\S+) in (\S+)$')
RE_BRACKETS = re.compile(r"\s*\([^()]*\)")
RE_NUMBER = re.compile(r"(?<![\w.,])(\d[\d,]*)(?![\w])")
RE_NUMUNIT = re.compile(r"(?<![\w.,])(\d[\d,]*)\s+([A-Za-z]+)")

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
    24: "the review"}


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
}


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
            ck.bad(n, "structure", "The heading \"%s\" is not one of the ten sections. Nothing under it "
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


def dash_values(ck, sec):
    """Return {key: (line, value)} for a section whose dash lines are 'Key: value'."""
    out = {}
    allowed = DASH_KEYS.get(sec.num, [])
    for n, text in sec.dash:
        m = re.match(r"^- ([^:]+):\s*(.*)$", text)
        key = find(m.group(1), allowed) if m else None
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


def check(lines, ck, project=None):
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
                ck.bad(n, "structure", "Section 1: the line \"%s\" is not one of A1 to A8." % short(text))
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
                ck.bad(n, "check 7", "Section 1, %s: the line must end with (worked out), (asked) or (assumed)." % q)
                answer = rest.strip()
            else:
                answer = rest[: hm.start()].strip()
                how[q] = (n, h)
            if not answer:
                ck.bad(n, "check 7", "Section 1, %s has no answer." % q)
            answers[q] = (n, answer)
        for q in sorted(A_LABELS):
            if q not in answers:
                ck.bad(S[1].line, "structure", "Section 1: %s (%s) is missing." % (q, A_LABELS[q]))
        if S[1].table:
            ck.bad(S[1].table[0][0], "structure", "Section 1 has no table. Its eight lines start with a dash.")

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
        head = re.split(r"\.(?:\s|$)", a3, 1)[0]
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
            dash_values(ck, S[2])

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
        d3 = dash_values(ck, S[3])

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
            ownlist[i] = re.split(r"\s*\(", v, 1)[0].strip()   # the name alone, so the form error is reported once
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
    catchup = []     # (number, unit) in the catch-up's Rule
    runlogs, auditlogs = [], []
    for n, r in rows3:
        item = r["Item"].strip()
        where = "Section 3, row \"%s\"" % short(item)
        mt = find(r["Memory type"], MEMORY_TYPES + OTHER_TYPES)
        if not mt:
            ck.bad(n, "check 2", "%s: Memory type must be one of: %s." % (where, "; ".join(MEMORY_TYPES + OTHER_TYPES)))
        elif mt in MEMORY_TYPES and mt in decision and decision[mt][1] == "skip":
            ck.bad(n, "check 1", "%s: it is saved under %s, which section 2 marks `skip`. Either the type "
                   "is needed, or this row belongs under another type." % (where, mt))
        if mt == "Run log":
            runlogs.append((n, r))
        if mt == "Audit log":
            auditlogs.append((n, r))
        if mt in ("Audit log", "Side effect protection"):
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
            else:
                ck.bad(n, "check 2", "%s: the expiry part \"%s\" is not in one of the four forms: "
                       "`<number> <minutes, hours, days, working days, weeks, months or years> after <what>`, "
                       "`when <an event code can test>`, `replaced when <what>`, or `permanent: <reason>`. "
                       "Join two forms with a semicolon." % (where, short(p)))
            for num, unit in RE_NUMUNIT.findall(p):
                numbers.append((n, num, unit, where + ", expiry"))
        if forms and set(forms) <= {"replaced", "event"}:     # no set time: something must end it
            if "event" not in forms:
                ends, ask = "when it is replaced", ("What replaces it, and does code check that? Being replaced is "
                                                    "enough when something will replace it.")
            else:
                ends = "when it is replaced or on an event" if "replaced" in forms else "on an event"
                ask = "What removes it if the event never comes%s?" % (
                    " and nothing replaces it" if "replaced" in forms else "")
            ck.judge("%s stops only %s (`%s`). %s If nothing ever would, it lives forever: give it a set time as "
                     "well, as for `permanent`." % (where, ends, short(r["Expiry"], 60), ask))
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
        d4 = dash_values(ck, S[4]) if S[4].dash else {}
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

    # ---------------------------------------------------------------- section 5
    actions = {}
    d5 = {}
    any_approval = False

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
        d5 = dash_values(ck, S[5])
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
    if section_switch(6, built("External memory and retrieval") if "External memory and retrieval" in decision else None,
                      "section 2 marks External memory and retrieval `build`",
                      "section 2 marks External memory and retrieval `skip`"):
        rows6 = table(ck, S[6], H6)
        if not rows6:
            if rows6 is not None or not S[6].table:
                ck.bad(S[6].line, "check 17", "Section 6 has no rows. Section 2 marks retrieval `build`.")
            rows6 = []
        unique(ck, rows6, "What it looks for", 6)
        d6 = dash_values(ck, S[6])
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

    # ---------------------------------------------------------------- section 7
    task_rows = 0
    approval_tasks = False
    if section_switch(7, built("Prospective memory") if "Prospective memory" in decision else None, "section 2 marks Prospective memory `build`",
                      "section 2 marks Prospective memory `skip`"):
        rows7 = table(ck, S[7], H7)
        if not rows7:
            if rows7 is not None or not S[7].table:
                ck.bad(S[7].line, "check 20", "Section 7 has no rows. Section 2 marks prospective memory `build`.")
            rows7 = []
        unique(ck, rows7, "Task", 7)
        d7 = dash_values(ck, S[7])
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
            dash_values(ck, S[8])
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
    }
    cf = {"trig": trig,
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
    if search_used and not cf["indexed"]:
        ck.judge("Section 6 searches a source that section 3 does not save, so the case of an old or deleted item "
                 "found by its old wording is not asked for. Does the agent really keep no copy or index of it?")
    listed_tests = {}
    if 9 in S:
        rows9 = table(ck, S[9], H9)
        if rows9 is None:
            if not S[9].table:
                ck.bad(S[9].line, "check 8", "Section 9 has no table.")
            rows9 = []
        unique(ck, rows9, "Test", 9)
        if S[9].dash:
            dash_values(ck, S[9])
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
    if 10 in S:
        sec = S[10]
        text10 = " ".join(t for _, t in sec.dash)
        if sec.table:
            ck.bad(sec.table[0][0], "structure", "Section 10 has no table. Each item is a line starting with a dash.")
        if not sec.dash:
            ck.bad(sec.line, "check 7", "Section 10 is empty. It lists every assumed answer and every number "
                   "in the design, each with who chose it.")
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
        plain10 = text10.replace(",", "")
        missing = []
        for n, num, unit, where in numbers:
            val = num.replace(",", "")
            if val == "1" and where.endswith("size limit"):
                continue
            stem = unit.lower()
            if len(stem) > 3 and stem.endswith("s"):
                stem = stem[:-1]
            pat = r"(?<![\d.])%s\s+(?:[A-Za-z]+\s+){0,2}?%s" % (re.escape(val), re.escape(stem))
            if not re.search(pat, plain10, re.I) and (val, stem) not in [(m[0], m[1]) for m in missing]:
                missing.append((val, stem, unit, n, where))
        for val, stem, unit, n, where in missing:
            ck.bad(n, "check 7", "`%s %s` (%s) is not in section 10. Every number in an expiry, a size limit, an "
                   "approval lifetime, the stuck task time, the lease on a claimed action, the episode count, how "
                   "often the app is woken or how far "
                   "the catch-up looks back is listed there with the word "
                   "that follows it in the design, and whether the person chose it or it is a starting value."
                   % (val, unit, where))

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
    return facts, listed_tests


def report(path, ck, facts, listed_tests):
    out = ["check_design.py: %s" % path, ""]
    probs = sorted(set(ck.problems))
    if probs:
        out.append("PROBLEMS (%d)" % len(probs))
        for line, tag, text in probs:
            where = "line %d: " % line if line else ""
            out.append("  [%s] %s%s" % (tag_text(tag), where, text))
        out.append("")
    if ck.reviewer:
        out.append("FOR THE REVIEWER TO JUDGE (%d) - a script cannot decide these, and none counts as passed"
                   % len(ck.reviewer))
        for text in ck.reviewer:
            out.append("  - %s" % text)
        out.append("")
    left_out = [n for n in (5, 6, 7, 8) if n not in ck.sections]
    if left_out and not probs:
        out.append("SECTIONS LEFT OUT because they do not apply: %s" % ", ".join(
            "%d (%s)" % (n, TITLES[n]) for n in left_out))
        out.append("")
    if facts is not None and not probs:
        na = [(line_no, NOT_NEEDED_BECAUSE[needs]) for name, line_no, needs, why in TESTS
              if not facts[needs] and name not in listed_tests
              and not (needs == "episodes" and facts.get("episodes_maybe"))
              and not (needs == "suggestions" and facts.get("suggestions_maybe"))]
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
    out.append("")
    out.append("This script checks that the file is complete and agrees with itself. It cannot tell")
    out.append("whether the design is right for the agent, and it reads no code. Tags like [check 5]")
    out.append("point to lines in CHECKLIST.md. The review in steps/5-review.md is still needed.")
    return "\n".join(out), (1 if probs else 0)


def main(argv):
    args = argv[1:]
    project = None
    paths = []
    i = 0
    while i < len(args):
        if args[i] in ("-h", "--help"):
            print(__doc__)
            return 0
        if args[i] == "--project":
            if i + 1 >= len(args):
                sys.stderr.write("--project needs a path\n")
                return 2
            project = args[i + 1]
            i += 2
            continue
        paths.append(args[i])
        i += 1
    if len(paths) != 1:
        sys.stderr.write("usage: python3 -B check_design.py MEMORY-DESIGN.md [--project <path>]\n")
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
    facts, listed_tests = check(lines, ck, project)
    text, code = report(paths[0], ck, facts, listed_tests)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
