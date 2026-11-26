"""factory eval: deterministic evals and the bounded improve loop (EVALS-SPEC, factory-v1.1).

    factory eval run <set id> [--build B] [--no-log]
    factory eval show <set id> [--build B]
    factory eval diagnose <set id> [--build B]
    factory eval improve start|next|decide|status|report|brief <set id> [researcher|builder] ...

An eval set is a JSONL file of examples (input plus the known answer) and the settings that
say how to run and score it. The project's own command reads one input and prints one output;
a fixed formula compares the output with the answer. Same input, same output, same score.

No model, no network, no clock in a score, no randomness. Every string written or printed
passes through factorylib.redact. The kit never runs git commit, reset, checkout or revert:
the improve loop only reads git and prints the undo command.

main(argv) -> int takes what follows the word `eval`. Python 3.9, standard library only.
"""

import copy
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from fractions import Fraction
from pathlib import Path

import factorylib as lib

OUTPUT_LIMIT = 1048576
CUT_LIMIT = 2000
LIST_LIMIT = 10
ID_RE = lib.EVAL_ID_RE
TARGET_RE = lib.EVAL_TARGET_RE
TARGET_KEYS = lib.EVAL_TARGET_KEYS
COST_RE = re.compile(r"^factory-cost:\s*([0-9]+(\.[0-9]+)?)$")
NUMBER_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
SEGMENT_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

USAGE = (
    "factory eval run <set id> [--build B] [--no-log]",
    "factory eval show <set id> [--build B]",
    "factory eval diagnose <set id> [--build B]",
    "factory eval improve start|next|decide|status|report|brief <set id> [researcher|builder] "
    "[--build B] [--suite ok|failed]",
)


# ---------------------------------------------------------------------------
# scorers (EVALS-SPEC 5): pure functions
# ---------------------------------------------------------------------------

def normalize(text):
    """NFC, casefold, collapse Unicode whitespace."""
    t = " ".join(unicodedata.normalize("NFC", text).casefold().split())
    return unicodedata.normalize("NFC", t)


