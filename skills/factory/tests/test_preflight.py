"""Preflight contracts with only local fake programs and sub-second limits."""

import copy
import json
import os
import stat
import time
from pathlib import Path

from tests.common import (DEFAULT_PROJECT_CONFIG, FactoryTestCase, PYTHON,
                          read_jsonl, write_json)


class PreflightTests(FactoryTestCase):
    def setUp(self):
        super().setUp()
        (self.project / "CONSTITUTION.md").write_text("Synthetic project rules.\n")
        self.config = copy.deepcopy(DEFAULT_PROJECT_CONFIG)
        self.config.update({
            "constitution": "CONSTITUTION.md",
            "roles": {
                "maker": {"runner": "claude", "model": "maker-model"},
                "reviewer": {
                    "runner": "codex", "model": "review-model",
                    "fallback": [
                        {"runner": "opencode", "model": "opencode/free-model"},
                        {"runner": "opencode", "model": "ollama/local-model"},
                    ],
                },
            },
            "vendors": {"required": ["claude", "codex", "opencode"],
                        "optional": ["cursor"]},
            "runners": {
                "claude": {"retains_data": False},
                "codex": {"retains_data": False},
                "opencode": {"retains_data": True,
                             "private_safe_prefixes": ["ollama/"],
                             "probe_model": "opencode/free-model"},
                "cursor": {"retains_data": True},
            },
            "preflight": {"limits": {"claude": 0.3, "codex": 0.3,
                                      "opencode": 0.3, "cursor": 0.3}},
            "release": {"preflight": [], "steps": [], "smoke": []},
        })
        write_json(self.project / "factory.json", self.config)
        build = self.factory_home / "runs" / "toy" / "preflight-case"
        build.mkdir(parents=True)
        (build / "trace.jsonl").write_text("")
        write_json(build / "build.json", {
            "project": "toy", "build": "preflight-case", "title": "Preflight case",
            "repo": str(self.project), "started": self.env["FACTORY_NOW"], "stop_times": [],
        })
        self.select("toy", "preflight-case", phase="preflight")
        self.build = build

    def healthy_env(self):
        exact = self.fake_program("probe-ok", "print('OK')")
        cursor = self.fake_program("cursor-ok", "print('Logged in')")
        pmset = self.fake_program("pmset-ok", "print('PreventUserIdleSystemSleep 1')")
        return {
            "FACTORY_CLAUDE_BIN": str(exact),
            "FACTORY_CODEX_BIN": str(exact),
            "FACTORY_OPENCODE_BIN": str(exact),
            "FACTORY_CURSOR_BIN": str(cursor),
            "FACTORY_PMSET_BIN": str(pmset),
        }

    def write_config(self):
        write_json(self.project / "factory.json", self.config)

    def test_preflight_json_is_complete_immutable_and_logged(self):
        """T-PRE-01: healthy JSON is saved append-only, probes every model/vendor, and logs the run."""
        env = self.healthy_env()
        first = self.run_factory("preflight", "--json", "--no-notify-test", env=env)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        payload = json.loads(first.stdout)
        self.assertTrue(payload["ok"])
        names = {item["name"] for item in payload["checks"]}
        expected = {
            "model:claude:maker-model", "model:codex:review-model",
            "model:opencode:opencode/free-model", "model:opencode:ollama/local-model",
            "vendor:claude", "vendor:codex", "vendor:opencode", "vendor:cursor",
            "config", "log-home", "sleep", "tools",
        }
        self.assertTrue(expected.issubset(names), sorted(names))
        log_home = next(item for item in payload["checks"] if item["name"] == "log-home")
        self.assertIn(str(self.factory_home.resolve()), log_home["detail"])

        preflight_dir = self.factory_home / "preflight"
        files = sorted(preflight_dir.glob("*.json"))
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(files[0].read_text()), payload)
        original = files[0].read_bytes()
        self.env["FACTORY_NOW"] = "2026-01-10T12:13:00Z"
        second = self.run_factory("preflight", "--json", "--no-notify-test", env=env)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(files[0].read_bytes(), original)
        self.assertEqual(len(list(preflight_dir.glob("*.json"))), 2)
        self.assertEqual(len(read_jsonl(preflight_dir / "index.jsonl")), 2)
        logged = read_jsonl(self.build / "trace.jsonl")
        self.assertTrue(any(line.get("node") == "preflight" and line.get("status") == "done"
                            for line in logged))

        sentinel = self.tmp / "probe-ran"
        should_not_run = self.fake_program("should-not-run", "open(%r,'w').write('bad')" % str(sentinel))
        (self.project / "factory.json").write_text("not json\n")
        invalid = self.run_factory("preflight", "--json", env={
            "FACTORY_CLAUDE_BIN": str(should_not_run),
        })
        self.assertEqual(invalid.returncode, 2)
        self.assertFalse(sentinel.exists())
        self.write_config()
        unknown = self.run_factory("preflight", "--only", "nosuch", env=env)
        self.assertEqual(unknown.returncode, 2)

    def test_preflight_text_release_sleep_and_notification_results(self):
        """T-PRE-02: text, release, sleep, notification, and no-notify modes report exact outcomes."""
        env = self.healthy_env()
        healthy = self.run_factory("preflight", "--no-notify-test", env=env)
        self.assertEqual(healthy.returncode, 0, healthy.stdout + healthy.stderr)
        self.assertTrue(all(line.startswith(("PASS", "WARN", "FAIL", "Ready.")) or
                            "credit" in line.lower() or not line.strip()
                            for line in healthy.stdout.splitlines()))
        self.assertIn("Ready.", healthy.stdout)
        self.assertIn("remaining credit", healthy.stdout.lower())

        self.config["release"]["preflight"] = [
            {"name": "clean", "cmd": "printf 'clean output\\n'", "timeout_s": 1},
            {"name": "broken", "cmd": "printf 'last failure line\\n'; exit 1", "timeout_s": 1},
        ]
        self.write_config()
        release = self.run_factory("preflight", "--release", "--no-notify-test", env=env)
        self.assertEqual(release.returncode, 1)
        self.assertRegex(release.stdout, r"PASS\s+release:clean")
        self.assertRegex(release.stdout, r"FAIL\s+release:broken")
        self.assertIn("last failure line", release.stdout)

        no_sleep = self.fake_program("pmset-no-assertion", "print('SleepDisabled 0')")
        sleep = self.run_factory("preflight", "--only", "sleep", "--no-notify-test",
                                 env=dict(env, FACTORY_PMSET_BIN=str(no_sleep)))
        self.assertEqual(sleep.returncode, 1)
        self.assertIn("caffeinate -dimsu -t 43200", sleep.stdout)

        failing = self.fake_program("desktop-fail", "import sys; sys.exit(1)")
        self.config["notify"] = {"channels": ["desktop"]}
        self.write_config()
        notice = self.run_factory("preflight", "--only", "notify:desktop",
                                  env=dict(env, FACTORY_OSASCRIPT_BIN=str(failing)))
        self.assertEqual(notice.returncode, 1)
        self.assertRegex(notice.stdout, r"FAIL\s+notify:desktop")
        self.config["notify"] = {"channels": []}
        self.write_config()
        none = self.run_factory("preflight", env=env)
        self.assertEqual(none.returncode, 0)
        self.assertIn("WARN", none.stdout)
        capture = self.tmp / "desktop-called"
        recorder = self.fake_program("desktop-recorder", "open(%r,'w').write('called')" % str(capture))
        skipped = self.run_factory("preflight", "--no-notify-test",
                                   env=dict(env, FACTORY_OSASCRIPT_BIN=str(recorder)))
        self.assertIn(skipped.returncode, (0, 1))
        self.assertNotIn("notify:", skipped.stdout)
        self.assertFalse(capture.exists())

    def test_preflight_fallback_privacy_credit_login_and_missing_program(self):
        """T-PRE-03: credit, fallback privacy, login, missing-program, and numbered fixes stay distinct."""
        quota = self.fake_program("codex-quota", "import sys; print('usage limit reached'); sys.exit(1)")
        ok = self.fake_program("fallback-ok", "print('OK')")
        env = self.healthy_env()
        env.update({"FACTORY_CODEX_BIN": str(quota), "FACTORY_OPENCODE_BIN": str(ok)})
        self.config["roles"] = {"reviewer": self.config["roles"]["reviewer"]}
        self.config["vendors"] = {"required": [], "optional": []}
        self.write_config()
        fallback = self.run_factory("preflight", "--no-notify-test", env=env)
        self.assertEqual(fallback.returncode, 1)
        self.assertIn("out of credits or rate limited", fallback.stdout)
        self.assertIn("will use fallback ollama/local-model", fallback.stdout)
        self.assertIn("on this machine", fallback.stdout)
        self.assertIn("only for calls marked non-private", fallback.stdout)
        self.assertIn("private ok", fallback.stdout)
        self.assertIn("non-private material only", fallback.stdout)
        self.assertRegex(fallback.stdout, r"(?m)^1\. ")

        self.config["roles"]["reviewer"].pop("fallback")
        self.write_config()
        no_fallback = self.run_factory("preflight", "--no-notify-test", env=env)
        self.assertEqual(no_fallback.returncode, 1)
        self.assertIn("reviewer", no_fallback.stdout.lower())

        login = self.fake_program("codex-login", "import sys; print('Not logged in'); sys.exit(1)")
        not_logged_in = self.run_factory("preflight", "--no-notify-test",
                                         env=dict(env, FACTORY_CODEX_BIN=str(login)))
        self.assertEqual(not_logged_in.returncode, 1)
        self.assertIn("not logged in", not_logged_in.stdout.lower())
        self.assertIn("login", not_logged_in.stdout.lower())
        missing = self.run_factory("preflight", "--no-notify-test",
                                   env=dict(env, FACTORY_CODEX_BIN=str(self.tmp / "missing-codex")))
        self.assertEqual(missing.returncode, 1)
        self.assertIn("not installed", missing.stdout.lower())

    def test_preflight_cloud_timeouts_run_in_parallel_under_one_second(self):
        """T-PRE-04: all never-answering cloud probes time out in parallel while local checks still run."""
        slow = self.fake_program("never-answers", "import time; time.sleep(30)")
        self.config["roles"] = {
            "one": {"runner": "claude", "model": "one"},
            "two": {"runner": "codex", "model": "two"},
            "three": {"runner": "opencode", "model": "three"},
            "four": {"runner": "cursor", "model": "four"},
        }
        self.config["vendors"] = {"required": [], "optional": []}
        self.write_config()
        env = {key: str(slow) for key in (
            "FACTORY_CLAUDE_BIN", "FACTORY_CODEX_BIN", "FACTORY_OPENCODE_BIN",
            "FACTORY_CURSOR_BIN")}
        env["FACTORY_PMSET_BIN"] = str(self.fake_program(
            "pmset-local", "print('PreventUserIdleSystemSleep 1')"))
        started = time.monotonic()
        result = self.run_factory("preflight", "--no-notify-test", env=env)
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 1)
        self.assertLess(elapsed, 0.95)
        self.assertGreaterEqual(result.stdout.count("no answer in"), 4)
        for local_name in ("config", "log-home", "sleep", "tools"):
            self.assertIn(local_name, result.stdout)

    def test_preflight_requires_an_exact_successful_OK_reply(self):
        """T-PRE-05: probe success needs exit zero and normalized stdout exactly equal to OK."""
        cases = [
            ("claude", "print('OK'); import sys; sys.exit(1)", False),
            ("codex", "print('Reply with exactly: OK')", False),
            ("opencode", "print('Sure! OK.')", False),
            ("claude", "print('\\x1b[32m\\nOK \\x1b[0m')", True),
        ]
        for index, (runner, body, passes) in enumerate(cases):
            with self.subTest(runner=runner, index=index):
                fake = self.fake_program("exact-%d" % index, body)
                model = "probe-%d" % index
                self.config["roles"] = {"probe": {"runner": runner, "model": model}}
                self.config["vendors"] = {"required": [], "optional": []}
                self.write_config()
                variable = "FACTORY_%s_BIN" % runner.upper()
                result = self.run_factory("preflight", "--only",
                                          "model:%s:%s" % (runner, model),
                                          "--no-notify-test", env={variable: str(fake)})
                self.assertEqual(result.returncode, 0 if passes else 1)
                if passes:
                    self.assertRegex(result.stdout, r"PASS\s+model:")
                else:
                    self.assertIn("unexpected answer", result.stdout)

    def test_preflight_vendor_probe_uses_discovery_and_optional_is_warning(self):
        """T-PRE-06: vendor-only probes use newest bin_glob, missing required fails, optional login warns."""
        versions = self.tmp / "versions"
        capture = self.tmp / "opencode-args.json"
        for version in ("2.9.9", "2.10.0"):
            folder = versions / version
            folder.mkdir(parents=True)
            program = folder / "opencode"
            program.write_text(
                "#!%s\nimport json,sys\nopen(%r,'w').write(json.dumps(sys.argv[1:]))\nprint('OK')\n" %
                (PYTHON, str(capture)))
            program.chmod(program.stat().st_mode | stat.S_IXUSR)
        self.config["roles"] = {}
        self.config["vendors"] = {"required": ["opencode"], "optional": []}
        self.config["runners"]["opencode"]["probe_model"] = "opencode/free-model"
        write_json(self.factory_home / "config.json", {
            "runners": {"opencode": {"bin_glob": str(versions / "*" / "opencode")}}
        })
        self.write_config()
        found = self.run_factory("preflight", "--only", "vendor:opencode",
                                 "--no-notify-test")
        self.assertEqual(found.returncode, 0, found.stdout + found.stderr)
        self.assertEqual(json.loads(capture.read_text()),
                         ["run", "-m", "opencode/free-model", "Reply with exactly: OK"])
        self.assertIn("2.10.0", found.stdout)
        self.assertIn("free tier: may keep what it is sent, non-private material only", found.stdout)

        write_json(self.factory_home / "config.json", {})
        empty_path = self.tmp / "empty-bin"
        empty_path.mkdir()
        missing = self.run_factory("preflight", "--only", "vendor:opencode",
                                   "--no-notify-test", env={"PATH": str(empty_path)})
        self.assertEqual(missing.returncode, 1)
        self.assertIn("not installed", missing.stdout.lower())

        cursor = self.fake_program("cursor-not-logged-in",
                                   "import sys; print('Not logged in'); sys.exit(1)")
        self.config["vendors"] = {"required": [], "optional": ["cursor"]}
        self.write_config()
        optional = self.run_factory("preflight", "--only", "vendor:cursor",
                                    "--no-notify-test", env={"FACTORY_CURSOR_BIN": str(cursor)})
        self.assertEqual(optional.returncode, 0)
        self.assertRegex(optional.stdout, r"WARN\s+vendor:cursor")
        self.assertIn("optional, not available", optional.stdout)


if __name__ == "__main__":
    import unittest
    unittest.main()
