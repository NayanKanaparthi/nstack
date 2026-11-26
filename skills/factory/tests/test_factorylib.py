"""Unit tests for config, logging, reading, boards, and notification."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

from tests.common import (
    FIXTURES, PYTHON, SCRIPTS_DIR, FactoryTestCase, board_strings, read_jsonl,
    write_json, write_jsonl,
)


class ReadBuildTests(FactoryTestCase):
    def test_fixture_a_merge_and_bad_line(self):
        """T-READ-01: schema-v1 lines merge in first-seen order and isolate one bad line."""
        lib = self.require_module("factorylib")
        result = lib.read_build(FIXTURES / "alpha")
        self.assertEqual(result["lines"], 37)
        self.assertEqual(len(result["spans"]), 22)
        self.assertEqual(result["bad_lines"], [18])
        self.assertEqual([span["span_id"] for span in result["spans"][:5]],
                         ["f1", "a1", "a2", "w1", "a3"])
        a3 = next(span for span in result["spans"] if span["span_id"] == "a3")
        self.assertEqual(a3["start"], "2026-01-10T10:50:00Z")
        self.assertEqual(a3["end"], "2026-01-10T11:00:00Z")
        self.assertEqual(a3["duration_s"], 600)
        self.assertEqual(a3["status"], "done")

    def test_old_format_normalization(self):
        """T-READ-02: old status words, null merge fields, durations, and human waits normalize."""
        lib = self.require_module("factorylib")
        build = self.tmp / "runs" / "demo" / "old"
        build.mkdir(parents=True)
        (build / "trace.jsonl").write_bytes((FIXTURES / "charlie" / "good.jsonl").read_bytes())
        result = lib.read_build(build)
        spans = {span["span_id"]: span for span in result["spans"]}
        self.assertEqual(spans["c1"]["model"], "old-model")
        self.assertEqual(spans["c1"]["start"], "2026-01-10T09:00:00Z")
        self.assertEqual(spans["c3"]["status"], "done")
        self.assertIs(spans["c3"]["warn"], True)
        self.assertEqual(spans["c4"]["status"], "failed")
        self.assertEqual(spans["c4"]["failure_class"], "env-tooling")
        self.assertNotIn("duration_s", spans["c2"])
        self.assertEqual(spans["c5"]["waiting_on"], "human")

    def test_bad_core_and_soft_fields_never_escape(self):
        """T-READ-03: missing, empty, corrupt, wrong-core, and wrong-shown fields are safe."""
        lib = self.require_module("factorylib")
        missing = self.tmp / "missing"
        missing.mkdir()
        with self.assertRaises(lib.BuildNotFound):
            lib.read_build(missing)

        empty = self.tmp / "empty"
        empty.mkdir()
        (empty / "trace.jsonl").write_text("")
        self.assertEqual(lib.read_build(empty)["spans"], [])

        only_bad = self.tmp / "only-bad"
        only_bad.mkdir()
        (only_bad / "trace.jsonl").write_bytes((FIXTURES / "charlie" / "wrong.jsonl").read_bytes())
        bad_result = lib.read_build(only_bad)
        self.assertEqual(bad_result["spans"], [])
        self.assertEqual(bad_result["bad_lines"], list(range(1, 7)))

        mixed = lib.read_build(FIXTURES / "charlie")
        self.assertEqual(len(mixed["spans"]), 5)
        self.assertEqual(mixed["bad_lines"], list(range(7, 13)))

        soft_strings = (
            "question", "recommend", "answer", "gate", "waiting_on", "call",
            "node_label", "effort", "runner", "session", "cmd", "failure_class",
            "verdict", "input_ref", "output_ref", "why_not_done", "data_class",
        )
        wrong_values = (7, ["wrong"], {"wrong": True})
        for field in soft_strings:
            for wrong in wrong_values:
                with self.subTest(field=field, wrong=type(wrong).__name__):
                    build = self.tmp / ("soft-%s-%s" % (field, type(wrong).__name__))
                    build.mkdir()
                    base = {
                        "v": 1, "span_id": "s001", "ts": "2026-01-10T10:00:00Z",
                        "kind": "wait" if field == "question" else "agent_call",
                        "actor": "human" if field == "question" else "maker",
                        "status": "running", "start": "2026-01-10T10:00:00Z",
                    }
                    base[field] = wrong
                    write_jsonl(build / "trace.jsonl", [base])
                    read = lib.read_build(build)
                    self.assertEqual(len(read["spans"]), 1)
                    self.assertNotIn(field, read["spans"][0])
                    self.assertIn({"line": 1, "field": field}, read["bad_fields"])
                    board = lib.board(build, "2026-01-10T10:01:00Z")
                    json.dumps(board)
                    if field == "question":
                        self.assertEqual(board["waiting_on_you"][0]["question"],
                                         "A decision is needed (question not recorded)")

        special = (("notified", "wrong"), ("notified", {"desktop": []}), ("warn", "yes"))
        for field, wrong in special:
            with self.subTest(field=field, wrong=repr(wrong)):
                build = self.tmp / ("special-%s-%s" % (field, len(list(self.tmp.iterdir()))))
                build.mkdir()
                value = {"span_id": "s001", "ts": "2026-01-10T10:00:00Z",
                         "kind": "command", "actor": "orchestrator", "status": "done",
                         field: wrong}
                write_jsonl(build / "trace.jsonl", [value])
                result = lib.read_build(build)
                self.assertEqual(result["bad_fields"][0]["field"], field)
                self.assertNotIn(field, result["spans"][0])

    def test_live_old_format_fixture(self):
        """T-READ-04: old running lines get starts and two-line closed spans get measured."""
        lib = self.require_module("factorylib")
        result = lib.read_build(FIXTURES / "delta")
        self.assertEqual(result["bad_lines"], [])
        spans = {span["span_id"]: span for span in result["spans"]}
        self.assertNotIn("start", spans["s001"])
        self.assertNotIn("duration_s", spans["s001"])
        self.assertEqual(spans["s003"]["duration_s"], 988)
        self.assertEqual(spans["s006"]["start"], "2026-11-25T13:08:34Z")
        self.assertEqual(spans["s006"]["end"], "2026-11-25T13:14:40Z")
        self.assertEqual(spans["s006"]["duration_s"], 366)
        self.assertEqual(spans["s007"]["start"], "2026-11-25T13:15:10Z")
        board = lib.board(FIXTURES / "delta", "2026-11-25T13:20:10Z")
        agent = next(item for item in board["agents"] if item["key"] == "s007")
        self.assertEqual(agent["state"], "running")
        self.assertEqual(agent["elapsed_s"], 300)
        self.assertEqual(agent["elapsed_label"], "5 min")


class LoggingTests(FactoryTestCase):
    def test_concurrent_append_is_atomic(self):
        """T-LOG-01: 20 processes append 500 valid lines with distinct ids."""
        self.require_module("factorylib")
        build = self.tmp / "concurrent"
        build.mkdir()
        (build / "trace.jsonl").write_text("")
        code = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import factorylib\n"
            "for _ in range(25):\n"
            " factorylib.append(sys.argv[2], {'kind':'command','actor':'orchestrator','status':'done'})\n"
        )
        processes = [subprocess.Popen(
            [PYTHON, "-c", code, str(SCRIPTS_DIR), str(build)], env=self.env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ) for _ in range(20)]
        try:
            deadline = time.monotonic() + 0.95
            for process in processes:
                remaining = max(0.01, deadline - time.monotonic())
                stdout, stderr = process.communicate(timeout=remaining)
                self.assertEqual(process.returncode, 0, stdout + stderr)
        except subprocess.TimeoutExpired:
            self.fail("concurrent append exceeded the sub-1-second deadline")
        finally:
            for child in processes:
                if child.poll() is None:
                    child.kill()
                child.communicate(timeout=0.4)
        lines = read_jsonl(build / "trace.jsonl")
        self.assertEqual(len(lines), 500)
        self.assertEqual(len({line["span_id"] for line in lines}), 500)

    def test_secret_redaction_in_memory_and_log(self):
        """T-LOG-02: every secret pattern is redacted, clean text stays exact, and logging warns."""
        lib = self.require_module("factorylib")
        values = [
            "sk-" + "a" * 20, "ghp_" + "b" * 30, "github_pat_" + "c" * 30,
            "npm_" + "d" * 30, "xoxb-" + "e" * 12, "AKIA" + "F" * 16,
            "-----" + "BEGIN PRIVATE" + " KEY-----", "tok" + "en=" + "g" * 12,
        ]
        dirty = " ".join(values)
        cleaned = lib.redact(dirty)
        for value in values:
            self.assertNotIn(value, cleaned)
        self.assertGreaterEqual(cleaned.count("[REDACTED]"), len(values))
        self.assertEqual(lib.redact("ordinary synthetic text"), "ordinary synthetic text")

        build = self.factory_home / "runs" / "demo" / "redact"
        build.mkdir(parents=True)
        (build / "trace.jsonl").write_text("")
        self.select("demo", "redact")
        secret = "tok" + "en=" + "z" * 12
        result = self.run_factory("log", "event", "--kind", "command", "--actor",
                                  "orchestrator", "--notes", secret)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, (build / "trace.jsonl").read_text())
        self.assertIn("redacted 1 secret-looking value", result.stderr)


class BoardTests(FactoryTestCase):
    def test_fixture_a_board_and_plain_labels(self):
        """T-ST-01: board A has the documented state, complete shape, and no process jargon."""
        lib = self.require_module("factorylib")
        board = lib.board(FIXTURES / "alpha", "2026-01-10T12:12:00Z")
        self.assertEqual(board["build"]["state"], "waiting")
        self.assertEqual(board["build"]["state_label"], "Waiting on you")
        self.assertEqual(len(board["waiting_on_you"]), 1)
        self.assertEqual(board["waiting_on_you"][0]["gate"], "GATE B")
        self.assertEqual(board["waiting_on_you"][0]["mins"], 10)
        self.assertEqual(board["agents_total"], 13)
        self.assertFalse(any(agent["state"] == "running" for agent in board["agents"]))
        pieces = {piece["piece"]: piece for piece in board["pieces"]}
        self.assertEqual(pieces["N1"]["loops"], 4)
        self.assertEqual(pieces["N1"]["last_verdict"], "approved")
        self.assertEqual(pieces["N2"]["loops"], 1)
        for key in ("build", "waiting_on_you", "agents", "agents_total", "pieces",
                    "recent", "warnings", "generated"):
            self.assertIn(key, board)
        forbidden = ("span", "iteration", "agent_call", "rubric", "node")
        for text in board_strings(board):
            lowered = text.lower()
            self.assertFalse(any(word in lowered for word in forbidden), text)
            self.assertNotRegex(text, r"\bs\d{3,}\b")

    def test_running_quiet_log_errors_and_stale_agent(self):
        """T-ST-02: board B shows live output, quiet age, failed logs, then unfinished state."""
        lib = self.require_module("factorylib")
        build = self.install_fixture("beta")
        output = build / "messages" / "a1.out.md"
        os.utime(output, (1768039370, 1768039370))  # 2026-01-10 10:02:50 UTC
        first = lib.board(build, "2026-01-10T10:03:00Z")
        agent = first["agents"][0]
        self.assertEqual((first["build"]["state"], agent["state_label"]), ("running", "Working"))
        self.assertEqual(agent["role_label"], "Builder")
        self.assertEqual(agent["piece_label"], "Greeting flag")
        self.assertEqual(agent["loop"], 2)
        self.assertEqual(agent["elapsed_s"], 180)
        self.assertEqual(agent["elapsed_label"], "3 min")
        self.assertEqual(agent["last"], "wrote hello.py")
        self.assertFalse(agent["quiet"])

        quiet = lib.board(build, "2026-01-10T10:15:00Z")
        self.assertTrue(quiet["agents"][0]["quiet"])
        self.assertEqual(quiet["agents"][0]["quiet_label"], "Quiet for 12 min")
        write_jsonl(build / "log-errors.jsonl", [{"reason": "x"}, {"reason": "x"}])
        warned = lib.board(build, "2026-01-10T10:15:00Z")
        self.assertTrue(any("2 log entries failed" in warning for warning in warned["warnings"]))

        stale = lib.board(build, "2026-01-10T10:45:00Z")
        self.assertEqual(stale["agents"][0]["state"], "unfinished")
        self.assertEqual(stale["agents"][0]["state_label"], "Unfinished in log")
        self.assertNotEqual(stale["build"]["state"], "running")


class ConfigAndNotifyTests(FactoryTestCase):
    def test_settings_merge_is_leafwise_and_tracks_sources(self):
        """T-CFG-02: project wins leafwise, lists replace, machine project keys warn, defaults remain."""
        lib = self.require_module("factorylib")
        project = {
            "project": "toy", "roles": {"maker": {"model": "project-model"}},
            "timers": {"wake_s": 7}, "notify": {"channels": ["desktop"]},
        }
        machine = {
            "roles": {"maker": {"model": "machine-model", "effort": "high"}},
            "timers": {"wake_s": 9}, "notify": {"channels": ["desktop", "command"],
            "command": "true"}, "tests": {"ignored": {"cmd": "false", "timeout_s": 1}},
        }
        write_json(self.project / "factory.json", project)
        self.factory_home.mkdir(exist_ok=True)
        write_json(self.factory_home / "config.json", machine)
        with mock.patch.dict(os.environ, self.env, clear=True):
            cfg, sources = lib.load_config(self.project)
        self.assertEqual(cfg["timers"]["wake_s"], 7)
        self.assertEqual(cfg["timers"]["quiet_s"], 600)
        self.assertEqual(cfg["roles"]["maker"]["model"], "project-model")
        self.assertEqual(cfg["roles"]["maker"]["effort"], "high")
        self.assertEqual(cfg["notify"]["channels"], ["desktop"])
        self.assertNotIn("ignored", cfg.get("tests", {}))
        self.assertEqual({key: sources[key] for key in (
            "timers.wake_s", "roles.maker.model", "roles.maker.effort",
            "notify.channels", "timers.quiet_s",
        )}, {
            "timers.wake_s": "project", "roles.maker.model": "project",
            "roles.maker.effort": "machine", "notify.channels": "project",
            "timers.quiet_s": "default",
        })

    def test_runner_selection_uses_numeric_version_then_explicit_then_env(self):
        """T-CFG-03: runner discovery picks 2.10.0, then bin, then override, then none."""
        lib = self.require_module("factorylib")
        for version in ("2.2.5", "2.9.9", "2.10.0"):
            path = self.tmp / "apps" / version / "opencode"
            path.parent.mkdir(parents=True)
            path.write_text("")
        cfg = {"runners": {"opencode": {"bin_glob": str(self.tmp / "apps" / "*" / "opencode")}}}
        with mock.patch.dict(os.environ, {"PATH": ""}, clear=False):
            self.assertEqual(Path(lib.find_runner(cfg, "opencode")),
                             self.tmp / "apps" / "2.10.0" / "opencode")
            explicit = self.tmp / "explicit"
            explicit.write_text("")
            cfg["runners"]["opencode"]["bin"] = str(explicit)
            self.assertEqual(Path(lib.find_runner(cfg, "opencode")), explicit)
            override = self.tmp / "override"
            override.write_text("")
            with mock.patch.dict(os.environ, {"FACTORY_OPENCODE_BIN": str(override)}):
                self.assertEqual(Path(lib.find_runner(cfg, "opencode")), override)
            self.assertIsNone(lib.find_runner({"runners": {"opencode": {}}}, "opencode"))

    def test_notify_channels_have_limits_and_no_connector_execution(self):
        """T-NOT-01: notify returns channel results, passes env, times out, and defers connector."""
        lib = self.require_module("factorylib")
        capture = self.tmp / "notify-env.json"
        desktop_ok = self.fake_program("osascript-ok", "import sys; sys.exit(0)")
        desktop_bad = self.fake_program("osascript-bad", "import sys; print('no', file=sys.stderr); sys.exit(1)")
        command = self.fake_program(
            "notify-command",
            "import json, os\n"
            "open(%r, 'w').write(json.dumps({k: os.environ[k] for k in "
            "['FACTORY_GATE','FACTORY_QUESTION','FACTORY_RECOMMEND']}))" % str(capture),
        )
        base = {"notify": {"channels": ["desktop"]},
                "timers": {"notify_desktop_s": 0.3, "notify_command_s": 0.3}}
        with mock.patch.dict(os.environ, {"FACTORY_OSASCRIPT_BIN": str(desktop_ok)}):
            self.assertEqual(lib.notify(base, "GATE A", "Question?", "Yes."), {"desktop": "sent"})
        with mock.patch.dict(os.environ, {"FACTORY_OSASCRIPT_BIN": str(desktop_bad)}):
            self.assertTrue(lib.notify(base, "GATE A", "Question?", "Yes.")["desktop"].startswith("failed:"))
        command_cfg = {"notify": {"channels": ["command"], "command": str(command)},
                       "timers": base["timers"]}
        self.assertEqual(lib.notify(command_cfg, "GATE A", "Question?", "Yes."), {"command": "sent"})
        self.assertEqual(json.loads(capture.read_text()), {
            "FACTORY_GATE": "GATE A", "FACTORY_QUESTION": "Question?", "FACTORY_RECOMMEND": "Yes.",
        })
        test_result = lib.notify(command_cfg, "Preflight", "ignored", "ignored", test=True)
        self.assertEqual(test_result["command"], "sent")
        slow = self.fake_program("slow-notify", "import time; time.sleep(30)")
        slow_cfg = {"notify": {"channels": ["command"], "command": str(slow)},
                    "timers": base["timers"]}
        started = time.monotonic()
        self.assertTrue(lib.notify(slow_cfg, "G", "Q", "R")["command"].startswith("failed"))
        self.assertLess(time.monotonic() - started, 0.95)
        connector = {"notify": {"channels": ["connector"], "connector": {
            "name": "owner-confirmed connector", "account_confirmed": True}},
            "timers": base["timers"]}
        self.assertEqual(lib.notify(connector, "G", "Q", "R"), {"connector": "to send"})


if __name__ == "__main__":
    import unittest
    unittest.main()
