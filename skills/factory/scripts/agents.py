#!/usr/bin/env python3
"""factory run, step, wait, gate and check: logging that happens by itself.

    run    wrap any program so its start, output and end are logged (SPEC 4.4)
    step   run a command the project's settings define (SPEC 4.4a)
    wait   the wake timer: block until something changes (SPEC 4.5)
    gate   ask the owner a decision and measure the wait (SPEC 4.6)
    check  find agent calls that were missed or never finished (SPEC 4.7)

factory.py imports this file lazily and calls main(argv) with the command name
as the first argument. Each command is also
available as cmd_run, cmd_step, cmd_wait, cmd_gate and cmd_check.

Python 3.9, standard library only. Nothing here deletes or rewrites a file.
"""

import argparse
import bisect
import codecs
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import factorylib as lib  # noqa: E402

COMMANDS = ("run", "step", "wait", "gate", "check")

ENV_FAILURE_RE = re.compile(
    r"(?i)usage limit|rate limit|quota|not logged in|unauthorized|ENOTFOUND|"
    r"network is unreachable|could not resolve host")
ID_TOKEN_RE = re.compile(r"\b(AC|R|T|N|F|M|O)-?\d+\b|\bT-[A-Z]+-\d+\b|§\s*\d")
TARGET_RE = re.compile(r"^\s*(>=|<=|==|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
QUESTION_LIMIT = 300
CMD_TEXT_LIMIT = 200
TAIL_LIMIT = 200000
CONNECTOR_NOTICE_LIMIT_S = 300


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """Argument errors become plain `factory:` lines with exit 2, never a usage dump."""

    def error(self, message):
        raise lib.FactoryError(lib.EXIT.USAGE, "factory: %s (try: factory %s --help)" % (
            message, self.prog.replace("factory ", "", 1)), "invalid arguments")


def _parser(prog):
    return _Parser(prog="factory " + prog, allow_abbrev=False)


def _fail(code, message, reason=None):
    raise lib.FactoryError(code, "factory: " + message, reason)


def _config():
    return lib.load_config(Path(os.getcwd()))[0]


def _number(value):
    """int when whole, else float (for values written to the log)."""
    return int(value) if float(value).is_integer() else value


def _minutes(seconds):
    return lib.words_for_duration(max(0, int(seconds)))


def _labels(spans):
    """{piece id: latest plain piece name} over every line of the log."""
    found = {}
    for span in spans:
        node, label = span.get("node"), span.get("node_label")
        if isinstance(node, str) and isinstance(label, str) and label:
            found[node] = label
    return found


def _who(role, node, labels, command=False, node_label=None):
    """`Builder on Greeting flag` (SPEC 5.1 wording, no ids unless the name is unknown)."""
    text = lib.role_label(role)
    if command:
        text += " command"
    label = node_label or (labels.get(node) if isinstance(node, str) else None)
    if label:
        return "%s on %s" % (text, label)
    if isinstance(node, str) and node:
        return "%s on %s [%s]" % (text, lib.UNRECORDED_PIECE, node)
    return text


def _stderr(text):
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except (OSError, ValueError):
        pass


def _read_prompt(path, what="--input"):
    target = Path(path)
    if not target.is_file():
        _fail(lib.EXIT.MISSING, "%s file not found: %s" % (what, path), "input file not found")
    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _fail(lib.EXIT.MISSING, "%s file can't be read: %s" % (what, exc.strerror or exc),
              "input file unreadable")
    if not text:
        _fail(lib.EXIT.EMPTY, "%s file is empty: %s" % (what, path), "input file is empty")
    return text


def _call_try(call, given=None):
    if given is not None:
        return given
    match = re.search(r"\.(\d+)$", call or "")
    return int(match.group(1)) if match else 1


# ---------------------------------------------------------------------------
# expected.jsonl (SPEC 4.7)
# ---------------------------------------------------------------------------

def _expected_path(build_dir):
    return Path(build_dir) / "expected.jsonl"


def _add_expected(build_dir, entry):
    """Append `entry` unless its call id is already there. True when a line was written."""
    path = str(_expected_path(build_dir))
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        size = os.fstat(fd).st_size
        raw = os.pread(fd, size, 0) if size else b""
        for line in raw.decode("utf-8", "replace").split("\n"):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and value.get("call") == entry["call"]:
                return False
        data = (json.dumps(entry, ensure_ascii=True) + "\n").encode("utf-8")
        if raw and not raw.endswith(b"\n"):
            data = b"\n" + data
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        return True
    finally:
        os.close(fd)


def _expected_entry(call, node, role, attempt, added_by):
    call, node, role = lib.redact(call), lib.redact(node or ""), lib.redact(role or "")
    entry = {"call": call, "node": node, "role": role, "try": _call_try(call, attempt),
             "added": lib.now()}
    if added_by:
        entry["added_by"] = added_by
    return entry


def _load_expected(build_dir):
    """The expected entries (distinct calls, first one wins). Raises exit 4 or 2."""
    path = _expected_path(build_dir)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = None
    entries = []
    if text is not None:
        for number, raw in enumerate(text.split("\n"), 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except ValueError:
                value = None
            if not (isinstance(value, dict) and all(
                    isinstance(value.get(key), str) for key in ("call", "node", "role"))):
                _fail(lib.EXIT.USAGE, "expected.jsonl line %d is not a record with a call, a piece and "
                      "a role. Fix or remove that line." % number, "expected list has a bad line")
            entries.append(value)
    if not entries:
        _fail(lib.EXIT.EMPTY, "this build has no list of expected agent calls (expected.jsonl is missing "
              "or empty). An empty list proves nothing: add calls with 'factory check --add', or start "
              "the build with 'factory new --from-graph'.", "expected list is missing or empty")
    seen = set()
    distinct = []
    for entry in entries:
        if entry["call"] not in seen:
            seen.add(entry["call"])
            distinct.append(entry)
    return distinct


# ---------------------------------------------------------------------------
# running a program (SPEC 4.4)
# ---------------------------------------------------------------------------

class _Interrupted(Exception):
    def __init__(self, signum):
        Exception.__init__(self, signum)
        self.signum = signum


def _group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _signal_group(pgid, signum):
    try:
        os.killpg(pgid, signum)
    except OSError:
        pass


def _stop_group(process, grace):
    """SIGTERM the whole process group, SIGKILL whatever is left after `grace` seconds."""
    pgid = process.pid
    _signal_group(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        if process.poll() is not None and not _group_alive(pgid):
            break
        time.sleep(0.01)
    _signal_group(pgid, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


class _Capture(object):
    """Streams a program's output to its file and to the caller, keeping a bounded tail."""

    def __init__(self, stream, out_path):
        self.stream = stream
        self.out = open(str(out_path), "a", encoding="utf-8")
        self.chars = 0
        self.tail = ""
        self.echo = True
        self.thread = threading.Thread(target=self._pump)
        self.thread.daemon = True
        self.thread.start()

    def _emit(self, text):
        """Write text that has already been through factorylib.redact."""
        if not text:
            return
        self.out.write(text)
        self.out.flush()
        self.chars += len(text)
        self.tail = (self.tail + text)[-TAIL_LIMIT:]
        if self.echo:
            try:
                sys.stdout.write(text)
                sys.stdout.flush()
            except (OSError, ValueError):
                self.echo = False

    # ---- the cut rule (try 4) ------------------------------------------------------------
    # Text is redacted with factorylib.redact one chunk at a time. A chunk may end anywhere
    # (a newline, or a fixed distance from the end of a long run); what makes that safe is a
    # small state carried from one chunk to the next, derived from the patterns themselves:
    #   * key state: the text so far ends with "<key> \s*" or "<key> \s* [=:] \s*" (the kept
    #     part of an assignment). It is carried as a short synthetic prefix ("password" or
    #     "password=") that is redacted with the next chunk and not written, so a value of any
    #     distance from its key is still replaced. Nothing is held for whitespace runs.
    #   * value state: a chunk ended inside an assignment value already replaced. It is carried
    #     as the key, "=", then a run of placeholder characters, so redact() itself decides how far the value reaches (a private
    #     key header inside a value joins the runs around it); the replaced assignment that
    #     prefix turns into is not written again.
    #   * token state: a chunk ended inside a token (sk-, ghp_, ...) already replaced. It is
    #     carried as the token's own head, filler up to its minimum length and its last 64 real
    #     chars, so redact() decides where it ends and which earlier-priority token starts in it.
    #   * a cut never falls inside a key word, a token shorter than its minimum, or a value
    #     shorter than 8 characters; it moves back to their start (at most a few dozen chars).
    #   * a private key header ("-----BEGIN [A-Z ]*") is held up to 4,096 chars; a longer one
    #     is written as [REDACTED] and carried as "-----BEGIN " plus its last 64 chars (after
    #     the value prefix when it sits inside an assignment value), across any number of reads.
    # Every read scans only the bytes still held (at most about 128 KB), so time is linear and
    # memory is bounded whatever the output looks like.

    _SOFT = 65536           # a line longer than this is cut without waiting for its newline
    _KEEP = 64              # chars kept back at a forced cut (> longest minimum token length)
    _HEADER_HOLD = 4096     # longest unfinished private key header held before redacting it
    _CTX = {1: ("password", 8), 2: ("password=", 9),
            3: ("password=" + "#" * 8, len("password=") + len(lib.REDACTED))}

    _patterns = None

    @classmethod
    def _rules(cls):
        """Classify factorylib's patterns once: unlimited tail class, header, or fixed size."""
        if cls._patterns is not None:
            return cls._patterns
        tokens = []
        header_partial = None
        for _name, pattern in lib._SECRET_PATTERNS:
            source = pattern.pattern
            tail = re.search(r"(\[[^\]]*\])\{\d+,\}\Z", source)
            if source.startswith("-----BEGIN") and "PRIVATE" in source:
                tokens.append((pattern, "header", None))
                header_partial = re.compile(source.split("PRIVATE")[0])
            elif tail:
                cls_ = re.compile(tail.group(1))
                filler = next(c for c in "A0a_" if cls_.match(c))
                count = int(re.search(r"\{(\d+),\}\Z", source).group(1))
                head = re.compile(source[:tail.start()])
                tokens.append((pattern, "tail", (head, filler * count)))
            else:
                tokens.append((pattern, "fixed", None))
        keys = re.search(r"\(\?:([^()]*(?:\[[^\]]*\][^()]*)*)\)", lib._ASSIGNMENT_RE.pattern)
        words = keys.group(1) if keys else r"password|passwd|secret|token|api[_-]?key"
        cls._patterns = {
            "tokens": tokens,
            "header_partial": header_partial,
            "key": re.compile(r"(?i)(?:%s)" % words),
            "key_end": re.compile(r"(?i)(?:%s)\Z" % words),
            "header_lit": header_partial.pattern.split("[")[0] if header_partial else "",
        }
        return cls._patterns

    @classmethod
    def _key_state(cls, text):
        """2 if `text` ends with key \\s* [=:] \\s*, 1 if with key \\s*, else 0."""
        rules = cls._rules()
        text = text.rstrip()
        state = 1
        if text and text[-1] in "=:":
            text = text[:-1].rstrip()
            state = 2
        if rules["key_end"].search(text, max(0, len(text) - 16)):
            return state
        return 0

    @classmethod
    def _view_spans(cls, buf):
        """Secret spans of `buf` exactly as factorylib.redact sees them, in `buf` positions.

        redact replaces the token patterns one after another (each only where nothing was
        replaced yet), then runs the assignment pattern over that result, so a value can run
        through a replaced private key header. Replay that, and map assignment matches back."""
        rules = cls._rules()
        spans = []
        free = [(0, len(buf))]
        for pattern, kind, tail in rules["tokens"]:
            next_free = []
            for lo, hi in free:
                at = lo
                for m in pattern.finditer(buf, lo, hi):
                    spans.append((m.start(), m.end(), kind, pattern, tail, None))
                    if m.start() > at:
                        next_free.append((at, m.start()))
                    at = m.end()
                if hi > at:
                    next_free.append((at, hi))
            free = next_free
        replaced = sorted((s[0], s[1]) for s in spans)
        parts, starts_t, ends_t, raw = [], [], [], []
        at = t = 0
        for lo, hi in replaced:
            parts.append(buf[at:lo])
            t += lo - at
            starts_t.append(t)
            parts.append(lib.REDACTED)
            t += len(lib.REDACTED)
            ends_t.append(t)
            raw.append((lo, hi))
            at = hi
        parts.append(buf[at:])
        view = "".join(parts)

        def to_raw(pos, inner_end):
            i = bisect.bisect_right(starts_t, pos) - 1
            if i < 0:
                return pos
            if pos < ends_t[i]:
                return raw[i][1] if (inner_end and pos > starts_t[i]) else raw[i][0]
            return raw[i][1] + (pos - ends_t[i])

        for m in lib._ASSIGNMENT_RE.finditer(view):
            if m.group(2).startswith(lib.REDACTED):
                continue
            key_len = rules["key"].match(view, m.start()).end() - m.start()
            start = to_raw(m.start(), False)
            spans.append((start, to_raw(m.end(), True), "assign", None, None,
                          (start + key_len, to_raw(m.start(2), False))))
        for m in rules["key"].finditer(buf):
            spans.append((m.start(), m.end(), "fixed", None, None, None))
        return spans

    @classmethod
    def _plan(cls, buf, lead):
        """Decide the next chunk of `buf` (whose first `lead` chars are a synthetic key prefix).

        Returns (cut, end, extra, carry, value): write redact(buf[:end]) minus the prefix,
        then `extra` (nothing at all when end is 0); continue from buf[cut:]. `carry` is
        (prefix, strip) when the cut fell inside a replaced token or private key header: the
        prefix goes in front of buf[cut:] so redact() decides how far it reaches; `value` is
        True when buf[cut:] continues an assignment value already replaced.
        cut <= lead means hold everything for now."""
        rules = cls._rules()
        n = len(buf)
        cut = buf.rfind("\n") + 1
        if n - max(cut, lead) > cls._SOFT:
            cut = n - cls._KEEP
        if cut <= lead:
            return 0, 0, "", None, False
        spans = cls._view_spans(buf)
        if rules["header_partial"] is not None:
            done = set(s[0] for s in spans if s[2] == "header")
            for m in rules["header_partial"].finditer(buf):
                if m.end() == n and m.start() not in done:
                    spans.append((m.start(), n, "open", None, None, None))
        spans.sort(key=lambda s: s[0])
        skip = None
        value = False
        moved = True
        while moved:
            moved = False
            skip = None
            value = False
            for start, end, kind, pattern, tail, extra in spans:
                if start >= cut:
                    break
                if end <= cut:
                    continue
                new = cut
                if kind == "tail":
                    if pattern.fullmatch(buf, start, cut):
                        head, filler = tail
                        h = head.match(buf, start).end()
                        skip = (buf[start:h] + filler + buf[max(h, cut - cls._KEEP):cut], None)
                    else:
                        new = start
                elif kind == "assign":
                    key_end, value_start = extra
                    if cut < key_end:
                        new = start
                    elif cut > value_start:
                        if cut - value_start >= 8:
                            value = True
                        else:
                            new = value_start
                elif kind == "header":
                    if cut - start > cls._HEADER_HOLD:
                        inside = any(s[2] == "assign" and s[5][1] < start < s[1] for s in spans)
                        return end, end, "", None, inside
                    new = start
                elif kind == "open":
                    if cut - start > cls._HEADER_HOLD:
                        lit = len(rules["header_lit"])
                        hdr = buf[start:start + lit] + buf[max(start + lit, n - cls._KEEP):n]
                        owner = [s for s in spans if s[2] == "assign" and s[5][1] < start <= s[1]]
                        if owner:
                            end_at = min(s[5][1] for s in owner)
                            ctx = cls._CTX[3][0]
                            carry = (ctx + hdr, cls._CTX[3][1])
                        else:
                            end_at, carry = start, (hdr, None)
                        if end_at <= lead:
                            return n, 0, "", carry, False
                        return n, end_at, lib.REDACTED, carry, False
                    new = start
                else:
                    new = start
                if new != cut:
                    cut = new
                    moved = True
                    break
        if cut <= lead:
            return 0, 0, "", None, False
        if value:
            skip = None
        return cut, cut, "", skip, value

    def _pump(self):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        buf = ""
        lead = 0          # chars of synthetic prefix at the front of buf
        strip = 0         # chars its redacted form takes at the front of the output
        read = getattr(self.stream, "read1", self.stream.read)

        def cleaned(text, prefix, strip):
            out = lib.redact(text)
            if strip is not None:
                return out[strip:]
            # A carried token or header: its replacement leads the output when redact
            # still sees it; otherwise the prefix itself is there, unchanged.
            if out.startswith(lib.REDACTED):
                return out[len(lib.REDACTED):]
            if out.startswith(prefix):
                return out[len(prefix):]
            return out

        try:
            while True:
                raw = read(65536)
                if not raw:
                    break
                text = decoder.decode(raw)
                buf += text
                if "\n" not in text and len(buf) - lead <= self._SOFT:
                    continue
                while True:
                    cut, end, extra, carry, value = self._plan(buf, lead)
                    if cut <= lead:
                        break
                    if end > 0:
                        self._emit(cleaned(buf[:end], buf[:lead], strip) + extra)
                    rest = buf[cut:]
                    if carry is not None and not value:
                        ctx, strip = carry
                    else:
                        state = 3 if value else self._key_state(buf[:cut])
                        ctx, strip = self._CTX.get(state, ("", 0))
                    buf, lead = ctx + rest, len(ctx)
                    if "\n" not in rest and len(rest) <= self._SOFT:
                        break
            buf += decoder.decode(b"", True)
            self._emit(cleaned(buf, buf[:lead], strip))
        except (OSError, ValueError):
            pass

    def finish(self, process, wait_s=2.0):
        self.thread.join(wait_s)
        if self.thread.is_alive():
            # A leftover descendant still holds the pipe: end the group so the wrapper can return.
            _signal_group(process.pid, signal.SIGKILL)
            self.thread.join(2.0)
        try:
            self.out.close()
        except OSError:
            pass


def _feed(stream, data):
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


def _out_file(build_dir, span_id):
    folder = Path(build_dir) / "messages"
    folder.mkdir(parents=True, exist_ok=True)
    name = "%s.out.md" % span_id
    number = 2
    while True:
        try:
            with open(str(folder / name), "x", encoding="utf-8"):
                pass
            return folder / name, "messages/" + name
        except FileExistsError:
            name = "%s.out-%d.md" % (span_id, number)
            number += 1


def _program_text(spec):
    if spec.get("shell") is not None:
        return spec["shell"]
    argv = spec["argv"]
    text = argv[0] if len(argv) == 1 else "%s %s" % (argv[0], argv[1])
    return text


def _execute(build, spec, finalize=None):
    """Log and run one program (SPEC 4.4). Returns the wrapper's exit code.

    spec keys: kind, actor, call, node, label, iteration, model, effort, runner, step,
    argv or shell, input_text, input_as_arg, timeout, cwd, extra (fields for the start line).
    """
    cfg = _config()
    timers = lib.timers_of(cfg)
    kind = spec["kind"]
    argv = list(spec["argv"]) if spec.get("argv") is not None else None
    start_fields = {
        "kind": kind, "actor": spec["actor"], "status": "running", "start": lib.now(),
        "cmd": _program_text(spec)[:CMD_TEXT_LIMIT], "call": spec.get("call"),
        "node": spec.get("node"), "node_label": spec.get("label"), "iteration": spec.get("iteration"),
        "model": spec.get("model"), "effort": spec.get("effort"), "runner": spec.get("runner"),
        "step": spec.get("step"),
    }
    start_fields.update(spec.get("extra") or {})
    input_text = spec.get("input_text")

    with lib.transaction(build.dir) as tx:
        if kind == "agent_call" and spec.get("call"):
            _add_expected(build.dir, _expected_entry(
                spec["call"], spec.get("node"), spec["actor"], spec.get("iteration"), "run"))
        span_id = tx.add(start_fields, {"in": input_text} if input_text is not None else None)

    out_path, out_ref = _out_file(build.dir, span_id)
    started = time.monotonic()
    state = {"interrupt": None, "armed": True}

    def on_signal(signum, _frame):
        if state["armed"] and state["interrupt"] is None:
            state["interrupt"] = signum
            raise _Interrupted(signum)

    saved = {}
    for name in ("SIGINT", "SIGTERM", "SIGHUP"):
        try:
            saved[getattr(signal, name)] = signal.signal(getattr(signal, name), on_signal)
        except (ValueError, OSError, AttributeError):
            pass

    process = None
    capture = None
    timed_out = False
    interrupted = None
    launch_error = None
    code = None
    try:
        try:
            feed = input_text is not None and not spec.get("input_as_arg")
            command = spec["shell"] if spec.get("shell") is not None else (
                argv + [input_text] if spec.get("input_as_arg") and input_text is not None else argv)
            process = subprocess.Popen(
                command, shell=spec.get("shell") is not None, cwd=spec.get("cwd"),
                stdin=subprocess.PIPE if feed else subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        except FileNotFoundError:
            launch_error = ("program not found: %s" % argv[0], 127)
        except OSError as exc:
            launch_error = ("program could not be started: %s" % (exc.strerror or exc), 126)
        if process is not None:
            capture = _Capture(process.stdout, out_path)
            if feed:
                writer = threading.Thread(target=_feed, args=(process.stdin, input_text.encode("utf-8")))
                writer.daemon = True
                writer.start()
            try:
                remaining = spec["timeout"] - (time.monotonic() - started)
                try:
                    process.wait(timeout=max(0.0, remaining))
                except subprocess.TimeoutExpired:
                    timed_out = True
            except _Interrupted as exc:
                interrupted = exc.signum
            if timed_out or interrupted is not None:
                state["armed"] = False
                _stop_group(process, timers["kill_grace_s"])
            capture.finish(process)
            code = process.returncode
    except _Interrupted as exc:
        interrupted = exc.signum
        if process is not None:
            _stop_group(process, timers["kill_grace_s"])
            if capture is not None:
                capture.finish(process)
    finally:
        state["armed"] = False
        for signum, handler in saved.items():
            try:
                signal.signal(signum, handler)
            except (ValueError, OSError):
                pass

    elapsed = time.monotonic() - started
    chars = capture.chars if capture is not None else 0
    tail = capture.tail if capture is not None else ""
    fields = {"kind": kind, "end": lib.now(), "duration_s": _number(round(elapsed, 1)),
              "output_ref": out_ref, "output_chars": chars}
    if spec.get("step"):
        fields["step"] = spec["step"]
    if launch_error is not None:
        message, exit_code = launch_error
        _stderr("factory: " + message)
        fields.update({"status": "failed", "failure_class": "env-tooling", "notes": message})
    elif interrupted is not None:
        exit_code = 128 + interrupted
        fields.update({"status": "stopped", "exit_code": exit_code,
                       "notes": "stopped by a %s signal" % signal.Signals(interrupted).name})
    elif timed_out:
        exit_code = lib.EXIT.TIMEOUT
        _stderr("factory: stopped after %gs, its time limit" % spec["timeout"])
        fields.update({
            "status": "failed", "exit_code": exit_code, "notes": "timed out after %gs" % spec["timeout"],
            "failure_class": "model-stall" if kind == "agent_call" else "env-tooling"})
    else:
        exit_code = code if code >= 0 else 128 - code
        fields["exit_code"] = exit_code
        if exit_code == 0:
            fields["status"] = "done"
            if chars == 0:
                fields["warn"] = True
                _stderr("factory: warning: %s exited 0 but printed nothing" % _program_text(spec).split(" ")[0])
        else:
            fields["status"] = "failed"
            fields["failure_class"] = "env-tooling" if ENV_FAILURE_RE.search(tail) else "impl-bug"
        if finalize is not None:
            exit_code = finalize(exit_code, tail, fields)
    try:
        fields["span_id"] = span_id
        lib.append(build.dir, fields)
    except (OSError, lib.FactoryError) as exc:
        _stderr("factory: the program finished but its closing line could not be written (%s)" % exc)
    return exit_code


# ---------------------------------------------------------------------------
# factory run
# ---------------------------------------------------------------------------

def _may_keep_data(cfg, runner, model):
    """True when a call may be kept by its vendor (SPEC 2, data rule)."""
    if not runner:
        return False
    entry = (cfg.get("runners") or {}).get(runner) or {}
    if not entry.get("retains_data"):
        return False
    for prefix in entry.get("private_safe_prefixes") or []:
        if model and str(model).startswith(str(prefix)):
            return False
    return True


def _under_public_root(paths, roots):
    resolved = []
    for root in roots or []:
        try:
            resolved.append(Path(os.path.expanduser(str(root))).resolve())
        except OSError:
            continue
    if not resolved:
        return False
    for path in paths:
        try:
            target = Path(path).resolve()
        except OSError:
            return False
        if not any(target == root or root in target.parents for root in resolved):
            return False
    return True


def _data_rule(cfg, args, input_text):
    """Extra start-line fields for a call that may keep data; refuses (exit 2) when not proven."""
    if not _may_keep_data(cfg, args.runner, args.model):
        return {}
    name = args.model or args.runner
    if not args.non_private:
        _fail(lib.EXIT.USAGE, "%s may keep what it is sent. Only non-private material may go to it. "
              "Add --non-private if this input is public." % name,
              "a model that may keep data needs --non-private")
    if input_text is None:
        _fail(lib.EXIT.USAGE, "%s may keep what it is sent, so the call needs --input: the file is "
              "checked before anything is sent." % name, "a model that may keep data needs an input file")
    # The program runs in --cwd (or the caller's folder) and can read what is there, so that
    # folder must itself be public, whatever the input proves.
    workdir = args.cwd if args.cwd else os.getcwd()
    if not _under_public_root([workdir], cfg.get("public_roots")):
        _fail(lib.EXIT.USAGE, "this call would run in %s, which is not under a public folder, and %s "
              "may keep what it is sent. Not sent. Run it from a public folder (--cwd)." % (workdir, name),
              "working folder is not public")
    if _under_public_root([args.input], cfg.get("public_roots")):
        return {"data_class": "non-private", "data_proof": "public-root"}
    found = lib.scan_text(input_text, cfg.get("private_patterns_file"))
    if found:
        names = []
        for item in found:
            if item not in names:
                names.append(item)
        _fail(lib.EXIT.USAGE, "this input is not under a public folder and the privacy scan found %d "
              "things (%s). Not sent." % (len(found), ", ".join(names)),
              "input is not public and the privacy scan found private-looking text")
    return {"data_class": "non-private", "data_proof": "scan-clean"}


def _positive_timeout(value):
    if value is None:
        return None
    if not (value > 0) or value == float("inf"):
        _fail(lib.EXIT.USAGE, "--timeout must be a number of seconds above 0", "invalid --timeout")
    return value


def cmd_run(argv):
    argv = list(argv)
    if "--" in argv:
        split = argv.index("--")
        flags, program = argv[:split], argv[split + 1:]
    else:
        flags, program = argv, []
    p = _parser("run")
    p.add_argument("--actor", required=True)
    p.add_argument("--call")
    p.add_argument("--node")
    p.add_argument("--label")
    p.add_argument("--iteration", type=int)
    p.add_argument("--model")
    p.add_argument("--effort")
    p.add_argument("--runner")
    p.add_argument("--kind", default="agent_call", choices=("agent_call", "command"))
    p.add_argument("--timeout", type=float)
    p.add_argument("--input")
    p.add_argument("--input-as-arg", dest="input_as_arg", action="store_true")
    p.add_argument("--non-private", dest="non_private", action="store_true")
    p.add_argument("--cwd")
    p.add_argument("--build")
    args = p.parse_args(flags)

    if not program:
        _fail(lib.EXIT.USAGE, "nothing to run: put the program after --, for example: "
              "factory run --actor maker --call N1.maker.1 --input prompt.md -- codex exec", "no program given")
    if args.kind == "agent_call" and (not args.call or args.input is None):
        _fail(lib.EXIT.USAGE, "an agent call needs --call <id> and --input <prompt file>, so what it was "
              "told is on record.", "agent call without call id or input")
    if args.iteration is not None and args.iteration < 1:
        _fail(lib.EXIT.USAGE, "--iteration must be 1 or more", "invalid --iteration")
    if args.input_as_arg and args.input is None:
        _fail(lib.EXIT.USAGE, "--input-as-arg needs --input <prompt file>", "--input-as-arg without input")
    timeout = _positive_timeout(args.timeout)
    build = lib.select_build(args)
    cfg = _config()
    input_text = _read_prompt(args.input) if args.input is not None else None
    extra = _data_rule(cfg, args, input_text)
    if args.cwd and not Path(args.cwd).is_dir():
        _fail(lib.EXIT.MISSING, "--cwd folder not found: %s" % args.cwd, "--cwd folder not found")
    if timeout is None:
        timeout = lib.timers_of(cfg)["default_cmd_timeout_s"]
    return _execute(build, {
        "kind": args.kind, "actor": args.actor, "call": args.call, "node": args.node,
        "label": args.label, "iteration": args.iteration, "model": args.model, "effort": args.effort,
        "runner": args.runner, "argv": program, "input_text": input_text,
        "input_as_arg": args.input_as_arg, "timeout": timeout, "cwd": args.cwd, "extra": extra})


# ---------------------------------------------------------------------------
# factory step
# ---------------------------------------------------------------------------

def _step_entries(cfg):
    """{step name: settings entry} for every command the project defines."""
    found = {}
    tests = cfg.get("tests")
    if isinstance(tests, dict):
        for key, entry in tests.items():
            found["tests.%s" % key] = entry
    evals = cfg.get("evals")
    if isinstance(evals, dict):
        for entry in evals.get("metrics") or []:
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                found["evals.%s" % entry["id"]] = entry
    release = cfg.get("release")
    if isinstance(release, dict):
        for group in ("preflight", "steps", "smoke"):
            for entry in release.get(group) or []:
                if isinstance(entry, dict) and isinstance(entry.get("name"), str):
                    found["release.%s.%s" % (group, entry["name"])] = entry
    return found


def _eval_finalizer(entry):
    target = entry.get("target")
    parsed = None
    if target is not None:
        match = TARGET_RE.match(str(target))
        if not match:
            _fail(lib.EXIT.USAGE, 'the target "%s" for this measure is not like ">=0.85" '
                  "(>=, >, <=, <, == followed by a number)" % target, "eval target is not valid")
        parsed = (match.group(1), float(match.group(2)))

    def finalize(exit_code, tail, fields):
        if exit_code != 0:
            return exit_code
        lines = [line.strip() for line in tail.splitlines() if line.strip()]
        value = None
        if lines:
            try:
                value = float(lines[-1])
                if value != value or value in (float("inf"), float("-inf")):
                    value = None
            except ValueError:
                value = None
        if value is None:
            fields.update({"status": "failed", "failure_class": "env-tooling",
                           "notes": "the last line of the output is not a number"})
            _stderr("factory: the measure printed no number on its last line, so it counts as failed")
            return lib.EXIT.EMPTY
        fields["value"] = _number(value)
        if parsed is not None:
            op, goal = parsed
            met = {">=": value >= goal, ">": value > goal, "<=": value <= goal,
                   "<": value < goal, "==": value == goal}[op]
            fields["target"] = str(target).strip()
            fields["target_met"] = met
            if not met:
                fields.update({"status": "failed", "failure_class": "impl-bug",
                               "notes": "target not met"})
                return lib.EXIT.NO
        return exit_code

    return finalize


def cmd_step(argv):
    p = _parser("step")
    p.add_argument("name")
    p.add_argument("--build")
    args = p.parse_args(list(argv))
    cwd = Path(os.getcwd())
    if not (cwd / "factory.json").is_file():
        _fail(lib.EXIT.MISSING, "this folder has no factory.json, so there are no project steps. "
              "Run 'factory init' in the project folder.", "no factory.json here")
    cfg = _config()
    entries = _step_entries(cfg)
    entry = entries.get(args.name)
    if entry is None:
        known = ", ".join(sorted(entries)) or "none are set in factory.json"
        _fail(lib.EXIT.USAGE, "this project has no step called \"%s\". Steps that exist: %s"
              % (args.name, known), "unknown step name")
    command = entry.get("cmd")
    if not isinstance(command, str) or not command.strip():
        _fail(lib.EXIT.USAGE, "the step \"%s\" has no command in factory.json" % args.name,
              "step has no command")
    timeout = entry.get("timeout_s")
    if not lib._is_number(timeout) or timeout <= 0:
        _fail(lib.EXIT.USAGE, "the step \"%s\" has no time limit (timeout_s) in factory.json" % args.name,
              "step has no time limit")
    finalize = _eval_finalizer(entry) if args.name.startswith("evals.") else None
    build = lib.select_build(args)
    return _execute(build, {
        "kind": "command", "actor": "orchestrator", "step": args.name, "shell": command,
        "timeout": float(timeout), "cwd": str(cwd)}, finalize)


# ---------------------------------------------------------------------------
# factory wait
# ---------------------------------------------------------------------------

_CLOSED = ("done", "failed", "stopped")


class _Watch(object):
    """Follows a build's log by reading only the bytes appended since the last look."""

    def __init__(self, path):
        self.path = str(path)
        self.offset = 0
        self.spans = {}
        self.fed = False

    def _apply(self, line):
        """Merge one log line. Returns (is_new, previous_status) for the span it names."""
        span_id = line.get("span_id")
        previous = self.spans.get(span_id)
        was = previous.get("status") if previous is not None else None
        merged = previous if previous is not None else {"span_id": span_id}
        for key, value in line.items():
            if value is None or key == "start" and "start" in merged:
                continue
            merged[key] = value
        status = merged.get("status")
        if isinstance(status, str):
            merged["status"] = (status.split() or ["running"])[0].lower()
        stamp = lib.to_epoch(line.get("ts"))
        if stamp is not None:
            merged["_last"] = max(merged.get("_last", 0), stamp)
        self.spans[span_id] = merged
        return previous is None, was

    def read(self):
        """Parse newly appended complete lines. Returns the list of (span, is_new, was_status)."""
        try:
            size = os.stat(self.path).st_size
        except OSError:
            return []
        if size == self.offset and self.fed:
            return []
        if size < self.offset:
            self.offset = 0
            self.spans = {}
        try:
            with open(self.path, "rb") as stream:
                stream.seek(self.offset)
                data = stream.read(max(0, size - self.offset))
        except OSError:
            return []
        self.fed = True
        cut = data.rfind(b"\n")
        if cut < 0:
            return []
        self.offset += cut + 1
        events = []
        for raw in data[:cut].split(b"\n"):
            try:
                line = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                continue
            if isinstance(line, dict) and isinstance(line.get("span_id"), str):
                is_new, was = self._apply(line)
                events.append((self.spans[line["span_id"]], is_new, was))
        return events

    def labels(self):
        return _labels(self.spans.values())

    def active(self):
        found = []
        for span in self.spans.values():
            if span.get("status") != "running":
                continue
            kind = span.get("kind")
            if kind in ("agent_call", "command") or (kind == "wait" and span.get("waiting_on") == "human"):
                found.append(span)
        return found


def _change_text(span, is_new, was, labels):
    kind = span.get("kind")
    status = span.get("status")
    if kind == "wait" and span.get("waiting_on") == "human":
        gate = span.get("gate") or "A decision"
        if is_new and status == "running":
            return "A question for you was opened: %s." % gate
        if status in _CLOSED and (is_new or was == "running"):
            return "Your answer was recorded: %s." % gate
        return None
    if kind == "phase":
        if is_new and status == "running":
            return "The phase changed to %s." % lib.phase_label(span.get("phase"))
        return None
    who = _who(span.get("actor"), span.get("node"), labels, kind == "command", span.get("node_label"))
    if is_new and status == "running":
        return "%s started." % who
    if status in _CLOSED and (is_new or was == "running"):
        word = {"done": "finished", "failed": "finished with a failure", "stopped": "was stopped"}[status]
        return "%s %s." % (who, word)
    return None


def _quiet_s(span, out_dir, now_value):
    last = span.get("_last")
    try:
        mtime = os.stat(os.path.join(out_dir, "%s.out.md" % span["span_id"])).st_mtime
        last = mtime if last is None else max(last, mtime)
    except OSError:
        pass
    return None if last is None else max(0, now_value - last)


def cmd_wait(argv):
    p = _parser("wait")
    p.add_argument("--timeout", type=float)
    p.add_argument("--build")
    args = p.parse_args(list(argv))
    build = lib.select_build(args)
    cfg = _config()
    timers = lib.timers_of(cfg)
    limit = _positive_timeout(args.timeout)
    if limit is None:
        limit = timers["wake_s"]
    poll = min(max(float(timers["poll_s"]), 0.01), 1.0)
    watch = _Watch(build.dir / "trace.jsonl")
    watch.read()
    if not watch.active():
        print("factory: nothing is running")
        return lib.EXIT.OK
    deadline = time.monotonic() + limit
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll, remaining))
        texts = []
        labels = None
        for span, is_new, was in watch.read():
            if labels is None:
                labels = watch.labels()
            text = _change_text(span, is_new, was, labels)
            if text:
                texts.append(text)
        if texts:
            print(" ".join(texts))
            return lib.EXIT.OK
    print("factory: nothing changed in %gs" % limit)
    labels = watch.labels()
    now_value = lib.now_epoch()
    out_dir = str(build.dir / "messages")
    for span in watch.active():
        start = lib.to_epoch(span.get("start"))
        running = "running %s" % _minutes(now_value - start) if start is not None else "running"
        if span.get("kind") == "wait":
            line = "  Waiting on you: %s, %s" % (span.get("gate") or "a decision", running)
        else:
            quiet = _quiet_s(span, out_dir, now_value)
            line = "  %s: %s%s" % (
                _who(span.get("actor"), span.get("node"), labels, span.get("kind") == "command",
                     span.get("node_label")), running,
                ", last output %s ago" % _minutes(quiet) if quiet is not None else "")
        print(line)
    return lib.EXIT.TIMEOUT


# ---------------------------------------------------------------------------
# factory gate
# ---------------------------------------------------------------------------

def _check_plain(label, text):
    if not text or not text.strip():
        _fail(lib.EXIT.USAGE, "the %s is empty. Write it as a plain sentence the owner can answer." % label,
              "gate %s is empty" % label)
    match = ID_TOKEN_RE.search(text)
    if match:
        _fail(lib.EXIT.USAGE, 'the %s contains "%s", which looks like an id the owner cannot read. '
              "Say it in plain words." % (label, match.group(0).strip()), "gate %s contains an id" % label)


def _gate_open(args):
    name = (args.name or "").strip()
    if not name:
        _fail(lib.EXIT.USAGE, "the gate needs a name, for example --name \"GATE A\"", "gate name is empty")
    _check_plain("question", args.question)
    _check_plain("recommendation", args.recommend)
    if len(args.question) > QUESTION_LIMIT:
        _fail(lib.EXIT.USAGE, "the question is too long (%d characters; the limit is %d). Make it shorter."
              % (len(args.question), QUESTION_LIMIT), "gate question is too long")
    file_text = _read_prompt(args.file, "--file") if args.file else None
    build = lib.select_build(args)
    cfg = _config()
    question = lib.redact(args.question.strip())
    recommend = lib.redact(args.recommend.strip())
    fields = {"kind": "wait", "actor": "orchestrator", "waiting_on": "human", "status": "running",
              "start": lib.now(), "gate": name, "question": question, "recommend": recommend}
    span_id = lib.append(build.dir, fields, {"in": file_text} if file_text is not None else None)
    print(span_id)
    sys.stdout.flush()
    if args.no_notify:
        return lib.EXIT.OK
    try:
        results = lib.notify(cfg, name, question, recommend)
    except Exception as exc:  # a notice must never lose the question
        results = {str(c): "failed: %s" % type(exc).__name__
                   for c in ((cfg.get("notify") or {}).get("channels") or [])}
    if not isinstance(results, dict):
        results = {}
    results = {str(key): str(value) for key, value in results.items()}
    try:
        lib.append(build.dir, dict(fields, span_id=span_id, notified=results))
    except (OSError, lib.FactoryError) as exc:
        _stderr("factory: warning: the notice result could not be written to the log (%s)" % exc)
    for channel, result in results.items():
        if result.startswith("failed"):
            _stderr("factory: warning: the %s notice did not go out (%s). The question is still in the log "
                    "and on the board." % (channel, result[len("failed"):].lstrip(": ") or "no reason given"))
    connector = (cfg.get("notify") or {}).get("connector")
    if results.get("connector") == "to send" and isinstance(connector, dict):
        print("Also send this through: %s" % connector.get("name"))
    return lib.EXIT.OK


def _gate_close(args):
    answer = (args.answer or "").strip()
    if not answer:
        _fail(lib.EXIT.USAGE, "the answer is empty. Record what the owner said.", "gate answer is empty")
    build = lib.select_build(args)
    with lib.transaction(build.dir) as tx:
        span = tx.span(args.span_id)
        if span is None or span.get("kind") != "wait":
            _fail(lib.EXIT.MISSING, "this build has no open question with that id: %s" % args.span_id,
                  "unknown question id")
        if span.get("status") != "running":
            _fail(lib.EXIT.NO, "that question already has an answer: %s" % args.span_id,
                  "question already answered")
        end = lib.now()
        closing = {"span_id": args.span_id, "status": "done", "end": end, "answer": answer}
        start = lib.to_epoch(span.get("start"))
        if start is not None:
            closing["duration_s"] = max(0, int(lib.to_epoch(end) - start))
        tx.add(closing)
    return lib.EXIT.OK


def _gate_sent(args):
    if args.channel != "connector":
        _fail(lib.EXIT.USAGE, "--channel must be connector (the only notice that is sent by hand)",
              "invalid --channel")
    build = lib.select_build(args)
    with lib.transaction(build.dir) as tx:
        span = tx.span(args.span_id)
        if span is None or span.get("kind") != "wait":
            _fail(lib.EXIT.MISSING, "this build has no question with that id: %s" % args.span_id,
                  "unknown question id")
        notified = dict(span.get("notified") or {})
        if notified.get("connector") is None:
            _fail(lib.EXIT.NO, "that question has no connector notice waiting to be sent",
                  "no connector notice to send")
        reason = (args.failed or "").strip()
        notified["connector"] = ("failed: %s" % reason[:160]) if args.failed is not None else "sent"
        tx.add({"span_id": args.span_id, "status": span.get("status") or "running", "notified": notified})
    return lib.EXIT.OK


def cmd_gate(argv):
    p = _parser("gate")
    sub = p.add_subparsers(dest="action", parser_class=_Parser)
    sub.required = True
    opened = sub.add_parser("open", allow_abbrev=False)
    opened.add_argument("--name", required=True)
    opened.add_argument("--question", default="")
    opened.add_argument("--recommend", default="")
    opened.add_argument("--file")
    opened.add_argument("--no-notify", dest="no_notify", action="store_true")
    opened.add_argument("--build")
    closed = sub.add_parser("close", allow_abbrev=False)
    closed.add_argument("span_id", metavar="question-id")
    closed.add_argument("--answer", default="")
    closed.add_argument("--build")
    sent = sub.add_parser("sent", allow_abbrev=False)
    sent.add_argument("span_id", metavar="question-id")
    sent.add_argument("--channel", required=True)
    sent.add_argument("--failed")
    sent.add_argument("--build")
    p.epilog = "\n".join("factory gate %s:\n%s" % (name, sub.choices[name].format_help())
                        for name in ("open", "close", "sent"))
    p.formatter_class = argparse.RawDescriptionHelpFormatter
    args = p.parse_args(list(argv))
    return {"open": _gate_open, "close": _gate_close, "sent": _gate_sent}[args.action](args)


# ---------------------------------------------------------------------------
# factory check
# ---------------------------------------------------------------------------

def _connector_findings(spans):
    found = []
    now_value = lib.now_epoch()
    for span in spans:
        notified = span.get("notified")
        if span.get("kind") == "wait" and isinstance(notified, dict) and notified.get("connector") == "to send":
            start = lib.to_epoch(span.get("start"))
            if start is not None and now_value - start > CONNECTOR_NOTICE_LIMIT_S:
                found.append("A notice was never sent through the connector: %s, %s ago"
                             % (span.get("gate") or "a decision", _minutes(now_value - start)))
    return found


def _check_add(args):
    if not args.node or not args.role:
        _fail(lib.EXIT.USAGE, "--add needs --node <piece id> and --role <role>", "--add without piece or role")
    call = args.add.strip()
    if not call or re.search(r"\s", call):
        _fail(lib.EXIT.USAGE, "the call id must be one word with no spaces", "invalid call id")
    if args.attempt is not None and args.attempt < 1:
        _fail(lib.EXIT.USAGE, "--try must be 1 or more", "invalid --try")
    build = lib.select_build(args)
    entry = _expected_entry(call, args.node, args.role, args.attempt, None)
    if not _add_expected(build.dir, entry):
        print("factory: %s is already on the expected list. Nothing was written." % entry["call"],
              file=sys.stderr)
        return lib.EXIT.NO
    print("added %s" % entry["call"])
    return lib.EXIT.OK


def cmd_check(argv):
    p = _parser("check")
    p.add_argument("--json", action="store_true")
    p.add_argument("--orphans-only", dest="orphans_only", action="store_true")
    p.add_argument("--add", metavar="CALL")
    p.add_argument("--node")
    p.add_argument("--role")
    p.add_argument("--try", dest="attempt", type=int)
    p.add_argument("--build")
    args = p.parse_args(list(argv))
    if args.add is not None:
        return _check_add(args)
    build = lib.select_build(args)
    cfg = _config()
    read = lib.read_build(build.dir)
    spans = read["spans"]
    unfinished = [item["text"] for item in lib.unfinished(read, lib.now(), cfg)]
    unfinished += _connector_findings(spans)

    missing, unplanned, duplicate = [], [], []
    counts = {"expected": 0, "logged": 0, "matched": 0, "missing": 0, "unplanned": 0,
              "duplicate": 0, "unfinished": len(unfinished)}
    if not args.orphans_only:
        expected = _load_expected(build.dir)
        labels = _labels(spans)
        agent_spans = [span for span in spans if span.get("kind") == "agent_call" and span.get("v", 1) == 1]
        planned = set(entry["call"] for entry in expected)
        by_call = {}
        for span in agent_spans:
            call = span.get("call")
            if isinstance(call, str) and call:
                by_call.setdefault(call, []).append(span)
        matched = 0
        for entry in expected:
            closed = [s for s in by_call.get(entry["call"], []) if s.get("status") in _CLOSED]
            if closed:
                matched += 1
                continue
            where = _who(entry["role"], entry["node"] or None, labels)
            attempt = entry.get("try")
            suffix = ", try %d" % attempt if lib._is_number(attempt) else ""
            missing.append("Expected but not logged: %s%s" % (where, suffix))
        for span in agent_spans:
            call = span.get("call")
            if not (isinstance(call, str) and call in planned):
                unplanned.append("Logged but not planned: %s" % _who(
                    span.get("actor"), span.get("node"), labels, False, span.get("node_label")))
        for call, group in by_call.items():
            if len(group) > 1:
                first = group[0]
                attempt = first.get("iteration")
                suffix = ", try %d" % attempt if lib._is_number(attempt) else ""
                duplicate.append("Duplicate entry: %s%s, logged %d times" % (_who(
                    first.get("actor"), first.get("node"), labels, False, first.get("node_label")),
                    suffix, len(group)))
        counts.update({"expected": len(expected), "logged": len(agent_spans), "matched": matched,
                       "missing": len(missing), "unplanned": len(unplanned), "duplicate": len(duplicate)})
    findings = missing + unplanned + duplicate + unfinished
    summary = ("Expected %(expected)d, logged %(logged)d, matched %(matched)d, missing %(missing)d, "
               "unplanned %(unplanned)d, duplicate %(duplicate)d, unfinished %(unfinished)d." % counts)
    if args.json:
        print(json.dumps({"ok": not findings, "counts": counts, "missing": missing,
                          "unplanned": unplanned, "duplicate": duplicate, "unfinished": unfinished}, indent=2))
    else:
        for line in findings:
            print(line)
        print(summary)
    return lib.EXIT.NO if findings else lib.EXIT.OK


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

HANDLERS = {"run": cmd_run, "step": cmd_step, "wait": cmd_wait, "gate": cmd_gate, "check": cmd_check}


def main(argv=None):
    """main(command, args...): the command name is the first argument, never guessed."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        _stderr("factory: no command given (one of: %s)" % ", ".join(COMMANDS))
        return lib.EXIT.USAGE
    try:
        return HANDLERS[argv[0]](argv[1:])
    except lib.FactoryError as exc:
        _stderr(exc.line())
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
