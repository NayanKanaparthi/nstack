"""Contract tests for the factory dispatcher, settings, builds, and log commands."""

import copy
import json
import shutil
from pathlib import Path

from tests.common import (
    COMMANDS, DEFAULT_PROJECT_CONFIG, FACTORY_PY, FIXTURES, KIT_DIR,
    FactoryTestCase, read_jsonl, tree_snapshot, write_json, write_jsonl,
)


class SkillAndDispatchTests(FactoryTestCase):
    def test_skill_contract(self):
        """T-KIT-01: SKILL frontmatter, size, commands, hard rules, and standalone use are stated."""
        path = KIT_DIR / "SKILL.md"
        self.assertTrue(path.is_file(), "planned file missing: skills/factory/SKILL.md")
        text = path.read_text()
        lines = text.splitlines()
        self.assertLess(len(lines), 250)
        self.assertTrue(lines and lines[0] == "---")
        end = lines.index("---", 1)
        frontmatter = lines[1:end]
        self.assertIn("name: factory", frontmatter)
        description = next((line.split(":", 1)[1].strip() for line in frontmatter
                            if line.startswith("description:")), None)
        self.assertIsNotNone(description)
        self.assertLess(len(description), 1024)
        for command in COMMANDS:
            self.assertRegex(text, r"\bfactory\s+%s\b" % command.replace("-", r"\-"))
        for phrase in (
                "factory wait", "time limit", "factory gate open", "configured channels",
                "--call", "--input", "factory check", "non-private", "factory step",
                "different vendor", "fails loudly", "before GATE B"):
            self.assertIn(phrase.lower(), text.lower())
        self.assertIn("without the Conductor app", text)
        self.assertNotRegex(text.lower(), r"edit.{0,30}(settings|settings\.json)")

    def test_dispatch_help_unknown_and_missing_module(self):
        """T-KIT-04: help lists 13 commands, unknown is 2, and a missing module is a clean 2."""
        help_result = self.run_factory("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for command in COMMANDS:
            self.assertIn(command, help_result.stdout)
        unknown = self.run_factory("nosuch")
        self.assertEqual(unknown.returncode, 2)
        self.assertNotIn("Traceback", unknown.stderr)

        scripts = self.tmp / "scripts"
        scripts.mkdir()
        self.assertTrue(FACTORY_PY.is_file(), "planned file missing: skills/factory/scripts/factory.py")
        for source in FACTORY_PY.parent.glob("*.py"):
            if source.name != "preflight.py":
                shutil.copy2(str(source), str(scripts / source.name))
        # Exercise the copied entry point directly, not the repository entry point.
        import subprocess
        from tests.common import PYTHON
        result = subprocess.run([PYTHON, str(scripts / "factory.py"), "preflight"],
                                cwd=str(self.project), env=self.env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=0.95)
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not installed", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class InitAndConfigTests(FactoryTestCase):
    def test_init_is_valid_idempotent_and_never_touches_claude(self):
        """T-INIT-01: init writes the safe project template, preflights, and preserves Claude files."""
        example = KIT_DIR / "factory.example.json"
        machine_example = KIT_DIR / "machine.example.json"
        self.assertTrue(example.is_file(), "planned file missing: skills/factory/factory.example.json")
        self.assertTrue(machine_example.is_file(), "planned file missing: skills/factory/machine.example.json")
        toy = self.tmp / "toy"
        toy.mkdir()
        marker = toy / ".claude" / "settings.local.json"
        marker.parent.mkdir()
        marker.write_text('{"keep": true}\n')
        first = self.run_factory("init", cwd=toy)
        self.assertEqual(first.returncode, 0, first.stderr)
        config = json.loads((toy / "factory.json").read_text())
        expected = json.loads(example.read_text())
        expected["project"] = "toy"
        self.assertEqual(config, expected)
        encoded = json.dumps(config)
        for forbidden in ('"command"', '"connector"', '"bin"', '"bin_glob"'):
            self.assertNotIn(forbidden, encoded)
        before = (toy / "factory.json").read_bytes()
        again = self.run_factory("init", cwd=toy)
        self.assertEqual(again.returncode, 0)
        self.assertIn("factory.json ok", again.stdout)
        self.assertEqual((toy / "factory.json").read_bytes(), before)
        self.assertEqual(marker.read_text(), '{"keep": true}\n')

        spaced = self.tmp / "my app"
        spaced.mkdir()
        bad = self.run_factory("init", cwd=spaced)
        self.assertEqual(bad.returncode, 2)
        self.assertIn("my app", bad.stderr)
        self.assertIn("--project", bad.stderr)
        self.assertFalse((spaced / "factory.json").exists())
        good = self.run_factory("init", "--project", "my-app", cwd=spaced)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertEqual(json.loads((spaced / "factory.json").read_text())["project"], "my-app")
        self.assertFalse((toy / ".claude").joinpath("anything-new").exists())

    def test_invalid_settings_name_file_and_key(self):
        """T-CFG-01: every invalid project setting exits 2 and identifies its file and key."""
        base = copy.deepcopy(DEFAULT_PROJECT_CONFIG)
        constitution = self.project / "CONSTITUTION.md"
        constitution.write_text("synthetic\n")
        base["constitution"] = str(constitution)
        cases = []
        cases.append(("not json", "project"))
        missing_project = copy.deepcopy(base); missing_project.pop("project")
        cases.append((missing_project, "project"))
        slash = copy.deepcopy(base); slash["project"] = "a/b"; cases.append((slash, "project"))
        runner = copy.deepcopy(base); runner["roles"] = {"maker": {"runner": "gemini", "model": "x"}}; cases.append((runner, "runner"))
        channel = copy.deepcopy(base); channel["notify"] = {"channels": ["slack"]}; cases.append((channel, "notify.channels"))
        command = copy.deepcopy(base); command["notify"] = {"channels": ["command"]}; cases.append((command, "notify.command"))
        missing_const = copy.deepcopy(base); missing_const["constitution"] = "missing.md"; cases.append((missing_const, "constitution"))
        vendors = copy.deepcopy(base); vendors["vendors"] = {"required": ["codex"], "optional": ["codex"]}; cases.append((vendors, "vendors"))
        project_command = copy.deepcopy(base); project_command["notify"] = {"channels": [], "command": "true"}; cases.append((project_command, "notify.command"))
        connector = copy.deepcopy(base); connector["notify"] = {"channels": ["connector"], "connector": {"name": "x", "account_confirmed": False}}; cases.append((connector, "account_confirmed"))
        material = copy.deepcopy(base); material["roles"] = {"maker": {"runner": "claude", "model": "x", "material": "public"}}; cases.append((material, "material"))
        binary = copy.deepcopy(base); binary["runners"] = {"opencode": {"bin": "/tmp/x"}}; cases.append((binary, "runners.opencode.bin"))
        timeout_missing = copy.deepcopy(base); timeout_missing["tests"] = {"fast": {"cmd": "true"}}; cases.append((timeout_missing, "timeout_s"))
        timeout_zero = copy.deepcopy(base); timeout_zero["release"] = {"steps": [{"name": "x", "cmd": "true", "timeout_s": 0}]}; cases.append((timeout_zero, "timeout_s"))
        for index, (value, key) in enumerate(cases):
            with self.subTest(key=key):
                folder = self.tmp / ("bad-config-%02d" % index)
                folder.mkdir()
                if value == "not json":
                    (folder / "factory.json").write_text("{")
                else:
                    write_json(folder / "factory.json", value)
                result = self.run_factory("preflight", "--json", cwd=folder)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("factory.json", result.stderr)
                self.assertIn(key.split(".")[-1], result.stderr)


class BuildAndLogTests(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.write_project_config(DEFAULT_PROJECT_CONFIG)

    def _new(self, build="shout"):
        result = self.run_factory("new", build, "--title", "Shout flag", "--stop", "GATE B=17:30")
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.factory_home / "runs" / "toy" / build

    def test_new_seeds_graph_and_handles_graph_errors(self):
        """T-NEW-01: new writes schema-v1 build files and mechanically seeds graph expectations."""
        graph = self.project / "GRAPH.yaml"
        graph.write_text(
            "nodes:\n"
            "  - id: N1\n    owns_files:\n      - one.py\n"
            "  - id: N2\n    owns_files:\n      - two.py\n"
            "  - id: TW\n    owns_files:\n      - tests.py\n"
            "  - id: EMPTY\n    owns_files: []\n")
        result = self.run_factory("new", "shout", "--title", "Shout flag", "--stop",
                                  "GATE B=17:30", "--from-graph", str(graph), "--skip", "TW")
        self.assertEqual(result.returncode, 0, result.stderr)
        build = self.factory_home / "runs" / "toy" / "shout"
        self.assertTrue((build / "messages").is_dir())
        trace = read_jsonl(build / "trace.jsonl")
        self.assertEqual(len(trace), 1)
        self.assertEqual((trace[0]["kind"], trace[0]["status"], trace[0]["v"]),
                         ("feature", "running", 1))
        metadata = json.loads((build / "build.json").read_text())
        self.assertEqual(metadata["title"], "Shout flag")
        self.assertEqual(metadata["stop_times"][0]["label"], "GATE B")
        expected = read_jsonl(build / "expected.jsonl")
        self.assertEqual([item["call"] for item in expected],
                         ["N1.maker.1", "N1.checker.1", "N2.maker.1", "N2.checker.1"])
        self.assertTrue(all(item["added_by"] == "graph" for item in expected))
        pointer = read_jsonl(self.factory_home / "current.jsonl")[-1]
        self.assertEqual(pointer["phase"], "intake")
        self.assertIn(str(build), result.stdout)

        missing = self.run_factory("new", "missing", "--title", "x", "--stop", "G=17:30",
                                   "--from-graph", str(self.project / "missing.yaml"))
        self.assertEqual(missing.returncode, 3)
        empty_graph = self.project / "EMPTY.yaml"; empty_graph.write_text("nodes: []\n")
        empty = self.run_factory("new", "empty", "--title", "x", "--stop", "G=17:30",
                                 "--from-graph", str(empty_graph))
        self.assertEqual(empty.returncode, 4)
        self.assertFalse((self.factory_home / "runs" / "toy" / "empty").exists())

    def test_new_refuses_existing_and_adopts_without_rewriting(self):
        """T-NEW-02: duplicate new and bad adoption fail; valid adoption is append-only and idempotent."""
        build = self._new()
        trace_before = (build / "trace.jsonl").read_bytes()
        duplicate = self.run_factory("new", "shout")
        self.assertEqual(duplicate.returncode, 1)
        self.assertEqual((build / "trace.jsonl").read_bytes(), trace_before)

        adopted = self.factory_home / "runs" / "toy" / "old"
        adopted.mkdir(parents=True)
        (adopted / "trace.jsonl").write_bytes((FIXTURES / "delta" / "trace.jsonl").read_bytes())
        no_title = self.run_factory("new", "old", "--adopt")
        self.assertEqual(no_title.returncode, 2)
        no_stop = self.run_factory("new", "old", "--adopt", "--title", "Old")
        self.assertEqual(no_stop.returncode, 2)
        original = (adopted / "trace.jsonl").read_bytes()
        valid = self.run_factory("new", "old", "--adopt", "--title", "Old build",
                                 "--repo", "/synthetic/repo", "--stop", "A=10:00",
                                 "--stop", "B=11:00", "--stop", "C=12:00")
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertEqual((adopted / "trace.jsonl").read_bytes(), original)
        metadata_before = (adopted / "build.json").read_bytes()
        metadata = json.loads(metadata_before)
        self.assertEqual((metadata["title"], metadata["repo"]), ("Old build", "/synthetic/repo"))
        self.assertEqual(len(metadata["stop_times"]), 3)
        again = self.run_factory("new", "old", "--adopt", "--title", "Different",
                                 "--stop", "D=13:00")
        self.assertEqual(again.returncode, 0)
        self.assertIn("kept", (again.stdout + again.stderr).lower())
        self.assertEqual((adopted / "build.json").read_bytes(), metadata_before)
        self.assertEqual(self.run_factory("new", "bad id").returncode, 2)
        no_project = self.tmp / "no-project"; no_project.mkdir()
        self.assertEqual(self.run_factory("new", "x", cwd=no_project).returncode, 2)

    def test_phase_closes_previous_and_appends_pointer(self):
        """T-NEW-03: phase measures the previous phase and only appends log and current lines."""
        build = self._new()
        self.env["FACTORY_NOW"] = "2026-01-10T10:00:00Z"
        first = self.run_factory("phase", "plan")
        self.assertEqual(first.returncode, 0, first.stderr)
        before_lines = (build / "trace.jsonl").read_text().splitlines()
        pointer_count = len((self.factory_home / "current.jsonl").read_text().splitlines())
        self.env["FACTORY_NOW"] = "2026-01-10T10:10:00Z"
        second = self.run_factory("phase", "build")
        self.assertEqual(second.returncode, 0, second.stderr)
        after_lines = (build / "trace.jsonl").read_text().splitlines()
        self.assertEqual(after_lines[:len(before_lines)], before_lines)
        spans = read_jsonl(build / "trace.jsonl")
        plan_close = next(line for line in spans if line.get("duration_s") == 600)
        self.assertEqual(plan_close["status"], "done")
        self.assertEqual(spans[-1]["status"], "running")
        self.assertEqual(spans[-1]["kind"], "phase")
        pointers = read_jsonl(self.factory_home / "current.jsonl")
        self.assertEqual(len(pointers), pointer_count + 1)
        self.assertEqual(pointers[-1]["phase"], "build")

    def test_log_start_requires_capture_and_copies_prompt(self):
        """T-LOG-03: agent start writes schema v1, continues ids, saves prompt, and requires call/input."""
        build = self.factory_home / "runs" / "toy" / "manual"
        build.mkdir(parents=True)
        lines = [
            {"span_id": "s%03d" % i, "ts": "2026-01-10T09:00:00Z", "kind": "command",
             "status": "done", "actor": "orchestrator"} for i in range(1, 5)
        ]
        write_jsonl(build / "trace.jsonl", lines)
        (build / "messages").mkdir()
        self.select("toy", "manual")
        prompt = self.project / "prompt.md"; prompt.write_text("make the greeting flag\n")
        result = self.run_factory("log", "start", "--kind", "agent_call", "--actor", "maker",
                                  "--call", "N1.maker.1", "--node", "N1", "--label",
                                  "Greeting flag", "--iteration", "1", "--model", "opus-5-5",
                                  "--input", str(prompt))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "s005\n")
        added = read_jsonl(build / "trace.jsonl")[-1]
        for key in ("v", "ts", "project", "feature", "phase", "call", "start"):
            self.assertIn(key, added)
        self.assertEqual(added["status"], "running")
        self.assertEqual((build / "messages" / "s005.in.md").read_text(), prompt.read_text())
        count = len((build / "trace.jsonl").read_text().splitlines())
        no_input = self.run_factory("log", "start", "--kind", "agent_call", "--actor", "maker",
                                    "--call", "x")
        no_call = self.run_factory("log", "start", "--kind", "agent_call", "--actor", "maker",
                                   "--input", str(prompt))
        self.assertEqual((no_input.returncode, no_call.returncode), (2, 2))
        self.assertEqual(len((build / "trace.jsonl").read_text().splitlines()), count)

    def test_log_end_event_and_beat(self):
        """T-LOG-04: end measures and saves output; event backdates; beat updates only open spans."""
        self.env["FACTORY_NOW"] = "2026-01-10T10:00:00Z"
        build = self._new()
        prompt = self.project / "p.md"; prompt.write_text("prompt\n")
        started = self.run_factory("log", "start", "--kind", "agent_call", "--actor", "maker",
                                   "--call", "N1.maker.1", "--input", str(prompt))
        span_id = started.stdout.strip()
        self.env["FACTORY_NOW"] = "2026-01-10T10:06:52Z"
        output = self.project / "reply.md"; output.write_text("finished\n")
        ended = self.run_factory("log", "end", span_id, "--output", str(output))
        self.assertEqual(ended.returncode, 0, ended.stderr)
        close = read_jsonl(build / "trace.jsonl")[-1]
        self.assertEqual(close["status"], "done")
        self.assertEqual(close["duration_s"], 412)
        self.assertEqual(close["output_chars"], len(output.read_text()))
        self.assertEqual((build / close["output_ref"]).read_text(), output.read_text())
        event = self.run_factory("log", "event", "--kind", "command", "--actor",
                                 "orchestrator", "--duration-s", "30")
        self.assertEqual(event.returncode, 0)
        event_line = read_jsonl(build / "trace.jsonl")[-1]
        self.assertEqual(event_line["duration_s"], 30)
        self.assertNotEqual(event_line["start"], event_line["end"])
        open_result = self.run_factory("log", "start", "--kind", "command", "--actor", "orchestrator")
        open_id = open_result.stdout.strip()
        beat = self.run_factory("log", "beat", open_id, "running tests")
        self.assertEqual(beat.returncode, 0)
        self.assertEqual(read_jsonl(build / "trace.jsonl")[-1]["last"], "running tests")
        before = (build / "trace.jsonl").read_bytes()
        closed_beat = self.run_factory("log", "beat", span_id, "late")
        self.assertEqual(closed_beat.returncode, 1)
        self.assertEqual((build / "trace.jsonl").read_bytes(), before)

    def test_checker_end_computes_rubric_deltas(self):
        """T-LOG-05: checker verdicts append computed iteration deltas for tries one and two."""
        build = self._new()
        prompt = self.project / "p.md"; prompt.write_text("check\n")
        for attempt, verdict, passed, failed, why in (
                (1, "rejected", "R1", "R2,R3", ["--why", "R2: crash"]),
                (2, "approved", "R1,R2,R3", "", [])):
            start = self.run_factory("log", "start", "--kind", "agent_call", "--actor", "checker",
                                     "--call", "N1.checker.%d" % attempt, "--node", "N1",
                                     "--iteration", str(attempt), "--input", str(prompt))
            args = ["log", "end", start.stdout.strip(), "--verdict", verdict,
                    "--rubric-pass", passed]
            if failed:
                args += ["--rubric-fail", failed]
            args += why
            self.assertEqual(self.run_factory(*args).returncode, 0)
        iterations = [line for line in read_jsonl(build / "trace.jsonl")
                      if line.get("kind") == "iteration"]
        self.assertEqual(len(iterations), 2)
        self.assertEqual(iterations[0]["rubric_before"], [])
        self.assertEqual(iterations[0]["newly_passing"], ["R1"])
        self.assertEqual(iterations[0]["iteration"], 1)
        self.assertEqual(iterations[1]["rubric_before"], ["R1"])
        self.assertEqual(iterations[1]["newly_passing"], ["R2", "R3"])
        self.assertEqual(iterations[1]["newly_failing"], [])
        self.assertEqual(iterations[1]["iteration"], 2)

    def test_log_invalid_inputs_have_exact_codes_and_no_traceback(self):
        """T-LOG-06: log errors use codes 1-4, write no trace line, and show no traceback."""
        no_build = self.run_factory("log", "end", "s999", cwd=self.project,
                                    env={"FACTORY_BUILD": ""})
        self.assertEqual(no_build.returncode, 3)
        self.assertIn("no build selected", no_build.stderr)
        missing_build = self.run_factory("log", "end", "s999", "--build", "nope/none")
        self.assertEqual(missing_build.returncode, 3)
        build = self._new()
        prompt = self.project / "p.md"; prompt.write_text("x")
        opened = self.run_factory("log", "start", "--kind", "command", "--actor", "orchestrator")
        span_id = opened.stdout.strip()
        self.assertEqual(self.run_factory("log", "end", "s999").returncode, 3)
        self.assertEqual(self.run_factory("log", "end", span_id).returncode, 0)
        cases = [
            (("log", "end", span_id), 1),
            (("log", "event", "--kind", "banana", "--actor", "x"), 2),
            (("log", "event", "--kind", "command", "--actor", "x", "--status", "failed"), 2),
            (("log", "event", "--kind", "command", "--actor", "x", "--failure-class", "oops"), 2),
            (("log", "start", "--kind", "agent_call", "--actor", "x", "--call", "c",
              "--iteration", "two", "--input", str(prompt)), 2),
            (("log", "start", "--kind", "agent_call", "--actor", "x", "--call", "c",
              "--input", "-"), 4),
            (("log", "start", "--kind", "agent_call", "--actor", "x", "--call", "c",
              "--input", str(self.project / "missing.md")), 3),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                before = (build / "trace.jsonl").read_bytes()
                result = self.run_factory(*args, input_text="" if args[-1] == "-" else None)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual((build / "trace.jsonl").read_bytes(), before)

    def test_failed_logging_attempts_are_sanitized_and_durable(self):
        """T-LOG-07: failed log attempts write sanitized build/home error records."""
        build = self._new()
        self.run_factory("log", "end", "s999")
        self.run_factory("log", "start", "--kind", "banana", "--notes", "private words")
        errors = read_jsonl(build / "log-errors.jsonl")
        self.assertEqual(len(errors), 2)
        for item in errors:
            self.assertEqual(set(item), {"ts", "command", "exit", "reason"})
        text = (build / "log-errors.jsonl").read_text()
        self.assertNotIn("banana", text)
        self.assertNotIn("private words", text)
        no_build_env = dict(self.env); no_build_env.pop("FACTORY_BUILD", None)
        (self.factory_home / "current.jsonl").write_text("")
        self.run_factory("log", "event", "--kind", "command", "--actor", "orchestrator",
                         env={"FACTORY_BUILD": ""})
        self.assertEqual(len(read_jsonl(self.factory_home / "log-errors.jsonl")), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
