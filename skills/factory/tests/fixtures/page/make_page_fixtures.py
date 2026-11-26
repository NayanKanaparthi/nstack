#!/usr/bin/env python3
"""Create disposable browser homes for T-PG-70..88 without using real user state."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PLAN_TEST = ROOT / "skills" / "factory" / "tests" / "test_plan_board.py"


def load_plan_helpers():
    spec = importlib.util.spec_from_file_location("page_fixture_plan_helpers", str(PLAN_TEST))
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "skills" / "factory"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
        sys.path.pop(0)
    return module


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def build_folder(home, build):
    return home / "runs" / "toy" / build


def metadata(build, title="Toy: add two options"):
    return {
        "project": "toy", "build": build, "title": title,
        "started": "2026-01-10T14:00:00Z",
        "stop_times": [{"label": "GATE B", "plain": "Release decision",
                        "at": "2026-01-10T17:30:00Z"}],
    }


def expected():
    return [{"call": "%s.%s.1" % (piece, role), "node": piece, "actor": role,
             "added_by": "graph"}
            for piece in ("A1", "B1", "B2", "C1") for role in ("maker", "checker")]


def write_build(home, name, lines, helpers, plan=True, title="Toy: add two options"):
    folder = build_folder(home, name)
    folder.mkdir(parents=True)
    for line in lines:
        if line.get("kind") == "agent_call":
            line.setdefault("iteration", 1)
    write_jsonl(folder / "trace.jsonl", lines)
    write_json(folder / "build.json", metadata(name, title))
    write_jsonl(folder / "expected.jsonl", expected())
    (folder / "messages").mkdir()
    if plan:
        write_json(folder / "plan.json", helpers.plan_value())
    return folder


def close(helpers, span, ts, plain, **extra):
    return helpers.end_line(span, ts, plain, **extra)


def completed_lines(helpers, with_gate=True, close_gate=False):
    lines = helpers.pg1_lines()
    lines.extend([
        close(helpers, "b2c1", "2026-01-10T14:35:00Z",
              "The checker approved the quiet option. This piece is finished.", verdict="approved"),
        close(helpers, "b1m2", "2026-01-10T14:50:00Z",
              "The builder made the requested fixes. A checker reads them next."),
        helpers.start_line("b1c2", "2026-01-10T14:50:00Z", "checker", "B1.checker.2",
                           "B1", "fable-5-2"),
        close(helpers, "b1c2", "2026-01-10T15:00:00Z",
              "The checker approved the shout option. This piece is finished.", verdict="approved"),
        helpers.start_line("c1m1", "2026-01-10T15:00:00Z", "maker", "C1.maker.1",
                           "C1", "sonnet-5-5"),
        close(helpers, "c1m1", "2026-01-10T15:10:00Z",
              "The builder prepared the final check. A checker reads it next."),
        helpers.start_line("c1c1", "2026-01-10T15:10:00Z", "checker", "C1.checker.1",
                           "C1", "fable-5-2"),
        close(helpers, "c1c1", "2026-01-10T15:20:00Z",
              "The checker approved the final check. This piece is finished.", verdict="approved"),
    ])
    if with_gate:
        lines.append({
            "v": 1, "span_id": "gate1", "ts": "2026-01-10T15:25:00Z",
            "start": "2026-01-10T15:25:00Z", "kind": "wait", "actor": "human",
            "status": "running", "waiting_on": "human", "gate": "GATE B", "node": "C1",
            "question": "Do you want the toy program released now?",
            "recommend": "Yes, release it now. Both options passed their checks.",
            "plain": "Do you want the toy program released now?", "plain_source": "agent",
        })
    if close_gate:
        lines.append({
            "v": 1, "span_id": "gate1", "ts": "2026-01-10T15:50:00Z",
            "end": "2026-01-10T15:50:00Z", "status": "done", "answer": "Yes",
            "plain": "You answered this decision, and the build carried on.",
            "plain_source": "auto",
        })
        lines.append({
            "v": 1, "span_id": "f1", "ts": "2026-01-10T15:51:00Z",
            "end": "2026-01-10T15:51:00Z", "status": "done",
        })
    return lines


def make(home):
    helpers = load_plan_helpers()
    write_build(home, "pg1", helpers.pg1_lines(), helpers)

    stopped = helpers.pg1_lines() + [close(
        helpers, "b2c1", "2026-01-10T14:50:00Z",
        "The checker stopped because its daily usage limit ran out. A new checker starts after the limit resets.",
        status="stopped", stop_reason="usage_limit",
        next_step="A new checker starts after the limit resets.")]
    write_build(home, "pg-stop", stopped, helpers)
    write_build(home, "pg-needs", completed_lines(helpers), helpers)
    write_build(home, "pg-done", completed_lines(helpers, close_gate=True), helpers)

    old_lines = [
        helpers.start_line("old1", "2026-01-10T14:00:00Z", "maker", "X1.maker.1", "X1",
                           "sonnet-5-5", node_label="First piece"),
        close(helpers, "old1", "2026-01-10T14:05:00Z",
              "The builder finished the first piece. A checker reads it next."),
        helpers.start_line("old2", "2026-01-10T14:06:00Z", "maker", "X2.maker.1", "X2",
                           "sonnet-5-5"),
        close(helpers, "old2", "2026-01-10T14:10:00Z",
              "The builder finished another piece. A checker reads it next."),
    ]
    write_build(home, "pg-old", old_lines, helpers, plan=False, title="Old build")

    label_lines = [
        helpers.start_line("label1", "2026-01-10T14:00:00Z", "maker", "N2.maker.1", "N2",
                           "sonnet-5-5", node_label="N2 trace core"),
        close(helpers, "label1", "2026-01-10T14:01:00Z",
              "The builder finished one piece. A checker reads it next."),
        helpers.start_line("label2", "2026-01-10T14:02:00Z", "maker", "K1.maker.1", "K1",
                           "sonnet-5-5", node_label="Trace core"),
        close(helpers, "label2", "2026-01-10T14:03:00Z",
              "The builder finished another piece. A checker reads it next."),
    ]
    write_build(home, "pg-label", label_lines, helpers, plan=False, title="Label fixture")

    hostile = "<img src=x onerror=window.__x=1>"
    xss_plan = helpers.plan_value()
    xss_plan["pieces"][0]["name"] = hostile
    xss_plan["pieces"][0]["purpose"] = hostile
    xss_plan["stages"][0]["name"] = hostile
    xss = write_build(home, "xss", completed_lines(helpers), helpers, title=hostile)
    write_json(xss / "plan.json", xss_plan)
    with (xss / "trace.jsonl").open("a") as stream:
        stream.write(json.dumps({
            "v": 1, "span_id": "hostile", "ts": "2026-01-10T15:30:00Z",
            "kind": "checkpoint", "actor": "orchestrator", "status": "done",
            "plain": hostile, "node_label": hostile,
        }, sort_keys=True) + "\n")

    legacy = home / "runs" / "demo"
    legacy.mkdir(parents=True)
    shutil.copytree(ROOT / "skills" / "factory" / "tests" / "fixtures" / "delta",
                    legacy / "delta")
    legacy_shape = "at" + "las-shape"
    shutil.copytree(ROOT / "tests" / "fixtures" / legacy_shape,
                    legacy / legacy_shape)


def main(argv):
    if len(argv) != 2:
        print("usage: make_page_fixtures.py HOME", file=sys.stderr)
        return 2
    home = Path(argv[1]).resolve()
    if home.exists() and any(home.iterdir()):
        print("fixture home must be absent or empty", file=sys.stderr)
        return 2
    home.mkdir(parents=True, exist_ok=True)
    make(home)
    empty = home.parent / (home.name + "-empty")
    empty.mkdir(exist_ok=True)
    print(str(home))
    print(str(empty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
