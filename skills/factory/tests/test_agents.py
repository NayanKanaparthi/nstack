"""Contract tests for wrapped programs, steps, waits, gates, checks, and status."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path

from tests.common import (
    DEFAULT_PROJECT_CONFIG, FACTORY_PY, PYTHON, FactoryTestCase, read_jsonl,
    tree_snapshot, write_json, write_jsonl,
)


class AgentCommandCase(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.config = json.loads(json.dumps(DEFAULT_PROJECT_CONFIG))
        self.write_project_config(self.config)
        self.build = self.factory_home / "runs" / "toy" / "work"
        self.build.mkdir(parents=True)
        (self.build / "trace.jsonl").write_text("")
        (self.build / "messages").mkdir()
        (self.build / "expected.jsonl").write_text("")
        self.select("toy", "work")
        self.prompt = self.project / "prompt.md"
        self.prompt.write_text("synthetic prompt\n")

    def trace(self):
        return read_jsonl(self.build / "trace.jsonl")


class RunTests(AgentCommandCase):
    def test_run_streams_saves_and_seeds_expected(self):
        """T-RUN-01: run seeds expected first, saves input/output, streams, supports arg mode and silence."""
        fake = self.fake_program(
            "streamer",
            "import pathlib, sys, time\n"
            "expected = pathlib.Path(sys.argv[1]).read_text()\n"
            "print('expected-first=' + str('tests.writer.1' in expected), flush=True)\n"
            "for line in sys.stdin:\n print('input=' + line.strip(), flush=True)\n"
            "print('last line', flush=True)",
        )
        result = self.run_factory(
            "run", "--actor", "test-writer", "--call", "tests.writer.1", "--model", "gpt-x",
            "--runner", "codex", "--input", str(self.prompt), "--", str(fake),
            str(self.build / "expected.jsonl"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("expected-first=True", result.stdout)
        expected = read_jsonl(self.build / "expected.jsonl")
        self.assertEqual([row["call"] for row in expected], ["tests.writer.1"])
        spans = self.trace()
        start, end = spans[-2:]
        self.assertEqual((start["status"], end["status"], end["exit_code"]), ("running", "done", 0))
        self.assertEqual((self.build / start["input_ref"]).read_text(), self.prompt.read_text())
        output = self.build / end["output_ref"]
        self.assertIn("last line", output.read_text())
        self.assertEqual(end["output_chars"], len(output.read_text()))
        self.assertEqual(start["cmd"], "%s %s" % (fake, self.build / "expected.jsonl"))

        arg_fake = self.fake_program("arg-reader", "import sys; print(sys.argv[-1])")
        arg = self.run_factory("run", "--actor", "test-writer", "--call", "tests.writer.1",
                               "--input", str(self.prompt), "--input-as-arg", "--", str(arg_fake))
        self.assertEqual(arg.returncode, 0)
        self.assertIn("synthetic prompt", arg.stdout)
        self.assertEqual(len(read_jsonl(self.build / "expected.jsonl")), 1)

        silent = self.fake_program("silent", "pass")
        quiet = self.run_factory("run", "--actor", "x", "--call", "silent.1",
                                 "--input", str(self.prompt), "--", str(silent))
        self.assertEqual(quiet.returncode, 0)
        close = self.trace()[-1]
        self.assertEqual(close["output_chars"], 0)
        self.assertIs(close["warn"], True)
        self.assertIn("warning", quiet.stderr.lower())

    def test_run_classifies_program_and_environment_failures(self):
        """T-RUN-02: ordinary nonzero output is impl-bug; quota output is env-tooling."""
        broken = self.fake_program("broken", "import sys; print('boom'); sys.exit(3)")
        result = self.run_factory("run", "--actor", "maker", "--call", "broken.1",
                                  "--input", str(self.prompt), "--", str(broken))
        self.assertEqual(result.returncode, 3)
        self.assertEqual((self.trace()[-1]["status"], self.trace()[-1]["failure_class"]),
                         ("failed", "impl-bug"))
        quota = self.fake_program(
            "quota", "import sys; print('You have hit your usage limit'); sys.exit(1)")
        result = self.run_factory("run", "--actor", "maker", "--call", "quota.1",
                                  "--input", str(self.prompt), "--", str(quota))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.trace()[-1]["failure_class"], "env-tooling")

    def test_run_timeout_kills_process_group(self):
        """T-RUN-03: explicit and configured 0.3-second limits close model-stall and kill children."""
        child_pid = self.tmp / "child.pid"
        sleeper = self.fake_program(
            "sleeper",
            "import subprocess, sys, time\n"
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
            "open(%r,'w').write(str(p.pid))\n"
            "time.sleep(30)" % str(child_pid),
        )
        started = time.monotonic()
        result = self.run_factory("run", "--actor", "maker", "--call", "slow.1",
                                  "--input", str(self.prompt), "--timeout", "0.3", "--", str(sleeper))
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.monotonic() - started, 0.95)
        close = self.trace()[-1]
        self.assertEqual((close["status"], close["failure_class"]), ("failed", "model-stall"))
        self.assertEqual(close["notes"], "timed out after 0.3s")
        if child_pid.exists():
            with self.assertRaises(ProcessLookupError):
                os.kill(int(child_pid.read_text()), 0)
        default = self.run_factory("run", "--actor", "maker", "--call", "slow.2",
                                   "--input", str(self.prompt), "--", str(sleeper))
        self.assertEqual(default.returncode, 124)

    def test_run_rejects_uncaptured_agent_but_supports_commands_and_missing_program(self):
        """T-RUN-04: agent capture is mandatory; command runs; missing program closes 127; empty argv is 2."""
        marker = self.tmp / "started"
        fake = self.fake_program("marker", "open(%r,'w').write('yes')" % str(marker))
        before = self.build.joinpath("trace.jsonl").read_bytes()
        uncaptured = self.run_factory("run", "--actor", "maker", "--", str(fake), "do the thing")
        self.assertEqual(uncaptured.returncode, 2)
        self.assertIn("--call", uncaptured.stderr)
        self.assertIn("--input", uncaptured.stderr)
        self.assertFalse(marker.exists())
        self.assertEqual(self.build.joinpath("trace.jsonl").read_bytes(), before)
        no_call = self.run_factory("run", "--actor", "maker", "--input", str(self.prompt),
                                   "--", str(fake))
        self.assertEqual(no_call.returncode, 2)
        command = self.run_factory("run", "--kind", "command", "--actor", "orchestrator",
                                   "--", str(fake))
        self.assertEqual(command.returncode, 0)
        missing = self.run_factory("run", "--actor", "a", "--call", "c", "--input",
                                   str(self.prompt), "--", "no-such-program-xyz")
        self.assertEqual(missing.returncode, 127)
        self.assertEqual(self.trace()[-1]["failure_class"], "env-tooling")
        self.assertEqual(self.trace()[-1]["notes"], "program not found: no-such-program-xyz")
        self.assertEqual(self.run_factory("run", "--actor", "a", "--call", "c",
                                          "--input", str(self.prompt), "--").returncode, 2)

    def test_run_sigterm_stops_child_and_span(self):
        """T-RUN-05: SIGTERM to the wrapper stops its child and appends a stopped closing line."""
        self.assertTrue(FACTORY_PY.is_file(), "planned command missing: skills/factory/scripts/factory.py")
        pid_file = self.tmp / "running.pid"
        fake = self.fake_program(
            "long-run", "import os,time; open(%r,'w').write(str(os.getpid())); time.sleep(30)" % str(pid_file))
        process = subprocess.Popen(
            [PYTHON, str(FACTORY_PY), "run", "--actor", "maker", "--call", "signal.1",
             "--input", str(self.prompt), "--", str(fake)], cwd=str(self.project), env=self.env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 0.4
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(pid_file.exists(), "wrapped child did not start")
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=0.5)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 0)
            self.assertEqual(self.trace()[-1]["status"], "stopped")
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=0.4)

    def test_run_data_retention_rule(self):
        """T-RUN-06: retained-data calls need marking plus proof; public/clean pass; local calls need neither."""
        public = self.tmp / "public"; public.mkdir()
        public_prompt = public / "p.md"; public_prompt.write_text("public synthetic text\n")
        fake = self.fake_program("ok", "print('OK')")
        self.config["runners"] = {"opencode": {
            "retains_data": True, "private_safe_prefixes": ["ollama/"]}}
        self.config["public_roots"] = [str(public)]
        write_json(self.project / "factory.json", self.config)
        common = ("run", "--actor", "reviewer", "--call", "free.1", "--runner", "opencode",
                  "--model", "opencode/some-free", "--input", str(self.prompt), "--", str(fake))
        before = self.build.joinpath("trace.jsonl").read_bytes()
        self.assertEqual(self.run_factory(*common).returncode, 2)
        self.assertEqual(self.build.joinpath("trace.jsonl").read_bytes(), before)
        private_path = "/" + "home" + "/example/private"
        self.prompt.write_text("home path " + private_path + "\n")
        private = list(common); private.insert(private.index("--"), "--non-private")
        result = self.run_factory(*private)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(private_path, result.stderr)
        self.prompt.write_text("clean synthetic prompt\n")
        in_public = list(private); in_public[in_public.index("--"):in_public.index("--")] = ["--cwd", str(public)]
        clean = self.run_factory(*in_public)  # a retaining runner must also run in a public folder
        self.assertEqual(clean.returncode, 0)
        self.assertEqual(self.trace()[-2]["data_proof"], "scan-clean")
        public_args = list(in_public); public_args[public_args.index(str(self.prompt))] = str(public_prompt)
        self.assertEqual(self.run_factory(*public_args).returncode, 0)
        self.assertEqual(self.trace()[-2]["data_proof"], "public-root")
        local = self.run_factory("run", "--actor", "reviewer", "--call", "local.1",
                                 "--runner", "opencode", "--model", "ollama/qwen3:4b",
                                 "--input", str(self.prompt), "--", str(fake))
        self.assertEqual(local.returncode, 0)
        direct = self.run_factory("run", "--actor", "reviewer", "--call", "local.2",
                                  "--runner", "ollama", "--model", "qwen3:4b",
                                  "--input", str(self.prompt), "--", str(fake))
        self.assertEqual(direct.returncode, 0)
        self.assertNotIn("data_class", self.trace()[-2])


    def test_run_data_rule_checks_working_folder(self):
        """N2 blocker 1: a data-retaining runner's working folder must be public too."""
        public = self.tmp / "public"; public.mkdir()
        public_prompt = public / "p.md"; public_prompt.write_text("public synthetic text\n")
        fake = self.fake_program("ok", "print('OK')")
        self.config["runners"] = {"opencode": {"retains_data": True, "private_safe_prefixes": ["ollama/"]}}
        self.config["public_roots"] = [str(public)]
        write_json(self.project / "factory.json", self.config)
        args = ("run", "--actor", "reviewer", "--call", "cwd.1", "--runner", "opencode",
                "--model", "opencode/some-free", "--non-private", "--input", str(public_prompt))
        before = self.build.joinpath("trace.jsonl").read_bytes()
        omitted = self.run_factory(*args, "--", str(fake), cwd=self.project)
        self.assertEqual(omitted.returncode, 2)
        explicit = self.run_factory(*args, "--cwd", str(self.project), "--", str(fake), cwd=public)
        self.assertEqual(explicit.returncode, 2)
        self.assertEqual(self.build.joinpath("trace.jsonl").read_bytes(), before)
        allowed = self.run_factory(*args, "--cwd", str(public), "--", str(fake), cwd=self.project)
        self.assertEqual(allowed.returncode, 0)
        self.assertEqual(self.trace()[-2]["data_proof"], "public-root")


