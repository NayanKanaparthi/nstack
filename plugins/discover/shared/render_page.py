#!/usr/bin/env python3
"""Check discovery.json and build discovery.html.

Usage:
    python render_page.py discovery.json discovery.html

Reads the discovery data, checks it against the rules in shared/data.md,
works out the evidence labels and the interview tallies mechanically (so they
never depend on anyone's judgement), and writes one self-contained page from
page-template.html, which sits next to this script.

If the data has any problem, nothing is written: every problem is listed and
the script exits with status 1. Fix the data and run it again.

Python 3 standard library only.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import tempfile
import unicodedata

KIT_VERSION = "2.3.0"
# The sections of data.md's starting file that a step not run (or skipped) leaves exactly as they are.
STARTING = {
    "fill_in_sentence": ("[who] struggles with [problem] when [situation], handles it today by [workaround], "
                         "and would pay [amount or way] for a better option"),
    "evidence": {"run_on": [], "results": [], "products": [], "language": [],
                 "unread_pages": {"count": 0, "wouldnt_open": []}, "checked": {"searches": 0, "pages_read": 0},
                 "suggested_checks": [], "checked_in_fresh_context": False},
    "stress_test": {"critics": [], "forcing": [], "changes": []},
    "interview_plan": {"talk_to": "", "reach": "", "where": [], "big_questions": [], "guide": [], "money": [],
                       "commitment_ask": "", "pass_marks": [], "question_check": [], "outreach": [],
                       "notes_fields": ["pain", "workaround", "money", "goal", "obstacle", "people mentioned",
                                        "follow-up"],
                       "approved_by_student": False},
}
MARKER = "__DISCOVERY_DATA__"

# ---------------------------------------------------------------------------
# Words and values the data may use (see shared/data.md)
# ---------------------------------------------------------------------------

TOP_REQUIRED = [
    "kit_version", "created", "updated", "entry", "mode", "steps",
    "waiting_on_student", "area", "problems", "idea", "fill_in_sentence",
    "solution_words", "who_counts", "assumptions", "kill_criteria", "evidence",
    "stress_test", "interview_plan", "interviews", "log",
]
TOP_OPTIONAL = ["problems_note"]

STEP_ORDER = ["find_problems", "frame", "evidence", "stress_test",
              "interview_plan", "interview_sort"]
STEP_VALUES = {
    "find_problems": ["not_run", "running", "waiting", "done", "skipped"],
    "frame": ["not_run", "waiting", "done"],
    # "skipped": a later command passed over this step (contract v1.8 point 2). It can still be run later.
    "evidence": ["not_run", "running", "done", "skipped"],
    "stress_test": ["not_run", "waiting", "done", "skipped"],
    "interview_plan": ["not_run", "waiting", "done", "skipped"],
    # "running": the privacy question about names in the notes is asked (contract v1.6 point 9)
    "interview_sort": ["not_run", "running", "done"],
}
STEP_COMMAND = {
    "find_problems": "/discover-find-problems", "frame": "/discover-frame", "evidence": "/discover-evidence",
    "stress_test": "/discover-stress-test", "interview_plan": "/discover-interview-plan",
    "interview_sort": "/discover-interview-sort",
}

# Evidence item shape from the evidence check v6, plus "signal".
SIDES = {"for", "against", "context"}
RESULTS = {"counts", "set aside", "removed"}
KINDS = {"own words", "number", "organisation fact"}
REASONS = {
    "second_hand", "stake", "not_original", "vague_amount", "indirect",
    "group_not_shown", "old", "could_not_open", "pasted", "not_on_page",
    "off_target",
    "author_not_shown",  # added by the kit (not in v6): a seller-run forum post with no author or date shown
}
SIGNALS = ["complaint", "money spent", "time spent", "workaround", "switched",
           "asked for recommendations", "none"]
ITEM_KEYS = ["side", "result", "reason", "kind", "quote", "who", "when", "where",
             "did", "note", "link", "voice", "found_in_check", "signal"]

LABELS = {
    "supported": "The web backs this up",
    "contradicted": "The web points the other way",
    "mixed": "People are split",
    "thin": "Too little to tell",
    "nothing": "Nothing solid found",
}

ASSUMPTION_KINDS = ["problem", "people", "today", "future"]
IMPORTANCE = ["high", "medium", "low"]
EVIDENCE_NOW = ["strong", "weak", "none"]
# Where a part of the idea or an assumption came from (contract v2.1 point 1).
SOURCES = ["student", "checked sources", "ai guess", "interviews"]
IDEA_SOURCES = ["student", "checked sources", "ai guess"]  # the idea's parts never come from interviews
IDEA_SOURCE_KEYS = ["who", "problem", "today", "who_pays"]
PRODUCT_KINDS = ["competitor", "workaround", "general AI assistant",
                 "person or agency", "do nothing"]
CRITIC_ROLES = ["skeptic", "outsider", "first-principles", "practical"]
DECISIONS = ["pending", "accepted", "rejected"]
GUIDE_SECTIONS = ["warm-up", "last time", "how important", "how costly",
                  "how they chose", "wrap-up", "commitment"]
UNTAGGED_SECTIONS = {"warm-up", "wrap-up", "commitment"}
QUESTION_PROBLEMS = ["yes/no", "future", "hypothetical", "leading", "pitch",
                     "two questions"]
FACT_SIDES = ["for", "against", "context"]
FACT_KINDS = ["did", "said would", "opinion"]
FACT_TAGS = ["pain", "workaround", "money", "goal", "obstacle"]
# Things a person raised on their own that the assumptions don't cover (contract v2.2 point 2).
FINDING_KINDS = ["new problem", "workaround", "solution idea", "customer group"]
FINDING_ABOUT_WORDS = 12
# What the fill-in sentence may not still hold once Frame has run: an empty slot or a slot name.
FILL_IN_SLOTS = ["[not said yet]", "[who]", "[problem]", "[situation]", "[workaround]", "[amount or way]"]
LOG_STEPS = ["discover", "find-problems", "frame", "evidence", "stress-test",
             "interview-plan", "interview-sort"]
NO_EVIDENCE = "no evidence either way"
# question_check "rewrite" values for a question that was dropped, not rewritten:
# "dropped" (it failed two check rounds) and this one, for a probe dropped because
# its main question was rewritten. Only this one may have an empty "problem".
DROPPED_MAIN_CHANGED = "dropped: main question changed"

# Interview questions that ask about the future or a hypothetical. The page
# refuses to carry them. This is a backstop with a fixed list, published in
# shared/data.md; the question-check sub-agent is the main guard.
# Each entry: (pattern, what the matched words do).
MIGHT = "asks what someone might do"
HYPOTHETICAL = "is a hypothetical"
FUTURE = "asks about the future"
# The patterns are matched after plain_text() below, so every apostrophe-like
# character is a plain "'" and invisible format characters are gone. "if" may be
# followed by a comma ("If, such a tool existed").
ACTIONS = r"(?:buy|pay|use|switch|try|sign|subscribe)"
IF = r"\bif[\s,]+"
# A word, for "within n words": any run of characters between spaces ("in-house", "company's",
# "team,", "Dr.", "R&D", "\u201cthe"), as data.md publishes.
W = r"\S+"
FUTURE_PATTERNS = [
    (r"\bwould(?:n'?t)?\b", MIGHT),
    (r"\bwill\s+(?:you|your|they|people)\b", FUTURE),
    (r"\b(?:who|what|which)\s+will\b", FUTURE),
    (r"\bwill\s+(?:" + W + r"\s+){0,3}" + ACTIONS + r"\b", FUTURE),
    (r"\bwon'?t\s+(?:you|your|they|people)\b", FUTURE),
    (r"\b(?:you|they)'d\b", MIGHT),
    (r"\b\w+'ll\b", FUTURE),
    (r"\bmight\s+(?:you|they)\b", MIGHT),
    (r"\bhow\s+much\s+could\s+(?:you|they)\b", MIGHT),
    (r"\bhow\s+likely\b", MIGHT),
    (r"\blikely\s+(?:are|is)\s+(?:you|they|it|he|she|we)\s+to\b", MIGHT),
    (r"\blikely\s+to\s+(?:buy|pay|use|switch|try)\b", MIGHT),
    (r"\b(?:are|is|am)\s+(?:you|they|it|he|she|we|i|people)\b\S*\s+(?:" + W + r"\s+){0,3}likely\s+to\b", MIGHT),
    (r"(?<!\bdid you )(?<!\bdid they )(?<!\bdid we )(?<!\bdid he )(?<!\bdid she )\b(?:wants?\s+to|wanna)\s+"
     + ACTIONS + r"\b", MIGHT),
    (r"\bwhat\s+if\b", HYPOTHETICAL),
    (IF + r"such\b", HYPOTHETICAL),
    (r"\bsay\s+there(?:\s+(?:was|were|is)|'s)\b", HYPOTHETICAL),
    (IF + r"(?:there|it|this|that|such)\s+(?:was|were|existed)\b", HYPOTHETICAL),
    (IF + r"there(?:\s+is|'s)\b", HYPOTHETICAL),  # "if there is", "if there's" (same family as "say there is")
    (IF + r"(?:such\s+)?an?\s+" + W + r"(?:\s+" + W + r")?\s+(?:existed|did|was|were)\b", HYPOTHETICAL),
    (IF + r"(?:" + W + r"\s+){1,4}existed\b", HYPOTHETICAL),
    (r"\bshould\s+(?:" + W + r"\s+){0,4}exist\b", HYPOTHETICAL),
    (r"(?:^|[,;:(\[.!?])\s*assuming\b", HYPOTHETICAL),
    (IF + r"(?:we|i|someone|somebody|a\s+company|an\s+app)\s+(?:built|made|offered|launched|created|had|could)\b",
     HYPOTHETICAL),
    (IF + r"you\s+(?:could|had|were|got)\b", HYPOTHETICAL),
    (r"\bimagine\b", HYPOTHETICAL),
    (r"\bsuppos(?:e|ing)\b", HYPOTHETICAL),
    (r"\bhypothetical", HYPOTHETICAL),
    (r"\bin\s+the\s+future\b", FUTURE),
    (r"\bwilling\s+to\b", FUTURE),
    (r"\bsee\s+yourself\b", FUTURE),
    (r"\b(?:going|plan|planning)\s+to\s+" + ACTIONS + r"\b", FUTURE),
]

EMAIL = re.compile(r"[^\s@<>()\[\],;:\"']+@[^\s@<>()\[\],;:\"']+\.[^\W\d_]{2,}")
PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
# Not phone numbers (data.md): one or more dates, and a number grouped in threes by spaces or dots.
ONE_DATE = r"(?:\d{4}[-.]\d{1,2}[-.]\d{1,2}|\d{1,2}[-.]\d{1,2}[-.](?:\d{4}|\d{2}))"
DATE_RUN = re.compile(ONE_DATE + r"(?:\s*[-\u2013]?\s*" + ONE_DATE + r")*")
THOUSANDS = re.compile(r"\d{1,3}(?:([ .])\d{3})(?:\1\d{3})*")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Helpers copied from the evidence check v6 (build_report.py). Unchanged.
# ---------------------------------------------------------------------------

def page_of(link):
    """Two links to the same page (ignoring #fragment and ?query) are one page."""
    return re.sub(r"[#?].*$", "", link).rstrip("/").lower()


def text(value):
    return isinstance(value, str) and value.strip() != ""


def grade(assumption):
    """Work out the label from the items. Mechanical on purpose."""
    sides = {}
    for side in ("for", "against"):
        counted = [i for i in assumption.get("items", [])
                   if i["side"] == side and i["result"] == "counts"]
        sides[side] = {
            "voices": len({i["voice"].strip().lower() for i in counted}),
            "pages": len({page_of(i["link"]) for i in counted}),
            "acted": any(text(i.get("did")) or i["kind"] != "own words" for i in counted),
            "number": any(i["kind"] == "number" for i in counted),
        }
    f, a = sides["for"], sides["against"]
    why = ""
    if f["voices"] == 0 and a["voices"] == 0:
        status = "nothing"
    elif f["voices"] > 0 and a["voices"] > 0:
        status = "mixed"
    else:
        name, side = ("supported", f) if f["voices"] else ("contradicted", a)
        if side["voices"] < 2:
            status, why = "thin", "one_voice"
        elif side["pages"] < 2:
            status, why = "thin", "one_page"
        elif not side["acted"]:
            status, why = "thin", "opinions_only"
        elif assumption.get("needs_number") and not side["number"]:
            status, why = "thin", "needs_number"
        else:
            status = name
    all_counted = [i for i in assumption.get("items", [])
                   if i["result"] == "counts" and i["side"] in ("for", "against")]
    assumption["_grade"] = {
        "status": status,
        "why": why,
        "for": f["voices"],
        "against": a["voices"],
        "voices": len({i["voice"].strip().lower() for i in all_counted}),
        "pages": len({page_of(i["link"]) for i in all_counted}),
    }
    return assumption["_grade"]


# ---------------------------------------------------------------------------
# Small checks
# ---------------------------------------------------------------------------

def is_link(value):
    """Only http and https links are allowed anywhere on the page. The scheme may be in any
    letter case ("HTTPS://"), the same as the page's own isWebLink() check."""
    return isinstance(value, str) and re.fullmatch(r"https?://\S+", value, re.I) is not None


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def is_date(value):
    if not isinstance(value, str) or not DATE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


# The characters that count as an apostrophe, a closed list published in data.md: backtick,
# acute accent, modifier letters (prime, turned comma, apostrophe), Hebrew geresh, Armenian
# apostrophe, the curly and reversed single quotes, prime and reversed prime, the saltillo,
# and the fullwidth apostrophe and grave accent.
APOSTROPHE_CHARS = ("\u0060\u00b4\u02b9\u02bb\u02bc\u055a\u05f3\u2018\u2019\u201b\u2032\u2035"
                    "\ua78b\ua78c\uff07\uff40")
APOSTROPHES = str.maketrans({ch: "'" for ch in APOSTROPHE_CHARS})
QUESTION_MARKS = "?\uff1f\ufe56"  # the question mark, fullwidth and small


def is_invisible(ch):
    """A character a reader doesn't see: every Unicode format character (category Cf: zero-width
    spaces, soft hyphens, word joiners, direction marks), the combining grapheme joiner and the
    variation selectors (U+FE00 to U+FE0F and U+E0100 to U+E01EF)."""
    code = ord(ch)
    return (unicodedata.category(ch) == "Cf" or code == 0x034F or 0xFE00 <= code <= 0xFE0F
            or 0xE0100 <= code <= 0xE01EF)


def visible_text(value):
    """The text as a reader sees it: Unicode NFC form (a letter and a separately typed accent
    are the accented letter), with invisible characters removed. Every check that reads
    kit-written or quoted text starts from this: the phrase checks, the contact check and the
    length rules (data.md)."""
    value = unicodedata.normalize("NFC", value)
    return "".join(ch for ch in value if not is_invisible(ch))


def plain_text(value):
    """visible_text, with every apostrophe-like character a plain "'": for every phrase check."""
    return visible_text(value).translate(APOSTROPHES)


def word_count(value):
    """Words as data.md counts them for a limit: runs between spaces that hold a letter or a
    digit, so a lone dash or bullet is not a word."""
    return len([w for w in visible_text(value).split() if is_word(w)])


def is_word(token):
    """A run between spaces that holds a letter or a digit (data.md): "___" and "-" are not words."""
    return re.search(r"[^\W_]", token) is not None


def norm(value):
    """Lower case, straight quotes, single spaces: for matching phrases to quotes."""
    value = plain_text(value)
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", value).strip().lower()


def future_reason(question):
    """Name the exact words that make a question future or hypothetical, or return ""."""
    # Every kind of space (a no-break space too) is one plain space, so the published list matches.
    # Double quotation marks are ignored ("will the team \u201cpay\u201d" reads "will the team pay").
    question = re.sub(r'["\u201c\u201d\u201e\u201f\u00ab\u00bb\uff02\u2033\u301d\u301e]', "", plain_text(question))
    # Single quotation marks around a word ("will the team 'pay'") are ignored too; an apostrophe inside
    # a word ("won't") stays.
    question = re.sub(r"\s+", " ", re.sub(r"(?<!\w)'|'(?!\w)", "", question))
    for pattern, what in FUTURE_PATTERNS:
        match = re.search(pattern, question, re.I)
        if match:
            return f'uses "{match.group(0)}", which {what}'
    return ""


def has_contact(value):
    if not isinstance(value, str):
        return False
    value = plain_text(value)
    if EMAIL.search(value):
        return True
    for match in PHONE.finditer(value):
        found = match.group(0).strip()
        groups = re.findall(r"\d+", found)
        if all(len(g) == 4 and g[:2] in ("19", "20") for g in groups):
            continue  # a run of years such as "2023 2024 2025", not a phone number
        if DATE_RUN.fullmatch(found) or THOUSANDS.fullmatch(found):
            continue  # dates such as "2026-03-01 - 2026-05-01", or a number such as "1 200 000 000"
        if sum(len(g) for g in groups) >= 10:
            return True
    return False


def contact_fields(value, where):
    """Every string inside value, with its location: for the privacy check on interviews."""
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, list):
        for index, entry in enumerate(value):
            yield from contact_fields(entry, f"{where}[{index}]")
    elif isinstance(value, dict):
        for key, entry in value.items():
            yield from contact_fields(entry, f"{where}.{key}")


