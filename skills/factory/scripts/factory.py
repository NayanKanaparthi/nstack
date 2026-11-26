#!/usr/bin/env python3
"""factory: the one entry point of the factory kit.

    python3 <kit>/scripts/factory.py <command> [args]

This file owns argument dispatch for every command. The commands init, new,
phase, log and status live here. The others are imported lazily from their own
module (each exposes main(argv) -> int); when a module file is missing the
command says so and exits 2 (SPEC 1.1).

Python 3.9, standard library only. Nothing here deletes or rewrites a file.
"""

import argparse
import importlib
import json
import os
import re
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import factorylib as lib  # noqa: E402

COMMAND_HELP = (
    ("init", "write factory.json for this project"),
    ("new", "start a build (or adopt an existing log)"),
    ("phase", "change the build's phase"),
    ("log", "write one line to the log: start, end, event, beat"),
    ("run", "run a program and log it automatically"),
    ("step", "run a command the project's settings define"),
    ("wait", "the wake timer: block until something changes"),
    ("gate", "ask the owner a decision: open, close, sent"),
    ("check", "find agent calls that were missed or never finished"),
    ("status", "show the live board in the terminal"),
    ("preflight", "check that the machine is ready"),
    ("trace-report", "write the run's trace report"),
    ("report-card", "write the run's report card"),
    ("eval", "run and improve deterministic evals: run, show, diagnose, improve"),
    ("plain", "write plain summaries for steps that have none"),
)
MODULES = {
    "run": ("agents", "agents.py"), "step": ("agents", "agents.py"), "wait": ("agents", "agents.py"),
    "gate": ("agents", "agents.py"), "check": ("agents", "agents.py"),
    "preflight": ("preflight", "preflight.py"),
    "trace-report": ("trace_report", "trace_report.py"), "report-card": ("trace_report", "trace_report.py"),
    "eval": ("evals", "evals.py"),
    "plain": ("agents", "agents.py"),
}
READS_CONFIG = ("run", "step", "wait", "gate", "check", "preflight", "eval", "plain")
RECORDS_FAILURES = ("log", "run", "step", "gate", "phase", "check", "eval")


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    """Argument errors become plain `factory:` lines with exit 2, never a usage dump."""

    def error(self, message):
        raise lib.FactoryError(lib.EXIT.USAGE, "factory: %s (try: factory %s --help)" % (
            message, self.prog.replace("factory ", "", 1)), "invalid arguments")


def _parser(prog, description=None):
    return _Parser(prog="factory " + prog, description=description, allow_abbrev=False)


def _fail(code, message, reason=None):
    raise lib.FactoryError(code, "factory: " + message, reason)


def _peek_build(argv):
    for index, item in enumerate(argv):
        if item == "--build" and index + 1 < len(argv):
            return argv[index + 1]
        if item.startswith("--build="):
            return item.split("=", 1)[1]
    return None


def _error_target(argv):
    try:
        return lib.select_build(_peek_build(argv)).dir
    except lib.FactoryError:
        return None


def _earliest_time(trace):
    """Earliest timestamp (start or ts) on any readable line of an existing log, or None."""
    best = None
    try:
        with open(str(trace), encoding="utf-8", errors="replace") as stream:
            for raw in stream:
                try:
                    line = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(line, dict):
                    continue
                for key in ("start", "ts"):
                    value = line.get(key)
                    epoch = lib.to_epoch(value) if isinstance(value, str) else None
                    if epoch is not None and (best is None or epoch < best[0]):
                        best = (epoch, value)
    except OSError:
        return None
    return best[1] if best else None


def _read_text_input(value, what):
    """Text for --input / --output: a file path, or - for stdin."""
    if value == "-":
        try:
            text = sys.stdin.read() if sys.stdin is not None else ""
        except (OSError, ValueError, AttributeError):
            text = ""
        if not text:
            _fail(lib.EXIT.EMPTY, "%s - was given but nothing arrived on stdin" % what, "empty input on stdin")
        return text
    path = Path(value)
    if not path.is_file():
        _fail(lib.EXIT.MISSING, "%s file not found: %s" % (what, value), "input file not found")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _fail(lib.EXIT.MISSING, "%s file can't be read: %s" % (what, exc.strerror or exc), "input file unreadable")
    if not text:
        _fail(lib.EXIT.EMPTY, "%s file is empty: %s" % (what, value), "input file is empty")
    return text


