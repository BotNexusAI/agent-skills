import contextlib
import io
import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml


SCRIPT = Path(__file__).parents[1] / "skills" / "linear-ops" / "scripts" / "linear_ops.py"
EXAMPLE_CONFIG = (
    Path(__file__).parents[1]
    / "skills"
    / "linear-ops"
    / "assets"
    / "linear-routing.example.yaml"
)

spec = importlib.util.spec_from_file_location("linear_ops", SCRIPT)
linear_ops = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(linear_ops)


def issue(identifier, *, state="Ready", state_type="started", labels=None, project="Example Product"):
    return {
        "identifier": identifier,
        "title": f"Issue {identifier}",
        "url": f"https://linear.app/example/issue/{identifier}",
        "priority": 3,
        "updatedAt": "2026-09-15T12:00:00",
        "state": {"name": state, "type": state_type},
        "team": {"key": "EXM", "name": "Example Team"},
        "project": {"name": project},
        "assignee": {},
        "labels": {"nodes": [{"name": label} for label in labels or []]},
    }


class LinearOpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))

    def test_example_config_is_valid(self):
        self.assertEqual(linear_ops.validate_config(self.config), [])

    def test_validator_rejects_crash_inducing_nested_config(self):
        invalid = dict(self.config)
        invalid["workspace"] = {}
        invalid["defaults"] = {"team": {}}
        errors = linear_ops.validate_config(invalid)
        self.assertIn("workspace must include a non-empty name", errors)
        self.assertIn("defaults.team must include key or name", errors)

    def test_planned_project_domain_is_valid(self):
        config = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        config["domains"]["product"].pop("project")
        config["domains"]["product"]["planned_project"] = "Planned Product"
        self.assertEqual(linear_ops.validate_config(config), [])

    def test_unknown_domain_is_an_error(self):
        with self.assertRaises(SystemExit):
            linear_ops.pick_domain(self.config, "typo")

    def test_dashboard_filters_use_and_within_view_and_or_across_views(self):
        issues = [
            issue("EXM-1", labels=["blocked"]),
            issue("EXM-2", project="Example Platform"),
            issue("EXM-3", state="Done", state_type="completed"),
        ]
        filtered = linear_ops.issues_for_dashboard(self.config, issues)
        self.assertEqual(
            [item["identifier"] for item in filtered], ["EXM-1", "EXM-2", "EXM-3"]
        )

    def test_seed_without_assignee_matches_unassigned_view(self):
        config = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        config["dashboard_views"] = [{"name": "Unassigned", "filters": {"unassigned": True}}]
        seed = {"title": "Unassigned work", "domain": "product", "type": "feature", "summary": "s"}
        seeded = linear_ops.seed_ticket_to_issue(config, seed, 1)
        self.assertTrue(linear_ops.issue_matches_view(seeded, {"unassigned": True}))

    def test_seed_loader_rejects_invalid_list_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            seed_path = Path(directory) / "seed.yaml"
            seed_path.write_text(
                "tickets:\n"
                "  - title: Invalid\n"
                "    domain: product\n"
                "    type: feature\n"
                "    summary: Bad labels\n"
                "    labels: not-a-list\n",
                encoding="utf-8",
            )
            with self.assertRaises(SystemExit):
                linear_ops.load_seed_tickets(seed_path)

    def test_dashboard_handles_naive_timestamps(self):
        content = linear_ops.render_dashboard_html(self.config, [issue("EXM-1")], mode="seed")
        self.assertIn("EXM-1", content)

    def test_dashboard_includes_completed_work(self):
        completed = issue("EXM-3", state="Done", state_type="completed")
        content = linear_ops.render_dashboard_html(self.config, [completed], mode="live")
        self.assertIn("Recently Completed Work", content)
        self.assertIn("EXM-3", content)

    def test_dashboard_drops_unsafe_links(self):
        unsafe = issue("EXM-1")
        unsafe["url"] = "javascript:alert(1)"
        content = linear_ops.issue_card_html(unsafe)
        self.assertNotIn("javascript:", content)
        self.assertNotIn("<a href=", content)

    def test_prefilled_url_uses_documented_lowercase_priority(self):
        url = linear_ops.ticket_url_from_fields(
            self.config,
            "product",
            self.config["domains"]["product"],
            "feature",
            "Example issue",
            "Example summary",
            [],
            "High",
            "Triage",
        )
        self.assertIn("priority=high", url)

    def test_dashboard_html_sources_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            linear_ops.build_parser().parse_args(
                ["dashboard-html", "--config", "config.yaml", "--live", "--seed", "seed.yaml"]
            )


if __name__ == "__main__":
    unittest.main()