def broken_text(value, where):
    """Locations of strings (or keys) that can't be saved as UTF-8, such as lone surrogates."""
    found = []
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            found.append(where)
    elif isinstance(value, list):
        for index, entry in enumerate(value):
            found += broken_text(entry, f"{where}[{index}]")
    elif isinstance(value, dict):
        for key, entry in value.items():
            name = key if isinstance(key, str) else repr(key)
            try:
                name.encode("utf-8")
            except UnicodeEncodeError:
                found.append(f"{where} (a field name)")
                name = name.encode("utf-8", "replace").decode("utf-8")
            found += broken_text(entry, f"{where}.{name}" if where else name)
    return found


# Kit-written text is held to the plain-words length rule (contract v1.3 point 7,
# v1.6 point 7): "under 25 words", so a sentence of 25 words or more is refused.
MAX_WORDS = 24
# Words inside double quotation marks don't count. Quotation marks are paired left to
# right first (see without_quotations); only outside a quotation is a straight " right
# after a digit an inch mark (7/12").
QUOTE_PAIRS = {'"': '"', "\u201c": "\u201d"}
QUOTE_GAP = "\x00"  # stands where a quotation was: starts a sentence, counts as no word
# The length check is a finite, published algorithm (contract v1.7 point 1, built in v2.2).
# When the renderer can't tell whether a full stop ends a sentence, it doesn't end it there.
# A full stop never ends a sentence:
#   - when the next word starts with a digit ("approx. 40", "Jan. 2024");
#   - after a word of five letters or fewer that starts with a capital and goes on in lower
#     case ("Jan.", "Calif.", "Prof.", "Corp.", "Dr.", "Paris."), or a single initial ("J.");
#     a word in capitals ("NYU.", "UK.") can end a sentence;
#   - after a run of single letters with full stops ("U.S.A.", "e.g.");
#   - after a lower-case short form on this published list (any letter case).
SHORT_FORMS = {"approx.", "e.g.", "i.e.", "etc.", "vs.", "incl.", "esp.", "min.", "mins.", "hr.", "hrs.",
               "no.", "nos.", "est.", "ca.", "cf.", "fig.", "p.", "pp.", "vol.", "dept.", "wk.", "wks.",
               "mo.", "mos.", "yr.", "yrs.", "a.m.", "p.m.", "avg.", "sec.", "secs.", "ft.", "sq.", "lb.",
               "lbs.", "oz.", "misc.", "govt.", "al."}
LETTER_RUN = re.compile(r"(?:[^\W\d_]\.){2,}")
OPENERS = "\"'\u201c\u2018([" + QUOTE_GAP
CLOSERS = "\"'\u201d\u2019)]"


def short_capitalised(word):
    """A word of five letters or fewer that starts with a capital letter and goes on in lower
    case, in any script ("Jan.", "Calif.", "Köln.", "José."), or a single capital initial ("J.", "É.")."""
    core = word[:-1] if word.endswith(".") else ""
    # An accent with no composed form ("Q" + U+0303) is part of its letter, not a letter of its own.
    core = "".join(ch for ch in core.translate(APOSTROPHES) if not unicodedata.category(ch).startswith("M") and ch != "'")
    return (0 < len(core) <= 5 and core.isalpha() and core[0].isupper()
            and (len(core) == 1 or core[1:].islower()))


def is_short_form(word):
    """True for a word whose full stop never ends a sentence (see SHORT_FORMS above)."""
    return (word.lower() in SHORT_FORMS or LETTER_RUN.fullmatch(word) is not None
            or short_capitalised(word))


def starts_sentence(word):
    """A word can start a sentence when it starts with a capital letter or a digit, after
    any opening "(" or "[". An opening quotation mark doesn't start one."""
    bare = word.lstrip("([")
    return bare != "" and (bare[0].isupper() or bare[0].isdigit())


def ends_sentence(token, following):
    """True when a sentence ends after token: it ends in . ! or ? (before any closing
    quote or bracket), and the next word can start a sentence. A full stop never ends one
    before a digit, or after a short form."""
    core = token.rstrip(CLOSERS)
    if not core or core[-1] not in ".!?":
        return False
    if not starts_sentence(following):
        return False
    if core[-1] == ".":
        if following.lstrip("([")[0].isdigit():
            return False
        if is_short_form(core.lstrip(OPENERS)):
            return False
    return True


def without_quotations(text):
    """text with every quotation replaced by a gap. Quotation marks are paired left to
    right: an opening " or \u201c is closed by the next " or \u201d. While a quotation is open,
    the next matching mark closes it, even right after a digit. Outside a quotation, a
    straight " right after a digit is an inch mark (7/12") and is dropped. An opening mark
    that is never closed stays as an ordinary character, so the words after it count."""
    out = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"' and index > 0 and text[index - 1].isdigit():
            index += 1  # an inch mark: no quotation is open here
            continue
        if char in QUOTE_PAIRS:
            close = text.find(QUOTE_PAIRS[char], index + 1)
            if close != -1:
                inner = text[index + 1:close].rstrip()
                # A quotation that ends a sentence ("... it hurt.") still ends it, with its own mark, so
                # the full stop's digit rule applies only to a full stop.
                gap = " " + QUOTE_GAP + (inner[-1] if inner.endswith((".", "!", "?")) else "")
                index = close + 1
                # A closing bracket or quote right after the quotation stays attached to it.
                while index < len(text) and text[index] in CLOSERS:
                    gap += text[index]
                    index += 1
                out.append(gap + " ")
                continue
        out.append(char)
        index += 1
    return "".join(out)


def line_ends_sentence(tokens, next_tokens):
    """A line break ends a sentence only when the line ends in . ! or ?, under the same
    rules for full stops: a short form, or a next line that starts with a digit, keeps the
    sentence open. A greeting ("Hi Sam,") or a line ending in ":" runs on."""
    if not tokens:
        return False
    core = tokens[-1].rstrip(CLOSERS)
    if not core or core[-1] not in ".!?":
        return False
    if core[-1] == ".":
        if is_short_form(core.lstrip(OPENERS)):
            return False
        if next_tokens and next_tokens[0].lstrip("([")[:1].isdigit():
            return False
    return True


