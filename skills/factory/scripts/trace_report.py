"""factory trace-report and factory report-card (SPEC 6).

Everything here is computed in code from the build's log. There is no model call and
no network, and no raw log line is ever placed in a prompt. Reports are new,
timestamped files: nothing that exists is replaced or removed.

    compute(build_dir, now, gap_s) -> dict        the JSON of SPEC 6.1
    main(argv) -> int                             `factory trace-report` or `factory report-card`
    main_trace(argv), main_card(argv)             the two commands, explicitly

factory.py hands both commands to `main(argv)` with only the arguments after the
command name, so `main` finds out which command was typed from the process
arguments (sys.argv[1]). Callers that know better use main_trace or main_card.
"""

import json
import sys
from pathlib import Path

import factorylib as lib

TIMED_KINDS = ("agent_call", "command", "wait")
DEFAULT_GAP_S = 300
NOTES_LIMIT = 200

FAILURE_WORDS = {
    "spec-ambiguity": "unclear spec",
    "test-wrong": "wrong test",
    "impl-bug": "code bug",
    "env-tooling": "tooling",
    "flaky": "flaky",
    "scope-creep": "scope creep",
    "context-overflow": "too much to read",
    "model-stall": "model stalled",
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _num(value):
    """A usable non-negative number, else None (bools and text are not numbers)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value < 0 or value == float("inf"):
        return None
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def _clean(value, limit=None):
    """A string safe to print: secrets replaced, one line, optionally cut short."""
    if not isinstance(value, str):
        return None
    text = " ".join(lib.redact(value).split())
    if limit and len(text) > limit:
        text = text[:limit - 3] + "..."
    return text or None


def _s(value):
    return int(value) if isinstance(value, float) and value == int(value) else value


def _share(part, total):
    return round(part / float(total), 3) if total else 0.0


def _stamp(now_text):
    return "".join(ch for ch in now_text if ch.isalnum())


def _plural(count, one, many=None):
    return "%d %s" % (count, one if count == 1 else (many or one + "s"))


def duration_text(seconds):
    """45 s, 12 min, 2 h 2 min. Whole minutes are rounded (round-half-even), as in the card."""
    seconds = int(max(0, round(seconds)))
    if seconds < 60:
        return "%d s" % seconds
    minutes = int(round(seconds / 60.0))
    if minutes < 60:
        return "%d min" % minutes
    return "%d h %d min" % (minutes // 60, minutes % 60)


def _role_text(actor):
    return lib.role_label(actor) if isinstance(actor, str) and actor else "Unknown role"


def _piece_label(node, labels):
    if not isinstance(node, str) or not node:
        return lib.NO_PIECE
    if node in labels:
        return labels[node]
    if node in lib.OLD_PHASES:
        return lib.phase_label(node)
    return lib.UNRECORDED_PIECE


def _phase_text(phase):
    return lib.phase_label(phase) if isinstance(phase, str) and phase else "Other"


def _is_human_wait(span):
    return span.get("kind") == "wait" and span.get("waiting_on") == "human"


# ---------------------------------------------------------------------------
# computing (SPEC 6.1)
# ---------------------------------------------------------------------------

def _merge(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged


def _analyse(build_dir, now, gap_s):
    """(report, read, timed_count). Never raises on log content."""
    build_dir = Path(build_dir)
    read = lib.read_build(build_dir)
    spans = read["spans"]
    meta = read["meta"]
    now_e = lib.to_epoch(now) if isinstance(now, str) else _num(now)
    if now_e is None:
        now_e = lib.now_epoch()
    labels = {}
    for span in spans:
        node, label = span.get("node"), _clean(span.get("node_label"))
        if isinstance(node, str) and label:
            labels[node] = label

    # which spans are timed, which are open, which have no duration
    timed, open_spans, unknown = [], [], 0
    human_waits = []     # (span, start_e, seconds, is_open)
    other_waits = []
    for span in spans:
        kind = span.get("kind")
        status = span.get("status")
        if status == "running":
            open_spans.append({"key": span.get("span_id"), "kind": kind,
                               "actor": _clean(span.get("actor")), "node": _clean(span.get("node"))})
        if kind not in TIMED_KINDS:
            continue
        duration = _num(span.get("duration_s"))
        if status in lib.CLOSED_STATUSES and duration is not None:
            timed.append((span, duration))
            if kind == "wait":
                (human_waits if _is_human_wait(span) else other_waits).append(
                    (span, lib.to_epoch(span.get("start")), duration, False))
        elif kind == "wait" and status == "running":
            start = lib.to_epoch(span.get("start"))
            if start is None:
                unknown += 1
            else:
                seconds = max(0, now_e - start)
                (human_waits if _is_human_wait(span) else other_waits).append(
                    (span, start, _s(seconds), True))
        else:
            unknown += 1

    # first and last event
    stamps = []
    for span in spans:
        for key in ("start", "end", "ts"):
            value = lib.to_epoch(span.get(key))
            if value is not None:
                stamps.append(value)
    first_e = min(stamps) if stamps else None
    last_e = max(stamps) if stamps else None

    report = {"build": {
        "project": _clean(meta.get("project")) or build_dir.parent.name,
        "id": _clean(meta.get("build")) or build_dir.name,
        "first_event": lib.from_epoch(first_e) if first_e is not None else None,
        "last_event": lib.from_epoch(last_e) if last_e is not None else None,
        "wall_s": _s(last_e - first_e) if first_e is not None else 0,
        "lines": read["lines"], "spans": len(spans), "bad_lines": len(read["bad_lines"]),
        "open_spans": open_spans, "unknown_duration_spans": unknown,
    }}

    # by phase, node, actor
    phase_sum = {}
    node_sum = {}
    actor_sum = {}
    for span, duration in timed:
        phase = span.get("phase") if isinstance(span.get("phase"), str) else "other"
        phase_sum[phase] = phase_sum.get(phase, 0) + duration
        if span.get("kind") == "wait":
            continue
        node = span.get("node") if isinstance(span.get("node"), str) and span.get("node") else None
        row = node_sum.setdefault(node, [0, 0])
        row[0] += duration
        row[1] += 1
        actor = span.get("actor") if isinstance(span.get("actor"), str) else None
        model = span.get("model") if isinstance(span.get("model"), str) else None
        row = actor_sum.setdefault((actor, model), {"t": 0, "n": 0, "failed": 0, "chars": []})
        row["t"] += duration
        row["n"] += 1
        if span.get("status") == "failed":
            row["failed"] += 1
        chars = _num(span.get("input_chars"))
        if chars is not None:
            row["chars"].append(chars)
    total = sum(phase_sum.values())
    report["by_phase"] = [
        {"phase": phase, "phase_label": _phase_text(phase), "time_s": _s(seconds),
         "share": _share(seconds, total)}
        for phase, seconds in sorted(phase_sum.items(), key=lambda kv: (-kv[1], kv[0]))]
    report["by_node"] = [
        {"node": node, "node_label": _piece_label(node, labels), "time_s": _s(vals[0]), "calls": vals[1]}
        for node, vals in sorted(node_sum.items(), key=lambda kv: (-kv[1][0], str(kv[0])))]
    report["by_actor"] = [
        {"actor": actor, "model": _clean(model), "calls": vals["n"], "time_s": _s(vals["t"]),
         "failed": vals["failed"],
         "input_chars_avg": (round(sum(vals["chars"]) / float(len(vals["chars"])), 1)
                             if vals["chars"] else None)}
        for (actor, model), vals in sorted(actor_sum.items(),
                                           key=lambda kv: (-kv[1]["t"], str(kv[0][0]), str(kv[0][1])))]

    report["loops"] = _loops(spans, labels)

    # waits
    items = []
    for group in (human_waits, other_waits):
        for span, _start, seconds, is_open in group:
            items.append({"gate": _clean(span.get("gate")) or _clean(span.get("question"), 60) or "a decision",
                          "waiting_on": _clean(span.get("waiting_on")) or "human",
                          "s": _s(seconds), "open": is_open})
    human_items = [item for item in items if item["waiting_on"] == "human"]
    longest = max(human_items, key=lambda item: item["s"]) if human_items else None
    report["waits"] = {
        "human_s": _s(sum(item["s"] for item in human_items)),
        "human_count": len(human_items),
        "human_open": sum(1 for item in human_items if item["open"]),
        "longest_human": {"gate": longest["gate"], "s": longest["s"]} if longest else None,
        "other_s": _s(sum(item["s"] for item in items if item["waiting_on"] != "human")),
        "items": items,
    }

    # idle gaps
    covered = []
    if first_e is not None:
        for span, duration in timed:
            if span.get("kind") in ("agent_call", "command"):
                start, end = lib.to_epoch(span.get("start")), lib.to_epoch(span.get("end"))
                if start is not None and end is not None and end > start:
                    covered.append((start, end))
        for span, start, _seconds, is_open in human_waits:
            if start is None:
                continue
            end = now_e if is_open else lib.to_epoch(span.get("end"))
            if end is not None and end > start:
                covered.append((start, end))
    gaps = []
    if first_e is not None and last_e is not None:
        clipped = [(max(a, first_e), min(b, last_e)) for a, b in covered if b > first_e and a < last_e]
        cursor = first_e
        for start, end in _merge(clipped) + [[last_e, last_e]]:
            if start - cursor > gap_s:
                gaps.append({"from": lib.from_epoch(cursor), "to": lib.from_epoch(start),
                             "s": _s(start - cursor)})
            cursor = max(cursor, end)
    report["idle_gaps"] = {"threshold_s": gap_s, "total_s": _s(sum(g["s"] for g in gaps)), "gaps": gaps}

    # failures
    report["failures"] = [
        {"node": _clean(span.get("node")), "actor": _clean(span.get("actor")),
         "failure_class": _clean(span.get("failure_class")),
         "notes": _clean(span.get("notes"), NOTES_LIMIT)}
        for span in spans if span.get("status") == "failed"]

    report["bottlenecks"] = _bottlenecks(report)
    evals = [summary for _entry, summary in lib.eval_summaries(build_dir)[0]]
    if evals:
        report["evals"] = evals
    return report, read, len(timed)


def _loops(spans, labels):
    order = []
    for span in spans:
        node = span.get("node")
        if isinstance(node, str) and node and (
                span.get("kind") == "iteration" or
                (span.get("kind") == "agent_call" and span.get("actor") == "maker")):
            if node not in order:
                order.append(node)
    rows = []
    for node in order:
        mine = [s for s in spans if s.get("node") == node]
        makers = [s for s in mine if s.get("kind") == "agent_call" and s.get("actor") == "maker"]
        tries = [_num(s.get("iteration")) for s in makers]
        tries = [t for t in tries if t is not None]
        approving = [s for s in mine if s.get("verdict") == "approved" and s.get("kind") != "iteration"]
        approved = bool(approving) or any(s.get("verdict") == "approved" for s in mine)
        starts = [e for e in (lib.to_epoch(s.get("start")) for s in makers) if e is not None]
        first_start = min(starts) if starts else None
        ends = sorted(e for e in (lib.to_epoch(s.get("end")) for s in approving) if e is not None)
        to_approval = _s(ends[0] - first_start) if (first_start is not None and ends) else None
        iterations = [s for s in mine if s.get("kind") == "iteration"]
        classes = {}
        for span in iterations:
            name = span.get("failure_class")
            if isinstance(name, str) and name:
                classes[name] = classes.get(name, 0) + 1
        rows.append({
            "node": node, "node_label": _piece_label(node, labels),
            "loops": int(max(tries)) if tries else len(makers),
            "approved": approved, "time_to_approval_s": to_approval,
            "churn": sum(1 for s in iterations if not s.get("newly_passing")) if iterations else None,
            "thrash": sum(1 for s in iterations if s.get("newly_failing")) if iterations else None,
            "failure_classes": classes,
        })
    return rows


def _bottlenecks(report):
    waits = report["waits"]
    candidates = []
    if waits["human_s"] > 0:
        longest = waits["longest_human"]
        text = "Waiting on a person took %s in %s." % (
            duration_text(waits["human_s"]), _plural(waits["human_count"], "wait"))
        if longest:
            text = text + " The longest was %s at %s." % (longest["gate"], duration_text(longest["s"]))
        candidates.append(("human-wait", "Waiting on a person", waits["human_s"], text))
    idle = report["idle_gaps"]
    if idle["total_s"] > 0:
        candidates.append(("idle", "Nobody working", idle["total_s"],
                           "Nobody was working for %s in %s." % (
                               duration_text(idle["total_s"]), _plural(len(idle["gaps"]), "gap"))))
    pieces = [r for r in report["by_node"] if r["node"]]
    if pieces and pieces[0]["time_s"] > 0:
        top = pieces[0]
        loop = next((row for row in report["loops"] if row["node"] == top["node"]), None)
        tries = loop["loops"] if loop else top["calls"]
        word = "piece" if loop else "step"
        candidates.append(("node", top["node_label"], top["time_s"],
                           "The slowest %s was %s at %s, in %s." % (
                               word, top["node_label"], duration_text(top["time_s"]),
                               _plural(tries, "try", "tries"))))
    if report["by_actor"] and report["by_actor"][0]["time_s"] > 0:
        top = report["by_actor"][0]
        who = _role_text(top["actor"])
        if top["model"]:
            who += " (%s)" % top["model"]
        candidates.append(("actor", who, top["time_s"],
                           "%s work took %s over %s." % (
                               who, duration_text(top["time_s"]), _plural(top["calls"], "call"))))
    candidates.sort(key=lambda c: (-c[2], c[0]))
    return [{"rank": i, "kind": kind, "label": label, "time_s": _s(seconds), "plain": plain}
            for i, (kind, label, seconds, plain) in enumerate(candidates[:3], 1)]


def compute(build_dir, now, gap_s=DEFAULT_GAP_S):
    """The JSON of SPEC 6.1 for one build folder. `now` is a timestamp (open waits count up to it)."""
    return _analyse(build_dir, now, gap_s)[0]


# ---------------------------------------------------------------------------
# the check counts shown under "Data quality" of the card (SPEC 4.7 / 6.2)
# ---------------------------------------------------------------------------

def _check_counts(build_dir, read, now):
    """{expected, logged, matched, missing, unplanned, duplicate, unfinished}, or None with no list."""
    expected = []
    try:
        text = (Path(build_dir) / "expected.jsonl").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for raw in text.splitlines():
        try:
            entry = json.loads(raw)
        except ValueError:
            continue
        if isinstance(entry, dict) and isinstance(entry.get("call"), str) and entry["call"] not in expected:
            expected.append(entry["call"])
    if not expected:
        return None
    calls = [s for s in read["spans"] if s.get("kind") == "agent_call"]
    seen = {}
    for span in calls:
        call = span.get("call")
        if isinstance(call, str) and call:
            seen.setdefault(call, []).append(span)
    matched = [c for c in expected if any(s.get("status") in lib.CLOSED_STATUSES for s in seen.get(c, []))]
    try:
        open_work = len(lib.unfinished(read, now))
    except Exception:
        open_work = 0
    return {
        "expected": len(expected), "logged": len(calls), "matched": len(matched),
        "missing": len(expected) - len(matched),
        "unplanned": sum(1 for s in calls if not isinstance(s.get("call"), str) or s.get("call") not in expected),
        "duplicate": sum(1 for spans in seen.values() if len(spans) > 1),
        "unfinished": open_work,
    }


# ---------------------------------------------------------------------------
# text output
# ---------------------------------------------------------------------------

def _table(headers, rows):
    if not rows:
        return ["Nothing recorded.", ""]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |")
    lines.append("")
    return lines


def _yes(value):
    return "yes" if value else "no"


def _plain_or(value, other="not recorded"):
    return other if value is None else value


def render_markdown(report):
    b = report["build"]
    lines = ["# Trace report: %s/%s" % (b["project"], b["id"]), "",
             "From %s to %s, %s from first to last event. Work done in parallel is counted in full "
             "in every table, so the times can add up to more than the total." % (
                 _plain_or(b["first_event"]), _plain_or(b["last_event"]), duration_text(b["wall_s"])), ""]
    lines += ["## Build", ""] + _table(
        ["Lines in log", "Things logged", "Unreadable lines", "Never closed", "Without a duration"],
        [[b["lines"], b["spans"], b["bad_lines"], len(b["open_spans"]), b["unknown_duration_spans"]]])
    lines += ["## By phase", ""] + _table(
        ["Phase", "Time", "Share"],
        [[r["phase_label"], duration_text(r["time_s"]), "%d%%" % round(r["share"] * 100)]
         for r in report["by_phase"]])
    lines += ["## By piece", ""] + _table(
        ["Piece", "Time", "Calls"],
        [[r["node_label"], duration_text(r["time_s"]), r["calls"]] for r in report["by_node"]])
    lines += ["## By actor", ""] + _table(
        ["Role", "Model", "Calls", "Time", "Failed", "Average input (characters)"],
        [[_role_text(r["actor"]), _plain_or(r["model"], "none"), r["calls"], duration_text(r["time_s"]),
          r["failed"], _plain_or(r["input_chars_avg"], "not recorded")] for r in report["by_actor"]])
    lines += ["## Loops", ""] + _table(
        ["Piece", "Tries", "Approved", "Time to approval", "Tries with no new pass", "Tries that broke something"],
        [[r["node_label"], r["loops"], _yes(r["approved"]),
          duration_text(r["time_to_approval_s"]) if r["time_to_approval_s"] is not None else "not recorded",
          _plain_or(r["churn"]), _plain_or(r["thrash"])] for r in report["loops"]])
    w = report["waits"]
    lines += ["## Waits", "",
              "Waiting on a person: %s in %s (%d still open). Waiting on something else: %s." % (
                  duration_text(w["human_s"]), _plural(w["human_count"], "wait"), w["human_open"],
                  duration_text(w["other_s"])), ""]
    lines += _table(["Decision", "Waiting on", "Time", "Still open"],
                    [[i["gate"], i["waiting_on"], duration_text(i["s"]), _yes(i["open"])] for i in w["items"]])
    g = report["idle_gaps"]
    lines += ["## Idle gaps", "",
              "Stretches over %s when nobody was working: %s in %s." % (
                  duration_text(g["threshold_s"]), duration_text(g["total_s"]), _plural(len(g["gaps"]), "gap")), ""]
    lines += _table(["From", "To", "Length"],
                    [[x["from"], x["to"], duration_text(x["s"])] for x in g["gaps"]])
    labels = {r["node"]: r["node_label"] for r in report["by_node"] + report["loops"] if r["node"]}
    lines += ["## Failures", ""] + _table(
        ["Piece", "Role", "Kind of failure", "Notes"],
        [[_piece_label(f["node"], labels) if f["node"] else "none", _role_text(f["actor"]) if f["actor"] else "none",
          FAILURE_WORDS.get(f["failure_class"], _plain_or(f["failure_class"], "not classified")),
          _plain_or(f["notes"], "")] for f in report["failures"]])
    if report.get("evals"):
        lines += ["## Evals", ""] + _table(
            ["Set", "Right", "Share", "Target met", "Slowest 5% (s)", "Cost per example"],
            [[_plain_or(r.get("name"), r.get("set")), "%s of %s" % (r.get("passed"), r.get("n")),
              "%d%%" % lib.eval_percent(r.get("passed", 0), r.get("n", 0)), _yes(r.get("met")),
              _plain_or(r.get("time_p95_s")),
              lib.eval_money(r["cost_per_example"], r.get("cost_unit"))
              if isinstance(r.get("cost_per_example"), (int, float)) else "not reported"]
             for r in report["evals"]])
    lines += ["## Bottlenecks", ""] + _table(
        ["Rank", "What", "Time", "In words"],
        [[r["rank"], r["label"], duration_text(r["time_s"]), r["plain"]] for r in report["bottlenecks"]])
    lines += ["## Data quality", "",
              "- %s." % _plural(b["bad_lines"], "unreadable line"),
              "- %s never closed." % _plural(len(b["open_spans"]), "thing"),
              "- %s without a duration (left out of every sum)." % _plural(b["unknown_duration_spans"], "thing"),
              ""]
    return "\n".join(lines)


def _failure_summary(failures):
    if not failures:
        return "none"
    counts = {}
    for item in failures:
        word = FAILURE_WORDS.get(item["failure_class"], "not classified")
        counts[word] = counts.get(word, 0) + 1
    parts = ["%d %s" % (n, word) for word, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return "%d (%s)" % (len(failures), ", ".join(parts))


def _ended_failed(read):
    """True when the build record closed as failed or stopped; else when the last timed span failed."""
    for span in read["spans"]:
        if span.get("kind") == "feature" and span.get("status") in ("failed", "stopped"):
            return True
    last = None
    for span in read["spans"]:
        if isinstance(span.get("step"), str) and span["step"].startswith("evalset."):
            continue  # a missed eval target is reported in its own block, it never fails the build
        end = lib.to_epoch(span.get("end"))
        if end is not None and span.get("kind") in TIMED_KINDS and (last is None or end >= last[0]):
            last = (end, span)
    return bool(last and last[1].get("status") == "failed")


def _target_words(summary):
    """What a missed target needs, in words: 'needs 90%, speed' (EVALS-SPEC 8.1)."""
    missed = {t.get("key"): t for t in summary.get("targets") or [] if isinstance(t, dict) and not t.get("met")}
    parts = []
    accuracy = missed.get("accuracy")
    if accuracy:
        text = str(accuracy.get("target", ""))
        op = text[:2] if text[:2] in (">=", "<=", "==") else text[:1]
        number = round(float(text[len(op):] or 0) * 100, 1)
        number = int(number) if float(number).is_integer() else number
        parts.append("%s %s%%" % ("over" if op == ">" else "needs", number))
    if "p95_s" in missed:
        parts.append("speed")
    if "cost_per_example" in missed:
        parts.append("cost")
    return ", ".join(parts)


def eval_card_lines(evals, improve=None):
    """The Evals block of the card: one line per set, at most 3, then 'and <k> more'."""
    improve = improve or {}
    lines = []
    for summary in evals[:3]:
        name = summary.get("name") if isinstance(summary.get("name"), str) and summary.get("name") else summary.get("set")
        passed, n = summary.get("passed", 0), summary.get("n", 0)
        line = "Evals: %s, %d of %d right (%d%%), " % (name, passed, n, lib.eval_percent(passed, n))
        if summary.get("met"):
            line += "target met."
            if isinstance(summary.get("time_p95_s"), (int, float)):
                line += " Slowest 5%%: %.3f s." % summary["time_p95_s"]
            if isinstance(summary.get("cost_per_example"), (int, float)):
                line += " Cost per example: %s" % lib.eval_money(summary["cost_per_example"], summary.get("cost_unit"))
        else:
            words = _target_words(summary)
            line += "target NOT met (%s)" % words if words else "target NOT met"
        tried = improve.get(summary.get("set"))
        if tried:
            line = line.rstrip(".") + ". Tried to improve: %s, %d%% to %d%%." % (
                _plural(tried["rounds"], "round"), lib.eval_percent_of_accuracy(tried["from"]),
                lib.eval_percent_of_accuracy(tried["to"]))
        lines.append(line)
    if len(evals) > 3:
        lines.append("and %d more" % (len(evals) - 3))
    return lines


def render_card(report, counts, title, failed=False, improve=None):
    b = report["build"]
    open_count = len(b["open_spans"])
    if open_count:
        result = "Still open: %s never closed" % _plural(open_count, "thing")
    elif failed:
        result = "Failed"
    else:
        result = "Finished"
    lines = ["# Report card: %s" % title, "", "Result: %s" % result,
             "Total time: %s from first to last event" % duration_text(b["wall_s"])]
    went = ", ".join("%s %d%%" % (r["phase_label"], round(r["share"] * 100)) for r in report["by_phase"][:5])
    lines.append("Where the time went: %s" % (went or "nothing recorded"))
    pieces = {row["node"]: row for row in report["loops"]}
    slowest = next((r for r in report["by_node"] if r["node"] in pieces), None) or (
        report["by_node"][0] if report["by_node"] else None)
    if slowest:
        tries = pieces[slowest["node"]]["loops"] if slowest["node"] in pieces else slowest["calls"]
        lines.append("Slowest piece: %s, %s, %s" % (
            slowest["node_label"], duration_text(slowest["time_s"]), _plural(tries, "try", "tries")))
    else:
        lines.append("Slowest piece: none recorded")
    if report["loops"]:
        lines.append("Tries per piece: " + ", ".join(
            "%s %d" % (r["node_label"], r["loops"]) for r in report["loops"]))
    else:
        lines.append("Tries per piece: none recorded")
    w = report["waits"]
    wait = "Waiting on a person: %s in %s" % (duration_text(w["human_s"]), _plural(w["human_count"], "wait"))
    if w["longest_human"]:
        wait += " (longest: %s, %s)" % (w["longest_human"]["gate"], duration_text(w["longest_human"]["s"]))
    lines.append(wait)
    g = report["idle_gaps"]
    lines.append("Idle time nobody was working: %s in %s" % (
        duration_text(g["total_s"]), _plural(len(g["gaps"]), "gap")))
    lines.append("Things that failed: %s" % _failure_summary(report["failures"]))
    if report.get("evals"):
        lines += eval_card_lines(report["evals"], improve)
    lines += ["", "Top 3 bottlenecks"]
    if report["bottlenecks"]:
        for row in report["bottlenecks"]:
            lines.append("%d. %s" % (row["rank"], row["plain"]))
    else:
        lines.append("None: no time was recorded.")
    lines += ["", "Data quality: %s, %s never closed, %d without a recorded time" % (
        _plural(b["bad_lines"], "unreadable line"), _plural(open_count, "thing"),
        b["unknown_duration_spans"])]
    if counts is None:
        lines.append("Checks: not run (no list of expected calls)")
    else:
        lines.append("Checks: Expected %(expected)d, logged %(logged)d, matched %(matched)d, "
                     "missing %(missing)d, unplanned %(unplanned)d, duplicate %(duplicate)d, "
                     "unfinished %(unfinished)d." % counts)
    return "\n".join(lines[:30]) + "\n"


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------

def _usage(message):
    raise lib.FactoryError(lib.EXIT.USAGE, "factory: " + message, "invalid arguments")


HELP = {
    "trace-report": (
        "factory trace-report [--build <project>/<build>] [--json] [--gap SECONDS] [--no-write]\n"
        "  Where the time went in a build: by phase, piece and role, tries, waits, idle gaps,\n"
        "  failures and the top 3 bottlenecks. Writes two new files under reports/ unless --no-write.\n"
        "  --json prints the numbers as JSON. --gap sets the idle gap length (default 300 seconds)."),
    "report-card": (
        "factory report-card [--build <project>/<build>]\n"
        "  A short end-of-build summary in plain words (30 lines at most), written to a new file under reports/."),
}


def _parse(argv, command):
    opts = {"build": None, "json": False, "gap": DEFAULT_GAP_S, "write": True}
    allowed = ("--build",) if command == "report-card" else ("--build", "--json", "--gap", "--no-write")
    items = list(argv)
    if any(item in ("-h", "--help") for item in items):
        opts["help"] = True
        return opts
    while items:
        item = items.pop(0)
        name, equals, inline = item.partition("=")
        if name not in allowed:
            _usage("unknown option '%s' (try: factory %s --build <project>/<build>)" % (item, command))
        if name in ("--json", "--no-write"):
            if equals:
                _usage("%s takes no value" % name)
            if name == "--json":
                opts["json"] = True
            else:
                opts["write"] = False
            continue
        if equals:
            value = inline
        elif items:
            value = items.pop(0)
        else:
            _usage("%s needs a value" % name)
        if name == "--build":
            opts["build"] = value
        else:
            if not (value.isascii() and value.isdigit()) or int(value) < 1:
                _usage("--gap must be a whole number of seconds, 1 or more")
            opts["gap"] = int(value)
    return opts


def _write_new(folder, name, text):
    """Create a new file in `folder`; never replaces one (a numbered name is used on a clash)."""
    folder.mkdir(parents=True, exist_ok=True)
    stem, dot, ext = name.rpartition(".")
    number = 1
    while True:
        candidate = name if number == 1 else "%s-%d.%s" % (stem, number, ext)
        try:
            with open(str(folder / candidate), "x", encoding="utf-8") as stream:
                stream.write(text)
            return folder / candidate
        except FileExistsError:
            number += 1


def _index(folder, now_text, kind, path, build):
    lib.append_jsonl_locked(folder / "index.jsonl", {
        "ts": now_text, "kind": kind, "file": "reports/" + path.name,
        "project": build.project, "build": build.id}, mkdir=True)


def _load(opts):
    """(build, report, read, now_text), after the exit-3 and exit-4 checks of SPEC 6.1."""
    build = lib.select_build({"build": opts["build"]})
    log = build.dir / "trace.jsonl"
    try:
        size = log.stat().st_size
    except FileNotFoundError:
        raise lib.BuildNotFound("factory: no log found at %s" % log)
    except OSError:
        raise lib.BuildNotFound("factory: the log at %s could not be read" % log)
    empty = lib.FactoryError(
        lib.EXIT.EMPTY, "factory: the log for %s/%s is empty. Nothing to report." % (build.project, build.id),
        "log is empty")
    has_evals = bool(lib.eval_summaries(build.dir)[0])  # eval results are something to report on
    if size == 0 and not has_evals:
        raise empty
    now_text = lib.now()
    report, read, timed = _analyse(build.dir, now_text, opts["gap"])
    if has_evals:
        return build, report, read, now_text
    if not read["spans"]:
        raise empty
    if timed == 0:
        raise lib.FactoryError(lib.EXIT.EMPTY, "factory: no span in this log has a duration. Report not written.",
                               "log has no durations")
    return build, report, read, now_text


def _improve_info(build_dir, report):
    """{set id: {rounds, from, to}} for the sets that have an improve session; never raises."""
    found = {}
    if not report.get("evals"):
        return found
    try:
        import evals as evals_module
        for summary in report["evals"]:
            info = evals_module.improve_summary(build_dir, summary.get("set"))
            if info:
                found[summary.get("set")] = info
    except Exception:
        return {}
    return found


def _run(command, argv):
    try:
        return _run_inner(command, argv)
    except OSError as exc:
        raise lib.FactoryError(lib.EXIT.NO, "factory: the report could not be written (check that the reports folder "
                               "can be written to).", "report not written")


def _run_inner(command, argv):
    opts = _parse(argv, command)
    if opts.get("help"):
        sys.stdout.write(HELP[command] + "\n")
        return lib.EXIT.OK
    build, report, read, now_text = _load(opts)
    folder = build.dir / "reports"
    stamp = _stamp(now_text)
    if command == "report-card":
        counts = _check_counts(build.dir, read, now_text)
        title = _clean(read["meta"].get("title")) or "%s/%s" % (build.project, build.id)
        card = render_card(report, counts, title, _ended_failed(read), _improve_info(build.dir, report))
        path = _write_new(folder, "REPORT-CARD-%s.md" % stamp, card)
        _index(folder, now_text, "report-card", path, build)
        sys.stdout.write(card)
        return lib.EXIT.OK
    text = render_markdown(report)
    if opts["write"]:
        md = _write_new(folder, "TRACE-REPORT-%s.md" % stamp, text)
        js = _write_new(folder, "trace-report-%s.json" % stamp,
                        json.dumps(report, indent=2) + "\n")
        _index(folder, now_text, "trace-report", md, build)
        _index(folder, now_text, "trace-report-json", js, build)
    if opts["json"]:
        sys.stdout.write(json.dumps(report, indent=2) + "\n")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return lib.EXIT.OK


def _command_from_process():
    """Which command factory.py is running: both commands come to main(argv) without the name."""
    return "report-card" if sys.argv[1:2] == ["report-card"] else "trace-report"


def _guarded(command, argv):
    try:
        return _run(command, list(argv))
    except lib.FactoryError as exc:
        sys.stderr.write(exc.line() + "\n")
        return exc.code


def main_trace(argv):
    return _guarded("trace-report", argv)


def main_card(argv):
    return _guarded("report-card", argv)


def main(argv=None):
    """Entry point from factory.py: `argv` is what follows the command name."""
    if argv is None:
        argv = sys.argv[1:]
        if argv[:1] in (["trace-report"], ["report-card"]):
            argv = argv[1:]
    argv = list(argv)
    return _guarded(_command_from_process(), argv)


if __name__ == "__main__":
    sys.exit(main())