def _split_list(text):
    if text is None:
        return None
    return [item.strip() for item in text.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# factory init
# ---------------------------------------------------------------------------

def cmd_init(argv):
    p = _parser("init", "Write factory.json in the current folder from the kit's template.")
    p.add_argument("--project", help="project name (default: the folder name)")
    args = p.parse_args(argv)
    cwd = Path(os.getcwd())
    target = cwd / "factory.json"
    if target.exists():
        lib.load_config_full(cwd)
        print("factory.json ok")
        return lib.EXIT.OK
    name = args.project if args.project is not None else cwd.name
    if not lib.valid_name(name):
        if args.project is None:
            _fail(lib.EXIT.USAGE, 'the folder name "%s" can\'t be used as a project name (letters, digits, '
                  'dot, dash, underscore only). Run: factory init --project <name>' % name,
                  "folder name can't be used as a project name")
        _fail(lib.EXIT.USAGE, 'the project name "%s" can\'t be used (letters, digits, dot, dash, '
              'underscore only)' % name, "project name can't be used")
    example = lib.kit_dir() / "factory.example.json"
    try:
        config = json.loads(example.read_text(encoding="utf-8"))
    except OSError:
        _fail(lib.EXIT.MISSING, "the kit file factory.example.json is missing (%s)" % example,
              "kit template missing")
    except ValueError:
        _fail(lib.EXIT.USAGE, "the kit file factory.example.json is not valid JSON", "kit template invalid")
    config["project"] = name
    lib.validate_project_settings(config, cwd, "factory.example.json")
    try:
        with open(str(target), "x", encoding="utf-8") as stream:
            stream.write(json.dumps(config, indent=2) + "\n")
    except FileExistsError:
        print("factory.json ok")
        return lib.EXIT.OK
    print("factory.json written for project %s" % name)
    print("Next: factory new <build-id> --title \"...\"")
    return lib.EXIT.OK


# ---------------------------------------------------------------------------
# factory new
# ---------------------------------------------------------------------------

def _parse_stop(text):
    label, equals, clock = text.rpartition("=")
    match = re.match(r"^(\d{1,2}):(\d{2})$", clock.strip())
    if not equals or not label.strip() or not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        _fail(lib.EXIT.USAGE, '--stop must look like "LABEL=HH:MM" (local time today)', "invalid --stop")
    local = time.localtime(lib.now_epoch())
    epoch = time.mktime((local.tm_year, local.tm_mon, local.tm_mday,
                         int(match.group(1)), int(match.group(2)), 0, 0, 0, -1))
    return {"label": label.strip(), "at": lib.from_epoch(epoch)}


def _graph_pieces(path, skip):
    """Piece ids of a GRAPH.yaml by plain line matching (no YAML library). See SPEC 4.2."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        _fail(lib.EXIT.MISSING, "graph file not found: %s" % path, "graph file not found")
    pieces = []
    in_nodes = False
    current = None
    for raw in text.splitlines():
        if re.match(r"^nodes\s*:", raw):
            in_nodes = True
            continue
        if in_nodes and raw and not raw[0].isspace() and not raw.startswith("#") and not raw.startswith("-"):
            in_nodes = False
        if not in_nodes:
            continue
        match = re.match(r"^\s*-\s*id:\s*([A-Za-z0-9._-]+)", raw)
        if match:
            current = {"id": match.group(1), "empty": False}
            pieces.append(current)
        elif current is not None and re.match(r"^\s*owns_files:\s*\[\s*\]\s*(#.*)?$", raw):
            current["empty"] = True
    chosen = []
    for piece in pieces:
        if piece["empty"] or piece["id"] in skip or piece["id"] in chosen:
            continue
        chosen.append(piece["id"])
    if not chosen:
        _fail(lib.EXIT.EMPTY, "no pieces found in the graph file: %s" % path, "no pieces in graph file")
    return chosen


def _apply_stop_plain(stops, items, allowed):
    """Attach `plain` words to stop times: --stop-plain "GATE B=Release decision" (PAGE-SPEC 4.7)."""
    for item in items:
        label, equals, words = item.rpartition("=")
        label, words = label.strip(), lib.plain_clean(words.strip())
        if not equals or not label or not words:
            _fail(lib.EXIT.USAGE, '--stop-plain must look like "LABEL=WORDS"', "invalid --stop-plain")
        target = [stop for stop in stops if stop["label"] == label]
        if not target:
            _fail(lib.EXIT.USAGE, '--stop-plain names "%s", which no --stop uses' % label, "invalid --stop-plain")
        reasons = lib.plain_label_check(words, allowed)
        if reasons:
            _fail(lib.EXIT.USAGE, "--stop-plain for %s: %s" % (label, reasons[0]), "invalid --stop-plain")
        for stop in target:
            stop["plain"] = words


def _graph_plan(path, skip, allowed):
    """The plan of a staged GRAPH.yaml, checked before anything is created. None for an old-style graph."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        _fail(lib.EXIT.MISSING, "graph file not found: %s" % path, "graph file not found")
    plan, problems = lib.graph_plan(text, skip, allowed)
    if problems:
        _fail(lib.EXIT.USAGE, "the graph file has problems:\n  - " + "\n  - ".join(problems),
              "graph file has problems")
    if plan is None:
        print("factory: no stages block in the graph, so the plan has no stages and a plan view shows a flat list of pieces",
              file=sys.stderr)
    return plan


def _store_plan(build_dir, plan):
    if plan is None:
        return
    _path, notice = lib.write_plan(build_dir, plan)
    if notice:
        print(notice, file=sys.stderr)


def _seed_expected(build_dir, pieces):
    path = build_dir / "expected.jsonl"
    present = set()
    for entry in lib.read_jsonl_tail(path):
        if isinstance(entry.get("call"), str):
            present.add(entry["call"])
    stamp = lib.now()
    for piece in pieces:
        for role in ("maker", "checker"):
            call = "%s.%s.1" % (piece, role)
            if call in present:
                continue
            lib.append_jsonl_locked(path, {"call": call, "node": piece, "role": role, "try": 1,
                                           "added": stamp, "added_by": "graph"})


def cmd_new(argv):
    p = _parser("new", "Start a build, or adopt an existing log with --adopt.")
    p.add_argument("build_id")
    p.add_argument("--title")
    p.add_argument("--project")
    p.add_argument("--repo")
    p.add_argument("--stop", action="append", default=[], metavar="LABEL=HH:MM")
    p.add_argument("--stop-plain", dest="stop_plain", action="append", default=[], metavar="LABEL=WORDS")
    p.add_argument("--adopt", action="store_true")
    p.add_argument("--from-graph", dest="from_graph", metavar="FILE")
    p.add_argument("--skip", action="append", default=[], metavar="ID")
    args = p.parse_args(argv)
    cwd = Path(os.getcwd())

    project = args.project
    if project is None and (cwd / "factory.json").is_file():
        project = lib.load_config_full(cwd)[0].get("project")
    elif (cwd / "factory.json").is_file():
        lib.load_config_full(cwd)
    if not project:
        _fail(lib.EXIT.USAGE, "no project name. Run this in a folder with factory.json, or pass --project.",
              "no project name")
    if not lib.valid_name(project):
        _fail(lib.EXIT.USAGE, 'the project name "%s" can\'t be used (letters, digits, dot, dash, '
              'underscore only)' % project, "project name can't be used")
    if not lib.valid_name(args.build_id):
        _fail(lib.EXIT.USAGE, 'the build id "%s" can\'t be used (letters, digits, dot, dash, '
              'underscore only)' % args.build_id, "build id can't be used")
    stops = [_parse_stop(item) for item in args.stop]
    allowed = lib.plain_words_of(lib.lenient_config(cwd))
    _apply_stop_plain(stops, args.stop_plain, allowed)
    if args.adopt and (not args.title or not stops):
        _fail(lib.EXIT.USAGE, "--adopt needs --title and at least one --stop, so the adopted build "
              "has a headline and stop times.", "--adopt needs a title and a stop time")
    pieces = _graph_pieces(args.from_graph, set(args.skip)) if args.from_graph else None
    plan = _graph_plan(args.from_graph, set(args.skip), allowed) if args.from_graph else None

    build_dir = lib.build_dir_of(project, args.build_id)
    trace = build_dir / "trace.jsonl"
    meta_path = build_dir / "build.json"

    def write_meta():
        meta = {"project": project, "build": args.build_id, "title": args.title or args.build_id,
                "repo": args.repo if args.repo else os.getcwd(), "started": lib.now(), "stop_times": stops}
        if args.adopt:
            # the build began when its log began, not when it was taken over
            meta.pop("started")
            first = _earliest_time(trace)
            if first:
                meta["started"] = first
        try:
            with open(str(meta_path), "x", encoding="utf-8") as stream:
                stream.write(json.dumps(meta, indent=2) + "\n")
            return True
        except FileExistsError:
            return False

    if args.adopt:
        if not trace.is_file():
            _fail(lib.EXIT.MISSING, "nothing to adopt: no log at %s" % trace, "nothing to adopt")
        (build_dir / "messages").mkdir(exist_ok=True)
        if not write_meta():
            print("factory: build.json already exists and was kept as it is", file=sys.stderr)
        phase = "intake"
        try:
            phase = lib.board(build_dir, None, lib.lenient_config(cwd))["build"]["phase"] or "intake"
        except lib.FactoryError:
            pass
        lib.append_current(project, args.build_id, phase)
        if pieces:
            _seed_expected(build_dir, pieces)
        _store_plan(build_dir, plan)
        print(build_dir)
        return lib.EXIT.OK

    if trace.exists():
        _fail(lib.EXIT.NO, "build %s/%s already exists. To take over an existing log, add --adopt."
              % (project, args.build_id), "build already exists")
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "messages").mkdir(exist_ok=True)
    try:
        with open(str(trace), "x", encoding="utf-8"):
            pass
    except FileExistsError:
        _fail(lib.EXIT.NO, "build %s/%s already exists." % (project, args.build_id), "build already exists")
    write_meta()
    lib.append(build_dir, {"kind": "feature", "actor": "orchestrator", "status": "running",
                           "start": lib.now(), "phase": "intake"})
    lib.append_current(project, args.build_id, "intake")
    if pieces:
        _seed_expected(build_dir, pieces)
    _store_plan(build_dir, plan)
    print(build_dir)
    return lib.EXIT.OK