def sentences(text):
    """The sentences of text, each as its list of tokens, with quotations taken out. The text
    is read in Unicode NFC first, so "José" is one five-letter-or-fewer word however it was typed."""
    bare = without_quotations(visible_text(text))
    lines = [line.split() for line in bare.splitlines()]
    out, current = [], []
    for number, tokens in enumerate(lines):
        for index, token in enumerate(tokens):
            current.append(token)
            if index + 1 < len(tokens) and ends_sentence(token, tokens[index + 1]):
                out.append(current)
                current = []
        following = next((t for t in lines[number + 1:] if t), [])
        if line_ends_sentence(tokens, following) and current:
            out.append(current)
            current = []
    if current:
        out.append(current)
    return out


def quoted_spans(text):
    """The text inside each quotation, paired left to right as without_quotations pairs them."""
    spans = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"' and index > 0 and text[index - 1].isdigit():
            index += 1
            continue
        if char in QUOTE_PAIRS:
            close = text.find(QUOTE_PAIRS[char], index + 1)
            if close != -1:
                spans.append(text[index + 1:close])
                index = close + 1
                continue
        index += 1
    return spans


def quotation_problems(text):
    """What is wrong with the quotation marks of a kit-written field (contract v1.7 point 1),
    each phrased as what to change. Empty when they are fine."""
    problems = []
    text = visible_text(text)
    if re.search(r'\d"', text):
        problems.append('a straight " right after a digit. Write "10-inch" for a measure, or use curly '
                        'quotation marks \u201c \u201d for a quotation that ends in a number')
    if text.count('"') % 2:
        problems.append('an odd number of straight quotation marks ("). Close every quotation, or remove '
                        'the stray mark')
    depth = 0
    for char in text:
        if char == "\u201c":
            if depth:
                problems.append("a curly quotation that opens inside another. Close the first one before "
                                "opening the next")
                break
            depth = 1
        elif char == "\u201d":
            if not depth:
                problems.append("a closing curly quotation mark (\u201d) with no opening one (\u201c) before it")
                break
            depth = 0
    else:
        if depth:
            problems.append("a curly quotation (\u201c) that is never closed (\u201d)")
    for span in quoted_spans(text):
        count = len([w for w in span.split() if is_word(w)])
        if count > MAX_WORDS:
            problems.append(f"a quotation of {count} words. Keep a quotation here under 25 words; long "
                            f"quotes belong in an item's quote field")
    return problems


def long_sentence_details(text):
    """(word count, first words, full stops read as not ending it) for each sentence of 25
    words or more, outside quotation marks."""
    found = []
    for sentence in sentences(text):
        words = [w for w in sentence if is_word(w)]
        if len(words) > MAX_WORDS:
            kept = []
            for index, token in enumerate(sentence[:-1]):
                core = token.rstrip(CLOSERS)
                if not core.endswith((".", "!", "?")):
                    continue
                following = sentence[index + 1]
                shown_as = core.lstrip(OPENERS) or core
                if QUOTE_GAP in core:
                    shown_as = "the quotation ending in " + core[-1]
                if core.endswith(".") and following.lstrip("([")[:1].isdigit():
                    why = "the next word starts with a number"
                elif core.endswith(".") and is_short_form(core.lstrip(OPENERS)):
                    why = "it ends a short form (a short capitalised word, an initial, e.g. or U.S.)"
                elif following.startswith(QUOTE_GAP) or following[:1] in "\"'\u201c\u2018":
                    why = "the next word opens a quotation"
                else:
                    why = "the next word doesn't start with a capital letter or a digit"
                kept.append((shown_as, why))
            found.append((len(words), " ".join(words[:8]), kept))
    return found


def long_sentences(text):
    """(word count, first words) for each sentence of 25 words or more, outside quotation marks."""
    return [(count, start) for count, start, _ in long_sentence_details(text)]


def check_lengths(c, data):
    """Every sentence in the kit-written fields is under 25 words (quotes and the fill-in sentence exempt)."""
    def one(value, where):
        if isinstance(value, str):
            quotation = quotation_problems(value)
            for problem in quotation:
                c.problems.append(f"{where} has {problem}.")
            if quotation:
                return  # the sentences can't be counted until the quotation marks are fixed
            for count, start, kept in long_sentence_details(value):
                message = (f'{where} has a sentence of {count} words, starting "{start} ...". Keep every '
                           f"sentence under 25 words: split it. Words inside quotation marks don't count.")
                if kept:
                    reasons = "; ".join(f'"{token}": {why}' for token, why in kept)
                    message += (f" These marks don't end a sentence here: {reasons}. Reword so a sentence "
                                f"ends where you want it to.")
                c.problems.append(message)

    def each(value):
        return list(enumerate(value)) if isinstance(value, list) else []

    def part(value):
        return value if isinstance(value, dict) else {}

    def notes(items, where):
        # Every line the page shows on an item card, apart from the quote itself (v1.6 point 7).
        for index, item in each(items):
            for key in ("who", "where", "did", "note"):
                one(part(item).get(key), f"{where}.items[{index}].{key}")

    for index, problem in each(data.get("problems")):
        where = f"problems[{index}]"
        one(part(problem).get("statement"), f"{where}.statement")
        one(part(problem).get("who"), f"{where}.who")
        notes(part(problem).get("items"), where)
        one(part(part(problem).get("about_one")).get("what"), f"{where}.about_one.what")
    one(data.get("problems_note"), "problems_note")
    one(part(data.get("idea")).get("sentence"), "idea.sentence")
    for index, a in each(data.get("assumptions")):
        for key in ("if_true", "if_false"):
            one(part(a).get(key), f"assumptions[{index}].{key}")
    evidence = part(data.get("evidence"))
    for index, result in each(evidence.get("results")):
        where = f"evidence.results[{index}]"
        one(part(result).get("still_open"), f"{where}.still_open")
        for n_index, line in each(part(result).get("not_found")):
            one(line, f"{where}.not_found[{n_index}]")
        notes(part(result).get("items"), where)
    for index, product in each(evidence.get("products")):
        one(part(product).get("fact"), f"evidence.products[{index}].fact")
    stress = part(data.get("stress_test"))
    for index, critic in each(stress.get("critics")):
        for p_index, point in each(part(critic).get("points")):
            where = f"stress_test.critics[{index}].points[{p_index}]"
            one(part(point).get("text"), f"{where}.text")
            one(part(point).get("would_settle"), f"{where}.would_settle")
    for index, entry in each(stress.get("forcing")):
        one(part(entry).get("question"), f"stress_test.forcing[{index}].question")
    for index, change in each(stress.get("changes")):
        one(part(change).get("change"), f"stress_test.changes[{index}].change")
        one(part(change).get("why"), f"stress_test.changes[{index}].why")
    plan = part(data.get("interview_plan"))
    one(plan.get("talk_to"), "interview_plan.talk_to")
    for index, place in each(plan.get("where")):
        one(part(place).get("why"), f"interview_plan.where[{index}].why")
    for index, message in each(plan.get("outreach")):
        one(part(message).get("text"), f"interview_plan.outreach[{index}].text")


def shown(value):
    """A value for a message: text in double quotes, anything else as Python shows it."""
    return f'"{value}"' if isinstance(value, str) else f"{value!r} (not a single text value)"


def is_id(value, ids):
    """True only for a text value that is one of the known ids. Never raises on lists or numbers."""
    return isinstance(value, str) and value in ids


class Check:
    """Collects every problem instead of stopping at the first one."""

    def __init__(self):
        self.problems = []

    def need(self, condition, message):
        if not condition:
            self.problems.append(message)
        return bool(condition)

    def block(self, value, where, keys, optional=()):
        """value must be an object with exactly these keys (plus optional ones)."""
        if not isinstance(value, dict):
            self.problems.append(f"{where} must be an object with the fields {', '.join(keys)}.")
            return False
        for key in keys:
            self.need(key in value, f'{where}: the field "{key}" is missing.')
        for key in value:
            if key not in keys and key not in optional:
                self.problems.append(
                    f'{where}: unknown field "{key}". Allowed fields: {", ".join(list(keys) + list(optional))}.')
        return True

    def string(self, value, where, required=False):
        if not isinstance(value, str):
            self.problems.append(f"{where} must be text.")
            return False
        if required and not value.strip():
            self.problems.append(f"{where} is empty.")
            return False
        return True

    def flag(self, value, where):
        return self.need(isinstance(value, bool), f"{where} must be true or false.")

    def one_of(self, value, allowed, where):
        return self.need(isinstance(value, str) and value in allowed,
                         f'{where} is {shown(value)}, but it must be one of: {", ".join(allowed)}.')

    def items_list(self, value, where):
        if not isinstance(value, list):
            self.problems.append(f"{where} must be a list.")
            return []
        return value

    def strings(self, value, where, required=False):
        out = []
        for index, entry in enumerate(self.items_list(value, where)):
            if self.string(entry, f"{where}[{index}]", required):
                out.append(entry)
        return out


# ---------------------------------------------------------------------------
# Section checks
# ---------------------------------------------------------------------------

def check_item(c, item, where):
    """One evidence item: the v6 item rules plus "signal"."""
    if not c.block(item, where, ITEM_KEYS):
        return False
    ok = True
    ok &= c.one_of(item.get("side"), sorted(SIDES), f"{where}.side")
    ok &= c.one_of(item.get("result"), sorted(RESULTS), f"{where}.result")
    ok &= c.one_of(item.get("kind"), sorted(KINDS), f"{where}.kind")
    ok &= c.one_of(item.get("signal"), SIGNALS, f"{where}.signal")
    ok &= c.string(item.get("quote"), f"{where}.quote", required=True)
    ok &= c.need(is_link(item.get("link")),
                 f"{where}.link must start with http:// or https:// (got {item.get('link')!r}).")
    c.string(item.get("who"), f"{where}.who", required=True)
    ok &= c.string(item.get("voice"), f"{where}.voice", required=True)
    for key in ("when", "where", "note"):
        c.string(item.get(key), f"{where}.{key}")
    ok &= c.string(item.get("did"), f"{where}.did")
    c.flag(item.get("found_in_check"), f"{where}.found_in_check")
    reason = item.get("reason")
    if c.string(reason, f"{where}.reason"):
        if item.get("result") in ("set aside", "removed"):
            c.need(reason in REASONS,
                   f'{where}: a set aside or removed item needs a "reason" from: {", ".join(sorted(REASONS))}.')
        elif item.get("result") == "counts" and item.get("side") in ("for", "against"):
            c.need(not reason,
                   f'{where}: an item that counts must not carry a "reason". Use "note" for a caveat.')
        elif reason:
            c.need(reason in REASONS,
                   f'{where}.reason "{reason}" is not one of: {", ".join(sorted(REASONS))}.')
    return ok


def counted_for(items):
    return [i for i in items if isinstance(i, dict) and i.get("result") == "counts"
            and i.get("side") == "for" and isinstance(i.get("voice"), str)
            and is_link(i.get("link"))]


def problem_counts(problem):
    good = counted_for(problem.get("items") if isinstance(problem.get("items"), list) else [])
    return {
        "voices": len({i["voice"].strip().lower() for i in good}),
        "pages": len({page_of(i["link"]) for i in good}),
    }


def most_on_one_page(problem):
    """The most different voices, among a problem's counted "for" items, that sit on one page.
    The page notes it when it is 2 or more ("4 of these are on one page")."""
    good = counted_for(problem.get("items") if isinstance(problem.get("items"), list) else [])
    by_page = {}
    for i in good:
        by_page.setdefault(page_of(i["link"]), set()).add(i["voice"].strip().lower())
    return max((len(v) for v in by_page.values()), default=0)


def same_statement(one, other):
    """Two statements are the same when they match ignoring letter case, spaces, quote styles
    and a full stop at the end."""
    return isinstance(one, str) and isinstance(other, str) and \
        norm(one).rstrip(".") == norm(other).rstrip(".") != ""