class StepTests(AgentCommandCase):
    def test_step_named_commands_and_errors(self):
        """T-STEP-01: configured steps pass through exit codes and unknown/outside-project errors are plain."""
        self.config["tests"] = {"fast": {"cmd": "true", "timeout_s": 1}}
        write_json(self.project / "factory.json", self.config)
        passed = self.run_factory("step", "tests.fast")
        self.assertEqual(passed.returncode, 0)
        span = self.trace()[-1]
        self.assertEqual((span["kind"], span["step"]), ("command", "tests.fast"))
        self.config["tests"]["fast"]["cmd"] = "false"
        write_json(self.project / "factory.json", self.config)
        self.assertEqual(self.run_factory("step", "tests.fast").returncode, 1)
        unknown = self.run_factory("step", "nosuch.thing")
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("tests.fast", unknown.stderr)
        self.assertEqual(self.run_factory("step", "evals.M9").returncode, 2)
        elsewhere = self.tmp / "elsewhere"; elsewhere.mkdir()
        self.assertEqual(self.run_factory("step", "tests.fast", cwd=elsewhere).returncode, 3)

    def test_step_timeout_is_bounded(self):
        """T-STEP-02: a configured 0.3-second step limit exits 124 and closes failed under one second."""
        self.config["tests"] = {"e2e": {"cmd": "%s -c 'import time; time.sleep(30)'" % PYTHON,
                                         "timeout_s": 0.3}}
        write_json(self.project / "factory.json", self.config)
        started = time.monotonic()
        result = self.run_factory("step", "tests.e2e")
        self.assertEqual(result.returncode, 124)
        self.assertLess(time.monotonic() - started, 0.95)
        self.assertEqual(self.trace()[-1]["status"], "failed")

    def test_step_eval_target_and_missing_number(self):
        """T-STEP-03: eval stores numeric target result, fails a miss, and loudly rejects no number."""
        metric = {"id": "M1", "name": "score", "cmd": "printf '0.91\\n'", "role": "floor",
                  "target": ">=0.85", "timeout_s": 1}
        self.config["evals"] = {"metrics": [metric]}
        write_json(self.project / "factory.json", self.config)
        self.assertEqual(self.run_factory("step", "evals.M1").returncode, 0)
        self.assertEqual((self.trace()[-1]["value"], self.trace()[-1]["target_met"]), (0.91, True))
        metric["cmd"] = "printf '0.70\\n'"; write_json(self.project / "factory.json", self.config)
        self.assertEqual(self.run_factory("step", "evals.M1").returncode, 1)
        self.assertEqual((self.trace()[-1]["status"], self.trace()[-1]["target_met"]),
                         ("failed", False))
        metric["cmd"] = "printf 'done\\n'"; write_json(self.project / "factory.json", self.config)
        self.assertEqual(self.run_factory("step", "evals.M1").returncode, 4)
        self.assertEqual(self.trace()[-1]["failure_class"], "env-tooling")


