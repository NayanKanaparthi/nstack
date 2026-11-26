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

COMMANDS = ("run", "step", "wait", "gate", "check", "plain")

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

    def __init__(self, stream, out_path, echo=True):
        self.stream = stream
        self.out = open(str(out_path), "a", encoding="utf-8")
        self.chars = 0
        self.tail = ""
        self.echo = echo
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

    # ---- what gets written (factory-v1.1) ------------------------------------------------
    # Rule: output is written in units that end at a line end (\n or \r), and only at a line
    # end where the text before it is not an "open key": a key word of factorylib's assignment
    # pattern, then only whitespace, optionally one = or : and more whitespace. Each unit is
    # written as factorylib.redact(unit). Once a unit passes _CAP chars it is dropped instead,
    # up to its end; one "[output line withheld: N bytes]" line stands in for it.
    # Text still held when the program ends is redacted as a whole and written.
    #
    # Why written == redact(whole output), withheld units aside:
    #   * No secret token pattern matches \n or \r, and redact's replacements contain none,
    #     so the token passes of redact act on each line alone.
    #   * An assignment match is key \s* [=:] \s* value, the value being one \S run, which
    #     cannot hold a line end. A match that starts before a line end and ends after it
    #     therefore has only key, whitespace and at most one = or : before that line end,
    #     which is exactly the open-key test. Replaced tokens end in "]", so a key run seen in
    #     the token-replaced text is also in the raw text: testing raw text can only hold more.
    #   * So no match of redact(whole) crosses a unit end, and redact of each unit gives the
    #     same pieces as redact of the whole. Nothing is ever cut inside a line.

    _CAP = 1 << 20          # longest unit held before it is withheld (chars)
    _LINE_END = re.compile(r"[\r\n]")
    _NONSPACE = re.compile(r"\S")
    _KEY_END = re.compile(
        "(?i)(?:" + lib._ASSIGNMENT_RE.pattern.split("(?:", 1)[1].split(")", 1)[0] + r")\Z")

    @classmethod
    def _open(cls, text):
        """True if `text` ends with a key, whitespace, and optionally [=:] and whitespace."""
        tail = text.rstrip()
        if tail.endswith(("=", ":")):
            tail = tail[:-1].rstrip()
        return cls._KEY_END.search(tail[-16:]) is not None

    @staticmethod
    def _sig(text):
        """A short stand-in for `text` that gives the same _open answer as any text it ends.

        The test only looks at the last two whitespace-separated runs (key, then = or :) and
        at most 16 chars of each, so keep exactly that, plus one space for trailing space."""
        runs = text.rsplit(None, 2)[-2:]
        sig = " ".join(run[-16:] for run in runs)
        if text and text[-1].isspace():
            sig += " "
        return sig

    def _withheld(self, size):
        self._emit("[output line withheld: %d bytes]\n" % size)

    def _pump(self):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        held = ""         # text not yet written (normal mode)
        skipped = None    # bytes dropped so far while withholding a unit, else None
        sig = ""          # _sig of the unit being withheld
        read = getattr(self.stream, "read1", self.stream.read)
        done = False
        try:
            while not done:
                raw = read(65536)
                if raw:
                    text = decoder.decode(raw)
                else:
                    text, done = decoder.decode(b"", True), True
                if skipped is not None:
                    # Withholding: the unit ends at a line end where it is no longer open.
                    # Checked at the first line end after the next non-space char (whitespace
                    # cannot close an open key) and at the last line end of this read.
                    look = 0
                    if self._open(sig):
                        nonspace = self._NONSPACE.search(text)
                        look = nonspace.start() if nonspace else len(text)
                    first = self._LINE_END.search(text, look)
                    last = max(text.rfind("\n"), text.rfind("\r")) + 1
                    end = None
                    for at in ([first.end(), last] if first else []):
                        if not self._open(self._sig(sig + text[:at])):
                            end = at
                            break
                    piece = text if end is None else text[:end]
                    skipped += len(piece.encode("utf-8"))
                    if end is None:
                        sig = self._sig(sig + piece)
                        if done:
                            self._withheld(skipped)
                        continue
                    self._withheld(skipped)
                    skipped, sig, text = None, "", text[end:]
                start = len(held)
                held += text
                ends = max(held.rfind("\n", start), held.rfind("\r", start)) + 1
                if ends and not self._open(held[:ends]):
                    self._emit(lib.redact(held[:ends]))
                    held = held[ends:]
                if done:
                    self._emit(lib.redact(held))
                elif len(held) > self._CAP:
                    skipped, sig, held = len(held.encode("utf-8")), self._sig(held), ""
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


