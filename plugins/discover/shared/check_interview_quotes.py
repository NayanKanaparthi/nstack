#!/usr/bin/env python3
"""Check that every interview quote in discovery.json is the interviewee's words in the notes.

Run it only as a command, never import it:

    python3 check_interview_quotes.py <student folder>/discovery.json
    python3 check_interview_quotes.py --text <a note>      (prints a note's text as this check reads it)

What it reads (contract v2.2 point 8, sorting-rules.md sections 1, 3, 4 and 6):

- discover-work/interviews-clean/<id>.md, one cleaned copy per interview, named after its id
  ("I3.md"). It is the original, line for line, after the listed changes, with who speaks put in
  front of every line: "Interviewer: " for the student's own words (questions, comments, ideas,
  notes to self, headings) or "Person: " / "Person 2: " for the interviewee's. A line may keep the
  original's own label, bullet and timestamp ("Person: Dana Reyes (00:00:06): Slow.") or leave
  them out ("Person: Slow."). Nothing else may be in the folder apart from replacements.json
  (hidden files such as .DS_Store are ignored).
- discover-work/interviews-clean/replacements.json: for each id, the original note it was made
  from (a file in the student's interviews/ folder: text, Markdown or Word .docx), optionally the
  lines of it that hold this interview, and every change made while cleaning:
  {"I3": {"original": "interviews/2026-11-14-interview-1.md", "lines": [1, 40],
          "replaced": {"Dana Reyes": "Person", "Nayan Kanaparthi": "Interviewer", "dana@example.org": ""}}}

A change may only be one of these kinds (anything else is refused):
- a name turned into a role: one to four capitalised words (particles such as de, van or da
  allowed; never a single common word such as No, Never or Rarely), turned into "Person",
  "Person N", "Interviewer" or a role naming a relation on RELATIONS after their, the, a, an, his,
  her, my, our or your, with at most one word between ("their landlord", "a close friend");
- a contact detail removed (an email, an @handle, a link, a phone number, a street address with a
  street word, an apartment number or a ZIP code), or a street address turned into its
  neighbourhood (one to three capitalised words);
- a speaker label ("Sam:") turned into "Person:", "Person N:" or "Interviewer:" (the student's own
  marks such as "Me:" or "Q:" only into "Interviewer:");
- a line break put before a label where a sentence ends, to split one line into two turns
  ("A:": "\nA:"); at a name, only before a label that starts another line of the note.

What it checks:

1. Each cleaned copy has the original's lines, in order, after the listed changes, each with who
   speaks in front and nothing else changed (spacing, invisible characters and the style of
   apostrophes and quotation marks aside). Blank lines, and lines holding only a timestamp, a cue
   number or "WEBVTT", may be kept or left out.
2. Who speaks: a line the original starts with one of the student's marks ("Me:", "Q:", "Idea:",
   "Note:", after a bullet or not) is the interviewer's. A label changed into a role keeps that
   role. Every line with the same speaker label has the same speaker. In a transcript (a speaker's
   label with a time, or two or more speakers' labels on at least four lines in five), a line with
   no speaker label continues the turn above it, so it keeps that speaker (or is the interviewer's),
   and both an interviewer and a person speak.
3. Each quote of an interview (its facts and its new findings) is inside the person's words in that
   interview's own copy, word for word, and is whole sentences by the rules sorting-rules section 3
   publishes. A new finding is one to three sentences.
4. Each original is a file in interviews/; no two interviews share one, unless each names its own
   lines and together they cover the file; and no two interviews hold the same person's words.
5. A cleaned copy holds no email address or phone number.
6. The batch holds at least one quote, so a run can't pass by checking nothing.

It writes the result to discover-work/interview-quote-check.json and prints it. It exits 1,
starting with "Not done:", when anything fails, so the sort is never saved as done with it.

Standard library only.
"""

import datetime as dt
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ElementTree
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True

# The same closed list of apostrophes and the same invisible characters as render_page.py (data.md).
APOSTROPHE_CHARS = ("\u0060\u00b4\u02b9\u02bb\u02bc\u055a\u05f3\u2018\u2019\u201b\u2032\u2035"
                    "\ua78b\ua78c\uff07\uff40")
APOSTROPHES = str.maketrans({ch: "'" for ch in APOSTROPHE_CHARS})
DOUBLE = str.maketrans({ch: '"' for ch in "\u201c\u201d\u201e\u201f\u00ab\u00bb\uff02\u2033"})

# Who speaks, in front of every line of a cleaned copy.
ROLE = re.compile(r"^\s*(?:[\[(]?\d{1,2}(?::\d{2}){1,2}[\])]?\s*)?(?P<b>\*\*|__)?(?P<role>Person(?: (?P<n>\d+))?|Interviewer)"
                  r"(?:(?P=b))?\s*(?:[\[(]\d{1,2}(?::\d{2}){1,2}[\])])?\s*(?:(?P<colon>:)(?:(?P=b))?(?:\s+|$)|"
                  r"(?P<alone>\s+\d{1,2}(?::\d{2}){1,2})?\s*$)")
