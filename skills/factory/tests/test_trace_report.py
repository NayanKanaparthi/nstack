"""Exact trace-report computations and report-card command contracts."""

import json
import shutil
from pathlib import Path

from tests.common import FactoryTestCase, FIXTURES, read_jsonl, write_json, write_jsonl


NOW = "2026-01-10T12:12:00Z"


class TraceComputeTests(FactoryTestCase):
    def compute(self, fixture="alpha", gap_s=300):
        module = self.require_module("trace_report")
        return module.compute(FIXTURES / fixture, NOW, gap_s)

    def test_trace_compute_build_and_time_breakdowns(self):
        """T-TR-01: Fixture A build quality and phase, piece, and actor rows have exact ordered values."""
        report = self.compute()
        build = report["build"]
        self.assertEqual(build["wall_s"], 7320)
        self.assertEqual(build["lines"], len((FIXTURES / "alpha" / "trace.jsonl").read_text().splitlines()))
        self.assertEqual(build["spans"], 22)
        self.assertEqual(build["bad_lines"], 1)
        self.assertEqual(len(build["open_spans"]), 2)
        self.assertEqual(build["unknown_duration_spans"], 1)

        phases = [(row["phase"], row["time_s"], row["share"]) for row in report["by_phase"]]
        self.assertEqual(phases, [
            ("build", 3960, 0.569), ("gate-a", 1800, 0.259),
            ("plan", 1080, 0.155), ("e2e", 120, 0.017),
        ])
        nodes = [(row["node"], row["time_s"], row["calls"]) for row in report["by_node"]]
        self.assertEqual(nodes, [
            ("N1", 3300, 8), ("plan", 720, 1), ("N2", 660, 2),
            ("plan-review", 360, 1), ("e2e", 120, 1),
        ])
        actors = [(row["actor"], row["time_s"], row["calls"], row["failed"])
                  for row in report["by_actor"]]
        self.assertEqual(actors, [
            ("maker", 2580, 5, 0), ("checker", 1380, 5, 0),
            ("planner", 720, 1, 0), ("plan-reviewer", 360, 1, 0),
            ("orchestrator", 120, 1, 1),
        ])

    def test_trace_compute_loop_churn_and_thrash(self):
        """T-TR-02: Fixture A loop rows preserve approval, churn, thrash, and not-recorded values."""
        loops = {row["node"]: row for row in self.compute()["loops"]}
        self.assertEqual(set(loops), {"N1", "N2", "N3"})
        self.assertEqual(
            {key: loops["N1"][key] for key in
             ("loops", "approved", "time_to_approval_s", "churn", "thrash")},
            {"loops": 4, "approved": True, "time_to_approval_s": 3300,
             "churn": 1, "thrash": 1})
        self.assertEqual(
            {key: loops["N2"][key] for key in
             ("loops", "approved", "time_to_approval_s", "churn", "thrash")},
            {"loops": 1, "approved": True, "time_to_approval_s": 1080,
             "churn": 0, "thrash": 0})
        self.assertEqual(loops["N3"]["loops"], 1)
        self.assertFalse(loops["N3"]["approved"])
        self.assertIsNone(loops["N3"]["time_to_approval_s"])
        self.assertIsNone(loops["N3"]["churn"])
        self.assertIsNone(loops["N3"]["thrash"])

    def test_trace_compute_waits_gaps_failures_and_bottlenecks(self):
        """T-TR-03: waits, both gap thresholds, failures, and ranked plain bottlenecks are exact."""
        report = self.compute()
        waits = report["waits"]
        self.assertEqual((waits["human_s"], waits["human_count"], waits["human_open"]),
                         (2400, 2, 1))
        self.assertEqual(waits["longest_human"], {"gate": "GATE A", "s": 1800})
        self.assertTrue(any(item["gate"] == "GATE B" and item["s"] == 600 and item["open"]
                            for item in waits["items"]))
        self.assertEqual(report["idle_gaps"], {
            "threshold_s": 300, "total_s": 900,
            "gaps": [{"from": "2026-01-10T11:45:00Z",
                      "to": "2026-01-10T12:00:00Z", "s": 900}],
        })
        shorter = self.compute(gap_s=60)["idle_gaps"]
        self.assertEqual(shorter["total_s"], 1020)
        self.assertEqual(shorter["gaps"], [
            {"from": "2026-01-10T10:18:00Z", "to": "2026-01-10T10:20:00Z", "s": 120},
            {"from": "2026-01-10T11:45:00Z", "to": "2026-01-10T12:00:00Z", "s": 900},
        ])
        self.assertEqual(len(report["failures"]), 1)
        self.assertEqual(report["failures"][0]["failure_class"], "env-tooling")
        bottlenecks = report["bottlenecks"]
        self.assertEqual([(row["rank"], row["kind"], row["time_s"]) for row in bottlenecks],
                         [(1, "node", 3300), (2, "actor", 2580), (3, "human-wait", 2400)])
        for row in bottlenecks:
            self.assertTrue(row["plain"].endswith("."), row)
            self.assertNotRegex(row["plain"], r"\b(?:s\d+|N\d+)\b")

    def test_trace_compute_old_and_incomplete_shapes_never_raise(self):
        """T-TR-04: old shapes and an E-shaped incomplete log count unknown, open, and failed work safely."""
        old = self.compute("charlie")
        self.assertGreaterEqual(old["build"]["unknown_duration_spans"], 1)
        for section in ("by_phase", "by_node", "by_actor"):
            self.assertTrue(all(row["time_s"] >= 0 for row in old[section]))

        shaped = self.tmp / "large-shaped-synthetic"
        shaped.mkdir()
        lines = []
        for index in range(8):
            lines.append({
                "span_id": "open-%d" % index, "ts": "2026-01-10T10:%02d:00Z" % index,
                "kind": "agent_call", "actor": "maker", "status": "running",
                "start": "2026-01-10T10:%02d:00Z" % index,
            })
        for index in range(4):
            lines.append({
                "span_id": "failed-%d" % index, "ts": "2026-01-10T11:%02d:00Z" % index,
                "kind": "command", "actor": "orchestrator", "status": "failed",
                "start": "2026-01-10T11:%02d:00Z" % index,
                "end": "2026-01-10T11:%02d:30Z" % index, "duration_s": 30,
                "failure_class": "env-tooling",
            })
        write_jsonl(shaped / "trace.jsonl", lines)
        report = self.require_module("trace_report").compute(shaped, NOW, 300)
        self.assertEqual(len(report["build"]["open_spans"]), 8)
        self.assertEqual(report["build"]["unknown_duration_spans"], 8)
        self.assertEqual(len(report["failures"]), 4)


