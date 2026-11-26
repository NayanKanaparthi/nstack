"""Round-3 plan and owner-facing board contracts (T-PG-19..24, 33..54, 91)."""

import json
import os
import shutil
from pathlib import Path

from tests.common import (
    DEFAULT_PROJECT_CONFIG, FIXTURES, FactoryTestCase, write_json, write_jsonl,
)


PAGE_FIXTURES = FIXTURES / "page"
PG_GRAPH = PAGE_FIXTURES / "PG-GRAPH.yaml"


def plan_value():
    return {
        "v": 1,
        "source": "GRAPH.yaml",
        "generated": "2026-01-10T14:00:00Z",
        "pieces": [
            {"id": "A1", "name": "Greeting words", "tech_name": "Alpha module",
             "purpose": "Choose the words the program says hello with.",
             "depends_on": [], "stage": 1},
            {"id": "B1", "name": "Shout option", "tech_name": "Beta module",
             "purpose": "Make the program shout when asked.",
             "depends_on": ["A1"], "stage": 2},
            {"id": "B2", "name": "Quiet option", "tech_name": "Gamma module",
             "purpose": "Make the program speak quietly when asked.",
             "depends_on": ["A1"], "stage": 2},
            {"id": "C1", "name": "Final check", "tech_name": "Final run",
             "purpose": "Run the whole program the way a person would.",
             "depends_on": ["B1", "B2"], "stage": 3},
        ],
        "stages": [
            {"n": 1, "name": "Groundwork", "purpose": "Set up the words the program uses.",
             "members": ["A1"]},
            {"n": 2, "name": "Two options", "purpose": "Build the two options side by side.",
             "members": ["B1", "B2"]},
            {"n": 3, "name": "Final check",
             "purpose": "Run the whole program the way a person would.", "members": ["C1"]},
        ],
    }


def start_line(span, ts, actor, call, node, model, **extra):
    line = {
        "v": 1, "span_id": span, "ts": ts, "start": ts, "kind": "agent_call",
        "actor": actor, "call": call, "node": node, "model": model, "status": "running",
    }
    line.update(extra)
    return line


def end_line(span, ts, plain, **extra):
    line = {
        "v": 1, "span_id": span, "ts": ts, "end": ts, "status": "done",
        "plain": plain, "plain_source": "agent",
    }
    line.update(extra)
    return line


def pg1_lines():
    return [
        {"v": 1, "span_id": "f1", "ts": "2026-01-10T14:00:00Z",
         "start": "2026-01-10T14:00:00Z", "kind": "feature", "actor": "orchestrator",
         "status": "running"},
        start_line("a1m1", "2026-01-10T14:00:00Z", "maker", "A1.maker.1", "A1", "sonnet-5-5"),
        end_line("a1m1", "2026-01-10T14:10:00Z",
                 "Wrote the greeting words and a short test for them. A checker reads them next."),
        start_line("a1c1", "2026-01-10T14:10:00Z", "checker", "A1.checker.1", "A1", "fable-5-2"),
        end_line("a1c1", "2026-01-10T14:15:00Z",
                 "The checker approved the greeting words. This piece is finished.",
                 verdict="approved"),
        start_line("b1m1", "2026-01-10T14:15:00Z", "maker", "B1.maker.1", "B1", "sonnet-5-5"),
        end_line("b1m1", "2026-01-10T14:30:00Z",
                 "Added the shout option. A checker reads it next."),
        start_line("b1c1", "2026-01-10T14:30:00Z", "checker", "B1.checker.1", "B1", "fable-5-2"),
        end_line("b1c1", "2026-01-10T14:40:00Z",
                 "The checker asked for 2 fixes: the option ignores capital letters and the help text "
                 "is missing. The builder fixes these next.", verdict="rejected",
                 failure_class="impl-bug"),
        start_line("b2m1", "2026-01-10T14:15:00Z", "maker", "B2.maker.1", "B2", "sonnet-5-5"),
        end_line("b2m1", "2026-01-10T14:25:00Z",
                 "Added the quiet option. A checker reads it next."),
        start_line("b2c1", "2026-01-10T14:25:00Z", "checker", "B2.checker.1", "B2", "fable-5-2"),
        start_line("b1m2", "2026-01-10T14:40:00Z", "maker", "B1.maker.2", "B1", "sonnet-5-5"),
    ]