def _read_plain_file(path, cwd):
    """Up to 4,000 bytes of a summary file the program wrote as its last act; None when missing or empty."""
    if not path:
        return None
    target = Path(path)
    if not target.is_absolute():
        target = Path(cwd or os.getcwd()) / target
    try:
        with open(str(target), "rb") as stream:
            data = stream.read(lib.PLAIN_FILE_LIMIT)
    except OSError:
        return None
    text = data.decode("utf-8", "replace").strip()
    return text or None


_AUTO_ENDINGS = {
    "launch": ("error", "The %s ended early because its program could not be started. "
                        "The coordinator decides what happens next."),
    "timeout": ("stuck", "The %s ended early because it ran past its time limit of %s. "
                         "The coordinator decides what happens next."),
    "exit": ("error", "The %s ended early because the program reported an error. "
                      "The coordinator reads its output next."),
    "signal": (None, "The %s was cut off before it finished, because it received a stop signal."),
}


def _closing_plain(spec, fields, how, cfg, notes):
    """Plain fields of the closing line (PAGE-SPEC 1.4, 1.5). `notes` collects stderr lines."""
    kind = spec["kind"]
    allowed = lib.plain_words_of(cfg)
    role = "project command" if kind == "command" else lib.role_name(spec["actor"]).lower()
    given = spec.get("plain")
    if spec.get("plain_file"):
        given = _read_plain_file(spec["plain_file"], spec.get("cwd")) or given
    status = fields["status"]
    if status == "done":
        auto = spec.get("auto_plain") or (lib.AUTO_COMMAND_PLAIN if kind == "command" else None)
        extra, found = lib.closing_plain_fields("done", kind, given, None, spec.get("next_step"), allowed, auto)
        notes.extend(found)
        return extra
    reason, text = _AUTO_ENDINGS[how]
    if how == "timeout":
        text = text % (role, lib.plain_duration(spec["timeout"]))
    else:
        text = text % role
    if fields.get("notes") == "target not met":
        reason = "error"
        text = ("The %s ran, but its result missed the target. "
                "The coordinator decides what happens next." % role)
    extra = {"plain": text, "plain_source": "auto"}
    if reason:
        extra["stop_reason"] = reason
    clean, reasons = lib.plain_candidate(given, allowed)
    if clean is not None and not reasons:
        extra["plain_given"] = clean
    if spec.get("next_step") is not None:
        value, found = lib.plain_candidate(spec["next_step"], allowed)
        if value is not None and not found:
            extra["next_step"] = value
        else:
            notes.append("factory: the next step was not kept: %s" % (found[0] if found else "It is empty."))
    return extra


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
        "group": lib.plain_clean(spec["group"], 80) if spec.get("group") else None,
    }
    start_fields.update(spec.get("extra") or {})
    input_text = spec.get("input_text")

    with lib.transaction(build.dir) as tx:
        if kind == "agent_call" and spec.get("call") and not spec.get("no_expected"):
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
            capture = _Capture(process.stdout, out_path, echo=not spec.get("quiet"))
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
    if isinstance(spec.get("result"), dict):
        spec["result"].update({"span_id": span_id, "tail": tail, "timed_out": timed_out})
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
    notes = []
    try:
        how = ("ok" if fields["status"] == "done" else "launch" if launch_error is not None
               else "signal" if interrupted is not None else "timeout" if timed_out else "exit")
        fields.update(_closing_plain(spec, fields, how, cfg, notes))
    except Exception as exc:  # a summary problem must never lose the closing line
        notes.append("factory: the plain summary could not be prepared (%s)" % type(exc).__name__)
    try:
        fields["span_id"] = span_id
        lib.append(build.dir, fields)
    except (OSError, lib.FactoryError) as exc:
        _stderr("factory: the program finished but its closing line could not be written (%s)" % exc)
    for note in notes:
        _stderr(note)
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
    p.add_argument("--group")
    p.add_argument("--plain")
    p.add_argument("--plain-file", dest="plain_file")
    p.add_argument("--next-step", dest="next_step")
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
        "input_as_arg": args.input_as_arg, "timeout": timeout, "cwd": args.cwd, "extra": extra,
        "group": args.group, "plain": args.plain, "plain_file": args.plain_file,
        "next_step": args.next_step})


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
    p.add_argument("--plain")
    p.add_argument("--next-step", dest="next_step")
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
        "timeout": float(timeout), "cwd": str(cwd), "next_step": args.next_step,
        "plain": args.plain if args.plain is not None else (
            entry.get("plain") if isinstance(entry.get("plain"), str) else None)}, finalize)


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

