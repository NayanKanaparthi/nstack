#!/usr/bin/env python3
"""Create disposable tn/* homes for the TONIGHT test plan."""

import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAGE_FIXTURES = HERE.parent / "page" / "make_page_fixtures.py"


def load_page_fixtures():
    spec = importlib.util.spec_from_file_location("tonight_page_fixtures", str(PAGE_FIXTURES))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def feature_line():
    return {
        "v": 1, "span_id": "f1", "ts": "2026-01-10T14:00:00Z",
        "start": "2026-01-10T14:00:00Z", "kind": "feature",
        "actor": "orchestrator", "status": "running",
    }


def approved_a1(helpers):
    return [
        feature_line(),
        helpers.start_line("a1m1", "2026-01-10T14:00:00Z", "maker",
                           "A1.maker.1", "A1", "sonnet-5-5"),
        helpers.end_line("a1m1", "2026-01-10T14:10:00Z",
                         "The builder finished the greeting words. A checker reads them next."),
        helpers.start_line("a1c1", "2026-01-10T14:10:00Z", "checker",
                           "A1.checker.1", "A1", "fable-5-2"),
        helpers.end_line("a1c1", "2026-01-10T14:15:00Z",
                         "The checker approved the greeting words. This piece is finished.",
                         verdict="approved"),
    ]


def built_lines(helpers):
    return approved_a1(helpers) + [
        helpers.start_line("b1m1", "2026-01-10T14:30:00Z", "maker",
                           "B1.maker.1", "B1", "sonnet-5-5"),
        helpers.end_line("b1m1", "2026-01-10T14:35:00Z",
                         "The builder finished this piece. No checker has started on it yet."),
    ]


def seven_piece_plan():
    words = ("one", "two", "three", "four", "five", "six", "seven")
    return {
        "v": 1, "source": "GRAPH.yaml", "generated": "2026-01-10T14:00:00Z",
        "pieces": [
            {"id": "P%d" % index, "name": "Plan piece %s" % word,
             "tech_name": "Piece %d" % index, "purpose": "Complete plan piece %s." % word,
             "depends_on": [], "stage": index}
            for index, word in enumerate(words, 1)
        ],
        "stages": [
            {"n": index, "name": "Stage %d" % index,
             "purpose": "Complete plan piece %s." % word, "members": ["P%d" % index]}
            for index, word in enumerate(words, 1)
        ],
    }


def metadata(name, title="Toy: add two options", stop_times=None):
    return {
        "project": "tn", "build": name, "title": title,
        "started": "2026-01-10T14:00:00Z",
        "stop_times": list(stop_times or []),
    }


def write_build(home, name, lines, plan, expected, title="Toy: add two options",
                stop_times=None):
    folder = home / "runs" / "tn" / name
    folder.mkdir(parents=True)
    for line in lines:
        if line.get("kind") == "agent_call":
            line.setdefault("iteration", 1)
    write_jsonl(folder / "trace.jsonl", lines)
    write_json(folder / "build.json", metadata(name, title, stop_times))
    write_jsonl(folder / "expected.jsonl", expected)
    write_json(folder / "plan.json", plan)
    (folder / "messages").mkdir()
    return folder


def toy_expected(page):
    return page.expected()


def hostile_value(marker, tag):
    return marker + " " + tag