# ---------------------------------------------------------------------------
# factory phase
# ---------------------------------------------------------------------------

def cmd_phase(argv):
    p = _parser("phase", "Change the build's phase.")
    p.add_argument("name")
    p.add_argument("--build")
    args = p.parse_args(argv)
    name = args.name.strip()
    if not name or any(ord(ch) < 32 for ch in name):
        _fail(lib.EXIT.USAGE, "the phase needs a plain name, for example: factory phase build",
              "phase name is empty")
    build = lib.select_build(args)
    cfg = lib.load_config(Path(os.getcwd()))[0]
    findings = lib.unfinished(build.dir, lib.now(), cfg)
    for item in findings:
        print("WARNING " + item["text"])
    with lib.transaction(build.dir) as tx:
        stamp = lib.now()
        closed_open = False
        for span in tx.read()["spans"]:
            if span.get("kind") == "phase" and span.get("status") == "running":
                closed_open = True
                start = lib.to_epoch(span.get("start"))
                closing = {"span_id": span["span_id"], "kind": "phase", "status": "done", "end": stamp}
                if start is not None:
                    closing["duration_s"] = max(0, int(lib.to_epoch(stamp) - start))
                if findings:
                    closing["warn"] = True
                tx.add(closing)
        if findings and not closed_open:
            cur = lib.read_current() or {}
            left = cur.get("phase") if cur.get("build") == build.id else None
            tx.add({"kind": "phase", "actor": "orchestrator", "status": "done", "end": stamp,
                    "phase": left or "unknown", "warn": True})
        tx.add({"kind": "phase", "actor": "orchestrator", "status": "running", "start": stamp,
                "phase": name})
    lib.append_current(build.project, build.id, name)
    print("phase: %s" % name)
    return lib.EXIT.OK