def covered_by_problem(data):
    """Contract v2.1 point 5: for an area entry, an assumption whose statement is the picked
    problem's statement, word for word, was already checked in Find problems. Returns
    {assumption id: picked problem id}."""
    if data.get("entry") != "area":
        return {}
    listed = data.get("problems") if isinstance(data.get("problems"), list) else []
    picked = [p for p in listed if isinstance(p, dict) and p.get("picked") is True]
    if len(picked) != 1:
        return {}
    problem = picked[0]
    assumptions = data.get("assumptions") if isinstance(data.get("assumptions"), list) else []
    return {a["id"]: problem.get("id") for a in assumptions
            if isinstance(a, dict) and isinstance(a.get("id"), str)
            and same_statement(a.get("statement"), problem.get("statement"))}


def check_top(c, data):
    if not isinstance(data, dict):
        c.problems.append("The file must hold one object with the fields listed in shared/data.md.")
        return False
    for key in TOP_REQUIRED:
        c.need(key in data, f'Top level: the field "{key}" is missing.')
    for key in data:
        if key not in TOP_REQUIRED and key not in TOP_OPTIONAL:
            c.problems.append(
                f'Top level: unknown field "{key}". Only the sections in shared/data.md are allowed.')
    c.need(isinstance(data.get("kit_version"), str)
           and re.fullmatch(r"\d+\.\d+\.\d+", data.get("kit_version")) is not None,
           f'kit_version must look like "{KIT_VERSION}".')
    for key in ("created", "updated"):
        c.need(is_date(data.get(key)), f'{key} must be a date written YYYY-MM-DD.')
    if is_date(data.get("created")) and is_date(data.get("updated")):
        c.need(data["updated"] >= data["created"], "updated must not be earlier than created.")
    c.one_of(data.get("entry"), ["idea", "area"], "entry")
    c.one_of(data.get("mode"), ["step", "path"], "mode")
    c.string(data.get("waiting_on_student"), "waiting_on_student")
    if "problems_note" in data:
        c.string(data.get("problems_note"), "problems_note")
    return True


def check_steps(c, data):
    steps = data.get("steps")
    if not c.block(steps, "steps", STEP_ORDER):
        return {key: "not_run" for key in STEP_ORDER}
    clean = {}
    for key in STEP_ORDER:
        value = steps.get(key)
        clean[key] = value if value in STEP_VALUES[key] else "not_run"
        c.one_of(value, STEP_VALUES[key], f"steps.{key}")
    entry = data.get("entry")
    if entry == "idea":
        c.need(clean["find_problems"] == "skipped",
               'steps.find_problems must be "skipped" when entry is "idea".')
    elif entry == "area":
        c.need(clean["find_problems"] != "skipped",
               'steps.find_problems can only be "skipped" when entry is "idea".')
    # Real dependencies, not strict order (contract v1.8 point 5).
    if clean["frame"] != "not_run":
        c.need(clean["find_problems"] in ("done", "skipped"),
               f'steps.frame is "{clean["frame"]}", but steps.find_problems is "{clean["find_problems"]}". '
               f"Frame needs a picked problem from /discover-find-problems, or an idea (find_problems \"skipped\").")
    later = STEP_ORDER[STEP_ORDER.index("frame") + 1:]
    for key in later:
        if clean[key] not in ("not_run", "skipped"):
            c.need(clean["frame"] == "done",
                   f'steps.{key} is "{clean[key]}", but steps.frame is "{clean["frame"]}". '
                   f"Every step after Frame needs /discover-frame done first.")
    for index, key in enumerate(later):
        started_after = [k for k in later[index + 1:] if clean[k] not in ("not_run", "skipped")]
        if clean[key] == "not_run" and started_after:
            c.need(False, f'steps.{key} is "not_run", but steps.{started_after[0]} has started. '
                          f'Mark a step a later command passed over as "skipped".')
        if clean[key] == "skipped":
            c.need(bool(started_after),
                   f'steps.{key} is "skipped", but no later step has started. '
                   f'Only a step a later command passed over is "skipped".')
    waiting = [k for k in STEP_ORDER if clean[k] == "waiting"]
    note = data.get("waiting_on_student")
    if isinstance(note, str):
        if waiting:
            c.need(note.strip() != "",
                   f"waiting_on_student is empty, but {', '.join('steps.' + w for w in waiting)} "
                   f"is waiting. Name the open decision in a plain sentence.")
        elif clean["interview_sort"] == "running":
            # The privacy question about names in the notes is waiting on the student (v1.6 point 9).
            c.need(note.strip() != "",
                   'waiting_on_student is empty, but steps.interview_sort is "running", so the student '
                   "owes an answer about the names in their notes. Say so in a plain sentence.")
        elif "running" not in (clean["evidence"], clean["find_problems"]):
            c.need(note.strip() == "",
                   "waiting_on_student must be empty when no step is waiting on the student.")
    return clean


def check_area_and_problems(c, data, steps):
    area = data.get("area")
    if c.block(area, "area", ["text", "people"]):
        c.string(area.get("text"), "area.text")
        c.string(area.get("people"), "area.people")
        if data.get("entry") == "area" and steps["find_problems"] in ("running", "waiting", "done"):
            c.string(area.get("text"), "area.text", required=True)

    problems = c.items_list(data.get("problems"), "problems")
    ids = []
    picked = 0
    for index, problem in enumerate(problems):
        where = f"problems[{index}]"
        if not c.block(problem, where, ["id", "statement", "who", "signals", "items", "picked"],
                       optional=["about_one"]):
            continue
        pid = problem.get("id")
        if c.need(isinstance(pid, str) and re.fullmatch(r"P[1-9]\d*", pid) is not None,
                  f'{where}.id must look like "P1".'):
            c.need(pid not in ids, f'{where}.id "{pid}" is used twice.')
            ids.append(pid)
            where = f"problems[{index}] ({pid})"
        c.string(problem.get("statement"), f"{where}.statement", required=True)
        c.string(problem.get("who"), f"{where}.who", required=True)
        if c.flag(problem.get("picked"), f"{where}.picked") and problem.get("picked"):
            picked += 1
        items = c.items_list(problem.get("items"), f"{where}.items")
        good_items = []
        for i_index, item in enumerate(items):
            spot = f"{where}.items[{i_index}]"
            if check_item(c, item, spot):
                good_items.append(item)
            if isinstance(item, dict):
                c.need(item.get("result") == "counts",
                       f'{spot}: only items that count stay on a problem (result is "{item.get("result")}").')
        counts = problem_counts({"items": good_items})
        c.need(counts["pages"] >= 2,
               f"{where} needs at least 2 counted items that show the problem, from at least 2 "
               f"different pages (it has {counts['pages']} page(s)).")
        if "about_one" in problem:
            # Optional: 2 or more of its voices are about one organisation or place, on any pages.
            # The checker names those voices, so the page's count can be checked against the items.
            about = problem.get("about_one")
            if c.block(about, f"{where}.about_one", ["voices", "what"]):
                c.string(about.get("what"), f"{where}.about_one.what", required=True)
                counted_voices = {i["voice"].strip().lower() for i in counted_for(good_items)}
                named = c.strings(about.get("voices"), f"{where}.about_one.voices", required=True)
                keys = [v.strip().lower() for v in named]
                c.need(len(keys) >= 2, f"{where}.about_one.voices names {len(keys)} voice(s). Name at least 2, "
                                       f"or leave about_one out.")
                c.need(len(set(keys)) == len(keys), f"{where}.about_one.voices names a voice twice.")
                for v_index, (voice, key) in enumerate(zip(named, keys)):
                    c.need(key in counted_voices,
                           f'{where}.about_one.voices[{v_index}] "{voice}" is not the voice of a counted "for" item '
                           f"on this problem. Name only voices it counts.")
        signals = c.strings(problem.get("signals"), f"{where}.signals", required=True)
        shown_for = sorted({i.get("signal") for i in counted_for(good_items)
                            if isinstance(i.get("signal"), str) and i.get("signal") != "none"})
        if isinstance(problem.get("signals"), list) and not problem.get("signals"):
            # Empty is allowed only when every counted "for" item shows "none" (contract v1.4 point 4).
            c.need(not shown_for,
                   f"{where}.signals is empty, but its counted items show {', '.join(shown_for)}. "
                   f"List the signals its items show. Leave it empty only when every counted item shows none.")
        item_signals = {i.get("signal") for i in good_items}
        for signal in signals:
            if c.one_of(signal, [s for s in SIGNALS if s != "none"], f"{where}.signals"):
                c.need(signal in item_signals,
                       f'{where}.signals lists "{signal}", but none of its items shows that signal.')
        c.need(len(set(signals)) == len(signals), f"{where}.signals repeats a signal.")
    c.need(len(problems) <= 8, f"problems has {len(problems)} entries. List at most 8.")
    c.need(picked <= 1, f"{picked} problems are marked picked. The student picks one.")

    # Order rule: independent voices, then pages.
    keyed = [problem_counts(p) for p in problems if isinstance(p, dict)]
    for index in range(1, len(keyed)):
        a, b = keyed[index - 1], keyed[index]
        c.need((a["voices"], a["pages"]) >= (b["voices"], b["pages"]),
               f"problems are out of order at position {index + 1}: list them by number of "
               f"different people or sources, then by number of pages, most first.")

    status = steps["find_problems"]
    note = data.get("problems_note", "")
    if status in ("not_run", "skipped", "running"):
        c.need(not problems, f"problems must be empty while steps.find_problems is \"{status}\".")
        c.need("problems_note" not in data, f'problems_note must be left out while steps.find_problems is "{status}".')
        if status != "running":
            # data.md: a section not run stays as in the starting file (an area entry's area.text aside).
            area = data.get("area") if isinstance(data.get("area"), dict) else {}
            c.need(area.get("people", "") == "" and (data.get("entry") == "area" or area.get("text", "") == ""),
                   f'area must be empty while steps.find_problems is "{status}": exactly as in the starting file in '
                   f"data.md (an area entry may hold its area in area.text).")
    else:
        if len(problems) < 5:
            c.need(isinstance(note, str) and note.strip() != "",
                   f"Only {len(problems)} problems survived the check. Say so honestly in problems_note.")
    if status == "done":
        c.need(picked == 1, 'steps.find_problems is "done", so exactly one problem must be picked by the student.')
    return ids


