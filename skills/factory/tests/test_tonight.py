"""Tonight release contracts T-TN-01 through T-TN-24."""

import http.client
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import time
from pathlib import Path
from unittest import mock

from tests.common import (
    FACTORY_PY, KIT_DIR, PYTHON, SCRIPTS_DIR, FactoryTestCase, read_jsonl,
    write_json, write_jsonl,
)
from tests.test_plan_board import pg1_lines, plan_value


FIXTURE_MAKER = Path(__file__).parent / "fixtures" / "tonight" / "make_tonight_fixtures.py"
DOCS = (KIT_DIR / "README.md", KIT_DIR / "SKILL.md", KIT_DIR / "PROCESS.md")
HOSTILE_TAGS = (
    "f-title", "f-piece", "f-purpose", "f-stage", "f-actor", "f-model", "f-call",
    "f-node-label", "f-plain", "f-notes", "f-next-step", "f-question", "f-answer",
    "f-deadline",
)
IMAGE_MARKER = '<img src=x onerror="window.__tn=(window.__tn||0)+1">'
SCRIPT_MARKER = "</script><script>window.__tn=99</script>"


class TonightFixtureCase(FactoryTestCase):
    """Install all tonight builds under a disposable Factory home."""

    def setUp(self):
        super().setUp()
        self.env["TZ"] = "America/New_York"
        self.env["FACTORY_OSASCRIPT_BIN"] = str(self.fake_program(
            "fake-osascript", "import sys; sys.exit(99)",
        ))
        made = self.run_fixture_maker()
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)

    def run_fixture_maker(self):
        import subprocess
        return subprocess.run(
            [PYTHON, "-I", str(FIXTURE_MAKER), str(self.factory_home)],
            cwd=str(KIT_DIR), env=self.env, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=0.95,
        )

    def fixture(self, name, project="tn"):
        path = self.factory_home / "runs" / project / name
        self.assertTrue(path.is_dir(), "planned tonight fixture missing: %s/%s" % (project, name))
        return path

    def board(self, name, now, project="tn"):
        lib = self.require_module("factorylib")
        with mock.patch.dict(os.environ, self.env, clear=False):
            time.tzset()
            value = lib.board(self.fixture(name, project), now_value=now)
        self.assertIn("owner", value, "planned field missing: board.owner")
        return lib, value

    @staticmethod
    def piece(board, piece_id):
        for piece in board.get("plan", {}).get("pieces", []):
            if piece.get("id") == piece_id:
                return piece
        raise AssertionError("planned piece missing from board: %s" % piece_id)

    @staticmethod
    def record(records, piece_id):
        for record in records:
            if record.get("piece") == piece_id or record.get("piece_id") == piece_id:
                return record
        raise AssertionError("planned board record missing for piece: %s" % piece_id)

    def make_pg1(self):
        folder = self.factory_home / "runs" / "toy" / "pg1"
        folder.mkdir(parents=True)
        write_jsonl(folder / "trace.jsonl", pg1_lines())
        write_json(folder / "plan.json", plan_value())
        write_json(folder / "build.json", {
            "project": "toy", "build": "pg1", "title": "Toy: add two options",
            "started": "2026-01-10T14:00:00Z", "stop_times": [],
        })
        write_jsonl(folder / "expected.jsonl", [
            {"call": "%s.%s.1" % (piece, role), "node": piece, "actor": role,
             "added_by": "graph"}
            for piece in ("A1", "B1", "B2", "C1") for role in ("maker", "checker")
        ])
        return folder


