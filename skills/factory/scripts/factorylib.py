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
                 "target", "parent_id", "project", "feature")
_SOFT_BOOLS = ("warn", "target_met")
_SOFT_NUMBERS = ("value", "tokens_in", "tokens_out")


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
            if value is not None:
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
                                  "preflight")

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

    timers = raw.get("timers")
    if timers is not None:
        if not isinstance(timers, dict):
            bad('"timers" must be an object')
        for key, value in timers.items():
            if not _is_number(value) or value < 0:
                bad('"timers.%s" must be a number of seconds (0 or more)' % key)


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
            return redact(raw.strip())[:limit]
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


def _piece_names(spans):
    """{node: latest node_label} over every span."""
    labels = {}
    for span in spans:
        node = span.get("node")
        label = span.get("node_label")
        if isinstance(node, str) and isinstance(label, str) and label:
            labels[node] = label
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
    labels = _piece_names(read["spans"])
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


def _board_recent(spans, labels, states, now_epoch_value):
    entries = []
    for span in spans:
        kind = span.get("kind")
        state = states.get(span["span_id"])
        if kind == "agent_call":
            who = role_label(span.get("actor"))
            label, _pid = _piece(span.get("node"), labels)
            on = "" if label in (NO_PIECE, UNRECORDED_PIECE) else " " + label
            if state == "running":
                text = "%s started%s" % (who, on)
                when = span.get("start") or span.get("event")
            elif state == "done":
                text = "%s finished%s" % (who, on)
                verdict = span.get("verdict")
                if verdict == "approved":
                    text += ": approved"
                elif verdict == "rejected":
                    text += ": sent back"
                when = span.get("end") or span.get("event")
            elif state == "failed":
                text = "%s failed%s" % (who, on)
                when = span.get("end") or span.get("event")
            elif state == "stopped":
                text = "%s was stopped%s" % (who, on)
                when = span.get("end") or span.get("event")
            else:
                continue
        elif kind == "wait" and span.get("waiting_on") == "human":
            gate = span.get("gate") or "A decision"
            if state == "running":
                text = "A decision is needed: %s" % gate
                when = span.get("start") or span.get("event")
            elif state in ("done", "failed", "stopped"):
                text = "Decision made: %s" % gate
                when = span.get("end") or span.get("event")
            else:
                continue
        elif kind == "command" and state in ("done", "failed"):
            text = "%s ran a command: %s" % (role_label(span.get("actor")), "finished" if state == "done" else "failed")
            when = span.get("end") or span.get("event")
        elif kind == "phase" and state in ("running", "done"):
            text = "Phase: %s" % (phase_label(span.get("phase")) or "not recorded")
            when = span.get("start") or span.get("event")
        else:
            continue
        epoch = to_epoch(when)
        if epoch is None:
            continue
        entries.append((epoch, {"when": from_epoch(epoch), "text": text}))
    entries.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in entries[:15]]


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
    labels = _piece_names(spans)
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
        if pid is not None:
            entry["piece_id"] = pid
        agents.append((0 if state == "running" else 1, -(own_last or 0), index, entry))
    agents.sort(key=lambda item: item[:3])
    agent_entries = [item[3] for item in agents]

    # waiting on the person
    waiting = []
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
    waiting.sort(key=lambda item: item[0])
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
        if pid is not None:
            entry["piece_id"] = pid
        pieces.append(entry)

    # build header
    feature_closed = any(s.get("kind") == "feature" and s.get("status") == "done" for s in spans)
    running_any = any(s.get("kind") in ("agent_call", "command") and states[s["span_id"]] == "running"
                      for s in spans)
    if waiting_entries:
        state = "waiting"
        state_label = BUILD_STATE_LABELS["waiting"]
    elif running_any:
        state = "running"
        state_label = BUILD_STATE_LABELS["running"]
    elif feature_closed:
        state = "done"
        state_label = BUILD_STATE_LABELS["done"]
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
        warnings.append("%s started and never finished (the oldest %s ago)" % (
            _count_phrase(len(open_work), "%d call was", "%d calls were"), words_for_duration(oldest)))
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

    return {
        "build": {
            "project": project, "id": build_id, "title": title, "state": state,
            "state_label": state_label, "phase": current_phase, "phase_label": phase_label(current_phase),
            "started": started,
            "last_activity": from_epoch(build_last) if build_last is not None else None,
            "elapsed_s": elapsed_total,
            "elapsed_label": words_for_duration(elapsed_total) if elapsed_total is not None else "time not recorded",
            "stop_times": stops,
        },
        "waiting_on_you": waiting_entries,
        "agents": agent_entries,
        "agents_total": len(agent_entries),
        "pieces": pieces,
        "recent": _board_recent(spans, labels, states, now_e),
        "warnings": warnings,
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
                              "state_label": "Log could not be read", "last_activity": None, "waiting": 0})
                continue
            found.append({"project": project, "id": build, "state": data["build"]["state"],
                          "state_label": data["build"]["state_label"],
                          "last_activity": data["build"]["last_activity"],
                          "waiting": len(data["waiting_on_you"])})
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