def check_frame(c, data, steps, problem_ids):
    idea = data.get("idea")
    idea_keys = ["sentence", "who", "problem", "today", "who_pays", "why_believe", "from_problem"]
    if c.block(idea, "idea", idea_keys, optional=["sources"]):
        for key in idea_keys:
            c.string(idea.get(key), f"idea.{key}")
        if "sources" in idea:
            # Where each part of the idea came from: the student, the checked sources or the AI's guess.
            sources = idea.get("sources")
            if not isinstance(sources, dict):
                c.problems.append(f"idea.sources must be an object, with any of the fields "
                                  f"{', '.join(IDEA_SOURCE_KEYS)}.")
            elif c.block(sources, "idea.sources", [], optional=IDEA_SOURCE_KEYS):
                for key, value in sources.items():
                    if key in IDEA_SOURCE_KEYS:
                        c.one_of(value, IDEA_SOURCES, f"idea.sources.{key}")
                        if value == "checked sources":
                            c.need(data.get("entry") == "area",
                                   f'idea.sources.{key} is "checked sources", but only an area entry has '
                                   f"checked sources from Find problems.")
                        c.need(isinstance(idea.get(key), str) and idea.get(key).strip() != "",
                               f"idea.sources.{key} says where idea.{key} came from, but idea.{key} is empty.")
        source = idea.get("from_problem")
        if isinstance(source, str) and source:
            if c.need(source in problem_ids, f'idea.from_problem "{source}" is not a problem id.'):
                listed = data.get("problems") if isinstance(data.get("problems"), list) else []
                chosen = [p for p in listed if isinstance(p, dict) and p.get("id") == source]
                c.need(bool(chosen) and chosen[0].get("picked") is True,
                       f'idea.from_problem is "{source}", but the student did not pick that problem.')
    c.string(data.get("fill_in_sentence"), "fill_in_sentence")
    c.strings(data.get("solution_words"), "solution_words", required=True)
    c.string(data.get("who_counts"), "who_counts")
    c.string(data.get("kill_criteria"), "kill_criteria")

    keys = ["id", "statement", "kind", "searchable", "importance", "evidence_now", "riskiest",
            "if_true", "if_false", "needs_number", "nearest_searchable", "confirmed_by_student"]
    assumptions = c.items_list(data.get("assumptions"), "assumptions")
    good = []
    ids = []
    for index, a in enumerate(assumptions):
        where = f"assumptions[{index}]"
        if not c.block(a, where, keys, optional=["source"]):
            continue
        aid = a.get("id")
        if c.need(isinstance(aid, str) and re.fullmatch(r"A[1-9]\d*", aid) is not None,
                  f'{where}.id must look like "A1".'):
            c.need(aid not in ids, f'{where}.id "{aid}" is used twice.')
            ids.append(aid)
            where = f"assumptions[{index}] ({aid})"
        c.string(a.get("statement"), f"{where}.statement", required=True)
        c.one_of(a.get("kind"), ASSUMPTION_KINDS, f"{where}.kind")
        c.one_of(a.get("importance"), IMPORTANCE, f"{where}.importance")
        c.one_of(a.get("evidence_now"), EVIDENCE_NOW, f"{where}.evidence_now")
        if "source" in a:
            if c.one_of(a.get("source"), SOURCES, f"{where}.source"):
                # Contract v2.1 point 1: an AI guess is a bet to test, so nobody has evidence for it yet.
                if a["source"] == "ai guess":
                    c.need(a.get("evidence_now") == "none",
                           f'{where} is the AI\'s guess, so its evidence now must be "none" (no evidence yet).')
                if a["source"] == "interviews":
                    # Contract v2.2 point 4: added from what people raised on their own, so "some" at most.
                    c.need(a.get("evidence_now") in ("weak", "none"),
                           f'{where} comes from your interviews, so its evidence now is "weak" or "none" at most.')
                    told = data.get("interviews") if isinstance(data.get("interviews"), list) else []
                    c.need(any(isinstance(i, dict) and i.get("new_findings") for i in told),
                           f'{where}.source is "interviews", but no interview records anything people raised '
                           f"on their own.")
                if a["source"] == "checked sources":
                    c.need(data.get("entry") == "area",
                           f'{where}.source is "checked sources", but only an area entry has checked sources '
                           f"from Find problems.")
        for key in ("searchable", "riskiest", "needs_number", "confirmed_by_student"):
            c.flag(a.get(key), f"{where}.{key}")
        for key in ("if_true", "if_false", "nearest_searchable"):
            c.string(a.get(key), f"{where}.{key}")
        if a.get("searchable") is True:
            c.string(a.get("if_true"), f"{where}.if_true", required=True)
            c.string(a.get("if_false"), f"{where}.if_false", required=True)
        a = dict(a)
        a["_where"] = where
        good.append(a)

    by_id = {a.get("id"): a for a in good if isinstance(a.get("id"), str)}
    for a in good:
        where = a["_where"]
        nearest = a.get("nearest_searchable")
        if a.get("kind") == "future":
            c.need(a.get("searchable") is False,
                   f"{where} is about future behaviour, so searchable must be false (interviews only).")
            if c.need(isinstance(nearest, str) and nearest.strip() != "",
                      f"{where} is about future behaviour, so nearest_searchable must name the "
                      f"assumption a search can check instead."):
                target = by_id.get(nearest)
                if c.need(target is not None, f'{where}.nearest_searchable "{nearest}" is not an assumption id.'):
                    c.need(target.get("searchable") is True and target.get("kind") != "future",
                           f'{where}.nearest_searchable points to "{nearest}", which is not searchable.')
        elif a.get("searchable") is True:
            c.need(nearest == "", f"{where} is searchable, so nearest_searchable must be empty.")
        elif isinstance(nearest, str) and nearest:
            target = by_id.get(nearest)
            if c.need(target is not None, f'{where}.nearest_searchable "{nearest}" is not an assumption id.'):
                c.need(target.get("searchable") is True,
                       f'{where}.nearest_searchable points to "{nearest}", which is not searchable.')

    # Riskiest: high importance with weak or no evidence, at most 3, searchable ones first.
    candidates = [a for a in good if a.get("importance") == "high" and a.get("evidence_now") in ("weak", "none")]
    risky = [a for a in good if a.get("riskiest") is True]
    for a in risky:
        c.need(a in candidates,
               f"{a['_where']} is marked riskiest, but riskiest needs high importance and weak or no evidence now.")
    c.need(len(risky) <= 3, f"{len(risky)} assumptions are marked riskiest. Mark at most 3.")
    if len(candidates) <= 3:
        for a in candidates:
            c.need(a.get("riskiest") is True,
                   f"{a['_where']} has high importance and weak or no evidence, so mark it riskiest.")
    else:
        c.need(len(risky) == 3,
               f"{len(candidates)} assumptions have high importance and weak or no evidence. Mark exactly 3 riskiest.")
        searchable = [a for a in candidates if a.get("searchable") is True]
        if len(searchable) >= 3:
            for a in risky:
                c.need(a.get("searchable") is True,
                       f"{a['_where']} is marked riskiest, but searchable ones come first and there are enough of them.")
        else:
            for a in searchable:
                c.need(a.get("riskiest") is True,
                       f"{a['_where']} should be marked riskiest: searchable ones come first.")

    status = steps["frame"]
    if status == "not_run":
        c.need(not assumptions, 'assumptions must be empty while steps.frame is "not_run".')
        if isinstance(idea, dict):
            c.need(all(idea.get(k, "") == "" for k in idea_keys) and not idea.get("sources"),
                   'idea must be empty while steps.frame is "not_run".')
        c.need(data.get("kill_criteria", "") == "", 'kill_criteria must be empty while steps.frame is "not_run".')
        c.need(not (isinstance(idea, dict) and "sources" in idea),
               'idea.sources must be left out while steps.frame is "not_run".')
        c.need(data.get("fill_in_sentence") == STARTING["fill_in_sentence"],
               'fill_in_sentence must stay the template from the starting file while steps.frame is "not_run".')
        c.need(data.get("who_counts", "") == "", 'who_counts must be empty while steps.frame is "not_run".')
        c.need(not data.get("solution_words"), 'solution_words must be empty while steps.frame is "not_run".')
    else:
        if isinstance(idea, dict):
            c.string(idea.get("sentence"), "idea.sentence", required=True)
        if c.string(data.get("fill_in_sentence"), "fill_in_sentence", required=True):
            filled = re.sub(r"\[\s*", "[", re.sub(r"\s*\]", "]", norm(data["fill_in_sentence"])))
            left = [slot for slot in FILL_IN_SLOTS if slot in filled]
            c.need(not left,
                   f'fill_in_sentence still holds {", ".join(chr(34) + s + chr(34) for s in left)}. Fill every '
                   f'slot: the student\'s words, the checked sources, or a guess written "[guess: ...]".')
        c.string(data.get("who_counts"), "who_counts", required=True)
        c.need(len(good) > 0, "assumptions is empty, but /discover-frame has run.")
        if data.get("entry") == "area" and isinstance(idea, dict):
            c.need(isinstance(idea.get("from_problem"), str) and idea.get("from_problem") != "",
                   "idea.from_problem must name the problem the student picked.")
    if status == "done":
        for a in good:
            c.need(a.get("confirmed_by_student") is True,
                   f'{a["_where"]}: steps.frame is "done", but the student has not confirmed this assumption.')
    return by_id