# What an original line may hold before its words (sorting-rules section 1, "Labels the check reads").
BULLET = re.compile(r"^\s*(?:[-*+>\u2022\u25e6\u25aa\u25cf\u2023\u2043\u2192\u00b7\u2013\u2014]|->|\d{1,2}[.)]|[a-z][.)])\s+")
STAMP = r"[\[(]?\d{1,2}(?::\d{2}){1,2}(?:[.,]\d{1,3})?[\])]?"
LEAD_STAMP = re.compile(r"^\s*" + STAMP + r"(?:\s*[-\u2013]\s*|\s+)")
VOICE = re.compile(r"^\s*<v(?:\.[\w.-]+)?\s+([^>]{1,60})>\s*")
BRACKET_NAME = re.compile(r"^\s*\[([^\]\d:]{1,40})\]\s*:?\s*")
NAME_LABEL = re.compile(r"^\s*(?P<b>\*\*|__|\*|_)?(?P<name>[^\s\d:\[(*_<][^:\n\[(*_]{0,39}?)\s*(?:(?P=b))?\s*"
                        r"(?P<paren>[\[(][^\])\n]{0,30}[\])])?\s*(?:(?P=b))?\s*:\s*(?:(?P=b)\s*)?")
HEADER = re.compile(r"^\s*(?P<b>\*\*|__)?(?P<name>[^\s\d:\[(*_<][^:\n\[(*_]{0,39}?)\s*(?:(?P=b))?\s*"
                    r"(?:[-\u2013]\s*)?(?P<stamp>" + STAMP + r")?\s*$")
SKIP_LINE = re.compile(r"^\s*(?:WEBVTT.*|\d{1,4}|" + STAMP + r"(?:\s*-->\s*" + STAMP + r".*)?)\s*$")
INDENT = re.compile(r"^\s{2,}\S")

# The sentence rules for quotes (sorting-rules section 3): data.md's length rules, except that a
# capitalised word ends a sentence ("Yes. It took weeks." and "No. They kept it." are two) unless
# it is a title or an abbreviation on TITLES, a single initial or a run of single letters.
SHORT_FORMS = {"approx.", "e.g.", "i.e.", "etc.", "vs.", "incl.", "esp.", "min.", "mins.", "hr.", "hrs.",
               "no.", "nos.", "est.", "ca.", "cf.", "fig.", "p.", "pp.", "vol.", "dept.", "wk.", "wks.",
               "mo.", "mos.", "yr.", "yrs.", "a.m.", "p.m.", "avg.", "sec.", "secs.", "ft.", "sq.", "lb.",
               "lbs.", "oz.", "misc.", "govt.", "al."}
LETTER_RUN = re.compile(r"(?:[^\W\d_]\.){2,}")
TITLES = set("""mr mrs ms mx dr st mt jr sr prof gen sen rep gov lt col capt sgt fr rev hon pres supt
    jan feb mar apr jun jul aug sep sept oct nov dec mon tue tues wed thu thur thurs fri sat sun ave blvd rd
    ln hwy inc ltd co corp bros vol fig dept est approx calif mass penn wash ariz colo conn fla ga ill ind
    kan ky la md mich minn miss mont neb nev okla ore pa tenn tex va vt wis wyo""".split())
OPENERS = "\"'([*_"
CLOSERS = "\"')]*_"

# Replacement kinds and speaker labels (sorting-rules section 1).
LABEL_VALUE = re.compile(r"(?:Person(?: \d+)?|Interviewer):")
PRONOUNS = {"i", "me", "you", "we", "us", "they", "them", "he", "him", "she", "her", "it", "my", "your", "our"}
# A role names a relation, from this list, after their, the, a, an, his, her, my, our or your, with at
# most one word before it ("their landlord", "a close friend", "the management company").
RELATIONS = set("""person interviewer landlord landlady roommate housemate flatmate friend broker agent agency manager
    partner neighbour neighbor boss colleague coworker co-worker sister brother mother father mom dad parent
    parents cousin aunt uncle son daughter kid child children wife husband boyfriend girlfriend fiance fiancee
    tenant owner super superintendent company firm employer client customer teacher professor doctor lawyer
    accountant contractor plumber sitter nanny relative family team office building school university
    college bank insurer platform app store shop restaurant business startup organisation organization
    group member members student classmate coach mentor advisor investor""".split())
ROLE_VALUE = re.compile(r"Person(?: \d+)?|Interviewer|(?:their|the|a|an|his|her|my|our|your)(?: [^\W\d_][\w'-]*)?"
                        r" (?P<relation>[^\W\d_][\w'-]*)", re.I)
PLACE_VALUE = re.compile(r"(?:(?:the|The) )?[^\W\d_][\w.'-]*(?: [^\W\d_][\w.'-]*){0,2}")
STREET = r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Place|Pl|Way|Court|Ct|Terrace|Parkway|Pkwy|Square|Sq|Highway|Hwy)\.?"
PARTICLES = {"de", "da", "do", "dos", "das", "di", "du", "del", "della", "van", "von", "der", "den", "ter", "ten",
             "la", "le", "bin", "binti", "al", "el", "y"}