class TraceCommandTests(FactoryTestCase):
    def setUp(self):
        super().setUp()
        self.build = self.install_fixture("alpha", project="demo", build="alpha")
        self.select("demo", "alpha")

    def report_files(self):
        folder = self.build / "reports"
        if not folder.exists():
            return []
        return sorted(path for path in folder.iterdir() if path.name != "index.jsonl")

    def make_case(self, name, content):
        build = self.factory_home / "runs" / "demo" / name
        build.mkdir(parents=True)
        (build / "trace.jsonl").write_text(content)
        write_json(build / "build.json", {
            "project": "demo", "build": name, "title": name,
            "repo": None, "started": NOW, "stop_times": [],
        })
        return build

    def test_trace_report_writes_immutable_pairs_and_supports_json_no_write(self):
        """T-TR-05: each markdown run appends an immutable pair; JSON no-write matches the compute shape."""
        first = self.run_factory("trace-report")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        files = self.report_files()
        self.assertEqual(len(files), 2)
        before = {path.name: path.read_bytes() for path in files}
        index = self.build / "reports" / "index.jsonl"
        self.assertEqual(len(read_jsonl(index)), 2)
        for heading in ("Build", "By phase", "By piece", "By actor", "Loops", "Waits",
                        "Idle gaps", "Failures", "Bottlenecks", "Data quality"):
            self.assertIn(heading.lower(), first.stdout.lower())
        self.assertIn("1 unreadable", first.stdout)
        self.assertIn("2", first.stdout)
        self.assertIn("never closed", first.stdout.lower())
        self.assertIn("1", first.stdout)
        self.assertIn("without a duration", first.stdout.lower())

        self.env["FACTORY_NOW"] = "2026-01-10T12:13:00Z"
        second = self.run_factory("trace-report")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(len(self.report_files()), 4)
        self.assertEqual(len(read_jsonl(index)), 4)
        for name, content in before.items():
            self.assertEqual((self.build / "reports" / name).read_bytes(), content)
        files_before_json = [path.name for path in self.report_files()]
        as_json = self.run_factory("trace-report", "--json", "--no-write")
        self.assertEqual(as_json.returncode, 0, as_json.stdout + as_json.stderr)
        payload = json.loads(as_json.stdout)
        self.assertEqual(set(payload), {"build", "by_phase", "by_node", "by_actor", "loops",
                                        "waits", "idle_gaps", "failures", "bottlenecks"})
        self.assertEqual([path.name for path in self.report_files()], files_before_json)

    def test_trace_report_rejects_empty_missing_untimed_and_bad_gaps(self):
        """T-TR-06: empty, unreadable, and untimed logs fail loudly; selection and gap errors use exact codes."""
        cases = [
            ("zero", ""),
            ("bad", "not json\n[]\n"),
            ("untimed", json.dumps({"span_id": "x", "kind": "command", "status": "done",
                                     "ts": NOW}) + "\n"),
        ]
        for name, content in cases:
            with self.subTest(name=name):
                build = self.make_case(name, content)
                result = self.run_factory("trace-report", "--build", "demo/" + name)
                self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                self.assertFalse((build / "reports").exists())
                if name == "untimed":
                    self.assertIn("no span in this log has a duration", result.stderr.lower())
                else:
                    self.assertIn("nothing to report", result.stderr.lower())
        (self.factory_home / "current.jsonl").write_text("")
        no_build = self.run_factory("trace-report", env={"FACTORY_BUILD": ""})
        self.assertEqual(no_build.returncode, 3)
        self.assertEqual(self.run_factory("trace-report", "--build", "nope/none").returncode, 3)
        for gap in ("0", "x"):
            self.assertEqual(self.run_factory("trace-report", "--build", "demo/alpha",
                                              "--gap", gap).returncode, 2)

    def test_report_card_matches_trace_json_and_uses_plain_words(self):
        """T-RC-01: Fixture A card is short, plain, numbered, and every featured number comes from JSON."""
        trace = self.run_factory("trace-report", "--json", "--no-write")
        self.assertEqual(trace.returncode, 0, trace.stdout + trace.stderr)
        data = json.loads(trace.stdout)
        card = self.run_factory("report-card")
        self.assertEqual(card.returncode, 0, card.stdout + card.stderr)
        files = list((self.build / "reports").glob("REPORT-CARD-*.md"))
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_text(), card.stdout)
        self.assertLessEqual(len(card.stdout.splitlines()), 30)
        for text in ("2 h 2 min", "4 tries", "40 min in 2 waits", "15 min in 1 gap"):
            self.assertIn(text, card.stdout)
        for rank, bottleneck in enumerate(data["bottlenecks"], 1):
            self.assertIn("%d." % rank, card.stdout)
            self.assertIn(str(round(bottleneck["time_s"] / 60)), card.stdout)
        self.assertRegex(card.stdout, r"Expected \d+, logged \d+, matched \d+")
        self.assertNotRegex(card.stdout.lower(), r"\b(?:span|iteration|rubric)\b")
        self.assertNotRegex(card.stdout, r"\b(?:s\d+|N\d+)\b")

    def test_report_card_has_same_empty_input_errors_and_writes_nothing(self):
        """T-RC-02: report-card returns 4 for three empty inputs and 3 without a build, writing nothing."""
        cases = [
            ("card-zero", ""),
            ("card-bad", "not json\n"),
            ("card-untimed", json.dumps({"span_id": "x", "kind": "command",
                                          "status": "done", "ts": NOW}) + "\n"),
        ]
        for name, content in cases:
            with self.subTest(name=name):
                build = self.make_case(name, content)
                result = self.run_factory("report-card", "--build", "demo/" + name)
                self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                self.assertFalse((build / "reports").exists())
        (self.factory_home / "current.jsonl").write_text("")
        self.assertEqual(self.run_factory("report-card", env={"FACTORY_BUILD": ""}).returncode, 3)


if __name__ == "__main__":
    import unittest
    unittest.main()