def check_evidence(c, data, steps, by_id):
    keys = ["run_on", "results", "products", "language", "unread_pages", "checked",
            "suggested_checks", "checked_in_fresh_context"]
    ev = data.get("evidence")
    links = set()
    if not c.block(ev, "evidence", keys):
        return {}, links
    run_on = c.strings(ev.get("run_on"), "evidence.run_on", required=True)
    c.need(len(set(run_on)) == len(run_on), "evidence.run_on repeats an assumption.")
    for aid in run_on:
        c.need(is_id(aid, by_id), f'evidence.run_on names "{aid}", which is not an assumption id.')
    # One run covers at most 3. A top-up after the stress test (contract v1.2 point 6) may
    # append more, but only riskiest assumptions a search can check, and never more than 6 in all.
    c.need(len(run_on) <= 6, f"evidence.run_on has {len(run_on)} assumptions. One run covers at most 3, "
                             f"and a top-up adds at most the 3 riskiest.")
    for aid in run_on[3:]:
        if is_id(aid, by_id):
            c.need(by_id[aid].get("riskiest") is True and by_id[aid].get("searchable") is True,
                   f'evidence.run_on lists "{aid}" after the first 3. Only a top-up adds more than 3, '
                   f"and it adds only riskiest assumptions a search can check.")

    graded = {}
    counted_quotes = []
    counted_links = set()
    seen = []
    pages = ev.get("unread_pages")
    total_unread = pages.get("count") if isinstance(pages, dict) and is_int(pages.get("count")) else None
    for index, result in enumerate(c.items_list(ev.get("results"), "evidence.results")):
        where = f"evidence.results[{index}]"
        if not c.block(result, where, ["assumption", "still_open", "not_found", "unread", "items"]):
            continue
        aid = result.get("assumption")
        if c.need(isinstance(aid, str) and aid in run_on, f'{where}.assumption {shown(aid)} is not in evidence.run_on.'):
            c.need(aid not in seen, f'{where}: "{aid}" has two results. Give each assumption one.')
            seen.append(aid)
            where = f"evidence.results[{index}] ({aid})"
        c.string(result.get("still_open"), f"{where}.still_open")
        gaps = c.strings(result.get("not_found"), f"{where}.not_found", required=True)
        unread = result.get("unread")
        if c.block(unread, f"{where}.unread", ["for", "against"], optional=["unclear"]):
            leaning = []
            # Contract v1.7 point 8 (built in v2.2): unread pages whose side wasn't clear get their own count.
            for side in ("for", "against", "unclear") if "unclear" in unread else ("for", "against"):
                if c.need(is_int(unread.get(side)) and unread.get(side) >= 0,
                          f"{where}.unread.{side} must be a whole number, 0 or more."):
                    if total_unread is not None:
                        c.need(unread[side] <= total_unread,
                               f"{where}.unread.{side} is {unread[side]}, more than the "
                               f"{total_unread} unread page(s) in evidence.unread_pages.count.")
                    if unread[side] > 0:
                        leaning.append(side)
            # A page whose side wasn't clear is in neither side's count, so the two never overlap.
            if total_unread is not None and all(is_int(unread.get(s)) for s in ("for", "against", "unclear")):
                c.need(unread["unclear"] + max(unread["for"], unread["against"]) <= total_unread,
                       f"{where}.unread.unclear ({unread['unclear']}) plus the larger side count "
                       f"({max(unread['for'], unread['against'])}) is more than the {total_unread} unread page(s) in "
                       f"evidence.unread_pages.count. A page whose side wasn't clear is counted only in unclear.")
            # Contract v1.6 point 3: gaps are honest about unread pages. The renderer can't
            # tell which side a line is about, so every line says it (it is true of every line).
            if leaning:
                for n_index, line in enumerate(gaps):
                    sides = " and ".join(s for s in leaning if s != "unclear")
                    seemed = (f"pages that seemed to hold items for the {sides} side weren't read" if sides
                              else "pages whose side wasn't clear weren't read")
                    c.need("in the pages read" in norm(line),
                           f'{where}.not_found[{n_index}] "{line}" must say "in the pages read", because '
                           f"{seemed} (unread.{leaning[0]} is above 0).")
        items = []
        all_ok = True
        for i_index, item in enumerate(c.items_list(result.get("items"), f"{where}.items")):
            if check_item(c, item, f"{where}.items[{i_index}]"):
                items.append(item)
                if is_link(item.get("link")):
                    links.add(item["link"])
                if item.get("result") == "counts":
                    if item.get("kind") == "own words" and item.get("side") in ("for", "against"):
                        counted_quotes.append(norm(item["quote"]))
                    counted_links.add(item["link"])
            else:
                all_ok = False
        if all_ok and is_id(aid, by_id) and isinstance(by_id[aid].get("needs_number"), bool):
            graded[aid] = grade({"items": [dict(i) for i in items],
                                 "needs_number": by_id[aid]["needs_number"]})

    products = c.items_list(ev.get("products"), "evidence.products")
    c.need(len(products) <= 4, f"evidence.products has {len(products)} entries. List at most 4.")
    for index, product in enumerate(products):
        where = f"evidence.products[{index}]"
        if not c.block(product, where, ["name", "link", "fact", "kind"]):
            continue
        c.string(product.get("name"), f"{where}.name", required=True)
        c.string(product.get("fact"), f"{where}.fact", required=True)
        c.one_of(product.get("kind"), PRODUCT_KINDS, f"{where}.kind")
        if c.need(is_link(product.get("link")), f"{where}.link must start with http:// or https://."):
            links.add(product["link"])

    for index, phrase in enumerate(c.strings(ev.get("language"), "evidence.language", required=True)):
        where = f"evidence.language[{index}]"
        c.need(word_count(phrase) <= 12, f'{where} is {word_count(phrase)} words. Keep phrases short (12 words or fewer).')
        whole = re.compile(r"(?<!\w)" + re.escape(norm(phrase)) + r"(?!\w)")
        c.need(bool(norm(phrase)) and any(whole.search(quote) for quote in counted_quotes),
               f'{where} "{phrase}" is not an exact phrase, in whole words, from a quote counted for or against '
               f'in people\'s own words (not background, an organisation fact or a number).')

    unread = ev.get("unread_pages")
    if c.block(unread, "evidence.unread_pages", ["count", "wouldnt_open"]):
        c.need(is_int(unread.get("count")) and unread.get("count") >= 0,
               "evidence.unread_pages.count must be a whole number, 0 or more.")
        stuck = c.items_list(unread.get("wouldnt_open"), "evidence.unread_pages.wouldnt_open")
        c.need(len(stuck) <= 3, "evidence.unread_pages.wouldnt_open lists at most 3 pages.")
        for index, page in enumerate(stuck):
            where = f"evidence.unread_pages.wouldnt_open[{index}]"
            if c.block(page, where, ["site", "link"]):
                c.string(page.get("site"), f"{where}.site", required=True)
                c.need(is_link(page.get("link")), f"{where}.link must start with http:// or https://.")

    checked = ev.get("checked")
    if c.block(checked, "evidence.checked", ["searches", "pages_read"]):
        for key in ("searches", "pages_read"):
            c.need(is_int(checked.get(key)) and checked.get(key) >= 0,
                   f"evidence.checked.{key} must be a whole number, 0 or more.")

    suggested = c.items_list(ev.get("suggested_checks"), "evidence.suggested_checks")
    c.need(len(suggested) <= 5, f"evidence.suggested_checks has {len(suggested)} links. List at most 5.")
    for index, link in enumerate(suggested):
        where = f"evidence.suggested_checks[{index}]"
        if c.need(is_link(link), f"{where} must be a link starting with http:// or https://."):
            c.need(link in counted_links, f"{where} is not the link of a counted item.")
    c.need(len(set(map(str, suggested))) == len(suggested), "evidence.suggested_checks repeats a link.")
    c.flag(ev.get("checked_in_fresh_context"), "evidence.checked_in_fresh_context")

    status = steps["evidence"]
    if status in ("not_run", "skipped"):
        c.need(ev == STARTING["evidence"],
               f'evidence must be empty while steps.evidence is "{status}": exactly as in the starting file in '
               f'data.md.')
    elif status == "running":
        c.need(len(run_on) > 0, 'steps.evidence is "running", so evidence.run_on must list the assumptions.')
        c.need(not ev.get("results"), 'evidence.results stays empty until the separate check has run.')
    else:
        c.need(len(run_on) > 0, 'steps.evidence is "done", so evidence.run_on must list the assumptions.')
        for aid in run_on:
            c.need(aid in seen, f'evidence.run_on names "{aid}", but evidence.results has nothing for it.')
        c.need(ev.get("checked_in_fresh_context") is True,
               'steps.evidence is "done", but checked_in_fresh_context is not true. '
               "The check must run in a fresh context.")
    return graded, links


def check_stress(c, data, steps, by_id, report_links):
    st = data.get("stress_test")
    if not c.block(st, "stress_test", ["critics", "forcing", "changes"], optional=["written_before_search"]):
        return
    if "written_before_search" in st:
        # True when the critics ran before any web search (contract v1.8 point 3).
        c.flag(st.get("written_before_search"), "stress_test.written_before_search")
    roles = []
    for index, critic in enumerate(c.items_list(st.get("critics"), "stress_test.critics")):
        where = f"stress_test.critics[{index}]"
        if not c.block(critic, where, ["role", "points"]):
            continue
        if c.one_of(critic.get("role"), CRITIC_ROLES, f"{where}.role"):
            c.need(critic["role"] not in roles, f'{where}: the role "{critic["role"]}" appears twice.')
            roles.append(critic["role"])
        points = c.items_list(critic.get("points"), f"{where}.points")
        c.need(len(points) <= 3, f"{where} has {len(points)} points. Each critic gives at most 3.")
        for p_index, point in enumerate(points):
            spot = f"{where}.points[{p_index}]"
            if not c.block(point, spot, ["text", "hits", "grounded_in", "would_settle"]):
                continue
            c.string(point.get("text"), f"{spot}.text", required=True)
            c.need(is_id(point.get("hits"), by_id), f'{spot}.hits {shown(point.get("hits"))} is not an assumption id.')
            ground = point.get("grounded_in")
            c.need(ground == NO_EVIDENCE or (is_link(ground) and ground in report_links),
                   f'{spot}.grounded_in must be a link that is already on the page (from the web findings) '
                   f'or exactly "{NO_EVIDENCE}".')
            c.string(point.get("would_settle"), f"{spot}.would_settle", required=True)

    forcing = c.items_list(st.get("forcing"), "stress_test.forcing")
    c.need(len(forcing) <= 3, "stress_test.forcing holds at most 3 questions.")
    for index, entry in enumerate(forcing):
        where = f"stress_test.forcing[{index}]"
        if c.block(entry, where, ["question", "answer", "pushed_once"]):
            c.string(entry.get("question"), f"{where}.question", required=True)
            c.string(entry.get("answer"), f"{where}.answer")
            c.flag(entry.get("pushed_once"), f"{where}.pushed_once")

    change_ids = []
    pending = 0
    for index, change in enumerate(c.items_list(st.get("changes"), "stress_test.changes")):
        where = f"stress_test.changes[{index}]"
        if not c.block(change, where, ["id", "assumption", "change", "why", "decision"]):
            continue
        cid = change.get("id")
        if c.need(isinstance(cid, str) and re.fullmatch(r"C[1-9]\d*", cid) is not None,
                  f'{where}.id must look like "C1".'):
            c.need(cid not in change_ids, f'{where}.id "{cid}" is used twice.')
            change_ids.append(cid)
        c.need(change.get("assumption") == "new" or is_id(change.get("assumption"), by_id),
               f'{where}.assumption must be an assumption id or "new" (got {shown(change.get("assumption"))}).')
        c.string(change.get("change"), f"{where}.change", required=True)
        c.string(change.get("why"), f"{where}.why", required=True)
        if c.one_of(change.get("decision"), DECISIONS, f"{where}.decision") and change["decision"] == "pending":
            pending += 1

    status = steps["stress_test"]
    if status in ("not_run", "skipped"):
        c.need(st == STARTING["stress_test"],
               f'stress_test must be empty while steps.stress_test is "{status}": exactly as in the starting file '
               f'in data.md.')
    else:
        c.need(sorted(roles) == sorted(CRITIC_ROLES),
               f"stress_test needs the four critics ({', '.join(CRITIC_ROLES)}); it has {', '.join(roles) or 'none'}.")
    if status == "done":
        c.need(len(forcing) == 3, 'steps.stress_test is "done", so all 3 forcing questions must be recorded.')
        for index, entry in enumerate(forcing):
            if isinstance(entry, dict):
                c.need(text(entry.get("answer")), f"stress_test.forcing[{index}] has no answer from the student.")
        c.need(pending == 0,
               f'steps.stress_test is "done", but {pending} change(s) still wait for the student\'s decision.')


def check_question(c, value, where):
    if not c.string(value, where, required=True):
        return
    reason = future_reason(value)
    c.need(not reason, f'{where} "{value}" {reason}. Ask about what the person did, not what they would do.')
    c.need(sum(visible_text(value).count(mark) for mark in QUESTION_MARKS) <= 1,
           f'{where} "{value}" asks more than one question. Ask one at a time.')


