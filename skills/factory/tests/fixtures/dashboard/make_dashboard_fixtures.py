#!/usr/bin/env python3
"""Create disposable standalone-dashboard browser fixtures."""

import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
PAGE_FIXTURE = HERE.parent / "page" / "make_page_fixtures.py"


def load_page_fixtures():
    spec = importlib.util.spec_from_file_location("dashboard_page_fixtures", str(PAGE_FIXTURE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def append_jsonl(path, value):
    with Path(path).open("a") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def retitle(folder, title):
    path = folder / "build.json"
    value = json.loads(path.read_text())
    value["title"] = title
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def make(home):
    page = load_page_fixtures()
    helpers = page.load_plan_helpers()
    page.write_build(home, "pg1", helpers.pg1_lines(), helpers, title="Add two options")
    stopped = helpers.pg1_lines() + [page.close(
        helpers, "b2c1", "2026-01-10T14:50:00Z",
        "The checker stopped because its daily usage limit ran out. A new checker starts after the limit resets.",
        status="stopped", stop_reason="usage_limit",
        next_step="A new checker starts after the limit resets.")]
    page.write_build(home, "pg-stop", stopped, helpers, title="Stopped checker example")
    page.write_build(home, "pg-needs", page.completed_lines(helpers), helpers,
                     title="Release the greeting tool")
    done = page.completed_lines(helpers, close_gate=True)
    done.append({
        "v": 1, "span_id": "feature", "ts": "2026-01-10T15:40:00Z",
        "end": "2026-01-10T15:40:00Z", "status": "done", "leftovers": [],
        "plain": "The build was marked finished.",
    })
    page.write_build(home, "pg-done", done, helpers, title="Finish the greeting tool")

    hostile = "<img src=x onerror=window.__x=1>"
    xss_plan = helpers.plan_value()
    xss_plan["pieces"][0]["name"] = hostile
    xss_plan["pieces"][0]["plain_name"] = hostile
    xss_plan["pieces"][0]["purpose"] = hostile
    xss_plan["stages"][0]["name"] = hostile
    xss = page.write_build(home, "xss", page.completed_lines(helpers), helpers, title=hostile)
    page.write_json(xss / "plan.json", xss_plan)
    append_jsonl(xss / "trace.jsonl", {
        "v": 1, "span_id": "hostile", "ts": "2026-01-10T15:30:00Z",
        "kind": "checkpoint", "actor": hostile, "model": hostile, "call": hostile,
        "status": "done", "plain": "</script><script>window.__x=99</script>",
        "node_label": hostile, "next_step": hostile, "question": hostile,
        "recommend": hostile, "deadline": hostile,
    })


def main(argv):
    if len(argv) != 2:
        print("usage: make_dashboard_fixtures.py HOME", file=sys.stderr)
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
