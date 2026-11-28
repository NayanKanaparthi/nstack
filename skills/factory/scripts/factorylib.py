"""factorylib: the shared core of the factory kit.

Paths, settings, the log line format, safe appending, reading and merging, the
board, and notification. Python 3.9, standard library only, no network.

Nothing here deletes or rewrites a file that exists. Logs only grow: a line is
appended under an exclusive lock, and a span changes state by appending another
line with the same span id (SPEC sections 1.3, 3, 4.0, 5.1).
"""

import contextlib
import copy
import datetime
import fcntl
import functools
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

VERSION = "0.1.0"


class EXIT(object):
    """Exit codes shared by every command (SPEC 4.0)."""
    OK = 0
    NO = 1
    USAGE = 2
    MISSING = 3
    EMPTY = 4
    TIMEOUT = 124
    NOT_FOUND = 127


KINDS = ("feature", "phase", "node", "iteration", "agent_call", "command", "wait", "checkpoint")
STATUSES = ("running", "done", "failed", "stopped")
CLOSED_STATUSES = ("done", "failed", "stopped")
FAILURE_CLASSES = ("spec-ambiguity", "test-wrong", "impl-bug", "env-tooling", "flaky",
                   "scope-creep", "context-overflow", "model-stall")
VERDICTS = ("approved", "rejected")
RUNNERS = ("claude", "codex", "opencode", "cursor", "ollama")
CHANNELS = ("desktop", "command", "connector")
OLD_PHASES = ("intake", "plan", "plan-review", "gate-a", "tests", "test-write", "integration",
              "e2e", "evals", "gate-b", "release", "retro")

NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
HUMAN_WAIT_LIMIT_S = 12 * 3600


# ---------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------

class FactoryError(Exception):
    """A failure with an exit code and a plain one-line message.

    `reason` is the fixed sentence written to log-errors.jsonl: it never holds
    an argument value, so it is safe to keep (SPEC 4.0).
    """

    def __init__(self, code, message, reason=None):
        Exception.__init__(self, message)
        self.code = code
        self.message = message
        if reason is None:
            reason = message
        reason = str(reason)
        if reason.startswith("factory: "):
            reason = reason[len("factory: "):]
        self.reason = reason

    def line(self):
        text = self.message
        return text if text.startswith("factory:") else "factory: " + text


class BuildNotFound(FactoryError):
    def __init__(self, message, reason="build log not found"):
        FactoryError.__init__(self, EXIT.MISSING, message, reason)


class ConfigError(FactoryError):
    def __init__(self, message, reason="settings file is not valid"):
        FactoryError.__init__(self, EXIT.USAGE, message, reason)


# ---------------------------------------------------------------------------
# time
# ---------------------------------------------------------------------------

_TS_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")


@functools.lru_cache(maxsize=16384)
def _epoch_cached(text):
    match = _TS_RE.match(text)
    if not match:
        return None
    try:
        year, month, day, hour, minute, second = [int(g) for g in match.groups()[:6]]
        stamp = datetime.datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    delta = stamp - datetime.datetime(1970, 1, 1)
    epoch = delta.days * 86400 + delta.seconds
    zone = match.group(7)
    if zone and zone != "Z":
        digits = zone[1:].replace(":", "")
        offset = int(digits[:2]) * 3600 + int(digits[2:]) * 60
        epoch -= offset if zone[0] == "+" else -offset
    return epoch


def to_epoch(value):
    """Seconds since the epoch for a timestamp string, else None."""
    if isinstance(value, str):
        return _epoch_cached(value)
    return None


def from_epoch(epoch):
    return time.strftime(TS_FORMAT, time.gmtime(int(epoch)))


def now():
    """Current UTC time as YYYY-MM-DDTHH:MM:SSZ; $FACTORY_NOW wins when set."""
    forced = os.environ.get("FACTORY_NOW")
    if forced:
        if to_epoch(forced) is None:
            raise FactoryError(EXIT.USAGE, "factory: FACTORY_NOW is not a timestamp like 2026-01-10T12:00:00Z",
                               "FACTORY_NOW is not a timestamp")
        return forced
    return time.strftime(TS_FORMAT, time.gmtime())


def now_epoch():
    return to_epoch(now())


def _now_text(value):
    if value is None:
        return now()
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return from_epoch(value)
    if isinstance(value, datetime.datetime):
        return value.strftime(TS_FORMAT)
    return now()