# ---------------------------------------------------------------------------
# factory log
# ---------------------------------------------------------------------------

def _add_span_flags(p):
    p.add_argument("--call")
    p.add_argument("--node")
    p.add_argument("--label")
    p.add_argument("--iteration", type=int)
    p.add_argument("--model")
    p.add_argument("--effort")
    p.add_argument("--runner")
    p.add_argument("--parent")
    p.add_argument("--waiting-on", dest="waiting_on")
    p.add_argument("--notes")
    p.add_argument("--last")
    p.add_argument("--group")


def _plain_flags(p):
    p.add_argument("--plain")
    p.add_argument("--stop-reason", dest="stop_reason")
    p.add_argument("--next-step", dest="next_step")


def _check_stop_reason(status, stop_reason):
    if stop_reason is None:
        return
    if stop_reason not in lib.STOP_REASONS:
        _fail(lib.EXIT.USAGE, "--stop-reason must be one of: %s" % ", ".join(lib.STOP_REASONS),
              "invalid --stop-reason")
    if status not in ("failed", "stopped"):
        _fail(lib.EXIT.USAGE, "--stop-reason only goes with --status failed or --status stopped",
              "--stop-reason without a failed or stopped status")


def _plain_fields(args, status, kind):
    """Plain fields for a closing line; the notices go to stderr, the exit code is not changed."""
    allowed = lib.plain_words_of(lib.lenient_config(Path(os.getcwd())))
    fields, notices = lib.closing_plain_fields(
        status, kind, args.plain, args.stop_reason, args.next_step, allowed,
        auto_done=lib.AUTO_COMMAND_PLAIN if kind == "command" else None)
    return fields, notices