class PageFixtureCase(FactoryTestCase):
    def make_custom(self, name, lines, plan=True):
        build = self.factory_home / "runs" / "toy" / name
        build.mkdir(parents=True)
        write_jsonl(build / "trace.jsonl", lines)
        write_json(build / "build.json", {
            "project": "toy", "build": name, "title": "Toy: add two options",
            "started": "2026-01-10T14:00:00Z", "stop_times": [],
        })
        write_jsonl(build / "expected.jsonl", [
            {"call": "%s.%s.1" % (piece, role), "node": piece, "actor": role,
             "added_by": "graph"}
            for piece in ("A1", "B1", "B2", "C1") for role in ("maker", "checker")
        ])
        if plan:
            write_json(build / "plan.json", plan_value())
        return build

    def make_pg1(self, name="pg1", plan=True):
        build = self.factory_home / "runs" / "toy" / name
        build.mkdir(parents=True)
        write_jsonl(build / "trace.jsonl", pg1_lines())
        write_json(build / "build.json", {
            "project": "toy", "build": name, "title": "Toy: add two options",
            "started": "2026-01-10T14:00:00Z",
            "stop_times": [{"label": "GATE B", "plain": "Release decision",
                            "at": "2026-01-10T17:30:00Z"}],
        })
        write_jsonl(build / "expected.jsonl", [
            {"call": "%s.%s.1" % (piece, role), "node": piece, "actor": role,
             "added_by": "graph"}
            for piece in ("A1", "B1", "B2", "C1") for role in ("maker", "checker")
        ])
        if plan:
            write_json(build / "plan.json", plan_value())
        return build

    def board(self, build=None, now="2026-01-10T14:50:00Z"):
        lib = self.require_module("factorylib")
        value = lib.board(build or self.make_pg1(), now)
        self.assertIn("owner", value, "planned field missing: board.owner")
        self.assertIn("plan", value, "planned field missing: board.plan")
        return lib, value