def check_plan(c, data, steps, by_id):
    keys = ["talk_to", "reach", "where", "big_questions", "guide", "money", "commitment_ask",
            "pass_marks", "question_check", "outreach", "notes_fields", "approved_by_student"]
    plan = data.get("interview_plan")
    if not c.block(plan, "interview_plan", keys):
        return []
    for key in ("talk_to", "reach"):
        c.string(plan.get(key), f"interview_plan.{key}")
    where_list = c.items_list(plan.get("where"), "interview_plan.where")
    for index, place in enumerate(where_list):
        where = f"interview_plan.where[{index}]"
        if c.block(place, where, ["place", "why", "link"]):
            c.string(place.get("place"), f"{where}.place", required=True)
            c.string(place.get("why"), f"{where}.why")
            link = place.get("link")
            c.need(link == "" or is_link(link), f'{where}.link must be empty or start with http:// or https://.')

    big = c.items_list(plan.get("big_questions"), "interview_plan.big_questions")
    for index, q in enumerate(big):
        where = f"interview_plan.big_questions[{index}]"
        if c.block(q, where, ["text", "tests"]):
            check_question(c, q.get("text"), f"{where}.text")
            c.need(is_id(q.get("tests"), by_id), f'{where}.tests {shown(q.get("tests"))} is not an assumption id.')

    sections = []
    for index, block in enumerate(c.items_list(plan.get("guide"), "interview_plan.guide")):
        where = f"interview_plan.guide[{index}]"
        if not c.block(block, where, ["section", "questions"]):
            continue
        name = block.get("section")
        if c.one_of(name, GUIDE_SECTIONS, f"{where}.section"):
            c.need(name not in sections, f'{where}: the section "{name}" appears twice.')
            sections.append(name)
        questions = c.items_list(block.get("questions"), f"{where}.questions")
        c.need(len(questions) > 0, f"{where} has no questions.")
        for q_index, q in enumerate(questions):
            spot = f"{where}.questions[{q_index}]"
            if not c.block(q, spot, ["text", "tests", "probes"]):
                continue
            check_question(c, q.get("text"), f"{spot}.text")
            tests = q.get("tests")
            if tests == "":
                c.need(isinstance(name, str) and name in UNTAGGED_SECTIONS,
                       f"{spot} must say which assumption it tests (only warm-up, wrap-up and commitment "
                       f"questions may leave it empty).")
            else:
                c.need(is_id(tests, by_id), f'{spot}.tests {shown(tests)} is not an assumption id.')
            probes = c.items_list(q.get("probes"), f"{spot}.probes")
            c.need(1 <= len(probes) <= 3, f"{spot} needs 1 to 3 probes (it has {len(probes)}).")
            for p_index, probe in enumerate(probes):
                check_question(c, probe, f"{spot}.probes[{p_index}]")

    money = c.items_list(plan.get("money"), "interview_plan.money")
    for index, q in enumerate(money):
        where = f"interview_plan.money[{index}]"
        if c.block(q, where, ["text", "tests"]):
            check_question(c, q.get("text"), f"{where}.text")
            c.need(is_id(q.get("tests"), by_id), f'{where}.tests {shown(q.get("tests"))} is not an assumption id.')

    ask = plan.get("commitment_ask")
    if c.string(ask, "interview_plan.commitment_ask") and ask.strip():
        check_question(c, ask, "interview_plan.commitment_ask")

    marks = c.items_list(plan.get("pass_marks"), "interview_plan.pass_marks")
    marked = []
    unset = 0
    for index, pm in enumerate(marks):
        where = f"interview_plan.pass_marks[{index}]"
        if not c.block(pm, where, ["assumption", "measure", "out_of", "mark"], optional=["stands_in_for"]):
            continue
        if c.need(is_id(pm.get("assumption"), by_id),
                  f'{where}.assumption {shown(pm.get("assumption"))} is not an assumption id.'):
            c.need(pm["assumption"] not in marked, f'{where}: "{pm["assumption"]}" has two pass marks.')
            marked.append(pm["assumption"])
            c.need(by_id[pm["assumption"]].get("kind") != "future",
                   f'{where} sits on "{pm["assumption"]}", which is about what people would do. A pass mark '
                   f"counts past actions, so put it on a past-behaviour assumption (its nearest searchable "
                   f"one) and list the would-claim in stands_in_for.")
        if "stands_in_for" in pm:
            stands = c.items_list(pm.get("stands_in_for"), f"{where}.stands_in_for")
            c.need(len(stands) > 0, f"{where}.stands_in_for is empty. Leave it out, or list the would-claims.")
            for s_index, sid in enumerate(stands):
                spot = f"{where}.stands_in_for[{s_index}]"
                if c.need(is_id(sid, by_id), f"{spot} {shown(sid)} is not an assumption id."):
                    c.need(by_id[sid].get("kind") == "future",
                           f'{spot} "{sid}" is not about what people would do. stands_in_for lists only '
                           f"future (would) assumptions.")
            c.need(len([x for x in stands if isinstance(x, str)]) == len({x for x in stands if isinstance(x, str)}),
                   f"{where}.stands_in_for repeats an assumption.")
        c.string(pm.get("measure"), f"{where}.measure", required=True)
        out_of = pm.get("out_of")
        c.need(is_int(out_of) and out_of >= 1, f"{where}.out_of must be a whole number, 1 or more.")
        mark = pm.get("mark")
        if mark is None:
            unset += 1
        else:
            c.need(is_int(mark) and mark >= 1 and (not is_int(out_of) or mark <= out_of),
                   f"{where}.mark must be null (not set yet) or a whole number from 1 to out_of.")

    for index, entry in enumerate(c.items_list(plan.get("question_check"), "interview_plan.question_check")):
        where = f"interview_plan.question_check[{index}]"
        if c.block(entry, where, ["original", "problem", "rewrite"]):
            c.string(entry.get("original"), f"{where}.original", required=True)
            if entry.get("rewrite") == DROPPED_MAIN_CHANGED and entry.get("problem") == "":
                pass  # a probe dropped because its main question changed may have had no flag of its own
            else:
                c.one_of(entry.get("problem"), QUESTION_PROBLEMS, f"{where}.problem")
            check_question(c, entry.get("rewrite"), f"{where}.rewrite")

    channels = []
    outreach = c.items_list(plan.get("outreach"), "interview_plan.outreach")
    for index, entry in enumerate(outreach):
        where = f"interview_plan.outreach[{index}]"
        if c.block(entry, where, ["channel", "text"]):
            if c.string(entry.get("channel"), f"{where}.channel", required=True):
                channels.append(entry["channel"].strip().lower())
            if c.string(entry.get("text"), f"{where}.text", required=True):
                # Contract section 7 and v1.6 point 1: every message asks for advice in so many words.
                c.need(re.search(r"\badvice\b", plain_text(entry["text"]), re.I) is not None,
                       f"{where}.text doesn't use the word \"advice\". Every message asks for the person's "
                       f"advice in so many words (\"I'd value your advice\"; \"and experience\" may be added).")
    fields = c.strings(plan.get("notes_fields"), "interview_plan.notes_fields", required=True)
    c.flag(plan.get("approved_by_student"), "interview_plan.approved_by_student")

    status = steps["interview_plan"]
    if status in ("not_run", "skipped"):
        c.need(plan == STARTING["interview_plan"],
               f'interview_plan must be empty while steps.interview_plan is "{status}": exactly as in the '
               f'starting file in data.md.')
    else:
        for key in ("talk_to", "reach", "commitment_ask"):
            c.need(text(plan.get(key)), f"interview_plan.{key} is empty.")
        c.need(len(where_list) >= 1, "interview_plan.where needs at least one place.")
        c.need(len(big) == 3, f"interview_plan.big_questions needs exactly 3 questions (it has {len(big)}).")
        c.need(len(sections) >= 1, "interview_plan.guide is empty.")
        c.need(len(money) >= 1, "interview_plan.money needs at least one question.")
        c.need(len(marks) >= 1, "interview_plan.pass_marks needs at least one measure.")
        c.need(len(set(channels)) >= 2, "interview_plan.outreach needs messages for two different channels.")
        c.need(len(fields) >= 1, "interview_plan.notes_fields is empty.")
    if status == "done":
        c.need(plan.get("approved_by_student") is True,
               'steps.interview_plan is "done", but the student has not approved the script.')
        c.need(unset == 0,
               f'steps.interview_plan is "done", but {unset} pass mark(s) have no number from the student.')
    return marks


def check_interviews(c, data, steps, by_id, marks):
    marked = {pm.get("assumption") for pm in marks
              if isinstance(pm, dict) and isinstance(pm.get("assumption"), str)}
    seen = []
    groups = {}
    interviews = c.items_list(data.get("interviews"), "interviews")
    for index, interview in enumerate(interviews):
        where = f"interviews[{index}]"
        if not c.block(interview, where, ["id", "date", "who", "facts"], optional=["question_flags", "new_findings"]):
            continue
        flagged = set()
        if "question_flags" in interview:
            for q_index, flag in enumerate(c.items_list(interview.get("question_flags"), f"{where}.question_flags")):
                spot = f"{where}.question_flags[{q_index}]"
                if c.block(flag, spot, ["question", "problem"]):
                    c.string(flag.get("question"), f"{spot}.question", required=True)
                    if c.one_of(flag.get("problem"), QUESTION_PROBLEMS, f"{spot}.problem"):
                        flagged.add(flag["problem"])
        iid = interview.get("id")
        if c.need(isinstance(iid, str) and re.fullmatch(r"I[1-9]\d*", iid) is not None,
                  f'{where}.id must look like "I1".'):
            c.need(iid not in seen, f'{where}.id "{iid}" is used twice.')
            seen.append(iid)
        c.string(interview.get("date"), f"{where}.date")
        c.string(interview.get("who"), f"{where}.who", required=True)
        for spot, value in contact_fields(interview, where):
            c.need(not has_contact(value),
                   f"{spot} holds an email address or phone number. Remove it (use a role, never contact details).")
        for f_index, fact in enumerate(c.items_list(interview.get("facts"), f"{where}.facts")):
            spot = f"{where}.facts[{f_index}]"
            if not c.block(fact, spot, ["assumption", "side", "kind", "quote", "tag"],
                           optional=["meets_measure", "reply_to_flag"]):
                continue
            aid = fact.get("assumption")
            c.need(is_id(aid, by_id), f'{spot}.assumption {shown(aid)} is not an assumption id.')
            c.one_of(fact.get("side"), FACT_SIDES, f"{spot}.side")
            c.one_of(fact.get("kind"), FACT_KINDS, f"{spot}.kind")
            c.one_of(fact.get("tag"), FACT_TAGS, f"{spot}.tag")
            c.string(fact.get("quote"), f"{spot}.quote", required=True)
            if "reply_to_flag" in fact:
                # Contract v1.6 point 10: a reply to a flagged question is never counted. It is
                # background, with the flag, the same way for every flag type.
                flag = fact.get("reply_to_flag")
                if c.one_of(flag, QUESTION_PROBLEMS, f"{spot}.reply_to_flag"):
                    c.need(fact.get("side") == "context",
                           f'{spot} replies to a flagged question, so it is never counted: its side must be '
                           f'"context" (background), not {shown(fact.get("side"))}.')
                    c.need(flag in flagged,
                           f'{spot} replies to a question flagged "{flag}", but {where}.question_flags has no '
                           f'question with that flag. Record the question there.')
            if fact.get("side") == "for" and fact.get("kind") == "did" and is_id(aid, by_id):
                c.need(by_id[aid].get("kind") != "future",
                       f'{spot} is something the person did, marked as backing "{aid}", which is about what '
                       f"people would do. A past action can't back a would-claim: put it on the past-behaviour "
                       f"assumption, or make it context.")
                if aid in marked:
                    c.need(isinstance(fact.get("meets_measure"), bool),
                           f'{spot} backs "{aid}", which has a pass mark, so it needs meets_measure: true or '
                           f"false (true only when the notes show every condition the measure names).")
        flag_list = interview.get("question_flags") if isinstance(interview.get("question_flags"), list) else []
        fact_list = interview.get("facts") if isinstance(interview.get("facts"), list) else []
        questions = {norm(q.get("question")) for q in flag_list
                     if isinstance(q, dict) and isinstance(q.get("question"), str)}
        fact_quotes = {norm(f.get("quote")) for f in fact_list
                       if isinstance(f, dict) and isinstance(f.get("quote"), str)}
        for f_index, fact in enumerate(fact_list):
            if isinstance(fact, dict) and isinstance(fact.get("quote"), str) and norm(fact["quote"]) in questions:
                c.problems.append(f"{where}.facts[{f_index}].quote is a question the student asked (it is in "
                                  f"question_flags). The interviewer's words are never what a person said.")
        if "new_findings" in interview:
            for n_index, finding in enumerate(c.items_list(interview.get("new_findings"), f"{where}.new_findings")):
                spot = f"{where}.new_findings[{n_index}]"
                if not c.block(finding, spot, ["kind", "about", "group", "quote"]):
                    continue
                c.one_of(finding.get("kind"), FINDING_KINDS, f"{spot}.kind")
                if c.string(finding.get("about"), f"{spot}.about", required=True):
                    c.need(word_count(finding["about"]) <= FINDING_ABOUT_WORDS,
                           f"{spot}.about is {word_count(finding['about'])} words. Name it in "
                           f"{FINDING_ABOUT_WORDS} words or fewer.")
                if c.string(finding.get("quote"), f"{spot}.quote", required=True):
                    c.need(norm(finding["quote"]) not in questions,
                           f"{spot}.quote is a question the student asked (it is in question_flags). The "
                           f"interviewer's words are never what a person raised.")
                    c.need(norm(finding["quote"]) not in fact_quotes,
                           f"{spot}.quote is also a fact of this interview. Something an assumption covers is a "
                           f"fact, not a new finding.")
                group = finding.get("group")
                if c.need(isinstance(group, str) and re.fullmatch(r"N[1-9]\d*", group) is not None,
                          f'{spot}.group must look like "N1".'):
                    groups.setdefault(group, []).append((spot, finding))
    # Contract v2.2 point 2: findings in one group are the same thing raised in different interviews.
    named = {}
    for group, members in groups.items():
        for _, f in members:
            if isinstance(f.get("about"), str) and isinstance(f.get("kind"), str):
                named.setdefault((f["kind"], norm(f["about"]).rstrip(".")), set()).add(group)
    for (kind, about), same in named.items():
        c.need(len(same) == 1, f'New findings in groups {", ".join(sorted(same))} are the same {kind}, named the same. '
                               f"The same thing raised in different interviews shares one group.")
    for group, members in groups.items():
        kinds = {f.get("kind") for _, f in members}
        abouts = {norm(f.get("about")).rstrip(".") for _, f in members if isinstance(f.get("about"), str)}
        c.need(len(kinds) == 1, f'New findings in group "{group}" have different kinds ({", ".join(sorted(map(str, kinds)))}). '
                                f"One group is one thing: give each kind its own group.")
        c.need(len(abouts) <= 1, f'New findings in group "{group}" are named differently. Give every finding in a '
                                 f"group the same about, word for word.")
    status = steps["interview_sort"]
    if status == "not_run":
        c.need(not interviews, 'interviews must be empty while steps.interview_sort is "not_run".')
    elif status == "done":
        c.need(len(interviews) >= 1, 'steps.interview_sort is "done", but no interviews are recorded.')
    # "running": the privacy question is asked. Interviews from an earlier batch may already be there.


