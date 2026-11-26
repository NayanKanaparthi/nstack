"""Deterministic fake system-under-test for eval acceptance tests."""

import json
import os
import signal
import sys
import time


table = json.loads(open(os.environ["FAKE_TABLE"], encoding="utf-8").read())
example_id = os.environ.get("FACTORY_EVAL_ID", "")
entry = table.get(example_id)
if entry is None:
    sys.stdout.write("unknown")
    raise SystemExit(9)

if entry.get("pidfile"):
    open(entry["pidfile"], "w", encoding="utf-8").write(str(os.getpid()))

stdin_text = "" if entry.get("no_stdin") else sys.stdin.read()
if os.environ.get("FAKE_LOG"):
    with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "id": example_id,
            "stdin": stdin_text,
            "cwd": os.getcwd(),
            "set": os.environ.get("FACTORY_EVAL_SET"),
        }, ensure_ascii=False, sort_keys=True) + "\n")

if entry.get("sleep"):
    time.sleep(float(entry["sleep"]))
sys.stdout.write(entry.get("out", ""))
repeat = entry.get("out_repeat")
if repeat:
    sys.stdout.write(str(repeat["char"]) * int(repeat["count"]))
sys.stdout.flush()
for line in entry.get("err_lines", []):
    sys.stderr.write(str(line) + "\n")
sys.stderr.flush()
if entry.get("signal"):
    os.kill(os.getpid(), int(entry["signal"]))
raise SystemExit(int(entry.get("exit", 0)))