def _span_fields(args):
    if args.iteration is not None and args.iteration < 1:
        _fail(lib.EXIT.USAGE, "--iteration must be 1 or more", "invalid --iteration")
    if args.waiting_on is not None and not re.match(r"^(human|node:\S+|tool:\S+)$", args.waiting_on):
        _fail(lib.EXIT.USAGE, "--waiting-on must be human, node:<id> or tool:<name>", "invalid --waiting-on")
    return {
        "call": args.call, "node": args.node, "node_label": args.label, "iteration": args.iteration,
        "model": args.model, "effort": args.effort, "runner": args.runner, "parent_id": args.parent,
        "waiting_on": args.waiting_on, "notes": args.notes,
        "last": args.last[:200] if args.last else None,
        "group": lib.plain_clean(args.group, 80) if args.group else None,
    }


def _check_kind(kind):
    if kind not in lib.KINDS:
        _fail(lib.EXIT.USAGE, "--kind must be one of: %s" % ", ".join(lib.KINDS), "invalid --kind")


def _check_closing(status, failure_class, verdict=None):
    if status not in ("done", "failed", "stopped"):
        _fail(lib.EXIT.USAGE, "--status must be one of: done, failed, stopped", "invalid --status")
    if failure_class is not None and failure_class not in lib.FAILURE_CLASSES:
        _fail(lib.EXIT.USAGE, "--failure-class must be one of: %s" % ", ".join(lib.FAILURE_CLASSES),
              "invalid --failure-class")
    if status == "failed" and failure_class is None:
        _fail(lib.EXIT.USAGE, "--status failed needs --failure-class (%s)" % ", ".join(lib.FAILURE_CLASSES),
              "failed status without failure class")
    if verdict is not None and verdict not in lib.VERDICTS:
        _fail(lib.EXIT.USAGE, "--verdict must be approved or rejected", "invalid --verdict")


def _log_start(args):
    _check_kind(args.kind)
    fields = _span_fields(args)
    if args.kind == "agent_call" and (not args.call or args.input is None):
        _fail(lib.EXIT.USAGE, "an agent call needs --call <id> and --input <prompt file>, so what it was "
              "told is on record.", "agent call without call id or input")
    text = _read_text_input(args.input, "--input") if args.input is not None else None
    build = lib.select_build(args)
    fields.update({"kind": args.kind, "actor": args.actor, "status": "running", "start": lib.now()})
    span_id = lib.append(build.dir, fields, {"in": text} if text is not None else None)
    print(span_id)
    return lib.EXIT.OK


def _closing_fields(args):
    fields = {"failure_class": args.failure_class, "verdict": args.verdict,
              "rubric_pass": _split_list(args.rubric_pass), "rubric_fail": _split_list(args.rubric_fail)}
    for name, flag in (("tokens_in", args.tokens_in), ("tokens_out", args.tokens_out)):
        if flag is not None:
            if flag < 0:
                _fail(lib.EXIT.USAGE, "--tokens-in and --tokens-out must be 0 or more", "invalid token count")
            fields[name] = flag
    return fields