def new_findings(data):
    """Contract v2.2 points 2 and 3: per group, the interviews that raised it on their own, most first.
    A new problem raised in 2 or more interviews is flagged for the page's pivot line."""
    groups = {}
    for interview in data.get("interviews") if isinstance(data.get("interviews"), list) else []:
        if not isinstance(interview, dict):
            continue
        listed = interview.get("new_findings") if isinstance(interview.get("new_findings"), list) else []
        for finding in listed:
            if not isinstance(finding, dict):
                continue
            entry = groups.setdefault(finding.get("group"), {"group": finding.get("group"), "kind": finding.get("kind"),
                                                             "about": finding.get("about"), "interviews": [],
                                                             "quotes": []})
            if interview.get("id") not in entry["interviews"]:
                entry["interviews"].append(interview.get("id"))
            entry["quotes"].append({"interview": interview.get("id"), "quote": finding.get("quote")})
    out = list(groups.values())
    for entry in out:
        entry["count"] = len(entry["interviews"])
        entry["pivot"] = entry["kind"] == "new problem" and entry["count"] >= 2
    out.sort(key=lambda e: (-e["count"], int(re.sub(r"\D", "", str(e["group"])) or 0)))
    return out


def check_log(c, data):
    for index, entry in enumerate(c.items_list(data.get("log"), "log")):
        where = f"log[{index}]"
        if c.block(entry, where, ["date", "step", "student_decision"]):
            c.need(is_date(entry.get("date")), f"{where}.date must be a date written YYYY-MM-DD.")
            c.one_of(entry.get("step"), LOG_STEPS, f"{where}.step")
            c.string(entry.get("student_decision"), f"{where}.student_decision")


def tallies(data, marks):
    """For each pass mark: how many interviews hold a "did" fact on the "for" side that meets the measure."""
    interviews = [i for i in data.get("interviews") or [] if isinstance(i, dict)]
    out = []
    for pm in marks:
        if not isinstance(pm, dict):
            continue
        aid = pm.get("assumption")
        count = 0
        for interview in interviews:
            facts = interview.get("facts") or []
            if any(isinstance(f, dict) and f.get("assumption") == aid and f.get("side") == "for"
                   and f.get("kind") == "did" and f.get("meets_measure") is True for f in facts):
                count += 1
        mark = pm.get("mark")
        if not is_int(mark):  # null, or a wrong type the checks have already listed
            state = "no mark set"
        elif count >= mark:
            state = "met"
        else:
            state = "not met yet"
        out.append({"assumption": aid, "measure": pm.get("measure"), "stands_in_for": pm.get("stands_in_for") or [],
                    "count": count, "mark": mark, "out_of": pm.get("out_of"),
                    "interviews": len(interviews), "state": state})
    return out


def validate(data):
    """Return (problems, computed). computed is only meaningful when problems is empty."""
    c = Check()
    for where in broken_text(data, ""):
        c.problems.append(f"{where or 'The file'} holds a broken character that can't be saved (often from "
                          f"copying a web page). Retype or remove it.")
    if not check_top(c, data):
        return c.problems, {}
    steps = check_steps(c, data)
    problem_ids = check_area_and_problems(c, data, steps)
    by_id = check_frame(c, data, steps, problem_ids)
    graded, report_links = check_evidence(c, data, steps, by_id)
    # Contract v2.1 point 5: the picked problem's counted items are web findings on the page too,
    # so a critic may ground a point in one of them.
    listed = data.get("problems") if isinstance(data.get("problems"), list) else []
    for problem in listed:
        if isinstance(problem, dict) and problem.get("picked") is True and isinstance(problem.get("items"), list):
            report_links |= {i["link"] for i in problem["items"] if isinstance(i, dict)
                             and i.get("result") == "counts" and is_link(i.get("link"))}
    check_stress(c, data, steps, by_id, report_links)
    marks = check_plan(c, data, steps, by_id)
    check_interviews(c, data, steps, by_id, marks or [])
    check_log(c, data)
    check_lengths(c, data)
    if c.problems:
        # Nothing is built from data that failed a check, so nothing below can trip on it.
        return c.problems, {}
    computed = {
        "kit_version": KIT_VERSION,
        "grades": {aid: dict(g, label=LABELS[g["status"]]) for aid, g in graded.items()},
        "problem_counts": {p["id"]: problem_counts(p) for p in data.get("problems") or []
                           if isinstance(p, dict) and isinstance(p.get("id"), str)},
        "problem_one_page": {p["id"]: most_on_one_page(p) for p in data.get("problems") or []
                             if isinstance(p, dict) and isinstance(p.get("id"), str)},
        "tallies": tallies(data, marks or []),
        "covered": covered_by_problem(data),
        "new_findings": new_findings(data),
    }
    return c.problems, computed


def one_line(message):
    """A problem message on one line: line breaks inside a quoted value are shown as \\n."""
    for raw, shown_as in (("\r", "\\r"), ("\n", "\\n"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        message = message.replace(raw, shown_as)
    return message


def plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def sources_on_pages(voices, pages):
    """ "1 person or source on 1 page", "5 people or sources on 3 pages" (contract v2.1 point 6)."""
    return f'{plural(voices, "person or source", "people or sources")} on {plural(pages, "page", "pages")}'



def full_stop(sentence):
    """The sentence with a full stop at the end, if it has none."""
    sentence = sentence.rstrip()
    return sentence if sentence.endswith((".", "!", "?")) else sentence + "."


def build_page(data, computed, template_text):
    payload = json.dumps({"data": data, "computed": computed}, ensure_ascii=False, sort_keys=False)
    # Nothing in the data can close the script tag or open a comment: every "<",
    # ">" and "&" becomes a JSON escape, which JSON.parse turns back into the character.
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return template_text.replace(MARKER, payload, 1)


def main(argv):
    # Never crash while reporting: a broken character or a non-UTF-8 console prints as an escape.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):
            pass
    if len(argv) != 3:
        print(__doc__)
        return 2
    source = pathlib.Path(argv[1])
    target = pathlib.Path(argv[2])
    if target.suffix.lower() != ".html":
        print(f"The page must be written to an .html file, not {target}. Nothing was written.")
        return 2
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"Could not read {source}: {error}")
        print("The page was NOT built. Nothing was written.")
        return 1
    except RecursionError:
        print(f"Could not read {source}: it is nested too deeply to be discovery data.")
        print("The page was NOT built. Nothing was written.")
        return 1

    try:
        problems, computed = validate(data)
    except RecursionError:
        print(f"The page was NOT built. Nothing was written. {source.name} is nested too deeply to be discovery data.")
        return 1
    if problems:
        print(f"The page was NOT built. Nothing was written. Fix these {len(problems)} problem(s) "
              f"in {source.name} and run again:")
        for problem in problems:
            print(" -", one_line(problem))
        return 1

    template_path = pathlib.Path(__file__).resolve().parent / "page-template.html"
    try:
        template = template_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"Could not read the page template {template_path}: {error}. Nothing was written.")
        return 1
    if template.count(MARKER) != 1:
        print(f"The page template must hold the marker {MARKER} exactly once. Nothing was written.")
        return 1
    page = build_page(data, computed, template)

    # Write to a temporary file first, so a half-written page never replaces a good one.
    try:
        encoded = page.encode("utf-8")
    except UnicodeError as error:
        print(f"The page was NOT built. Nothing was written. The data holds a character that can't be saved: {error}")
        return 1
    folder = target.resolve().parent
    temp_name = None
    try:
        handle, temp_name = tempfile.mkstemp(prefix=".discovery-", suffix=".html", dir=folder)
        with os.fdopen(handle, "wb") as out:
            out.write(encoded)
        os.chmod(temp_name, 0o644)  # mkstemp makes the file owner-only; the page is for sharing
        os.replace(temp_name, target)
        temp_name = None
    except (OSError, UnicodeError) as error:
        print(f"Could not write {target}: {error}. Nothing was written.")
        return 1
    finally:
        if temp_name and os.path.exists(temp_name):
            os.remove(temp_name)

    print(f"Built {target}")
    problems = [p for p in data.get("problems") or [] if isinstance(p, dict)]
    if problems:
        print("Problems (repeat these counts, nothing stronger):")
        for p in problems:
            n = computed["problem_counts"][p["id"]]
            line = f'  {p["id"]} "{p["statement"]}": {sources_on_pages(n["voices"], n["pages"])}.'
            same = computed["problem_one_page"][p["id"]]
            if same >= 2:
                line += f" {same} of these are on one page."
            if isinstance(p.get("about_one"), dict):
                line += f' {len(p["about_one"]["voices"])} of these are about one {full_stop(p["about_one"]["what"])}'
            print(line)
    grades = computed["grades"]
    if grades:
        print("Evidence labels (repeat these words, nothing stronger):")
        statements = {a["id"]: a["statement"] for a in data["assumptions"]}
        for aid, g in grades.items():
            print(f'  {aid} "{statements.get(aid, "")}": {g["label"]} '
                  f'({g["for"]} for, {g["against"]} against, on {plural(g["pages"], "page", "pages")})')
    ran_on = (data.get("evidence") or {}).get("run_on") or []
    covered = {aid: pid for aid, pid in computed["covered"].items() if aid not in ran_on}
    if covered:
        print("Checked in Find problems, not searched again (repeat these counts, nothing stronger):")
        statements = {a["id"]: a["statement"] for a in data["assumptions"]}
        for aid, pid in covered.items():
            n = computed["problem_counts"].get(pid, {"voices": 0, "pages": 0})
            print(f'  {aid} "{statements.get(aid, "")}": {sources_on_pages(n["voices"], n["pages"])}, '
                  f'under the problem you picked ({pid}).')
    if computed["tallies"]:
        print("Pass marks (interviews where the person did something that meets the measure; repeat these words):")
        statements = {a["id"]: a["statement"] for a in data["assumptions"]}
        for t in computed["tallies"]:
            mark = ("No mark set." if t["mark"] is None else
                    f'Your mark: {t["mark"]} of {plural(t["out_of"], "person", "people")}. {t["state"].capitalize()}.')
            so_far = (f'So far: {t["count"]} of {plural(t["interviews"], "interview", "interviews")}.'
                      if t["interviews"] else "So far: no interviews sorted yet.")
            print(f'  {t["assumption"]} {t["measure"]}: {so_far} {mark}')
            for sid in t["stands_in_for"]:
                print(f'      Stands in for: {full_stop(statements.get(sid, sid))} '
                      f'This counts past actions like it, not promises.')
    if computed["new_findings"]:
        print("What people raised without being asked (repeat these counts, nothing stronger):")
        for g in computed["new_findings"]:
            print(f'  {g["group"]} {g["kind"]} "{g["about"]}": raised in {plural(g["count"], "interview", "interviews")} '
                  f'({", ".join(map(str, g["interviews"]))}).')
        for g in computed["new_findings"]:
            if g["pivot"]:
                print(f'  Line on the page: "{g["about"]}" came up in {g["count"]} interviews without being asked.')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