class WaitGateCheckStatusTests(AgentCommandCase):
    def _open_agent(self, span_id="s001", started="2026-01-10T12:00:00Z", call="N1.maker.1"):
        line = {"v": 1, "span_id": span_id, "ts": started, "kind": "agent_call",
                "actor": "maker", "node": "N1", "node_label": "Greeting flag", "iteration": 1,
                "call": call, "status": "running", "start": started}
        with self.build.joinpath("trace.jsonl").open("a") as stream:
            stream.write(json.dumps(line) + "\n")

    def test_wait_returns_when_log_changes(self):
        """T-WAIT-01: wait sees a running span close after 0.2 seconds and exits before 0.7."""
        self._open_agent()
        helper = subprocess.Popen(
            [PYTHON, "-c",
             "import json,time; time.sleep(.2); open(%r,'a').write(json.dumps(%r)+'\\n')" %
             (str(self.build / "trace.jsonl"), {"span_id": "s001", "ts": "2026-01-10T12:00:01Z",
                                                 "status": "done", "end": "2026-01-10T12:00:01Z",
                                                 "duration_s": 1})],
            env=self.env, stdin=subprocess.DEVNULL)
        try:
            started = time.monotonic()
            result = self.run_factory("wait", "--timeout", "0.9")
            helper.wait(timeout=0.4)
            self.assertEqual(result.returncode, 0)
            self.assertLess(time.monotonic() - started, 0.7)
            self.assertIn("finished", result.stdout.lower())
        finally:
            if helper.poll() is None:
                helper.kill()
            helper.wait(timeout=0.4)

    def test_wait_timeout_nothing_running_and_no_build(self):
        """T-WAIT-02: wait times out with live details, exits immediately if idle, and is 3 without build."""
        self._open_agent()
        result = self.run_factory("wait", "--timeout", "0.3")
        self.assertEqual(result.returncode, 124)
        self.assertIn("nothing changed", result.stdout)
        self.assertIn("Builder", result.stdout)
        self.assertIn("Greeting flag", result.stdout)
        self.build.joinpath("trace.jsonl").write_text("")
        started = time.monotonic()
        idle = self.run_factory("wait", "--timeout", "0.3")
        self.assertEqual(idle.returncode, 0)
        self.assertLess(time.monotonic() - started, 0.1)
        self.assertIn("nothing is running", idle.stdout)
        self.factory_home.joinpath("current.jsonl").write_text("")
        self.assertEqual(self.run_factory("wait", env={"FACTORY_BUILD": ""}).returncode, 3)

    def test_gate_open_notifies_and_close_measures(self):
        """T-GATE-01: gate logs a human wait, sends desktop question, and closes with measured answer."""
        received = self.tmp / "desktop-args.json"
        fake = self.fake_program("osascript", "import json,sys; open(%r,'w').write(json.dumps(sys.argv))" % str(received))
        self.config["notify"] = {"channels": ["desktop"]}
        write_json(self.project / "factory.json", self.config)
        result = self.run_factory(
            "gate", "open", "--name", "GATE A", "--question",
            "Should the new flag be on by default?", "--recommend", "No. Keep today's behavior.",
            env={"FACTORY_OSASCRIPT_BIN": str(fake)})
        self.assertEqual(result.returncode, 0, result.stderr)
        span_id = result.stdout.strip()
        start = self.trace()[-1]
        self.assertEqual((start["kind"], start["waiting_on"], start["status"]),
                         ("wait", "human", "running"))
        self.assertEqual(start["notified"]["desktop"], "sent")
        self.assertIn("Should the new flag", received.read_text())
        self.env["FACTORY_NOW"] = "2026-01-10T12:45:00Z"
        closed = self.run_factory("gate", "close", span_id, "--answer", "yes to all")
        self.assertEqual(closed.returncode, 0)
        self.assertEqual((self.trace()[-1]["answer"], self.trace()[-1]["duration_s"]),
                         ("yes to all", 1980))

    def test_gate_rejects_ids_empty_missing_long_and_id_recommendation(self):
        """T-GATE-02: gate plain-question validation rejects ids, empty/missing text, length, and id advice."""
        cases = [
            ("--question", "Approve AC7 and T-LOG-03?", "--recommend", "Yes."),
            ("--question", "", "--recommend", "Yes."),
            ("--question", "A plain question?",),
            ("--question", "x" * 301, "--recommend", "Yes."),
            ("--question", "A plain question?", "--recommend", "see R2"),
        ]
        before = self.build.joinpath("trace.jsonl").read_bytes()
        for args in cases:
            with self.subTest(args=args):
                result = self.run_factory("gate", "open", "--name", "GATE A", *args)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(any(word in result.stderr.lower() for word in
                                    ("question", "recommend", "id", "long", "empty")))
                self.assertEqual(self.build.joinpath("trace.jsonl").read_bytes(), before)

    def test_gate_notification_failures_connector_and_kit_privacy(self):
        """T-GATE-03: failed/slow/no notifications preserve gates; connector is manual; kit has no account code."""
        failing = self.fake_program("notify-fail", "import sys; sys.exit(1)")
        self.config["notify"] = {"channels": ["command"], "command": str(failing)}
        write_json(self.factory_home / "config.json", self.config)
        write_json(self.project / "factory.json", {k: v for k, v in self.config.items() if k != "notify"})
        result = self.run_factory("gate", "open", "--name", "GATE A", "--question",
                                  "Approve the plain plan?", "--recommend", "Yes.")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.trace()[-1]["notified"]["command"].startswith("failed"))
        slow = self.fake_program("slow-desktop", "import time; time.sleep(30)")
        self.config["notify"] = {"channels": ["desktop"]}
        write_json(self.project / "factory.json", self.config)
        started = time.monotonic()
        slow_result = self.run_factory("gate", "open", "--name", "GATE B", "--question",
                                       "Approve release?", "--recommend", "Yes.",
                                       env={"FACTORY_OSASCRIPT_BIN": str(slow)})
        self.assertEqual(slow_result.returncode, 0)
        self.assertLess(time.monotonic() - started, 0.95)
        self.config["notify"] = {"channels": []}; write_json(self.project / "factory.json", self.config)
        none = self.run_factory("gate", "open", "--name", "GATE C", "--question",
                                "Continue?", "--recommend", "Yes.")
        self.assertEqual(none.returncode, 0)
        self.assertEqual(self.trace()[-1]["notified"], {})
        self.config["notify"] = {"channels": ["connector"], "connector": {
            "name": "owner-confirmed", "account_confirmed": True}}
        write_json(self.factory_home / "config.json", self.config)
        write_json(self.project / "factory.json", {k: v for k, v in self.config.items() if k != "notify"})
        connector = self.run_factory("gate", "open", "--name", "GATE D", "--question",
                                     "Continue now?", "--recommend", "Yes.")
        self.assertEqual(connector.returncode, 0)
        self.assertIn("Also send this through: owner-confirmed", connector.stdout)
        gate_id = connector.stdout.splitlines()[0]
        self.assertEqual(self.run_factory("gate", "sent", gate_id, "--channel", "connector").returncode, 0)
        self.assertEqual(self.trace()[-1]["notified"]["connector"], "sent")
        kit_text = "\n".join(path.read_text(errors="replace") for path in FACTORY_PY.parents[1].rglob("*")
                              if path.is_file() and not {"tests", "__pycache__"} & set(path.parts))
        self.assertNotRegex(kit_text.lower(), r"slack|calendar|smtp|gmail|[\w.+-]+@[\w.-]+")

    def test_check_clean_and_stale_unfinished(self):
        """T-CHK-01: check prints exact clean counts, then names and counts a 40-minute unfinished call."""
        expected = [
            {"call": "N1.maker.1", "node": "N1", "role": "maker", "try": 1},
            {"call": "N1.checker.1", "node": "N1", "role": "checker", "try": 1},
            {"call": "N2.maker.1", "node": "N2", "role": "maker", "try": 1},
        ]
        write_jsonl(self.build / "expected.jsonl", expected)
        lines = []
        for index, item in enumerate(expected, 1):
            lines += [{"span_id": "s%03d" % index, "ts": "2026-01-10T11:00:00Z",
                       "kind": "agent_call", "actor": item["role"], "node": item["node"],
                       "node_label": "Greeting flag", "call": item["call"], "status": "done",
                       "start": "2026-01-10T10:50:00Z", "end": "2026-01-10T11:00:00Z",
                       "duration_s": 600}]
        write_jsonl(self.build / "trace.jsonl", lines)
        clean = self.run_factory("check")
        self.assertEqual(clean.returncode, 0)
        self.assertIn("Expected 3, logged 3, matched 3, missing 0, unplanned 0, duplicate 0, unfinished 0.", clean.stdout)
        lines[-1]["status"] = "running"; lines[-1].pop("end"); lines[-1].pop("duration_s")
        lines[-1]["ts"] = "2026-01-10T11:32:00Z"; lines[-1]["start"] = "2026-01-10T11:32:00Z"
        write_jsonl(self.build / "trace.jsonl", lines)
        stale = self.run_factory("check")
        self.assertEqual(stale.returncode, 1)
        self.assertIn("Started and never finished: Builder on Greeting flag, 40 min ago", stale.stdout)
        self.assertIn("unfinished 1", stale.stdout)

    def test_check_missing_duplicate_unplanned_and_late_fixes(self):
        """T-CHK-02: check distinguishes tries, duplicate/unplanned calls, and leaves duplicate after late fixes."""
        expected = [
            {"call": "N1.%s.%d" % (role, attempt), "node": "N1", "role": role, "try": attempt}
            for attempt in (1, 2) for role in ("maker", "checker")]
        write_jsonl(self.build / "expected.jsonl", expected)
        calls = ["N1.maker.1", "N1.checker.1", "N1.maker.2", "N1.maker.2", "extra.1"]
        lines = [{"span_id": "s%03d" % index, "ts": "2026-01-10T12:00:00Z",
                  "kind": "agent_call", "actor": "maker", "node": "N1",
                  "node_label": "Greeting flag", "call": call, "status": "done",
                  "start": "2026-01-10T11:59:00Z", "end": "2026-01-10T12:00:00Z",
                  "duration_s": 60} for index, call in enumerate(calls, 1)]
        write_jsonl(self.build / "trace.jsonl", lines)
        result = self.run_factory("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Expected but not logged: Checker on Greeting flag, try 2", result.stdout)
        self.assertEqual(result.stdout.count("Duplicate"), 1)
        self.assertIn("Logged but not planned", result.stdout)
        self.assertIn("Expected 4, logged 5, matched 3, missing 1, unplanned 1, duplicate 1", result.stdout)
        self.assertEqual(self.run_factory("check", "--add", "extra.1", "--node", "N1",
                                          "--role", "maker", "--try", "1").returncode, 0)
        late = self.run_factory("log", "event", "--kind", "agent_call", "--actor", "checker",
                                "--call", "N1.checker.2", "--node", "N1", "--input", str(self.prompt))
        self.assertEqual(late.returncode, 0)
        fixed = self.run_factory("check")
        self.assertEqual(fixed.returncode, 1)
        self.assertNotIn("Expected but not logged", fixed.stdout)
        self.assertNotIn("Logged but not planned", fixed.stdout)
        self.assertIn("duplicate 1", fixed.stdout)

    def test_check_expectation_errors_and_phase_orphan_warning(self):
        """T-CHK-03: missing/empty/bad expectations fail loudly; add duplicate is 1; phase warns but succeeds."""
        expected_path = self.build / "expected.jsonl"
        expected_path.unlink()
        self.assertEqual(self.run_factory("check").returncode, 4)
        expected_path.write_text("")
        self.assertEqual(self.run_factory("check").returncode, 4)
        expected_path.write_text("[]\n")
        bad = self.run_factory("check")
        self.assertEqual(bad.returncode, 2)
        self.assertIn("line 1", bad.stderr)
        write_jsonl(expected_path, [{"call": "c", "node": "N1", "role": "maker", "try": 1}])
        before = expected_path.read_bytes()
        self.assertEqual(self.run_factory("check", "--add", "c", "--node", "N1",
                                          "--role", "maker").returncode, 1)
        self.assertEqual(expected_path.read_bytes(), before)
        expected_path.unlink()
        self.assertEqual(self.run_factory("check", "--orphans-only").returncode, 0)
        self._open_agent(started="2026-01-10T11:32:00Z")
        phase = self.run_factory("phase", "e2e")
        self.assertEqual(phase.returncode, 0)
        self.assertIn("WARNING", phase.stdout)
        self.assertIn("Builder", phase.stdout)
        self.assertIs(next(line for line in self.trace() if line.get("kind") == "phase" and
                           line.get("status") == "done")["warn"], True)

    def test_status_text_json_all_empty_and_missing(self):
        """T-ST-03: status text/JSON/all share board data; empty is friendly; no selection is 3."""
        alpha = self.install_fixture("alpha", build="alpha")
        self.select("demo", "alpha")
        text = self.run_factory("status")
        self.assertEqual(text.returncode, 0)
        self.assertIn("WAITING ON YOU (1)", text.stdout)
        self.assertIn("Release this build?", text.stdout)
        self.assertIn("AGENTS", text.stdout)
        as_json = self.run_factory("status", "--json")
        self.assertEqual(as_json.returncode, 0)
        factorylib = self.require_module("factorylib")
        self.assertEqual(json.loads(as_json.stdout), factorylib.board(alpha, self.env["FACTORY_NOW"]))
        self.install_fixture("beta", build="beta")
        listing = self.run_factory("status", "--all")
        self.assertEqual(listing.returncode, 0)
        self.assertLess(listing.stdout.index("demo/beta"), listing.stdout.index("demo/alpha"))
        empty = self.factory_home / "runs" / "demo" / "empty"; empty.mkdir(parents=True)
        (empty / "trace.jsonl").write_text("")
        empty_result = self.run_factory("status", "--build", "demo/empty")
        self.assertEqual(empty_result.returncode, 0)
        self.assertIn("No activity logged yet", empty_result.stdout)
        self.factory_home.joinpath("current.jsonl").write_text("")
        self.assertEqual(self.run_factory("status", env={"FACTORY_BUILD": ""}).returncode, 3)


if __name__ == "__main__":
    import unittest
    unittest.main()
