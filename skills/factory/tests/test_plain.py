"""Round-3 plain-summary contracts for the Factory page (T-PG-01..32, 61, 62, 89)."""

import json
import os
import re
import subprocess
from pathlib import Path

from tests.common import (
    DEFAULT_PROJECT_CONFIG, FIXTURES, KIT_DIR, PYTHON, REPO_ROOT, FactoryTestCase,
    read_jsonl, tree_snapshot, write_json,
)


PAGE_FIXTURES = FIXTURES / "page"
PROBES = PAGE_FIXTURES / "plain_probes.json"
DESIGNER_NOTES = PAGE_FIXTURES / "designer_plain_notes.json"


class PlainWordsContractTests(FactoryTestCase):
    def _plain_functions(self):
        lib = self.require_module("factorylib")
        self.assertTrue(callable(getattr(lib, "plain_check", None)),
                        "planned function missing: factorylib.plain_check")
        self.assertTrue(callable(getattr(lib, "plain_label_check", None)),
                        "planned function missing: factorylib.plain_label_check")
        return lib.plain_check, lib.plain_label_check

    def test_T_PG_01_probe_file_is_the_complete_round_3_contract(self):
        """T-PG-01: pass, fail, exact, labels, allowed words, and secret-safe reasons."""
        plain_check, label_check = self._plain_functions()
        data = json.loads(PROBES.read_text())

        for text in data["pass"]:
            with self.subTest(kind="pass", text=text):
                self.assertEqual(plain_check(text), [])
        for text in data["fail"]:
            with self.subTest(kind="fail", text=text):
                self.assertTrue(plain_check(text), "known bad owner text was accepted")
        for text, reasons in data["exact"]:
            with self.subTest(kind="exact", text=text):
                self.assertEqual(plain_check(text), reasons)
        for text in data["label_pass"]:
            with self.subTest(kind="label-pass", text=text):
                self.assertEqual(label_check(text), [])
        for text in data["label_fail"]:
            with self.subTest(kind="label-fail", text=text):
                self.assertTrue(label_check(text), "known bad owner label was accepted")

        allowed = data["allowed_words"]
        for text in data["pass_with_allowed"]:
            self.assertEqual(plain_check(text, allowed), [])
        for text in data["fail_without_allowed"]:
            self.assertTrue(plain_check(text))
        for text in data["fail_with_allowed"]:
            self.assertTrue(plain_check(text, allowed))

        # known_gaps is intentionally not passed to either checker.
        self.assertEqual(len(data["known_gaps"]), 44)
        probe_text = data["secret_cases"][0][0]
        reasons = plain_check(probe_text)
        rendered = " ".join(reasons)
        self.assertNotRegex(rendered, r"[0-9a-fA-F]{13}")
        self.assertNotIn("9f86d081884c7", rendered)

    def test_T_PG_02_designer_notes_and_shipped_examples_are_regressions(self):
        """T-PG-02: at least 59 designer notes and every shipped rewrite example pass."""
        plain_check, _ = self._plain_functions()
        designer = json.loads(DESIGNER_NOTES.read_text())
        notes = designer["notes"]
        texts = [item["p"] for item in notes.values()] + list(designer["recent"].values())
        self.assertEqual(len(texts), 75)
        passed = sum(not plain_check(text) for text in texts)
        self.assertGreaterEqual(passed, 59)
        for key, needles in {
                "s02A": ("abbreviation", "model"),
                "s030": ("model",),
                "s100": ("abbreviation", "model"),
        }.items():
            reasons = " ".join(plain_check(notes[key]["p"])).lower()
            for needle in needles:
                self.assertIn(needle, reasons)

        examples = KIT_DIR / "templates" / "plain-examples.json"
        self.assertTrue(examples.is_file(),
                        "planned file missing: skills/factory/templates/plain-examples.json")
        for item in json.loads(examples.read_text()):
            self.assertEqual(plain_check(item["plain"]), [])