class TonightBoardTests(TonightFixtureCase):
    def test_T_TN_01_built_piece_waits_for_a_check(self):
        """T-TN-01: a finished builder with no checker running has the built state."""
        _lib, board = self.board("built", "2026-01-10T14:37:00Z")
        owner = board["owner"]
        self.assertEqual(
            owner.get("sentence"),
            "Building: 1 of 4 pieces done, 1 waiting for a check, none running right now.",
        )
        self.assertNotIn("being checked", owner["sentence"])
        self.assertEqual(owner.get("counts"), {
            "total": 4, "done": 1, "building": 0, "checking": 0, "built": 1,
            "sent_back": 0, "stopped": 0, "waiting": 2, "needs_you": 0,
        })
        b1 = self.piece(board, "B1")
        self.assertEqual(b1.get("state"), "built")
        self.assertEqual(b1.get("state_label"), "Built, waiting for a check")
        self.assertEqual(b1.get("now"), "Built. Waiting for a check. No checker has started yet.")
        self.assertEqual(b1.get("attempt_label"), "Attempt 1 of this piece")
        self.assertIsNone(b1.get("quiet_text"))
        self.assertEqual(b1.get("roles", {}).get("builder", {}).get("note"),
                         "finished this attempt")
        self.assertNotIn("checker", b1.get("roles", {}))
        stage = next(stage for stage in board["plan"]["stages"]
                     if "B1" in stage.get("pieces", []))
        self.assertEqual(stage.get("state"), "active")

    def test_T_TN_02_running_checker_is_still_checking(self):
        """T-TN-02: a currently running checker keeps the checking state."""
        _lib, board = self.board("checking", "2026-01-10T14:37:00Z")
        counts = board["owner"].get("counts", {})
        self.assertIn("built", counts, "planned field missing: owner.counts.built")
        self.assertEqual(board["owner"].get("sentence"),
                         "Building: 1 of 4 pieces done, 1 being checked.")
        self.assertEqual(counts.get("checking"), 1)
        self.assertEqual(counts.get("built"), 0)
        b1 = self.piece(board, "B1")
        self.assertEqual((b1.get("state"), b1.get("state_label")),
                         ("checking", "Being checked"))

    def test_T_TN_03_existing_pg1_checker_remains_checking(self):
        """T-TN-03: the existing PG-1 running checker does not regress to built."""
        lib = self.require_module("factorylib")
        with mock.patch.dict(os.environ, self.env, clear=False):
            time.tzset()
            board = lib.board(self.make_pg1(), now_value="2026-01-10T14:50:00Z")
        counts = board.get("owner", {}).get("counts", {})
        self.assertIn("built", counts, "planned field missing: owner.counts.built")
        self.assertEqual(board["owner"].get("sentence"),
                         "Building: 1 of 4 pieces done, 1 being checked, 1 being built.")
        self.assertEqual(counts.get("built"), 0)

    def test_T_TN_04_new_board_words_pass_plain_checks(self):
        """T-TN-04: every new fixed board sentence and label passes the plain-word checks."""
        lib = self.require_module("factorylib")
        sentences = (
            "Built. Waiting for a check. No checker has started yet.",
            "Building: 1 of 4 pieces done, 1 waiting for a check, none running right now.",
            "Nothing is running. Last activity Jan 10, 9:35 am. 1 of 4 pieces done, 1 waiting for a check.",
            "Nothing is running. Last activity Jan 10, 9:35 am. 1 of 4 pieces done, 1 ended early.",
            "Finished. All 4 pieces are done.",
            "Building: 0 of 7 pieces done, 1 waiting for a check. 1 other task running.",
        )
        for sentence in sentences:
            with self.subTest(sentence=sentence):
                self.assertEqual(lib.plain_check(sentence), [])
        self.assertEqual(lib.plain_label_check("Built, waiting for a check"), [])

    def test_T_TN_05_all_done_is_not_finished_without_marker(self):
        """T-TN-05: all approved pieces still need the explicit finish marker."""
        lib, board = self.board("alldone", "2026-01-10T15:44:00Z")
        self.assertEqual(board["owner"].get("sentence"),
                         "All 4 pieces are done. The build has not been closed yet.")
        self.assertNotEqual(board.get("build", {}).get("state"), "done")
        self.assertIn("finished_at", board.get("build", {}),
                      "planned field missing: board.build.finished_at")
        self.assertIsNone(board["build"]["finished_at"])
        self.assertEqual(board["build"].get("leftovers"), [])
        rows = lib.list_builds(self.factory_home, "2026-01-10T15:44:00Z")
        row = next(item for item in rows if item["project"] == "tn" and item["id"] == "alldone")
        self.assertNotEqual(row.get("state_word"), "Finished")

    def test_T_TN_06_quiet_and_stale_builds_do_not_say_building(self):
        """T-TN-06: quiet work reports its real last activity and never says Building."""
        _lib, quiet = self.board("quiet", "2026-01-11T05:35:00Z")
        _lib, stale = self.board("stale", "2026-01-11T05:35:00Z")
        _lib, recent = self.board("built", "2026-01-10T14:37:00Z")
        self.assertEqual(
            quiet["owner"].get("sentence"),
            "Nothing is running. Last activity Jan 10, 9:35 am. 1 of 4 pieces done, 1 waiting for a check.",
        )
        self.assertEqual(
            stale["owner"].get("sentence"),
            "Nothing is running. Last activity Jan 10, 9:35 am. 1 of 4 pieces done, 1 ended early.",
        )
        self.assertNotIn("Building", quiet["owner"]["sentence"])
        self.assertNotIn("Building", stale["owner"]["sentence"])
        self.assertTrue(recent["owner"].get("sentence", "").startswith("Building:"))

    def test_T_TN_07_finish_closes_build_once_and_is_append_only(self):
        """T-TN-07: finish writes a marker once, updates the board, then is idempotent."""
        path = self.fixture("alldone") / "trace.jsonl"
        before = path.read_bytes()
        first = self.run_factory("finish", "--build", "tn/alldone")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout, "Finished tn/alldone.\n")
        self.assertEqual(first.stderr, "")
        after = path.read_bytes()
        self.assertTrue(after.startswith(before), "factory finish rewrote existing log bytes")
        lib = self.require_module("factorylib")
        merged = lib.read_build(self.fixture("alldone"))["spans"]
        feature = next(span for span in merged if span.get("kind") == "feature")
        self.assertEqual(feature.get("status"), "done")
        self.assertTrue(feature.get("end"))
        self.assertEqual(feature.get("leftovers"), [])
        self.assertEqual(feature.get("plain"), "The build was marked finished.")
        self.assertFalse(any(span.get("kind") == "phase" and span.get("status") == "running"
                             for span in merged))
        _lib, board = self.board("alldone", self.env["FACTORY_NOW"])
        self.assertEqual(board["owner"].get("sentence"), "Finished. All 4 pieces are done.")
        self.assertEqual(board["build"].get("state"), "done")
        self.assertTrue(board["build"].get("finished_at"))
        self.assertEqual(board["owner"].get("calm", {}).get("text"),
                         "This build is finished. Nothing is left to decide.")
        row = next(item for item in lib.list_builds(self.factory_home, self.env["FACTORY_NOW"])
                   if item["project"] == "tn" and item["id"] == "alldone")
        self.assertEqual(row.get("state_word"), "Finished")
        second = self.run_factory("finish", "--build", "tn/alldone")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(second.stdout, "tn/alldone was already marked finished.\n")
        self.assertEqual(path.read_bytes(), after)

    def test_T_TN_08_finish_refuses_questions_calls_and_pieces_atomically(self):
        """T-TN-08: open questions, calls, and pieces refuse finish in stable order."""
        path = self.fixture("open") / "trace.jsonl"
        before = path.read_bytes()
        result = self.run_factory("finish", "--build", "tn/open")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(path.read_bytes(), before)
        lines = result.stderr.splitlines()
        self.assertEqual(lines[0], "factory: this build cannot be finished yet. Still open:")
        self.assertTrue(lines[1].startswith("  question GATE B: answer it in the conversation first"))
        self.assertRegex(lines[2], r"^  call B1\.maker\.2 \(.+\): still running$")
        self.assertRegex(lines[3], r"^  piece B1 \(.+\): Building$")
        self.assertRegex(lines[4], r"^  piece C1 \(.+\): Waiting$")
        self.assertEqual(lines[-1],
                         'Close them, or give a reason for each one you are leaving: --leftover ID="why"')
        self.assertNotIn("Traceback", result.stderr)

    def test_T_TN_09_leftovers_cover_piece_calls_and_are_recorded(self):
        """T-TN-09: piece leftovers cover calls, require every piece, and survive on the board."""
        source = self.fixture("open")
        target = self.factory_home / "runs" / "tn" / "open-copy"
        shutil.copytree(source, target)
        gate = self.run_factory("gate", "close", "gate-b", "--answer", "Yes",
                                "--build", "tn/open-copy")
        self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
        path = target / "trace.jsonl"
        before = path.read_bytes()
        missing = self.run_factory("finish", "--build", "tn/open-copy",
                                   "--leftover", "B1=moved to the next release")
        self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
        self.assertIn("piece C1", missing.stderr)
        self.assertNotIn("piece B1", missing.stderr)
        self.assertEqual(path.read_bytes(), before)
        done = self.run_factory(
            "finish", "--build", "tn/open-copy",
            "--leftover", "B1=moved to the next release",
            "--leftover", "C1=not needed",
        )
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stdout, "Finished tn/open-copy. Left open: 2, reasons recorded.\n")
        lib = self.require_module("factorylib")
        spans = lib.read_build(target)["spans"]
        feature = next(span for span in spans if span.get("kind") == "feature")
        self.assertEqual(feature.get("leftovers"), [
            {"id": "B1", "kind": "piece", "reason": "moved to the next release"},
            {"id": "C1", "kind": "piece", "reason": "not needed"},
        ])
        self.assertEqual(feature.get("plain"),
                         "The build was marked finished with 2 things left open.")
        b1_call = next(span for span in spans if span.get("call") == "B1.maker.2")
        self.assertEqual(b1_call.get("status"), "running")
        with mock.patch.dict(os.environ, self.env, clear=False):
            board = lib.board(target, now_value=self.env["FACTORY_NOW"])
        self.assertEqual(board["build"].get("state"), "done")
        self.assertEqual(board["owner"].get("sentence"), "Finished. 2 of 4 pieces are done.")
        self.assertEqual(len(board["build"].get("leftovers", [])), 2)

    def test_T_TN_10_finish_validation_help_and_reopen_rules(self):
        """T-TN-10: finish validates leftovers, advertises flags, and reopens after later work."""
        path = self.fixture("alldone") / "trace.jsonl"
        invalid = (
            (("--leftover", "B1"),
             'factory: --leftover must look like ID=reason, for example B2="not needed after all".\n'),
            (("--leftover", "B1="),
             'factory: --leftover must look like ID=reason, for example B2="not needed after all".\n'),
            (("--leftover", "ZZ=why"),
             "factory: --leftover names ZZ, which is not open in this build.\n"),
        )
        for args, expected in invalid:
            before = path.read_bytes()
            result = self.run_factory("finish", "--build", "tn/alldone", *args)
            with self.subTest(args=args):
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stderr, expected)
                self.assertEqual(path.read_bytes(), before)
        help_result = self.run_factory("finish", "--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        for flag in ("--build", "--leftover", "--plain"):
            self.assertIn(flag, help_result.stdout)
        root_help = self.run_factory("--help")
        lines = root_help.stdout.splitlines()
        finish_line = "  finish        mark the build finished (refuses while work is open)"
        self.assertIn(finish_line, lines)
        self.assertEqual(lines.index(finish_line),
                         next(i for i, line in enumerate(lines) if line.strip().startswith("dashboard")) + 1)
        finished = self.run_factory("finish", "--build", "tn/alldone")
        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        marker = next(item for item in read_jsonl(path) if item.get("leftovers") == [])
        later = "2026-01-10T16:00:00Z"
        with path.open("a") as stream:
            stream.write(json.dumps({
                "v": 1, "span_id": "later-call", "ts": later, "start": later,
                "kind": "agent_call", "actor": "maker", "call": "Z9.maker.1",
                "node": "Z9", "status": "running",
            }, sort_keys=True) + "\n")
        _lib, board = self.board("alldone", "2026-01-10T16:01:00Z")
        self.assertEqual(board["build"].get("state"), "running")
        self.assertIsNone(board["build"].get("finished_at"))
        self.assertEqual(board["owner"].get("sentence"),
                         "All 4 pieces are done. The build has not been closed yet. "
                         "1 other task running.")
        refused = self.run_factory("finish", "--build", "tn/alldone")
        self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
        self.assertIn("Z9.maker.1", refused.stderr)
        self.assertTrue(marker.get("end"))

    def test_T_TN_11_plan_counts_exclude_other_work(self):
        """T-TN-11: owner counts use plan pieces while Other work stays visible."""
        _lib, board = self.board("other", "2026-01-10T14:37:00Z")
        self.assertEqual(board["owner"].get("sentence"),
                         "Building: 0 of 7 pieces done, 1 waiting for a check. 1 other task running.")
        self.assertEqual(board["owner"].get("counts", {}).get("total"), 7)
        self.assertEqual(board["owner"].get("other"), {"total": 1, "running": 1, "done": 0})
        pieces = board.get("plan", {}).get("pieces", [])
        self.assertTrue(all("planned" in piece for piece in pieces),
                        "planned field missing: plan.pieces[].planned")
        self.assertEqual(sum(piece["planned"] is True for piece in pieces), 7)
        x9 = next(piece for piece in pieces if piece.get("id") == "X9")
        self.assertIs(x9["planned"], False)
        stage = board["plan"]["stages"][-1]
        self.assertEqual(stage.get("name"), "Other work")
        self.assertEqual(stage.get("pieces"), ["X9"])

    def test_T_TN_12_plan_names_win_and_other_names_use_work_lines(self):
        """T-TN-12: notes cannot rename plan pieces or override work-line names."""
        lib, board = self.board("other", "2026-01-10T14:37:00Z")
        plan_p1 = self.piece(board, "P1")
        self.assertEqual(plan_p1.get("name"), "Plan piece one")
        piece_p1 = self.record(board.get("pieces", []), "P1")
        self.assertEqual(piece_p1.get("piece_label"), "Plan piece one")
        p1_agents = [agent for agent in board.get("agents", []) if agent.get("piece_id") == "P1"]
        self.assertTrue(p1_agents)
        self.assertTrue(all(agent.get("piece_label") == "Plan piece one" for agent in p1_agents))
        names = json.dumps({"plan": board.get("plan", {}).get("pieces"),
                            "pieces": board.get("pieces"), "agents": board.get("agents")})
        self.assertNotIn("Planner model rule overridden", names)
        trace = self.fixture("other") / "trace.jsonl"
        with trace.open("a") as stream:
            rows = [
                {"v": 1, "span_id": "x9-label", "ts": "2026-01-10T14:36:20Z",
                 "start": "2026-01-10T14:36:20Z", "kind": "agent_call",
                 "actor": "investigator", "call": "X9.investigator.2", "node": "X9",
                 "node_label": "Look into the incident", "status": "running"},
                {"v": 1, "span_id": "x9-note", "ts": "2026-01-10T14:36:30Z",
                 "kind": "event", "actor": "orchestrator", "node": "X9",
                 "node_label": "A note", "status": "done", "plain": "A note was recorded."},
                {"v": 1, "span_id": "y8", "ts": "2026-01-10T14:36:40Z",
                 "start": "2026-01-10T14:36:40Z", "kind": "agent_call",
                 "actor": "investigator", "call": "Y8.investigator.1", "node": "Y8",
                 "status": "running"},
            ]
            for row in rows:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        with mock.patch.dict(os.environ, self.env, clear=False):
            changed = lib.board(self.fixture("other"), now_value="2026-01-10T14:37:00Z")
        self.assertEqual(self.piece(changed, "X9").get("name"), "Look into the incident")
        self.assertTrue(changed["owner"].get("sentence", "").endswith(" 2 other tasks running."))


class TonightModelAndDocsTests(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.env["TZ"] = "America/New_York"
        self.env["FACTORY_OSASCRIPT_BIN"] = str(self.fake_program(
            "fake-osascript", "import sys; sys.exit(99)",
        ))

    def test_T_TN_13_model_family_is_deterministic(self):
        """T-TN-13: model_family identifies vendors from runner and model names."""
        lib = self.require_module("factorylib")
        self.assertTrue(hasattr(lib, "model_family"),
                        "planned function missing: factorylib.model_family")
        cases = (
            (("claude", "fable-5-2"), "anthropic"),
            (("codex", "gpt-5.6-sol"), "openai"),
            (("opencode", "opencode/deepseek-v4.1-flash-free"), "deepseek"),
            (("ollama", "qwen3:14b"), "qwen"),
            (("opencode", "openrouter/anthropic/claude-x"), "anthropic"),
            (("cursor", "gpt-5.6"), "openai"),
            (("cursor", "grok-4"), "grok"),
            (("cursor", None), "unknown"),
            (("opencode", "opencode/jev-1.13-free"), "jev"),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                self.assertEqual(lib.model_family(*args), expected)

    def config_error(self, lib, value):
        write_json(self.project / "factory.json", value)
        with mock.patch.dict(os.environ, self.env, clear=False):
            try:
                lib.load_config(self.project)
            except lib.FactoryError as exc:
                return exc.line()
        return ""

    def test_T_TN_14_outside_roles_cannot_fall_back_to_maker_company(self):
        """T-TN-14: merged settings reject same-company and unknown outside models."""
        lib = self.require_module("factorylib")
        example = json.loads((KIT_DIR / "factory.example.json").read_text())
        write_json(self.project / "factory.json", example)
        good = self.run_factory("status", "--all")
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        with mock.patch.dict(os.environ, self.env, clear=False):
            lib.load_config(self.project)
        bad_shape = dict(example)
        bad_shape["roles"] = 5
        write_json(self.project / "factory.json", bad_shape)
        shape_code = self.run_factory("status", "--all").returncode
        self.assertEqual(shape_code, 2)
        cases = []
        same_fallback = json.loads(json.dumps(example))
        same_fallback["roles"]["test-writer"]["fallback"] = [
            {"runner": "claude", "model": "haiku-5-5"},
        ]
        cases.append((same_fallback,
            '"roles.test-writer.fallback" names claude haiku-5-5, from the same company as the maker (anthropic). This role must come from another company. Use another model or remove it.'))
        same_role = json.loads(json.dumps(example))
        same_role["roles"]["final-reviewer"] = {"runner": "claude", "model": "opus-5-5"}
        cases.append((same_role,
            '"roles.final-reviewer" names claude opus-5-5, from the same company as the maker (anthropic). This role must come from another company. Use another model or remove it.'))
        unknown = json.loads(json.dumps(example))
        unknown["roles"]["plan-reviewer"]["fallback"] = [{"runner": "cursor", "model": ""}]
        cases.append((unknown,
            '"roles.plan-reviewer.fallback" names cursor (no model), and the kit cannot tell which company made it. Name the model.'))
        openai_maker = json.loads(json.dumps(example))
        openai_maker["roles"]["maker"] = {"runner": "codex", "model": "gpt-5.6-sol"}
        cases.append((openai_maker, "codex gpt-5.6-sol"))
        for value, message in cases:
            with self.subTest(message=message):
                write_json(self.project / "factory.json", value)
                command = self.run_factory("status", "--all")
                self.assertEqual(
                    command.returncode, shape_code,
                    "planned outside-company settings check did not reject the value: "
                    + command.stdout + command.stderr,
                )
                self.assertIn(message, command.stderr)
                loaded_error = self.config_error(lib, value)
                self.assertTrue(loaded_error, "planned merged settings check did not reject the value")
                self.assertIn(message, loaded_error)
                if value is openai_maker:
                    self.assertIn("(openai)", loaded_error)

    def test_T_TN_15_example_settings_have_outside_fallbacks(self):
        """T-TN-15: examples parse and keep every outside fallback outside the maker company."""
        lib = self.require_module("factorylib")
        self.assertTrue(hasattr(lib, "model_family"),
                        "planned function missing: factorylib.model_family")
        example = json.loads((KIT_DIR / "factory.example.json").read_text())
        machine = json.loads((KIT_DIR / "machine.example.json").read_text())
        fallback = [
            {"runner": "opencode", "model": "opencode/deepseek-v4.1-flash-free"},
            {"runner": "ollama", "model": "qwen3:14b"},
        ]
        for role in ("plan-reviewer", "test-writer", "final-reviewer"):
            entry = example.get("roles", {}).get(role, {})
            self.assertEqual(entry.get("runner"), "codex")
            self.assertEqual(entry.get("fallback"), fallback)
        for role in getattr(lib, "OUTSIDE_ROLES", ()):
            entry = example.get("roles", {}).get(role)
            if not entry:
                continue
            candidates = [entry] + list(entry.get("fallback", []))
            self.assertNotIn("anthropic", [lib.model_family(item.get("runner"), item.get("model"))
                                            for item in candidates])
        self.assertEqual(example.get("roles", {}).get("planner", {}).get("effort"), "medium")
        self.assertEqual(machine.get("roles", {}).get("planner", {}).get("effort"), "medium")

    @staticmethod
    def json_block_after(text, label):
        lines = text.splitlines()
        try:
            start = next(index for index, line in enumerate(lines) if label in line)
            fence = next(index for index in range(start + 1, len(lines))
                         if lines[index].strip() in ("```json", "```"))
            end = next(index for index in range(fence + 1, len(lines))
                       if lines[index].strip() == "```")
        except StopIteration:
            raise AssertionError("planned README JSON block missing after: %s" % label)
        return json.loads("\n".join(lines[fence + 1:end]))

    def test_T_TN_16_ready_config_blocks_load_and_stay_outside(self):
        """T-TN-16: the Claude-only and Codex-only README blocks load over the example."""
        lib = self.require_module("factorylib")
        self.assertTrue(hasattr(lib, "model_family"),
                        "planned function missing: factorylib.model_family")
        text = (KIT_DIR / "README.md").read_text()
        example = json.loads((KIT_DIR / "factory.example.json").read_text())
        cases = (("Only Claude Code", "anthropic", ["claude", "opencode"]),
                 ("Only Codex", "openai", ["codex", "opencode"]))
        for label, maker_family, vendors in cases:
            with self.subTest(label=label):
                block = self.json_block_after(text, label)
                merged = lib.deep_merge(example, block)
                write_json(self.project / "factory.json", merged)
                with mock.patch.dict(os.environ, self.env, clear=False):
                    loaded = lib.load_config(self.project)[0]
                maker = loaded["roles"]["maker"]
                self.assertEqual(lib.model_family(maker.get("runner"), maker.get("model")),
                                 maker_family)
                for role in lib.OUTSIDE_ROLES:
                    entry = loaded.get("roles", {}).get(role)
                    if entry:
                        self.assertNotEqual(lib.model_family(entry.get("runner"), entry.get("model")),
                                            maker_family)
                self.assertEqual(loaded.get("vendors", {}).get("required"), vendors)

    def test_T_TN_17_readme_has_ordered_setup_guide_and_known_commands(self):
        """T-TN-17: README contains the complete setup path and only real factory commands."""
        text = (KIT_DIR / "README.md").read_text()
        headings = (
            "## Install", "## Set up your models", "### 1. Sign in to one main tool",
            "### 2. Add free models with OpenCode (no key)",
            "### 3. Optional: an OpenRouter key",
            "### 4. Optional: local models with Ollama",
            "### 5. Tell the kit what you have", "### Who does what", "## How a run goes",
        )
        positions = []
        for heading in headings:
            self.assertTrue(heading in text, "planned README heading missing: " + heading)
            positions.append(text.index(heading))
        self.assertEqual(positions, sorted(positions))
        for value in ("codex login", "opencode models", "opencode auth login",
                      "ollama pull qwen3:14b", "factory preflight", "--non-private",
                      'See "Set up your models" below if you have only one of them.'):
            self.assertIn(value, text)
        self.assertNotIn("\u2014", text)
        help_result = self.run_factory("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        known = set(re.findall(r"^  ([a-z][a-z0-9-]*)\s", help_result.stdout, re.M))
        documented = set(re.findall(r"\bfactory\s+([a-z][a-z0-9-]*)", text))
        self.assertFalse(documented - known, "README names unknown commands: %s" %
                         sorted(documented - known))

    def test_T_TN_18_who_does_what_table_is_exact(self):
        """T-TN-18: the README model table has five jobs and the honest enforcement note."""
        text = (KIT_DIR / "README.md").read_text()
        self.assertTrue("### Who does what" in text,
                        "planned README heading missing: ### Who does what")
        section = text.split("### Who does what", 1)[1]
        rows = []
        for line in section.splitlines():
            if line.startswith("### ") or line.startswith("## "):
                break
            if line.lstrip().startswith("|"):
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                if cells and not all(set(cell) <= {"-", ":"} for cell in cells):
                    rows.append(cells)
        self.assertGreaterEqual(len(rows), 6, "planned Who does what table missing")
        self.assertEqual(rows[0][-1], "Does the kit enforce it today?")
        data = rows[1:]
        self.assertEqual(len(data), 5)
        self.assertEqual([row[0] for row in data], [
            "Planning", "Building", "Checking by another company", "Quick decisions",
            "Routine work: summaries, formatting",
        ])
        self.assertIn("medium", data[0])
        self.assertIn("On trust", data[0])
        checking = " | ".join(data[2])
        self.assertIn("Never the builder's company", checking)
        self.assertIn("stop and ask the owner", checking)
        paragraph = ("Today the kit checks your settings and tests that each model answers. "
                     "It does not choose the model when an agent starts: the session that starts "
                     "the agent types it. So the split above is on trust until the model picker ships.")
        self.assertIn(paragraph, section)

    def test_T_TN_19_docs_cover_finish_fallbacks_and_medium_planning(self):
        """T-TN-19: all three docs carry finish and the outside-fallback rule."""
        readme, skill, process = [path.read_text() for path in DOCS]
        self.assertTrue("`status`, `dashboard`, `finish`," in readme,
                        "planned README Commands text missing dashboard and finish")
        self.assertTrue("`status`, `dashboard`, `finish`, `preflight`" in readme,
                        "planned README run command list missing dashboard and finish")
        self.assertIn(
            "`factory finish` marks the build finished. It refuses while a call or a piece is still open, "
            "unless you give a reason for each one. Until then the board never says \"Finished\".",
            readme,
        )
        self.assertIn("factory finish           mark the build finished", skill)
        fallback = ("If a model fails mid-build, switch to its configured fallback and log the swap with "
                    "`factory log event`. For the outside roles (plan reviewer, test writer, stuck diagnosis, "
                    "final reviewer) the fallback is always a model from another company than the maker. "
                    "When none is left, stop and ask the owner with `factory gate open`. Never switch to the "
                    "maker's company on your own. [on trust] The settings check refuses a same-company "
                    "fallback for these roles. [enforced by code]")
        self.assertIn(fallback, skill)
        self.assertNotIn("log the swap with `factory log event`. Models that may keep data", skill)
        for text in (skill, process):
            self.assertIn("Last step: run `factory finish`. [on trust]", text)
        self.assertIn("Strongest model available, medium effort. [on trust]", process)
        self.assertNotIn("Highest effort setting.", process)

    def test_T_TN_22_on_trust_labels_cover_every_listed_rule(self):
        """T-TN-22: every manually governed sentence has the exact on-trust tag."""
        readme, skill, process = [path.read_text() for path in DOCS]
        exact = {
            readme: (
                "Keeps maker and checker apart, and asks a different vendor to review the plan and the final diff.",
                "Makers cannot change them.",
                "Nothing is pushed, published or merged before then.",
            ),
            skill: (
                "A reviewer from a different vendor than the maker reads the plan.",
                "Locked tests are read-only for makers.",
                "Only after GATE B is answered yes.",
            ),
            process: (
                "A test writer from a different vendor writes them as code.",
                "The same rubric item fails twice: a second vendor diagnoses before the next try.",
                "Raw log lines never go into a model prompt.",
            ),
        }
        for text, sentences in exact.items():
            for sentence in sentences:
                with self.subTest(sentence=sentence):
                    self.assertTrue(sentence + " [on trust]" in text,
                                    "listed rule is missing its [on trust] tag: " + sentence)
        self.assertEqual(skill.count("Maker and checker are never the same session. [on trust]"), 2)
        skill_starts = (
            "A fresh test writer session, on a different vendor than the maker,",
            "Breakers:", "One review of the full diff comes from a different vendor than the maker",
            "Whenever any agent is running", "Eval files hold known answers",
            "Every agent dispatch gets a call id", "`factory check` runs before each gate",
            "Project commands run through", "Raw log lines never go into a model prompt",
            "Any script whose output feeds", "Never delete or overwrite an existing file",
            "Nothing is pushed, published or merged before GATE B",
        )
        for start in skill_starts:
            line = next((line for line in skill.splitlines() if line.lstrip(" -*").startswith(start)), "")
            self.assertTrue(line, "listed SKILL rule missing: " + start)
            self.assertIn("[on trust]", line, "listed SKILL rule is untagged: " + line)
        for role in ("Orchestrator", "Planner", "Plan reviewer", "Test writer", "Maker",
                     "Checker", "Stuck diagnosis", "Final reviewer"):
            line = next((line for line in process.splitlines() if line.startswith("| " + role + " |")), "")
            self.assertTrue(line, "PROCESS role row missing: " + role)
            self.assertRegex(line, r"\[on trust\]\s*\|\s*$")
        for text in (readme, skill, process):
            for match in re.finditer(r"\[(?:enforced[^\]]*|on trust[^\]]*)\]", text):
                self.assertIn(match.group(0), ("[enforced by code]", "[on trust]"))

    def test_T_TN_23_known_limits_has_proved_and_on_trust_rules(self):
        """T-TN-23: Known limits links enforced claims to tests and lists trust rules exactly."""
        readme = (KIT_DIR / "README.md").read_text()
        self.assertIn("## Known limits", readme)
        known = readme.split("## Known limits", 1)[1]
        enforced_at = known.find("### Rules the code enforces")
        trust_at = known.find("### Rules on trust")
        self.assertGreaterEqual(enforced_at, 0, "planned heading missing: Rules the code enforces")
        self.assertGreater(trust_at, enforced_at, "Rules on trust must follow enforced rules")
        item6 = ("6. The dashboard is read-only and local. It cannot answer decisions, it cannot be reached "
                 "from another computer, and it checks for changes every few seconds rather than instantly. "
                 "`factory status` shows the same board in a terminal.")
        self.assertIn(item6, known[:enforced_at])
        trust_rules = (
            "1. A model from a different company than the maker reviews the plan, writes the tests, diagnoses stuck pieces and reviews the final change. The settings check refuses a same-company fallback, but the kit does not pick or verify the model that really ran.",
            "2. Maker and checker are never the same session.",
            "3. Makers cannot change locked tests. `TESTLOCK` is a record, not a lock.",
            "4. Nothing is pushed, published or merged before GATE B.",
            "5. Breakers fire when a piece is stuck. They are computed by the orchestrator, not by the kit.",
            "6. A maker gets a small packet and never the whole plan.",
            "7. A wait timer runs whenever an agent runs.",
            "8. Raw log lines never go into a model prompt.",
            "9. Nothing that existed before the build is deleted or overwritten.",
            "10. `factory check` runs before each gate, and project commands run only through `factory step`.",
            "11. The model each role uses is the one in your settings. The command that starts an agent takes whatever model is typed.",
            "12. `factory finish` is run at the end. Until it is, the board says the build is not closed.",
        )
        for rule in trust_rules:
            self.assertIn(rule, known[trust_at:])
        rows = []
        for line in known[enforced_at:trust_at].splitlines():
            if line.startswith("|"):
                cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
                if len(cells) >= 2 and cells[0] not in ("Rule", "---") and set(cells[0]) != {"-"}:
                    rows.append(cells)
        self.assertGreaterEqual(len(rows), 3)
        source = "\n".join(path.read_text(errors="replace")
                           for path in sorted((KIT_DIR / "tests").rglob("*.py")))
        for row in rows:
            self.assertIn("def %s(" % row[1], source,
                          "enforced rule names no real unittest function: " + row[1])
        tags = sum(path.read_text().count("[enforced by code]") for path in DOCS)
        self.assertLessEqual(tags, 3 * len(rows))

    @staticmethod
    def untagged_rule_lines(text):
        phrases = (
            "different vendor", "another vendor", "second vendor", "same session",
            "Makers cannot", "read-only for makers", "read-only inputs for makers",
            "pushed, published or merged", "Never delete or overwrite", "never the whole plan",
            "Never sees the whole plan", "Raw log lines never",
        )
        in_trust = False
        bad = []
        for number, line in enumerate(text.splitlines(), 1):
            if line.strip() == "### Rules on trust":
                in_trust = True
                continue
            if in_trust and line.startswith("### "):
                in_trust = False
            exempt = in_trust and re.match(r"^\d+\. ", line)
            if not exempt and any(phrase in line for phrase in phrases):
                if "[on trust]" not in line and "[enforced by code]" not in line:
                    bad.append("line %d: %s" % (number, line))
        return bad

    def test_T_TN_24_rule_phrase_lint_bites(self):
        """T-TN-24: governance phrases require a trust or code-enforcement label."""
        for path in DOCS:
            bad = self.untagged_rule_lines(path.read_text())
            self.assertEqual(bad, [], "%s has untagged rule lines:\n%s" %
                             (path.name, "\n".join(bad)))
        mutation = (KIT_DIR / "README.md").read_text() + "\nMakers cannot change locked tests.\n"
        mutation_bad = self.untagged_rule_lines(mutation)
        self.assertTrue(mutation_bad, "rule lint did not reject an untagged added sentence")
        self.assertIn("Makers cannot change locked tests.", "\n".join(mutation_bad))
        mutated = (KIT_DIR / "README.md").read_text() + "\nMakers cannot change locked tests.\n"
        bad = self.untagged_rule_lines(mutated)
        self.assertTrue(bad, "rule phrase lint did not reject an untagged sentence")
        self.assertIn("Makers cannot change locked tests.", "\n".join(bad))


class TonightSafeTextTests(TonightFixtureCase):
    FORBIDDEN = (
        "innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
        "new Function", "createContextualFragment", "DOMParser", "srcdoc", "cssText",
        "javascript:", "window.open", "location.href =", "location.assign",
        "setAttribute('style'", 'setAttribute("style"',
    )

    def lint_dashboard_text(self, app_text, index_text):
        problems = []
        for name, text in (("app.js", app_text), ("index.html", index_text)):
            for token in self.FORBIDDEN:
                if token in text:
                    problems.append("%s contains %s" % (name, token))
        literals = []
        for call in re.finditer(r"\.setAttribute\(\s*([^,]+)", app_text):
            prefix = app_text[max(0, call.start() - 100):call.start()]
            if (call.group(1).strip() == "name" and
                    re.search(r"function\s+attr\s*\(\s*n\s*,\s*name\s*,\s*value\s*\)\s*\{[^{}]*$",
                              prefix)):
                continue
            literals.append((call.group(0), call.group(1).strip()))
        for call in re.finditer(r"\battr\(\s*([^,]+),\s*([^,]+)", app_text):
            prefix = app_text[max(0, call.start() - 12):call.start()]
            if re.search(r"function\s*$", prefix):
                continue
            literals.append((call.group(0), call.group(2).strip()))
        for source, literal in literals:
            match = re.fullmatch(r"(['\"])([^'\"]+)\1", literal)
            if not match:
                problems.append("attribute name is not a string literal: " + source)
                continue
            name = match.group(2).lower()
            if name in {"href", "src", "action", "formaction", "style"} or name.startswith("on"):
                problems.append("unsafe attribute name: " + name)
        return problems

    def test_T_TN_20_dashboard_text_sink_lint_rejects_dynamic_markup(self):
        """T-TN-20: dashboard files have no markup sinks or dynamic attribute names."""
        folder = KIT_DIR / "dashboard"
        self.assertTrue(folder.is_dir(), "planned page missing: skills/factory/dashboard/")
        app = folder / "app.js"
        index = folder / "index.html"
        self.assertTrue(app.is_file(), "planned page element source missing: dashboard/app.js")
        self.assertTrue(index.is_file(), "planned page element source missing: dashboard/index.html")
        self.assertEqual(self.lint_dashboard_text(app.read_text(), index.read_text()), [])
        self.assertTrue(self.lint_dashboard_text("el.setAttribute(name, value)", ""),
                        "lint accepted a dynamic attribute name")
        self.assertTrue(self.lint_dashboard_text("el.innerHTML = x", ""),
                        "lint accepted an HTML sink")

    def load_server(self):
        path = KIT_DIR / "dashboard" / "server.py"
        self.assertTrue(path.is_file(),
                        "module not found: planned module skills/factory/dashboard/server.py")
        spec = importlib.util.spec_from_file_location("tonight_dashboard_server", str(path))
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.addCleanup(lambda: sys.path.remove(str(SCRIPTS_DIR)))
        with mock.patch.dict(os.environ, self.env, clear=False):
            spec.loader.exec_module(module)
        return module

    def serve_in_thread(self):
        server = self.load_server()
        with mock.patch.dict(os.environ, self.env, clear=False):
            httpd, _port = server.bind(0, tries=1)
        thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05},
                                  daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return httpd

    def test_T_TN_21_api_escapes_every_hostile_log_value(self):
        """T-TN-21: API JSON has no raw markup while parsed values remain exact."""
        httpd = self.serve_in_thread()
        port = httpd.server_address[1]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.9)
        self.addCleanup(connection.close)
        connection.request("GET", "/api/factory?build=tn%2Fhostile")
        response = connection.getresponse()
        body = response.read()
        self.assertEqual(response.status, 200)
        self.assertNotIn(b"<", body)
        self.assertNotIn(b">", body)
        self.assertNotIn(b"&", body)
        parsed = json.loads(body.decode("utf-8"))
        strings = []

        def collect_strings(value):
            if isinstance(value, dict):
                for child in value.values():
                    collect_strings(child)
            elif isinstance(value, list):
                for child in value:
                    collect_strings(child)
            elif isinstance(value, str):
                strings.append(value)

        collect_strings(parsed)
        self.assertTrue(any("<img" in value for value in strings))
        for tag in HOSTILE_TAGS:
            self.assertTrue(any(tag in value for value in strings), tag)
        self.assertTrue(any(IMAGE_MARKER in value for value in strings))
        self.assertTrue(any(SCRIPT_MARKER in value for value in strings))
        self.assertEqual(response.getheader("Content-Type"), "application/json; charset=utf-8")
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")


if __name__ == "__main__":
    import unittest
    unittest.main()