def make(home):
    page = load_page_fixtures()
    helpers = page.load_plan_helpers()
    toy_plan = helpers.plan_value()
    expected = toy_expected(page)

    built = built_lines(helpers)
    write_build(home, "built", list(built), toy_plan, expected)
    write_build(home, "quiet", list(built), toy_plan, expected)
    write_build(home, "checking", list(built) + [
        helpers.start_line("b1c1", "2026-01-10T14:36:00Z", "checker",
                           "B1.checker.1", "B1", "fable-5-2"),
    ], toy_plan, expected)

    stale = approved_a1(helpers) + [
        helpers.start_line("b1m1", "2026-01-10T14:30:00Z", "maker",
                           "B1.maker.1", "B1", "sonnet-5-5"),
        {"v": 1, "span_id": "stale-note", "ts": "2026-01-10T14:35:00Z",
         "kind": "checkpoint", "actor": "orchestrator", "node": "B1",
         "status": "done", "plain": "The builder has not left a new note yet."},
    ]
    write_build(home, "stale", stale, toy_plan, expected)

    alldone = page.completed_lines(helpers, with_gate=False)
    alldone.append({
        "v": 1, "span_id": "done-note", "ts": "2026-01-10T15:30:00Z",
        "kind": "checkpoint", "actor": "orchestrator", "status": "done",
        "plain": "All four pieces passed their checks.",
    })
    write_build(home, "alldone", alldone, toy_plan, expected)

    opened = helpers.pg1_lines() + [
        helpers.end_line("b2c1", "2026-01-10T14:35:00Z",
                         "The checker approved the quiet option. This piece is finished.",
                         verdict="approved"),
        {"v": 1, "span_id": "gate-b", "ts": "2026-01-10T15:40:00Z",
         "start": "2026-01-10T15:40:00Z", "kind": "wait", "actor": "human",
         "status": "running", "waiting_on": "human", "gate": "GATE B",
         "question": "Do you want the build closed now?",
         "recommend": "Close it after the open work has a recorded reason.",
         "plain": "Do you want the build closed now?", "plain_source": "agent"},
    ]
    write_build(home, "open", opened, toy_plan, expected)

    other_plan = seven_piece_plan()
    other_expected = [{"call": "P1.checker.1", "node": "P1", "actor": "checker",
                       "added_by": "graph"}]
    other = [
        feature_line(),
        helpers.start_line("p1", "2026-01-10T14:30:00Z", "planner",
                           "P1.planner.1", "P1", "fable-5-2"),
        helpers.end_line("p1", "2026-01-10T14:35:00Z",
                         "The planner finished this piece. A checker reads it next."),
        {"v": 1, "span_id": "p1-note", "ts": "2026-01-10T14:35:30Z",
         "kind": "event", "actor": "orchestrator", "node": "P1", "status": "done",
         "node_label": "Planner model rule overridden", "plain": "A note was recorded."},
        helpers.start_line("x9", "2026-01-10T14:36:00Z", "investigator",
                           "X9.investigator.1", "X9", "grok-4"),
    ]
    write_build(home, "other", other, other_plan, other_expected, title="Seven piece plan")

    image = '<img src=x onerror="window.__tn=(window.__tn||0)+1">'
    script = "</script><script>window.__tn=99</script>"
    hostile_plan = helpers.plan_value()
    hostile_plan["pieces"][0]["name"] = hostile_value(image, "f-piece")
    hostile_plan["pieces"][0]["purpose"] = hostile_value(script, "f-purpose")
    hostile_plan["stages"][0]["name"] = hostile_value(image, "f-stage")
    hostile_lines = [
        feature_line(),
        helpers.start_line(
            "hostile-call", "2026-01-10T14:20:00Z", hostile_value(image, "f-actor"),
            hostile_value(script, "f-call"), "X1", hostile_value(image, "f-model"),
            node_label=hostile_value(script, "f-node-label"),
            notes=hostile_value(image, "f-notes"),
            next_step=hostile_value(script, "f-next-step")),
        helpers.end_line("hostile-call", "2026-01-10T14:25:00Z",
                         hostile_value(image, "f-plain"),
                         notes=hostile_value(script, "f-notes-end")),
        {"v": 1, "span_id": "hostile-gate", "ts": "2026-01-10T14:30:00Z",
         "start": "2026-01-10T14:30:00Z", "kind": "wait", "actor": "human",
         "status": "running", "waiting_on": "human", "gate": "GATE B",
         "question": hostile_value(image, "f-question"),
         "recommend": hostile_value(script, "f-answer"),
         "plain": hostile_value(image, "f-gate-plain"), "plain_source": "agent"},
    ]
    write_build(
        home, "hostile", hostile_lines, hostile_plan, expected,
        title=hostile_value(image, "f-title"),
        stop_times=[{"label": hostile_value(script, "f-deadline"),
                     "plain": "A hostile deadline label", "at": "2026-01-10T17:30:00Z"}],
    )


def main(argv):
    if len(argv) != 2:
        print("usage: make_tonight_fixtures.py HOME", file=sys.stderr)
        return 2
    home = Path(argv[1]).resolve()
    if home.exists() and any(home.iterdir()):
        print("fixture home must be absent or empty", file=sys.stderr)
        return 2
    home.mkdir(parents=True, exist_ok=True)
    make(home)
    print(str(home))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