class PlanCreationContractTests(PageFixtureCase):
    def setUp(self):
        super().setUp()
        self.write_project_config(DEFAULT_PROJECT_CONFIG)

    def test_T_PG_19_and_20_graph_creates_exact_plan_without_changing_seeding(self):
        """T-PG-19..20: staged graph writes plan.json and the same eight expected calls."""
        result = self.run_factory(
            "new", "pg-plan", "--project", "toy", "--title", "T",
            "--from-graph", str(PG_GRAPH),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        build = self.factory_home / "runs" / "toy" / "pg-plan"
        path = build / "plan.json"
        self.assertTrue(path.is_file(), "planned field file missing: plan.json")
        actual = json.loads(path.read_text())
        expected = plan_value()
        actual.pop("generated", None)
        expected.pop("generated", None)
        self.assertEqual(actual, expected)
        calls = [item["call"] for item in
                 [json.loads(line) for line in (build / "expected.jsonl").read_text().splitlines()]]
        self.assertEqual(calls, [
            "A1.maker.1", "A1.checker.1", "B1.maker.1", "B1.checker.1",
            "B2.maker.1", "B2.checker.1", "C1.maker.1", "C1.checker.1",
        ])
        self.assertFalse(any("Z0" in call for call in calls))

    def test_T_PG_21_to_23_graph_parser_is_strict_atomic_and_understands_comments(self):
        """T-PG-21..23: old graphs stay flat; staged graph errors are complete and atomic."""
        old = self.project / "old.yaml"
        old.write_text("nodes:\n  - id: A1\n    name: One\n    depends_on: []\n    owns_files: [a.py]\n")
        old_result = self.run_factory("new", "old", "--title", "Old", "--from-graph", str(old))
        self.assertEqual(old_result.returncode, 0, old_result.stderr)
        self.assertFalse((self.factory_home / "runs" / "toy" / "old" / "plan.json").exists())
        self.assertIn("no stages block in the graph", old_result.stderr)

        source = PG_GRAPH.read_text()
        cases = [
            (source.replace("    plain_name: Shout option\n", ""), ("plain_name is missing",)),
            (source.replace("Make the program shout when asked.", "Edit shout.py."), ("shout.py",)),
            (source.replace("plain_name: Shout option", "plain_name: Option N2"),
             ("looks like an id",)),
            (source.replace("depends_on: [A1, Z0]", "depends_on: [Q9]"),
             ("not in the graph",)),
            (source.replace("    members: [C1]", "    members: []"),
             ("Final check", "C1", "no stage")),
            (source.replace("    members: [C1]", "    members: [B1, C1]"),
             ("B1", "two stages")),
            (source.replace("  - id: A1\n    name: Alpha module",
                            "  - id: A1\n    name: Alpha module").replace(
                                "    depends_on: []\n    owns_files: [a.py]",
                                "    depends_on: [C1]\n    owns_files: [a.py]", 1),
             ("cycle through",)),
            (source.replace("    depends_on: [A1]\n", "    depends_on:\n      - A1\n", 1),
             ("must be written on one line",)),
            (source.replace("  - id: B1", "\t- id: B1"), ("uses tabs",)),
            (source.replace("plain_name: Shout option", "plain_name: " + "x" * 41),
             ("plain_name", "40")),
            (source.replace("    plain_name: Shout option\n", "").replace(
                "depends_on: [A1, Z0]", "depends_on: [Q9]"),
             ("plain_name is missing", "not in the graph")),
        ]
        pointer = self.factory_home / "current.jsonl"
        before_pointer = pointer.read_bytes()
        for index, (text, messages) in enumerate(cases):
            graph = self.project / ("bad-%d.yaml" % index)
            graph.write_text(text)
            result = self.run_factory(
                "new", "bad-%d" % index, "--title", "Bad", "--from-graph", str(graph),
            )
            with self.subTest(index=index):
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                for message in messages:
                    self.assertIn(message, result.stderr)
                self.assertFalse((self.factory_home / "runs" / "toy" / ("bad-%d" % index)).exists())
                self.assertEqual(pointer.read_bytes(), before_pointer)

        comments = source.replace(
            "plain_name: Greeting words", 'plain_name: "Greeting words"  # first').replace(
            "purpose: Choose the words the program says hello with.",
            "purpose: Choose the words. # a comment").replace(
            "purpose: Make the program shout when asked.",
            'purpose: "Choose words for hello # and goodbye."')
        comment_graph = self.project / "comments.yaml"
        comment_graph.write_text(comments)
        valid = self.run_factory("new", "comments", "--title", "Comments",
                                 "--from-graph", str(comment_graph))
        self.assertEqual(valid.returncode, 0, valid.stderr)
        stored = json.loads((self.factory_home / "runs" / "toy" / "comments" /
                             "plan.json").read_text())
        self.assertEqual(stored["pieces"][0]["name"], "Greeting words")
        self.assertEqual(stored["pieces"][0]["purpose"], "Choose the words.")
        self.assertEqual(stored["pieces"][1]["purpose"],
                         "Choose words for hello # and goodbye.")

    def test_T_PG_24_adopt_versions_plan_without_overwriting_prior_bytes(self):
        """T-PG-24: adopt writes once, is idempotent, and suffixes same-second plan changes."""
        made = self.run_factory("new", "pg1", "--title", "T")
        self.assertEqual(made.returncode, 0, made.stderr)
        adopted = self.run_factory(
            "new", "pg1", "--adopt", "--title", "T", "--stop", "GATE B=12:30",
            "--stop-plain", "GATE B=Release decision", "--from-graph", str(PG_GRAPH),
        )
        self.assertEqual(adopted.returncode, 0, adopted.stderr)
        build = self.factory_home / "runs" / "toy" / "pg1"
        first = build / "plan.json"
        self.assertTrue(first.is_file(), "planned adopt output missing: plan.json")
        original = first.read_bytes()
        again = self.run_factory(
            "new", "pg1", "--adopt", "--title", "T", "--stop", "GATE B=12:30",
            "--stop-plain", "GATE B=Release decision", "--from-graph", str(PG_GRAPH),
        )
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(first.read_bytes(), original)
        self.assertEqual(list(build.glob("plan-*.json")), [])

        source = PG_GRAPH.read_text()
        extra_node = (
            "  - id: D1\n"
            "    name: Release note module\n"
            "    plain_name: Release notes\n"
            "    purpose: Write the words people read before release.\n"
            "    depends_on: [C1]\n"
            "    owns_files: [e.py]\n")
        changed = source.replace("stages:\n", extra_node + "stages:\n").replace(
            "    members: [C1]", "    members: [C1, D1]")
        changed_graph = self.project / "changed.yaml"
        changed_graph.write_text(changed)
        third = self.run_factory(
            "new", "pg1", "--adopt", "--title", "T", "--stop", "GATE B=12:30",
            "--stop-plain", "GATE B=Release decision", "--from-graph", str(changed_graph),
        )
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertEqual(first.read_bytes(), original)
        versions = sorted(build.glob("plan-*.json"))
        self.assertEqual(len(versions), 1)
        self.assertEqual(len(json.loads(versions[0].read_text())["pieces"]), 5)
        version_bytes = versions[0].read_bytes()

        renamed_graph = self.project / "renamed.yaml"
        renamed_graph.write_text(changed.replace("plain_name: Shout option",
                                                 "plain_name: Loud option"))
        fourth = self.run_factory(
            "new", "pg1", "--adopt", "--title", "T", "--stop", "GATE B=12:30",
            "--stop-plain", "GATE B=Release decision", "--from-graph", str(renamed_graph),
        )
        self.assertEqual(fourth.returncode, 0, fourth.stderr)
        versions = sorted(build.glob("plan-*.json"))
        self.assertEqual(len(versions), 2)
        suffixed = next(path for path in versions if path.stem.endswith("-2"))
        prior = next(path for path in versions if path != suffixed)
        self.assertEqual(prior.read_bytes(), version_bytes)


class BoardOwnerContractTests(PageFixtureCase):
    def test_T_PG_33_and_34_owner_summary_deadline_and_stage_spine(self):
        """T-PG-33..34: first screen and three ordered stages are derived from plan and log."""
        _, board = self.board()
        owner = board["owner"]
        self.assertFalse(owner["needs_you"])
        self.assertEqual(owner["calm"], {
            "title": "Nothing needs you",
            "text": "The build is moving on its own. A question will appear here the moment it needs you.",
        })
        self.assertEqual(owner["sentence"],
                         "Building: 1 of 4 pieces done, 1 being checked, 1 being built.")
        self.assertEqual(owner["counts"], {
            "total": 4, "done": 1, "building": 1, "checking": 1,
            "sent_back": 0, "stopped": 0, "waiting": 1, "needs_you": 0,
        })
        self.assertEqual(owner["started_label"], "9:00 am")
        self.assertEqual(owner["elapsed_label"], "50 min")
        self.assertEqual(owner["deadline_text"],
                         "Next: Release decision at 12:30 pm, in 2 h 40 min.")
        stages = board["plan"]["stages"]
        self.assertEqual([(s["name"], s["state"], s["parallel"], s["count_label"])
                          for s in stages], [
            ("Groundwork", "done", False, "1 piece"),
            ("Two options", "active", True, "2 pieces"),
            ("Final check", "waiting", False, "1 piece"),
        ])

    def test_T_PG_35_to_39_piece_states_counts_chips_roles_waits_and_quiet_text(self):
        """T-PG-35..39: each PG-1 piece has the exact owner-facing state and coordination text."""
        _, board = self.board(now="2026-01-10T14:55:00Z")
        pieces = {piece["id"]: piece for piece in board["plan"]["pieces"]}
        a1, b1, b2, c1 = [pieces[key] for key in ("A1", "B1", "B2", "C1")]
        self.assertEqual((a1["state"], a1["attempts"], a1["reviews"], a1["summary"]),
                         ("done", 1, 1, "1 attempt · 15 min"))
        self.assertEqual([chip["text"] for chip in a1["chips"]["items"]], ["Built", "Approved"])
        self.assertEqual((b1["state"], b1["attempts"], b1["reviews"]), ("building", 2, 1))
        self.assertEqual(b1["attempt_label"], "Attempt 2 of this piece")
        self.assertEqual(b1["now"], "The builder is making the fixes the checker asked for.")
        self.assertEqual(b1["last"]["label"], "Review 1")
        self.assertEqual([chip["text"] for chip in b1["chips"]["items"]],
                         ["Built", "Sent back", "Building now"])
        self.assertEqual(b1["quiet_text"], "No new output for 15 minutes.")
        self.assertEqual((b2["state"], b2["quiet_text"]),
                         ("checking", "No new output for 30 minutes."))
        self.assertEqual(c1["state"], "waiting")
        self.assertEqual(c1["waits_for_names"], ["Shout option", "Quiet option"])
        self.assertEqual(c1["now"], "Starts after: Shout option, Quiet option")

    def test_T_PG_40_to_45_early_parallel_gate_done_and_stale_rules(self):
        """T-PG-40..45: uncounted stops, groups, decisions, completion, and stale calls are explicit."""
        build = self.make_pg1("pg-stop")
        lines = [end_line(
            "b2c1", "2026-01-10T14:50:00Z",
            "The checker stopped because its daily usage limit ran out. A new checker starts after the limit resets.",
            status="stopped", stop_reason="usage_limit",
            next_step="A new checker starts after the limit resets.",
        )]
        with (build / "trace.jsonl").open("a") as stream:
            for line in lines:
                stream.write(json.dumps(line, sort_keys=True) + "\n")
        _, stopped = self.board(build, "2026-01-10T14:55:00Z")
        b2 = next(piece for piece in stopped["plan"]["pieces"] if piece["id"] == "B2")
        self.assertEqual((b2["state"], b2["reviews"], b2["roles"]), ("stopped", 0, {}))
        self.assertEqual(b2["calls"][-1]["result"], "Didn't finish")
        self.assertFalse(b2["calls"][-1]["counted"])
        self.assertEqual(stopped["owner"]["sentence"],
                         "Building: 1 of 4 pieces done, 1 being built, 1 ended early.")

        purpose_build = self.make_pg1("pg-purpose")
        with (purpose_build / "trace.jsonl").open("a") as stream:
            stream.write(json.dumps(end_line(
                "b1m2", "2026-01-10T14:45:00Z",
                "The builder was stopped on purpose so the work could be split in two.",
                status="stopped", stop_reason="on_purpose"), sort_keys=True) + "\n")
            stream.write(json.dumps(start_line(
                "b1m3", "2026-01-10T14:46:00Z", "maker", "B1.maker.3", "B1",
                "sonnet-5-5"), sort_keys=True) + "\n")
        _, purpose = self.board(purpose_build)
        purpose_b1 = next(piece for piece in purpose["plan"]["pieces"] if piece["id"] == "B1")
        self.assertEqual((purpose_b1["attempts"], purpose_b1["attempt_label"]),
                         (2, "Attempt 2 of this piece"))
        uncounted = next(call for call in purpose_b1["calls"] if call["call"] == "B1.maker.2")
        self.assertEqual((uncounted["result"], uncounted["counted"], uncounted["label"]),
                         ("Stopped on purpose", False, "Attempt, ended early"))

        grouped_lines = [
            start_line("ga", "2026-01-10T14:00:00Z", "test-writer", "A1.writer-a.1",
                       "A1", "gpt-5.6-sol", group="tests"),
            start_line("gb", "2026-01-10T14:00:00Z", "test-writer", "A1.writer-b.1",
                       "A1", "gpt-5.6-sol", group="tests"),
            end_line("ga", "2026-01-10T14:10:00Z",
                     "The first writer finished its half. A checker reads it next."),
            end_line("gb", "2026-01-10T14:10:00Z",
                     "The second writer finished its half. A checker reads it next."),
        ]
        group_build = self.make_custom("pg-group", grouped_lines)
        _, grouped = self.board(group_build, "2026-01-10T14:20:00Z")
        grouped_a1 = next(piece for piece in grouped["plan"]["pieces"] if piece["id"] == "A1")
        self.assertEqual((grouped_a1["attempts"], grouped_a1["attempt_label"],
                          grouped_a1["state"]), (1, "", "checking"))
        self.assertEqual([call["label"] for call in grouped_a1["calls"]],
                         ["Attempt 1", "Attempt 1"])

        completed = pg1_lines() + [
            end_line("b2c1", "2026-01-10T14:35:00Z",
                     "The checker approved the quiet option. This piece is finished.",
                     verdict="approved"),
            end_line("b1m2", "2026-01-10T14:50:00Z",
                     "The builder made the requested fixes. A checker reads them next."),
            start_line("b1c2", "2026-01-10T14:50:00Z", "checker", "B1.checker.2",
                       "B1", "fable-5-2"),
            end_line("b1c2", "2026-01-10T15:00:00Z",
                     "The checker approved the shout option. This piece is finished.",
                     verdict="approved"),
            start_line("c1m1", "2026-01-10T15:00:00Z", "maker", "C1.maker.1", "C1",
                       "sonnet-5-5"),
            end_line("c1m1", "2026-01-10T15:10:00Z",
                     "The builder prepared the final check. A checker reads it next."),
            start_line("c1c1", "2026-01-10T15:10:00Z", "checker", "C1.checker.1", "C1",
                       "fable-5-2"),
            end_line("c1c1", "2026-01-10T15:20:00Z",
                     "The checker approved the final check. This piece is finished.",
                     verdict="approved"),
            {"v": 1, "span_id": "gate1", "ts": "2026-01-10T15:25:00Z",
             "start": "2026-01-10T15:25:00Z", "kind": "wait", "actor": "human",
             "status": "running", "waiting_on": "human", "gate": "GATE B", "node": "C1",
             "question": "Do you want the toy program released now?",
             "recommend": "Yes, release it now. Both options passed their checks.",
             "plain": "Do you want the toy program released now?", "plain_source": "agent"},
        ]
        needs_build = self.make_custom("pg-needs", completed)
        _, needs = self.board(needs_build, "2026-01-10T15:44:00Z")
        c1 = next(piece for piece in needs["plan"]["pieces"] if piece["id"] == "C1")
        self.assertEqual((c1["state"], c1["state_label"], c1["now"]),
                         ("needs_you", "Waiting for you", "This waits on your decision."))
        self.assertTrue(needs["owner"]["needs_you"])
        self.assertEqual(needs["owner"]["items"][0]["how"], "Reply in the Conductor chat.")
        self.assertEqual(needs["owner"]["sentence"],
                         "3 of 4 pieces are done. Your answer is needed: release decision.")

        done_lines = completed + [
            {"v": 1, "span_id": "gate1", "ts": "2026-01-10T15:50:00Z",
             "end": "2026-01-10T15:50:00Z", "status": "done", "answer": "Yes",
             "plain": "You answered this decision, and the build carried on.",
             "plain_source": "auto"},
            {"v": 1, "span_id": "f1", "ts": "2026-01-10T15:51:00Z",
             "end": "2026-01-10T15:51:00Z", "status": "done"},
        ]
        done_build = self.make_custom("pg-done", done_lines)
        _, done = self.board(done_build, "2026-01-10T15:55:00Z")
        self.assertEqual(done["owner"]["sentence"], "Finished. All 4 pieces are done.")
        self.assertEqual(done["owner"]["deadline_text"], "No deadlines left.")
        self.assertTrue(all(stage["state"] == "done" for stage in done["plan"]["stages"]))

        stale_build = self.make_pg1("pg-stale")
        _, stale = self.board(stale_build, "2026-01-10T16:00:00Z")
        self.assertEqual(stale["build"]["state"], "idle")
        self.assertFalse(any(piece["state"] in ("building", "checking")
                             for piece in stale["plan"]["pieces"]))
        self.assertTrue(stale["owner"]["sentence"].endswith("none running right now."))

    def test_T_PG_46_47_and_91_old_missing_bad_extra_and_hostile_log_labels(self):
        """T-PG-46,47,91: plan fallback is ordered, warning-safe, and strips ids from labels."""
        build = self.make_pg1("pg-old", plan=False)
        _, old = self.board(build)
        self.assertFalse(old["plan"]["present"])
        self.assertEqual(old["plan"]["stages"][0]["name"], "Pieces")

        (build / "plan.json").write_text("{not json")
        _, unreadable = self.board(build)
        self.assertIn("The plan file could not be read, so the pieces come from the log.",
                      unreadable["warnings"])

        missing_build = self.make_custom("pg-missing", pg1_lines(), plan=False)
        _, missing = self.board(missing_build)
        self.assertFalse(missing["plan"]["present"])
        self.assertNotIn("The plan file could not be read, so the pieces come from the log.",
                         missing["warnings"])

        extra_lines = pg1_lines() + [
            start_line("q9", "2026-01-10T14:41:00Z", "maker", "Q9.maker.1", "Q9",
                       "sonnet-5-5", node_label="Extra work"),
            end_line("q9", "2026-01-10T14:45:00Z",
                     "The builder finished the extra work. A checker reads it next."),
        ]
        extra_build = self.make_custom("pg-extra", extra_lines)
        _, extra = self.board(extra_build)
        self.assertEqual(extra["plan"]["stages"][-1]["name"], "Other work")
        self.assertEqual(extra["plan"]["stages"][-1]["purpose"],
                         "Work in the log that the plan does not list.")
        self.assertEqual(extra["plan"]["pieces"][-1]["name"], "Extra work")

        label_build = self.factory_home / "runs" / "toy" / "pg-label"
        label_build.mkdir(parents=True)
        write_jsonl(label_build / "trace.jsonl", [
            start_line("n2", "2026-01-10T14:00:00Z", "maker", "N2.maker.1", "N2",
                       "sonnet-5-5", node_label="N2 trace core"),
            end_line("n2", "2026-01-10T14:01:00Z", "The builder finished the work."),
            start_line("k1", "2026-01-10T14:02:00Z", "maker", "K1.maker.1", "K1",
                       "sonnet-5-5", node_label="Trace core"),
            end_line("k1", "2026-01-10T14:03:00Z", "The builder finished the work."),
        ])
        write_json(label_build / "build.json", {"project": "toy", "build": "pg-label",
                                                 "started": "2026-01-10T14:00:00Z",
                                                 "stop_times": []})
        write_jsonl(label_build / "expected.jsonl", [])
        lib, labels = self.board(label_build, "2026-01-10T14:04:00Z")
        names = {piece["id"]: piece for piece in labels["plan"]["pieces"]}
        self.assertEqual(names["N2"]["name"], "A piece without a plain name")
        self.assertEqual(names["N2"]["tech_name"], "N2 trace core")
        self.assertEqual(names["K1"]["name"], "Trace core")
        for piece in names.values():
            self.assertEqual(lib.plain_label_check(piece["name"]), [])

    def test_T_PG_48_to_52_call_details_names_activity_and_all_board_words(self):
        """T-PG-48..52: call drawer data, friendly names, activity, and key-specific checks match."""
        lib, board = self.board()
        pieces = {piece["id"]: piece for piece in board["plan"]["pieces"]}
        calls = {call["call"]: call for call in pieces["B1"]["calls"]}
        maker = calls["B1.maker.1"]
        self.assertEqual((maker["label"], maker["role_name"], maker["model_name"]),
                         ("Attempt 1", "Builder", "Claude Sonnet 5.5"))
        self.assertEqual((maker["start_label"], maker["end_label"], maker["duration_label"]),
                         ("9:15 am", "9:30 am", "15 min"))
        self.assertEqual(maker["then"], "A checker reviewed it.")
        self.assertEqual(calls["B1.checker.1"]["then"], "Sent back to the builder for fixes.")
        self.assertEqual(calls["B1.maker.2"]["result"], "In progress")

        flagged_lines = pg1_lines() + [
            start_line("flagged", "2026-01-10T14:41:00Z", "maker", "C1.maker.1", "C1",
                       "sonnet-5-5"),
            {"v": 1, "span_id": "flagged", "ts": "2026-01-10T14:42:00Z",
             "end": "2026-01-10T14:42:00Z", "status": "done", "plain_flag": "missing"},
        ]
        flagged_build = self.make_custom("pg-flagged", flagged_lines)
        _, flagged_board = self.board(flagged_build)
        flagged_c1 = next(piece for piece in flagged_board["plan"]["pieces"]
                          if piece["id"] == "C1")
        flagged_call = next(call for call in flagged_c1["calls"] if call["call"] == "C1.maker.1")
        self.assertEqual(flagged_call["plain"],
                         "No plain summary has been written for this step yet.")
        self.assertEqual(flagged_call["plain_source"], "missing")

        self.assertEqual(lib.role_name("public-reviewer"), "Independent reviewer")
        self.assertEqual(lib.role_name("foo-bar"), "Foo bar")
        self.assertEqual(lib.model_name("qwen3:14b"), "Qwen 3 (14B, local)")
        self.assertEqual(lib.model_name("weird-model"), "Another AI model")
        self.assertEqual(lib.model_name(None), "Model not recorded")
        self.assertLessEqual(len(board["recent"]), 15)
        plains = [item["plain"] for item in board["recent"]]
        self.assertIn("A builder started Shout option.", plains)
        self.assertIn("A checker sent Shout option back for fixes.", plains)

        sentence_values = [
            board["owner"]["sentence"], board["owner"]["calm"]["text"],
            board["owner"]["deadline_text"],
        ]
        label_values = []
        for piece in board["plan"]["pieces"]:
            sentence_values.extend(value for value in (
                piece.get("now"), piece.get("quiet_text"),
                (piece.get("last") or {}).get("text"),
            ) if value)
            label_values.extend(value for value in (
                piece.get("name"), piece.get("state_label"), piece.get("attempt_label"),
                piece.get("summary"),
            ) if value)
        for value in sentence_values:
            self.assertEqual(lib.plain_check(value), [], value)
        for value in label_values:
            self.assertEqual(lib.plain_label_check(value), [], value)
        self.assertNotRegex(board["owner"]["sentence"], r"\d/\d")


if __name__ == "__main__":
    import unittest
    unittest.main()