def _check_plain(label, text, allowed=()):
    if not text or not text.strip():
        _fail(lib.EXIT.USAGE, "the %s is empty. Write it as a plain sentence the owner can answer." % label,
              "gate %s is empty" % label)
    match = ID_TOKEN_RE.search(text)
    if match:
        _fail(lib.EXIT.USAGE, 'the %s contains "%s", which looks like an id the owner cannot read. '
              "Say it in plain words." % (label, match.group(0).strip()), "gate %s contains an id" % label)
    reasons = lib.plain_check(lib.plain_clean(text), allowed)
    if reasons:
        _fail(lib.EXIT.USAGE, "the %s is not plain enough: %s Say it in plain words." % (label, reasons[0]),
              "gate %s is not plain enough" % label)


def _gate_open(args):
    name = (args.name or "").strip()
    if not name:
        _fail(lib.EXIT.USAGE, "the gate needs a name, for example --name \"GATE A\"", "gate name is empty")
    allowed = lib.plain_words_of(_config())
    _check_plain("question", args.question, allowed)
    _check_plain("recommendation", args.recommend, allowed)
    if len(args.question) > QUESTION_LIMIT:
        _fail(lib.EXIT.USAGE, "the question is too long (%d characters; the limit is %d). Make it shorter."
              % (len(args.question), QUESTION_LIMIT), "gate question is too long")
    file_text = _read_prompt(args.file, "--file") if args.file else None
    build = lib.select_build(args)
    cfg = _config()
    question = lib.redact(args.question.strip())
    recommend = lib.redact(args.recommend.strip())
    fields = {"kind": "wait", "actor": "orchestrator", "waiting_on": "human", "status": "running",
              "start": lib.now(), "gate": name, "question": question, "recommend": recommend,
              "plain": lib.redact_plain(question), "plain_source": "agent", "node": args.node or None}
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
        extra, _notes = lib.closing_plain_fields(
            "done", "wait", args.plain, None, None, lib.plain_words_of(_config()), lib.GATE_CLOSE_PLAIN)
        closing.update(extra)
        if extra.get("plain_flag") == "failed_check":
            closing["plain"], closing["plain_source"] = lib.GATE_CLOSE_PLAIN, "auto"
            closing.pop("plain_flag")
        for note in _notes:
            _stderr(note)
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
    opened.add_argument("--node")
    opened.add_argument("--build")
    closed = sub.add_parser("close", allow_abbrev=False)
    closed.add_argument("span_id", metavar="question-id")
    closed.add_argument("--answer", default="")
    closed.add_argument("--plain")
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
# factory plain: write plain summaries for steps that have none (PAGE-SPEC 1.6)
# ---------------------------------------------------------------------------

SUMMARY_AUTO_PLAIN = "A summary writer rewrote one note."
NOTE_LIMIT = 1500
CONTEXT_LIMIT = 300
EXAMPLE_COUNT = 8


def _template(name):
    try:
        return (lib.kit_dir() / "templates" / name).read_text(encoding="utf-8")
    except OSError:
        return ""


def _examples():
    try:
        items = json.loads(_template("plain-examples.json") or "[]")
    except ValueError:
        return []
    return [i for i in items if isinstance(i, dict) and isinstance(i.get("raw"), str)
            and isinstance(i.get("plain"), str)][:EXAMPLE_COUNT]