COMMON = {w.lower() for w in """I I'm I've I'd I'll A An The No Not Never Yes Yeah Nope Always Sometimes Maybe
    Probably Definitely Really Actually It It's We They He She You My Our Their His Her Your This That These
    Those So But And Or If When Then Honestly Well Okay OK Oh Um Uh Just Only Every Each Some Any None
    Nothing Everything Nobody Everyone Someone Don't Didn't Can't Won't Wasn't Isn't Do Did Does Was Is
    Are Were Have Had What Who Why How Where There Here Me Us Them Still Also Even Very Too Once Twice
    Rarely Often Usually Seldom Hardly Barely Almost Mostly Totally Completely Absolutely Literally Basically
    Exactly Occasionally Constantly Frequently Generally Typically Normally Regularly Mainly Nearly Partly
    Sure Right Fine Good Great Bad Worse Worst Better Best Lots Many Much More Most Less Least Few Several
    All Both Either Neither Other Another Same First Last Next Now Today Yesterday Tomorrow Again Already
    Yet Soon Later Before After Because Since Although Though While Thanks Thank Please Like Kind Pretty
    Quite Super Plus Free Cheap Expensive Easy Hard Fast Slow Late Early Weekly Monthly Daily Yearly Quick
    Question Answer Biggest Main Key Overall Also""".split()}
# Labels that mark the student's own words: never the person's.
STUDENT_MARKS = {"me", "i", "q", "question", "questions", "idea", "ideas", "note", "notes", "note to self",
                 "thought", "thoughts", "todo", "to do", "my take", "my notes", "us", "we", "follow-up question",
                 "interviewer", "the interviewer", "hypothesis", "hypotheses", "assumption", "assumptions",
                 "observation", "observations", "guess", "reminder", "to ask", "ask"}
# Field names on a notes sheet ("Pain: waited 7 weeks"): not speakers.
FIELDS = {"pain", "pains", "workaround", "workarounds", "money", "goal", "goals", "obstacle", "obstacles",
          "people mentioned", "follow-up", "follow up", "quote", "quotes", "context", "background", "date",
          "time", "when", "where", "who", "role", "summary", "takeaway", "takeaways", "insight", "insights",
          "action", "actions", "next steps", "price", "cost", "costs", "tools", "budget", "problem", "problems",
          "current solution", "solution", "location", "setting", "rent", "fee", "transcript", "attendees",
          "participants", "agenda", "recording", "meeting notes", "interview", "call", "notes",
          "fees", "deposit", "landlord", "issue", "issues", "story", "result", "outcome", "age", "job"}
SPEAKER = re.compile(r"(?:unknown\s+|other\s+)?(?:speaker|person|participant|interviewee|respondent|guest|host|customer|"
                     r"user|caller)(?:\s*[\da-z])?|[prs]\d{1,2}|a|r|answer|response|her|she|he|him|them|they|you", re.I)
SPLIT_WORDS = {"a", "q", "r", "answer", "question", "response", "reply", "me", "i", "interviewer", "person",
               "interviewee", "respondent"}
ROLE_WORDS = re.compile(r"(?:the\s+)?(?:interviewer|person(?:\s+\d+)?)")
EMAIL = re.compile(r"[^\s@<>()\[\],;:\"']+@[^\s@<>()\[\],;:\"']+\.[^\W\d_]{2,}")
PHONE = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
ONE_DATE = r"(?:\d{4}[-.]\d{1,2}[-.]\d{1,2}|\d{1,2}[-.]\d{1,2}[-.](?:\d{4}|\d{2}))"
DATE_RUN = re.compile(ONE_DATE + r"(?:\s*[-\u2013]?\s*" + ONE_DATE + r")*")
THOUSANDS = re.compile(r"\d{1,3}(?:([ .])\d{3})(?:\1\d{3})*")
LINK_KEY = re.compile(r"(?:https?://|www\.)\S+|@[\w.]{2,}|[\w.-]+\.[a-z]{2,}(?:/\S*)?", re.I)
APARTMENT = r"(?:Apt|Apartment|Unit|Suite|Ste|Flat|#)\.?\s*\d+[A-Za-z]?"
ADDRESS_KEY = re.compile(r"\d{1,6}\s+(?:[NSEW]\.?\s+)?(?:\w+\s+){0,3}" + STREET + r"(?:,?\s+" + APARTMENT + r")?"
                         r"(?:,\s*[A-Z][\w.'-]*(?:\s+[A-Z][\w.'-]*)*)*(?:\s+\d{5})?|" + APARTMENT + r"|\d{5}(?:-\d{4})?")
NOTE_SUFFIX = ".md"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def is_invisible(ch):
    code = ord(ch)
    return (unicodedata.category(ch) == "Cf" or code == 0x034F or 0xFE00 <= code <= 0xFE0F
            or 0xE0100 <= code <= 0xE01EF)


def norm(text):
    """NFC, no invisible characters, one apostrophe and one double quote style, single spaces."""
    text = unicodedata.normalize("NFC", text)
    text = "".join(ch for ch in text if not is_invisible(ch))
    return re.sub(r"\s+", " ", text.translate(APOSTROPHES).translate(DOUBLE)).strip()


def read_note(path):
    """A note's text as this check reads it: a Word .docx one paragraph per line, anything else as
    UTF-8 text (a byte order mark at the start is dropped)."""
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        lines = []
        for paragraph in root.iter(WORD_NS + "p"):
            parts = []
            for node in paragraph.iter():
                if node.tag == WORD_NS + "t":
                    parts.append(node.text or "")
                elif node.tag == WORD_NS + "tab":
                    parts.append("\t")
                elif node.tag in (WORD_NS + "br", WORD_NS + "cr"):
                    parts.append("\n")
            lines.append("".join(parts))
        return "\n".join(lines)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def clean_key(name):
    """A label as written, without brackets, bold marks or spare spaces ("**Dana Reyes** (she/her)" gives
    "Dana Reyes"). Compare labels in lower case; tell a name by its capitals."""
    name = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", norm(name))
    return re.sub(r"\s+", " ", name.strip("*_ -\u2013:"))