def _log_end(args):
    status = args.status or "done"
    _check_closing(status, args.failure_class, args.verdict)
    _check_stop_reason(status, args.stop_reason)
    text = _read_text_input(args.output, "--output") if args.output is not None else None
    build = lib.select_build(args)
    notices = []
    with lib.transaction(build.dir) as tx:
        span = tx.span(args.span_id)
        if span is None:
            _fail(lib.EXIT.MISSING, "No entry with that id in this build: %s" % args.span_id, "unknown span id")
        if span.get("status") != "running":
            _fail(lib.EXIT.NO, "That entry is already closed: %s" % args.span_id, "span already closed")
        end = lib.now()
        fields = _closing_fields(args)
        fields.update({"span_id": args.span_id, "status": status, "end": end})
        extra, notices = _plain_fields(args, status, span.get("kind"))
        fields.update(extra)
        if args.notes:
            fields["notes"] = args.notes
        start = lib.to_epoch(span.get("start"))
        if start is not None:
            fields["duration_s"] = max(0, int(lib.to_epoch(end) - start))
        tx.add(fields, {"out": text} if text is not None else None)
        node = span.get("node")
        if args.verdict and isinstance(node, str) and node:
            previous = None
            for item in tx.read()["spans"]:
                if item.get("kind") == "iteration" and item.get("node") == node:
                    previous = item
            before = []
            number = 0
            if previous is not None:
                recorded = previous.get("rubric_after")
                if not isinstance(recorded, list):
                    recorded = previous.get("rubric_pass")
                before = list(recorded) if isinstance(recorded, list) else []
                if lib._is_number(previous.get("iteration")):
                    number = int(previous["iteration"])
            after = fields.get("rubric_pass") or []
            tx.add({
                "kind": "iteration", "actor": span.get("actor"), "node": node,
                "node_label": span.get("node_label"), "status": "done", "start": end, "end": end,
                "duration_s": 0, "iteration": number + 1, "rubric_before": before, "rubric_after": after,
                "rubric_pass": after, "rubric_fail": fields.get("rubric_fail") or [],
                "newly_passing": [item for item in after if item not in before],
                "newly_failing": [item for item in before if item not in after],
                "why_not_done": args.why, "failure_class": args.failure_class, "verdict": args.verdict,
            })
    for notice in notices:
        print(notice, file=sys.stderr)
    return lib.EXIT.OK


def _log_event(args):
    _check_kind(args.kind)
    if args.kind == "agent_call" and not args.call:
        _fail(lib.EXIT.USAGE, "an agent call needs --call <id>, so it can be matched to its record.",
              "agent call without call id")
    status = args.status or "done"
    _check_closing(status, args.failure_class, args.verdict)
    _check_stop_reason(status, args.stop_reason)
    fields = _span_fields(args)
    fields.update(_closing_fields(args))
    extra, notices = _plain_fields(args, status, args.kind)
    fields.update(extra)
    duration = args.duration_s
    if duration is not None and duration < 0:
        _fail(lib.EXIT.USAGE, "--duration-s must be 0 or more", "invalid --duration-s")
    messages = {}
    if args.input is not None:
        messages["in"] = _read_text_input(args.input, "--input")
    if args.output is not None:
        messages["out"] = _read_text_input(args.output, "--output")
    build = lib.select_build(args)
    stamp = lib.now()
    end = lib.to_epoch(stamp)
    seconds = 0 if duration is None else (int(duration) if float(duration).is_integer() else duration)
    fields.update({"kind": args.kind, "actor": args.actor, "status": status, "end": stamp,
                   "start": lib.from_epoch(end - seconds), "duration_s": seconds})
    if args.why:
        fields["why_not_done"] = args.why
    span_id = lib.append(build.dir, fields, messages or None)
    print(span_id)
    for notice in notices:
        print(notice, file=sys.stderr)
    return lib.EXIT.OK


def _log_beat(args):
    build = lib.select_build(args)
    with lib.transaction(build.dir) as tx:
        span = tx.span(args.span_id)
        if span is None:
            _fail(lib.EXIT.MISSING, "No entry with that id in this build: %s" % args.span_id, "unknown span id")
        if span.get("status") != "running":
            _fail(lib.EXIT.NO, "That entry is already closed: %s" % args.span_id, "span already closed")
        tx.add({"span_id": args.span_id, "status": "running", "last": " ".join(args.text)[:200]})
    return lib.EXIT.OK