def _raw_note(build_dir, span, limit):
    """What the step left behind, redacted and cut: its note, else its last line, else the end of its output."""
    for key in ("notes", "last"):
        if isinstance(span.get(key), str) and span[key].strip():
            return lib.plain_clean(span[key].strip(), limit)
    ref = span.get("output_ref")
    if isinstance(ref, str) and ref and not os.path.isabs(ref) and ".." not in Path(ref).parts:
        try:
            with open(str(Path(build_dir) / ref), "rb") as stream:
                stream.seek(0, os.SEEK_END)
                stream.seek(max(0, stream.tell() - 4096))
                text = stream.read().decode("utf-8", "replace").strip()
            return lib.plain_clean(text, None)[-limit:]
        except OSError:
            return ""
    return ""


def _shown_plain(span, build_dir, allowed):
    if span.get("plain") and not span.get("plain_flag"):
        return lib.plain_clean(span["plain"], CONTEXT_LIMIT)
    return _raw_note(build_dir, span, CONTEXT_LIMIT)


def _summary_prompt(role, piece_name, span, note, rejected, before, after, rules, examples, reasons=None):
    lines = [rules.strip(), ""]
    if examples:
        lines.append("Worked examples (raw note, then the plain version):")
        for item in examples:
            lines += ["Raw: " + item["raw"], "Plain: " + item["plain"], ""]
    lines += ["Now write the plain summary for this step.",
              "Who did it: " + role,
              "Piece: " + piece_name,
              "How it ended: " + str(span.get("status")),
              "Why it ended early: " + (span.get("stop_reason") or "not written down")
              if span.get("status") in ("failed", "stopped") else "",
              ("What happens next: " + span["next_step"]) if isinstance(span.get("next_step"), str) else "",
              "The raw note: " + (note or "(none)")]
    if rejected:
        lines.append("A summary that was refused as not plain enough: " + rejected)
    for label, text in before:
        lines.append("Earlier step on this piece: " + text)
    if after:
        lines.append("Next step on this piece: " + after)
    if reasons:
        lines += ["", "Your last answer was not plain enough:"] + ["- " + r for r in reasons] + [
            "Write it again, in one to three sentences, fixing these."]
    lines += ["", "Reply with the summary only."]
    return "\n".join(line for line in lines if line is not None) + "\n"


def _reply_text(raw):
    text = lib.plain_clean(" ".join((raw or "").split()))
    text = re.sub(r"(?i)^plain\s*:\s*", "", text).strip().strip("\"'“”").strip()
    return " ".join(lib.plain_sentences(text)[:3])


def _summary_argv(cfg, role):
    runner, model = role.get("runner"), role.get("model")
    program = lib.find_runner(cfg, runner)
    if not program:
        _fail(lib.EXIT.MISSING, "the %s program for the summaries role was not found on this machine" % runner,
              "summaries runner not found")
    if runner == "ollama":
        return [program, "run", model] if model else [program, "run"], False
    if runner == "claude":
        return [program, "-p"] + (["--model", model] if model else []), False
    if runner == "codex":
        return [program, "exec"] + (["-m", model] if model else []) + ["-"], False
    if runner == "opencode":
        return [program, "run"] + (["-m", model] if model else []), True
    return [program, "-p"] + (["--model", model] if model else []), True


