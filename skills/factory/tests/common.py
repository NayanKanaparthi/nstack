"""Shared, stdlib-only helpers for factory kit acceptance tests."""

import contextlib
import importlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


TESTS_DIR = Path(__file__).resolve().parent
KIT_DIR = TESTS_DIR.parent
REPO_ROOT = KIT_DIR.parents[1]
SCRIPTS_DIR = KIT_DIR / "scripts"
FACTORY_PY = SCRIPTS_DIR / "factory.py"
FIXTURES = TESTS_DIR / "fixtures"
PYTHON = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
COMMANDS = (
    "init", "new", "phase", "log", "run", "step", "wait", "gate", "check",
    "status", "preflight", "trace-report", "report-card",
)


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_jsonl(path, values):
    Path(path).write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))


def tree_snapshot(root):
    root = Path(root)
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def board_strings(value, key=""):
    """Yield human-facing strings from a board without treating raw ids as labels."""
    if isinstance(value, dict):
        for child_key, child in value.items():
            if child_key in {"key", "piece", "piece_id", "id"}:
                continue
            yield from board_strings(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from board_strings(child, key)
    elif isinstance(value, str) and (
            key.endswith("_label") or key in {"question", "recommend", "text", "warnings"}):
        yield value


class FactoryTestCase(unittest.TestCase):
    """Give every test an isolated HOME and FACTORY_HOME."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="factory-test-")
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.factory_home = self.tmp / "factory-home"
        self.project = self.tmp / "project"
        self.home.mkdir()
        self.factory_home.mkdir()
        self.project.mkdir()
        self.env = dict(os.environ)
        self.env.update({
            "HOME": str(self.home),
            "FACTORY_HOME": str(self.factory_home),
            "PYTHONDONTWRITEBYTECODE": "1",
            "FACTORY_NOW": "2026-01-10T12:12:00Z",
        })
        for key in (
                "FACTORY_BUILD", "FACTORY_CLAUDE_BIN", "FACTORY_CODEX_BIN",
                "FACTORY_OPENCODE_BIN", "FACTORY_CURSOR_BIN", "FACTORY_OLLAMA_URL",
                "FACTORY_PMSET_BIN", "FACTORY_OSASCRIPT_BIN", "FACTORY_DEBUG"):
            self.env.pop(key, None)

    def tearDown(self):
        self._tmp.cleanup()

    def require_module(self, name):
        """Import a planned module, failing clearly while implementation is absent."""
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.addCleanup(lambda: sys.path.remove(str(SCRIPTS_DIR)))
        importlib.invalidate_caches()
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as exc:
            if exc.name == name:
                self.fail("module not found: %s (planned module skills/factory/scripts/%s.py)" %
                          (name, name))
            raise

    def run_factory(self, *args, cwd=None, input_text=None, env=None, timeout=0.95):
        self.assertTrue(
            FACTORY_PY.is_file(),
            "planned command missing: skills/factory/scripts/factory.py",
        )
        child_env = dict(self.env)
        if env:
            child_env.update(env)
        try:
            return subprocess.run(
                [PYTHON, str(FACTORY_PY)] + list(args),
                cwd=str(cwd or self.project), env=child_env, input=input_text,
                stdin=None if input_text is not None else subprocess.DEVNULL,
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            self.fail("factory command exceeded the test's sub-1-second deadline: %s" % (exc,))

    def run_main(self, module_name, argv):
        module = self.require_module(module_name)
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main(list(argv))
        return code, stdout.getvalue(), stderr.getvalue()

    def install_fixture(self, name, project="demo", build=None):
        build = build or name
        source = FIXTURES / name
        target = self.factory_home / "runs" / project / build
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(source), str(target))
        return target

    def select(self, project, build, phase="build"):
        with (self.factory_home / "current.jsonl").open("a") as stream:
            stream.write(json.dumps({
                "ts": self.env["FACTORY_NOW"], "project": project,
                "build": build, "phase": phase,
            }) + "\n")
        self.env["FACTORY_BUILD"] = "%s/%s" % (project, build)

    def fake_program(self, name, body):
        bindir = self.tmp / "bin"
        bindir.mkdir(exist_ok=True)
        path = bindir / name
        path.write_text("#!%s\n%s\n" % (PYTHON, body))
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path

    def write_project_config(self, value):
        write_json(self.project / "factory.json", value)
        return self.project / "factory.json"

    def assert_plain_error(self, result, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        self.assertIn("factory:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


DEFAULT_PROJECT_CONFIG = {
    "project": "toy",
    "roles": {"maker": {"runner": "claude", "model": "opus-test"}},
    "vendors": {"required": [], "optional": []},
    "notify": {"channels": []},
    "timers": {
        "wake_s": 0.3, "quiet_s": 600, "stale_s": 1800,
        "default_cmd_timeout_s": 0.3, "kill_grace_s": 0.1,
        "notify_desktop_s": 0.3, "notify_command_s": 0.3, "poll_s": 0.05,
    },
    "tests": {"fast": {"cmd": "true", "timeout_s": 1}},
}