def cmd_log(argv):
    p = _parser("log", "Write one line to the build's log.")
    sub = p.add_subparsers(dest="action", parser_class=_Parser)
    sub.required = True

    start = sub.add_parser("start", allow_abbrev=False)
    start.add_argument("--kind", required=True)
    start.add_argument("--actor", required=True)
    _add_span_flags(start)
    start.add_argument("--input", help="prompt file, or - for stdin")
    start.add_argument("--build")

    end = sub.add_parser("end", allow_abbrev=False)
    end.add_argument("span_id")
    end.add_argument("--status")
    end.add_argument("--failure-class", dest="failure_class")
    end.add_argument("--output", help="reply file, or - for stdin")
    end.add_argument("--verdict")
    end.add_argument("--rubric-pass", dest="rubric_pass")
    end.add_argument("--rubric-fail", dest="rubric_fail")
    end.add_argument("--why")
    end.add_argument("--notes")
    end.add_argument("--tokens-in", dest="tokens_in", type=int)
    end.add_argument("--tokens-out", dest="tokens_out", type=int)
    _plain_flags(end)
    end.add_argument("--build")

    event = sub.add_parser("event", allow_abbrev=False)
    event.add_argument("--kind", required=True)
    event.add_argument("--actor", required=True)
    _add_span_flags(event)
    event.add_argument("--status")
    event.add_argument("--duration-s", dest="duration_s", type=float)
    event.add_argument("--failure-class", dest="failure_class")
    event.add_argument("--verdict")
    event.add_argument("--rubric-pass", dest="rubric_pass")
    event.add_argument("--rubric-fail", dest="rubric_fail")
    event.add_argument("--why")
    event.add_argument("--tokens-in", dest="tokens_in", type=int)
    event.add_argument("--tokens-out", dest="tokens_out", type=int)
    event.add_argument("--input")
    event.add_argument("--output")
    _plain_flags(event)
    event.add_argument("--build")

    beat = sub.add_parser("beat", allow_abbrev=False)
    beat.add_argument("span_id")
    beat.add_argument("text", nargs="+")
    beat.add_argument("--build")

    p.formatter_class = argparse.RawDescriptionHelpFormatter
    p.epilog = "\n".join("factory log %s:\n%s" % (name, sub.choices[name].format_help())
                         for name in ("start", "end", "event", "beat"))
    args = p.parse_args(argv)
    handler = {"start": _log_start, "end": _log_end, "event": _log_event, "beat": _log_beat}[args.action]
    return handler(args)


# ---------------------------------------------------------------------------
# factory status
# ---------------------------------------------------------------------------

def render_status(data):
    """The plain-text board (SPEC 5.2)."""
    head_build = data["build"]
    head = ["%s/%s" % (head_build["project"], head_build["id"]), head_build["state_label"]]
    if head_build.get("phase_label"):
        head.append(head_build["phase_label"])
    if head_build.get("elapsed_s") is not None:
        head.append("%s so far" % head_build["elapsed_label"])
    upcoming = [stop for stop in head_build.get("stop_times", []) if stop["mins_left"] >= 0]
    if upcoming:
        nearest = min(upcoming, key=lambda stop: stop["mins_left"])
        head.append("%s in %s" % (nearest["label"], lib.words_for_duration(nearest["mins_left"] * 60)))
    lines = ["   ".join(head)]
    for warning in data["warnings"]:
        lines.append("WARNING " + warning)
    waiting = data["waiting_on_you"]
    if waiting:
        lines += ["", "WAITING ON YOU (%d)" % len(waiting)]
        for item in waiting:
            age = ", %s" % lib.words_for_duration(item["mins"] * 60) if item.get("mins") is not None else ""
            tail = "   Suggested: %s" % item["recommend"] if item.get("recommend") else ""
            lines.append("  %s%s: %s%s" % (item["gate"], age, item["question"], tail))
    agents = data["agents"]
    if agents:
        rows = []
        for agent in agents:
            piece = agent["piece_label"]
            if agent.get("piece_id"):
                piece += " [%s]" % agent["piece_id"]
            last = agent["last"]
            if agent.get("quiet_label"):
                last = ("%s. %s" % (agent["quiet_label"], last)).strip()
            rows.append((agent["state_label"], agent["role_label"], agent["model_label"], piece,
                         "try %d" % agent["loop"] if agent.get("loop") else "",
                         agent["elapsed_label"], last))
        widths = [max(len(row[i]) for row in rows) for i in range(6)]
        lines += ["", "AGENTS"]
        for row in rows:
            cells = [row[i].ljust(widths[i]) for i in range(6)] + [row[6]]
            lines.append("  " + "   ".join(cells).rstrip())
    evals = data.get("evals") or []
    if evals:
        rows = [(item["name"], "%d of %d right (%d%%)" % (
                    item["passed"], item["n"], lib.eval_percent(item["passed"], item["n"])),
                 "target met" if item["met"] else "target NOT met", item["when"]) for item in evals]
        widths = [max(len(row[i]) for row in rows) for i in range(3)]
        lines += ["", "EVALS"]
        for row in rows:
            lines.append("  " + "   ".join([row[i].ljust(widths[i]) for i in range(3)] + [row[3]]).rstrip())
    return "\n".join(lines)