def cmd_plain(argv):
    p = _parser("plain")
    p.add_argument("--build")
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--fallback-only", dest="fallback_only", action="store_true")
    args = p.parse_args(list(argv))
    if args.limit < 1:
        _fail(lib.EXIT.USAGE, "--limit must be 1 or more", "invalid --limit")
    timeout = _positive_timeout(args.timeout)
    build = lib.select_build(args)
    cfg = _config()
    allowed = lib.plain_words_of(cfg)
    read = lib.read_build(build.dir)
    todo = lib.spans_needing_plain(read["spans"])
    chosen, left = todo[:args.limit], max(0, len(todo) - args.limit)
    if args.dry_run:
        print("factory: %d entries would be rewritten" % len(chosen))
        return lib.EXIT.OK
    role = (cfg.get("roles") or {}).get("summaries")
    if not args.fallback_only and (not isinstance(role, dict) or not role.get("runner")):
        _fail(lib.EXIT.MISSING, "no summaries role in factory.json; add roles.summaries, "
              "see factory.example.json", "no summaries role")
    argv_base, as_arg = (None, False)
    if not args.fallback_only:
        if _may_keep_data(cfg, role.get("runner"), role.get("model")):
            _fail(lib.EXIT.USAGE, "the summaries role uses a model that may keep what it is sent, and step "
                  "notes can be private. Use a local model for roles.summaries.", "summaries model keeps data")
        argv_base, as_arg = _summary_argv(cfg, role)
    plan, _bad = lib.read_plan(build.dir)
    plan_names = {}
    if plan is not None:
        for piece in plan["pieces"]:
            if isinstance(piece, dict) and isinstance(piece.get("id"), str) and isinstance(piece.get("name"), str):
                plan_names[piece["id"]] = piece["name"]
    labels = _labels(read["spans"])
    by_node = {}
    for index, span in enumerate(read["spans"]):
        node = span.get("node")
        if span.get("kind") == "agent_call" and isinstance(node, str) and node:
            start = lib.to_epoch(span.get("start")) or lib.to_epoch(span.get("event")) or 0
            by_node.setdefault(node, []).append((start, index, span))
    for calls in by_node.values():
        calls.sort(key=lambda item: item[:2])
    rules, examples = _template("plain-rules.md"), _examples()
    rewrote = fell = timeouts = called = 0
    for span in chosen:
        node = span.get("node") if isinstance(span.get("node"), str) else None
        piece_name = plan_names.get(node) or (labels.get(node) if node and not lib.plain_label_check(labels.get(node, "")) and labels.get(node) else None) \
            or "not recorded"
        role_text = "project command" if span.get("kind") == "command" else lib.role_name(span.get("actor")).lower()
        note = _raw_note(build.dir, span, NOTE_LIMIT)
        rejected = lib.plain_clean(span["plain_rejected"], 400) if isinstance(span.get("plain_rejected"), str) else ""
        text, source = None, "fallback"
        if not args.fallback_only and (note or rejected):
            before, after = [], ""
            calls = by_node.get(node, [])
            ids = [c[2]["span_id"] for c in calls]
            if span["span_id"] in ids:
                at = ids.index(span["span_id"])
                before = [("", _shown_plain(c[2], build.dir, allowed)) for c in calls[max(0, at - 2):at]]
                if at + 1 < len(calls):
                    after = _shown_plain(calls[at + 1][2], build.dir, allowed)
            reasons = None
            for attempt in (1, 2):
                prompt = _summary_prompt(role_text, piece_name, span, note, rejected, before, after,
                                         rules, examples, reasons)
                result = {}
                called += 1 if attempt == 1 else 0
                code = _execute(build, {
                    "kind": "agent_call", "actor": "summaries", "call": "plain.%s.%d" % (span["span_id"], attempt),
                    "model": role.get("model"), "runner": role.get("runner"), "argv": argv_base,
                    "input_text": prompt, "input_as_arg": as_arg, "timeout": timeout, "quiet": True,
                    "no_expected": True, "auto_plain": SUMMARY_AUTO_PLAIN, "result": result})
                if code == lib.EXIT.TIMEOUT:
                    timeouts += 1 if attempt == 1 else 0
                    break
                candidate = _reply_text(result.get("tail", "")) if code == 0 else ""
                reasons = lib.plain_check(candidate, allowed)
                if not reasons:
                    text, source = candidate, "rewritten"
                    break
                if not candidate:
                    reasons = ["It is empty."]
        if text is None:
            if not (note or rejected):
                text = "The %s did not leave a note." % role_text
            else:
                text = lib.plain_fallback_text(span.get("status"))
            source = "fallback"
        lib.append(build.dir, {"span_id": span["span_id"], "status": span.get("status"), "phase": span.get("phase"),
                               "plain": text, "plain_source": source, "plain_flag": ""})
        if source == "rewritten":
            rewrote += 1
        else:
            fell += 1
    print("factory: rewrote %d, fell back on %d, left %d for later" % (rewrote, fell, left))
    return lib.EXIT.TIMEOUT if called and timeouts == called else lib.EXIT.OK


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

HANDLERS = {"run": cmd_run, "step": cmd_step, "wait": cmd_wait, "gate": cmd_gate, "check": cmd_check,
            "plain": cmd_plain}


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