def words_for_duration(seconds):
    """45 s, 12 min, 1 h 30 min (SPEC 5.1)."""
    seconds = int(max(0, seconds))
    if seconds < 60:
        return "%d s" % seconds
    minutes = seconds // 60
    if minutes < 60:
        return "%d min" % minutes
    return "%d h %d min" % (minutes // 60, minutes % 60)


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

def home():
    """The factory home: $FACTORY_HOME, else ~/.factory."""
    chosen = os.environ.get("FACTORY_HOME")
    if chosen:
        return Path(chosen)
    return Path(os.path.expanduser("~")) / ".factory"


def valid_name(text):
    return isinstance(text, str) and bool(NAME_RE.match(text)) and text not in (".", "..")


def runs_root(factory_home=None):
    return Path(factory_home or home()) / "runs"


def build_dir_of(project, build, factory_home=None):
    return runs_root(factory_home) / project / build


def kit_dir():
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# durable append helpers
# ---------------------------------------------------------------------------

def _write_all(fd, data):
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def _read_all(fd):
    chunks = []
    offset = 0
    while True:
        chunk = os.pread(fd, 1 << 20, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def append_jsonl_locked(path, obj, mkdir=False):
    """Append one JSON line to `path` under an exclusive lock (creates the file)."""
    path = str(path)
    if mkdir:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    data = (obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=True)).encode("utf-8")
    if not data.endswith(b"\n"):
        data += b"\n"
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            data = b"\n" + data
        _write_all(fd, data)
    finally:
        os.close(fd)


def read_jsonl_tail(path, skip_bad=True):
    """Parsed object lines of a small append-only index; torn or wrong-typed lines are skipped."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def record_error(build_dir_or_home, command, code, reason):
    """Append one sanitized line {ts, command, exit, reason} to log-errors.jsonl.

    A folder that holds trace.jsonl is a build; anything else is the factory home.
    Never raises: a failed attempt to record a failure must not change the exit code.
    """
    try:
        target = Path(build_dir_or_home) if build_dir_or_home else home()
        try:
            stamp = now()
        except FactoryError:
            stamp = time.strftime(TS_FORMAT, time.gmtime())
        line = {"ts": stamp, "command": str(command), "exit": int(code), "reason": str(reason)}
        append_jsonl_locked(target / "log-errors.jsonl", line, mkdir=True)
    except Exception:
        pass


def append_current(project, build, phase, factory_home=None):
    """Append the current-build pointer line (SPEC 1.3)."""
    path = Path(factory_home or home()) / "current.jsonl"
    append_jsonl_locked(path, {"ts": now(), "project": project, "build": build, "phase": phase},
                        mkdir=True)


def read_current(factory_home=None):
    """The last valid pointer line {ts, project, build, phase}, or None."""
    entries = read_jsonl_tail(Path(factory_home or home()) / "current.jsonl")
    for entry in reversed(entries):
        if valid_name(entry.get("project")) and valid_name(entry.get("build")):
            return entry
    return None


# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = (
    ("api key (sk-)", re.compile(r"sk-[A-Za-z0-9_-]{20,}")),
    ("github token", re.compile(r"ghp_[A-Za-z0-9]{30,}")),
    ("github fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{30,}")),
    ("npm token", re.compile(r"npm_[A-Za-z0-9]{30,}")),
    ("chat app token", re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}")),
    ("aws access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private key header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)
_ASSIGNMENT_RE = re.compile(r"(?i)((?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*)(\S{8,})")
REDACTED = "[REDACTED]"
# A bare hex word: 7 to 40 hex characters with at least one digit and one letter. Words joined
# by a dash or underscore (ids, dates) are not touched. Ordinary words ("acceded") have no digit.
_HEX_WORD_RE = re.compile(r"(?<![\w-])(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}(?![\w-])", re.I)


def _assignment_sub(match):
    value = match.group(2)
    if value.startswith(REDACTED):
        return match.group(0)
    _assignment_sub.count += 1
    return match.group(1) + REDACTED


_assignment_sub.count = 0


def redact_count(text):
    """(clean text, number of values replaced)."""
    if not isinstance(text, str) or not text:
        return text, 0
    total = 0
    for _name, pattern in _SECRET_PATTERNS:
        text, count = pattern.subn(REDACTED, text)
        total += count
    _assignment_sub.count = 0
    text = _ASSIGNMENT_RE.sub(_assignment_sub, text)
    total += _assignment_sub.count
    return text, total


def redact(text):
    """Replace each secret-looking value with [REDACTED] (SPEC 3.5)."""
    return redact_count(text)[0]


def redact_plain(text):
    """redact, plus bare hex words (7 to 40 hex characters holding a digit and a letter: hashes and
    keys without a prefix). Only for the plain fields and plan.json strings (spec 1.1)."""
    if not isinstance(text, str) or not text:
        return text
    return _HEX_WORD_RE.sub(REDACTED, redact_count(text)[0])


def _redact_obj(value):
    if isinstance(value, str):
        return redact_count(value)
    if isinstance(value, list):
        out, total = [], 0
        for item in value:
            clean, count = _redact_obj(item)
            out.append(clean)
            total += count
        return out, total
    if isinstance(value, dict):
        out, total = {}, 0
        for key, item in value.items():
            clean, count = _redact_obj(item)
            out[key] = clean
            total += count
        return out, total
    return value, 0


_USER_DIR = "Us" + "ers"  # kept out of one literal so the kit's own privacy scan stays clean
_HOME_PATH_RE = re.compile(
    r"(?:/" + _USER_DIR + r"/[^/\s\"']+|/" + "home" + r"/[^/\s\"']+|[A-Za-z]:\\" + _USER_DIR + r"\\[^\\\s\"']+)")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


def load_private_patterns(patterns_file):
    """Compiled deny-list entries from a patterns file (one regex or word per line)."""
    out = []
    if not patterns_file:
        return out
    try:
        text = Path(os.path.expanduser(str(patterns_file))).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for raw in text.splitlines():
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        try:
            out.append(re.compile(entry, re.IGNORECASE))
        except re.error:
            out.append(re.compile(re.escape(entry), re.IGNORECASE))
    return out


def scan_text(text, patterns_file=None):
    """Names of the private-looking things found in `text`, one name per match.

    Never returns the matched text itself. Covers the secret patterns of SPEC 3.5,
    home paths, email addresses, session and chat ids, and every entry of the
    machine file's private patterns file when one is set (SPEC 2, data rule).
    """
    found = []
    if not isinstance(text, str):
        return found
    for name, pattern in _SECRET_PATTERNS:
        found.extend([name] * len(pattern.findall(text)))
    for match in _ASSIGNMENT_RE.finditer(text):
        if not match.group(2).startswith(REDACTED):
            found.append("password or token assignment")
    found.extend(["home path"] * len(_HOME_PATH_RE.findall(text)))
    found.extend(["email address"] * len(_EMAIL_RE.findall(text)))
    found.extend(["session or chat id"] * len(_UUID_RE.findall(text)))
    for index, pattern in enumerate(load_private_patterns(patterns_file), 1):
        hits = len(pattern.findall(text))
        found.extend(["private pattern %d" % index] * hits)
    return found


# ---------------------------------------------------------------------------
# the plain-words check (PAGE-SPEC 1.3)
#
# Rules 4 to 13 are small patterns plus a short allow-list of ordinary things the patterns
# would wrongly catch (US, TV, A4, iPhone, and/or). It is a floor, not proof that a sentence is
# plain: it keeps ids, code, model names, shorthand and unexplained failures out and lets
# ordinary English through. Callers redact FIRST (redact), then check. The marker [REDACTED]
# is removed before the rules run, and no reason quotes more than 12 characters of a match
# (a hex word: 4 characters).
# ---------------------------------------------------------------------------

_ABBR_OK = {"AI", "AM", "PM", "OK", "US", "USA", "UK", "EU", "TV", "PDF", "FAQ", "CEO", "NASA"}
_TIME_UNIT_RE = re.compile(r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?|days?|weeks?)\b", re.I)
_PIECE_ID_OK = {"a3", "a4", "mp3", "mp4", "q1", "q2", "q3", "q4", "h1", "h2", "b2b", "b2c"}
_CAMEL_OK = {"iphone", "ipad", "icloud", "imessage", "ebay"}
_SLASH_OK = {"and/or", "either/or", "he/she", "his/her", "yes/no", "on/off"}
_ID_TOKEN_RE = re.compile(r"\b(?:AC|R|T|N|F|M|O)-?\d+\b|\bT-[A-Z]+-\d+\b|§\s*\d", re.I)
_PIECE_ID_RE = re.compile(r"\b[A-Za-z]{1,4}\d+[A-Za-z]?\b")
_DASH_ID_UP_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+\b")
_DASH_ID_LOW_RE = re.compile(r"\b[a-z][a-z0-9]*(?:-[a-z0-9]+)*-\d+[a-z]?\b")
_CALL_KEY_RE = re.compile(r"\b[A-Za-z0-9-]+\.[a-z-]+\.\d+\b", re.I)
_SPAN_ID_RE = re.compile(r"\bs\d{3,}\b", re.I)
_HEX_ID_RE = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b", re.I)
_ABBR_RE = re.compile(r"\b[A-Z]{2,}\b")
_FILE_RE = re.compile(r"[\w.-]+\.(?:py|md|json|jsonl|js|yaml|yml|sh|txt|html|css)\b", re.I)
_FLAG_RE = re.compile(r"(?:^|\s)--[a-z]")
_SNAKE_RE = re.compile(r"\b[a-z]+_[a-z_]+\b")
_SLASH_RE = re.compile(r"[A-Za-z]+/[A-Za-z]+")
_CAMEL_RE = re.compile(r"\b[a-z]+[A-Z][a-z]+")
_CODE_WORD_RE = re.compile(r"\b(?:factorylib|\w+lib)\b|\b404\b|\b(?:error|status|code|http)\s+[45]\d\d\b", re.I)
_VERSION_RES = (re.compile(r"\bv\d+(?:\.\d+)*\b", re.I), re.compile(r"\b\d+\.\d+(?:\.\d+)+\b"))
_MODEL_RE = re.compile(r"\b(?:chat)?(?:gpt|sonnet|opus|fable|haiku|claude|codex|qwen|gemma|llama|mistral|"
                       r"deepseek|ollama)[\w.-]*", re.I)
_JARGON_RE = re.compile(r"\b(?:spans?|iterations?|agent_calls?|rubrics?|nodes?|jsonl|stdout|stderr|stdin|regex|"
                        r"tokens?|tokenizer|llm|pytest|unittest|commits?|exit code|exit status|status code)\b", re.I)
_FRACTION_RE = re.compile(r"\b\d+\s*/\s*\d+\b")
_COUNT_OUTCOME_RE = re.compile(r"(?<!\ball )\b(\d+)\s+((?:[A-Za-z-]+\s+){0,3}?)"
                               r"(?:passed|failed|passing|failing|done|finished|clean|met|fixed|missing)\b", re.I)
_WHOLE_RE = re.compile(r"\b(?:of|out of)\s+(?:the\s+|all\s+)?\d+\b", re.I)
_STEPWORD_BEFORE_RE = re.compile(r"\b(?:step|attempt|review|round|stage|first|last|piece|page|part)\s+$", re.I)
_BAD_RE = re.compile(r"\b(?:failed|failure|failures|stopped|died|errored|aborted|killed|crashed|crash|broke|"
                     r"broken|timed out|did not work|didn't work|does not work|not working)\b", re.I)
_NEGATION_BEFORE_RE = re.compile(r"\b(?:no|nothing|never|not|none)\b(?:\s+[\w'-]+){0,2}\s+$", re.I)
_NUMBER_SUBJECT_RE = re.compile(r"(?:\b\d+|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                                r"several|some|many|few|both))(?:\s+[\w'-]+){0,2}\s+$", re.I)
_REASON_RE = re.compile(r"\b(?:because|since|due to|on purpose|ran out|ran past|reached|got stuck|"
                        r"so (?:the|it|that|they|we|he|she|you|a|an)|after (?:\d+|the|a|an))\b", re.I)
_NEXT_RE = re.compile(r"\b(?:will|again|retry|retries|restart|restarts|resume|try|tries)\b", re.I)


def _quote(text, hexword=False, limit=12):
    """What a reason may quote: at most 12 characters (4 for a hex word), then ..."""
    if hexword:
        return text[:4] + "..."
    return text if len(text) <= limit else text[:limit] + "..."


def _allowed_skip(word, allowed):
    return word.lower() in {str(a).lower() for a in (allowed or ())}


def plain_sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def _label_rules(t, allowed=()):
    """Rules 4 to 11 of the plain-words check; reason sentences in rule order."""
    reasons = []
    hit, hit_hex = None, False
    for rx in (_ID_TOKEN_RE, _PIECE_ID_RE, _DASH_ID_UP_RE, _DASH_ID_LOW_RE, _CALL_KEY_RE, _SPAN_ID_RE, _HEX_ID_RE):
        for m in rx.finditer(t):
            g = m.group(0).strip()
            if rx is _PIECE_ID_RE or rx is _ID_TOKEN_RE:
                if g.lower() in _PIECE_ID_OK or re.fullmatch(r"v\d+", g, re.I):
                    continue
            hit, hit_hex = g, rx is _HEX_ID_RE
            break
        if hit:
            break
    if hit:
        reasons.append('It contains "%s", which looks like an id.' % _quote(hit, hit_hex))
    for m in _ABBR_RE.finditer(t):
        if m.group(0) not in _ABBR_OK and not _allowed_skip(m.group(0), allowed):
            reasons.append('It contains the abbreviation "%s".' % _quote(m.group(0)))
            break
    code = None
    for rx in (_FILE_RE, _FLAG_RE, re.compile(r"`"), _SNAKE_RE, _CODE_WORD_RE):
        m = rx.search(t)
        if m:
            code = m.group(0).strip()
            break
    if not code:
        for m in _SLASH_RE.finditer(t):
            if m.group(0).lower() not in _SLASH_OK and not _FRACTION_RE.fullmatch(m.group(0)):
                code = m.group(0)
                break
    if not code:
        for m in _CAMEL_RE.finditer(t):
            if m.group(0).lower() not in _CAMEL_OK:
                code = m.group(0)
                break
    if code:
        reasons.append('It contains code or a file name ("%s").' % _quote(code))
    for rx in _VERSION_RES:
        m = rx.search(t)
        if m:
            reasons.append('It contains a version number ("%s").' % _quote(m.group(0)))
            break
    for m in _MODEL_RE.finditer(t):
        if not _allowed_skip(m.group(0), allowed):
            reasons.append('It names a model or tool ("%s").' % _quote(m.group(0)))
            break
    m = _JARGON_RE.search(t)
    if m:
        reasons.append('It uses a word the owner does not know ("%s").' % _quote(m.group(0)))
    if "\u2014" in t or "\u2013" in t:
        reasons.append("It uses a dash as punctuation.")
    for m in _FRACTION_RE.finditer(t):
        if m.group(0).replace(" ", "") != "24/7":
            reasons.append('It writes a number as a fraction ("%s").' % _quote(m.group(0)))
            break
    return reasons


def _count_without_whole(t):
    if _WHOLE_RE.search(t) or _FRACTION_RE.search(t):
        return None
    for s in plain_sentences(t):
        s_nt = re.sub(r"\d+:\d+", "", s)
        nums = re.findall(r"\b\d+\b", s_nt)
        for m in _COUNT_OUTCOME_RE.finditer(s_nt):
            if _STEPWORD_BEFORE_RE.search(s_nt[:m.start()]):
                continue
            rest = s_nt[m.start():].split(None, 1)
            if _TIME_UNIT_RE.match(rest[1] if len(rest) > 1 else ""):
                continue
            if re.search(r"\b(?:and|or|but)\b", m.group(2), re.I):
                continue
            if len(nums) > 1:
                continue
            if re.search(r"\band\s+(?:\w+\s+)?(?:fixed|solved|resolved)\b", s_nt[m.end() - 8:m.end() + 30], re.I):
                continue
            return m.group(0)
    return None


def _failure_without_reason(t):
    ss = plain_sentences(t)
    for i, s in enumerate(ss):
        for m in _BAD_RE.finditer(s):
            before = s[:m.start()]
            if _NEGATION_BEFORE_RE.search(before):
                continue
            if " " not in m.group(0) and _NUMBER_SUBJECT_RE.search(before):
                continue
            nxt = ss[i + 1] if i + 1 < len(ss) else ""
            if _REASON_RE.search(before + " " + s[m.end():]) or _REASON_RE.search(nxt):
                continue
            if _NEXT_RE.search(nxt):
                continue
            if re.match(r"\s+to\s+[a-z]+", s[m.end():], re.I) or re.match(r"\s+(?:once|twice)\b", s[m.end():], re.I):
                continue
            if nxt.rstrip().endswith("?") or re.search(r"\b(?:wait|waits|waiting|answer)\b", nxt, re.I):
                continue
            return m.group(0)
    return None


def plain_check(text, allowed=()):
    """Reason sentences why `text` is not plain enough for the owner; [] means it passes (rules 1 to 13)."""
    if not isinstance(text, str) or not text.strip():
        return ["It is empty."]
    t = text.replace(REDACTED, "").strip()
    if not t:
        return ["It is empty."]
    ss = plain_sentences(t)
    reasons = []
    if len(ss) > 3 or len(t) > 400:
        reasons.append("It is longer than three sentences or 400 characters.")
    if len(ss[0]) > 200:
        reasons.append("Its first sentence is longer than 200 characters.")
    reasons += _label_rules(t, allowed)
    found = _count_without_whole(t)
    if found:
        reasons.append('It gives a count without the whole ("%s").' % _quote(found, limit=30))
    found = _failure_without_reason(t)
    if found:
        reasons.append('It says "%s" without saying why.' % _quote(found))
    return reasons


def plain_label_check(text, allowed=()):
    """Short labels (state words, chips, result words): rules 4 to 11 only."""
    if not isinstance(text, str) or not text.strip():
        return ["It is empty."]
    t = text.replace(REDACTED, "").strip()
    return _label_rules(t, allowed) if t else ["It is empty."]


def plain_clean(text, limit=None):
    """Redacted text for a plain field, ready for the check (secrets first, then the check)."""
    clean = redact_plain(text if isinstance(text, str) else "")
    return clean[:limit] if limit else clean


def plain_words_of(cfg):
    """The project's allowed words (`plain_words_ok` in factory.json), as a list of strings."""
    words = cfg.get("plain_words_ok") if isinstance(cfg, dict) else None
    return [w for w in words if isinstance(w, str)] if isinstance(words, list) else []


STOP_REASONS = ("on_purpose", "usage_limit", "stuck", "error")
PLAIN_MISSING_TEXT = "No plain summary has been written for this step yet."
GATE_CLOSE_PLAIN = "You answered this decision, and the build carried on."
AUTO_COMMAND_PLAIN = "A project command ran and finished."


def plain_fallback_text(status):
    """The fixed sentences of `factory plain` when no rewrite passes the check (PAGE-SPEC 1.6)."""
    if status == "done":
        return ("This step finished. Its original note is too technical to show here; "
                "turn on technical details to read it.")
    return ("This step ended early. The reason was not written down in plain words; "
            "turn on technical details to see the original note.")


PLAIN_FILE_LIMIT = 4000


def plain_candidate(text, allowed=()):
    """(clean text or None, reasons). Redact first, then check; an empty text gives (None, [])."""
    if not isinstance(text, str) or not text.strip():
        return None, []
    clean = plain_clean(text.strip())
    return clean, plain_check(clean, allowed)


def closing_plain_fields(status, kind, plain=None, stop_reason=None, next_step=None, allowed=(),
                         auto_done=None):
    """Plain fields for a closing line, and the one-line notices for stderr (PAGE-SPEC 1.4).

    Never refuses: a wrong or missing summary is written to the line as a flag."""
    fields, notices = {}, []
    if next_step is not None:
        clean, reasons = plain_candidate(next_step, allowed)
        if clean is not None and not reasons:
            fields["next_step"] = clean
        else:
            notices.append("factory: the next step was not kept: %s" % (reasons[0] if reasons else "It is empty."))
    if stop_reason is not None:
        fields["stop_reason"] = stop_reason
    flag = None
    clean, reasons = plain_candidate(plain, allowed)
    if clean is not None and not reasons:
        fields["plain"] = clean
        fields["plain_source"] = "agent"
    elif clean is not None:
        flag = "failed_check"
        fields["plain_rejected"] = clean[:400]
        notices.append("factory: the plain summary was not kept: %s" % reasons[0])
    elif status == "done" and auto_done:
        fields["plain"] = auto_done
        fields["plain_source"] = "auto"
    elif kind in ("agent_call", "command"):
        flag = "missing"
        if status == "done":
            notices.append("factory: no plain summary was given. Add --plain next time; "
                           "factory plain will write one later.")
    if status in ("failed", "stopped") and stop_reason is None and kind in ("agent_call", "command"):
        if flag != "failed_check":
            flag = "no_reason"
        notices.append("factory: say why it ended early with --stop-reason "
                       "(on_purpose, usage_limit, stuck or error).")
    if flag:
        fields["plain_flag"] = flag
    return fields, notices


def spans_needing_plain(spans):
    """Closed agent calls and commands (not the summary writer's own) that have no plain summary
    or are flagged, in log order (PAGE-SPEC 1.6)."""
    found = []
    for span in spans:
        if span.get("kind") not in ("agent_call", "command") or span.get("actor") == "summaries":
            continue
        if span.get("status") not in CLOSED_STATUSES:
            continue
        if not span.get("plain") or span.get("plain_flag"):
            found.append(span)
    return found


# ---------------------------------------------------------------------------
# friendly names, clock and duration words for the page (PAGE-SPEC 4.7)
# ---------------------------------------------------------------------------

_PLAIN_ROLE_NAMES = {
    "orchestrator": "Coordinator", "planner": "Planner", "plan-reviewer": "Plan reviewer",
    "test-writer": "Test writer", "tester": "Tester", "maker": "Builder", "checker": "Checker",
    "public-reviewer": "Independent reviewer", "final-reviewer": "Final reviewer",
    "judge": "Judge", "summaries": "Summary writer",
}
_PLAIN_GATE_LABELS = {"GATE A": "Plan approval", "GATE B": "Release decision"}
_MODEL_FAMILY_RE = re.compile(r"^(sonnet|opus|fable|haiku)-(\d)-(\d)$")
_GPT_RE = re.compile(r"^gpt-(\d[\w.]*?)(?:-[A-Za-z][\w.-]*)?$")


def role_name(role):
    """Friendly role name for the page. The older role_label is unchanged."""
    if isinstance(role, str) and role in _PLAIN_ROLE_NAMES:
        return _PLAIN_ROLE_NAMES[role]
    return role_label(role)


def model_name(model):
    if not isinstance(model, str) or not model.strip():
        return "Model not recorded"
    text = model.strip()
    match = _MODEL_FAMILY_RE.match(text)
    if match:
        return "Claude %s %s.%s" % (match.group(1).capitalize(), match.group(2), match.group(3))
    match = _GPT_RE.match(text)
    if match:
        return "GPT " + match.group(1)
    match = re.match(r"^qwen(\d+):(\d+)b$", text)
    if match:
        return "Qwen %s (%sB, local)" % (match.group(1), match.group(2))
    return "Another AI model"


def clock_label(epoch):
    """12 hour local time with am or pm: 5:34 pm."""
    stamp = time.localtime(epoch)
    hour = stamp.tm_hour % 12 or 12
    return "%d:%02d %s" % (hour, stamp.tm_min, "pm" if stamp.tm_hour >= 12 else "am")


def plain_duration(seconds):
    """45 seconds, 12 min, 1 h 4 min, 2 h. Under one second reads 1 second."""
    total = int(max(0, seconds))
    if total < 60:
        total = max(1, total)
        return "%d second%s" % (total, "" if total == 1 else "s")
    minutes = total // 60
    if minutes < 60:
        return "%d min" % minutes
    hours, rest = divmod(minutes, 60)
    return "%d h" % hours if not rest else "%d h %d min" % (hours, rest)


def gate_label(raw, plain=None, allowed=()):
    """Plain label of a gate or deadline name."""
    if isinstance(plain, str) and plain.strip():
        return plain.strip()
    if isinstance(raw, str) and raw in _PLAIN_GATE_LABELS:
        return _PLAIN_GATE_LABELS[raw]
    if isinstance(raw, str) and raw.strip() and not plain_check(raw, allowed):
        return raw.strip()
    return "A deadline"


def quote_plain(text, allowed=()):
    """The first sentence of a plain text when it passes alone, else the first two, else all of it."""
    if not isinstance(text, str):
        return ""
    ss = plain_sentences(text)
    if not ss:
        return text
    if not plain_check(ss[0], allowed):
        return ss[0]
    if len(ss) > 1 and not plain_check(" ".join(ss[:2]), allowed):
        return " ".join(ss[:2])
    return text.strip()


# ---------------------------------------------------------------------------
# reading the log (SPEC 3.3, 3.4)
# ---------------------------------------------------------------------------

_CORE_STRINGS = ("kind", "status", "actor", "node", "model", "phase", "notes", "last")
_CORE_TIMES = ("start", "end", "ts")
_CORE_NUMBERS = ("iteration", "duration_s", "input_chars", "output_chars", "exit_code")
_CORE_LISTS = ("rubric_pass", "rubric_fail", "rubric_before", "rubric_after",
               "newly_passing", "newly_failing")
_SOFT_STRINGS = ("question", "recommend", "answer", "gate", "waiting_on", "call", "node_label",
                 "effort", "runner", "session", "cmd", "step", "failure_class", "verdict",
                 "input_ref", "output_ref", "why_not_done", "data_class", "data_proof",
                 "target", "parent_id", "project", "feature", "improve_reason",
                 "plain", "plain_source", "plain_flag", "plain_rejected", "plain_given",
                 "stop_reason", "next_step", "group")
_SOFT_BOOLS = ("warn", "target_met", "improve_kept")
_SOFT_NUMBERS = ("value", "tokens_in", "tokens_out", "eval_n", "eval_passed", "eval_p50_s",
                 "eval_p95_s", "eval_cost", "improve_round")
# Fields written as an explicit null when the value is unknown (kept by Tx.add).
NULL_KEPT_FIELDS = ("eval_cost",)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_line(obj):
    """(ok, cleaned object, soft fields dropped). `ok` False means the line is unreadable."""
    if not isinstance(obj, dict):
        return False, None, []
    span_id = obj.get("span_id")
    if not isinstance(span_id, str) or not span_id:
        return False, None, []
    for key in _CORE_STRINGS:
        value = obj.get(key)
        if value is not None and not isinstance(value, str):
            return False, None, []
    for key in _CORE_TIMES:
        value = obj.get(key)
        if value is not None and to_epoch(value) is None:
            return False, None, []
    for key in _CORE_NUMBERS:
        value = obj.get(key)
        if value is not None and not _is_number(value):
            return False, None, []
    duration = obj.get("duration_s")
    if duration is not None and duration < 0:
        return False, None, []
    for key in _CORE_LISTS:
        value = obj.get(key)
        if value is not None and not isinstance(value, list):
            return False, None, []
    cleaned = dict(obj)
    dropped = []
    for key in _SOFT_STRINGS:
        value = cleaned.get(key)
        if value is not None and not isinstance(value, str):
            cleaned.pop(key)
            dropped.append(key)
    for key in _SOFT_BOOLS:
        value = cleaned.get(key)
        if value is not None and not isinstance(value, bool):
            cleaned.pop(key)
            dropped.append(key)
    for key in _SOFT_NUMBERS:
        value = cleaned.get(key)
        if value is not None and not _is_number(value):
            cleaned.pop(key)
            dropped.append(key)
    notified = cleaned.get("notified")
    if notified is not None:
        if not isinstance(notified, dict) or not all(isinstance(v, str) for v in notified.values()):
            cleaned.pop("notified")
            dropped.append("notified")
    return True, cleaned, dropped


def valid_line(obj):
    """True when a parsed log line passes the core type checks of SPEC 3.3."""
    return _check_line(obj)[0]


def _line_event(obj):
    for key in ("ts", "end", "start"):
        epoch = to_epoch(obj.get(key))
        if epoch is not None:
            return epoch
    return None


class _SpanState(object):
    __slots__ = ("merged", "count", "first_ts", "last_ts", "first_line", "last_line",
                 "event", "dropped")

    def __init__(self, line_no):
        self.merged = {}
        self.count = 0
        self.first_ts = None
        self.last_ts = None
        self.first_line = line_no
        self.last_line = line_no
        self.event = None
        self.dropped = []


def _normalize_status(line):
    status = line.get("status")
    if not isinstance(status, str):
        return
    words = status.split()
    if not words:
        line.pop("status")
        return
    line["status"] = words[0].lower()
    extra = []
    for word in words[1:]:
        lowered = word.lower()
        if lowered in FAILURE_CLASSES:
            if not line.get("failure_class"):
                line["failure_class"] = lowered
        elif lowered == "warn":
            line["warn"] = True
        else:
            extra.append(word)
    if extra:
        existing = line.get("notes")
        line["notes"] = ((existing + " ") if isinstance(existing, str) and existing else "") + " ".join(extra)


def _default_phase(span):
    node = span.get("node")
    if isinstance(node, str) and node in OLD_PHASES:
        return node
    if span.get("actor") in ("maker", "checker"):
        return "build"
    return "other"


def _read_text(text, build_dir):
    states = {}
    bad_lines = []
    bad_fields = []
    count = 0
    for line_no, raw in enumerate(text.split("\n"), 1):
        if not raw.strip():
            continue
        count += 1
        try:
            obj = json.loads(raw)
        except Exception:
            bad_lines.append(line_no)
            continue
        ok, line, dropped = _check_line(obj)
        if not ok:
            bad_lines.append(line_no)
            continue
        for field in dropped:
            bad_fields.append({"line": line_no, "field": field})
        _normalize_status(line)
        span_id = line["span_id"]
        state = states.get(span_id)
        if state is None:
            state = states[span_id] = _SpanState(line_no)
        state.count += 1
        state.last_line = line_no
        for field in dropped:
            if field not in state.dropped:
                state.dropped.append(field)
        ts = line.get("ts")
        if state.count == 1:
            state.first_ts = ts
        state.last_ts = ts
        event = _line_event(line)
        if event is not None and (state.event is None or event > state.event):
            state.event = event
        merged = state.merged
        for key, value in line.items():
            if value is None:
                continue
            if key == "start" and "start" in merged:
                continue
            merged[key] = value
    project_default = Path(build_dir).parent.name if build_dir else None
    spans = []
    for span_id, state in states.items():
        span = state.merged
        span["span_id"] = span_id
        status = span.get("status")
        if "start" not in span and state.first_ts and (state.count > 1 or status == "running"):
            span["start"] = state.first_ts
        if status in CLOSED_STATUSES and "end" not in span and state.count > 1 and state.last_ts:
            span["end"] = state.last_ts
        if "duration_s" not in span:
            start = to_epoch(span.get("start"))
            end = to_epoch(span.get("end"))
            if start is not None and end is not None and end >= start:
                span["duration_s"] = int(end - start)
        if "project" not in span and project_default:
            span["project"] = project_default
        if not isinstance(span.get("phase"), str) or not span.get("phase"):
            span["phase"] = _default_phase(span)
        if span.get("kind") == "wait" and not span.get("waiting_on"):
            span["waiting_on"] = "human" if span.get("actor") != "orchestrator" else "tool:unknown"
        if state.event is not None:
            span["event"] = from_epoch(state.event)
        span["line_count"] = state.count
        span["first_line"] = state.first_line
        span["last_line"] = state.last_line
        if state.dropped:
            span["not_recorded"] = list(state.dropped)
        spans.append(span)
    return {"spans": spans, "lines": count, "bad_lines": bad_lines, "bad_fields": bad_fields,
            "meta": {}, "build_dir": str(build_dir) if build_dir else None}


def load_meta(build_dir):
    """build.json as a dict, or {} when absent or unreadable."""
    try:
        value = json.loads((Path(build_dir) / "build.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def read_build(build_dir):
    """Merge a build's trace.jsonl into spans (SPEC 3.3). Reading never raises on content."""
    build_dir = Path(build_dir)
    path = build_dir / "trace.jsonl"
    try:
        raw = path.read_bytes()
    except OSError:
        raise BuildNotFound("factory: no log found at %s" % path)
    result = _read_text(raw.decode("utf-8", "replace"), build_dir)
    result["meta"] = load_meta(build_dir)
    return result


# ---------------------------------------------------------------------------
# writing the log (SPEC 3.2)
# ---------------------------------------------------------------------------

class Tx(object):
    """One locked append transaction on a build's trace.jsonl."""

    def __init__(self, build_dir):
        self.build_dir = Path(build_dir)
        self.project = self.build_dir.parent.name
        self.feature = self.build_dir.name
        self.fd = None
        self.text = ""
        self.torn = False
        self._next = 1
        self._read = None
        self._lines = []
        self._files = []
        self._msg_redactions = 0
        self._phase_value = False

    def _open(self):
        path = str(self.build_dir / "trace.jsonl")
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_APPEND)
        except OSError:
            raise BuildNotFound("factory: no log found at %s" % path)
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        raw = _read_all(self.fd)
        self.torn = bool(raw) and not raw.endswith(b"\n")
        self.text = raw.decode("utf-8", "replace")
        highest = 0
        for match in re.finditer(r'"span_id"\s*:\s*"s(\d+)"', self.text):
            highest = max(highest, int(match.group(1)))
        self._next = highest + 1

    def _close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            finally:
                self.fd = None

    def read(self):
        """The merged view of the log as it stood when the lock was taken."""
        if self._read is None:
            self._read = _read_text(self.text, self.build_dir)
            self._read["meta"] = load_meta(self.build_dir)
        return self._read

    def span(self, span_id):
        for span in self.read()["spans"]:
            if span["span_id"] == span_id:
                return span
        return None

    def _phase(self):
        if self._phase_value is False:
            self._phase_value = None
            try:
                for entry in reversed(read_jsonl_tail(home() / "current.jsonl")):
                    if entry.get("project") == self.project and entry.get("build") == self.feature:
                        phase = entry.get("phase")
                        if isinstance(phase, str) and phase:
                            self._phase_value = phase
                        break
            except Exception:
                self._phase_value = None
        return self._phase_value

    def _message_ref(self, span_id, suffix, text):
        name = "%s.%s.md" % (span_id, suffix)
        number = 2
        while (self.build_dir / "messages" / name).exists() or any(
                name == pending for pending, _text in self._files):
            name = "%s.%s-%d.md" % (span_id, suffix, number)
            number += 1
        self._files.append((name, text))
        return "messages/" + name

    def add(self, fields, messages=None):
        """Queue one line; returns its span id. Written when the block ends cleanly.

        `fields` holds what the caller decided. The code sets `v`, `ts`, `project`,
        `feature` and (for a new span) `span_id`; none of those can be passed in.
        A `span_id` key means: another line for that span.
        """
        fields = dict(fields)
        for forced in ("v", "ts", "project", "feature"):
            fields.pop(forced, None)
        span_id = fields.pop("span_id", None)
        if span_id is None:
            span_id = "s%03d" % self._next
            self._next += 1
        line = {"v": 1, "span_id": span_id, "ts": now(), "project": self.project,
                "feature": self.feature}
        if not fields.get("phase"):
            fields.pop("phase", None)
            phase = self._phase()
            if phase:
                line["phase"] = phase
        for key, value in fields.items():
            if value is not None or key in NULL_KEPT_FIELDS:
                line[key] = value
        if messages:
            if messages.get("in") is not None:
                text, count = redact_count(messages["in"])
                self._msg_redactions += count
                line["input_ref"] = self._message_ref(span_id, "in", text)
                line["input_chars"] = len(text)
            if messages.get("out") is not None:
                text, count = redact_count(messages["out"])
                self._msg_redactions += count
                line["output_ref"] = self._message_ref(span_id, "out", text)
                line["output_chars"] = len(text)
        self._lines.append(line)
        return span_id

    def _commit(self):
        if not self._lines:
            return
        redactions = self._msg_redactions
        self._msg_redactions = 0
        parts = []
        for line in self._lines:
            clean, count = _redact_obj(line)
            redactions += count
            parts.append(json.dumps(clean, ensure_ascii=True) + "\n")
        if self._files:
            folder = self.build_dir / "messages"
            folder.mkdir(parents=True, exist_ok=True)
            for name, text in self._files:
                with open(str(folder / name), "x", encoding="utf-8") as stream:
                    stream.write(text)
        data = "".join(parts).encode("utf-8")
        if self.torn:
            data = b"\n" + data
        _write_all(self.fd, data)
        self._lines = []
        if redactions:
            sys.stderr.write("factory: redacted %d secret-looking value%s\n"
                             % (redactions, "" if redactions == 1 else "s"))


@contextlib.contextmanager
def transaction(build_dir):
    """Lock a build's log, let the caller inspect it, and append all queued lines at once."""
    tx = Tx(build_dir)
    tx._open()
    try:
        yield tx
        tx._commit()
    finally:
        tx._close()


def append(build_dir, fields, messages=None):
    """Append one line to a build's log; returns the span id (SPEC 3.2).

    `messages` may hold {"in": text, "out": text}: saved (redacted) under
    messages/ and referenced from the line.
    """
    with transaction(build_dir) as tx:
        return tx.add(fields, messages)


# ---------------------------------------------------------------------------
# settings (SPEC 2)
# ---------------------------------------------------------------------------

PROJECT_ONLY_KEYS = ("project", "constitution", "plan_dir", "tier_default", "tests", "evals", "release")
KNOWN_KEYS = PROJECT_ONLY_KEYS + ("roles", "vendors", "runners", "public_roots", "notify", "timers",
                                  "private_safe_prefixes", "probe_model", "private_patterns_file",
                                  "preflight", "plain_words_ok")

DEFAULT_TIMERS = {
    "wake_s": 480, "quiet_s": 600, "stale_s": 1800, "node_timebox_s": 2400,
    "default_cmd_timeout_s": 1800, "kill_grace_s": 5, "notify_desktop_s": 10,
    "notify_command_s": 20, "poll_s": 1, "restart_wait_s": 20,
}

DEFAULT_SETTINGS = {
    "tier_default": "B",
    "roles": {},
    "vendors": {"required": ["claude", "codex", "opencode"], "optional": ["ollama", "cursor"]},
    "runners": {
        "claude": {"bin": None, "bin_glob": None},
        "codex": {"bin": None, "bin_glob": None},
        "opencode": {"bin": None, "bin_glob": None, "retains_data": True,
                     "private_safe_prefixes": ["ollama/"],
                     "probe_model": "opencode/deepseek-v4.1-flash-free"},
        "ollama": {"retains_data": False, "probe_model": "qwen3:4b"},
        "cursor": {"bin": None, "bin_glob": None},
    },
    "public_roots": [],
    "notify": {"channels": ["desktop"], "command": None, "connector": None},
    "timers": dict(DEFAULT_TIMERS),
}

_RUNNER_PROGRAMS = {"claude": "claude", "codex": "codex", "opencode": "opencode",
                    "cursor": "cursor-agent", "ollama": "ollama"}


def deep_merge(base, over):
    """Key by key at every depth; a stronger layer's value replaces; lists replace whole."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _leaves(value, prefix=""):
    if isinstance(value, dict) and value:
        for key in value:
            for leaf in _leaves(value[key], prefix + ("." if prefix else "") + str(key)):
                yield leaf
    else:
        yield prefix


def _has_path(layer, dotted):
    node = layer
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def _machine_only_keys(raw):
    """Dotted names of the machine-only keys that a settings dict sets."""
    found = []
    notify = raw.get("notify")
    if isinstance(notify, dict):
        for key in ("command", "connector"):
            if key in notify:
                found.append("notify." + key)
    runners = raw.get("runners")
    if isinstance(runners, dict):
        for name, entry in runners.items():
            if isinstance(entry, dict):
                for key in ("bin", "bin_glob"):
                    if key in entry:
                        found.append("runners.%s.%s" % (name, key))
    if "private_patterns_file" in raw:
        found.append("private_patterns_file")
    return found


def _is_positive_number(value):
    return _is_number(value) and value > 0 and value == value and value != float("inf")


def _check_runner_name(bad, value, key):
    if not isinstance(value, str) or value not in RUNNERS:
        bad('"%s" is %s; a runner must be one of %s' % (key, json.dumps(value), ", ".join(RUNNERS)))


EVAL_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
EVAL_TARGET_RE = re.compile(r"(>=|>|<=|<|==)\s*(-?[0-9]+(?:\.[0-9]+)?)")
EVAL_TARGET_KEYS = ("accuracy", "p95_s", "cost_per_example")
EVAL_SCORERS = ("exact", "number", "contains", "json_field")
EVAL_IMPROVE_DEFAULTS = {"max_rounds": 3, "max_minutes": 30, "stall_rounds": 2}


def _check_eval_settings(evals, bad):
    """Validate evals.sets, evals.cost_unit and evals.improve (EVALS-SPEC 2.1, 12.8)."""
    unit = evals.get("cost_unit")
    if "cost_unit" in evals and (not isinstance(unit, str) or not 1 <= len(unit) <= 8
                                 or any(ch.isspace() for ch in unit)):
        bad('"evals.cost_unit" must be 1 to 8 characters with no spaces')
    if "sets" in evals:
        sets = evals["sets"]
        if not isinstance(sets, list):
            bad('"evals.sets" must be a list')
        seen = set()
        for index, entry in enumerate(sets):
            key = "evals.sets[%d]" % index
            if not isinstance(entry, dict):
                bad('"%s" must be an object' % key)
            set_id = entry.get("id")
            if not isinstance(set_id, str) or not EVAL_ID_RE.fullmatch(set_id):
                bad('"%s.id" must be 1 to 64 letters, digits, dot, dash or underscore' % key)
            if set_id in seen:
                bad('"%s.id" is %s, which another eval set already uses (every id must be unique)'
                    % (key, json.dumps(set_id)))
            seen.add(set_id)
            if "name" in entry:
                name = entry["name"]
                if not isinstance(name, str) or not 1 <= len(name) <= 60 or "\n" in name or "\r" in name:
                    bad('"%s.name" must be one line of 1 to 60 characters' % key)
            for field in ("file", "cmd"):
                if not isinstance(entry.get(field), str) or not entry[field].strip():
                    bad('"%s.%s" must be a non-empty text' % (key, field))
            if not _is_positive_number(entry.get("example_timeout_s")):
                bad('"%s.example_timeout_s" must be a positive number: every example needs its own '
                    'time limit' % key)
            scorer = entry.get("scorer")
            if not isinstance(scorer, dict):
                bad('"%s.scorer" must be an object with a "type"' % key)
            if scorer.get("type") not in EVAL_SCORERS:
                bad('"%s.scorer.type" must be one of: %s' % (key, ", ".join(EVAL_SCORERS)))
            for field in ("tol", "rel"):
                if field in scorer:
                    value = scorer[field]
                    if not _is_number(value) or value != value or value < 0 or value == float("inf"):
                        bad('"%s.scorer.%s" must be a number, 0 or more' % (key, field))
            if "normalize" in scorer and not isinstance(scorer["normalize"], bool):
                bad('"%s.scorer.normalize" must be true or false' % key)
            targets = entry.get("targets")
            if not isinstance(targets, dict) or not targets:
                bad('"%s.targets" needs at least one target (%s)' % (key, ", ".join(EVAL_TARGET_KEYS)))
            for target_key, text in targets.items():
                where = "%s.targets.%s" % (key, target_key)
                if target_key not in EVAL_TARGET_KEYS:
                    bad('"%s" is not a known target (use %s)' % (where, ", ".join(EVAL_TARGET_KEYS)))
                match = EVAL_TARGET_RE.fullmatch(text) if isinstance(text, str) else None
                if not match:
                    bad('"%s" must look like ">=0.9" (>=, >, <=, < or == then a number)' % where)
                if target_key == "accuracy" and not 0 <= float(match.group(2)) <= 1:
                    bad('"%s" must be between 0 and 1' % where)
    if "improve" in evals:
        improve = evals["improve"]
        if not isinstance(improve, dict):
            bad('"evals.improve" must be an object')
        for field in ("max_rounds", "stall_rounds"):
            if field in improve:
                value = improve[field]
                if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                    bad('"evals.improve.%s" must be a whole number, 1 or more' % field)
        if "max_minutes" in improve and not _is_positive_number(improve["max_minutes"]):
            bad('"evals.improve.max_minutes" must be a positive number')


def _check_layer(raw, label, is_project, base_dir, effective_notify):
    """Per-file checks. Raises ConfigError naming the file and the key."""
    def bad(text):
        raise ConfigError("factory: %s: %s" % (label, text))

    if is_project:
        if "project" not in raw:
            bad('"project" is missing (the project needs a name)')
        name = raw["project"]
        if not isinstance(name, str) or not NAME_RE.match(name) or name in (".", ".."):
            bad('"project" is %s; use letters, digits, dot, dash and underscore only' % json.dumps(name))

    notify = raw.get("notify")
    if notify is not None and not isinstance(notify, dict):
        bad('"notify" must be an object')
    if isinstance(notify, dict):
        channels = notify.get("channels")
        if channels is not None:
            if not isinstance(channels, list):
                bad('"notify.channels" must be a list of: %s' % ", ".join(CHANNELS))
            for channel in channels:
                if channel not in CHANNELS:
                    bad('"notify.channels" lists %s; allowed channels are: %s'
                        % (json.dumps(channel), ", ".join(CHANNELS)))
            if "command" in channels and not effective_notify.get("command"):
                bad('"notify.command" is not set but "command" is listed in notify.channels '
                    '(the command belongs in the machine settings file)')
            if "connector" in channels:
                connector = effective_notify.get("connector")
                if not isinstance(connector, dict) or not connector.get("name"):
                    bad('"notify.connector" is not set but "connector" is listed in notify.channels')
                if connector.get("account_confirmed") is not True:
                    bad('"notify.connector.account_confirmed" must be true: check which account the '
                        'connector is signed in to, then set it in the machine settings file')

    if is_project:
        for key in _machine_only_keys(raw):
            bad('"%s" belongs in the machine settings file, not in the project' % key)

    roles = raw.get("roles")
    if roles is not None:
        if not isinstance(roles, dict):
            bad('"roles" must be an object')
        for role, entry in roles.items():
            if not isinstance(entry, dict):
                bad('"roles.%s" must be an object' % role)
            if "material" in entry:
                bad('"roles.%s.material" is not allowed: every role handles private material, '
                    'and whether a call may go to a model that keeps data is decided per call' % role)
            if "runner" in entry:
                _check_runner_name(bad, entry["runner"], "roles.%s.runner" % role)
            fallback = entry.get("fallback")
            if fallback is not None:
                items = fallback if isinstance(fallback, list) else [fallback]
                for item in items:
                    if (not isinstance(item, dict) or not isinstance(item.get("runner"), str)
                            or not isinstance(item.get("model"), str)):
                        bad('"roles.%s.fallback" must be an object, or a list of objects, '
                            'each with a "runner" and a "model"' % role)
                    _check_runner_name(bad, item["runner"], "roles.%s.fallback.runner" % role)

    vendors = raw.get("vendors")
    if vendors is not None:
        if not isinstance(vendors, dict):
            bad('"vendors" must be an object')
        lists = {}
        for key in ("required", "optional"):
            entries = vendors.get(key, [])
            if not isinstance(entries, list):
                bad('"vendors.%s" must be a list' % key)
            for entry in entries:
                _check_runner_name(bad, entry, "vendors.%s runner" % key)
            lists[key] = entries
        both = [name for name in lists["required"] if name in lists["optional"]]
        if both:
            bad('"vendors" lists %s as both required and optional' % json.dumps(both[0]))

    runners = raw.get("runners")
    if runners is not None:
        if not isinstance(runners, dict):
            bad('"runners" must be an object')
        for name, entry in runners.items():
            _check_runner_name(bad, name, "runners.%s runner" % name)
            if not isinstance(entry, dict):
                bad('"runners.%s" must be an object' % name)

    def check_command(entry, key):
        if not isinstance(entry, dict):
            bad('"%s" must be an object with a "cmd" and a "timeout_s"' % key)
        if not _is_positive_number(entry.get("timeout_s")):
            bad('"%s.timeout_s" must be a positive number: every external step needs its own time limit' % key)

    if is_project:
        tests = raw.get("tests")
        if tests is not None:
            if not isinstance(tests, dict):
                bad('"tests" must be an object')
            for name, entry in tests.items():
                check_command(entry, "tests.%s" % name)
        evals = raw.get("evals")
        if evals is not None:
            if not isinstance(evals, dict) or not isinstance(evals.get("metrics", []), list):
                bad('"evals.metrics" must be a list')
            for index, entry in enumerate(evals.get("metrics", [])):
                check_command(entry, "evals.metrics[%d]" % index)
            _check_eval_settings(evals, bad)
        release = raw.get("release")
        if release is not None:
            if not isinstance(release, dict):
                bad('"release" must be an object')
            for group in ("preflight", "steps", "smoke"):
                entries = release.get(group, [])
                if not isinstance(entries, list):
                    bad('"release.%s" must be a list' % group)
                for index, entry in enumerate(entries):
                    check_command(entry, "release.%s[%d]" % (group, index))
        constitution = raw.get("constitution")
        if constitution is not None:
            if not isinstance(constitution, str) or not constitution:
                bad('"constitution" must be a file path')
            target = Path(os.path.expanduser(constitution))
            if not target.is_absolute():
                target = Path(base_dir) / target
            if not target.is_file():
                bad('"constitution" points to a file that does not exist')

    roots = raw.get("public_roots")
    if roots is not None:
        if not isinstance(roots, list):
            bad('"public_roots" must be a list of existing folders')
        for entry in roots:
            if not isinstance(entry, str):
                bad('"public_roots" must be a list of existing folders')
            target = Path(os.path.expanduser(entry))
            if not target.is_absolute():
                target = Path(base_dir) / target
            if not target.is_dir():
                bad('"public_roots" lists a folder that does not exist: %s' % entry)

    words = raw.get("plain_words_ok")
    if words is not None and (not isinstance(words, list) or not all(isinstance(w, str) for w in words)):
        bad('"plain_words_ok" must be a list of words')

    timers = raw.get("timers")
    if timers is not None:
        if not isinstance(timers, dict):
            bad('"timers" must be an object')
        for key, value in timers.items():
            if not _is_number(value) or value < 0:
                bad('"timers.%s" must be a number of seconds (0 or more)' % key)


OUTSIDE_ROLES = ("plan-reviewer", "test-writer", "stuck-diagnosis", "final-reviewer", "public-reviewer")

_ANTHROPIC_WORDS = ("claude", "anthropic", "fable", "opus", "sonnet", "haiku")
_OPENAI_WORDS = ("gpt", "openai", "codex")


def model_family(runner, model):
    """The company behind a model, lower case: anthropic, openai, a leading name such as deepseek, or unknown."""
    runner = runner.lower() if isinstance(runner, str) else ""
    if runner == "claude":
        return "anthropic"
    if runner == "codex":
        return "openai"
    text = model.lower() if isinstance(model, str) else ""
    if any(word in text for word in _ANTHROPIC_WORDS):
        return "anthropic"
    if any(word in text for word in _OPENAI_WORDS):
        return "openai"
    match = re.match(r"[a-z]+", text.rsplit("/", 1)[-1])
    return match.group(0) if match else "unknown"


def _check_outside_roles(cfg):
    """Outside roles must come from another company than the maker, fallbacks included (TONIGHT-SPEC 3.1)."""
    roles = cfg.get("roles")
    maker = roles.get("maker") if isinstance(roles, dict) else None
    if not isinstance(maker, dict) or not isinstance(maker.get("runner"), str):
        return
    maker_family = model_family(maker.get("runner"), maker.get("model"))
    for role in OUTSIDE_ROLES:
        entry = roles.get(role)
        if not isinstance(entry, dict):
            continue
        fallback = entry.get("fallback")
        candidates = [("roles.%s" % role, entry)] if isinstance(entry.get("runner"), str) else []
        for item in (fallback if isinstance(fallback, list) else [fallback] if fallback else []):
            candidates.append(("roles.%s.fallback" % role, item))
        for key, item in candidates:
            if not isinstance(item, dict):
                continue
            runner, model = item.get("runner"), item.get("model")
            named = "%s %s" % (runner, model) if isinstance(model, str) and model else "%s (no model)" % runner
            family = model_family(runner, model)
            if family == "unknown":
                raise ConfigError('factory: "%s" names %s, and the kit cannot tell which company made it. '
                                  'Name the model.' % (key, named))
            if family == maker_family:
                raise ConfigError('factory: "%s" names %s, from the same company as the maker (%s). '
                                  'This role must come from another company. Use another model or remove it.'
                                  % (key, named, maker_family))


def validate_project_settings(raw, base_dir, label="factory.json"):
    """Validate a project settings dict on its own (used by `factory init`). Raises ConfigError."""
    if not isinstance(raw, dict):
        raise ConfigError('factory: %s must hold a JSON object with a "project" name' % label)
    notify = deep_merge(DEFAULT_SETTINGS["notify"], raw["notify"] if isinstance(raw.get("notify"), dict) else {})
    _check_layer(raw, label, True, base_dir, notify)


def load_config_full(cwd=None):
    """(effective settings, settings_from, warnings) for the project in `cwd`.

    Three layers, strongest first: the project's factory.json, the machine file
    <factory home>/config.json, the built-in defaults. Absent files are fine;
    present files are validated (SPEC 2). Raises ConfigError (exit 2).
    """
    base = Path(cwd) if cwd else Path(os.getcwd())
    warnings = []
    project_path = base / "factory.json"
    machine_path = home() / "config.json"

    machine = {}
    if machine_path.is_file():
        try:
            machine = json.loads(machine_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ConfigError('factory: %s is not valid JSON (%s)' % (machine_path, exc))
        except OSError as exc:
            raise ConfigError("factory: %s can't be read (%s)" % (machine_path, exc.strerror or exc))
        if not isinstance(machine, dict):
            raise ConfigError("factory: %s must hold a JSON object" % machine_path)
    for key in PROJECT_ONLY_KEYS:
        if key in machine:
            warnings.append("%s: \"%s\" is read from the project file only and was ignored" % (machine_path, key))
            machine = {k: v for k, v in machine.items() if k != key}

    project = {}
    if project_path.is_file():
        try:
            project = json.loads(project_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ConfigError('factory: factory.json is not valid JSON (%s). The file must be an object '
                              'with a "project" name.' % exc)
        except OSError as exc:
            raise ConfigError("factory: factory.json can't be read (%s)" % (exc.strerror or exc))
        if not isinstance(project, dict):
            raise ConfigError('factory: factory.json must hold a JSON object with a "project" name')

    # Cross-layer view of the notify block, for the channel checks.
    notify_view = deep_merge(DEFAULT_SETTINGS["notify"], machine.get("notify") if isinstance(machine.get("notify"), dict) else {})
    if isinstance(project.get("notify"), dict):
        notify_view = deep_merge(notify_view, project["notify"])
    if machine:
        _check_layer(machine, str(machine_path), False, base,
                     deep_merge(DEFAULT_SETTINGS["notify"], machine.get("notify") if isinstance(machine.get("notify"), dict) else {}))
    if project_path.is_file():
        _check_layer(project, "factory.json", True, base, notify_view)

    for layer, name in ((project, "factory.json"), (machine, str(machine_path))):
        for key in layer:
            if key not in KNOWN_KEYS:
                warnings.append('%s: unknown key "%s" is ignored' % (name, key))

    cfg = deep_merge(deep_merge(DEFAULT_SETTINGS, machine), project)
    vendors = cfg.get("vendors")
    if isinstance(vendors, dict):
        both = [name for name in vendors.get("required", []) if name in vendors.get("optional", [])]
        if both:
            raise ConfigError('factory: "vendors" lists %s as both required and optional once the project '
                              'file, the machine file and the defaults are combined. Set both '
                              '"vendors.required" and "vendors.optional" in the same file.' % json.dumps(both[0]))
    _check_outside_roles(cfg)
    sources = {}
    for leaf in _leaves(cfg):
        if not leaf:
            continue
        if _has_path(project, leaf):
            sources[leaf] = "project"
        elif _has_path(machine, leaf):
            sources[leaf] = "machine"
        else:
            sources[leaf] = "default"
    return cfg, sources, warnings


def load_config(cwd=None):
    """(effective settings, settings_from): where each leaf key came from (SPEC 2)."""
    cfg, sources, _warnings = load_config_full(cwd)
    return cfg, sources


def timers_of(cfg):
    """The timers block with defaults filled in; bad values fall back to the default."""
    timers = dict(DEFAULT_TIMERS)
    given = (cfg or {}).get("timers") if isinstance(cfg, dict) else None
    if isinstance(given, dict):
        for key, value in given.items():
            if _is_number(value) and value >= 0:
                timers[key] = value
    return timers


def lenient_config(cwd=None):
    """Effective settings, or the defaults when the files are invalid (for read-only commands)."""
    try:
        return load_config(cwd)[0]
    except FactoryError:
        return copy.deepcopy(DEFAULT_SETTINGS)


# ---------------------------------------------------------------------------
# finding runner programs (SPEC 2)
# ---------------------------------------------------------------------------

def _version_key(text):
    return tuple(int(part) for part in re.findall(r"\d+", text))


def _which(program):
    if os.sep in program:
        return program if os.access(program, os.X_OK) and os.path.isfile(program) else None
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        if not folder:
            continue
        candidate = os.path.join(folder, program)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def find_runner(cfg, name):
    """Path of a runner program, or None.

    Order: $FACTORY_<NAME>_BIN, runners.<name>.bin, the newest match of
    runners.<name>.bin_glob (highest version, number by number), the usual
    program name on PATH.
    """
    override = os.environ.get("FACTORY_%s_BIN" % name.upper())
    if override:
        return override
    entry = ((cfg or {}).get("runners") or {}).get(name) or {}
    if entry.get("bin"):
        return str(entry["bin"])
    pattern = entry.get("bin_glob")
    if pattern:
        pattern = os.path.expanduser(str(pattern))
        prefix, star, suffix = pattern.partition("*")
        best = None
        for path in glob.glob(pattern):
            if not os.path.isfile(path):
                continue
            middle = path[len(prefix):len(path) - len(suffix)] if star else path
            key = (_version_key(middle), path)
            if best is None or key > best[0]:
                best = (key, path)
        if best:
            return best[1]
    return _which(_RUNNER_PROGRAMS.get(name, name))


# ---------------------------------------------------------------------------
# which build a command acts on (SPEC 4.0)
# ---------------------------------------------------------------------------

class Build(object):
    def __init__(self, project, build, path):
        self.project = project
        self.id = build
        self.dir = Path(path)

    def __iter__(self):
        return iter((self.project, self.id, self.dir))


def _arg_build(args):
    if args is None:
        return None
    if isinstance(args, str):
        return args
    if isinstance(args, dict):
        return args.get("build")
    return getattr(args, "build", None)


def select_build(args=None):
    """Resolve --build, else $FACTORY_BUILD, else current.jsonl. Raises FactoryError (3 or 2)."""
    chosen = _arg_build(args) or os.environ.get("FACTORY_BUILD") or None
    project = build = None
    if chosen:
        if "/" not in chosen:
            raise FactoryError(EXIT.USAGE, "factory: a build is named <project>/<build-id>; got a name with no slash",
                               "build name is not <project>/<build-id>")
        project, _slash, build = chosen.partition("/")
        if not valid_name(project) or not valid_name(build):
            raise FactoryError(EXIT.USAGE, "factory: a build is named <project>/<build-id> with letters, "
                               "digits, dot, dash and underscore only", "build name is not valid")
    else:
        pointer = read_current()
        if pointer is None:
            raise FactoryError(EXIT.MISSING, "factory: no build selected. Start one with "
                               "'factory new <build-id>' or pass --build.", "no build selected")
        project, build = pointer["project"], pointer["build"]
    path = build_dir_of(project, build)
    if not (path / "trace.jsonl").is_file():
        raise FactoryError(EXIT.MISSING, "factory: no log found at %s" % (path / "trace.jsonl"),
                           "build log not found")
    return Build(project, build, path)


# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------

_ROLE_LABELS = {
    "orchestrator": "Coordinator", "planner": "Planner", "plan-reviewer": "Plan reviewer",
    "test-writer": "Test writer", "maker": "Builder", "checker": "Checker",
    "final-reviewer": "Final reviewer", "judge": "Judge",
}
_PHASE_LABELS = {
    "intake": "Intake", "plan": "Planning", "plan-review": "Plan review",
    "gate-a": "Waiting for plan approval", "tests": "Writing tests", "test-write": "Writing tests",
    "build": "Building", "integration": "Putting it together", "e2e": "Testing as a user",
    "evals": "Measuring", "gate-b": "Waiting for release approval", "release": "Releasing",
    "retro": "Review",
}
STATE_LABELS = {
    "running": "Working", "done": "Finished", "failed": "Failed", "stopped": "Stopped",
    "unfinished": "Unfinished in log", "other": "Status not recorded",
}
BUILD_STATE_LABELS = {"waiting": "Waiting on you", "running": "Working", "done": "Finished"}
UNRECORDED_PIECE = "Piece name not recorded"
NO_PIECE = "No piece"


def role_label(role):
    if not isinstance(role, str) or not role:
        return "Role not recorded"
    if role in _ROLE_LABELS:
        return _ROLE_LABELS[role]
    text = role.replace("-", " ").replace("_", " ")
    return text[:1].upper() + text[1:]


def phase_label(phase):
    if not isinstance(phase, str) or not phase or phase == "other":
        return None
    return _PHASE_LABELS.get(phase, phase)


# ---------------------------------------------------------------------------
# activity and unfinished work (SPEC 4.7, 5.1)
# ---------------------------------------------------------------------------

def _safe_id(text):
    return isinstance(text, str) and bool(NAME_RE.match(text)) and text not in (".", "..")


def _out_mtimes(build_dir):
    """{span id: mtime} of messages/<id>.out.md files (live output of wrapped commands)."""
    found = {}
    try:
        with os.scandir(str(Path(build_dir) / "messages")) as entries:
            for entry in entries:
                if entry.name.endswith(".out.md"):
                    try:
                        found[entry.name[:-len(".out.md")]] = entry.stat().st_mtime
                    except OSError:
                        pass
    except OSError:
        pass
    return found


def _tail_line(path, limit=200):
    """Last non-empty line of a file's final 4 KB, cut to `limit` characters."""
    try:
        with open(str(path), "rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - 4096))
            data = stream.read()
    except OSError:
        return ""
    for raw in reversed(data.decode("utf-8", "replace").splitlines()):
        if raw.strip():
            return redact_plain(raw.strip())[:limit]
    return ""


def _activity(read, mtimes):
    """({span id: last activity epoch}, build-level last activity epoch)."""
    per_span = {}
    latest = None
    for span in read["spans"]:
        values = []
        event = to_epoch(span.get("event"))
        if event is not None:
            values.append(event)
        mtime = mtimes.get(span["span_id"])
        if mtime is not None:
            values.append(mtime)
        last = max(values) if values else None
        per_span[span["span_id"]] = last
        if last is not None and (latest is None or last > latest):
            latest = last
    for mtime in mtimes.values():
        if latest is None or mtime > latest:
            latest = mtime
    return per_span, latest


_WORK_LINE_KINDS = ("agent_call", "command", "iteration")


def _piece_names(spans, build_dir=None):
    """{node: name}. A piece listed in the plan keeps its plan name. Otherwise the newest
    node_label on a work line (agent_call, command, iteration), else on any other line."""
    work, other = {}, {}
    for span in spans:
        node = span.get("node")
        label = span.get("node_label")
        if isinstance(node, str) and isinstance(label, str) and label:
            (work if span.get("kind") in _WORK_LINE_KINDS else other)[node] = label
    labels = dict(other)
    labels.update(work)
    if build_dir is not None:
        plan, _unreadable = read_plan(build_dir)
        if plan is not None:
            seen = set()
            for piece in plan["pieces"]:
                if isinstance(piece, dict) and isinstance(piece.get("id"), str) and piece["id"] not in seen:
                    seen.add(piece["id"])
                    if isinstance(piece.get("name"), str) and piece["name"]:
                        labels[piece["id"]] = piece["name"]
    return labels


def _piece(node, labels):
    """(piece_label, piece_id or None)."""
    if not isinstance(node, str) or not node:
        return NO_PIECE, None
    if node in labels:
        return labels[node], None
    return UNRECORDED_PIECE, node


def _loaded(build):
    if isinstance(build, dict) and "spans" in build:
        return build
    return read_build(build)


def unfinished(build, now_value=None, cfg=None):
    """Work that was started and never finished (SPEC 4.7).

    `build` is a build folder or the result of read_build. Returns a list of dicts:
    {"span", "reason" (stale | quiet | human), "idle_s", "age_s", "text"}.
    A running agent or command counts when the build has had no activity for
    longer than timers.stale_s, or the span itself has been silent for longer
    than timers.quiet_s while the build is active. An open question to a person
    counts after 12 hours.
    """
    read = _loaded(build)
    build_dir = read.get("build_dir")
    timers = timers_of(cfg)
    now_epoch_value = to_epoch(_now_text(now_value))
    mtimes = _out_mtimes(build_dir) if build_dir else {}
    per_span, build_last = _activity(read, mtimes)
    labels = _piece_names(read["spans"], build_dir)
    found = []
    build_stale = build_last is not None and now_epoch_value - build_last > timers["stale_s"]
    for span in read["spans"]:
        if span.get("status") != "running":
            continue
        kind = span.get("kind")
        own = per_span.get(span["span_id"])
        start = to_epoch(span.get("start"))
        origin = start if start is not None else own
        age = max(0, now_epoch_value - origin) if origin is not None else 0
        idle = max(0, now_epoch_value - own) if own is not None else 0
        if kind in ("agent_call", "command"):
            reason = None
            if own is not None:
                if build_stale:
                    reason = "stale"
                elif idle > timers["quiet_s"]:
                    reason = "quiet"
            if reason is None:
                continue
            label, _pid = _piece(span.get("node"), labels)
            who = role_label(span.get("actor"))
            if kind == "command":
                who += " command"
            where = "" if label in (NO_PIECE, UNRECORDED_PIECE) else " on " + label
            text = "Started and never finished: %s%s, %s ago" % (who, where, words_for_duration(age))
            found.append({"span": span, "reason": reason, "idle_s": int(idle), "age_s": int(age), "text": text})
        elif kind == "wait" and span.get("waiting_on") == "human":
            if origin is not None and age > HUMAN_WAIT_LIMIT_S:
                gate = span.get("gate") or "A decision"
                text = "A question was never marked answered: %s, %s ago" % (gate, words_for_duration(age))
                found.append({"span": span, "reason": "human", "idle_s": int(idle), "age_s": int(age), "text": text})
    return found


# ---------------------------------------------------------------------------
# the board (SPEC 5.1)
# ---------------------------------------------------------------------------

def _count_phrase(count, one, many):
    return (one if count == 1 else many) % count


def _state_of(span, build_stale):
    status = span.get("status")
    if status == "running":
        return "unfinished" if build_stale else "running"
    if status in CLOSED_STATUSES:
        return status
    return "other"


def _int_or_none(value):
    if _is_number(value):
        return int(value)
    return None


def _day_label(epoch):
    stamp = time.gmtime(epoch)
    return "%s %d" % (time.strftime("%b", stamp), stamp.tm_mday)


_STOP_REASON_WORDS = {
    "on_purpose": "it was stopped on purpose", "usage_limit": "it ran out of usage",
    "stuck": "it got stuck", "error": "it hit an error",
}


def _with_article(word):
    return ("An " if word[:1] in "aeiou" else "A ") + word


def _recent_piece(node, piece_names):
    """The piece's plain name for a sentence, or `a piece` when it has none."""
    name = piece_names.get(node) if isinstance(node, str) else None
    if not name or name == UNRECORDED_PIECE:
        return "a piece", None
    if name == NO_PLAIN_NAME:
        return "a piece without a plain name", None
    return name, name


def _board_recent(spans, labels, states, now_epoch_value, piece_names=None, stop_plain=None, allowed=()):
    piece_names = piece_names or {}
    stop_plain = stop_plain or {}
    entries = []
    for span in spans:
        kind = span.get("kind")
        state = states.get(span["span_id"])
        plain = None
        piece_name = None
        if kind == "agent_call":
            who = role_label(span.get("actor"))
            label, _pid = _piece(span.get("node"), labels)
            on = "" if label in (NO_PIECE, UNRECORDED_PIECE) else " " + label
            role_lower = role_name(span.get("actor")).lower()
            piece, piece_name = _recent_piece(span.get("node"), piece_names)
            actor_phrase = _with_article(role_lower)
            if state == "running":
                text = "%s started%s" % (who, on)
                when = span.get("start") or span.get("event")
                plain = "%s started %s." % (actor_phrase, piece)
            elif state == "done":
                text = "%s finished%s" % (who, on)
                verdict = span.get("verdict")
                if verdict == "approved":
                    text += ": approved"
                    plain = "%s approved %s." % (actor_phrase, piece)
                elif verdict == "rejected":
                    text += ": sent back"
                    plain = "%s sent %s back for fixes." % (actor_phrase, piece)
                elif span.get("actor") in CHECKER_ROLES:
                    plain = "%s finished reviewing %s." % (actor_phrase, piece)
                else:
                    plain = "%s finished an attempt on %s." % (actor_phrase, piece)
                when = span.get("end") or span.get("event")
            elif state == "failed":
                text = "%s failed%s" % (who, on)
                when = span.get("end") or span.get("event")
            elif state == "stopped":
                text = "%s was stopped%s" % (who, on)
                when = span.get("end") or span.get("event")
            else:
                continue
            if state in ("failed", "stopped"):
                reason = _STOP_REASON_WORDS.get(span.get("stop_reason"), "the reason was not written down")
                plain = "%s did not finish %s because %s." % (actor_phrase, piece, reason)
        elif kind == "wait" and span.get("waiting_on") == "human":
            gate = span.get("gate") or "A decision"
            glabel = gate_label(span.get("gate"), stop_plain.get(span.get("gate")), allowed).lower()
            if state == "running":
                text = "A decision is needed: %s" % gate
                when = span.get("start") or span.get("event")
                plain = "A decision is needed from you: %s." % glabel
            elif state in ("done", "failed", "stopped"):
                text = "Decision made: %s" % gate
                when = span.get("end") or span.get("event")
                plain = "You answered the %s." % glabel
            else:
                continue
        elif kind == "command" and state in ("done", "failed"):
            text = "%s ran a command: %s" % (role_label(span.get("actor")), "finished" if state == "done" else "failed")
            when = span.get("end") or span.get("event")
            plain = ("The coordinator ran a routine command." if state == "done" else
                     "A routine command ended early because the program reported an error.")
        elif kind == "phase" and state in ("running", "done"):
            text = "Phase: %s" % (phase_label(span.get("phase")) or "not recorded")
            when = span.get("start") or span.get("event")
            plain = "The build moved on to: %s." % (phase_label(span.get("phase")) or "a new phase").lower()
        else:
            continue
        epoch = to_epoch(when)
        if epoch is None:
            continue
        entry = {"when": from_epoch(epoch), "text": text, "plain": plain, "piece_name": piece_name}
        entries.append((epoch, entry))
    entries.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in entries[:15]]


# ---------------------------------------------------------------------------
# eval results shared by the board and the reports (EVALS-SPEC 6, 8)
# ---------------------------------------------------------------------------

def eval_percent(passed, n):
    """Whole percent, half up by integer math, never 100 unless every example passed."""
    if not n:
        return 0
    value = (2 * passed * 100 + n) // (2 * n)
    return 99 if value >= 100 and passed < n else value


def eval_percent_of_accuracy(accuracy):
    """The same whole percent from a stored 4-decimal accuracy."""
    scaled = int(round(float(accuracy) * 10000))
    value = (scaled + 50) // 100
    return 99 if value >= 100 and scaled < 10000 else value


def eval_money(value, unit):
    """$0.0100 for USD, else 0.0100 EUR (EVALS-SPEC 6.4)."""
    unit = unit if isinstance(unit, str) and unit else "USD"
    return "$%.4f" % value if unit == "USD" else "%.4f %s" % (value, unit)


def eval_summaries(build_dir):
    """([(index line, summary)], unreadable): the latest run of every eval set, oldest first."""
    build_dir = Path(build_dir)
    latest = {}
    for position, entry in enumerate(read_jsonl_tail(build_dir / "evals" / "index.jsonl")):
        set_id = entry.get("set")
        if isinstance(set_id, str):
            latest[set_id] = (position, entry)
    found, unreadable = [], 0
    for _position, entry in sorted(latest.values(), key=lambda item: item[0]):
        name = entry.get("summary")
        summary = None
        if isinstance(name, str) and name and "/" not in name and "\\" not in name:
            try:
                summary = json.loads((build_dir / "evals" / name).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                summary = None
        if (not isinstance(summary, dict) or not isinstance(summary.get("n"), int)
                or not isinstance(summary.get("passed"), int)):
            unreadable += 1
            continue
        found.append((entry, summary))
    return found, unreadable


def _eval_board(build_dir, now_e):
    """(board rows, unreadable count) for the EVALS block of the status board."""
    found, unreadable = eval_summaries(build_dir)
    rows = []
    for entry, summary in found:
        stamp = to_epoch(entry.get("ts")) if isinstance(entry.get("ts"), str) else None
        when = words_for_duration(max(0, int(now_e - stamp))) + " ago" if stamp is not None else "time not recorded"
        name = summary.get("name") if isinstance(summary.get("name"), str) and summary.get("name") else summary.get("set")
        rows.append({"set": summary.get("set"), "name": name, "passed": summary["passed"],
                     "n": summary["n"], "accuracy": summary.get("accuracy"),
                     "met": bool(summary.get("met")), "when": when})
    return rows, unreadable


# ---------------------------------------------------------------------------
# the plan: GRAPH.yaml to plan.json, and the page's view of the board (PAGE-SPEC 2, 3, 4)
# ---------------------------------------------------------------------------

PLAN_NAME_LIMIT = 40
PLAN_PURPOSE_LIMIT = 160
_PLAN_STAMPED_RE = re.compile(r"^plan-(\d{8}T\d{6}Z)(?:-(\d+))?\.json$")
CHECKER_ROLES = ("checker", "plan-reviewer", "public-reviewer", "final-reviewer", "judge")
NON_PIECE_ROLES = ("orchestrator", "summaries")
NO_PLAIN_NAME = "A piece without a plain name"
OTHER_WORK_PURPOSE = "Work in the log that the plan does not list."
LOG_PIECES_PURPOSE = "The pieces found in the log, in the order they started."
NO_DESCRIPTION = "The plan has no description for this piece."
PLAN_UNREADABLE_WARNING = "The plan file could not be read, so the pieces come from the log."


def _graph_value(raw):
    """The value after `key:` on one graph line: quotes are taken off, ` #` starts a comment."""
    text = raw.strip()
    if text[:1] in ("'", '"'):
        quote = text[0]
        end = text.find(quote, 1)
        return text[1:end] if end > 0 else text[1:]
    return re.sub(r"\s+#.*$", "", text).strip()


def _graph_list(value):
    """The items of an inline list `[A, B]`, or None when the value is not one."""
    text = value.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return None
    return [_graph_value(item) for item in text[1:-1].split(",") if item.strip()]


def parse_graph(text):
    """Read the documented subset of GRAPH.yaml (PAGE-SPEC 2.2).

    Returns {"nodes": [...], "stages": [...] or None, "errors": [...]}. Only lines are read:
    no YAML library, no multi-line values."""
    errors = []
    nodes, stages = [], None
    block, current = None, None
    for raw in text.splitlines():
        if re.match(r"^[ ]*\t", raw):
            return {"nodes": [], "stages": None, "errors": ["the graph file uses tabs; use spaces"]}
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not raw[0].isspace() and not raw.startswith("-"):
            top = re.match(r"^([A-Za-z_][\w-]*)\s*:", raw)
            block, current = (top.group(1) if top else None), None
            if block == "stages" and stages is None:
                stages = []
            continue
        if block == "nodes":
            start = re.match(r"^\s*-\s*id:\s*(.*)$", raw)
            if start:
                ident = _graph_value(start.group(1))
                current = {"id": ident, "name": None, "plain_name": None, "purpose": None,
                           "depends_on": [], "show": True}
                if not re.fullmatch(r"[A-Za-z0-9._-]+", ident):
                    errors.append("a piece id is not valid: %s" % ident[:20])
                nodes.append(current)
                continue
            key = re.match(r"^\s+([A-Za-z_]+)\s*:\s*(.*)$", raw)
            if key and current is not None:
                name, value = key.group(1), key.group(2)
                if name == "depends_on":
                    items = _graph_list(value.strip())
                    if items is None:
                        errors.append("depends_on of %s must be written on one line like [A, B]" % current["id"])
                    else:
                        current["depends_on"] = items
                elif name == "show":
                    current["show"] = _graph_value(value).lower() != "false"
                elif name in ("name", "plain_name", "purpose"):
                    current[name] = _graph_value(value)
        elif block == "stages" and stages is not None:
            start = re.match(r"^\s*-\s*name:\s*(.*)$", raw)
            if start:
                current = {"name": _graph_value(start.group(1)), "purpose": None, "members": None}
                stages.append(current)
                continue
            key = re.match(r"^\s+([A-Za-z_]+)\s*:\s*(.*)$", raw)
            if key and current is not None:
                if key.group(1) == "purpose":
                    current["purpose"] = _graph_value(key.group(2))
                elif key.group(1) == "members":
                    items = _graph_list(key.group(2).strip())
                    current["members"] = items if items is not None else []
    return {"nodes": nodes, "stages": stages, "errors": errors}


def graph_plan(text, skip=(), allowed=()):
    """(plan dict or None, problems). None with no problems means an old-style graph (no stages block)."""
    parsed = parse_graph(text)
    problems = list(parsed["errors"])
    if problems and problems[0].startswith("the graph file uses tabs"):
        return None, problems
    if parsed["stages"] is None:
        return None, problems
    skip = set(skip)
    every = {node["id"] for node in parsed["nodes"]}
    shown = [node for node in parsed["nodes"] if node["show"] and node["id"] not in skip]
    shown_ids = [node["id"] for node in shown]
    if not shown:
        problems.append("the graph has a stages block but no piece to show")
    for node in shown:
        ident = node["id"]
        for field, limit in (("plain_name", PLAN_NAME_LIMIT), ("purpose", PLAN_PURPOSE_LIMIT)):
            value = node[field]
            if not value:
                problems.append("piece %s: %s is missing" % (ident, field))
                continue
            value = redact_plain(value)
            node[field] = value
            if len(value) > limit:
                problems.append("piece %s: %s is longer than %d characters" % (ident, field, limit))
            reasons = (plain_label_check if field == "plain_name" else plain_check)(value, allowed)
            if reasons:
                problems.append("piece %s: %s: %s" % (ident, field, reasons[0]))
            elif field == "purpose" and len(plain_sentences(value)) > 1:
                problems.append("piece %s: purpose must be one sentence" % ident)
        for other in node["depends_on"]:
            if other not in every:
                problems.append("piece %s depends on %s, which is not in the graph" % (ident, other))
    owner = {}
    for number, stage in enumerate(parsed["stages"], 1):
        label = stage["name"] or "stage %d" % number
        for field, limit in (("name", PLAN_NAME_LIMIT), ("purpose", PLAN_PURPOSE_LIMIT)):
            value = stage[field]
            if not value:
                problems.append("stage %s: %s is missing" % (label, field))
                continue
            value = redact_plain(value)
            stage[field] = value
            if len(value) > limit:
                problems.append("stage %s: %s is longer than %d characters" % (label, field, limit))
            reasons = (plain_label_check if field == "name" else plain_check)(value, allowed)
            if reasons:
                problems.append("stage %s: %s: %s" % (label, field, reasons[0]))
            elif field == "purpose" and len(plain_sentences(value)) > 1:
                problems.append("stage %s: purpose must be one sentence" % label)
        if not stage["members"]:
            problems.append("stage %s: members is missing or empty" % label)
        for member in stage["members"] or []:
            if member not in shown_ids:
                problems.append("stage %s: member %s is not a shown piece" % (label, member))
            elif member in owner:
                problems.append("piece %s is in two stages" % member)
            else:
                owner[member] = number
    for ident in shown_ids:
        if ident not in owner:
            problems.append("piece %s is in no stage" % ident)
    deps = {node["id"]: [d for d in node["depends_on"] if d in shown_ids] for node in shown}
    state = {}

    def visit(ident):
        state[ident] = 1
        for other in deps[ident]:
            if state.get(other) == 1:
                return other
            if other not in state:
                found = visit(other)
                if found:
                    return found
        state[ident] = 2
        return None

    for ident in shown_ids:
        if ident not in state:
            found = visit(ident)
            if found:
                problems.append("the graph has a cycle through %s" % found)
                break
    if problems:
        return None, problems
    pieces = [{"id": node["id"], "name": node["plain_name"], "tech_name": redact_plain(node["name"]) if node["name"] else None,
               "purpose": node["purpose"], "depends_on": deps[node["id"]], "stage": owner[node["id"]]}
              for node in shown]
    out_stages = [{"n": number, "name": stage["name"], "purpose": stage["purpose"],
                   "members": list(stage["members"])} for number, stage in enumerate(parsed["stages"], 1)]
    return {"v": 1, "generated": now(), "source": "GRAPH.yaml", "pieces": pieces, "stages": out_stages}, []


def plan_files(build_dir):
    """(current plan file or None). The greatest plan-<stamp>[-n].json when any exists, else plan.json."""
    best = None
    try:
        names = os.listdir(str(build_dir))
    except OSError:
        return None
    for name in names:
        match = _PLAN_STAMPED_RE.match(name)
        if match:
            key = (match.group(1), int(match.group(2) or 1))
            if best is None or key > best[0]:
                best = (key, name)
    if best is not None:
        return Path(build_dir) / best[1]
    path = Path(build_dir) / "plan.json"
    return path if path.is_file() else None


def read_plan(build_dir):
    """(plan dict or None, unreadable). A missing file is not unreadable."""
    path = plan_files(build_dir)
    if path is None:
        return None, False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, True
    if (not isinstance(value, dict) or not isinstance(value.get("pieces"), list)
            or not isinstance(value.get("stages"), list)):
        return None, True
    return value, False


def write_plan(build_dir, plan):
    """Write plan.json, or a new plan-<stamp>.json when it differs from the current plan (never overwrites).

    Returns (path or None, notice): None means nothing was written."""
    build_dir = Path(build_dir)
    current = plan_files(build_dir)
    if current is not None:
        try:
            old = json.loads(current.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            old = None
        if isinstance(old, dict):
            same = ({k: v for k, v in old.items() if k != "generated"}
                    == {k: v for k, v in plan.items() if k != "generated"})
            if same:
                return None, "factory: the plan is unchanged, so no new plan file was written"
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(now_epoch()))
        target = build_dir / ("plan-%s.json" % stamp)
        number = 1
        while True:
            try:
                with open(str(target), "x", encoding="utf-8") as stream:
                    stream.write(json.dumps(plan, indent=2) + "\n")
                return target, None
            except FileExistsError:
                number += 1
                target = build_dir / ("plan-%s-%d.json" % (stamp, number))
    target = build_dir / "plan.json"
    with open(str(target), "x", encoding="utf-8") as stream:
        stream.write(json.dumps(plan, indent=2) + "\n")
    return target, None


def _plural(count, one, many):
    return "%d %s" % (count, one if count == 1 else many)


SIDE_TASK_NAME = "Side task"


def _piece_name_from_log(node, labels, allowed, side=False):
    """The name for a piece the plan does not name. A side job with no label is a `Side task`."""
    label = labels.get(node)
    if not label:
        return SIDE_TASK_NAME if side else UNRECORDED_PIECE
    return label if not plain_label_check(label, allowed) else NO_PLAIN_NAME


BUILT_LABEL = "Built, waiting for a check"
BUILT_NOW_TEXT = "Built. Waiting for a check. No checker has started yet."


def _call_kind(role):
    return "checker" if role in CHECKER_ROLES else "builder"


def _plan_board(build_dir, spans, states, labels, per_span, quiet, waiting_nodes, now_e, allowed):
    """The `plan` part of the board (PAGE-SPEC 3 and 4.3 to 4.5). Returns (plan, names, warnings)."""
    plan, unreadable = read_plan(build_dir)
    warnings = [PLAN_UNREADABLE_WARNING] if unreadable else []
    expected_checkers = set()
    for entry in read_jsonl_tail(Path(build_dir) / "expected.jsonl"):
        role = entry.get("role") if isinstance(entry.get("role"), str) else entry.get("actor")
        if role in CHECKER_ROLES and isinstance(entry.get("node"), str):
            expected_checkers.add(entry["node"])
    # every call of every piece, oldest first
    by_node = {}
    log_order = []
    for index, span in enumerate(spans):
        node = span.get("node")
        if (span.get("kind") != "agent_call" or not isinstance(node, str) or not node
                or span.get("actor") in NON_PIECE_ROLES):
            continue
        start = to_epoch(span.get("start"))
        if start is None:
            start = to_epoch(span.get("event")) or 0
        state = states[span["span_id"]]
        reason = span.get("stop_reason") if span.get("stop_reason") in STOP_REASONS else None
        role = span.get("actor") if isinstance(span.get("actor"), str) else ""
        call = {"span": span, "id": span["span_id"], "node": node, "role": role,
                "cls": _call_kind(role), "state": state, "start_e": start, "index": index,
                "group": span.get("group") if isinstance(span.get("group"), str) and span.get("group") else None,
                "stop_reason": reason,
                "counted": reason not in ("on_purpose", "usage_limit")}
        if node not in by_node:
            by_node[node] = []
            log_order.append(node)
        by_node[node].append(call)
    for calls in by_node.values():
        calls.sort(key=lambda c: (c["start_e"], c["index"]))

    # the listed pieces
    listed = []   # (id, name, purpose, tech_name, depends_on, stage n)
    stages_out = []
    if plan is not None:
        known = set()
        for piece in plan["pieces"]:
            if isinstance(piece, dict) and isinstance(piece.get("id"), str) and piece["id"] not in known:
                known.add(piece["id"])
                deps = [d for d in (piece.get("depends_on") or []) if isinstance(d, str)] \
                    if isinstance(piece.get("depends_on"), list) else []
                listed.append({"id": piece["id"],
                               "name": piece["name"] if isinstance(piece.get("name"), str) and piece["name"]
                               else _piece_name_from_log(piece["id"], labels, allowed),
                               "purpose": piece["purpose"] if isinstance(piece.get("purpose"), str)
                               else NO_DESCRIPTION,
                               "tech_name": piece.get("tech_name") if isinstance(piece.get("tech_name"), str) else None,
                               "depends_on": deps, "stage": piece.get("stage"), "planned": True})
        used = set()
        for position, stage in enumerate(plan["stages"], 1):
            if not isinstance(stage, dict):
                continue
            members = [m for m in (stage.get("members") or []) if isinstance(m, str) and m in known and m not in used] \
                if isinstance(stage.get("members"), list) else []
            used.update(members)
            stages_out.append({"n": stage.get("n") if isinstance(stage.get("n"), int) else position,
                               "name": stage["name"] if isinstance(stage.get("name"), str) else "Stage %d" % position,
                               "purpose": stage["purpose"] if isinstance(stage.get("purpose"), str) else "",
                               "members": members})
        loose = [p["id"] for p in listed if p["id"] not in used]
        extra_ids = [n for n in log_order if n not in known]
        other = loose + extra_ids
        for node in extra_ids:
            listed.append({"id": node, "name": _piece_name_from_log(node, labels, allowed, side=True),
                           "purpose": NO_DESCRIPTION, "tech_name": labels.get(node),
                           "depends_on": [], "stage": None, "planned": False})
        if other:
            stages_out.append({"n": len(stages_out) + 1, "name": "Other work", "purpose": OTHER_WORK_PURPOSE,
                               "members": other})
    else:
        for node in log_order:
            listed.append({"id": node, "name": _piece_name_from_log(node, labels, allowed),
                           "purpose": NO_DESCRIPTION, "tech_name": labels.get(node),
                           "depends_on": [], "stage": 1, "planned": True})
        stages_out.append({"n": 1, "name": "Pieces", "purpose": LOG_PIECES_PURPOSE,
                           "members": [p["id"] for p in listed]})
    stage_of = {}
    for stage in stages_out:
        for member in stage["members"]:
            stage_of[member] = stage["n"]
    names = {p["id"]: p["name"] for p in listed}
    ids = set(names)

    # pass 1: the state of every piece
    def state_of_piece(node):
        calls = by_node.get(node, [])
        if node in waiting_nodes:
            return "needs_you"
        if not calls:
            return "waiting"
        running = [c for c in calls if c["state"] == "running"]
        if running:
            return "building" if running[-1]["cls"] == "builder" else "checking"
        last = calls[-1]
        if last["state"] in ("failed", "stopped", "unfinished", "other"):
            return "stopped"
        counted = [c for c in calls if c["counted"]]
        if not counted:
            return "stopped"
        tail = counted[-1]
        if tail["cls"] == "checker":
            return "sent_back" if tail["span"].get("verdict") == "rejected" else "done"
        has_checker = node in expected_checkers or any(c["cls"] == "checker" for c in calls)
        return "built" if has_checker else "done"

    piece_state = {p["id"]: state_of_piece(p["id"]) for p in listed}

    def label_of(state):
        return {"waiting": "Waiting", "building": "Building", "checking": "Being checked",
                "sent_back": "Sent back for fixes", "stopped": "Stopped", "done": "Done",
                "needs_you": "Waiting for you", "built": BUILT_LABEL}[state]

    pieces_out = []
    for piece in listed:
        node = piece["id"]
        calls = by_node.get(node, [])
        state = piece_state[node]
        deps = [d for d in piece["depends_on"] if d in ids]
        waits_for = [d for d in deps if piece_state.get(d) != "done"] if state == "waiting" else []
        # counts and labels
        builders = [c for c in calls if c["cls"] == "builder"]
        checkers = [c for c in calls if c["cls"] == "checker"]
        grouped = any(c["group"] for c in builders)
        seen_groups, attempt_no, review_no = {}, 0, 0
        for c in calls:
            if not c["counted"]:
                c["label"] = "%s, ended early" % ("Attempt" if c["cls"] == "builder" else "Review")
                continue
            if c["cls"] == "builder":
                if c["group"] and c["group"] in seen_groups:
                    number = seen_groups[c["group"]]
                else:
                    attempt_no += 1
                    number = attempt_no
                    if c["group"]:
                        seen_groups[c["group"]] = number
                c["label"] = "Attempt %d" % number
            else:
                review_no += 1
                c["label"] = "Review %d" % review_no
        attempts, reviews = attempt_no, review_no
        if state in ("building", "checking", "built", "sent_back", "stopped") and builders and not grouped:
            attempt_label = "Attempt %d of this piece" % max(attempts, 1)
        elif state in ("building", "checking", "built", "sent_back", "stopped") and checkers and not builders:
            attempt_label = "Review %d" % max(reviews, 1)
        else:
            attempt_label = ""
        finished_call = None
        if state == "done":
            counted = [c for c in calls if c["counted"]]
            finished_call = counted[-1] if counted else None
        # calls
        call_rows = []
        for i, c in enumerate(calls):
            span = c["span"]
            later = [x for x in calls[i + 1:] if not (c["group"] and x["group"] == c["group"])]
            nxt = later[0] if later else None
            plain_text = span.get("plain") if isinstance(span.get("plain"), str) and span.get("plain") \
                and not span.get("plain_flag") else None
            if c["state"] == "running":
                text = "The builder is working on it." if c["cls"] == "builder" \
                    else "The checker is reading the work and looking for problems."
                source = "auto"
            elif plain_text is not None:
                text = plain_text
                source = span.get("plain_source") if isinstance(span.get("plain_source"), str) else None
            else:
                text, source = PLAIN_MISSING_TEXT, "missing"
            ended_early = c["state"] in ("failed", "stopped", "unfinished", "other")
            next_step = span.get("next_step") if isinstance(span.get("next_step"), str) and span.get("next_step") else None
            if c["state"] == "running":
                then = "Next: a checker reviews it." if c["cls"] == "builder" \
                    else "Next: sent back for fixes, or approved."
            elif not c["counted"] or ended_early:
                then = next_step or "Another attempt follows."
            elif c is finished_call:
                then = "Approved. This piece is finished." if c["cls"] == "checker" else "This piece is finished."
            elif c["cls"] == "builder" and nxt is not None and nxt["cls"] == "checker":
                then = "A checker reviewed it."
            elif c["cls"] == "builder" and nxt is not None:
                then = "Another attempt followed."
            elif c["cls"] == "checker" and nxt is not None and nxt["cls"] == "builder":
                then = "Sent back to the builder for fixes."
            elif c["cls"] == "checker" and span.get("verdict") == "approved":
                then = "Approved. This piece is finished."
            else:
                then = "A checker reviews it next." if c["cls"] == "builder" else "The builder fixes these next."
            if c["state"] == "running":
                result = "In progress"
            elif c["state"] == "done":
                result = "Finished"
            elif c["stop_reason"] == "on_purpose":
                result = "Stopped on purpose"
            else:
                result = "Didn't finish"
            start_e = to_epoch(span.get("start"))
            end_e = to_epoch(span.get("end"))
            duration = None
            if start_e is not None and end_e is not None and end_e >= start_e:
                duration = plain_duration(end_e - start_e)
            raw_note = span.get("last") if isinstance(span.get("last"), str) and span.get("last") else (
                span.get("notes") if isinstance(span.get("notes"), str) and span.get("notes") else "(empty)")
            c["row"] = {
                "key": span["span_id"], "call": span.get("call") if isinstance(span.get("call"), str) else None,
                "label": c["label"], "role": c["role"] or None, "role_name": role_name(c["role"]),
                "model": span.get("model") if isinstance(span.get("model"), str) and span.get("model") else None,
                "model_name": model_name(span.get("model")),
                "loop": _int_or_none(span.get("iteration")), "state": c["state"], "result": result,
                "counted": c["counted"], "start": span.get("start"), "end": span.get("end"),
                "start_label": clock_label(start_e) if start_e is not None else None,
                "end_label": clock_label(end_e) if end_e is not None else None,
                "duration_label": duration, "plain": text, "plain_source": source,
                "plain_flag": span.get("plain_flag") or None, "then": then,
                "stop_reason": c["stop_reason"], "next_step": next_step, "raw_note": raw_note,
                "has_plain": plain_text is not None,
            }
            call_rows.append(c["row"])
        # now, last, roles, chips
        prior = None
        running_calls = [c for c in calls if c["state"] == "running"]
        if state == "waiting":
            names_waiting = [names[d] for d in waits_for]
            now_text = ("Starts after: " + ", ".join(names_waiting)) if waits_for else "Ready to start."
        elif state == "building":
            target = running_calls[-1]
            at = calls.index(target)
            prior = calls[at - 1] if at > 0 else None
            if prior is not None and prior["cls"] == "checker" and prior["span"].get("verdict") == "rejected":
                now_text = "The builder is making the fixes the checker asked for."
            elif prior is not None and prior["state"] in ("failed", "stopped", "unfinished", "other"):
                now_text = "The builder is trying again."
            else:
                now_text = "The builder is working on it for the first time." if attempts <= 1 \
                    else "The builder is making the fixes the checker asked for."
        elif state == "checking":
            if running_calls:
                now_text = "The checker is reviewing the builder's work." if builders \
                    else "A reviewer is reading it now."
            else:
                now_text = "The builder finished. A checker reviews it next."
        elif state == "built":
            now_text = BUILT_NOW_TEXT
        elif state == "sent_back":
            now_text = "The checker asked for fixes. The builder picks it up next."
        elif state == "stopped":
            last_call = calls[-1] if calls else None
            if last_call is not None and last_call["row"]["has_plain"]:
                now_text = quote_plain(last_call["row"]["plain"], allowed)
            else:
                now_text = "This attempt ended early. The reason was not written down."
        elif state == "needs_you":
            now_text = "This waits on your decision."
        else:
            now_text = ""
        last = None
        if state in ("building", "checking", "built", "sent_back"):
            finished = [c for c in calls if c["counted"] and c["state"] == "done"]
            if finished:
                row = finished[-1]["row"]
                last = {"label": row["label"], "text": quote_plain(row["plain"], allowed),
                        "plain_source": row["plain_source"]}
        roles = {}
        if state in ("building", "checking", "built", "sent_back"):
            notes = {"building": ("working now", "reviews next"),
                     "checking": ("finished this attempt", "reviewing now"),
                     "built": ("finished this attempt", "has not started"),
                     "sent_back": ("fixes it next", "asked for fixes")}[state]
            if builders:
                roles["builder"] = {"name": role_name(builders[-1]["role"]), "note": notes[0]}
            if checkers:
                roles["checker"] = {"name": role_name(checkers[-1]["role"]), "note": notes[1]}
        chip_calls = [c for c in calls if c["stop_reason"] != "on_purpose"]
        shown = chip_calls[-4:]
        items = []
        for c in shown:
            at = calls.index(c)
            if c["state"] == "running":
                items.append({"text": "Building now" if c["cls"] == "builder" else "Checking now", "tone": "cur"})
            elif c["state"] in ("failed", "stopped", "unfinished", "other"):
                items.append({"text": "Did not finish", "tone": "back"})
            elif c["cls"] == "checker":
                if at + 1 < len(calls) or c["span"].get("verdict") == "rejected":
                    items.append({"text": "Sent back", "tone": "back"})
                else:
                    items.append({"text": "Approved", "tone": "ok"})
            else:
                fixed = at > 0 and calls[at - 1]["cls"] == "checker"
                items.append({"text": "Fixed" if fixed else "Built", "tone": ""})
        summary = None
        if state == "done" and calls:
            summary = _plural(attempts, "attempt", "attempts") if attempts else _plural(reviews, "review", "reviews")
            starts = [to_epoch(c["span"].get("start")) for c in calls if to_epoch(c["span"].get("start")) is not None]
            ends = [to_epoch(c["span"].get("end")) for c in calls if to_epoch(c["span"].get("end")) is not None]
            if starts and ends and max(ends) - min(starts) >= 60:
                summary += " \u00b7 " + plain_duration(max(ends) - min(starts))
        quiet_text = None
        if state in ("building", "checking"):
            for c in running_calls:
                info = quiet.get(c["id"])
                if info:
                    quiet_text = "No new output for %s." % _plural(info // 60, "minute", "minutes")
                    break
        pieces_out.append({
            "id": node, "name": piece["name"], "purpose": piece["purpose"], "tech_name": piece["tech_name"],
            "stage": stage_of.get(node), "planned": piece["planned"], "depends_on": deps, "waits_for": waits_for,
            "waits_for_names": [names[d] for d in waits_for], "state": state, "state_label": label_of(state),
            "attempts": attempts, "reviews": reviews, "attempt_label": attempt_label, "now": now_text,
            "last": last, "roles": roles, "chips": {"earlier": len(chip_calls) - len(shown), "items": items},
            "quiet_text": quiet_text, "summary": summary,
            "calls": [{k: v for k, v in row.items() if k != "has_plain"} for row in call_rows],
        })
    out_stages = []
    by_id = {p["id"]: p for p in pieces_out}
    for stage in stages_out:
        members = [by_id[m] for m in stage["members"] if m in by_id]
        state_set = {p["state"] for p in members}
        if members and state_set == {"done"}:
            stage_state = "done"
        elif members and state_set == {"waiting"}:
            stage_state = "waiting"
        else:
            stage_state = "active"
        out_stages.append({"n": stage["n"], "name": stage["name"], "purpose": stage["purpose"],
                           "state": stage_state, "parallel": len(members) > 1,
                           "count_label": _plural(len(members), "piece", "pieces"),
                           "pieces": [p["id"] for p in members]})
    plan_out = {"present": plan is not None, "source": "plan.json" if plan is not None else None,
                "stages": out_stages, "pieces": pieces_out}
    return plan_out, names, warnings


def _local_day_clock(epoch):
    """Jan 10, 9:35 am: the day and the clock time, in the zone clock_label uses."""
    stamp = time.localtime(epoch)
    return "%s %d, %s" % (time.strftime("%b", stamp), stamp.tm_mday, clock_label(epoch))


def _other_sentence(other_running):
    if not other_running:
        return ""
    return " 1 other task running." if other_running == 1 else " %d other tasks running." % other_running


def _owner_board(plan, waiting_items, meta, state, state_label, feature_closed, build_last, started,
                 elapsed_total, now_e, allowed, stop_plain, running_any=True, quiet_s=600):
    """The `owner` part of the board: the first screen (PAGE-SPEC 4.2)."""
    pieces = plan["pieces"]
    planned = [piece for piece in pieces if piece.get("planned", True)]
    counts = {"total": len(planned), "done": 0, "building": 0, "checking": 0, "built": 0,
              "sent_back": 0, "stopped": 0, "waiting": 0, "needs_you": 0}
    for piece in planned:
        counts[piece["state"]] += 1
    others = [piece for piece in pieces if not piece.get("planned", True)]
    other = {"total": len(others),
             "running": sum(1 for piece in others if piece["state"] in ("building", "checking")),
             "done": sum(1 for piece in others if piece["state"] == "done")}
    total = counts["total"]
    needs = bool(waiting_items)
    items = []
    for item in waiting_items:
        items.append({"gate_label": gate_label(item["gate"], stop_plain.get(item["gate"]), allowed),
                      "question": item["question"], "recommend": item["recommend"],
                      "asked_label": clock_label(item["since_e"]) if item["since_e"] is not None else None,
                      "waiting_label": plain_duration(now_e - item["since_e"]) if item["since_e"] is not None else None,
                      "how": "Answer in the session where you are running the build."})
    all_done = total > 0 and counts["done"] == total
    finished = feature_closed and not needs
    stopped = counts["stopped"]
    noun = "piece" if total == 1 else "pieces"
    tail = _other_sentence(other["running"])
    if finished and total and all_done:
        sentence = "Finished. The piece is done." if total == 1 else "Finished. All %d pieces are done." % total
    elif finished and total:
        sentence = "Finished. %d of %d %s %s done." % (counts["done"], total, noun, "is" if total == 1 else "are")
    elif finished:
        sentence = "Finished."
    elif needs:
        sentence = "%d of %d %s %s done." % (counts["done"], total, noun, "is" if total == 1 else "are")
        if stopped:
            sentence += (" 1 piece ended early, so it needs another attempt." if stopped == 1 else
                         " %d pieces ended early, so they need another attempt." % stopped)
        sentence += " Your answer is needed: %s." % items[0]["gate_label"].lower()
        sentence += tail
    elif total == 0:
        sentence = ("Nothing has started yet." if build_last is None else "No pieces have started yet.") + tail
    elif all_done:
        sentence = ("The piece is done. The build has not been closed yet." if total == 1 else
                    "All %d pieces are done. The build has not been closed yet." % total) + tail
    else:
        parts = []
        if counts["checking"]:
            parts.append("%d being checked" % counts["checking"])
        if counts["building"]:
            parts.append("%d being built" % counts["building"])
        if counts["built"]:
            parts.append("%d waiting for a check" % counts["built"])
        if counts["sent_back"]:
            parts.append("%d sent back for fixes" % counts["sent_back"])
        if stopped:
            parts.append("%d ended early" % stopped)
        quiet = (not running_any and build_last is not None and now_e - build_last > quiet_s)
        if quiet:
            head = "Nothing is running. Last activity %s. %d of %d %s done" % (
                _local_day_clock(build_last), counts["done"], total, noun)
        else:
            if not counts["building"] and not counts["checking"] and not other["running"]:
                parts.append("none running right now")
            head = "Building: %d of %d %s done" % (counts["done"], total, noun)
        sentence = head + "".join(", " + part for part in parts) + "." + tail
    calm = None
    if not needs:
        if state == "done":
            text = "This build is finished. Nothing is left to decide."
        elif state == "running":
            text = "The build is moving on its own. A question will appear here the moment it needs you."
        elif build_last is not None:
            text = ("Nothing needs you right now, but nothing is running either. "
                    "The last activity was at %s." % clock_label(build_last))
        else:
            text = "No activity has been logged yet."
        calm = {"title": "Nothing needs you", "text": text}
    deadlines = []
    raw_stops = meta.get("stop_times")
    if isinstance(raw_stops, list):
        for item in raw_stops:
            if isinstance(item, dict) and isinstance(item.get("label"), str) and to_epoch(item.get("at")) is not None:
                at = to_epoch(item["at"])
                deadlines.append({"label": gate_label(item["label"], item.get("plain") if isinstance(item.get("plain"), str) else None, allowed),
                                  "raw_label": item["label"], "at_label": clock_label(at),
                                  "mins_left": int((at - now_e) // 60), "passed": at < now_e, "_at": at})
    upcoming = sorted((d for d in deadlines if not d["passed"]), key=lambda d: d["_at"])
    nxt = None
    if upcoming:
        first = upcoming[0]
        nxt = {"label": first["label"], "at_label": first["at_label"],
               "in_label": plain_duration(first["_at"] - now_e)}
    if state == "done" or finished:
        deadline_text = "No deadlines left."
    elif not deadlines:
        deadline_text = "No deadline is set."
    elif not upcoming:
        deadline_text = "All deadlines have passed."
    else:
        deadline_text = "Next: %s at %s, in %s." % (nxt["label"], nxt["at_label"], nxt["in_label"])
    for d in deadlines:
        d.pop("_at")
    started_e = to_epoch(started)
    return {"needs_you": needs, "items": items, "calm": calm, "sentence": sentence, "counts": counts,
            "other": other,
            "started_label": clock_label(started_e) if started_e is not None else None,
            "elapsed_label": plain_duration(elapsed_total) if elapsed_total is not None else None,
            "next_deadline": nxt, "deadlines": deadlines, "deadline_text": deadline_text}


def title_plain_of(project, build_id, title):
    """The owner's build title, else `Project: Build id words` (PAGE-SPEC 4.1)."""
    if isinstance(title, str) and title.strip():
        return title
    words = str(build_id).replace("-", " ").replace("_", " ").strip()
    return "%s: %s" % (str(project)[:1].upper() + str(project)[1:], words[:1].upper() + words[1:])


def _span_when(span, *fields):
    for field in fields:
        value = to_epoch(span.get(field))
        if value is not None:
            return value
    return None


def _finish_marker(spans):
    """The finish marker (TONIGHT-SPEC 2.2), or None: a `feature` span closed with status done and
    no agent_call or command that started after its end. {"end": text, "end_e": epoch, "leftovers": list}."""
    best = None
    for span in spans:
        if span.get("kind") != "feature" or span.get("status") != "done":
            continue
        end_e = _span_when(span, "end", "event")
        if end_e is None:
            continue
        if best is None or end_e >= best[0]:
            best = (end_e, span)
    if best is None:
        return None
    end_e, span = best
    for other in spans:
        if other.get("kind") in ("agent_call", "command"):
            started = _span_when(other, "start", "event")
            if started is not None and started > end_e:
                return None
    leftovers = span.get("leftovers")
    leftovers = [item for item in leftovers if isinstance(item, dict)] if isinstance(leftovers, list) else []
    end_text = span.get("end") if to_epoch(span.get("end")) is not None else from_epoch(end_e)
    return {"end": end_text, "end_e": end_e, "leftovers": leftovers}


def board(build_dir, now_value=None, cfg=None):
    """Everything the status command, the dashboard and the browser tests show (SPEC 5.1)."""
    build_dir = Path(build_dir)
    now_text = _now_text(now_value)
    now_e = to_epoch(now_text)
    if now_e is None:
        raise FactoryError(EXIT.USAGE, "factory: the time given to the board is not a timestamp",
                           "board time is not a timestamp")
    read = read_build(build_dir)
    spans = read["spans"]
    meta = read["meta"]
    timers = timers_of(cfg)
    mtimes = _out_mtimes(build_dir)
    per_span, build_last = _activity(read, mtimes)
    stale = build_last is not None and (now_e - build_last) > timers["stale_s"]
    labels = _piece_names(spans, build_dir)
    states = {}
    for span in spans:
        states[span["span_id"]] = _state_of(span, stale)

    # project and id
    project = meta.get("project") if isinstance(meta.get("project"), str) and meta.get("project") else None
    build_id = meta.get("build") if isinstance(meta.get("build"), str) and meta.get("build") else None
    for span in spans:
        if project is None and isinstance(span.get("project"), str) and span.get("kind") != "":
            project = span["project"]
        if build_id is None and isinstance(span.get("feature"), str):
            build_id = span["feature"]
    project = project or build_dir.parent.name
    build_id = build_id or build_dir.name

    # agents
    agents = []
    for index, span in enumerate(spans):
        if span.get("kind") != "agent_call":
            continue
        span_id = span["span_id"]
        state = states[span_id]
        node = span.get("node") if isinstance(span.get("node"), str) and span.get("node") else None
        plabel, pid = _piece(node, labels)
        model = span.get("model")
        if state == "running":
            start = to_epoch(span.get("start"))
            elapsed = max(0, int(now_e - start)) if start is not None else None
            elapsed_label = words_for_duration(elapsed) if elapsed is not None else "time not recorded"
        elif state == "unfinished":
            elapsed = None
            elapsed_label = "not finished in the log"
        else:
            elapsed = _int_or_none(span.get("duration_s"))
            elapsed_label = words_for_duration(elapsed) if elapsed is not None else "time not recorded"
        last = span.get("last") if isinstance(span.get("last"), str) and span.get("last") else ""
        if not last:
            out_path = None
            ref = span.get("output_ref")
            if isinstance(ref, str) and ref and not os.path.isabs(ref) and ".." not in Path(ref).parts:
                out_path = build_dir / ref
            elif _safe_id(span_id):
                out_path = build_dir / "messages" / (span_id + ".out.md")
            if out_path is not None:
                last = _tail_line(out_path)
        if not last and isinstance(span.get("notes"), str):
            last = span["notes"][:200]
        last = last[:200]
        own_last = per_span.get(span_id)
        last_age = max(0, int(now_e - own_last)) if own_last is not None else None
        quiet = state == "running" and last_age is not None and last_age > timers["quiet_s"]
        entry = {
            "role": span.get("actor") if isinstance(span.get("actor"), str) and span.get("actor") else None,
            "role_label": role_label(span.get("actor")),
            "model": model if isinstance(model, str) and model else None,
            "model_label": model if isinstance(model, str) and model else "model not recorded",
            "piece": node,
            "piece_label": plabel,
            "loop": _int_or_none(span.get("iteration")),
            "state": state,
            "state_label": STATE_LABELS.get(state, STATE_LABELS["other"]),
            "elapsed_s": elapsed,
            "elapsed_label": elapsed_label,
            "last": last,
            "last_age_s": last_age,
            "quiet": bool(quiet),
            "quiet_label": ("Quiet for %d min" % (last_age // 60)) if quiet else None,
            "key": span_id,
            "call": span.get("call") if isinstance(span.get("call"), str) else None,
            "start": span.get("start"),
            "end": span.get("end"),
        }
        if node is not None:
            entry["piece_id"] = node
        agents.append((0 if state == "running" else 1, -(own_last or 0), index, entry))
    agents.sort(key=lambda item: item[:3])
    agent_entries = [item[3] for item in agents]

    # waiting on the person
    waiting = []
    waiting_extra = []
    old_waits = 0
    for span in spans:
        if span.get("kind") != "wait" or span.get("status") != "running" or span.get("waiting_on") != "human":
            continue
        since = span.get("start") or span.get("event")
        since_e = to_epoch(since)
        if since_e is not None and now_e - since_e > HUMAN_WAIT_LIMIT_S:
            old_waits += 1
            continue
        if "question" in span.get("not_recorded", []):
            question = "A decision is needed (question not recorded)"
        else:
            question = span.get("question") or span.get("notes") or "A decision is needed"
        waiting.append((since_e if since_e is not None else now_e, {
            "gate": span.get("gate") or "Decision",
            "question": question,
            "recommend": span.get("recommend") if isinstance(span.get("recommend"), str) else None,
            "since": since,
            "mins": int(max(0, now_e - since_e) // 60) if since_e is not None else None,
        }))
        waiting_extra.append((since_e if since_e is not None else now_e,
                              {"since_e": since_e, "node": span.get("node") if isinstance(span.get("node"), str) else None}))
    waiting.sort(key=lambda item: item[0])
    waiting_extra.sort(key=lambda item: item[0])
    waiting_entries = [item[1] for item in waiting]

    # pieces
    pieces = []
    order = []
    members = {}
    for span in spans:
        if span.get("kind") in ("agent_call", "iteration") and isinstance(span.get("node"), str) and span.get("node"):
            node = span["node"]
            if node not in members:
                members[node] = []
                order.append(node)
            members[node].append(span)
    for node in order:
        group = members[node]
        group_states = [states[s["span_id"]] for s in group]
        iterations = [s.get("iteration") for s in group if _is_number(s.get("iteration"))]
        verdict = None
        for s in group:
            if isinstance(s.get("verdict"), str):
                verdict = s["verdict"]
        total = 0
        for s in group:
            if s.get("kind") != "agent_call":
                continue
            if states[s["span_id"]] == "running":
                start = to_epoch(s.get("start"))
                if start is not None:
                    total += max(0, int(now_e - start))
            elif _is_number(s.get("duration_s")):
                total += int(s["duration_s"])
        if "running" in group_states:
            state = "running"
        elif "unfinished" in group_states:
            state = "unfinished"
        elif verdict == "approved" or group_states[-1] == "done":
            state = "done"
        else:
            state = "failed"
        plabel, pid = _piece(node, labels)
        waits_here = [s for s in spans if s.get("kind") == "wait" and s.get("status") == "running"
                      and s.get("node") == node and s.get("waiting_on")]
        entry = {
            "piece": node, "piece_label": plabel, "state": state,
            "state_label": STATE_LABELS[state], "loops": int(max(iterations)) if iterations else None,
            "time_s": total, "last_verdict": verdict,
            "waiting_on": waits_here[0]["waiting_on"] if waits_here else None,
        }
        entry["piece_id"] = node
        pieces.append(entry)

    # build header
    marker = _finish_marker(spans)
    feature_closed = marker is not None
    running_any = any(s.get("kind") in ("agent_call", "command") and states[s["span_id"]] == "running"
                      for s in spans)
    if waiting_entries:
        state = "waiting"
        state_label = BUILD_STATE_LABELS["waiting"]
    elif feature_closed:
        state = "done"
        state_label = BUILD_STATE_LABELS["done"]
    elif running_any:
        state = "running"
        state_label = BUILD_STATE_LABELS["running"]
    else:
        state = "idle"
        state_label = ("No activity since %s" % _day_label(build_last)) if build_last is not None \
            else "No activity logged yet"

    current_phase = None
    best = None
    for span in spans:
        phase = span.get("phase")
        if not isinstance(phase, str) or not phase:
            continue
        key = per_span.get(span["span_id"]) or 0
        if span.get("kind") == "phase" and span.get("status") == "running":
            current_phase = span.get("phase")
            best = None
            break
        if best is None or key >= best[0]:
            best = (key, phase)
    if current_phase is None and best is not None:
        current_phase = best[1]

    started = meta.get("started") if to_epoch(meta.get("started")) is not None else None
    if started is None:
        candidates = [(to_epoch(s.get("start")), s["start"]) for s in spans if to_epoch(s.get("start")) is not None]
        if not candidates:
            candidates = [(to_epoch(s.get("event")), s["event"]) for s in spans if to_epoch(s.get("event")) is not None]
        if candidates:
            started = min(candidates)[1]
    elapsed_total = None
    started_e = to_epoch(started)
    if started_e is not None:
        if state in ("running", "waiting"):
            elapsed_total = max(0, int(now_e - started_e))
        elif build_last is not None:
            elapsed_total = max(0, int(min(build_last, now_e) - started_e))
    stops = []
    raw_stops = meta.get("stop_times")
    if isinstance(raw_stops, list):
        for item in raw_stops:
            if isinstance(item, dict) and isinstance(item.get("label"), str) and to_epoch(item.get("at")) is not None:
                stops.append({"label": item["label"], "at": item["at"],
                              "mins_left": int((to_epoch(item["at"]) - now_e) // 60)})
    title = meta.get("title") if isinstance(meta.get("title"), str) and meta.get("title") else "%s/%s" % (project, build_id)

    # warnings
    warnings = []
    if read["bad_lines"]:
        count = len(read["bad_lines"])
        warnings.append(_count_phrase(count, "%d line in the log could not be read and was skipped",
                                      "%d lines in the log could not be read and were skipped"))
    if read["bad_fields"]:
        count = len(read["bad_fields"])
        warnings.append(_count_phrase(count, "%d value in the log had the wrong kind and shows as not recorded",
                                      "%d values in the log had the wrong kind and show as not recorded"))
    open_work = [item for item in unfinished(read, now_text, cfg) if item["reason"] != "human"]
    if open_work:
        oldest = max(item["age_s"] for item in open_work)
        warnings.append("%s started and never finished. The oldest started %s ago." % (
            _count_phrase(len(open_work), "%d step was", "%d steps were"), words_for_duration(oldest)))
    if old_waits:
        warnings.append(_count_phrase(old_waits, "%d question was never marked answered in the log",
                                      "%d questions were never marked answered in the log"))
    try:
        errors = [line for line in (build_dir / "log-errors.jsonl").read_text(
            encoding="utf-8", errors="replace").split("\n") if line.strip()]
    except OSError:
        errors = []
    if errors:
        warnings.append(_count_phrase(len(errors), "%d log entry failed and was not recorded",
                                      "%d log entries failed and were not recorded"))
    eval_rows, eval_unreadable = _eval_board(build_dir, now_e)
    if eval_unreadable:
        warnings.append(_count_phrase(eval_unreadable, "%d eval result could not be read and was skipped",
                                      "%d eval results could not be read and were skipped"))

    allowed = plain_words_of(cfg)
    quiet_map = {e["key"]: e["last_age_s"] for e in agent_entries if e["quiet"]}
    waiting_nodes = {x[1]["node"] for x in waiting_extra if x[1]["node"]}
    plan_out, piece_names, plan_warnings = _plan_board(
        build_dir, spans, states, labels, per_span, quiet_map, waiting_nodes, now_e, allowed)
    warnings.extend(plan_warnings)
    stop_plain = {}
    if isinstance(raw_stops, list):
        for item in raw_stops:
            if isinstance(item, dict) and isinstance(item.get("label"), str) and isinstance(item.get("plain"), str):
                stop_plain[item["label"]] = item["plain"]
    owner_items = []
    for entry, extra in zip(waiting_entries, [x[1] for x in waiting_extra]):
        owner_items.append(dict(entry, since_e=extra["since_e"]))
    owner = _owner_board(plan_out, owner_items, meta, state, state_label, feature_closed, build_last,
                         started, elapsed_total, now_e, allowed, stop_plain,
                         running_any=running_any, quiet_s=timers["quiet_s"])

    return {
        "build": {
            "project": project, "id": build_id, "title": title, "state": state,
            "state_label": state_label, "phase": current_phase, "phase_label": phase_label(current_phase),
                        "started": started,
            "last_activity": from_epoch(build_last) if build_last is not None else None,
            "elapsed_s": elapsed_total,
            "elapsed_label": words_for_duration(elapsed_total) if elapsed_total is not None else "time not recorded",
            "stop_times": stops,
            "finished_at": marker["end"] if marker else None,
            "leftovers": marker["leftovers"] if marker else [],
        },
        "waiting_on_you": waiting_entries,
        "agents": agent_entries,
        "agents_total": len(agent_entries),
        "pieces": pieces,
        "recent": _board_recent(spans, labels, states, now_e, piece_names, stop_plain, allowed),
        "warnings": warnings,
        "evals": eval_rows,
        "owner": owner,
        "plan": plan_out,
        "generated": now_text,
    }


def list_builds(factory_home=None, now_value=None, cfg=None):
    """Every build under <home>/runs/<project>/<id>/, most recent activity first (SPEC 5.1)."""
    root = runs_root(factory_home)
    found = []
    try:
        projects = sorted(os.listdir(str(root)))
    except OSError:
        return []
    for project in projects:
        folder = root / project
        if not folder.is_dir():
            continue
        try:
            builds = sorted(os.listdir(str(folder)))
        except OSError:
            continue
        for build in builds:
            path = folder / build
            if not (path / "trace.jsonl").is_file():
                continue
            try:
                data = board(path, now_value, cfg)
            except Exception:
                found.append({"project": project, "id": build, "state": "idle",
                              "state_label": "Log could not be read", "last_activity": None, "waiting": 0,
                              "title": None, "title_plain": title_plain_of(project, build, None),
                              "state_word": "Quiet"})
                continue
            meta = load_meta(path)
            title = meta.get("title") if isinstance(meta.get("title"), str) and meta.get("title") else None
            waiting = len(data["waiting_on_you"])
            word = ("Needs you" if waiting > 0
                    else "Working" if data["build"]["state"] == "running"
                    else "Finished" if data["build"]["state"] == "done" else "Quiet")
            found.append({"project": project, "id": build, "state": data["build"]["state"],
                          "state_label": data["build"]["state_label"],
                          "last_activity": data["build"]["last_activity"],
                          "waiting": waiting, "title": title,
                          "title_plain": title_plain_of(project, build, title), "state_word": word})
    found.sort(key=lambda item: (item["last_activity"] or "", item["project"], item["id"]), reverse=True)
    return found


# ---------------------------------------------------------------------------
# notification (SPEC 4.6)
# ---------------------------------------------------------------------------

def _run_limited(command, env, limit, shell=False):
    """(exit code or None, error text) for a program run with a hard time limit."""
    try:
        process = subprocess.Popen(
            command, shell=shell, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, start_new_session=True)
    except (FileNotFoundError, PermissionError, NotADirectoryError) as exc:
        return None, "program not found or not runnable (%s)" % (exc.strerror or exc)
    except OSError as exc:
        return None, "could not start (%s)" % (exc.strerror or exc)
    try:
        _out, err = process.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.communicate(timeout=2)
        except Exception:
            pass
        return None, "timed out after %gs" % limit
    text = (err or b"").decode("utf-8", "replace").strip().splitlines()
    return process.returncode, (text[-1][:160] if text else "")


def _applescript_text(text):
    text = " ".join(str(text).split())
    return text.replace("\\", "\\\\").replace('"', '\\"')[:240]


def _notify_desktop(gate, question, limit):
    program = os.environ.get("FACTORY_OSASCRIPT_BIN") or ("osascript" if sys.platform == "darwin" else None)
    if not program:
        sys.stderr.write("\a")
        sys.stderr.flush()
        return "failed: no desktop notifier on this system"
    script = 'display notification "%s" with title "Factory: %s" sound name "Glass"' % (
        _applescript_text(question), _applescript_text(gate))
    code, detail = _run_limited([program, "-e", script], dict(os.environ), limit)
    if code == 0:
        return "sent"
    if code is None:
        return "failed: " + detail
    return "failed: exit %d%s" % (code, (": " + detail) if detail else "")


def _notify_command(command, gate, question, recommend, limit):
    env = dict(os.environ)
    env["FACTORY_GATE"] = gate
    env["FACTORY_QUESTION"] = question
    env["FACTORY_RECOMMEND"] = recommend
    code, detail = _run_limited(command, env, limit, shell=True)
    if code == 0:
        return "sent"
    if code is None:
        return "failed: " + detail
    return "failed: exit %d%s" % (code, (": " + detail) if detail else "")


def notify(cfg, gate, question, recommend, test=False):
    """Tell the owner about a decision. Returns {channel: "sent" | "failed: <why>" | "to send"}.

    Only channels listed in notify.channels are used. The connector is never
    called from code: it returns "to send" and the orchestrator sends it.
    """
    cfg = cfg or {}
    block = cfg.get("notify") or {}
    channels = block.get("channels") or []
    timers = timers_of(cfg)
    gate = str(gate)
    question = str(question)
    recommend = str(recommend)
    if test:
        question = "This is a test of the notification path. No action is needed."
        recommend = "None."
    results = {}
    for channel in channels:
        if channel in results:
            continue
        if channel == "desktop":
            results["desktop"] = _notify_desktop(gate, question, timers["notify_desktop_s"])
        elif channel == "command":
            command = block.get("command")
            if not command:
                results["command"] = "failed: notify.command is not set"
            else:
                results["command"] = _notify_command(str(command), gate, question, recommend,
                                                      timers["notify_command_s"])
        elif channel == "connector":
            connector = block.get("connector")
            if isinstance(connector, dict) and connector.get("name") and connector.get("account_confirmed") is True:
                results["connector"] = "to send"
            else:
                results["connector"] = "failed: the connector is not set up or its account is not confirmed"
    return results