class PlainCommandContractTests(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.config = json.loads(json.dumps(DEFAULT_PROJECT_CONFIG))
        self.write_project_config(self.config)
        self.build = self.factory_home / "runs" / "toy" / "page"
        self.build.mkdir(parents=True)
        (self.build / "trace.jsonl").write_text("")
        (self.build / "expected.jsonl").write_text("")
        (self.build / "messages").mkdir()
        write_json(self.build / "build.json", {
            "project": "toy", "build": "page", "title": "Toy page",
            "started": "2026-01-10T12:00:00Z", "stop_times": [],
        })
        self.select("toy", "page")
        self.prompt = self.project / "prompt.md"
        self.prompt.write_text("synthetic prompt\n")

    def trace(self):
        return read_jsonl(self.build / "trace.jsonl")

    def start(self, actor="maker", call="A1.maker.1", node="A1", *extra):
        result = self.run_factory(
            "log", "start", "--kind", "agent_call", "--actor", actor,
            "--call", call, "--node", node, "--input", str(self.prompt), *extra,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return self.trace()[-1]["span_id"]

    def test_T_PG_03_to_05_gate_text_uses_plain_check_and_closes_with_plain(self):
        """T-PG-03..05: gate validation stays atomic and closing lines gain plain fields."""
        before = (self.build / "trace.jsonl").read_bytes()
        bad = self.run_factory(
            "gate", "open", "--name", "GATE A", "--question", "Approve T-UI-01?",
            "--recommend", "Yes.", "--no-notify",
        )
        self.assertEqual(bad.returncode, 2)
        self.assertIn(
            'the question contains "T-UI-01", which looks like an id the owner cannot read. '
            'Say it in plain words.', bad.stderr)
        self.assertEqual((self.build / "trace.jsonl").read_bytes(), before)

        unexplained = self.run_factory(
            "gate", "open", "--name", "GATE A", "--question", "The review failed.",
            "--recommend", "Yes.", "--no-notify",
        )
        self.assertEqual(unexplained.returncode, 2)
        self.assertIn("without saying why", unexplained.stderr)

        opened = self.run_factory(
            "gate", "open", "--name", "GATE A", "--question",
            "Do you want it released now?", "--recommend", "Yes, release it now.",
            "--no-notify",
        )
        self.assertEqual(opened.returncode, 0, opened.stderr)
        wait = self.trace()[-1]
        self.assertEqual(wait.get("plain"), "Do you want it released now?")
        self.assertEqual(wait.get("plain_source"), "agent")
        closed = self.run_factory("gate", "close", wait["span_id"], "--answer", "Yes")
        self.assertEqual(closed.returncode, 0, closed.stderr)
        self.assertEqual(self.trace()[-1].get("plain"),
                         "You answered this decision, and the build carried on.")
        self.assertEqual(self.trace()[-1].get("plain_source"), "auto")

    def test_T_PG_06_to_12_log_plain_group_reason_and_next_step_contract(self):
        """T-PG-06..12: logging writes soft plain fields and rejects only bad flag usage."""
        span = self.start("maker", "A1.maker.1", "A1", "--group", "tests")
        self.assertEqual(self.trace()[-1].get("group"), "tests")
        result = self.run_factory(
            "log", "end", span, "--plain",
            "Wrote the greeting words. A checker reads them next.",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        line = self.trace()[-1]
        self.assertEqual(line.get("plain_source"), "agent")
        self.assertNotIn("plain_flag", line)

        missing_span = self.start(call="A1.maker.2")
        missing = self.run_factory("log", "end", missing_span)
        self.assertEqual(missing.returncode, 0)
        self.assertEqual(self.trace()[-1].get("plain_flag"), "missing")
        self.assertEqual(missing.stderr,
                         "factory: no plain summary was given. Add --plain next time; "
                         "factory plain will write one later.\n")

        rejected_span = self.start(call="A1.maker.3")
        rejected = self.run_factory("log", "end", rejected_span, "--plain", "Stopped.")
        self.assertEqual(rejected.returncode, 0)
        self.assertEqual(self.trace()[-1].get("plain_flag"), "failed_check")
        self.assertEqual(self.trace()[-1].get("plain_rejected"), "Stopped.")
        self.assertNotIn("plain", self.trace()[-1])

        reason_span = self.start(call="A1.maker.4")
        reason = self.run_factory(
            "log", "end", reason_span, "--status", "stopped", "--stop-reason",
            "usage_limit", "--next-step", "A new checker starts after the limit resets.",
            "--plain", "The checker stopped because its daily usage limit ran out. "
            "A new checker starts after the limit resets.",
        )
        self.assertEqual(reason.returncode, 0, reason.stderr)
        self.assertEqual(self.trace()[-1].get("stop_reason"), "usage_limit")
        self.assertEqual(self.trace()[-1].get("next_step"),
                         "A new checker starts after the limit resets.")

        before = (self.build / "trace.jsonl").read_bytes()
        for args in (
                ("log", "event", "--kind", "command", "--actor", "orchestrator",
                 "--status", "done", "--stop-reason", "stuck"),
                ("log", "event", "--kind", "command", "--actor", "orchestrator",
                 "--status", "failed", "--stop-reason", "nope"),
                ("log", "beat", "--stop-reason", "error"),
        ):
            with self.subTest(args=args):
                bad = self.run_factory(*args)
                self.assertEqual(bad.returncode, 2)
                self.assertNotIn("Traceback", bad.stderr)
        self.assertEqual((self.build / "trace.jsonl").read_bytes(), before)

        next_span = self.start(call="A1.maker.5")
        bad_next = self.run_factory(
            "log", "end", next_span, "--status", "failed", "--failure-class",
            "env-tooling", "--stop-reason", "error", "--next-step", "Retry N2.",
        )
        self.assertEqual(bad_next.returncode, 0)
        self.assertNotIn("next_step", self.trace()[-1])
        self.assertIn('factory: the next step was not kept: It contains "N2"', bad_next.stderr)

    def test_T_PG_13_to_18_run_plain_file_auto_endings_and_step_precedence(self):
        """T-PG-13..18: run and step keep valid text and generate factual abnormal summaries."""
        ok = self.run_factory(
            "run", "--actor", "maker", "--call", "A1.maker.1", "--node", "A1",
            "--input", str(self.prompt), "--plain",
            "Wrote the greeting words. A checker reads them next.", "--", "/bin/echo", "hi",
        )
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertEqual(self.trace()[-1].get("plain_source"), "agent")

        from_file = self.run_factory(
            "run", "--actor", "maker", "--call", "A1.maker.2", "--node", "A1",
            "--input", str(self.prompt), "--plain-file", "out.txt", "--", "/bin/sh", "-c",
            'echo "Wrote the words. A checker reads them next." > out.txt',
        )
        self.assertEqual(from_file.returncode, 0, from_file.stderr)
        self.assertEqual(self.trace()[-1].get("plain"),
                         "Wrote the words. A checker reads them next.")

        missing_file = self.run_factory(
            "run", "--actor", "maker", "--call", "A1.maker.file-missing", "--node", "A1",
            "--input", str(self.prompt), "--plain-file", "missing.txt", "--", "/usr/bin/true",
        )
        self.assertEqual(missing_file.returncode, 0, missing_file.stderr)
        self.assertEqual(self.trace()[-1].get("plain_flag"), "missing")
        self.assertNotIn("plain", self.trace()[-1])

        failed = self.run_factory(
            "run", "--actor", "maker", "--call", "A1.maker.3", "--node", "A1",
            "--input", str(self.prompt), "--plain", "All good.", "--", "/bin/sh", "-c",
            "exit 3",
        )
        self.assertEqual(failed.returncode, 3)
        self.assertEqual(self.trace()[-1].get("stop_reason"), "error")
        self.assertEqual(self.trace()[-1].get("plain"),
                         "The builder ended early because the program reported an error. "
                         "The coordinator reads its output next.")
        self.assertEqual(self.trace()[-1].get("plain_given"), "All good.")

        missing = self.run_factory(
            "run", "--actor", "maker", "--call", "A1.maker.4", "--node", "A1",
            "--input", str(self.prompt), "--", "/definitely/not/a/program",
        )
        self.assertNotEqual(missing.returncode, 0)
        self.assertEqual(self.trace()[-1].get("plain"),
                         "The builder ended early because its program could not be started. "
                         "The coordinator decides what happens next.")

        timed = self.run_factory(
            "run", "--actor", "checker", "--call", "A1.checker.timeout", "--node", "A1",
            "--input", str(self.prompt), "--timeout", "0.2", "--", "/bin/sleep", "5",
        )
        self.assertEqual(timed.returncode, 124, timed.stderr)
        self.assertEqual(self.trace()[-1].get("stop_reason"), "stuck")
        self.assertEqual(self.trace()[-1].get("plain"),
                         "The checker ended early because it ran past its time limit of 1 second. "
                         "The coordinator decides what happens next.")

        self.config["tests"]["fast"]["cmd"] = "echo hi"
        write_json(self.project / "factory.json", self.config)
        step = self.run_factory("step", "tests.fast")
        self.assertEqual(step.returncode, 0, step.stderr)
        self.assertEqual(self.trace()[-1].get("plain"), "A project command ran and finished.")
        self.config["tests"]["fast"]["plain"] = "The quick tests ran and passed."
        write_json(self.project / "factory.json", self.config)
        configured = self.run_factory("step", "tests.fast")
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertEqual(self.trace()[-1].get("plain"), "The quick tests ran and passed.")
        self.assertEqual(self.trace()[-1].get("plain_source"), "agent")
        override = self.run_factory("step", "tests.fast", "--plain",
                                    "A short check ran. It found nothing wrong.")
        self.assertEqual(override.returncode, 0, override.stderr)
        self.assertEqual(self.trace()[-1].get("plain_source"), "agent")

    def test_T_PG_25_to_32_plain_rewriter_is_append_only_bounded_and_idempotent(self):
        """T-PG-25..32: factory plain dry-run, retry, fallback, prompt, status, and idempotence."""
        for index in range(3):
            span = self.start(call="A1.maker.%d" % (index + 1))
            closed = self.run_factory("log", "end", span, "--notes", "wrote technical words")
            self.assertEqual(closed.returncode, 0, closed.stderr)
        before = (self.build / "trace.jsonl").read_bytes()
        status_before = self.run_factory("status")
        self.assertIn("3 steps have no plain summary yet. Run: factory plain", status_before.stdout)
        dry = self.run_factory("plain", "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertEqual(dry.stdout, "factory: 3 entries would be rewritten\n")
        self.assertEqual((self.build / "trace.jsonl").read_bytes(), before)

        absent = self.run_factory("plain")
        self.assertEqual(absent.returncode, 3)
        self.assertEqual(absent.stderr,
                         "factory: no summaries role in factory.json; add roles.summaries, "
                         "see factory.example.json\n")
        self.assertEqual((self.build / "trace.jsonl").read_bytes(), before)

        fallback = self.run_factory("plain", "--fallback-only")
        self.assertEqual(fallback.returncode, 0, fallback.stderr)
        self.assertIn("factory: rewrote 0, fell back on 3, left 0 for later", fallback.stdout)
        self.assertEqual(before, (self.build / "trace.jsonl").read_bytes()[:len(before)])
        merged = self.require_module("factorylib").read_build(self.build)["spans"]
        calls = [item for item in merged if item.get("kind") == "agent_call"]
        self.assertTrue(all(item.get("plain_source") == "fallback" for item in calls))
        again_before = (self.build / "trace.jsonl").read_bytes()
        again = self.run_factory("plain", "--fallback-only")
        self.assertEqual(again.returncode, 0)
        self.assertEqual((self.build / "trace.jsonl").read_bytes(), again_before)

        status = self.run_factory("status")
        self.assertNotIn("steps have no plain summary yet", status.stdout)

    def test_T_PG_26_to_31_model_rewrite_retries_and_prompt_privacy(self):
        """T-PG-26..31: summary stub calls are logged, retried once, and receive field-only context."""
        key = "ghp_abcdefghijklmnopqr" + "stuvwxyz0123456789"
        write_json(self.build / "plan.json", {
            "v": 1, "source": "GRAPH.yaml", "generated": "2026-01-10T12:00:00Z",
            "pieces": [{"id": "B1", "name": "Shout option", "tech_name": "Beta module",
                        "purpose": "Make the program shout when asked.",
                        "depends_on": [], "stage": 1}],
            "stages": [{"n": 1, "name": "Two options",
                        "purpose": "Build the options.", "members": ["B1"]}],
        })
        previous = self.start(call="B1.maker.previous", node="B1")
        previous_end = self.run_factory(
            "log", "end", previous, "--plain",
            "The builder prepared the first words. A checker read them next.")
        self.assertEqual(previous_end.returncode, 0, previous_end.stderr)
        span = self.start(call="B1.maker.1", node="B1")
        closed = self.run_factory("log", "end", span, "--notes", "wrote words with " + key)
        self.assertEqual(closed.returncode, 0, closed.stderr)
        following = self.start(call="B1.checker.following", node="B1", actor="checker")
        following_end = self.run_factory(
            "log", "end", following, "--plain",
            "The checker approved the words. This piece is finished.")
        self.assertEqual(following_end.returncode, 0, following_end.stderr)
        before = (self.build / "trace.jsonl").read_bytes()

        stub_log = self.tmp / "stub.log"
        stub_count = self.tmp / "stub.count"
        stub_replies = self.tmp / "stub.replies"
        stub_replies.write_text(
            "Sonnet 5.5 rewrote this step.\n"
            "The builder wrote the greeting words. A checker reads them next.\n")
        stub = self.fake_program(
            "ollama",
            "import os, pathlib, sys\n"
            "log=pathlib.Path(os.environ['STUB_LOG'])\n"
            "prompt=sys.stdin.read()\n"
            "with log.open('a') as f: f.write(prompt + '\\n---\\n')\n"
            "count=pathlib.Path(os.environ['STUB_COUNT'])\n"
            "n=int(count.read_text()) if count.exists() else 0\n"
            "lines=pathlib.Path(os.environ['STUB_REPLIES']).read_text().splitlines()\n"
            "count.write_text(str(n+1))\n"
            "print(lines[min(n, len(lines)-1)])",
        )
        self.config["roles"]["summaries"] = {"runner": "ollama", "model": "qwen3:14b"}
        write_json(self.project / "factory.json", self.config)
        env = {
            "PATH": str(stub.parent) + os.pathsep + self.env.get("PATH", ""),
            "STUB_LOG": str(stub_log), "STUB_COUNT": str(stub_count),
            "STUB_REPLIES": str(stub_replies),
        }
        result = self.run_factory("plain", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stub_count.read_text(), "2")
        self.assertIn("factory: rewrote 1, fell back on 0, left 0 for later", result.stdout)
        self.assertEqual((self.build / "trace.jsonl").read_bytes()[:len(before)], before)
        merged = self.require_module("factorylib").read_build(self.build)["spans"]
        original = next(item for item in merged if item.get("call") == "B1.maker.1")
        self.assertEqual(original.get("plain"),
                         "The builder wrote the greeting words. A checker reads them next.")
        self.assertEqual(original.get("plain_source"), "rewritten")
        summary_calls = [item for item in merged if item.get("actor") == "summaries"]
        self.assertEqual(len(summary_calls), 2)
        self.assertTrue(all(item.get("plain") == "A summary writer rewrote one note."
                            for item in summary_calls))
        prompt = stub_log.read_text()
        self.assertIn('It names a model or tool ("Sonnet").', prompt)
        self.assertIn("Shout option", prompt)
        self.assertIn("The builder prepared the first words.", prompt)
        self.assertIn("The checker approved the words.", prompt)
        self.assertIn("[REDACTED]", prompt)
        self.assertNotIn(key, prompt)
        for forbidden in ('"span_id"', '"ts"', '{"v"'):
            self.assertNotIn(forbidden, prompt)

        second_before = (self.build / "trace.jsonl").read_bytes()
        second = self.run_factory("plain", env=env)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.build / "trace.jsonl").read_bytes(), second_before)

    def test_T_PG_28_and_29_two_bad_replies_and_empty_notes_use_fixed_fallbacks(self):
        """T-PG-28..29: two rejected rewrites fall back; an empty entry calls no model."""
        done_span = self.start(call="A1.maker.done")
        done_end = self.run_factory("log", "end", done_span, "--notes", "technical done note")
        self.assertEqual(done_end.returncode, 0, done_end.stderr)
        failed_span = self.start(call="A1.maker.failed")
        failed_end = self.run_factory(
            "log", "end", failed_span, "--status", "failed", "--failure-class", "env-tooling",
            "--stop-reason", "error", "--notes", "technical failed note")
        self.assertEqual(failed_end.returncode, 0, failed_end.stderr)
        empty_span = self.start(call="A1.maker.empty")
        empty_end = self.run_factory("log", "end", empty_span)
        self.assertEqual(empty_end.returncode, 0, empty_end.stderr)

        stub_count = self.tmp / "fallback.count"
        stub_replies = self.tmp / "fallback.replies"
        stub_replies.write_text("Sonnet rewrote it.\nSonnet rewrote it.\nStopped.\nStopped.\n")
        stub = self.fake_program(
            "ollama",
            "import os, pathlib\n"
            "count=pathlib.Path(os.environ['STUB_COUNT'])\n"
            "n=int(count.read_text()) if count.exists() else 0\n"
            "lines=pathlib.Path(os.environ['STUB_REPLIES']).read_text().splitlines()\n"
            "count.write_text(str(n+1))\n"
            "print(lines[min(n, len(lines)-1)])",
        )
        self.config["roles"]["summaries"] = {"runner": "ollama", "model": "qwen3:14b"}
        write_json(self.project / "factory.json", self.config)
        env = {"PATH": str(stub.parent) + os.pathsep + self.env.get("PATH", ""),
               "STUB_COUNT": str(stub_count), "STUB_REPLIES": str(stub_replies)}
        result = self.run_factory("plain", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stub_count.read_text(), "4")
        spans = {item.get("call"): item for item in
                 self.require_module("factorylib").read_build(self.build)["spans"]}
        self.assertEqual(spans["A1.maker.done"]["plain"],
                         "This step finished. Its original note is too technical to show here; "
                         "turn on technical details to read it.")
        self.assertEqual(spans["A1.maker.failed"]["plain"],
                         "This step ended early. The reason was not written down in plain words; "
                         "turn on technical details to see the original note.")
        self.assertEqual(spans["A1.maker.empty"]["plain"],
                         "The builder did not leave a note.")
        self.assertTrue(all(spans[key]["plain_source"] == "fallback" for key in
                            ("A1.maker.done", "A1.maker.failed", "A1.maker.empty")))

    def test_T_PG_89_redaction_precedes_check_and_narrow_hex_rule_is_binding(self):
        """T-PG-89: secrets never reach files or reasons; ordinary all-hex words remain."""
        lib = self.require_module("factorylib")
        self.assertTrue(callable(getattr(lib, "plain_check", None)),
                        "planned function missing: factorylib.plain_check")
        mixed_hex = "9f86d081884c7d659a2f" + "eaa0c55ad015a3bf4f1b"
        self.assertEqual(lib.redact("acceded defaced"), "acceded defaced")
        self.assertNotIn(mixed_hex, lib.redact_plain("key " + mixed_hex))
        self.assertIn("[REDACTED]", lib.redact_plain("key " + mixed_hex))

        span = self.start()
        key = "ghp_abcdefghijklmnopqr" + "stuvwxyz0123456789"
        result = self.run_factory(
            "log", "end", span, "--plain",
            "Wrote the key %s into the notes. A checker reads them next." % key,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        all_bytes = b"".join(path.read_bytes() for path in self.build.rglob("*") if path.is_file())
        self.assertNotIn(key.encode(), all_bytes)
        self.assertNotIn(mixed_hex[:13], result.stderr)
        line = self.trace()[-1]
        self.assertEqual(line.get("plain_flag"), None)
        self.assertEqual(lib.plain_check(line["plain"]), [])


class PlainFilesContractTests(FactoryTestCase):
    def test_T_PG_61_and_62_templates_are_private_safe_plain_and_valid(self):
        """T-PG-61..62: all new templates exist; examples pass; graph creates a plan."""
        lib = self.require_module("factorylib")
        self.assertTrue(callable(getattr(lib, "plain_check", None)),
                        "planned function missing: factorylib.plain_check")
        self.assertTrue(callable(getattr(lib, "scan_text", None)),
                        "planned function missing: factorylib.scan_text")
        templates = KIT_DIR / "templates"
        for name in ("plain-examples.json", "plain-rules.md", "GRAPH.yaml"):
            self.assertTrue((templates / name).is_file(), "planned template missing: " + name)
        for item in json.loads((templates / "plain-examples.json").read_text()):
            self.assertEqual(lib.plain_check(item["plain"]), [])

        for name in ("plain-examples.json", "plain-rules.md", "GRAPH.yaml"):
            findings = lib.scan_text((templates / name).read_text(encoding="utf-8"))
            self.assertEqual(findings, [], name + " contains private-looking content")

        self.write_project_config(DEFAULT_PROJECT_CONFIG)
        result = self.run_factory(
            "new", "template-plan", "--project", "toy", "--title", "Template plan",
            "--from-graph", str(templates / "GRAPH.yaml"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.factory_home / "runs" / "toy" / "template-plan" / "plan.json").is_file())


if __name__ == "__main__":
    import unittest
    unittest.main()