def label_of(line):
    """(key, words, strong): the label at the start of an original line, in lower case, or None; the
    line's words after its bullet, timestamp and label; and whether the label has the marks of a
    transcript (a timestamp, a name alone on its line, a voice tag or a bracketed name)."""
    rest, key, strong = line, None, False
    match = BULLET.match(rest)
    if match:
        rest = rest[match.end():]
    match = LEAD_STAMP.match(rest)
    stamped = bool(match)
    if match:
        rest = rest[match.end():]
    for pattern in (VOICE, BRACKET_NAME):
        match = pattern.match(rest)
        if match and kind_of(clean_key(match.group(1))):
            words = re.sub(r"\s*</v>\s*$", "", rest[match.end():])
            stamp = LEAD_STAMP.match(words) or re.fullmatch(r"\s*" + STAMP + r"\s*", words)
            return clean_key(match.group(1)), words[stamp.end():] if stamp else words, True
    header = HEADER.match(rest)
    if header and header.group("stamp") and "," not in header.group("name") \
            and (kind_of(clean_key(header.group("name"))) == "speaker"
                 or ROLE_WORDS.fullmatch(clean_key(header.group("name")).lower())):
        return clean_key(header.group("name")), "", True
    match = NAME_LABEL.match(rest)
    if match and len(match.group("name").split()) <= 5 and re.search(r"[^\W\d_]", match.group("name")):
        name = clean_key(match.group("name"))
        if kind_of(name) or name.lower() in FIELDS:
            key, rest = name, rest[match.end():]
            strong = bool(kind_of(name)) and (stamped or bool(
                match.group("paren") and re.search(r"\d:\d", match.group("paren"))))
            stamp = LEAD_STAMP.match(rest)
            if stamp:
                rest, strong = rest[stamp.end():], bool(kind_of(name))
    return key, rest, strong


def kind_of(label):
    """"student", "speaker" or None for a label as written: one of the student's marks (or any label
    starting "My "), a speaker (a name in capitals, "Speaker 1", "P1", "Her", "A", a role), or neither
    (a field such as "Pain")."""
    if not label:
        return None
    low = label.lower()
    if low in STUDENT_MARKS or low.startswith("my "):
        return "student"
    if low in FIELDS:
        return None
    if SPEAKER.fullmatch(low) or ROLE_WORDS.fullmatch(low) or is_name(label):
        return "speaker"
    return None


def short_capitalised(word):
    """A title or abbreviation on TITLES ("Dr.", "Jan.", "Calif."), or a single capital initial ("J.")."""
    core = word[:-1] if word.endswith(".") else ""
    core = "".join(ch for ch in core.translate(APOSTROPHES) if not unicodedata.category(ch).startswith("M") and ch != "'")
    return core.isalpha() and core[:1].isupper() and (len(core) == 1 or core.lower() in TITLES)


def is_short_form(word):
    if word[:1].isupper():
        return LETTER_RUN.fullmatch(word) is not None or short_capitalised(word)
    # "no." and "nos." are numbers only before a digit; "I said no. They kept it." is two sentences.
    return word.lower() in SHORT_FORMS - {"no.", "nos."} or LETTER_RUN.fullmatch(word) is not None


def ends_sentence(token, following):
    core = token.rstrip(CLOSERS)
    if not core or core[-1] not in ".!?":
        return False
    # A number after a full stop starts a sentence ("They kept most of it. $150 was for cleaning."),
    # unless the full stop ends a title or short form ("Jan. 5", "approx. 40", "no. 5").
    bare = following.lstrip("([*_$\u00a3\u20ac")
    if not bare or not (bare[0].isupper() or bare[0].isdigit()):
        return False
    if core[-1] == "." and (is_short_form(core.lstrip(OPENERS)) or bare[0].isdigit()
                            and core.lstrip(OPENERS).lower() in {"no.", "nos."}):
        return False
    return True


def line_ends_sentence(last, following, bulleted):
    """data.md's line-break rule: a line ends a sentence only when it ends in . ! or ? (a short form
    or a next line starting with a digit keeps it open), or when the next line is a bullet."""
    if bulleted:
        return True
    core = last.rstrip(CLOSERS)
    if not core or core[-1] not in ".!?":
        return False
    if core[-1] == "." and is_short_form(core.lstrip(OPENERS)):
        return False
    return True


def make_turn(lines):
    """(text, starts, ends) for the (words, bulleted) lines of one turn, joined by a space, with the
    offsets where a sentence starts and ends."""
    text, ends, tokens = "", set(), []
    for number, (words, bulleted) in enumerate(lines):
        words = norm(words)
        if not words:
            continue
        if text:
            text += " "
        offset = len(text)
        for match in re.finditer(r"\S+", words):
            tokens.append((offset + match.start(), offset + match.end(), match.group(0), number, bulleted))
        text += words
    starts = {0}
    for (_, end, token, line_no, _), (start, _, following, next_no, next_bullet) in zip(tokens, tokens[1:]):
        if (ends_sentence(token, following) if line_no == next_no
                else line_ends_sentence(token, following, next_bullet)):
            ends.add(end)
            starts.add(start)
    ends.add(len(text))
    return text, starts, ends