def json_equal(a, b):
    """Equality where a bool equals only the same bool and numbers compare by value."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and a == b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(json_equal(a[k], b[k]) for k in a)
    return False


def _reject_constant(_name):
    raise ValueError("not a JSON number")


def _loads(text):
    return json.loads(text, parse_constant=_reject_constant)


def _is_real(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite_float(value):
    try:
        number = float(value)
    except (OverflowError, ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _text_pair(scorer, output, expected):
    if scorer.get("normalize", True) is False:
        return output, expected
    return normalize(output), normalize(expected)


def _score_number(scorer, output, expected):
    wanted = _finite_float(expected) if _is_real(expected) else None
    if wanted is None:
        return False, "expected must be a number"
    text = output.strip()
    got = _finite_float(text) if NUMBER_RE.fullmatch(text) else None
    if got is None:
        return False, "not a number"
    tol = scorer.get("tol", 0) or 0
    rel = scorer.get("rel", 0) or 0
    if abs(got - wanted) <= max(tol, rel * abs(wanted)):
        return True, "ok"
    return False, "outside tolerance (got %g, wanted %g)" % (got, wanted)


def _score_contains(scorer, output, expected):
    items = [expected] if isinstance(expected, str) else expected
    if (not isinstance(items, list) or not items or not all(isinstance(x, str) for x in items)):
        return False, "expected must be a string or a list of strings"
    for position, item in enumerate(items, 1):
        haystack, needle = _text_pair(scorer, output, item)
        if needle not in haystack:
            return False, "missing expected text %d of %d" % (position, len(items))
    return True, "ok"


_MISSING = object()


def _field(document, path):
    current = document
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        elif isinstance(current, list) and re.fullmatch(r"[0-9]+", segment) and int(segment) < len(current):
            current = current[int(segment)]
        else:
            return _MISSING
    return current


def _score_json_field(scorer, output, expected):
    if not isinstance(expected, dict) or not expected:
        return False, "expected must be an object"
    for path in expected:
        if not all(SEGMENT_RE.fullmatch(part) for part in path.split(".")):
            return False, "bad field path"
    try:
        document = _loads(output.strip())
    except (ValueError, RecursionError):
        return False, "output is not JSON"
    for path, wanted in expected.items():
        found = _field(document, path)
        if found is _MISSING:
            return False, "missing field %s" % path
        if not json_equal(found, wanted):
            return False, "field %s differs" % path
    return True, "ok"


def score(scorer, output_text, expected):
    """(passed, reason). A pass has reason 'ok'. Reasons never hold example text."""
    kind = scorer.get("type")
    if kind == "exact":
        if not isinstance(expected, str):
            return False, "expected must be a string"
        left, right = _text_pair(scorer, output_text, expected)
        return (True, "ok") if left == right else (False, "output differs")
    if kind == "number":
        return _score_number(scorer, output_text, expected)
    if kind == "contains":
        return _score_contains(scorer, output_text, expected)
    if kind == "json_field":
        return _score_json_field(scorer, output_text, expected)
    raise ValueError("unknown scorer type")


# ---------------------------------------------------------------------------
# metrics (EVALS-SPEC 6.2, 7): pure functions
# ---------------------------------------------------------------------------

def percentile(values, p):
    """Nearest rank: the value at position ceil(p/100 * n), 1-based."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("no values")
    position = max(1, -((-p * len(ordered)) // 100))
    return ordered[min(position, len(ordered)) - 1]


def _accuracy(passed, n):
    return (2 * passed * 10000 + n) // (2 * n) / 10000


def clean_target(text):
    return "".join(str(text).split())


def _compare(value, target_text):
    match = TARGET_RE.fullmatch(target_text)
    if value is None or not match:
        return False
    op, number = match.group(1), float(match.group(2))
    return {">=": value >= number, ">": value > number, "<=": value <= number,
            "<": value < number, "==": value == number}[op]


def summarize(set_id, name, rows, targets, cost_unit):
    """The summary object of 6.2 without `ts` and `results_file`."""
    n = len(rows)
    passed = sum(1 for row in rows if row["pass"])
    summary = {"set": set_id, "name": name, "tags": [], "n": n, "passed": passed,
               "accuracy": _accuracy(passed, n) if n else 0.0}
    times = [row["time_s"] for row in rows]
    summary["time_p50_s"] = round(percentile(times, 50), 3) if times else 0.0
    summary["time_p95_s"] = round(percentile(times, 95), 3) if times else 0.0
    missing = sum(1 for row in rows if row.get("cost") is None)
    if rows and not missing:
        total = math.fsum(row["cost"] for row in rows)
        summary["cost_total"] = round(total, 4)
        summary["cost_per_example"] = round(total / n, 4)
    else:
        summary["cost_total"] = None
        summary["cost_per_example"] = None
        if rows:
            summary["cost_note"] = "not reported by %d of %d examples" % (missing, n)
    summary["cost_unit"] = cost_unit
    by_tag = {}
    for row in rows:
        for tag in row.get("tags") or []:
            entry = by_tag.setdefault(tag, {"n": 0, "passed": 0})
            entry["n"] += 1
            entry["passed"] += 1 if row["pass"] else 0
    summary["by_tag"] = {tag: {"n": e["n"], "passed": e["passed"],
                               "accuracy": _accuracy(e["passed"], e["n"])}
                         for tag, e in sorted(by_tag.items())}
    summary["failed"] = [{"id": row["id"], "reason": row["reason"]} for row in rows if not row["pass"]]
    values = {"accuracy": summary["accuracy"], "p95_s": summary["time_p95_s"],
              "cost_per_example": summary["cost_per_example"]}
    entries = []
    for key in TARGET_KEYS:
        if key in targets:
            text = clean_target(targets[key])
            entries.append({"key": key, "target": text, "value": values[key],
                            "met": _compare(values[key], text)})
    summary["targets"] = entries
    summary["met"] = all(entry["met"] for entry in entries)
    return summary


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------

def render_lines(summary):
    """The five summary lines of 4.1, from a summary object only."""
    set_id = summary.get("set")
    notes = {t.get("key"): t for t in summary.get("targets") or [] if isinstance(t, dict)}

    def note(key):
        target = notes.get(key)
        if not target:
            return ""
        return " (target %s %s)" % (target.get("target"), "met" if target.get("met") else "not met")

    lines = ["eval %s: %s of %s passed, accuracy %.4f%s" % (
        set_id, summary.get("passed"), summary.get("n"), summary.get("accuracy") or 0, note("accuracy"))]
    lines.append("time per example: p50 %.3f s, p95 %.3f s%s" % (
        summary.get("time_p50_s") or 0, summary.get("time_p95_s") or 0, note("p95_s")))
    unit = summary.get("cost_unit")
    if _is_real(summary.get("cost_per_example")) and _is_real(summary.get("cost_total")):
        lines.append("cost: %s total, %s per example%s" % (
            lib.eval_money(summary["cost_total"], unit), lib.eval_money(summary["cost_per_example"], unit),
            note("cost_per_example")))
    else:
        lines.append("cost: not reported")
    failed = [f for f in summary.get("failed") or [] if isinstance(f, dict)]
    if failed:
        shown = ["%s (%s)" % (f.get("id"), f.get("reason")) for f in failed[:LIST_LIMIT]]
        if len(failed) > LIST_LIMIT:
            shown.append("and %d more" % (len(failed) - LIST_LIMIT))
        lines.append("failed: " + ", ".join(shown))
    if summary.get("met"):
        lines.append("eval %s: targets met" % set_id)
    else:
        missed = [t.get("key") for t in summary.get("targets") or [] if isinstance(t, dict) and not t.get("met")]
        lines.append("eval %s: targets NOT met: %s" % (set_id, ", ".join(missed)))
    return lines


def _out(lines):
    sys.stdout.write(lib.redact("\n".join(lines)) + "\n")


def _fail(code, message, reason=None):
    raise lib.FactoryError(code, "factory: " + message, reason)


# ---------------------------------------------------------------------------
# diagnosis (EVALS-SPEC 12.2): pure functions
# ---------------------------------------------------------------------------

def reason_class(reason):
    reason = str(reason)
    if reason == "output differs":
        return "output differs"
    if reason.startswith("timed out after"):
        return "timed out"
    if reason.startswith("runner exit"):
        return "runner exit"
    if reason == "output too large":
        return "output too large"
    if reason == "not a number":
        return "not a number"
    if reason.startswith("outside tolerance"):
        return "outside tolerance"
    if reason.startswith("missing expected text"):
        return "missing expected text"
    if reason == "output is not JSON":
        return "output is not JSON"
    if reason.startswith("missing field"):
        return "missing field"
    if reason.startswith("field ") and reason.endswith(" differs"):
        return "field differs"
    if reason.startswith("expected must be") or reason == "bad field path":
        return "bad example"
    return "other"


def diagnose(rows):
    failed = [row for row in rows if not row["pass"]]
    groups = {}
    for row in failed:
        group = groups.setdefault(reason_class(row["reason"]), {"ids": [], "tags": {}})
        group["ids"].append(row["id"])
        for tag in row.get("tags") or []:
            group["tags"][tag] = group["tags"].get(tag, 0) + 1
    ordered = []
    for cls, group in groups.items():
        ordered.append({"class": cls, "count": len(group["ids"]), "ids": group["ids"],
                        "tags": [[tag, count] for tag, count in
                                 sorted(group["tags"].items(), key=lambda kv: (-kv[1], kv[0]))]})
    ordered.sort(key=lambda g: (-g["count"], g["class"]))
    stats = {}
    for row in rows:
        for tag in row.get("tags") or []:
            entry = stats.setdefault(tag, {"n": 0, "passed": 0, "failed": 0})
            entry["n"] += 1
            entry["passed" if row["pass"] else "failed"] += 1
    candidates = [(Fraction(e["passed"], e["n"]), -e["failed"], tag, e) for tag, e in stats.items() if e["failed"]]
    weak = None
    if candidates:
        _acc, _neg, tag, entry = min(candidates, key=lambda c: (c[0], c[1], c[2]))
        weak = {"tag": tag, "passed": entry["passed"], "n": entry["n"]}
    return {"n": len(rows), "failed": len(failed), "groups": ordered, "weak_spot": weak}


def _ids_text(ids):
    shown = list(ids[:LIST_LIMIT])
    if len(ids) > LIST_LIMIT:
        shown.append("and %d more" % (len(ids) - LIST_LIMIT))
    return ", ".join(shown)


def diagnose_text(diag, set_id, accuracy, target_text, passed, n):
    lines = ["diagnosis %s (latest run %d of %d, accuracy %.4f, target %s)" % (
        set_id, passed, n, accuracy, target_text if target_text else "none")]
    if not diag["failed"]:
        return lines + ["nothing failed in the latest run"]
    lines.append("  %d failed: %s" % (diag["failed"], "; ".join(
        "%s: %d (%s)" % (g["class"], g["count"], _ids_text(g["ids"])) for g in diag["groups"])))
    lines.append("reason groups:")
    for g in diag["groups"]:
        tags = ", ".join("%s(%d)" % (tag, count) for tag, count in g["tags"]) or "none"
        lines.append("  %s  %d of %d  ids: %s  tags: %s" % (
            g["class"], g["count"], diag["failed"], _ids_text(g["ids"]), tags))
    weak = diag["weak_spot"]
    lines.append("weak spot: tag %s (%d of %d right)" % (weak["tag"], weak["passed"], weak["n"])
                 if weak else "weak spot: none by tag")
    if any(g["class"] == "bad example" for g in diag["groups"]):
        lines.append("note: the example file may be wrong (the builder may not edit it): tell the owner")
    return lines


# ---------------------------------------------------------------------------
# improve-loop decisions (EVALS-SPEC 12.5): pure functions
# ---------------------------------------------------------------------------

def decide_round(kept, cand, suite_ok, commits, changed_paths, protected_paths, set_id):
    if commits == 0:
        return "revert", "no change made"
    if commits > 1:
        return "revert", "more than one change"
    protected = set(protected_paths)
    changed_text = any(
        cand["sets"][sid].get("targets_text") != entry.get("targets_text")
        for sid, entry in kept["sets"].items() if sid in cand["sets"])
    if any(path in protected for path in changed_paths) or changed_text:
        return "revert", "eval files or settings changed"
    if not suite_ok:
        return "revert", "tests or metrics failed"
    if any(passed and not cand["pass"].get(example, False) for example, passed in kept["pass"].items()):
        return "revert", "a passing example now fails"
    for sid, entry in kept["sets"].items():
        if sid != set_id and sid in cand["sets"] and cand["sets"][sid]["accuracy"] < entry["accuracy"]:
            return "revert", "another set got worse"
    for sid, entry in kept["sets"].items():
        for key, met in (entry.get("targets") or {}).items():
            if met and not (cand["sets"].get(sid, {}).get("targets") or {}).get(key, False):
                return "revert", "a met target is now missed"
    if not cand["sets"][set_id]["accuracy"] > kept["sets"][set_id]["accuracy"]:
        return "revert", "no gain"
    return "keep", "score improved"


def _events(lines):
    found = []
    for line in lines:
        if isinstance(line, dict):
            found.append(line)
            continue
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            found.append(value)
    return found


def replay(lines):
    """Rebuild a session from its log lines. Same lines, same result."""
    state = {"limits": {}, "start_ts": None, "set_id": None, "rounds": [], "open_round": None,
             "round_start": None, "kept": None, "stopped": None}
    for event in _events(lines):
        kind = event.get("ev")
        if kind == "start" and state["set_id"] is None:
            state["limits"] = dict(event.get("limits") or {})
            ts = event.get("ts")
            state["start_ts"] = lib.to_epoch(ts) if isinstance(ts, str) else ts
            state["set_id"] = event.get("set")
            state["kept"] = copy.deepcopy(event.get("baseline"))
        elif kind == "round_start":
            state["open_round"] = event.get("n")
            state["round_start"] = event
        elif kind == "round":
            state["rounds"].append({key: event.get(key) for key in (
                "n", "decision", "reason", "commits", "sha", "accuracy_before", "accuracy_after",
                "text", "suite", "index_lines")})
            if event.get("decision") == "keep" and isinstance(event.get("cand"), dict):
                state["kept"] = copy.deepcopy(event["cand"])
            state["open_round"] = None
            state["round_start"] = None
        elif kind == "stop":
            state["stopped"] = event.get("reason")
    return state


def stop_reason(state, now):
    """'continue' or the reason to stop; first match wins."""
    set_id = state["set_id"]
    kept = (((state.get("kept") or {}).get("sets") or {}).get(set_id) or {})
    if (kept.get("targets") or {}).get("accuracy") is True:
        return "target met"
    limits = state["limits"]
    rounds = state["rounds"]
    if len(rounds) >= limits["max_rounds"]:
        return "round limit"
    if (now - state["start_ts"]) / 60.0 >= limits["max_minutes"]:
        return "time limit"
    stall = limits["stall_rounds"]
    if len(rounds) >= stall and all(r["decision"] != "keep" for r in rounds[-stall:]):
        return "no progress"
    return "continue"


# ---------------------------------------------------------------------------
# reading the eval file (EVALS-SPEC 2.2)
# ---------------------------------------------------------------------------

def _line_error(label, number, reason):
    _fail(lib.EXIT.USAGE, "%s line %d: %s" % (label, number, reason), "eval file line is not valid")


def read_examples(path, label, set_id):
    try:
        raw = Path(path).read_bytes()
    except OSError:
        _fail(lib.EXIT.MISSING, "eval file %s for set '%s' was not found or can't be read." % (label, set_id),
              "eval file missing or unreadable")
    examples, seen = [], set()
    for number, chunk in enumerate(raw.split(b"\n"), 1):
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            _line_error(label, number, "not valid JSON")
        if not text.strip():
            continue
        try:
            obj = _loads(text)
        except (ValueError, RecursionError):
            _line_error(label, number, "not valid JSON")
        if not isinstance(obj, dict):
            _line_error(label, number, "not an object")
        ident = obj.get("id")
        if "id" not in obj or ident == "":
            _line_error(label, number, "missing id")
        if not isinstance(ident, str) or not ID_RE.fullmatch(ident) or lib.redact(ident) != ident:
            _line_error(label, number, "bad id")
        if ident in seen:
            _line_error(label, number, "duplicate id %s" % ident)
        seen.add(ident)
        if "input" not in obj:
            _line_error(label, number, "missing input")
        if "expected" not in obj:
            _line_error(label, number, "missing expected")
        tags = obj.get("tags", [])
        if "tags" in obj:
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                _line_error(label, number, "tags must be a list of strings")
            if any(not ID_RE.fullmatch(t) or lib.redact(t) != t for t in tags):
                _line_error(label, number, "bad tag")
        examples.append({"id": ident, "input": obj["input"], "expected": obj["expected"], "tags": list(tags)})
    if not examples:
        _fail(lib.EXIT.EMPTY, "%s has no examples. Nothing to run." % label, "eval file has no examples")
    return examples


# ---------------------------------------------------------------------------
# running the system under test (EVALS-SPEC 3)
# ---------------------------------------------------------------------------

class _Interrupted(Exception):
    def __init__(self, signum):
        Exception.__init__(self, signum)
        self.signum = signum


def _signal_group(pgid, signum):
    try:
        os.killpg(pgid, signum)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


def _stop_group(process, grace):
    pgid = process.pid
    _signal_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if process.poll() is not None and not _group_alive(pgid):
            break
        time.sleep(0.005)
    _signal_group(pgid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def input_text(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


class _Reader(object):
    """Reads stdout up to the limit, or stderr line by line for the last cost line."""

    def __init__(self, stream, keep_output):
        self.stream = stream
        self.keep_output = keep_output
        self.chunks = []
        self.total = 0
        self.too_large = threading.Event()
        self.cost = None
        self._partial = ""
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()

    def _run(self):
        try:
            while True:
                data = self.stream.read1(65536) if hasattr(self.stream, "read1") else self.stream.read(65536)
                if not data:
                    break
                if self.keep_output:
                    room = OUTPUT_LIMIT - self.total
                    if len(data) > room:
                        self.chunks.append(data[:max(room, 0)])
                        self.total = OUTPUT_LIMIT
                        self.too_large.set()
                        return
                    self.chunks.append(data)
                    self.total += len(data)
                else:
                    self._feed_cost(data)
        except (OSError, ValueError):
            pass
        finally:
            if not self.keep_output and self._partial:
                self._cost_line(self._partial)

    def _feed_cost(self, data):
        text = self._partial + data.decode("utf-8", "replace")
        parts = text.split("\n")
        self._partial = parts.pop()[-512:]
        for line in parts:
            self._cost_line(line)

    def _cost_line(self, line):
        match = COST_RE.match(line.strip()) if len(line) < 512 else None
        if match:
            value = _finite_float(match.group(1))
            self.cost = value


def _write_stdin(stream, data):
    try:
        stream.write(data)
        stream.flush()
    except (OSError, ValueError):
        pass
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def run_example(cmd, cwd, env, text, timeout, grace):
    """One example: {output, exit_code, time_s, cost, timed_out, too_large}."""
    started = time.monotonic()
    result = {"output": "", "exit_code": None, "time_s": 0.0, "cost": None,
              "timed_out": False, "too_large": False}
    try:
        process = subprocess.Popen(["sh", "-c", cmd], cwd=cwd, env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError:
        result.update({"exit_code": 127, "time_s": round(time.monotonic() - started, 3)})
        return result
    writer = threading.Thread(target=_write_stdin, args=(process.stdin, text.encode("utf-8", "replace")))
    writer.daemon = True
    writer.start()
    out_reader = _Reader(process.stdout, True)
    err_reader = _Reader(process.stderr, False)
    deadline = started + timeout
    timed_out = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            try:
                process.wait(timeout=min(remaining, 0.02))
                break
            except subprocess.TimeoutExpired:
                if out_reader.too_large.is_set():
                    break
        elapsed = time.monotonic() - started
        too_large = out_reader.too_large.is_set()
        if timed_out or too_large:
            _stop_group(process, grace)
    except BaseException:
        _stop_group(process, grace)
        raise
    out_reader.thread.join(0.2)
    err_reader.thread.join(0.2)
    if out_reader.thread.is_alive() or err_reader.thread.is_alive():
        _signal_group(process.pid, signal.SIGKILL)  # a leftover child still holds the pipes
        out_reader.thread.join(1)
        err_reader.thread.join(1)
    result["cost"] = err_reader.cost
    result["too_large"] = out_reader.too_large.is_set() and not timed_out
    if timed_out:
        result.update({"timed_out": True, "time_s": round(timeout, 3)})
        return result
    data = b"".join(out_reader.chunks)
    output = data.decode("utf-8", "replace")
    if output.endswith("\n"):
        output = output[:-1]
    result["output"] = output
    result["time_s"] = round(elapsed, 3)
    result["exit_code"] = None if result["too_large"] else process.returncode
    return result


def judge(setting, example, ran):
    """(passed, reason) for one run of one example, raw values."""
    if ran["timed_out"]:
        return False, "timed out after %g s" % setting["example_timeout_s"]
    if ran["too_large"]:
        return False, "output too large"
    if ran["exit_code"] != 0:
        return False, "runner exit %d" % ran["exit_code"]
    return score(setting["scorer"], ran["output"], example["expected"])


# ---------------------------------------------------------------------------
# settings and context
# ---------------------------------------------------------------------------

def _eval_settings(cfg):
    block = cfg.get("evals") if isinstance(cfg.get("evals"), dict) else {}
    sets = []
    for entry in block.get("sets") or []:
        item = dict(entry)
        item["name"] = entry.get("name") or entry["id"]
        item["targets"] = {key: clean_target(text) for key, text in entry["targets"].items()}
        sets.append(item)
    improve = dict(lib.EVAL_IMPROVE_DEFAULTS)
    improve.update(block.get("improve") or {})
    return {"sets": sets, "cost_unit": block.get("cost_unit") or "USD", "improve": improve}


class Context(object):
    def __init__(self, project, cfg, settings, setting):
        self.project = project
        self.cfg = cfg
        self.settings = settings
        self.set = setting
        self.build = None
        self.log = True


def _load_context(set_id, state, build_arg, need_build=True):
    project = Path(os.environ.get("FACTORY_PROJECT") or os.getcwd()).resolve()
    cfg = lib.load_config_full(project)[0]
    if not (project / "factory.json").is_file():
        _fail(lib.EXIT.MISSING, "no factory.json found in %s. Run this from the project folder." % project,
              "no project settings file")
    settings = _eval_settings(cfg)
    known = [item["id"] for item in settings["sets"]]
    setting = next((item for item in settings["sets"] if item["id"] == set_id), None)
    if setting is None:
        if known:
            _fail(lib.EXIT.USAGE, "no eval set '%s'. Known sets: %s." % (set_id, ", ".join(known)),
                  "unknown eval set")
        _fail(lib.EXIT.USAGE, "no eval set '%s': none are declared in factory.json." % set_id, "unknown eval set")
    ctx = Context(project, cfg, settings, setting)
    if need_build:
        ctx.build = lib.select_build({"build": build_arg})
        state["build"] = ctx.build
    return ctx


def _latest_entry(build_dir, set_id):
    entries = [e for e in lib.read_jsonl_tail(Path(build_dir) / "evals" / "index.jsonl") if e.get("set") == set_id]
    return entries[-1] if entries else None


def _no_run(set_id):
    _fail(lib.EXIT.EMPTY, "no eval run recorded for '%s' in this build." % set_id, "no eval run recorded")


def _read_summary(build_dir, entry):
    name = entry.get("summary")
    try:
        if not isinstance(name, str) or "/" in name:
            raise ValueError(name)
        value = json.loads((Path(build_dir) / "evals" / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(name)
        return value
    except (OSError, ValueError):
        _fail(lib.EXIT.MISSING, "the eval result for '%s' can't be read." % entry.get("set"),
              "eval result unreadable")


def _read_results(build_dir, entry):
    name = entry.get("file")
    try:
        if not isinstance(name, str) or "/" in name:
            raise ValueError(name)
        text = (Path(build_dir) / "evals" / name).read_text(encoding="utf-8")
    except (OSError, ValueError):
        _fail(lib.EXIT.MISSING, "the eval results file for '%s' can't be read." % entry.get("set"),
              "eval results file unreadable")
    rows = []
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            rows.append(value)
    return rows


# ---------------------------------------------------------------------------
# factory eval run
# ---------------------------------------------------------------------------

def _store(value, counter):
    if not isinstance(value, str):
        value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    clean, count = lib.redact_count(value)
    counter[0] += count
    if len(clean) > CUT_LIMIT:
        clean = clean[:CUT_LIMIT] + "...[cut]"
    return clean


def _stamp(now_text):
    return re.sub(r"[-:]", "", now_text)


def _create_new(path, text):
    with open(str(path), "x", encoding="utf-8") as stream:
        stream.write(text)


def _redact_counted(value, counter):
    if isinstance(value, str):
        clean, count = lib.redact_count(value)
        counter[0] += count
        return clean
    if isinstance(value, list):
        return [_redact_counted(v, counter) for v in value]
    if isinstance(value, dict):
        return {k: _redact_counted(v, counter) for k, v in value.items()}
    return value


def _write_run_files(build_dir, set_id, rows, summary_value):
    """Create the results and summary files; returns (summary name, results name, ts)."""
    folder = Path(build_dir) / "evals"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _stamp(lib.now())
    number = 1
    while True:
        stem = "%s-%s" % (set_id, stamp) + ("" if number == 1 else "-%d" % number)
        results, summary = folder / (stem + ".jsonl"), folder / (stem + ".json")
        if not results.exists() and not summary.exists():
            try:
                _create_new(results, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
                break
            except FileExistsError:
                pass
        number += 1
    summary_value["ts"] = lib.now()
    summary_value["results_file"] = results.name
    _create_new(summary, json.dumps(summary_value, ensure_ascii=False, indent=2) + "\n")
    lib.append_jsonl_locked(folder / "index.jsonl", {
        "ts": summary_value["ts"], "set": set_id, "file": results.name, "summary": summary.name,
        "met": summary_value["met"]}, mkdir=True)
    return summary.name


def _span_target_text(summary):
    return "; ".join("%s%s" % (t["key"], t["target"]) for t in summary["targets"])


def cmd_run(ctx, no_log):
    setting = ctx.set
    set_id = setting["id"]
    label = setting["file"]
    examples = read_examples(ctx.project / label, label, set_id)
    timers = lib.timers_of(ctx.cfg)
    grace = timers["kill_grace_s"]
    build_dir = ctx.build.dir if ctx.build is not None and not no_log else None
    span_id = None
    started = time.monotonic()
    cmd_text = "factory eval run %s" % set_id
    base_fields = {"kind": "command", "actor": "orchestrator", "step": "evalset.%s" % set_id, "cmd": cmd_text}

    def on_signal(signum, _frame):
        raise _Interrupted(signum)

    saved = {}
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        try:
            saved[getattr(signal, name)] = signal.signal(getattr(signal, name), on_signal)
        except (ValueError, OSError, AttributeError):
            pass
    rows = []
    try:
        try:
            if build_dir is not None:
                start_fields = dict(base_fields)
                start_fields.update({"status": "running", "start": lib.now()})
                span_id = lib.append(build_dir, start_fields)
            for example in examples:
                env = dict(os.environ)
                env["FACTORY_EVAL_ID"] = example["id"]
                env["FACTORY_EVAL_SET"] = set_id
                ran = run_example(setting["cmd"], str(ctx.project), env, input_text(example["input"]),
                                  setting["example_timeout_s"], grace)
                passed, reason = judge(setting, example, ran)
                rows.append({"example": example, "ran": ran, "pass": passed, "reason": reason})
        except _Interrupted as exc:
            code = 128 + exc.signum
            if span_id is not None:
                fields = dict(base_fields)
                fields.update({"span_id": span_id, "end": lib.now(), "status": "stopped", "exit_code": code,
                               "duration_s": int(round(time.monotonic() - started)),
                               "notes": "stopped by a %s signal" % signal.Signals(exc.signum).name})
                try:
                    lib.append(build_dir, fields)
                except (OSError, lib.FactoryError):
                    pass
            return code
    finally:
        for signum, handler in saved.items():
            try:
                signal.signal(signum, handler)
            except (ValueError, OSError):
                pass

    redactions = [0]
    stored = []
    plain = []
    for item in rows:
        example, ran = item["example"], item["ran"]
        stored.append({
            "id": example["id"], "pass": item["pass"], "reason": _store(item["reason"], redactions),
            "input": _store(example["input"], redactions), "expected": _store(example["expected"], redactions),
            "output": _store(ran["output"], redactions), "exit_code": ran["exit_code"],
            "time_s": ran["time_s"], "cost": ran["cost"], "tags": example["tags"]})
        plain.append({"id": example["id"], "pass": item["pass"], "reason": item["reason"],
                      "time_s": ran["time_s"], "cost": ran["cost"], "tags": example["tags"]})
    summary = summarize(set_id, setting["name"], plain, setting["targets"], ctx.settings["cost_unit"])
    summary = _redact_counted(summary, redactions)
    if build_dir is not None:
        summary_name = _write_run_files(build_dir, set_id, stored, summary)
        fields = dict(base_fields)
        fields.update({
            "span_id": span_id, "end": lib.now(), "duration_s": int(round(time.monotonic() - started)),
            "status": "done" if summary["met"] else "failed", "exit_code": 0 if summary["met"] else 1,
            "value": summary["accuracy"], "target": _span_target_text(summary), "target_met": summary["met"],
            "eval_n": summary["n"], "eval_passed": summary["passed"], "eval_p50_s": summary["time_p50_s"],
            "eval_p95_s": summary["time_p95_s"], "eval_cost": summary["cost_total"],
            "output_ref": "evals/" + summary_name})
        if not summary["met"]:
            fields["failure_class"] = "impl-bug"
        lib.append(build_dir, fields)
        if redactions[0]:
            sys.stderr.write("factory: redacted %d secret-looking value(s) in eval results\n" % redactions[0])
    _out(render_lines(summary))
    return lib.EXIT.OK if summary["met"] else lib.EXIT.NO


# ---------------------------------------------------------------------------
# factory eval show / diagnose
# ---------------------------------------------------------------------------

def cmd_show(ctx):
    entry = _latest_entry(ctx.build.dir, ctx.set["id"])
    if entry is None:
        _no_run(ctx.set["id"])
    _out(render_lines(_read_summary(ctx.build.dir, entry)))
    return lib.EXIT.OK


def _diagnosis(ctx):
    """(lines, entry, summary, rows) for the latest run; raises exit 4 with no run."""
    entry = _latest_entry(ctx.build.dir, ctx.set["id"])
    if entry is None:
        _no_run(ctx.set["id"])
    summary = _read_summary(ctx.build.dir, entry)
    rows = _read_results(ctx.build.dir, entry)
    diag = diagnose([{"id": r["id"], "pass": bool(r.get("pass")), "reason": str(r.get("reason", "")),
                      "tags": [t for t in (r.get("tags") or []) if isinstance(t, str)]} for r in rows])
    lines = diagnose_text(diag, ctx.set["id"], summary.get("accuracy") or 0,
                          ctx.set["targets"].get("accuracy"),
                          summary.get("passed") or 0, summary.get("n") or 0)
    return lines, entry, summary, rows


def cmd_diagnose(ctx):
    _out(_diagnosis(ctx)[0])
    return lib.EXIT.OK


# ---------------------------------------------------------------------------
# git reads (the only git sub-commands used: rev-parse, status, rev-list, log, diff, ls-files)
# ---------------------------------------------------------------------------

def _git(project, *args):
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        done = subprocess.run(["git"] + list(args), cwd=str(project), env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return done.returncode, done.stdout.decode("utf-8", "replace")


def _git_head(project):
    code, out = _git(project, "rev-parse", "HEAD")
    return out.strip() if code == 0 and out.strip() else None


def _git_commits(project, start):
    code, out = _git(project, "rev-list", "--count", "%s..HEAD" % start)
    try:
        return int(out.strip()) if code == 0 else 0
    except ValueError:
        return 0


def _git_clean(project):
    code, out = _git(project, "status", "--porcelain", "--untracked-files=no")
    return code == 0 and not out.strip()


# ---------------------------------------------------------------------------
# improve: session files and state
# ---------------------------------------------------------------------------

def _redact_obj(value):
    if isinstance(value, str):
        return lib.redact(value)
    if isinstance(value, list):
        return [_redact_obj(v) for v in value]
    if isinstance(value, dict):
        return {k: _redact_obj(v) for k, v in value.items()}
    return value


def _sessions(build_dir, set_id):
    pattern = re.compile(r"^%s-(\d{8}T\d{6}Z)(?:-(\d+))?\.jsonl$" % re.escape(set_id))
    found = []
    try:
        names = os.listdir(str(Path(build_dir) / "evals" / "improve"))
    except OSError:
        return []
    for name in names:
        match = pattern.match(name)
        if match:
            found.append(((match.group(1), int(match.group(2) or 1)), name))
    found.sort()
    return [Path(build_dir) / "evals" / "improve" / name for _key, name in found]


def _read_lines(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").split("\n")
    except OSError:
        return []


def _log(path, event):
    lib.append_jsonl_locked(path, _redact_obj(event), mkdir=True)


def _index_count(build_dir):
    return len(lib.read_jsonl_tail(Path(build_dir) / "evals" / "index.jsonl"))


def _build_state(ctx):
    """The state shape of 12.5 from the latest runs and the current settings."""
    found, _bad = lib.eval_summaries(ctx.build.dir)
    texts = {item["id"]: item["targets"] for item in ctx.settings["sets"]}
    sets, passes = {}, {}
    for entry, summary in found:
        sid = summary.get("set")
        targets = {t["key"]: bool(t.get("met")) for t in summary.get("targets") or [] if isinstance(t, dict)}
        text = texts.get(sid)
        if text is None:
            text = {t["key"]: t.get("target") for t in summary.get("targets") or [] if isinstance(t, dict)}
        sets[sid] = {"accuracy": summary.get("accuracy"), "targets": targets, "targets_text": dict(text)}
        if sid == ctx.set["id"]:
            try:
                passes = {r["id"]: bool(r.get("pass")) for r in _read_results(ctx.build.dir, entry)}
            except lib.FactoryError:
                passes = {}
    return {"sets": sets, "pass": passes}


class Session(object):
    def __init__(self, path, lines):
        self.path = path
        self.lines = lines
        self.id = path.stem
        self.state = replay(lines)
        self.events = _events(lines)


def _load_session(ctx, allow_stopped=True):
    sessions = _sessions(ctx.build.dir, ctx.set["id"])
    if not sessions:
        _fail(lib.EXIT.EMPTY, "no improve session for '%s' in this build." % ctx.set["id"], "no improve session")
    session = Session(sessions[-1], _read_lines(sessions[-1]))
    if session.state["set_id"] is None:
        _fail(lib.EXIT.EMPTY, "no improve session for '%s' in this build." % ctx.set["id"], "no improve session")
    if not allow_stopped and session.state["stopped"] is not None:
        _fail(lib.EXIT.EMPTY, "the session for '%s' has stopped." % ctx.set["id"], "improve session stopped")
    return session


def _pct_of_target(text):
    match = TARGET_RE.fullmatch(clean_target(text or ""))
    if not match:
        return None
    number = round(float(match.group(2)) * 100, 1)
    return int(number) if float(number).is_integer() else number


def _kept_accuracy(state):
    return (((state.get("kept") or {}).get("sets") or {}).get(state["set_id"]) or {}).get("accuracy")


def _baseline_accuracy(session):
    start = next((e for e in session.events if e.get("ev") == "start"), {})
    return ((((start.get("baseline") or {}).get("sets") or {}).get(session.state["set_id"]) or {})
            .get("accuracy"))


def _target_text(state):
    kept = ((state.get("kept") or {}).get("sets") or {}).get(state["set_id"]) or {}
    return (kept.get("targets_text") or {}).get("accuracy")


def _next_number(state):
    return state["open_round"] if state["open_round"] else len(state["rounds"]) + 1


def _undo_check(ctx, session):
    """Exit 2 unless the last reverted change was undone and the evals rerun (12.5)."""
    rounds = session.state["rounds"]
    if not rounds:
        return
    last = rounds[-1]
    if last.get("decision") != "revert" or (last.get("commits") or 0) < 1:
        return
    set_id = ctx.set["id"]
    entries = lib.read_jsonl_tail(ctx.build.dir / "evals" / "index.jsonl")
    newer = any(e.get("set") == set_id for e in entries[(last.get("index_lines") or 0):])
    undone = _git_commits(ctx.project, last.get("sha") or "HEAD") >= 1
    same = _build_state(ctx)["pass"] == (session.state["kept"] or {}).get("pass")
    if not (undone and newer and same):
        _fail(lib.EXIT.USAGE, "undo the last change and rerun the evals first.", "last change not undone")


def _write_stop(ctx, session, reason):
    state = replay(_read_lines(session.path))
    kept = state["kept"] or {}
    entry = (kept.get("sets") or {}).get(state["set_id"]) or {}
    _log(session.path, {
        "ev": "stop", "ts": lib.now(), "reason": reason, "rounds": len(state["rounds"]),
        "accuracy_start": _baseline_accuracy(session), "accuracy_end": entry.get("accuracy"),
        "met": (entry.get("targets") or {}).get("accuracy") is True})


def _limits_text(limits):
    return "%g" % limits["max_minutes"]


def improve_start(ctx):
    set_id = ctx.set["id"]
    sessions = _sessions(ctx.build.dir, set_id)
    if sessions:
        session = Session(sessions[-1], _read_lines(sessions[-1]))
        if session.state["set_id"] is not None and session.state["stopped"] is None:
            _out(["session %s continues at round %d" % (session.id, _next_number(session.state))])
            return lib.EXIT.OK
    need_git = "improve needs a git project with no uncommitted changes."
    code, inside = _git(ctx.project, "rev-parse", "--is-inside-work-tree")
    if code != 0 or inside.strip() != "true" or not _git_clean(ctx.project):
        _fail(lib.EXIT.USAGE, need_git, "improve needs a clean git project")
    paths = ["factory.json"] + [item["file"] for item in ctx.settings["sets"]]
    if any(_git(ctx.project, "ls-files", "--error-unmatch", "--", path)[0] != 0 for path in paths):
        _fail(lib.EXIT.USAGE, "improve needs factory.json and the eval files tracked by git.",
              "improve needs tracked eval files")
    head = _git_head(ctx.project)
    if head is None:
        _fail(lib.EXIT.USAGE, need_git, "improve needs a clean git project")
    entry = _latest_entry(ctx.build.dir, set_id)
    if entry is None:
        _no_run(set_id)
    target = ctx.set["targets"].get("accuracy")
    summary = _read_summary(ctx.build.dir, entry)
    if target is None:
        _fail(lib.EXIT.EMPTY, "improve works on a missed accuracy target only.", "no accuracy target")
    if _compare(summary.get("accuracy"), target):
        if summary.get("met"):
            _fail(lib.EXIT.EMPTY, "'%s' already meets its target. Nothing to improve." % set_id, "target already met")
        _fail(lib.EXIT.EMPTY, "improve works on a missed accuracy target only.", "accuracy target already met")
    limits = {key: ctx.settings["improve"][key] for key in lib.EVAL_IMPROVE_DEFAULTS}
    stamp = _stamp(lib.now())
    folder = ctx.build.dir / "evals" / "improve"
    folder.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        path = folder / ("%s-%s%s.jsonl" % (set_id, stamp, "" if number == 1 else "-%d" % number))
        if not path.exists():
            break
        number += 1
    _log(path, {"ev": "start", "ts": lib.now(), "set": set_id, "head": head, "limits": limits,
                "baseline": _build_state(ctx)})
    _out(["session %s: limits %d rounds, %s min, stop after %d without gain" % (
        path.stem, limits["max_rounds"], _limits_text(limits), limits["stall_rounds"])])
    return lib.EXIT.OK


def improve_next(ctx):
    session = _load_session(ctx, allow_stopped=False)
    state = session.state
    if state["open_round"]:
        _out(["continue (round %d)" % state["open_round"]])
        return lib.EXIT.OK
    _undo_check(ctx, session)
    reason = stop_reason(state, lib.now_epoch())
    if reason != "continue":
        _write_stop(ctx, session, reason)
        _out(["stop: %s" % reason])
        return lib.EXIT.OK
    number = len(state["rounds"]) + 1
    _log(session.path, {"ev": "round_start", "n": number, "ts": lib.now(), "head": _git_head(ctx.project),
                        "index_lines": _index_count(ctx.build.dir)})
    _out(["continue (round %d)" % number])
    return lib.EXIT.OK


def _commit_text(ctx, set_id, number, commits):
    if commits == 0:
        return ""
    if commits > 1:
        return "Several changes made"
    code, out = _git(ctx.project, "log", "-1", "--format=%s")
    subject = out.strip() if code == 0 else ""
    prefix = "improve(%s) r%d:" % (set_id, number)
    if not subject.startswith(prefix):
        return "Change made"
    text = lib.redact(CONTROL_RE.sub(" ", subject[len(prefix):]))
    text = " ".join(text.split())[:100].rstrip()
    if text.endswith("."):
        text = text[:-1].rstrip()
    return text or "Change made"


def improve_decide(ctx, suite):
    set_id = ctx.set["id"]
    session = _load_session(ctx, allow_stopped=False)
    state = session.state
    number = state["open_round"]
    if not number:
        _fail(lib.EXIT.USAGE, "run 'factory eval improve next %s' first." % set_id, "no open improve round")
    if not _git_clean(ctx.project):
        _fail(lib.EXIT.USAGE, "commit or undo uncommitted changes first.", "uncommitted changes")
    start = state["round_start"] or {}
    head_start = start.get("head")
    commits = _git_commits(ctx.project, head_start) if head_start else 0
    entries = lib.read_jsonl_tail(ctx.build.dir / "evals" / "index.jsonl")
    if commits:
        after = entries[(start.get("index_lines") or 0):]
        ran = set(e.get("set") for e in after)
        if any(sid not in ran for sid in state["kept"]["sets"]):
            _fail(lib.EXIT.USAGE, "rerun the evals first.", "evals not rerun")
    cand = _build_state(ctx)
    changed = []
    if commits:
        code, out = _git(ctx.project, "diff", "--name-only", "--relative", "-z", "%s..HEAD" % head_start)
        changed = [p for p in out.split("\0") if p] if code == 0 else []
    protected = ["factory.json"] + [item["file"] for item in ctx.settings["sets"]]
    protected = [os.path.normpath(p).replace(os.sep, "/") for p in protected]
    decision, reason = decide_round(state["kept"], cand, suite == "ok", commits, changed, protected, set_id)
    sha = _git_head(ctx.project)
    before = ((state["kept"]["sets"].get(set_id)) or {}).get("accuracy")
    after_acc = (cand["sets"].get(set_id) or {}).get("accuracy")
    research = "r%d-research.md" % number
    event = {"ev": "round", "n": number, "ts": lib.now(), "sha": sha, "commits": commits,
             "decision": decision, "reason": reason, "suite": suite, "accuracy_before": before,
             "accuracy_after": after_acc, "text": _commit_text(ctx, set_id, number, commits),
             "research": research if (ctx.build.dir / "evals" / "improve" / session.id / research).is_file() else None,
             "index_lines": len(entries)}
    if decision == "keep":
        event["cand"] = cand
    _log(session.path, event)
    now_text = lib.now()
    lib.append(ctx.build.dir, {
        "kind": "command", "actor": "orchestrator", "step": "improve.%s.r%d" % (set_id, number),
        "cmd": "factory eval improve decide %s" % set_id, "status": "done", "start": now_text, "end": now_text,
        "duration_s": 0, "value": after_acc, "improve_round": number, "improve_kept": decision == "keep",
        "improve_reason": reason})
    out = ["kept: %s" % reason] if decision == "keep" else ["reverted: %s" % reason]
    if decision == "revert" and commits == 1:
        out.append("undo with: git revert --no-edit %s" % sha)
    elif decision == "revert" and commits > 1:
        out.append("undo with: git revert --no-edit %s..HEAD" % head_start)
    new_state = replay(_read_lines(session.path))
    verdict = stop_reason(new_state, lib.now_epoch())
    if verdict != "continue":
        _write_stop(ctx, session, verdict)
        out.append("next: stop: %s" % verdict)
    else:
        out.append("next: continue")
    _out(out)
    return lib.EXIT.OK


def improve_status(ctx):
    session = _load_session(ctx)
    state = session.state
    limits = state["limits"]
    minutes = int(max(0, lib.now_epoch() - state["start_ts"]) // 60)
    kept_rounds = sum(1 for r in state["rounds"] if r["decision"] == "keep")
    number = _next_number(state) if state["stopped"] is None else len(state["rounds"])
    target = _pct_of_target(_target_text(state))
    accuracy = _kept_accuracy(state)
    running = "running" if state["stopped"] is None else "stopped: %s" % state["stopped"]
    _out(["session %s: round %d of %d, %d of %s min, kept %d, score %d%% (target %s%%), %s" % (
        session.id, number, limits["max_rounds"], minutes, _limits_text(limits), kept_rounds,
        lib.eval_percent_of_accuracy(accuracy or 0), "%g" % target if target is not None else "none", running)])
    return lib.EXIT.OK


def _plural_rounds(count):
    return "%d round%s" % (count, "" if count == 1 else "s")


def improve_report_text(session, name):
    state = session.state
    start = _baseline_accuracy(session)
    kept = _kept_accuracy(state)
    stop = next((e for e in reversed(session.events) if e.get("ev") == "stop"), None)
    if stop and stop.get("accuracy_start") is not None:
        start = stop["accuracy_start"]
    target = _pct_of_target(_target_text(state))
    head = "%s: tried to improve it in %s. Score went from %d%% to %d%%" % (
        name, _plural_rounds(len(state["rounds"])), lib.eval_percent_of_accuracy(start or 0),
        lib.eval_percent_of_accuracy(kept or 0))
    lines = [head + ("; the target is %g%%." % target if target is not None else ".")]
    for item in state["rounds"]:
        a = lib.eval_percent_of_accuracy(item.get("accuracy_before") or 0)
        b = lib.eval_percent_of_accuracy(item.get("accuracy_after") or 0)
        text = item.get("text") or "No change made"
        if item.get("decision") == "keep":
            lines.append("Round %s: %s. Score %d%% to %d%%. Kept." % (item["n"], text, a, b))
        elif not item.get("text"):
            lines.append("Round %s: No change made. Undone: %s." % (item["n"], item.get("reason")))
        elif item.get("accuracy_before") == item.get("accuracy_after"):
            lines.append("Round %s: %s. Score stayed at %d%%. Undone: %s." % (item["n"], text, b, item.get("reason")))
        else:
            lines.append("Round %s: %s. Score %d%% to %d%%. Undone: %s." % (item["n"], text, a, b, item.get("reason")))
    limits = state["limits"]
    reason = state["stopped"]
    if reason is None:
        lines.append("Still running.")
    else:
        stall = limits.get("stall_rounds", 0)
        words = {"target met": "the target was reached",
                 "round limit": "the limit of %s rounds was reached" % limits.get("max_rounds"),
                 "time limit": "the time limit of %g minutes was reached" % limits.get("max_minutes", 0),
                 "no progress": "%s in a row did not improve it" % (
                     "1 round" if stall == 1 else "%s rounds" % stall)}.get(reason, reason)
        lines.append("Stopped because: %s." % words)
    return lines


def improve_report(ctx):
    session = _load_session(ctx)
    _undo_check(ctx, session)
    _out(improve_report_text(session, ctx.set["name"]))
    return lib.EXIT.OK


def improve_summary(build_dir, set_id):
    """{rounds, from, to} for the latest improve session of a set (for the report card), else None."""
    sessions = _sessions(build_dir, set_id)
    if not sessions:
        return None
    session = Session(sessions[-1], _read_lines(sessions[-1]))
    if session.state["set_id"] is None:
        return None
    start, kept = _baseline_accuracy(session), _kept_accuracy(session.state)
    if start is None or kept is None:
        return None
    return {"rounds": len(session.state["rounds"]), "from": start, "to": kept}


def improve_brief(ctx, role):
    set_id = ctx.set["id"]
    session = _load_session(ctx, allow_stopped=False)
    state = session.state
    number = state["open_round"]
    if not number:
        _fail(lib.EXIT.USAGE, "run 'factory eval improve next %s' first." % set_id, "no open improve round")
    lines, entry, _summary, _rows = _diagnosis(ctx)
    target = ctx.set["targets"].get("accuracy") or "none"
    out = []
    if role == "researcher":
        out += ["You are the researcher for round %d of improving the eval set \"%s\" (id %s)." % (
                    number, ctx.set["name"], set_id),
                "Accuracy target: %s. Project folder: %s" % (target, ctx.project), ""]
        out += lines
        out += ["", "Rules:",
                "- Find ways to fix the weak spot using the project's own code and docs, the libraries' docs and prior art.",
                "- Recommend ONE change.",
                "- Write at most 40 lines: what you found, the one change, the evidence or source.",
                "- Change no project file.",
                "- Print the note to stdout and write no file.", "",
                "Do not open these files (they hold the known answers):"]
        out += ["- %s" % item["file"] for item in ctx.settings["sets"]]
    else:
        note = ctx.build.dir / "evals" / "improve" / session.id / ("r%d-research.md" % number)
        out += ["You are the builder for round %d of improving the eval set \"%s\" (id %s)." % (
                    number, ctx.set["name"], set_id),
                "Accuracy target: %s. Project folder: %s" % (target, ctx.project), ""]
        out += lines
        out += ["", "Research note: %s" % note,
                "Redacted results of the latest run: %s" % (ctx.build.dir / "evals" / entry["file"]), "",
                "Rules:",
                "- Make one change only: one git commit whose message is `improve(%s) r%d: <one plain past-tense sentence>`." % (
                    set_id, number),
                "- Never edit any eval file, factory.json or any locked test.",
                "- If nothing is worth changing, make no commit."]
    _out(out)
    return lib.EXIT.OK


# ---------------------------------------------------------------------------
# argument handling
# ---------------------------------------------------------------------------

def _usage(stream=None, code=lib.EXIT.USAGE):
    stream = stream or sys.stderr
    stream.write("factory: usage:\n" + "".join("  %s\n" % line for line in USAGE))
    return code


_SUB_HELP = {
    "run": ["factory eval run <set id> [--build <id>] [--no-log]",
            "Score every example in the set and write new files under the build's evals/ folder."],
    "show": ["factory eval show <set id> [--build <id>]",
             "Show the latest saved run of the set. Runs nothing."],
    "diagnose": ["factory eval diagnose <set id> [--build <id>]",
                 "Group the misses of the latest run by tag and say what to look at first."],
    "improve": ["factory eval improve <start|next|decide|status|report|brief> <set id> [--build <id>] [--suite ok|failed]",
                "  start   open an improve session for the set",
                "  next    begin the next round",
                "  decide  close the round; needs --suite ok|failed",
                "  status  show the session so far",
                "  report  write the session report",
                "  brief   print a prompt: brief <set id> researcher|builder"],
}


def _sub_help(sub):
    sys.stdout.write("factory: usage:\n" + "".join("  %s\n" % line for line in _SUB_HELP[sub]))
    return lib.EXIT.OK


def _parse(args, value_options, flag_options):
    positional, options = [], {}
    items = list(args)
    while items:
        item = items.pop(0)
        if item.startswith("--"):
            name, equals, inline = item.partition("=")
            if name in flag_options and not equals:
                options[name] = True
            elif name in value_options:
                if equals:
                    options[name] = inline
                elif items:
                    options[name] = items.pop(0)
                else:
                    return None
            else:
                return None
        else:
            positional.append(item)
    return positional, options


def _main(argv, state):
    if not argv or argv[0] in ("-h", "--help"):
        return _usage(sys.stdout, lib.EXIT.OK) if argv else _usage()
    sub = argv[0]
    if sub in _SUB_HELP and any(a in ("-h", "--help") for a in argv[1:]):
        return _sub_help(sub)
    if sub in ("run", "show", "diagnose"):
        parsed = _parse(argv[1:], ("--build",), ("--no-log",) if sub == "run" else ())
        if parsed is None or len(parsed[0]) != 1:
            return _usage()
        (set_id,), options = parsed
        no_log = bool(options.get("--no-log"))
        state["log"] = not no_log
        ctx = _load_context(set_id, state, options.get("--build"), need_build=not no_log)
        if sub == "run":
            return cmd_run(ctx, no_log)
        return cmd_show(ctx) if sub == "show" else cmd_diagnose(ctx)
    if sub == "improve":
        parsed = _parse(argv[1:], ("--build", "--suite"), ("--no-log",))
        if parsed is None or len(parsed[0]) < 2:
            return _usage()
        positional, options = parsed
        action, set_id = positional[0], positional[1]
        extra = positional[2:]
        if action not in ("start", "next", "decide", "status", "report", "brief"):
            return _usage()
        if options.get("--no-log"):
            _fail(lib.EXIT.USAGE, "--no-log does not apply to improve.", "bad improve options")
        if action == "brief":
            if len(extra) != 1 or extra[0] not in ("researcher", "builder"):
                return _usage()
        elif extra:
            return _usage()
        suite = options.get("--suite")
        if action == "decide" and suite not in ("ok", "failed"):
            _fail(lib.EXIT.USAGE, "--suite ok|failed is required.", "suite result missing")
        state["log"] = True
        ctx = _load_context(set_id, state, options.get("--build"))
        if action == "start":
            return improve_start(ctx)
        if action == "next":
            return improve_next(ctx)
        if action == "decide":
            return improve_decide(ctx, suite)
        if action == "status":
            return improve_status(ctx)
        if action == "report":
            return improve_report(ctx)
        return improve_brief(ctx, extra[0])
    return _usage()


def main(argv=None):
    """Entry point from factory.py: `argv` is what follows the word `eval`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    state = {"build": None, "log": True}
    try:
        return _main(argv, state)
    except lib.FactoryError as exc:
        sys.stderr.write(lib.redact(exc.line()) + "\n")
        if state["build"] is not None and state["log"] and exc.code in (
                lib.EXIT.USAGE, lib.EXIT.MISSING, lib.EXIT.EMPTY):
            lib.record_error(state["build"].dir, "eval", exc.code, lib.redact(exc.reason))
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