def cmd_status(argv):
    p = _parser("status", "Show the live board for the current build.")
    p.add_argument("--build")
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args(argv)
    cfg = lib.load_config(Path(os.getcwd()))[0]
    if args.all:
        builds = lib.list_builds(None, None, cfg)
        if not builds:
            print("No builds found under %s." % (lib.home() / "runs"))
            return lib.EXIT.OK
        for item in builds:
            extra = "   %d waiting on you" % item["waiting"] if item["waiting"] else ""
            print("%s/%s   %s   last activity %s%s" % (
                item["project"], item["id"], item["state_label"], item["last_activity"] or "not recorded", extra))
        return lib.EXIT.OK
    build = lib.select_build(args)
    data = lib.board(build.dir, None, cfg)
    if args.json:
        print(json.dumps(data, indent=2))
        return lib.EXIT.OK
    if not lib.read_build(build.dir)["spans"]:
        print("No activity logged yet for %s/%s." % (build.project, build.id))
        for warning in data["warnings"]:
            print("WARNING " + warning)
        return lib.EXIT.OK
    print(render_status(data))
    missing = len(lib.spans_needing_plain(lib.read_build(build.dir)["spans"]))
    if missing:
        print("%d step%s no plain summary yet. Run: factory plain" % (
            missing, " has" if missing == 1 else "s have"))
    return lib.EXIT.OK


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

LOCAL = {"init": cmd_init, "new": cmd_new, "phase": cmd_phase, "log": cmd_log, "status": cmd_status}


def print_help(stream):
    stream.write("factory %s: the factory kit. Usage: python3 factory.py <command> [args]\n\n" % lib.VERSION)
    stream.write("Commands:\n")
    for name, text in COMMAND_HELP:
        stream.write("  %-13s %s\n" % (name, text))
    stream.write("\nRun 'factory <command> --help' for the flags of one command.\n")


def _dispatch_module(command, argv):
    module_name, filename = MODULES[command]
    if not (SCRIPT_DIR / filename).is_file():
        _fail(lib.EXIT.USAGE, "'%s' is not installed (missing scripts/%s)" % (command, filename),
              "command is not installed")
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        _fail(lib.EXIT.USAGE, "'%s' could not be loaded (%s)" % (command, exc), "module could not be loaded")
    code = module.main([command] + list(argv) if module_name == "agents" else list(argv))
    return lib.EXIT.OK if code is None else int(code)


def _run(command, argv):
    if command in READS_CONFIG:
        lib.load_config_full(Path(os.getcwd()))
    if command in LOCAL:
        return LOCAL[command](argv)
    return _dispatch_module(command, argv)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print_help(sys.stderr)
        return lib.EXIT.USAGE
    command = argv[0]
    if command in ("-h", "--help", "help"):
        print_help(sys.stdout)
        return lib.EXIT.OK
    if command in ("-V", "--version", "version"):
        print("factory %s" % lib.VERSION)
        return lib.EXIT.OK
    known = [name for name, _text in COMMAND_HELP]
    if command not in known:
        sys.stderr.write("factory: unknown command '%s'. Commands: %s\n" % (command, ", ".join(known)))
        return lib.EXIT.USAGE
    rest = argv[1:]
    try:
        return _run(command, rest)
    except lib.FactoryError as exc:
        sys.stderr.write(exc.line() + "\n")
        if command in RECORDS_FAILURES and exc.code in (lib.EXIT.USAGE, lib.EXIT.MISSING, lib.EXIT.EMPTY):
            lib.record_error(_error_target(rest), command, exc.code, exc.reason)
        return exc.code
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    except BrokenPipeError:
        try:
            sys.stdout = None
        except Exception:
            pass
        return lib.EXIT.OK
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        if os.environ.get("FACTORY_DEBUG") == "1":
            raise
        sys.stderr.write("factory: unexpected error (%s: %s). Set FACTORY_DEBUG=1 to see the details.\n"
                         % (type(exc).__name__, exc))
        return lib.EXIT.NO


if __name__ == "__main__":
    sys.exit(main())
