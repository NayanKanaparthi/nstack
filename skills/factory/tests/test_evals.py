"""Deterministic acceptance tests for factory-v1.1 evals (T-EVAL-01..47).

These tests intentionally precede the implementation.  While ``scripts/evals.py``
is absent, every case stops at ``require_module`` with a planned-module failure;
the assertions below become the executable contract once the module is added.
"""

import ast
import copy
import io
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path
from unittest import mock

from tests.common import (
    DEFAULT_PROJECT_CONFIG, FACTORY_PY, FIXTURES, KIT_DIR, PYTHON, SCRIPTS_DIR,
    FactoryTestCase, read_jsonl, tree_snapshot, write_json, write_jsonl,
)


EVAL_FIXTURES = FIXTURES / "evals"
RESULT_KEYS = {
    "id", "pass", "reason", "input", "expected", "output", "exit_code",
    "time_s", "cost", "tags",
}
SUMMARY_KEYS = {
    "set", "name", "ts", "tags", "n", "passed", "accuracy", "time_p50_s",
    "time_p95_s", "cost_total", "cost_per_example", "cost_unit", "by_tag",
    "failed", "targets", "met", "results_file",
}


class EvalTestCase(FactoryTestCase):
    """Small builders shared by command cases; all paths remain in the temp tree."""

    def require_evals(self):
        return self.require_module("evals")

    def install_suts(self):
        bindir = self.project / "bin"
        bindir.mkdir(exist_ok=True)
        for name in ("fake_sut.py", "echo_sut.py", "shout.py"):
            shutil.copy2(str(EVAL_FIXTURES / name), str(bindir / name))
        return bindir

    def eval_set(self, set_id="greet", name="Greeting answers", file_name=None,
                 cmd=None, timeout=0.9, scorer=None, targets=None):
        return {
            "id": set_id,
            "name": name,
            "file": file_name or "evals/%s.jsonl" % set_id,
            "cmd": cmd or "%s bin/fake_sut.py" % PYTHON,
            "example_timeout_s": timeout,
            "scorer": scorer or {"type": "exact"},
            "targets": targets or {"accuracy": ">=0.5"},
        }

    def configure(self, sets=None, cost_unit=None, improve=None, folder=None):
        folder = Path(folder or self.project)
        value = copy.deepcopy(DEFAULT_PROJECT_CONFIG)
        value["project"] = "toy"
        value["timers"]["kill_grace_s"] = 0.1
        value["evals"] = {"metrics": [], "sets": sets or [self.eval_set()]}
        if cost_unit is not None:
            value["evals"]["cost_unit"] = cost_unit
        if improve is not None:
            value["evals"]["improve"] = improve
        write_json(folder / "factory.json", value)
        return value

    def write_examples(self, rows, file_name="greet.jsonl", folder=None):
        root = Path(folder or self.project) / "evals"
        root.mkdir(parents=True, exist_ok=True)
        write_jsonl(root / file_name, rows)
        return root / file_name

    def write_table(self, value, name="table.json"):
        path = self.project / name
        write_json(path, value)
        self.env["FAKE_TABLE"] = str(path)
        return path

    def new_build(self, build="b1"):
        result = self.run_factory("new", build, "--title", "Eval test", "--stop", "GATE B=23:59")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return Path(self.env["FACTORY_HOME"]) / "runs" / "toy" / build

    def close_build(self, build):
        feature = next(x for x in read_jsonl(build / "trace.jsonl")
                       if x.get("kind") == "feature" and x.get("status") == "running")
        result = self.run_factory("log", "end", feature["span_id"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def command_fixture(self, rows=None, table=None, sets=None, build=True,
                        cost_unit=None, improve=None):
        self.install_suts()
        self.configure(sets=sets, cost_unit=cost_unit, improve=improve)
        self.write_examples(rows or [{"id": "e1", "input": "x", "expected": "x"}])
        self.write_table(table or {"e1": {"out": "x"}})
        return self.new_build() if build else None

    def latest(self, build, set_id="greet"):
        entries = [x for x in read_jsonl(build / "evals" / "index.jsonl")
                   if x["set"] == set_id]
        self.assertTrue(entries)
        entry = entries[-1]
        summary = json.loads((build / "evals" / entry["summary"]).read_text())
        rows = read_jsonl(build / "evals" / entry["file"])
        return entry, summary, rows

    def result(self, rows=None, table=None, sets=None, *args, **kwargs):
        build = self.command_fixture(rows=rows, table=table, sets=sets,
                                     cost_unit=kwargs.pop("cost_unit", None),
                                     improve=kwargs.pop("improve", None))
        result = self.run_factory("eval", "run", "greet", *args, env=kwargs.pop("env", None))
        self.assertFalse(kwargs)
        return build, result, self.latest(build)

    def seed_summary(self, build, set_id, summary, stamp="20261125T180000Z"):
        eval_dir = build / "evals"
        eval_dir.mkdir(parents=True, exist_ok=True)
        name = "%s-%s.json" % (set_id, stamp)
        value = dict(summary)
        value.setdefault("set", set_id)
        value.setdefault("name", set_id)
        value.setdefault("ts", "2026-11-25T18:00:00Z")
        value.setdefault("tags", [])
        value.setdefault("cost_unit", "USD")
        value.setdefault("by_tag", {})
        value.setdefault("failed", [])
        value.setdefault("results_file", name[:-5] + ".jsonl")
        write_json(eval_dir / name, value)
        with (eval_dir / "index.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"ts": value["ts"], "set": set_id,
                                     "file": value["results_file"], "summary": name,
                                     "met": value["met"]}, sort_keys=True) + "\n")

    def git_env(self):
        empty = self.tmp / "empty-gitconfig"
        empty.write_text("")
        env = dict(self.env)
        env.update({
            "GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_SYSTEM": str(empty),
            "GIT_AUTHOR_NAME": "Eval Test", "GIT_AUTHOR_EMAIL": "eval.invalid",
            "GIT_COMMITTER_NAME": "Eval Test", "GIT_COMMITTER_EMAIL": "eval.invalid",
        })
        return env

    def git(self, *args, cwd=None, env=None):
        git_bin = shutil.which("git")
        self.assertIsNotNone(git_bin, "planned test dependency missing: git")
        result = subprocess.run([git_bin] + list(args), cwd=str(cwd or self.project),
                                env=env or self.git_env(), stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=0.95)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def init_git(self, tracked=True):
        env = self.git_env()
        self.git("init", cwd=self.project, env=env)
        if tracked:
            self.git("add", "factory.json", "evals", "bin", cwd=self.project, env=env)
            self.git("commit", "-m", "baseline", cwd=self.project, env=env)
        self.env.update({key: env[key] for key in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
                                                    "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
                                                    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")})
        return env


class EvalSettingsAndFileTests(EvalTestCase):
    def test_T_EVAL_01_valid_settings_load(self):
        """T-EVAL-01: valid settings are known; show distinguishes no run and unknown set."""
        self.require_evals()
        self.command_fixture()
        known = self.run_factory("eval", "show", "greet")
        self.assertEqual(known.returncode, 4)
        self.assertEqual(known.stderr, "factory: no eval run recorded for 'greet' in this build.\n")
        unknown = self.run_factory("eval", "show", "nope")
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("greet", unknown.stderr)
        self.assertNotIn("Traceback", unknown.stderr)

    def test_T_EVAL_02_invalid_settings(self):
        """T-EVAL-02: every invalid eval setting is a clean exit 2 naming file and key."""
        self.require_evals()
        base = self.eval_set()
        cases = []
        for value in (None, 0, -1, "5", True):
            item = copy.deepcopy(base)
            if value is None:
                item.pop("example_timeout_s")
            else:
                item["example_timeout_s"] = value
            cases.append((item, "example_timeout_s"))
        item = copy.deepcopy(base); item["scorer"] = {"type": "llm"}; cases.append((item, "scorer.type"))
        item = copy.deepcopy(base); item["targets"] = {}; cases.append((item, "targets"))
        for key in ("recall", "passed", "p50_s"):
            item = copy.deepcopy(base); item["targets"] = {key: ">=0.5"}; cases.append((item, key))
        for target in ("0.5", ">= x", ">=90"):
            item = copy.deepcopy(base); item["targets"] = {"accuracy": target}; cases.append((item, "accuracy"))
        item = copy.deepcopy(base); item["id"] = "a b"; cases.append((item, "id"))
        item = copy.deepcopy(base); item["id"] = "a" * 65; cases.append((item, "id"))
        for key in ("cmd", "file"):
            item = copy.deepcopy(base); item.pop(key); cases.append((item, key))
        for scorer, key in (({"type": "number", "tol": -1}, "tol"),
                            ({"type": "number", "rel": "x"}, "rel"),
                            ({"type": "number", "tol": True}, "tol"),
                            ({"type": "exact", "normalize": "no"}, "normalize")):
            item = copy.deepcopy(base); item["scorer"] = scorer; cases.append((item, key))
        for name in ("", "n" * 61, "bad\nname"):
            item = copy.deepcopy(base); item["name"] = name; cases.append((item, "name"))
        for index, (item, key) in enumerate(cases):
            with self.subTest(index=index, key=key):
                folder = self.tmp / ("bad-%02d" % index); folder.mkdir()
                self.configure([item], folder=folder)
                result = self.run_factory("eval", "show", "greet", cwd=folder)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("factory.json", result.stderr)
                self.assertIn(key.split(".")[-1], result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        duplicate = self.tmp / "duplicate"; duplicate.mkdir()
        self.configure([base, copy.deepcopy(base)], folder=duplicate)
        result = self.run_factory("eval", "show", "greet", cwd=duplicate)
        self.assertEqual(result.returncode, 2)
        self.assertIn("id", result.stderr)
        for index, unit in enumerate(("", "US D", "123456789", 5)):
            folder = self.tmp / ("unit-%d" % index); folder.mkdir()
            self.configure(folder=folder, cost_unit=unit)
            result = self.run_factory("eval", "show", "greet", cwd=folder)
            self.assertEqual(result.returncode, 2)
            self.assertIn("cost_unit", result.stderr)
        accepted = copy.deepcopy(base); accepted["scorer"]["foo"] = 1
        self.configure([accepted]); self.new_build("accepted")
        result = self.run_factory("eval", "show", "greet")
        self.assertEqual(result.returncode, 4, result.stderr)

    def test_T_EVAL_03_example_machine_and_missing_script(self):
        """T-EVAL-03: shipped defaults, project-only machine keys, dispatch, and usage."""
        self.require_evals()
        example = json.loads((KIT_DIR / "factory.example.json").read_text())
        self.assertEqual(example["evals"]["sets"], [])
        init_dir = self.tmp / "init"; init_dir.mkdir()
        result = self.run_factory("init", "--project", "toy", cwd=init_dir)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_factory("eval", "show", "x", cwd=init_dir)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("settings", result.stderr.lower())

        self.configure([self.eval_set("project")])
        machine = copy.deepcopy(DEFAULT_PROJECT_CONFIG)
        machine["evals"] = {"sets": [self.eval_set()], "improve": {"max_rounds": 1}}
        write_json(self.factory_home / "config.json", machine)
        preflight = self.run_factory("preflight", "--only", "config", "--json")
        self.assertIn("project", preflight.stdout.lower() + preflight.stderr.lower())
        self.assertIn("evals", preflight.stdout.lower() + preflight.stderr.lower())
        ignored = self.run_factory("eval", "show", "greet")
        self.assertEqual(ignored.returncode, 2)

        scripts = self.tmp / "scripts"; scripts.mkdir()
        for source in SCRIPTS_DIR.glob("*.py"):
            if source.name != "evals.py":
                shutil.copy2(str(source), str(scripts / source.name))
        missing = subprocess.run([PYTHON, str(scripts / "factory.py"), "eval", "show", "greet"],
                                 cwd=str(self.project), env=self.env, stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=0.95)
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(missing.stderr,
                         "factory: 'eval' is not installed (missing scripts/evals.py)\n")
        usage = self.run_factory("eval", "frob")
        self.assertEqual(usage.returncode, 2)
        for phrase in ("eval run", "eval show", "eval diagnose", "eval improve"):
            self.assertIn(phrase, usage.stderr)

    def test_T_EVAL_04_malformed_files(self):
        """T-EVAL-04: malformed JSONL stops before execution and logs one plain error."""
        self.require_evals()
        build = self.command_fixture()
        fake_log = self.tmp / "fake.log"; self.env["FAKE_LOG"] = str(fake_log)
        cases = [
            ('{"id":"a","input":"x","expected":"y"}\n{bad\n', 2, "not valid JSON"),
            ('{"id":"a","input":NaN,"expected":"y"}\n', 1, "not valid JSON"),
            ('[1,2]\n', 1, "not an object"),
            ('{"input":"x","expected":"y"}\n', 1, "missing id"),
            ('{"id":"","input":"x","expected":"y"}\n', 1, "missing id"),
            ('{"id":"a b","input":"x","expected":"y"}\n', 1, "bad id"),
            (json.dumps({"id": "sk-" + "a" * 24, "input": "x", "expected": "y"}) + "\n", 1, "bad id"),
            (json.dumps({"id": "a", "input": "x", "expected": "y", "tags": ["sk-" + "a" * 24]}) + "\n", 1, "bad tag"),
            (json.dumps({"id": "sk-" + "a" * 24 + "\n", "input": "x", "expected": "y"}) + "\n", 1, "bad id"),
            ('{"id":"a","expected":"y"}\n', 1, "missing input"),
            ('{"id":"a","input":"x"}\n', 1, "missing expected"),
            ('{"id":"a","input":"x","expected":"y"}\n' * 2, 2, "duplicate id a"),
            ('{"id":"a","input":"x","expected":"y","tags":"t"}\n', 1, "tags must be a list of strings"),
            ('{"id":"a","input":"x","expected":"y","tags":[1]}\n', 1, "tags must be a list of strings"),
            ('{"id":"a","input":"x","expected":"y","tags":["a b"]}\n', 1, "bad tag"),
        ]
        path = self.project / "evals" / "greet.jsonl"
        trace_before = (build / "trace.jsonl").read_bytes()
        for body, line, reason in cases:
            with self.subTest(reason=reason, line=line):
                path.write_text(body)
                errors = build / "log-errors.jsonl"
                count = len(read_jsonl(errors)) if errors.exists() else 0
                result = self.run_factory("eval", "run", "greet")
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(result.stderr,
                                 "factory: evals/greet.jsonl line %d: %s\n" % (line, reason))
                self.assertFalse(fake_log.exists() and fake_log.read_text())
                self.assertFalse((build / "evals").exists())
                self.assertEqual((build / "trace.jsonl").read_bytes(), trace_before)
                logged = read_jsonl(errors)
                self.assertEqual(len(logged), count + 1)
                self.assertEqual((logged[-1]["command"], logged[-1]["exit"]), ("eval", 2))

    def test_T_EVAL_05_no_examples(self):
        """T-EVAL-05: empty and blank-only eval files exit 4 without artifacts."""
        self.require_evals()
        build = self.command_fixture()
        path = self.project / "evals" / "greet.jsonl"
        trace = (build / "trace.jsonl").read_bytes()
        for body in ("", "\n  \n\t\n"):
            path.write_text(body)
            result = self.run_factory("eval", "run", "greet")
            self.assertEqual(result.returncode, 4)
            self.assertEqual(result.stderr,
                             "factory: evals/greet.jsonl has no examples. Nothing to run.\n")
            self.assertEqual((build / "trace.jsonl").read_bytes(), trace)
            self.assertFalse((build / "evals").exists())

    def test_T_EVAL_06_check_order_and_missing_things(self):
        """T-EVAL-06: settings, project, set, build, then file determine the first error."""
        self.require_evals()
        self.install_suts(); self.configure(); self.write_table({"e1": {"out": "x"}})
        no_build_unknown = self.run_factory("eval", "run", "nope")
        self.assertEqual(no_build_unknown.returncode, 2)
        self.assertIn("greet", no_build_unknown.stderr)
        no_build = self.run_factory("eval", "run", "greet")
        self.assertEqual(no_build.returncode, 3)
        self.assertTrue(no_build.stderr.startswith("factory: no build selected."))
        self.new_build()
        missing = self.run_factory("eval", "run", "greet")
        self.assertEqual(missing.returncode, 3)
        self.assertIn("evals/greet.jsonl", missing.stderr)
        outside = self.tmp / "outside"; outside.mkdir()
        result = self.run_factory("eval", "run", "greet", cwd=outside)
        self.assertEqual(result.returncode, 3)
        bad = self.tmp / "bad-settings"; bad.mkdir(); (bad / "factory.json").write_text("{")
        result = self.run_factory("eval", "run", "nope", cwd=bad)
        self.assertEqual(result.returncode, 2)
        self.assertIn("factory.json", result.stderr)

    def test_T_EVAL_07_tolerant_reading(self):
        """T-EVAL-07: blank lines, unknown keys, absent tags, and empty tags are accepted."""
        self.require_evals()
        rows = [
            {"id": "e1", "input": "x", "expected": "x", "note": "hi"},
            {"id": "e2", "input": "y", "expected": "y"},
            {"id": "e3", "input": "z", "expected": "z", "tags": []},
        ]
        table = {key: {"out": value} for key, value in (("e1", "x"), ("e2", "y"), ("e3", "z"))}
        build = self.command_fixture(rows=rows, table=table)
        path = self.project / "evals" / "greet.jsonl"
        path.write_text("\n".join((json.dumps(rows[0]), "", json.dumps(rows[1]),
                                    "  ", json.dumps(rows[2]), "")))
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        _, summary, stored = self.latest(build)
        self.assertEqual(summary["n"], 3)
        self.assertTrue(all("note" not in row for row in stored))


class EvalRunnerAndScorerTests(EvalTestCase):
    def test_T_EVAL_08_string_input_untouched(self):
        """T-EVAL-08: string stdin has no added newline and Unicode survives."""
        self.require_evals()
        rows = [
            {"id": "e1", "input": "héllo wörld", "expected": "echo:héllo wörld"},
            {"id": "e2", "input": "", "expected": "echo:"},
            {"id": "e3", "input": "a\nb", "expected": "echo:a b"},
        ]
        setting = self.eval_set(cmd="%s bin/echo_sut.py" % PYTHON,
                                scorer={"type": "contains"})
        build = self.command_fixture(rows=rows, sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        _, summary, stored = self.latest(build)
        self.assertEqual(summary["passed"], 3)
        self.assertEqual(stored[0]["output"], "echo:héllo wörld")

    def test_T_EVAL_09_non_string_input_compact_json(self):
        """T-EVAL-09: non-string inputs use compact ensure-ascii-false JSON."""
        self.require_evals()
        values = [{"a": [1, 2], "b": "é"}, 42, None, True]
        rows = [{"id": "e%d" % i, "input": value, "expected": "echo:"}
                for i, value in enumerate(values, 1)]
        setting = self.eval_set(cmd="%s bin/echo_sut.py" % PYTHON,
                                scorer={"type": "contains"})
        build = self.command_fixture(rows=rows, sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        outputs = [row["output"] for row in self.latest(build)[2]]
        self.assertEqual(outputs, ['echo:{"a":[1,2],"b":"é"}', "echo:42", "echo:null", "echo:true"])

    def test_T_EVAL_10_environment_and_project_folder(self):
        """T-EVAL-10: eval id/set env and cwd are correct even from another cwd."""
        self.require_evals()
        build = self.command_fixture()
        fake_log = self.tmp / "fake.log"; self.env["FAKE_LOG"] = str(fake_log)
        elsewhere = self.tmp / "elsewhere"; elsewhere.mkdir()
        result = self.run_factory("eval", "run", "greet", cwd=elsewhere,
                                  env={"FACTORY_PROJECT": str(self.project)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        logged = read_jsonl(fake_log)[0]
        self.assertEqual(logged, {"id": "e1", "stdin": "x",
                                  "cwd": str(self.project.resolve()), "set": "greet"})
        self.assertTrue((build / "evals" / "index.jsonl").exists())

    def test_T_EVAL_11_output_trimming_empty_and_broken_pipe(self):
        """T-EVAL-11: one newline is trimmed; empty output and broken pipe are scored."""
        self.require_evals()
        rows = [
            {"id": "one", "input": "x", "expected": "x"},
            {"id": "two", "input": "x", "expected": "x"},
            {"id": "empty", "input": "x", "expected": ""},
            {"id": "nostdin", "input": "q" * 200000, "expected": "ok"},
        ]
        table = {"one": {"out": "x\n"}, "two": {"out": "x\n\n"},
                 "empty": {"out": ""}, "nostdin": {"no_stdin": True, "out": "ok"}}
        setting = self.eval_set(scorer={"type": "exact", "normalize": False})
        build = self.command_fixture(rows=rows, table=table, sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertIn(result.returncode, (0, 1))
        stored = {row["id"]: row for row in self.latest(build)[2]}
        self.assertEqual(stored["one"]["output"], "x")
        self.assertEqual(stored["two"]["output"], "x\n")
        self.assertEqual(stored["empty"]["output"], "")
        self.assertTrue(stored["one"]["pass"])
        self.assertFalse(stored["two"]["pass"])
        self.assertTrue(stored["empty"]["pass"])
        self.assertTrue(stored["nostdin"]["pass"])

    def test_T_EVAL_12_timeout_continues_and_kills_group(self):
        """T-EVAL-12: a 0.3-second timeout is recorded and later examples run."""
        self.require_evals()
        pidfile = self.tmp / "pid"
        rows = [{"id": key, "input": "x", "expected": "ok"} for key in ("e1", "e2", "e3")]
        table = {"e1": {"sleep": 5, "pidfile": str(pidfile), "out": "ok"},
                 "e2": {"out": "ok"}, "e3": {"out": "ok"}}
        setting = self.eval_set(timeout=0.3)
        build = self.command_fixture(rows=rows, table=table, sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        stored = self.latest(build)[2]
        self.assertEqual((stored[0]["pass"], stored[0]["reason"], stored[0]["exit_code"],
                          stored[0]["time_s"], stored[0]["output"]),
                         (False, "timed out after 0.3 s", None, 0.3, ""))
        self.assertTrue(stored[1]["pass"] and stored[2]["pass"])
        if pidfile.exists():
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pidfile.read_text()), 0)

    def test_T_EVAL_13_runner_errors_and_output_limit(self):
        """T-EVAL-13: exit, signal, command-not-found, and output cap are per-example failures."""
        self.require_evals()
        rows = [{"id": key, "input": "x", "expected": "partial"}
                for key in ("exit", "signal", "huge", "after")]
        table = {"exit": {"out": "partial", "exit": 3},
                 "signal": {"signal": 9},
                 "huge": {"out_repeat": {"char": "a", "count": 1048577}},
                 "after": {"out": "partial"}}
        build = self.command_fixture(rows=rows, table=table)
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 1)
        stored = {row["id"]: row for row in self.latest(build)[2]}
        self.assertEqual((stored["exit"]["reason"], stored["exit"]["output"]),
                         ("runner exit 3", "partial"))
        self.assertEqual(stored["signal"]["reason"], "runner exit -9")
        self.assertEqual(stored["huge"]["reason"], "output too large")
        self.assertIsNone(stored["huge"]["exit_code"])
        self.assertLessEqual(len(stored["huge"]["output"]), 2008)
        self.assertTrue(stored["after"]["pass"])

        missing_set = self.eval_set(cmd="nonexistent-program-xyz")
        self.configure([missing_set]); self.write_examples([{"id": "e1", "input": "x", "expected": "x"}])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 1)
        _, summary, missing_rows = self.latest(build)
        self.assertEqual((missing_rows[0]["reason"], summary["passed"], summary["accuracy"]),
                         ("runner exit 127", 0, 0.0))

    def test_T_EVAL_14_cost_line_parsing(self):
        """T-EVAL-14: the last valid finite stderr cost wins; stdout never counts."""
        self.require_evals()
        specs = [
            (["factory-cost: 0.5"], "", 0.5),
            (["noise", "factory-cost: 0.5", "factory-cost: 0.7"], "", 0.7),
            (["factory-cost: 0"], "", 0.0),
            (["factory-cost: abc"], "", None),
            (["  factory-cost:  0.25  "], "", 0.25),
            (["factory-cost: 1e999"], "", None),
            (["factory-cost: 5 dollars"], "", None),
            ([], "factory-cost: 9", None),
        ]
        rows = [{"id": "e%d" % i, "input": "x", "expected": out}
                for i, (_, out, _) in enumerate(specs, 1)]
        table = {"e%d" % i: {"err_lines": err, "out": out}
                 for i, (err, out, _) in enumerate(specs, 1)}
        build = self.command_fixture(rows=rows, table=table)
        self.run_factory("eval", "run", "greet")
        self.assertEqual([row["cost"] for row in self.latest(build)[2]],
                         [item[2] for item in specs])

    def test_T_EVAL_15_normalize(self):
        """T-EVAL-15: NFC, casefold, and Python Unicode whitespace define normalization."""
        e = self.require_evals()
        self.assertEqual(e.normalize("  Hello \n\tWorld "), "hello world")
        self.assertEqual(e.normalize("école"), e.normalize("e\u0301cole"))
        self.assertEqual(e.normalize("STRASSE"), e.normalize("straße"))
        self.assertEqual(e.normalize(""), "")
        self.assertEqual(e.normalize("A   B"), "a b")
        self.assertEqual(e.normalize("a\u00a0b"), "a b")
        self.assertEqual(e.normalize("a\u200bb"), "a\u200bb")
        self.assertEqual(len(e.normalize("a\u200bb")), 3)

    def test_T_EVAL_16_exact_scorer(self):
        """T-EVAL-16: exact scorer supports normalized/raw text and type errors."""
        e = self.require_evals()
        self.assertEqual(e.score({"type": "exact"}, "Hello!", "hello!"), (True, "ok"))
        self.assertEqual(e.score({"type": "exact"}, "Hello", "Hello!"), (False, "output differs"))
        raw = {"type": "exact", "normalize": False}
        self.assertEqual(e.score(raw, "Hello", "hello"), (False, "output differs"))
        self.assertEqual(e.score(raw, "hello", "hello"), (True, "ok"))
        self.assertEqual(e.score(raw, "5", 5), (False, "expected must be a string"))

    def test_T_EVAL_17_number_scorer(self):
        """T-EVAL-17: strict ASCII number grammar, finite values, and max tolerance."""
        e = self.require_evals()
        cases = [
            ("3.14", 3.14, {}, (True, "ok")),
            ("3.1", 3.14, {"tol": .05}, (True, "ok")),
            ("3.2", 3.14, {"tol": .05}, (False, "outside tolerance (got 3.2, wanted 3.14)")),
            ("100.9", 100, {"rel": .01}, (True, "ok")),
            ("101.1", 100, {"rel": .01}, (False, "outside tolerance (got 101.1, wanted 100)")),
            ("1000.9", 1000, {"tol": .5, "rel": .001}, (True, "ok")),
            ("1e3", 1000, {}, (True, "ok")), (" 7 \n", 7, {}, (True, "ok")),
            ("+5", 5, {}, (True, "ok")), (".5", .5, {}, (True, "ok")),
            ("5.", 5, {}, (True, "ok")),
        ]
        for output, expected, extra, wanted in cases:
            scorer = {"type": "number"}; scorer.update(extra)
            self.assertEqual(e.score(scorer, output, expected), wanted)
        for output in ("abc", "nan", "inf", "infinity", "1e999", "1_000", "١٢٣", "12 apples", ""):
            self.assertEqual(e.score({"type": "number"}, output, 7), (False, "not a number"))
        for expected in (True, "7", float("inf"), 10 ** 400):
            self.assertEqual(e.score({"type": "number"}, "7", expected),
                             (False, "expected must be a number"))

    def test_T_EVAL_18_contains_scorer(self):
        """T-EVAL-18: contains requires every item and never leaks expected text in reasons."""
        e = self.require_evals(); scorer = {"type": "contains"}; output = "The Answer is 42"
        self.assertEqual(e.score(scorer, output, "answer is"), (True, "ok"))
        self.assertEqual(e.score(scorer, output, ["answer", "42"]), (True, "ok"))
        self.assertEqual(e.score(scorer, output, ["answer", "43"]),
                         (False, "missing expected text 2 of 2"))
        reason = e.score(scorer, output, ["zzz", "43"])
        self.assertEqual(reason, (False, "missing expected text 1 of 2"))
        self.assertNotIn("zzz", reason[1]); self.assertNotIn("43", reason[1])
        self.assertEqual(e.score(scorer, output, "zzz"),
                         (False, "missing expected text 1 of 1"))
        for expected in ([], 5, ["a", 1]):
            self.assertEqual(e.score(scorer, output, expected),
                             (False, "expected must be a string or a list of strings"))
        self.assertEqual(e.score({"type": "contains", "normalize": False}, "Answer", "answer"),
                         (False, "missing expected text 1 of 1"))

    def test_T_EVAL_19_json_field_scorer(self):
        """T-EVAL-19: dotted fields, list indices, and bool-safe recursive equality."""
        e = self.require_evals(); scorer = {"type": "json_field"}
        output = '{"user":{"name":"Ann"},"items":[{"id":7}],"n":1,"ok":true,"0":"zero"}'
        self.assertEqual(e.score(scorer, output,
                                 {"user.name": "Ann", "items.0.id": 7, "n": 1.0, "0": "zero"}),
                         (True, "ok"))
        cases = [
            ({"n": True}, "field n differs"), ({"ok": 1}, "field ok differs"),
            ({"user.age": 3}, "missing field user.age"),
            ({"items.1.id": 1}, "missing field items.1.id"),
            ({"user.name.first": "A"}, "missing field user.name.first"),
            ({"user.name": "ann"}, "field user.name differs"),
            ({"a b": 1}, "bad field path"), ({"a" * 65: 1}, "bad field path"),
            ({"a..b": 1}, "bad field path"),
        ]
        for expected, reason in cases:
            self.assertEqual(e.score(scorer, output, expected), (False, reason))
        self.assertEqual(e.score(scorer, '{"items":[{"id":1}]}', {"items.0.id": True}),
                         (False, "field items.0.id differs"))
        self.assertEqual(e.score(scorer, '{"items":[{"id":1}]}', {"items.0.id": 1.0}),
                         (True, "ok"))
        for bad_output in ("nope", ""):
            self.assertEqual(e.score(scorer, bad_output, {"n": 1}),
                             (False, "output is not JSON"))
        self.assertEqual(e.score(scorer, '  {"n":1} \n', {"n": 1}), (True, "ok"))
        for expected in (["n"], "n", {}):
            self.assertEqual(e.score(scorer, output, expected),
                             (False, "expected must be an object"))
        self.assertFalse(e.json_equal([1], [True]))
        self.assertTrue(e.json_equal({"a": [1, {"b": None}]}, {"a": [1.0, {"b": None}]}))
        self.assertFalse(e.json_equal(1, True)); self.assertFalse(e.json_equal("1", 1))

    def test_T_EVAL_20_scorer_failures_continue(self):
        """T-EVAL-20: a bad expected type fails only its example."""
        self.require_evals()
        rows = [{"id": "e1", "input": "x", "expected": 5},
                {"id": "e2", "input": "x", "expected": "five"},
                {"id": "e3", "input": "x", "expected": 5}]
        table = {key: {"out": "5"} for key in ("e1", "e2", "e3")}
        setting = self.eval_set(scorer={"type": "number"})
        build = self.command_fixture(rows=rows, table=table, sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 0)
        stored = self.latest(build)[2]
        self.assertEqual([(x["pass"], x["reason"]) for x in stored],
                         [(True, "ok"), (False, "expected must be a number"), (True, "ok")])


class EvalMetricsTargetsAndStorageTests(EvalTestCase):
    def rows(self, n, passed, costs=None, times=None, tags=None):
        costs = costs if costs is not None else [None] * n
        times = times if times is not None else [0.1] * n
        tags = tags if tags is not None else [[] for _ in range(n)]
        return [{"id": "e%d" % (i + 1), "pass": i < passed,
                 "reason": "ok" if i < passed else "output differs",
                 "time_s": times[i], "cost": costs[i], "tags": tags[i]}
                for i in range(n)]

    def summarize(self, e, rows, targets=None, unit="USD"):
        return e.summarize("greet", "Greeting answers", rows,
                           targets or {"accuracy": ">=0"}, unit)

    def test_T_EVAL_21_accuracy_rounding(self):
        """T-EVAL-21: accuracy is half-up integer math and all rows count in n."""
        e = self.require_evals()
        for n, passed, wanted in ((3, 2, .6667), (3, 1, .3333), (32, 1, .0313),
                                  (4, 0, 0.0), (4, 4, 1.0)):
            with self.subTest(n=n, passed=passed):
                summary = self.summarize(e, self.rows(n, passed))
                self.assertEqual(summary["accuracy"], wanted)
                self.assertEqual(summary["n"], n)
                self.assertEqual(summary["passed"], passed)
                self.assertIs(type(summary["n"]), int)
                self.assertIs(type(summary["passed"]), int)
        failed = self.rows(3, 1)
        failed[1]["reason"] = "timed out after 0.3 s"
        failed[2]["reason"] = "runner exit 3"
        self.assertEqual(self.summarize(e, failed)["n"], 3)

    def test_T_EVAL_22_percentile_nearest_rank(self):
        """T-EVAL-22: percentile uses nearest rank and summary rounds times to 3 decimals."""
        e = self.require_evals()
        cases = [([.5, .1, .4, .2, .3], .3, .5), ([.7], .7, .7),
                 (list(range(1, 21)), 10, 19), (list(range(1, 101)), 50, 95),
                 (list(range(1, 22)), 11, 20)]
        for values, p50, p95 in cases:
            self.assertEqual(e.percentile(values, 50), p50)
            self.assertEqual(e.percentile(values, 95), p95)
        summary = self.summarize(e, self.rows(1, 1, times=[.12345]))
        self.assertEqual(summary["time_p50_s"], .123)
        self.assertEqual(summary["time_p95_s"], .123)
        with self.assertRaises(ValueError):
            e.percentile([], 50)

    def test_T_EVAL_23_cost_metrics(self):
        """T-EVAL-23: fsum, missing-cost notes, zeros, and independent rounding."""
        e = self.require_evals()
        summary = self.summarize(e, self.rows(3, 3, costs=[.1, .2, .3]))
        self.assertEqual((summary["cost_total"], summary["cost_per_example"]), (.6, .2))
        self.assertNotIn("cost_note", summary)
        summary = self.summarize(e, self.rows(3, 3, costs=[.1, None, .3]))
        self.assertEqual((summary["cost_total"], summary["cost_per_example"]), (None, None))
        self.assertEqual(summary["cost_note"], "not reported by 1 of 3 examples")
        summary = self.summarize(e, self.rows(3, 3, costs=[None, None, None]))
        self.assertEqual(summary["cost_note"], "not reported by 3 of 3 examples")
        summary = self.summarize(e, self.rows(2, 2, costs=[0, 0]))
        self.assertEqual((summary["cost_total"], summary["cost_per_example"]), (0.0, 0.0))
        self.assertNotIn("cost_note", summary)
        summary = self.summarize(e, self.rows(3, 3, costs=[.00005] * 3))
        self.assertEqual((summary["cost_total"], summary["cost_per_example"]), (.0002, .0001))
        self.assertEqual(summary["cost_unit"], "USD")

    def test_T_EVAL_24_tags_and_no_filter_option(self):
        """T-EVAL-24: tag aggregates overlap and --tag is rejected."""
        self.require_evals()
        rows = [
            {"id": "a1", "input": "x", "expected": "ok", "tags": ["x"]},
            {"id": "a2", "input": "x", "expected": "ok", "tags": ["x"]},
            {"id": "b1", "input": "x", "expected": "ok", "tags": ["y"]},
            {"id": "b2", "input": "x", "expected": "ok", "tags": ["y"]},
            {"id": "c1", "input": "x", "expected": "ok", "tags": ["x", "y"]},
            {"id": "d1", "input": "x", "expected": "ok"},
        ]
        table = {key: {"out": "bad" if key in ("a2", "d1") else "ok"}
                 for key in ("a1", "a2", "b1", "b2", "c1", "d1")}
        build = self.command_fixture(rows=rows, table=table)
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 0)
        summary = self.latest(build)[1]
        self.assertEqual(summary["by_tag"], {
            "x": {"n": 3, "passed": 2, "accuracy": .6667},
            "y": {"n": 3, "passed": 3, "accuracy": 1.0},
        })
        self.assertEqual(summary["tags"], [])
        self.assertEqual(summary["n"], 6)
        rejected = self.run_factory("eval", "run", "greet", "--tag", "x")
        self.assertEqual(rejected.returncode, 2)

    def test_T_EVAL_25_target_operators(self):
        """T-EVAL-25: every target operator compares rounded metrics and normalizes spaces."""
        e = self.require_evals()
        rows = self.rows(10, 9, costs=[.01] * 10, times=[.04] * 10)
        cases = [
            ("accuracy", ">= 0.9", True, ">=0.9"), ("accuracy", ">0.9", False, ">0.9"),
            ("accuracy", "<=0.9", True, "<=0.9"), ("accuracy", "<0.9", False, "<0.9"),
            ("accuracy", "==0.9", True, "==0.9"), ("p95_s", "<=0.04", True, "<=0.04"),
            ("p95_s", "<0.04", False, "<0.04"),
            ("cost_per_example", "<=0.01", True, "<=0.01"),
            ("cost_per_example", "<0.01", False, "<0.01"),
        ]
        for key, text, met, stored in cases:
            target = self.summarize(e, rows, {key: text})["targets"][0]
            self.assertEqual(target["key"], key)
            self.assertEqual(target["target"], stored)
            self.assertEqual(target["met"], met)
            self.assertIn("value", target)

    def test_T_EVAL_26_missing_cost_never_passes(self):
        """T-EVAL-26: a cost target with any null cost fails and prints not reported."""
        self.require_evals()
        setting = self.eval_set(targets={"accuracy": ">=0.5", "cost_per_example": "<=1"})
        build = self.command_fixture(sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 1)
        summary = self.latest(build)[1]
        target = next(x for x in summary["targets"] if x["key"] == "cost_per_example")
        self.assertIsNone(target["value"]); self.assertFalse(target["met"])
        self.assertFalse(summary["met"])
        lines = result.stdout.splitlines()
        self.assertEqual(lines[2], "cost: not reported")
        self.assertEqual(lines[-1], "eval greet: targets NOT met: cost_per_example")

    def test_T_EVAL_27_output_exit_money_and_show(self):
        """T-EVAL-27: summary text, exits, failure elision, money, and show-only reads."""
        self.require_evals()
        rows = [{"id": "e%d" % i, "input": "x", "expected": "ok"} for i in range(1, 5)]
        table = {"e1": {"out": "ok"}, "e2": {"out": "ok"},
                 "e3": {"out": "ok"}, "e4": {"out": "bad"}}
        setting = self.eval_set(targets={"accuracy": ">=0.9"})
        build = self.command_fixture(rows=rows, table=table, sets=[setting])
        result = self.run_factory("eval", "run", "greet")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, re.compile(
            r"^eval greet: 3 of 4 passed, accuracy 0\.7500 \(target >=0\.9 not met\)\n"
            r"time per example: p50 [0-9.]+ s, p95 [0-9.]+ s\n"
            r"cost: not reported\nfailed: e4 \(output differs\)\n"
            r"eval greet: targets NOT met: accuracy\n$"))
        table["e4"]["out"] = "ok"; self.write_table(table)
        passed = self.run_factory("eval", "run", "greet")
        self.assertEqual(passed.returncode, 0)
        self.assertIn("eval greet: 4 of 4 passed, accuracy 1.0000 (target >=0.9 met)", passed.stdout)
        self.assertTrue(passed.stdout.endswith("eval greet: targets met\n"))
        self.assertNotIn("failed:", passed.stdout)

        # Show formats a synthetic 12-failure summary, proving the ten-id cap without 12 SUT runs.
        many = self.factory_home / "runs" / "toy" / "many"; many.mkdir(parents=True)
        (many / "trace.jsonl").write_text("")
        failed = [{"id": "f%d" % i, "reason": "output differs"} for i in range(1, 13)]
        self.seed_summary(many, "greet", {
            "n": 12, "passed": 0, "accuracy": 0.0, "time_p50_s": .01,
            "time_p95_s": .02, "cost_total": None, "cost_per_example": None,
            "cost_note": "not reported by 12 of 12 examples", "failed": failed,
            "targets": [{"key": "accuracy", "target": ">=0.9", "value": 0.0, "met": False}],
            "met": False,
        })
        self.select("toy", "many")
        shown = self.run_factory("eval", "show", "greet")
        self.assertEqual(shown.returncode, 0)
        self.assertIn("and 2 more", shown.stdout)

        # Money rendering is exercised by two short real runs.
        for unit, wanted in (("USD", "cost: $0.2000 total, $0.0500 per example"),
                             ("EUR", "cost: 0.2000 EUR total, 0.0500 EUR per example")):
            self.select("toy", "b1")
            cost_table = {"e%d" % i: {"out": "ok", "err_lines": ["factory-cost: 0.05"]}
                          for i in range(1, 5)}
            self.write_table(cost_table)
            self.configure([setting], cost_unit=unit)
            cost_result = self.run_factory("eval", "run", "greet")
            self.assertIn(wanted, cost_result.stdout)
        entry, _, _ = self.latest(build)
        result_path = build / "evals" / entry["file"]
        mode = result_path.stat().st_mode
        result_path.chmod(0)
        try:
            shown = self.run_factory("eval", "show", "greet")
            self.assertEqual(shown.returncode, 0, shown.stderr)
        finally:
            result_path.chmod(mode)

    def test_T_EVAL_28_append_only_files_and_no_log(self):
        """T-EVAL-28: stamped results/index are append-only; --no-log writes nothing."""
        self.require_evals()
        self.env["FACTORY_NOW"] = "2026-11-25T18:00:00Z"
        build = self.command_fixture(rows=[{"id": "e1", "input": "x", "expected": "x"}])
        first = self.run_factory("eval", "run", "greet")
        self.assertEqual(first.returncode, 0)
        eval_dir = build / "evals"
        first_jsonl = eval_dir / "greet-20261125T180000Z.jsonl"
        first_json = eval_dir / "greet-20261125T180000Z.json"
        stored = first_jsonl.read_bytes(), first_json.read_bytes()
        rows = read_jsonl(first_jsonl)
        self.assertEqual(len(rows), 1); self.assertEqual(set(rows[0]), RESULT_KEYS)
        summary = json.loads(first_json.read_text())
        self.assertTrue(SUMMARY_KEYS.issubset(summary))
        index = read_jsonl(eval_dir / "index.jsonl")
        self.assertEqual(set(index[0]), {"ts", "set", "file", "summary", "met"})
        second = self.run_factory("eval", "run", "greet")
        self.assertEqual(second.returncode, 0)
        self.assertTrue((eval_dir / "greet-20261125T180000Z-2.jsonl").exists())
        self.assertTrue((eval_dir / "greet-20261125T180000Z-2.json").exists())
        self.assertEqual((first_jsonl.read_bytes(), first_json.read_bytes()), stored)
        self.assertEqual(len(read_jsonl(eval_dir / "index.jsonl")), 2)

        isolated = self.tmp / "no-log-factory"; isolated.mkdir()
        old_home = self.env["FACTORY_HOME"]; self.env["FACTORY_HOME"] = str(isolated)
        try:
            before = tree_snapshot(isolated)
            no_log = self.run_factory("eval", "run", "greet", "--no-log")
            self.assertEqual(no_log.returncode, 0)
            self.assertEqual(tree_snapshot(isolated), before)
            (self.project / "evals" / "greet.jsonl").write_text("{bad\n")
            bad = self.run_factory("eval", "run", "greet", "--no-log")
            self.assertEqual(bad.returncode, 2)
            self.assertEqual(tree_snapshot(isolated), before)
        finally:
            self.env["FACTORY_HOME"] = old_home

    def test_T_EVAL_29_redaction_and_secret_shaped_ids(self):
        """T-EVAL-29: scoring uses raw values but every stored/printed string is redacted."""
        self.require_evals()
        secret = "sk-" + "a" * 24
        row = {"id": "e1", "input": secret, "expected": "echo:"}
        setting = self.eval_set(cmd="%s bin/echo_sut.py" % PYTHON,
                                scorer={"type": "contains"})
        build = self.command_fixture(rows=[row], sets=[setting])
        first = self.run_factory("eval", "run", "greet")
        self.assertEqual(first.returncode, 0)
        self.assertNotIn(secret, first.stdout + first.stderr)
        self.assertEqual(first.stderr, "factory: redacted 2 secret-looking value(s) in eval results\n")
        _, _, stored = self.latest(build)
        self.assertIn("[REDACTED]", stored[0]["input"])
        self.assertIn("[REDACTED]", stored[0]["output"])

        password = "pass" + "word: " + "hunter" + "22222"
        self.write_examples([row, {"id": "e2", "input": "hello", "expected": password}])
        second = self.run_factory("eval", "run", "greet")
        self.assertEqual(second.stderr, "factory: redacted 3 secret-looking value(s) in eval results\n")
        entry, summary, rows = self.latest(build)
        self.assertEqual(rows[1]["reason"], "missing expected text 1 of 1")
        checked = second.stdout + second.stderr + json.dumps(summary)
        checked += (build / "evals" / "index.jsonl").read_text()
        checked += (build / "trace.jsonl").read_text()
        for forbidden in (secret, "hunter" + "22222", "pass" + "word"):
            self.assertNotIn(forbidden, checked)
        self.assertNotIn("echo:", (build / "trace.jsonl").read_text())

        for field in ("id", "tag"):
            item = {"id": secret if field == "id" else "e1", "input": "x", "expected": "x"}
            if field == "tag": item["tags"] = [secret]
            self.write_examples([item])
            before = tree_snapshot(build)
            rejected = self.run_factory("eval", "run", "greet")
            self.assertEqual(rejected.returncode, 2)
            self.assertIn("bad %s" % field, rejected.stderr)
            self.assertEqual(tree_snapshot(build / "evals"), tree_snapshot(build / "evals"))
            self.assertEqual((build / "trace.jsonl").read_bytes(), before["trace.jsonl"])

    def test_T_EVAL_30_result_string_truncation(self):
        """T-EVAL-30: strings cut after redaction at 2000 characters, not at 2000."""
        self.require_evals()
        secret = "sk-" + "a" * 24
        rows = [{"id": "long", "input": "x", "expected": "z"},
                {"id": "exact", "input": "x", "expected": "z"},
                {"id": "redact", "input": "x", "expected": "z"}]
        table = {"long": {"out_repeat": {"char": "a", "count": 5000}},
                 "exact": {"out_repeat": {"char": "b", "count": 2000}},
                 "redact": {"out": secret + " ", "out_repeat": {"char": "c", "count": 3000}}}
        build = self.command_fixture(rows=rows, table=table)
        result = self.run_factory("eval", "run", "greet")
        stored = {x["id"]: x for x in self.latest(build)[2]}
        self.assertEqual(stored["long"]["output"], "a" * 2000 + "...[cut]")
        self.assertEqual(stored["exact"]["output"], "b" * 2000)
        self.assertTrue(stored["redact"]["output"].startswith("[REDACTED]"))
        self.assertEqual(len(stored["redact"]["output"]), 2008)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_T_EVAL_31_spans_failures_and_interrupt(self):
        """T-EVAL-31: exactly one two-line span; misses log; early errors do not; signals stop."""
        self.require_evals()
        build = self.command_fixture()
        before = len(read_jsonl(build / "trace.jsonl"))
        met = self.run_factory("eval", "run", "greet")
        self.assertEqual(met.returncode, 0)
        added = read_jsonl(build / "trace.jsonl")[before:]
        self.assertEqual(len(added), 2)
        self.assertEqual(len({x["span_id"] for x in added}), 1)
        close = added[-1]
        expected = {"kind": "command", "actor": "orchestrator", "step": "evalset.greet",
                    "cmd": "factory eval run greet", "status": "done", "exit_code": 0,
                    "target_met": True, "eval_n": 1, "eval_passed": 1,
                    "output_ref": "evals/greet-20260110T121200Z.json"}
        for key, value in expected.items(): self.assertEqual(close[key], value)
        for key in ("value", "target", "eval_p50_s", "eval_p95_s", "eval_cost", "duration_s"):
            self.assertIn(key, close)
        self.assertIs(type(close["duration_s"]), int)
        self.assertFalse((build / "messages").exists() and any((build / "messages").iterdir()))

        self.write_table({"e1": {"out": "wrong"}})
        missed = self.run_factory("eval", "run", "greet")
        self.assertEqual(missed.returncode, 1)
        close = read_jsonl(build / "trace.jsonl")[-1]
        self.assertEqual((close["status"], close["failure_class"], close["target_met"], close["exit_code"]),
                         ("failed", "impl-bug", False, 1))

        self.write_examples([{"id": "e1", "input": "x", "expected": "x"}])
        self.write_table({"e1": {"sleep": 5, "pidfile": str(self.tmp / "interrupt-pid")}})
        eval_before = set((build / "evals").iterdir())
        process = subprocess.Popen([PYTHON, str(FACTORY_PY), "eval", "run", "greet"],
                                   cwd=str(self.project), env=self.env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + .3
            while time.monotonic() < deadline and not (self.tmp / "interrupt-pid").exists():
                time.sleep(.01)
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=.9)
        finally:
            if process.poll() is None:
                process.kill(); process.communicate(timeout=.2)
        self.assertIsNotNone(process.returncode)
        self.assertEqual(read_jsonl(build / "trace.jsonl")[-1]["status"], "stopped")
        self.assertEqual(set((build / "evals").iterdir()), eval_before)
        pidfile = self.tmp / "interrupt-pid"
        if pidfile.exists():
            with self.assertRaises(ProcessLookupError): os.kill(int(pidfile.read_text()), 0)


class EvalDisplaySafetyAndEndToEndTests(EvalTestCase):
    def display_fixture(self):
        self.install_suts()
        greet = self.eval_set("greet", "Greeting answers", targets={"accuracy": ">=0.9", "p95_s": "<=1.5"})
        parse = self.eval_set("parse", "Parser", scorer={"type": "contains"},
                              targets={"accuracy": ">=0.9"})
        self.configure([greet, parse])
        greet_rows = [{"id": "g%d" % i, "input": "x", "expected": "ok"} for i in range(1, 11)]
        parse_rows = [{"id": "p%d" % i, "input": "SENTINEL_IN_77", "expected": "SENTINEL_EXP_88"}
                      for i in range(1, 6)]
        self.write_examples(greet_rows, "greet.jsonl"); self.write_examples(parse_rows, "parse.jsonl")
        table = {"g%d" % i: {"out": "ok" if i < 10 else "bad",
                                      "err_lines": ["factory-cost: 0.01"]} for i in range(1, 11)}
        table.update({"p%d" % i: {"out": "SENTINEL_EXP_88" if i < 5 else "wrong"}
                      for i in range(1, 6)})
        self.write_table(table)
        build = self.new_build()
        self.close_build(build)
        self.assertEqual(self.run_factory("eval", "run", "greet").returncode, 0)
        self.env["FACTORY_NOW"] = "2026-01-10T12:13:00Z"
        self.assertEqual(self.run_factory("eval", "run", "parse").returncode, 1)
        return build

    def test_T_EVAL_32_report_card(self):
        """T-EVAL-32: card placement, caps, target prose, percent rules, and result independence."""
        e = self.require_evals()
        build = self.display_fixture()
        card = self.run_factory("report-card")
        self.assertEqual(card.returncode, 0, card.stderr)
        lines = card.stdout.splitlines()
        greeting = next(x for x in lines if x.startswith("Evals: Greeting answers"))
        parser = next(x for x in lines if x.startswith("Evals: Parser"))
        self.assertRegex(greeting, r"^Evals: Greeting answers, 9 of 10 right \(90%\), target met\. Slowest 5%: [0-9.]+ s\. Cost per example: \$0\.0100$")
        self.assertEqual(parser, "Evals: Parser, 4 of 5 right (80%), target NOT met (needs 90%)")
        failure_at = next(i for i, x in enumerate(lines) if x.startswith("Things that failed"))
        eval_at = lines.index(greeting); bottleneck_at = next(i for i, x in enumerate(lines) if x.startswith("Top 3 bottlenecks"))
        self.assertLess(failure_at, eval_at); self.assertLess(eval_at, bottleneck_at)
        self.assertLessEqual(len(lines), 30)
        self.assertFalse(any(word in card.stdout.lower() for word in ("span", "iteration", "node", "rubric", "evalset")))
        result_line = next(x for x in lines if x.startswith("Result:"))
        self.assertEqual(result_line, "Result: Finished")
        self.assertIn("evalset.parse", (build / "trace.jsonl").read_text())

        # Synthetic latest summaries exercise the display-only edge cases cheaply.
        synth = self.factory_home / "runs" / "toy" / "display"; synth.mkdir(parents=True)
        (synth / "trace.jsonl").write_text("")
        scenarios = [
            ("speed", [{"key": "p95_s", "target": "<=1", "value": 2, "met": False}], "speed"),
            ("cost", [{"key": "cost_per_example", "target": "<=1", "value": 2, "met": False}], "cost"),
            ("both", [{"key": "accuracy", "target": ">=0.9", "value": .8, "met": False},
                      {"key": "p95_s", "target": "<=1", "value": 2, "met": False}], "needs 90%, speed"),
        ]
        for i, (set_id, targets, _,) in enumerate(scenarios):
            self.seed_summary(synth, set_id, {"name": set_id, "n": 10, "passed": 8,
                "accuracy": .8, "time_p50_s": .1, "time_p95_s": 2,
                "cost_total": 20, "cost_per_example": 2, "targets": targets, "met": False},
                stamp="20261125T18000%dZ" % i)
        self.select("toy", "display")
        synthetic_card = self.run_factory("report-card").stdout
        for _, _, phrase in scenarios: self.assertIn("(%s)" % phrase, synthetic_card)

        thresholds = self.factory_home / "runs" / "toy" / "thresholds"
        thresholds.mkdir(parents=True); (thresholds / "trace.jsonl").write_text("")
        threshold_scenarios = [
            ("over", [{"key": "accuracy", "target": ">0.9", "value": .9, "met": False}], "over 90%"),
            ("decimal", [{"key": "accuracy", "target": ">=0.925", "value": .9, "met": False}], "needs 92.5%"),
        ]
        for i, (set_id, targets, _,) in enumerate(threshold_scenarios):
            self.seed_summary(thresholds, set_id, {"name": set_id, "n": 10, "passed": 8,
                "accuracy": .8, "time_p50_s": .1, "time_p95_s": 2,
                "cost_total": 20, "cost_per_example": 2, "targets": targets, "met": False},
                stamp="20261125T18000%dZ" % i)
        self.select("toy", "thresholds")
        threshold_card = self.run_factory("report-card").stdout
        for _, _, phrase in threshold_scenarios: self.assertIn("(%s)" % phrase, threshold_card)

        capped = self.factory_home / "runs" / "toy" / "capped"
        capped.mkdir(parents=True); (capped / "trace.jsonl").write_text("")
        for i in range(5):
            self.seed_summary(capped, "cap%d" % i, {"n": 1, "passed": 1, "accuracy": 1.0,
                "time_p50_s": .1, "time_p95_s": .1, "cost_total": None,
                "cost_per_example": None,
                "targets": [{"key": "accuracy", "target": ">=1", "value": 1.0, "met": True}],
                "met": True}, stamp="20261125T18000%dZ" % i)
        self.select("toy", "capped")
        self.assertIn("and 2 more", self.run_factory("report-card").stdout)

        summary = e.summarize("almost", "Almost", self._summary_rows(250, 249), {"accuracy": ">=1"}, "USD")
        almost = self.factory_home / "runs" / "toy" / "almost"; almost.mkdir(parents=True)
        (almost / "trace.jsonl").write_text(""); self.seed_summary(almost, "almost", summary)
        self.select("toy", "almost")
        almost_card = self.run_factory("report-card").stdout
        self.assertIn("249 of 250 right (99%)", almost_card); self.assertNotIn("(100%)", almost_card)

    @staticmethod
    def _summary_rows(n, passed):
        return [{"id": "x%d" % i, "pass": i < passed, "reason": "ok" if i < passed else "output differs",
                 "time_s": .1, "cost": .01, "tags": []} for i in range(n)]

    def test_T_EVAL_33_status(self):
        """T-EVAL-33: board/text show latest sets, empty state, and tolerate one bad summary."""
        self.require_evals()
        build = self.display_fixture()
        text_result = self.run_factory("status")
        self.assertEqual(text_result.returncode, 0)
        text = text_result.stdout
        self.assertIn("EVALS", text)
        self.assertRegex(text, r"Greeting answers\s+9 of 10 right \(90%\)\s+target met")
        self.assertRegex(text, r"Parser\s+4 of 5 right \(80%\)\s+target NOT met")
        json_result = self.run_factory("status", "--json")
        board = json.loads(json_result.stdout)
        self.assertEqual(len(board["evals"]), 2)
        self.assertEqual(set(board["evals"][0]), {"set", "name", "passed", "n", "accuracy", "met", "when"})
        empty = self.factory_home / "runs" / "toy" / "empty"; empty.mkdir(parents=True)
        (empty / "trace.jsonl").write_text(""); self.select("toy", "empty")
        empty_text = self.run_factory("status").stdout
        empty_json = json.loads(self.run_factory("status", "--json").stdout)
        self.assertNotIn("EVALS", empty_text); self.assertEqual(empty_json["evals"], [])
        self.select("toy", "b1")
        parse_summary = next(x["summary"] for x in read_jsonl(build / "evals" / "index.jsonl") if x["set"] == "parse")
        path = build / "evals" / parse_summary; original = path.read_bytes(); path.write_text("{")
        try:
            damaged = json.loads(self.run_factory("status", "--json").stdout)
            self.assertEqual(len(damaged["evals"]), 1)
            self.assertEqual(len(damaged["warnings"]), 1)
            self.assertRegex(damaged["warnings"][0], r"\d")
        finally:
            path.write_bytes(original)

    def test_T_EVAL_34_trace_report(self):
        """T-EVAL-34: trace report includes exact latest summaries only when runs exist."""
        self.require_evals()
        build = self.display_fixture()
        result = self.run_factory("trace-report", "--json")
        report = json.loads(result.stdout)
        expected = [json.loads((build / "evals" / entry["summary"]).read_text())
                    for entry in read_jsonl(build / "evals" / "index.jsonl")]
        self.assertEqual(report["evals"], expected)
        markdown = self.run_factory("trace-report").stdout
        self.assertIn("Evals", markdown)
        self.assertGreater(markdown.index("Evals"), markdown.index("Failures"))
        empty = self.new_build("empty-report")
        self.close_build(empty)
        timed = self.run_factory("log", "event", "--kind", "command",
                                 "--actor", "orchestrator", "--duration-s", "1")
        self.assertEqual(timed.returncode, 0, timed.stdout + timed.stderr)
        empty_json = json.loads(self.run_factory("trace-report", "--json").stdout)
        self.assertNotIn("evals", empty_json)
        self.assertNotIn("Evals", self.run_factory("trace-report").stdout)

    def test_T_EVAL_35_checker_separation_and_show_privacy(self):
        """T-EVAL-35: evals do not alter check/result and show contains summary data only."""
        self.require_evals()
        build = self.display_fixture()
        with_evals = self.run_factory("check")
        trace = build / "trace.jsonl"; full = trace.read_bytes()
        lines = [line for line in full.splitlines(True) if b'"step": "evalset.' not in line and b'"step":"evalset.' not in line]
        trace.write_bytes(b"".join(lines))
        try:
            without_evals = self.run_factory("check")
            self.assertEqual((with_evals.returncode, with_evals.stdout, with_evals.stderr),
                             (without_evals.returncode, without_evals.stdout, without_evals.stderr))
        finally:
            trace.write_bytes(full)
        card = self.run_factory("report-card").stdout
        self.assertEqual(next(x for x in card.splitlines() if x.startswith("Result:")), "Result: Finished")
        shown = self.run_factory("eval", "show", "parse")
        self.assertEqual(shown.returncode, 0)
        self.assertIn("missing expected text 1 of 1", shown.stdout)
        for sentinel in ("SENTINEL_IN_77", "SENTINEL_EXP_88"):
            self.assertNotIn(sentinel, shown.stdout + shown.stderr)

    def test_T_EVAL_36_no_model_network_or_deletion(self):
        """T-EVAL-36: commands invoke no model/network and preserve all pre-existing bytes."""
        self.require_evals()
        source = SCRIPTS_DIR / "evals.py"
        tree = ast.parse(source.read_text(), filename=str(source))
        forbidden = {"socket", "urllib", "http", "ssl", "requests", "random"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imported.update(x.name.split(".")[0] for x in node.names)
            if isinstance(node, ast.ImportFrom) and node.module: imported.add(node.module.split(".")[0])
        self.assertFalse(imported & forbidden)
        build = self.command_fixture()
        spy_file = self.tmp / "spy.log"
        for name in ("claude", "codex"):
            path = self.tmp / "bin" / name; path.parent.mkdir(exist_ok=True)
            shutil.copy2(str(EVAL_FIXTURES / "spy_program.py"), str(path)); path.chmod(0o755)
        self.env["PATH"] = str(self.tmp / "bin") + os.pathsep + self.env.get("PATH", "")
        self.env["SPY_FILE"] = str(spy_file)
        project_before = tree_snapshot(self.project); build_before = tree_snapshot(build)
        for args in (("eval", "run", "greet"), ("eval", "show", "greet"),
                     ("eval", "diagnose", "greet"), ("status",),
                     ("report-card",), ("trace-report",)):
            self.run_factory(*args)
        self.assertFalse(spy_file.exists())
        for rel, data in project_before.items(): self.assertEqual((self.project / rel).read_bytes(), data)
        allowed_growth = {"trace.jsonl", "log-errors.jsonl", "evals/index.jsonl"}
        for rel, data in build_before.items():
            after = (build / rel).read_bytes()
            if rel in allowed_growth: self.assertTrue(after.startswith(data))
            else: self.assertEqual(after, data)

    def test_T_EVAL_37_toy_project_end_to_end(self):
        """T-EVAL-37: shout project runs, stores, shows, boards, cards, and keeps traces private."""
        self.require_evals()
        self.install_suts()
        shout_rows = [
            {"id": "e1", "input": "hello", "expected": "HELLO!", "tags": ["basic"]},
            {"id": "e2", "input": "World", "expected": "WORLD!", "tags": ["basic"]},
            {"id": "e3", "input": "", "expected": "!", "tags": ["edge"]},
            {"id": "e4", "input": "ok go", "expected": "OK GO!", "tags": ["basic"]},
            {"id": "e5", "input": "stop", "expected": "STOP?", "tags": ["edge"]},
        ]
        shout = self.eval_set("shout", "Shout", cmd="%s bin/shout.py" % PYTHON,
            timeout=1, targets={"accuracy": ">=0.8", "p95_s": "<=1", "cost_per_example": "<=0.002"})
        strict = self.eval_set("strict", "strict", file_name="evals/shout.jsonl",
            cmd="%s bin/shout.py" % PYTHON, timeout=1, targets={"accuracy": ">=1"})
        self.configure([shout, strict]); self.write_examples(shout_rows, "shout.jsonl")
        build = self.new_build()
        first = self.run_factory("eval", "run", "shout")
        self.assertEqual(first.returncode, 0)
        self.assertIn("eval shout: 4 of 5 passed, accuracy 0.8000 (target >=0.8 met)", first.stdout)
        self.assertIn("cost: $0.0050 total, $0.0010 per example (target <=0.002 met)", first.stdout)
        self.assertIn("failed: e5 (output differs)", first.stdout)
        self.assertTrue(first.stdout.endswith("eval shout: targets met\n"))
        second = self.run_factory("eval", "run", "strict")
        self.assertEqual(second.returncode, 1)
        self.assertTrue(second.stdout.endswith("eval strict: targets NOT met: accuracy\n"))
        for set_id in ("shout", "strict"):
            self.assertEqual(self.run_factory("eval", "show", set_id).returncode, 0)
        spans = [x for x in read_jsonl(build / "trace.jsonl") if str(x.get("step", "")).startswith("evalset.") and "end" in x]
        self.assertEqual([x["status"] for x in spans], ["done", "failed"])
        self.assertEqual(len(list((build / "evals").glob("*.jsonl"))) - 1, 2)
        self.assertEqual(len(list((build / "evals").glob("*.json"))), 2)
        self.assertEqual(len(read_jsonl(build / "evals" / "index.jsonl")), 2)
        status = self.run_factory("status").stdout
        self.assertIn("Shout", status); self.assertIn("strict", status)
        card = self.run_factory("report-card").stdout
        self.assertRegex(card, r"Evals: Shout, 4 of 5 right \(80%\), target met\. Slowest 5%: [0-9.]+ s\. Cost per example: \$0\.0010")
        self.assertIn("Evals: strict, 4 of 5 right (80%), target NOT met (needs 100%)", card)
        trace_text = (build / "trace.jsonl").read_text()
        for private in ("hello", "World", "ok go"):
            self.assertNotIn(private, trace_text)
        self.assertFalse((build / "messages").exists() and any((build / "messages").iterdir()))


class EvalImproveTests(EvalTestCase):
    def improve_fixture(self, improve=None, target=">=0.9", table=None, start=False,
                        extra_sets=None):
        rows = [{"id": "e%d" % i, "input": "in%d" % i,
                 "expected": "ok", "tags": ["hi"]} for i in range(1, 5)]
        base_table = table or {"e1": {"out": "ok"}, "e2": {"out": "ok"},
                               "e3": {"out": "bad"}, "e4": {"out": "bad"}}
        setting = self.eval_set(targets={"accuracy": target})
        sets = [setting] + list(extra_sets or [])
        build = self.command_fixture(rows=rows, table=base_table, sets=sets,
                                     improve=improve or {"max_rounds": 3,
                                                         "max_minutes": 30,
                                                         "stall_rounds": 2})
        for other in extra_sets or []:
            if other["file"] != setting["file"]:
                self.write_examples(rows, Path(other["file"]).name)
        baseline = self.run_factory("eval", "run", "greet")
        self.assertIn(baseline.returncode, (0, 1), baseline.stdout + baseline.stderr)
        self.init_git()
        if start:
            result = self.run_factory("eval", "improve", "start", "greet")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return build, rows, base_table

    def test_T_EVAL_38_diagnose_grouping(self):
        """T-EVAL-38: diagnosis groups fixed classes, sorts, caps ids, and finds weak tags."""
        e = self.require_evals()
        rows = [
            {"id": "e1", "pass": False, "reason": "output differs", "tags": ["a"]},
            {"id": "e2", "pass": False, "reason": "output differs", "tags": ["a", "b"]},
            {"id": "e3", "pass": False, "reason": "timed out after 2 s", "tags": ["b"]},
            {"id": "e4", "pass": False, "reason": "runner exit 3", "tags": ["b"]},
            {"id": "e5", "pass": False, "reason": "runner exit -9", "tags": []},
            {"id": "e6", "pass": False, "reason": "missing expected text 2 of 3", "tags": ["a"]},
            {"id": "e7", "pass": False, "reason": "expected must be a number", "tags": ["c"]},
            {"id": "e8", "pass": True, "reason": "ok", "tags": ["a"]},
            {"id": "e9", "pass": True, "reason": "ok", "tags": ["x"]},
            {"id": "e10", "pass": True, "reason": "ok", "tags": []},
        ]
        diag = e.diagnose(rows)
        self.assertEqual((diag["n"], diag["failed"]), (10, 7))
        self.assertEqual([(g["class"], g["count"]) for g in diag["groups"]],
                         [("output differs", 2), ("runner exit", 2), ("bad example", 1),
                          ("missing expected text", 1), ("timed out", 1)])
        self.assertEqual(diag["groups"][0], {"class": "output differs", "count": 2,
                                             "ids": ["e1", "e2"],
                                             "tags": [["a", 2], ["b", 1]]})
        self.assertEqual(diag["weak_spot"], {"tag": "b", "passed": 0, "n": 3})
        text = e.diagnose_text(diag, "greet", .3, ">=0.9", 3, 10)
        self.assertIn("note: the example file may be wrong (the builder may not edit it): tell the owner", text)

        tie = [{"id": "x", "pass": False, "reason": "output differs", "tags": ["x"]},
               {"id": "y", "pass": False, "reason": "output differs", "tags": ["y"]}]
        self.assertEqual(e.diagnose(tie)["weak_spot"]["tag"], "x")
        tie.append({"id": "y2", "pass": False, "reason": "output differs", "tags": ["y"]})
        self.assertEqual(e.diagnose(tie)["weak_spot"]["tag"], "y")
        many = [{"id": "e%d" % i, "pass": False, "reason": "output differs", "tags": []}
                for i in range(12)]
        many_text = "\n".join(e.diagnose_text(e.diagnose(many), "greet", 0, None, 0, 12))
        self.assertIn("and 2 more", many_text)
        none = e.diagnose([{"id": "p", "pass": True, "reason": "ok", "tags": ["x"]}])
        self.assertEqual(none["groups"], []); self.assertIsNone(none["weak_spot"])
        self.assertIn("nothing failed in the latest run",
                      e.diagnose_text(none, "greet", 1, None, 1, 1))
        class_cases = {
            "outside tolerance (got 3 wanted 4)": "outside tolerance",
            "missing field a.b": "missing field", "field a.b differs": "field differs",
            "bad field path": "bad example", "output too large": "output too large",
            "unexpected": "other",
        }
        for reason, wanted in class_cases.items():
            one = e.diagnose([{"id": "x", "pass": False, "reason": reason, "tags": []}])
            self.assertEqual(one["groups"][0]["class"], wanted)

    def test_T_EVAL_39_diagnose_command(self):
        """T-EVAL-39: diagnose is read-only, exact, private, supports no-run/pass/no-target."""
        self.require_evals()
        rows = [{"id": "g1", "input": "SENTINEL_IN_77", "expected": "SENTINEL_EXP_88", "tags": ["hi"]},
                {"id": "g2", "input": "SENTINEL_IN_77", "expected": "SENTINEL_EXP_88", "tags": ["hi"]}]
        table = {"g1": {"out": "SENTINEL_EXP_88"}, "g2": {"out": "wrong"}}
        setting = self.eval_set(targets={"accuracy": ">=0.9"})
        build = self.command_fixture(rows=rows, table=table, sets=[setting])
        no_run = self.run_factory("eval", "diagnose", "greet")
        self.assertEqual(no_run.returncode, 4)
        self.assertEqual(no_run.stderr, "factory: no eval run recorded for 'greet' in this build.\n")
        self.run_factory("eval", "run", "greet")
        before = tree_snapshot(build)
        result = self.run_factory("eval", "diagnose", "greet")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout,
            "diagnosis greet (latest run 1 of 2, accuracy 0.5000, target >=0.9)\n"
            "  1 failed: output differs: 1 (g2)\n"
            "reason groups:\n"
            "  output differs  1 of 1  ids: g2  tags: hi(1)\n"
            "weak spot: tag hi (1 of 2 right)\n")
        self.assertEqual(tree_snapshot(build), before)
        self.assertNotIn("SENTINEL", result.stdout + result.stderr)
        self.assertFalse(any(x in result.stdout.lower() for x in ("span", "iteration", "node", "rubric", "evalset")))
        self.write_table({"g1": {"out": "SENTINEL_EXP_88"}, "g2": {"out": "SENTINEL_EXP_88"}})
        self.run_factory("eval", "run", "greet")
        self.assertIn("nothing failed in the latest run",
                      self.run_factory("eval", "diagnose", "greet").stdout)
        setting["targets"] = {"p95_s": "<=1"}; self.configure([setting])
        self.assertIn("target none", self.run_factory("eval", "diagnose", "greet").stdout)

    def test_T_EVAL_40_decide_round_rules(self):
        """T-EVAL-40: keep-or-revert rules are complete and first-match ordered."""
        e = self.require_evals()
        kept = {"sets": {
            "greet": {"accuracy": .5, "targets": {"accuracy": False, "p95_s": True},
                      "targets_text": {"accuracy": ">=0.9", "p95_s": "<=1.5"}},
            "other": {"accuracy": .8, "targets": {"accuracy": True},
                      "targets_text": {"accuracy": ">=0.5"}}},
            "pass": {"a": True, "b": True, "c": False, "d": False}}
        protected = ["factory.json", "evals/greet.jsonl"]

        def candidate(score=.75):
            value = copy.deepcopy(kept)
            value["sets"]["greet"]["accuracy"] = score
            value["pass"] = {"a": True, "b": True, "c": score > .5, "d": False}
            return value

        cases = []
        cases.append((candidate(), True, 0, ["src/p.py"], ("revert", "no change made")))
        cases.append((candidate(), True, 2, ["src/p.py"], ("revert", "more than one change")))
        cases.append((candidate(), True, 1, ["evals/greet.jsonl"], ("revert", "eval files or settings changed")))
        cases.append((candidate(), True, 1, ["factory.json"], ("revert", "eval files or settings changed")))
        lowered = candidate(); lowered["sets"]["greet"]["targets_text"]["accuracy"] = ">=0.4"
        cases.append((lowered, True, 1, ["src/p.py"], ("revert", "eval files or settings changed")))
        cases.append((candidate(), False, 2, protected, ("revert", "more than one change")))
        cases.append((candidate(), False, 1, protected, ("revert", "eval files or settings changed")))
        cases.append((candidate(), False, 1, ["src/p.py"], ("revert", "tests or metrics failed")))
        broke = candidate(); broke["pass"]["a"] = False
        cases.append((broke, True, 1, ["src/p.py"], ("revert", "a passing example now fails")))
        other_worse = candidate(); other_worse["sets"]["other"]["accuracy"] = .7
        cases.append((other_worse, True, 1, ["src/p.py"], ("revert", "another set got worse")))
        metric_worse = candidate(); metric_worse["sets"]["greet"]["targets"]["p95_s"] = False
        cases.append((metric_worse, True, 1, ["src/p.py"], ("revert", "a met target is now missed")))
        cases.append((candidate(.5), True, 1, ["src/p.py"], ("revert", "no gain")))
        swapped = candidate(.5); swapped["pass"] = {"a": True, "b": False, "c": True, "d": False}
        cases.append((swapped, True, 1, ["src/p.py"], ("revert", "a passing example now fails")))
        cases.append((candidate(), True, 1, ["src/p.py"], ("keep", "score improved")))
        improved_other = candidate(); improved_other["sets"]["other"]["accuracy"] = .9
        cases.append((improved_other, True, 1, ["src/p.py"], ("keep", "score improved")))
        cases.append((candidate(), False, 2, ["src/p.py"], ("revert", "more than one change")))
        for cand, suite, commits, paths, wanted in cases:
            self.assertEqual(e.decide_round(kept, cand, suite, commits, paths, protected, "greet"), wanted)

    def test_T_EVAL_41_replay_and_stop_rules(self):
        """T-EVAL-41: replay is deterministic/torn-line-safe and stop precedence uses kept state."""
        e = self.require_evals()
        baseline = {"sets": {"greet": {"accuracy": .5, "targets": {"accuracy": False},
                                         "targets_text": {"accuracy": ">=0.9"}}},
                    "pass": {"a": True, "b": False}}
        improved = copy.deepcopy(baseline); improved["sets"]["greet"]["accuracy"] = .75
        improved["pass"]["b"] = True
        lines = [
            {"ev": "start", "ts": "2026-11-25T18:00:00Z", "set": "greet",
             "limits": {"max_rounds": 3, "max_minutes": 30, "stall_rounds": 2},
             "baseline": baseline},
            {"ev": "round_start", "n": 1, "ts": "2026-11-25T18:01:00Z", "head": "a", "index_lines": 1},
            {"ev": "round", "n": 1, "decision": "keep", "reason": "score improved",
             "commits": 1, "sha": "b", "accuracy_before": .5, "accuracy_after": .75,
             "text": "Improved it", "suite": "ok", "index_lines": 2, "cand": improved},
            {"ev": "round_start", "n": 2, "ts": "2026-11-25T18:02:00Z", "head": "b", "index_lines": 2},
            {"ev": "round", "n": 2, "decision": "revert", "reason": "no gain",
             "commits": 0, "sha": "b", "accuracy_before": .75, "accuracy_after": .75,
             "text": "", "suite": "ok", "index_lines": 2},
            {"ev": "stop", "reason": "no progress"},
        ]
        state = e.replay(lines)
        self.assertEqual(len(state["rounds"]), 2)
        self.assertEqual(state["kept"], improved)
        self.assertEqual(state["stopped"], "no progress")
        self.assertIsNone(state["open_round"])
        self.assertEqual(e.replay(lines), e.replay(lines))
        self.assertEqual(e.replay(lines + ["{broken"]), state)
        open_state = e.replay(lines[:4])
        self.assertEqual(open_state["open_round"], 2)
        self.assertIsNone(e.replay(lines[:-1])["stopped"])

        def state_for(round_decisions=(), met=False, max_rounds=3, max_minutes=30, stall=2):
            value = {"limits": {"max_rounds": max_rounds, "max_minutes": max_minutes,
                                "stall_rounds": stall}, "start_ts": 0, "set_id": "greet",
                     "rounds": [{"decision": d} for d in round_decisions],
                     "kept": copy.deepcopy(baseline)}
            value["kept"]["sets"]["greet"]["targets"]["accuracy"] = met
            return value

        self.assertEqual(e.stop_reason(state_for(["revert"] * 3, met=True), 99999), "target met")
        self.assertEqual(e.stop_reason(state_for(["keep"] * 3), 0), "round limit")
        self.assertEqual(e.stop_reason(state_for(["keep"], max_rounds=5), 1800), "time limit")
        self.assertEqual(e.stop_reason(state_for(["keep"], max_rounds=5), 1799), "continue")
        self.assertEqual(e.stop_reason(state_for(["keep", "revert", "revert"], max_rounds=5), 0), "no progress")
        self.assertEqual(e.stop_reason(state_for(["revert", "keep", "revert"], max_rounds=5), 0), "continue")
        self.assertEqual(e.stop_reason(state_for(["revert"] * 2, max_rounds=5, stall=3), 0), "continue")
        self.assertEqual(e.stop_reason(state_for(["revert"] * 3, max_rounds=5, stall=3), 0), "no progress")
        self.assertEqual(e.stop_reason(state_for([], max_rounds=5), 0), "continue")

    def test_T_EVAL_42_improve_settings(self):
        """T-EVAL-42: defaults and positive numeric limits validate and freeze at start."""
        self.require_evals()
        bad_values = [("max_rounds", x) for x in (0, -1, 1.5, "3", True)]
        bad_values += [("max_minutes", x) for x in (0, -5, "x", True)]
        bad_values += [("stall_rounds", x) for x in (0, 2.5)]
        for i, (key, value) in enumerate(bad_values):
            folder = self.tmp / ("improve-bad-%d" % i); folder.mkdir()
            self.configure(improve={key: value}, folder=folder)
            result = self.run_factory("eval", "show", "greet", cwd=folder)
            self.assertEqual(result.returncode, 2)
            self.assertIn("factory.json", result.stderr); self.assertIn("evals.improve", result.stderr)
            self.assertIn(key, result.stderr)
        folder = self.tmp / "improve-list"; folder.mkdir()
        value = self.configure(folder=folder); value["evals"]["improve"] = []
        write_json(folder / "factory.json", value)
        result = self.run_factory("eval", "show", "greet", cwd=folder)
        self.assertEqual(result.returncode, 2); self.assertIn("evals.improve", result.stderr)

        build, _, _ = self.improve_fixture(improve={"max_minutes": .5, "unknown": 7})
        started = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(started.returncode, 0)
        self.assertRegex(started.stdout, r"session greet-[^:]+: limits 3 rounds, 0\.5 min, stop after 2 without gain")
        config = json.loads((self.project / "factory.json").read_text())
        config["evals"]["improve"] = {"max_rounds": 99, "max_minutes": 99, "stall_rounds": 99}
        write_json(self.project / "factory.json", config)
        next_result = self.run_factory("eval", "improve", "next", "greet")
        self.assertEqual(next_result.stdout, "continue (round 1)\n")
        log = next((build / "evals" / "improve").glob("greet-*.jsonl"))
        self.assertEqual(read_jsonl(log)[0]["limits"],
                         {"max_rounds": 3, "max_minutes": .5, "stall_rounds": 2})

    def test_T_EVAL_43_start_preconditions_and_tracked_files(self):
        """T-EVAL-43: start order includes clean git plus binding tracked-config/eval erratum."""
        self.require_evals()
        build = self.command_fixture(table={"e1": {"out": "wrong"}})
        self.run_factory("eval", "run", "greet")
        not_git = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(not_git.returncode, 2)
        self.assertEqual(not_git.stderr, "factory: improve needs a git project with no uncommitted changes.\n")

        env = self.init_git(tracked=False)
        untracked = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(untracked.returncode, 2)
        self.assertEqual(untracked.stderr,
                         "factory: improve needs factory.json and the eval files tracked by git.\n")
        self.git("add", "factory.json", "evals", "bin", cwd=self.project, env=env)
        self.git("commit", "-m", "baseline", cwd=self.project, env=env)
        tracked_file = self.project / "bin" / "fake_sut.py"
        tracked_file.write_text(tracked_file.read_text() + "\n# dirty\n")
        dirty = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(dirty.returncode, 2)
        self.assertEqual(dirty.stderr, "factory: improve needs a git project with no uncommitted changes.\n")
        # Restore with a new commit, preserving history rather than destructive checkout.
        self.git("add", "bin/fake_sut.py", env=env); self.git("commit", "-m", "record test change", env=env)

        no_run_build = self.new_build("no-run")
        no_run = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(no_run.returncode, 4)
        self.assertEqual(no_run.stderr, "factory: no eval run recorded for 'greet' in this build.\n")
        self.assertTrue(no_run_build.exists())

        self.write_table({"e1": {"out": "x"}})
        met_build = self.new_build("met")
        self.assertEqual(self.run_factory("eval", "run", "greet").returncode, 0)
        met = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(met.returncode, 4)
        self.assertEqual(met.stderr, "factory: 'greet' already meets its target. Nothing to improve.\n")
        self.assertTrue(met_build.exists())

        speed_setting = self.eval_set(targets={"accuracy": ">=0.5", "p95_s": "<0"})
        self.configure([speed_setting]); self.git("add", "factory.json", env=env)
        self.git("commit", "-m", "record speed target", env=env)
        speed_build = self.new_build("speed-miss")
        self.assertEqual(self.run_factory("eval", "run", "greet").returncode, 1)
        speed = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(speed.returncode, 4)
        self.assertEqual(speed.stderr, "factory: improve works on a missed accuracy target only.\n")
        self.assertTrue(speed_build.exists())

        speed_only_setting = self.eval_set(targets={"p95_s": "<0"})
        self.configure([speed_only_setting]); self.git("add", "factory.json", env=env)
        self.git("commit", "-m", "record speed-only target", env=env)
        speed_only_build = self.new_build("speed-only")
        self.assertEqual(self.run_factory("eval", "run", "greet").returncode, 1)
        speed_only = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(speed_only.returncode, 4)
        self.assertEqual(speed_only.stderr,
                         "factory: improve works on a missed accuracy target only.\n")
        self.assertTrue(speed_only_build.exists())

        missing_home = self.tmp / "missing-build-home"; missing_home.mkdir()
        old_home = self.env["FACTORY_HOME"]
        old_build = self.env.pop("FACTORY_BUILD", None)
        self.env["FACTORY_HOME"] = str(missing_home)
        try:
            missing = self.run_factory("eval", "improve", "start", "greet")
            self.assertEqual(missing.returncode, 3)
            self.assertTrue(missing.stderr.startswith("factory: no build selected."))
        finally:
            self.env["FACTORY_HOME"] = old_home
            if old_build is not None:
                self.env["FACTORY_BUILD"] = old_build

        self.configure([self.eval_set(targets={"accuracy": ">=0.9"})])
        self.git("add", "factory.json", env=env); self.git("commit", "-m", "restore accuracy target", env=env)
        self.select("toy", "b1")
        started = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.assertRegex(started.stdout, r"^session greet-[^:]+: limits 3 rounds, 30 min, stop after 2 without gain\n$")
        logs = list((build / "evals" / "improve").glob("greet-*.jsonl"))
        self.assertEqual(len(logs), 1)
        first = read_jsonl(logs[0]); self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["ev"], "start")
        self.assertEqual(first[0]["head"], self.git("rev-parse", "HEAD", env=env))
        self.assertEqual(first[0]["limits"], {"max_rounds": 3, "max_minutes": 30, "stall_rounds": 2})
        self.assertEqual(first[0]["baseline"]["pass"], {"e1": False})
        tracked_file.write_text(tracked_file.read_text() + "# dirty again\n")
        reused = self.run_factory("eval", "improve", "start", "greet")
        self.assertEqual(reused.returncode, 0)
        self.assertRegex(reused.stdout, r"session greet-[^ ]+ continues at round 1")
        self.assertEqual(len(read_jsonl(logs[0])), 1)
        no_log = self.run_factory("eval", "improve", "start", "greet", "--no-log")
        self.assertEqual(no_log.returncode, 2)

    def test_T_EVAL_44_next_status_decide_errors(self):
        """T-EVAL-44: no-session/open-round/suite/stopped errors and time/round stops are exact."""
        self.require_evals()
        build, _, _ = self.improve_fixture()
        for args in (("next", "greet"), ("status", "greet"), ("report", "greet"),
                     ("brief", "greet", "researcher"), ("decide", "greet", "--suite", "ok")):
            result = self.run_factory("eval", "improve", *args)
            self.assertEqual(result.returncode, 4)
            self.assertEqual(result.stderr, "factory: no improve session for 'greet' in this build.\n")
        self.assertEqual(self.run_factory("eval", "improve", "start", "greet").returncode, 0)
        no_round = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(no_round.returncode, 2)
        self.assertEqual(no_round.stderr, "factory: run 'factory eval improve next greet' first.\n")
        first = self.run_factory("eval", "improve", "next", "greet")
        self.assertEqual(first.stdout, "continue (round 1)\n")
        log = next((build / "evals" / "improve").glob("greet-*.jsonl"))
        count = len(read_jsonl(log))
        again = self.run_factory("eval", "improve", "next", "greet")
        self.assertEqual(again.stdout, "continue (round 1)\n")
        self.assertEqual(len(read_jsonl(log)), count)
        status = self.run_factory("eval", "improve", "status", "greet")
        self.assertRegex(status.stdout, r"session greet-.*: round 1 of 3, 0 of 30 min, kept 0, score 50% \(target 90%\), running")
        for suite_args in ((), ("--suite", "maybe")):
            result = self.run_factory("eval", "improve", "decide", "greet", *suite_args)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stderr, "factory: --suite ok|failed is required.\n")

        # A separate session reaches the time limit through next with no open round.
        timed_home = self.tmp / "timed-home"; timed_home.mkdir()
        old_home = self.env["FACTORY_HOME"]; self.env["FACTORY_HOME"] = str(timed_home)
        try:
            timed_build = self.new_build("timed")
            self.run_factory("eval", "run", "greet")
            self.run_factory("eval", "improve", "start", "greet")
            self.env["FACTORY_NOW"] = "2026-01-10T12:43:00Z"
            stopped = self.run_factory("eval", "improve", "next", "greet")
            self.assertEqual(stopped.stdout, "stop: time limit\n")
            self.assertTrue(self.run_factory("eval", "improve", "status", "greet").stdout.rstrip().endswith("stopped: time limit"))
            after = self.run_factory("eval", "improve", "next", "greet")
            self.assertEqual(after.returncode, 4)
            self.assertEqual(after.stderr, "factory: the session for 'greet' has stopped.\n")
            self.assertEqual(self.run_factory("eval", "improve", "report", "greet").returncode, 0)
            self.assertTrue(timed_build.exists())
        finally:
            self.env["FACTORY_HOME"] = old_home

    def test_T_EVAL_45a_full_session_and_undo_rule(self):
        """T-EVAL-45a: three rounds keep/revert/stall, enforce undo+rereun, and log four eval spans."""
        self.require_evals()
        build, _, table = self.improve_fixture(improve={"max_rounds": 5, "max_minutes": 30,
                                                        "stall_rounds": 2}, start=True)
        self.assertEqual(self.run_factory("eval", "improve", "next", "greet").stdout,
                         "continue (round 1)\n")
        table["e3"]["out"] = "ok"; self.write_table(table)
        self.git("add", "table.json"); self.git("commit", "-m", "improve(greet) r1: Fixed the date parser.")
        self.env["FACTORY_NOW"] = "2026-01-10T12:14:00Z"
        self.assertEqual(self.run_factory("eval", "run", "greet").returncode, 1)
        decide1 = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(decide1.stdout, "kept: score improved\nnext: continue\n")
        self.assertEqual(self.run_factory("eval", "improve", "next", "greet").stdout,
                         "continue (round 2)\n")

        table["e4"]["out"] = "ok"; table["e1"]["out"] = "bad"; self.write_table(table)
        self.git("add", "table.json"); self.git("commit", "-m", "improve(greet) r2: Simplified the number cleanup.")
        round2_sha = self.git("rev-parse", "HEAD")
        self.env["FACTORY_NOW"] = "2026-01-10T12:16:00Z"
        self.run_factory("eval", "run", "greet")
        decide2 = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(decide2.stdout,
            "reverted: a passing example now fails\nundo with: git revert --no-edit %s\nnext: continue\n" % round2_sha)
        for command in (("next", "greet"), ("report", "greet")):
            blocked = self.run_factory("eval", "improve", *command)
            self.assertEqual(blocked.returncode, 2)
            self.assertEqual(blocked.stderr, "factory: undo the last change and rerun the evals first.\n")
        self.git("revert", "--no-edit", round2_sha)
        blocked = self.run_factory("eval", "improve", "next", "greet")
        self.assertEqual(blocked.returncode, 2)
        self.env["FACTORY_NOW"] = "2026-01-10T12:18:00Z"
        self.run_factory("eval", "run", "greet")
        self.assertEqual(self.run_factory("eval", "improve", "next", "greet").stdout,
                         "continue (round 3)\n")
        decide3 = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(decide3.stdout,
                         "reverted: no change made\nnext: stop: no progress\n")
        log = next((build / "evals" / "improve").glob("greet-*.jsonl"))
        events = read_jsonl(log)
        rounds = [x for x in events if x["ev"] == "round"]
        self.assertEqual([(x["decision"], x["reason"]) for x in rounds],
                         [("keep", "score improved"), ("revert", "a passing example now fails"),
                          ("revert", "no change made")])
        self.assertEqual((rounds[0]["accuracy_before"], rounds[0]["accuracy_after"], rounds[0]["text"]),
                         (.5, .75, "Fixed the date parser"))
        stop = events[-1]
        self.assertEqual((stop["reason"], stop["rounds"], stop["accuracy_start"],
                          stop["accuracy_end"], stop["met"]),
                         ("no progress", 3, .5, .75, False))
        closes = [x for x in read_jsonl(build / "trace.jsonl") if x.get("end")]
        improve_spans = [x for x in closes if str(x.get("step", "")).startswith("improve.greet.r")]
        eval_spans = [x for x in closes if x.get("step") == "evalset.greet"]
        self.assertEqual(len(improve_spans), 3)
        self.assertEqual([(x["improve_round"], x["improve_kept"], x["improve_reason"])
                          for x in improve_spans],
                         [(1, True, "score improved"), (2, False, "a passing example now fails"),
                          (3, False, "no change made")])
        # Binding erratum r3: baseline, r1, r2, after undo = four, not five.
        self.assertEqual(len(eval_spans), 4)
        trace_text = (build / "trace.jsonl").read_text()
        self.assertNotIn("Fixed the date parser", trace_text)
        self.assertNotIn("Simplified the number cleanup", trace_text)

    def test_T_EVAL_45b_single_rule_command_checks(self):
        """T-EVAL-45b: rerun/commit/suite/protected/dirty/regression rules and relative paths."""
        self.require_evals()
        build, _, table = self.improve_fixture(start=True)
        self.run_factory("eval", "improve", "next", "greet")
        table["e3"]["out"] = "ok"; self.write_table(table)
        self.git("add", "table.json"); self.git("commit", "-m", "improve(greet) r1: Improved output.")
        no_rerun = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(no_rerun.returncode, 2)
        self.assertEqual(no_rerun.stderr, "factory: rerun the evals first.\n")
        self.run_factory("eval", "run", "greet")
        suite = self.run_factory("eval", "improve", "decide", "greet", "--suite", "failed")
        self.assertIn("reverted: tests or metrics failed", suite.stdout)

        # Dirty tracked tree is rejected before decision.
        dirty_build, _, _ = self._fresh_improve_home("dirty")
        dirty_file = self.project / "bin" / "fake_sut.py"
        dirty_file.write_text(dirty_file.read_text() + "# uncommitted\n")
        dirty = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(dirty.returncode, 2)
        self.assertEqual(dirty.stderr, "factory: commit or undo uncommitted changes first.\n")
        self.assertTrue(dirty_build.exists())

        # Protected eval edit is caught. This also uses a project below the repo root,
        # exercising binding erratum r3's git diff --relative behavior.
        old_project = self.project
        repo = self.tmp / "parent-repo"; sub = repo / "app"; sub.mkdir(parents=True)
        self.project = sub
        try:
            self.install_suts(); self.configure(); self.write_examples([{"id": "e1", "input": "x", "expected": "bad"}])
            self.write_table({"e1": {"out": "ok"}})
            sub_build = self.new_build("subfolder")
            self.run_factory("eval", "run", "greet")
            env = self.git_env(); self.git("init", cwd=repo, env=env)
            self.git("add", "app/factory.json", "app/evals", "app/bin", cwd=repo, env=env)
            self.git("commit", "-m", "baseline", cwd=repo, env=env); self.env.update(env)
            self.run_factory("eval", "improve", "start", "greet")
            self.run_factory("eval", "improve", "next", "greet")
            self.write_examples([{"id": "e1", "input": "x", "expected": "ok"}])
            self.git("add", "app/evals/greet.jsonl", cwd=repo, env=env)
            self.git("commit", "-m", "improve(greet) r1: Changed answers.", cwd=repo, env=env)
            self.run_factory("eval", "run", "greet")
            protected = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
            self.assertIn("reverted: eval files or settings changed", protected.stdout)
            self.assertTrue(sub_build.exists())
        finally:
            self.project = old_project

    def _fresh_improve_home(self, name):
        new_home = self.tmp / (name + "-factory-home"); new_home.mkdir()
        self.env["FACTORY_HOME"] = str(new_home)
        build = self.new_build(name)
        self.run_factory("eval", "run", "greet")
        self.run_factory("eval", "improve", "start", "greet")
        self.run_factory("eval", "improve", "next", "greet")
        return build, None, None

    def test_T_EVAL_45c_target_met(self):
        """T-EVAL-45c: a kept target-reaching round stops from kept state and reports it."""
        self.require_evals()
        build, _, table = self.improve_fixture(start=True)
        self.run_factory("eval", "improve", "next", "greet")
        table["e3"]["out"] = "ok"; table["e4"]["out"] = "ok"; self.write_table(table)
        self.git("add", "table.json"); self.git("commit", "-m", "improve(greet) r1: Fixed all outputs.")
        self.run_factory("eval", "run", "greet")
        decided = self.run_factory("eval", "improve", "decide", "greet", "--suite", "ok")
        self.assertEqual(decided.stdout, "kept: score improved\nnext: stop: target met\n")
        log = next((build / "evals" / "improve").glob("greet-*.jsonl"))
        stop = read_jsonl(log)[-1]
        self.assertEqual((stop["met"], stop["accuracy_end"]), (True, 1.0))
        self.assertTrue(self.run_factory("eval", "improve", "status", "greet").stdout.rstrip().endswith("stopped: target met"))
        self.assertTrue(self.run_factory("eval", "improve", "report", "greet").stdout.rstrip().endswith(
            "Stopped because: the target was reached."))

    def test_T_EVAL_46_report_and_card(self):
        """T-EVAL-46: improve report/card use kept scores, plain prose, pluralization, and stop text."""
        self.require_evals()
        build = self.command_fixture(improve={"max_rounds": 5, "max_minutes": 30, "stall_rounds": 2})
        self.run_factory("eval", "run", "greet")
        improve_dir = build / "evals" / "improve"; improve_dir.mkdir(parents=True)
        baseline = {"sets": {"greet": {"accuracy": .5, "targets": {"accuracy": False},
                                         "targets_text": {"accuracy": ">=0.9"}}},
                    "pass": {"e1": True, "e2": True, "e3": False, "e4": False}}
        kept = copy.deepcopy(baseline); kept["sets"]["greet"]["accuracy"] = .75
        kept["pass"]["e3"] = True
        events = [
            {"ev": "start", "ts": "2026-11-25T18:00:00Z", "set": "greet", "head": "a",
             "limits": {"max_rounds": 5, "max_minutes": 30, "stall_rounds": 2}, "baseline": baseline},
            {"ev": "round", "n": 1, "decision": "keep", "reason": "score improved", "commits": 1,
             "sha": "b", "accuracy_before": .5, "accuracy_after": .75,
             "text": "Fixed the date parser", "suite": "ok", "index_lines": 2, "cand": kept},
            {"ev": "round", "n": 2, "decision": "revert", "reason": "a passing example now fails", "commits": 1,
             "sha": "c", "accuracy_before": .75, "accuracy_after": .75,
             "text": "Simplified the number cleanup", "suite": "ok", "index_lines": 3},
            {"ev": "round", "n": 3, "decision": "revert", "reason": "no change made", "commits": 0,
             "sha": "c", "accuracy_before": .75, "accuracy_after": .75,
             "text": "", "suite": "ok", "index_lines": 4},
            {"ev": "stop", "ts": "2026-11-25T18:10:00Z", "reason": "no progress", "rounds": 3,
             "accuracy_start": .5, "accuracy_end": .75, "met": False},
        ]
        write_jsonl(improve_dir / "greet-20261125T180000Z.jsonl", events)
        report = self.run_factory("eval", "improve", "report", "greet")
        self.assertEqual(report.returncode, 0)
        self.assertEqual(report.stdout,
            "Greeting answers: tried to improve it in 3 rounds. Score went from 50% to 75%; the target is 90%.\n"
            "Round 1: Fixed the date parser. Score 50% to 75%. Kept.\n"
            "Round 2: Simplified the number cleanup. Score stayed at 75%. Undone: a passing example now fails.\n"
            "Round 3: No change made. Undone: no change made.\n"
            "Stopped because: 2 rounds in a row did not improve it.\n")
        card = self.run_factory("report-card").stdout
        self.assertIn("Tried to improve: 3 rounds, 50% to 75%.", card)
        self.assertLessEqual(len(card.splitlines()), 30)
        self.assertFalse(any(word in card.lower() for word in ("span", "iteration", "node", "rubric", "evalset")))
        running = events[:-1]; write_jsonl(improve_dir / "greet-20261125T180001Z.jsonl", running)
        self.assertTrue(self.run_factory("eval", "improve", "report", "greet").stdout.rstrip().endswith("Still running."))

    def test_T_EVAL_47_private_deterministic_briefs(self):
        """T-EVAL-47: researcher/builder briefs contain only allowed paths, rules, and diagnosis."""
        self.require_evals()
        other = self.eval_set("other", "Other", targets={"accuracy": ">=0.5"})
        build, _, _ = self.improve_fixture(extra_sets=[other], start=True)
        no_open = self.run_factory("eval", "improve", "brief", "greet", "researcher")
        self.assertEqual(no_open.returncode, 2)
        self.assertEqual(no_open.stderr, "factory: run 'factory eval improve next greet' first.\n")
        self.run_factory("eval", "improve", "next", "greet")
        before = tree_snapshot(build)
        researcher = self.run_factory("eval", "improve", "brief", "greet", "researcher")
        again = self.run_factory("eval", "improve", "brief", "greet", "researcher")
        self.assertEqual(researcher.returncode, 0); self.assertEqual(researcher.stdout, again.stdout)
        self.assertIn("diagnosis greet", researcher.stdout)
        self.assertIn("Greeting answers", researcher.stdout); self.assertIn(">=0.9", researcher.stdout)
        self.assertIn(str(self.project), researcher.stdout)
        self.assertIn("do not open", researcher.stdout.lower())
        self.assertIn("evals/greet.jsonl", researcher.stdout); self.assertIn("evals/other.jsonl", researcher.stdout)
        self.assertNotRegex(researcher.stdout, r"evals/greet-[0-9TZ-]+\.jsonl")
        self.assertNotIn("SENTINEL_IN_77", researcher.stdout); self.assertNotIn("SENTINEL_EXP_88", researcher.stdout)
        self.assertEqual(tree_snapshot(build), before)

        builder = self.run_factory("eval", "improve", "brief", "greet", "builder")
        self.assertEqual(builder.returncode, 0)
        self.assertIn("diagnosis greet", builder.stdout)
        self.assertIn("r1-research.md", builder.stdout)
        self.assertRegex(builder.stdout, r"evals/greet-[0-9TZ-]+\.jsonl")
        for phrase in ("improve(greet) r1:", "one change", "never edit", "factory.json", "locked test"):
            self.assertIn(phrase.lower(), builder.stdout.lower())
        self.assertNotIn("SENTINEL", builder.stdout)