def quotations(text):
    """(start, end) of the words inside each pair of double quotation marks, left to right."""
    spans, index = [], text.find('"')
    while index != -1:
        close = text.find('"', index + 1)
        if close == -1:
            break
        inner = text[index + 1:close]
        start = index + 1 + len(inner) - len(inner.lstrip())
        spans.append((start, start + len(inner.strip())))
        index = text.find('"', close + 1)
    return spans


def find(wanted, turns, whole_sentences, typed):
    """How many sentences the first match of wanted in one of turns holds, or 0 when none matches.
    With whole_sentences, a match must start where a sentence starts and end where one ends (or, in
    typed notes, be the whole of a quotation in the notes)."""
    for text, starts, ends in turns:
        quoted = quotations(text) if typed else []
        index = text.find(wanted)
        while index != -1:
            end = index + len(wanted)
            before = text[index - 1] if index > 0 else " "
            after = text[end] if end < len(text) else " "
            if not (before.isalnum() or after.isalnum()):
                if not whole_sentences or (index in starts and end in ends) or (index, end) in quoted:
                    return 1 + sum(1 for e in ends if index < e < end)
            index = text.find(wanted, index + 1)
    return 0


def capital(word):
    """A word that starts with a capital letter, or with a letter of a script that has no capitals."""
    first = word[:1]
    return first.isupper() or (first.isalpha() and not first.islower())


def is_name(text):
    words = text.strip("*_ ").split()
    if not 1 <= len(words) <= 4 or re.search(r"\d", text) or not capital(words[0]):
        return False
    if not all(capital(w) or w.lower() in PARTICLES for w in words):
        return False
    bare = [w.translate(APOSTROPHES).strip(",.()").lower() for w in words if w.lower() not in PARTICLES]
    return not all(w in COMMON for w in bare)


def has_contact(text):
    """An email address, or a phone number of 10 or more digits, as render_page.py reads them (data.md)."""
    text = norm(text)
    if EMAIL.search(text):
        return True
    for match in PHONE.finditer(text):
        found = match.group(0).strip()
        groups = re.findall(r"\d+", found)
        if all(len(g) == 4 and g[:2] in ("19", "20") for g in groups) or DATE_RUN.fullmatch(found) \
                or THOUSANDS.fullmatch(found):
            continue
        if sum(len(g) for g in groups) >= 10:
            return True
    return False


def replacement_problem(old, new, raw):
    """Why this change isn't one of the kinds sorting-rules section 1 allows, or ""."""
    if not isinstance(old, str) or not isinstance(new, str) or not old.strip():
        return "it isn't text"
    key = old.strip()
    if new.startswith("\n"):
        if not (new == "\n" + old or LABEL_VALUE.fullmatch(new[1:])) or not key.endswith(":") or not (
                clean_key(key).lower() in SPLIT_WORDS or is_name(key[:-1])):
            return ('a split only puts a line break before a label such as "A:" or "Sam:" ("A:": "\\nA:" or '
                    '"\\nPerson:")')
        if clean_key(key).lower() in STUDENT_MARKS and new not in ("\n" + old, "\nInterviewer:"):
            return f'"{key}" marks the student\'s own words, so it turns only into "Interviewer:"'
        for match in re.finditer(re.escape(key), raw):
            before = raw[:match.start()].rstrip(" \t")
            if before and not before.endswith("\n") and before[-1] not in ".?!\"')\u201d\u2019":
                return "a split goes only where a sentence ends"
        if clean_key(key).lower() not in SPLIT_WORDS and not re.search(r"(?m)^\s*" + re.escape(key), raw):
            return "a split at a name goes only before a label that starts another line of the note"
        return ""
    if key.endswith(":") and "\n" not in key and len(key.split()) <= 5:
        if not LABEL_VALUE.fullmatch(new):
            return 'a speaker label turns only into "Person:", "Person N:" or "Interviewer:"'
        if clean_key(key).lower() in STUDENT_MARKS and new != "Interviewer:":
            return f'"{key}" marks the student\'s own words, so it turns only into "Interviewer:"'
        return ""
    if EMAIL.fullmatch(key) or LINK_KEY.fullmatch(key) or ADDRESS_KEY.fullmatch(key) or (
            re.fullmatch(r"\+?[\d\s().-]{7,}", key) and len(re.findall(r"\d", key)) >= 7):
        place = PLACE_VALUE.fullmatch(new) and all(capital(w) or w.lower() == "the" for w in new.split())
        return "" if new == "" or (place and ADDRESS_KEY.fullmatch(key)) else \
            "a contact detail is removed, or an address turned into its neighbourhood (capitalised words)"
    if is_name(key) or SPEAKER.fullmatch(key.lower()) and key[:1].isupper():
        role = ROLE_VALUE.fullmatch(new)
        if role and (not role.group("relation") or role.group("relation").lower().rstrip("s") in RELATIONS
                     or role.group("relation").lower() in RELATIONS):
            return ""
        return ('a name turns only into "Person", "Person N", "Interviewer" or a role such as "their landlord" or '
                '"a close friend" (a relation the check knows, after their, the, a, an, his, her, my, our or your)')
    return ("only a name, a contact detail or a speaker label may be changed (a name is one to four "
            "capitalised words, never a single common word such as No, Never or Rarely)")


