"""Generate deterministic synthetic factory fixtures A through D.

This script refuses to replace an existing fixture file. Run it only in a new
fixture tree. It never reads a real factory log.
"""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def line(span_id, ts, kind=None, status="running", **fields):
    value = {
        "v": 1, "span_id": span_id, "ts": ts,
        "project": "demo", "feature": "alpha", "status": status,
    }
    if kind is not None:
        value["kind"] = kind
    value.update(fields)
    return value


def write_new(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SystemExit("refusing to replace existing fixture: %s" % path)
    with path.open("w") as stream:
        for value in lines:
            if isinstance(value, str):
                stream.write(value + "\n")
            else:
                stream.write(json.dumps(value, sort_keys=True) + "\n")


def pair(key, kind, actor, phase, start, end, **fields):
    start_fields = dict(fields)
    start_fields.update({"actor": actor, "phase": phase, "start": start})
    end_fields = {"end": end, "duration_s": seconds(start, end)}
    return [line(key, start, kind=kind, **start_fields), line(key, end, status="done", **end_fields)]


def seconds(start, end):
    def total(value):
        hh, mm, ss = map(int, value[11:19].split(":"))
        return hh * 3600 + mm * 60 + ss
    return total(end) - total(start)


def iteration(key, ts, node, number, verdict, passed, failed, before):
    return line(
        key, ts, kind="iteration", status="done", actor="checker", phase="build",
        node=node, iteration=number, verdict=verdict, rubric_before=before,
        rubric_after=passed, rubric_pass=passed, rubric_fail=failed,
        newly_passing=[item for item in passed if item not in before],
        newly_failing=[item for item in before if item not in passed],
        failure_class="impl-bug" if verdict == "rejected" else None,
    )


def fixture_alpha():
    day = "2026-01-10T"
    at = lambda clock: day + clock + "Z"
    lines = [line("f1", at("10:00:00"), kind="feature", actor="orchestrator",
                  phase="intake", start=at("10:00:00"))]
    lines += pair("a1", "agent_call", "planner", "plan", at("10:00:00"), at("10:12:00"),
                  model="fable-5-2", node="plan", call="plan.planner.1", input_chars=4000,
                  input_ref="messages/a1.in.md")
    lines += pair("a2", "agent_call", "plan-reviewer", "plan", at("10:12:00"), at("10:18:00"),
                  model="gpt-5.6-sol", node="plan-review", call="plan.reviewer.1",
                  input_ref="messages/a2.in.md")
    lines += pair("w1", "wait", "human", "gate-a", at("10:20:00"), at("10:50:00"),
                  waiting_on="human", gate="GATE A", question="Approve this plan?",
                  recommend="Yes. The tests cover every required behavior.", answer="yes")
    specs = [
        ("a3", "maker", "N1", "Greeting flag", 1, "10:50:00", "11:00:00", None, None),
        ("a4", "checker", "N1", "Greeting flag", 1, "11:00:00", "11:05:00", "rejected", ["R1"]),
        ("a5", "maker", "N1", "Greeting flag", 2, "11:05:00", "11:15:00", None, None),
        ("a6", "checker", "N1", "Greeting flag", 2, "11:15:00", "11:20:00", "rejected", ["R1"]),
        ("a7", "maker", "N1", "Greeting flag", 3, "11:20:00", "11:30:00", None, None),
        ("a8", "checker", "N1", "Greeting flag", 3, "11:30:00", "11:35:00", "rejected", ["R2", "R3"]),
        ("a9", "maker", "N1", "Greeting flag", 4, "11:35:00", "11:40:00", None, None),
        ("a10", "checker", "N1", "Greeting flag", 4, "11:40:00", "11:45:00", "approved", ["R1", "R2", "R3"]),
        ("b1", "maker", "N2", "Help text", 1, "10:50:00", "10:58:00", None, None),
        ("b2", "checker", "N2", "Help text", 1, "11:05:00", "11:08:00", "approved", ["R4"]),
    ]
    previous = {"N1": [], "N2": []}
    iteration_number = {"N1": 0, "N2": 0}
    for key, actor, node, label, attempt, start, end, verdict, passed in specs:
        fields = {
            "model": "opus-5-5" if actor == "maker" else "fable-5-2",
            "node": node, "node_label": label, "iteration": attempt,
            "call": "%s.%s.%s" % (node, actor, attempt),
            "input_ref": "messages/%s.in.md" % key,
        }
        if verdict:
            fields.update({"verdict": verdict, "rubric_pass": passed,
                           "rubric_fail": [x for x in ["R1", "R2", "R3"] if x not in passed]})
        lines += pair(key, "agent_call", actor, "build", at(start), at(end), **fields)
        if verdict:
            iteration_number[node] += 1
            lines.append(iteration("i-" + key, at(end), node, iteration_number[node], verdict,
                                   passed, fields["rubric_fail"], previous[node]))
            previous[node] = passed
        if key == "a6":
            lines.append("not json")
    lines.append(line("x1", at("11:50:00"), kind="agent_call", status="done", actor="maker",
                      model="opus-5-5", node="N3", node_label="Third piece", phase="build",
                      iteration=1, call="N3.maker.1", end=at("11:50:00")))
    lines += pair("c1", "command", "orchestrator", "e2e", at("12:00:00"), at("12:02:00"),
                  node="e2e")
    lines[-1].update({"status": "failed", "failure_class": "env-tooling"})
    lines.append(line("w2", at("12:02:00"), kind="wait", actor="human", phase="gate-b",
                      start=at("12:02:00"), waiting_on="human", gate="GATE B",
                      question="Release this build?", recommend="Yes. All required checks passed."))
    write_new(HERE / "alpha" / "trace.jsonl", lines)
    write_new(HERE / "alpha" / "expected.jsonl", [
        {"call": "%s.%s.%s" % (node, role, attempt), "node": node, "role": role,
         "try": attempt, "added_by": "fixture"}
        for node, count in (("N1", 4), ("N2", 1))
        for attempt in range(1, count + 1) for role in ("maker", "checker")
    ] + [{"call": "N3.maker.1", "node": "N3", "role": "maker", "try": 1,
          "added_by": "fixture"}])
    build = {
        "project": "demo", "build": "alpha", "title": "Alpha fixture", "repo": "/synthetic/demo",
        "started": at("10:00:00"), "stop_times": [
            {"label": "Soon", "at": at("12:22:00")},
            {"label": "Later", "at": at("13:47:00")},
            {"label": "Past", "at": at("12:07:00")},
        ],
    }
    write_new(HERE / "alpha" / "build.json", [build])
    messages = HERE / "alpha" / "messages"
    messages.mkdir()
    for key in ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10", "b1", "b2"]:
        (messages / (key + ".in.md")).write_text("synthetic prompt for %s\n" % key)


def fixture_beta():
    at = lambda clock: "2026-01-10T" + clock + "Z"
    lines = [
        {"v": 1, "span_id": "f1", "ts": at("10:00:00"), "project": "demo", "feature": "beta",
         "kind": "feature", "actor": "orchestrator", "phase": "intake", "status": "running",
         "start": at("10:00:00")},
        {"v": 1, "span_id": "a1", "ts": at("10:00:00"), "project": "demo", "feature": "beta",
         "kind": "agent_call", "actor": "maker", "model": "opus-5-5", "node": "N1",
         "node_label": "Greeting flag", "iteration": 2, "call": "N1.maker.2", "phase": "build",
         "status": "running", "start": at("10:00:00"), "output_ref": "messages/a1.out.md"},
    ]
    write_new(HERE / "beta" / "trace.jsonl", lines)
    write_new(HERE / "beta" / "build.json", [{"project": "demo", "build": "beta",
              "title": "Beta fixture", "started": at("10:00:00"), "stop_times": []}])
    messages = HERE / "beta" / "messages"
    messages.mkdir()
    (messages / "a1.out.md").write_text("starting\n\nwrote hello.py\n")


def fixture_charlie():
    good = [
        {"span_id": "c1", "ts": "2026-01-10T09:00:00Z", "kind": "agent_call", "actor": "maker",
         "node": "N1", "model": "old-model", "status": "running", "start": "2026-01-10T09:00:00Z"},
        {"span_id": "c1", "ts": "2026-01-10T09:02:00Z", "status": "done", "model": None,
         "end": "2026-01-10T09:02:00Z", "duration_s": 120},
        {"span_id": "c2", "end": "2026-01-10T09:03:00Z", "kind": "command", "actor": "orchestrator",
         "status": "done"},
        {"span_id": "c3", "ts": "2026-01-10T09:04:00Z", "kind": "command", "actor": "orchestrator",
         "status": "done warn"},
        {"span_id": "c4", "ts": "2026-01-10T09:05:00Z", "kind": "command", "actor": "orchestrator",
         "status": "failed env-tooling"},
        {"span_id": "c5", "ts": "2026-01-10T09:06:00Z", "kind": "wait", "actor": "human",
         "status": "done", "start": "2026-01-10T09:05:00Z", "end": "2026-01-10T09:06:00Z",
         "duration_s": 60},
    ]
    wrong = [
        {"span_id": ["bad"], "kind": "command", "status": "done"},
        {"span_id": "bad-start", "start": "yesterday", "kind": "command", "status": "done"},
        {"span_id": "bad-try", "iteration": "two", "kind": "agent_call", "status": "done"},
        {"span_id": "bad-duration", "duration_s": -5, "kind": "command", "status": "done"},
        ["not", "an", "object"],
        {"span_id": "bad-notes", "notes": 7, "kind": "command", "status": "done"},
    ]
    write_new(HERE / "charlie" / "trace.jsonl", good + wrong)
    write_new(HERE / "charlie" / "good.jsonl", good)
    write_new(HERE / "charlie" / "wrong.jsonl", wrong)


def fixture_delta():
    lines = [
        {"span_id": "s001", "ts": "2026-11-25T12:50:00Z", "kind": "phase", "actor": "orchestrator", "status": "done"},
        {"span_id": "s002", "ts": "2026-11-25T12:51:00Z", "kind": "command", "actor": "orchestrator", "status": "done"},
        {"span_id": "s003", "ts": "2026-11-25T12:52:15Z", "kind": "agent_call", "actor": "planner", "node": "PLAN", "status": "running"},
        {"span_id": "s003", "ts": "2026-11-25T13:08:43Z", "status": "done", "duration_s": 988},
        {"span_id": "s004", "ts": "2026-11-25T13:08:44Z", "kind": "command", "actor": "orchestrator", "status": "done warn"},
        {"span_id": "s005", "ts": "2026-11-25T13:08:50Z", "kind": "command", "actor": "orchestrator", "status": "done"},
        {"span_id": "s006", "ts": "2026-11-25T13:08:34Z", "kind": "agent_call", "actor": "plan-reviewer", "node": "REVIEW", "iteration": 1, "status": "running"},
        {"span_id": "s006", "ts": "2026-11-25T13:14:40Z", "status": "done"},
        {"span_id": "s007", "ts": "2026-11-25T13:15:10Z", "kind": "agent_call", "actor": "planner", "node": "PLAN", "iteration": 2, "status": "running"},
    ]
    write_new(HERE / "delta" / "trace.jsonl", lines)


def main():
    fixture_alpha()
    fixture_beta()
    fixture_charlie()
    fixture_delta()


if __name__ == "__main__":
    main()