def apply(text, changes):
    """The text with each listed change made, longest first, at word boundaries."""
    for old in sorted(changes, key=len, reverse=True):
        key = unicodedata.normalize("NFC", old)
        pattern = ((r"(?<!\w)" if key[:1].isalnum() else "") + re.escape(key)
                   + (r"(?!\w)" if key[-1:].isalnum() else ""))
        text = re.sub(pattern, lambda _match, new=str(changes[old]): new, text)
    return text


def original_lines(raw, changes):
    """The original after the listed changes, one record per line, without blank lines and lines
    holding only a timestamp, a cue number or WEBVTT. A line holding only a label ("Dana Reyes  0:07",
    "Sam:") is joined to the line after it. Each record: the forms a copy may give the line ("full",
    "words"), the line's label now and before the changes, whether it looks like a transcript's, and
    whether it starts with a bullet or is indented."""
    raw_lines = unicodedata.normalize("NFC", raw).splitlines()
    pieces = []
    for number, raw_line in enumerate(raw_lines):
        following = next((line for line in raw_lines[number + 1:] if line.strip()), "")
        if (kind_of(clean_key(raw_line)) == "speaker" and "," not in raw_line and len(raw_line.split()) <= 4
                and re.fullmatch(r"\s*" + STAMP + r"\s*", following)):
            raw_line = raw_line.rstrip() + ":"  # "Dana Reyes" on a line, then "00:00:09": the label "Dana Reyes:"
        before = label_of(raw_line)[0]
        for index, piece in enumerate(apply(raw_line, changes).split("\n")):
            if piece.strip() and not SKIP_LINE.fullmatch(piece):
                pieces.append((piece, before if index == 0 else label_of(piece)[0]))
    out, index = [], 0
    while index < len(pieces):
        line, before = pieces[index]
        label, words, strong = label_of(line)
        bullet = BULLET.match(line)
        record = {"full": [norm(line), norm(BULLET.sub("", line, count=1)),
                           norm((bullet.group(0) if bullet else "") + words)]
                          + ([norm(f"{label}: {words}")] if label else []), "words": norm(words), "label": label,
                  "before": before, "strong": strong, "bulleted": BULLET.match(line) is not None,
                  "indented": INDENT.match(line) is not None and not BULLET.match(line) and not label}
        if label and not norm(words) and (index + 1 >= len(pieces) or kind_of(label_of(pieces[index + 1][0])[0])):
            index += 1  # a label with nothing after it before the next speaker: it holds no words
            continue
        if label and not norm(words):
            following = pieces[index + 1][0]
            record["full"] = [norm(line + " " + following), norm(following),
                              norm(BULLET.sub("", following, count=1))]
            record["words"] = norm(label_of(following)[1])
            record["bulleted"] = BULLET.match(following) is not None
            index += 1
        out.append(record)
        index += 1
    return out


def role_name(role):
    return "Interviewer" if role[0] == "interviewer" else "Person" + (f" {role[1]}" if role[1] else "")


def check_copy(path, before, copy_text):
    """(problems, [(role, words, bulleted, indented)], transcript): the copy against its original."""
    rows, current = [], None
    for number, line in enumerate(copy_text.splitlines(), 1):
        if not line.strip() or SKIP_LINE.fullmatch(line):
            continue
        if line.lstrip().startswith("#"):
            line = "Interviewer: " + line.strip()
        match = ROLE.match(line)
        if match:
            role = ("interviewer", None) if match.group("role") == "Interviewer" else ("person", match.group("n"))
            rest = line[match.end():] if match.group("colon") else ""
            current = role if not rest.strip() else current
        elif current:
            role, rest = current, line
        else:
            return ([f'{path.name}: line {number} doesn\'t start with "Interviewer:" or "Person:". Put who speaks in '
                     f"front of every line, and change nothing else."], [], False)
        rows.append((role, rest))
    after = []
    for index, (role, rest) in enumerate(rows):
        following = rows[index + 1][1] if index + 1 < len(rows) else ""
        label, words, _ = label_of(rest)
        bare_name = ((kind_of(clean_key(rest)) == "speaker" or ROLE_WORDS.fullmatch(clean_key(rest).lower()))
                     and "," not in rest and len(rest.split()) <= 4
                     and re.fullmatch(r"\s*" + STAMP + r"\s*", following))
        if rest.strip() and not SKIP_LINE.fullmatch(rest) and not (label and not words.strip()) and not bare_name:
            after.append((role, rest))
    if len(before) != len(after):
        return ([f"{path.name} has {len(after)} lines where its original, after the listed changes, has {len(before)}. "
                 f"Keep one line for each line of the original, in order; split a line only with a listed change "
                 f'("A:": "\\nA:").'], [], False)
    kinds = [kind_of(r["before"]) for r in before]
    speakers = {r["before"].lower() for r, k in zip(before, kinds) if k == "speaker"}
    labelled = sum(1 for k in kinds if k)
    transcript = (any(r["strong"] for r in before)
                  or len(speakers) >= 2 and labelled >= 0.8 * len(before))
    seen, previous, turns = {}, None, []
    for number, (record, (role, rest)) in enumerate(zip(before, after), 1):
        label, before_label = record["label"], record["before"]
        key, before_key = (label or "").lower() or None, (before_label or "").lower() or None
        if norm(rest) not in record["full"] + [record["words"]]:
            return ([f'{path.name} differs from its original at line {number}: "{norm(rest)[:60]}" (the original '
                     f'says "{record["full"][0][:60]}"). A cleaned copy puts who speaks in front of each line and '
                     f"changes only names and contact details, each listed in replacements.json."], [], False)
        needed, why = None, ""
        if kind_of(before_label) == "student" or kind_of(label) == "student":
            mark = before_label if kind_of(before_label) == "student" else label
            needed, why = ("interviewer", None), f'its original starts with "{mark}:", the student\'s own words'
        elif key and ROLE_WORDS.fullmatch(key) and key != before_key:
            needed, why = (("interviewer", None) if "interviewer" in key else ("person", role[1])), \
                f'its label was changed to "{label}"'
        elif kind_of(label) == "speaker":
            if key in seen:
                needed, why = seen[key], f'its label "{label}" is {role_name(seen[key])} on another line'
            seen.setdefault(key, role)
        elif transcript and role != ("interviewer", None):
            needed = previous or ("interviewer", None)
            why = (f"it has no speaker's label and continues {role_name(previous)}'s turn above it" if previous
                   else "it has no speaker's label and comes before anyone speaks")
        if needed and role != needed:
            return ([f"{path.name} line {number} is labelled {role_name(role)}, but {why}. Label it "
                     f"{role_name(needed)}."], [], False)
        if kind_of(label) or kind_of(before_label):
            previous = role
        spoken = kind_of(label) == "speaker" or bool(label and ROLE_WORDS.fullmatch(label.lower()))
        turns.append((role, record["words"], record["bulleted"], record["indented"], spoken, label is None))
    problems = []
    if transcript:
        spoken = {turn[0][0] for turn in turns}
        for role, word in (("interviewer", "Interviewer"), ("person", "Person")):
            if role not in spoken:
                problems.append(f"{path.name} is a transcript (its lines name who speaks) but has no {word} line. Mark "
                                f"which speaker is the student and which the person.")
    return problems, turns, transcript


def main(argv):
    if len(argv) == 3 and argv[1] == "--text":
        path = Path(argv[2])
        try:
            print(read_note(path))
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as error:
            print(f"Not done: could not read {path}: {error}. Save it as .docx, .md or .txt.")
            return 1
        return 0
    if len(argv) != 2:
        print(__doc__)
        return 2
    source = Path(argv[1])
    try:
        data = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        print(f"Not done: could not read {source}: {error}")
        return 1
    folder = source.resolve().parent
    work = folder / "discover-work"
    clean = work / "interviews-clean"
    originals_root = (folder / "interviews").resolve()
    interviews = [i for i in data.get("interviews") or [] if isinstance(i, dict)]
    problems, checked = [], 0
    if not interviews:
        print("No interviews in discovery.json yet. Write this batch into it first, then run this check.")
        return 1
    try:
        replacements = json.loads((clean / "replacements.json").read_text(encoding="utf-8-sig"))
        if not isinstance(replacements, dict):
            raise ValueError
    except (OSError, ValueError):
        replacements = None
        problems.append("discover-work/interviews-clean/replacements.json is missing or not valid JSON. Write it "
                        "as sorting-rules.md section 1 says.")
    ids = [str(i.get("id")) for i in interviews]
    files = {}
    if clean.is_dir():
        for entry in sorted(clean.iterdir()):
            if entry.name.startswith(".") or entry.name == "replacements.json":
                continue
            if entry.is_file() and entry.suffix == NOTE_SUFFIX and entry.stem in ids:
                files[entry.stem] = entry
            else:
                problems.append(f"discover-work/interviews-clean/{entry.name} isn't the cleaned copy of an interview "
                                f"in discovery.json. Keep only <id>.md files (I1.md) and replacements.json there.")
    in_batch = sum(1 for i in interviews for f in (i.get("facts") or []) + (i.get("new_findings") or [])
                   if isinstance(f, dict) and isinstance(f.get("quote"), str) and f["quote"].strip())
    used, voices = {}, {}
    for interview in interviews:
        iid = str(interview.get("id"))
        path = files.get(iid)
        if path is None:
            problems.append(f"{iid}: no cleaned copy named {iid}.md in discover-work/interviews-clean/.")
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if has_contact(text):
            problems.append(f"{path.name} still holds an email address or a phone number. Remove it and list the "
                            f"change in replacements.json.")
        if replacements is None:
            continue
        entry = replacements.get(iid)
        if not isinstance(entry, dict) or not isinstance(entry.get("original"), str):
            problems.append(f"{iid}: replacements.json names no original note for it.")
            continue
        original = (folder / entry["original"]).resolve()
        if originals_root not in original.parents or not original.is_file():
            problems.append(f"{iid}: its original note {entry['original']} isn't a file in the student's "
                            f"interviews/ folder. Every note keeps its original there (pasted notes too).")
            continue
        span = entry.get("lines")
        if span is not None and not (isinstance(span, list) and len(span) == 2
                                     and all(type(n) is int and n >= 1 for n in span) and span[0] <= span[1]):
            problems.append(f'{iid}: "lines" must be [first, last], line numbers of the original.')
            continue
        for other, other_span in used.get(original, []):
            if span is None or other_span is None or not (span[1] < other_span[0] or other_span[1] < span[0]):
                problems.append(f"{iid} and {other} are cleaned from the same lines of {entry['original']}. One "
                                f'interview is one note; when one file holds several, give each its own "lines".')
        used.setdefault(original, []).append((iid, span))
        changes = entry.get("replaced", {})
        if not isinstance(changes, dict):
            problems.append(f'{iid}: "replaced" in replacements.json must map each change to what replaced it.')
            continue
        try:
            raw = read_note(original)
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            problems.append(f"{iid}: its original note {entry['original']} can't be read. Save it as .docx, .md or .txt.")
            continue
        if span is not None:
            raw = "\n".join(raw.splitlines()[span[0] - 1:span[1]])
        bad = [(old, why) for old, new in changes.items() for why in [replacement_problem(old, new, raw)] if why]
        for old, why in bad:
            problems.append(f'{iid}: replacements.json changes "{str(old)[:40]}", but {why}.')
        if bad:
            continue
        found, turns, transcript = check_copy(path, original_lines(raw, changes), text)
        problems += found
        if not turns:
            continue
        # The person's words, for quoting: in a transcript, one speaker's lines read together; in typed
        # notes, each line stands alone, unless it is indented under the line above.
        groups, said = [], []
        for role, words, bulleted, indented, spoken, unlabelled in turns:
            wrapped = (groups and not bulleted and words[:1].islower() and len(groups[-1][1][-1][0]) >= 60
                       and groups[-1][1][-1][0].rstrip(CLOSERS)[-1:] not in ".!?")
            # A line with no label under a speaker's labelled line goes on with that speaker's turn.
            goes_on = groups and said[-1] and unlabelled and not bulleted
            if groups and groups[-1][0] == role and (transcript and not bulleted or indented or wrapped or goes_on):
                groups[-1][1].append((words, bulleted))
            else:
                groups.append((role, [(words, bulleted)]))
                said.append(spoken)
        person = [make_turn(lines) for role, lines in groups if role[0] == "person"]
        voice = " ".join(t for t, _, _ in person)
        twin = next((other for seen_voice, other in voices.items() if voice and seen_voice and (
            voice == seen_voice or len(min(voice, seen_voice, key=len)) > 40 and (voice in seen_voice or seen_voice in voice))),
            None)
        if twin:
            problems.append(f"{iid} and {twin} hold the same person's words. One conversation is one "
                            f"interview: drop the second copy.")
        voices.setdefault(voice, iid)
        interviewer = [norm(" ".join(w for w, _ in lines)) for role, lines in groups if role[0] == "interviewer"]
        quotes = [("fact", f.get("quote")) for f in interview.get("facts") or [] if isinstance(f, dict)]
        quotes += [("new finding", f.get("quote")) for f in interview.get("new_findings") or [] if isinstance(f, dict)]
        for kind, quote in quotes:
            if not isinstance(quote, str) or not quote.strip():
                continue
            checked += 1
            wanted = norm(quote)
            start = " ".join(quote.split()[:8])
            count = find(wanted, person, True, not transcript)
            if count:
                if kind == "new finding" and count > 3:
                    problems.append(f'{iid} {kind} "{start} ...": {count} sentences. Quote the one to three '
                                    f"sentences where the person raised it.")
                continue
            if any(wanted in turn for turn in interviewer):
                problems.append(f'{iid} {kind} "{start} ...": these are the interviewer\'s words (the student\'s own), '
                                f"not the person's. Drop it.")
            elif any(wanted in turn for turn, _, _ in person):
                unit = "sentence" if find(wanted, person, False, False) else "word"
                problems.append(f'{iid} {kind} "{start} ...": cut in the middle of a {unit}. Quote whole sentences, '
                                f"as the person said them: start the quote earlier or end it later. A full stop after "
                                f"a title or abbreviation (Dr., Jan., U.S., e.g.) or before a word in lower case "
                                f"doesn't end a sentence, and a line ends one only after . ! or ?.")
            else:
                problems.append(f'{iid} {kind} "{start} ...": not in {path.name}, the person\'s words, word for word. '
                                f"Copy it exactly, or drop it.")
    for original, spans in used.items():
        if any(span is not None for _, span in spans):
            covered = {n for _, span in spans if span for n in range(span[0], span[1] + 1)}
            left = [n for n, line in enumerate(read_note(original).splitlines(), 1) if line.strip() and n not in covered]
            if left:
                problems.append(f'{original.name}: its lines {left[0]} to {left[-1]} belong to no interview. With "lines", '
                                f"every line of a note belongs to one interview, so nothing that prompted a reply "
                                f"is left out.")
    if in_batch == 0:
        problems.append("No quotes were checked. Write this batch's facts into discovery.json first, then run this.")
    result = {"date": dt.date.today().isoformat(), "checked": checked, "notes": sorted(p.name for p in files.values()),
              "ok": not problems, "problems": problems}
    work.mkdir(exist_ok=True)
    (work / "interview-quote-check.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
    if problems:
        print(f"Not done: {len(problems)} problem(s). Fix them, then run this again:")
        for line in problems:
            print(" -", line)
        return 1
    print(f"All {checked} interview quotes are the interviewees' own words, in their own interview's cleaned notes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
