"""Smoke tests for the Codex edition without requiring Codex itself."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "codex-frugal" / "scripts" / "codex_frugal.py"


class CodexFrugalTests(unittest.TestCase):
    def run_command(self, command: str, project: Path) -> str:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, "--project", str(project)],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_diagnostics_are_read_only_previews(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "large.py").write_text("x = 1\n" * 301, encoding="utf-8")

            self.assertIn("CODEX FRUGAL DOCTOR", self.run_command("doctor", project))
            self.assertIn("large.py", self.run_command("audit", project))
            self.assertIn("Preview only", self.run_command("handover", project))
            self.assertIn("Preview only", self.run_command("report", project))

            self.assertFalse((project / "HANDOVER.md").exists())
            self.assertFalse((project / "CODEX_FRUGAL_REPORT.md").exists())

    def test_usage_calculates_remaining_daily_budget_from_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            output = self.run_command("usage", project)
            self.assertIn("Used: not provided", output)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "usage",
                    "--project",
                    str(project),
                    "--plan",
                    "free",
                    "--used-percent",
                    "44",
                    "--days-to-reset",
                    "30",
                    "--resets",
                    "1",
                ],
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Remaining daily budget: 1.87%", result.stdout)
            self.assertIn("Compare two snapshots", result.stdout)

    def test_usage_snapshot_record_stays_outside_project(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as codex_directory:
            project = Path(directory)
            environment = {**os.environ, "CODEX_HOME": codex_directory}
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "usage",
                    "snapshot",
                    "--project",
                    str(project),
                    "--record",
                    "--plan",
                    "free",
                    "--used-percent",
                    "62",
                    "--days-to-reset",
                    "29.98",
                    "--task",
                    "usage audit",
                    "--complexity",
                    "hard",
                ],
                capture_output=True,
                encoding="utf-8",
                env=environment,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            history = Path(codex_directory) / "frugal" / "usage-history.jsonl"
            self.assertTrue(history.exists())
            record = json.loads(history.read_text(encoding="utf-8"))
            self.assertEqual(record["used_percent"], 62.0)
            self.assertEqual(record["complexity"], "hard")

            history_result = subprocess.run(
                [sys.executable, str(SCRIPT), "usage", "history", "--project", str(project)],
                capture_output=True,
                encoding="utf-8",
                env=environment,
                check=False,
            )
            self.assertEqual(history_result.returncode, 0, history_result.stderr)
            self.assertIn("Local records: 1", history_result.stdout)
            self.assertIn("insufficient data", history_result.stdout)

    def test_usage_history_does_not_compare_across_reset_windows(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as codex_directory:
            project = Path(directory)
            history = Path(codex_directory) / "frugal" / "usage-history.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text(
                "\n".join(
                    [
                        json.dumps({"recorded_at": "first", "used_percent": 70, "reset_at": "old", "plan": "free"}),
                        json.dumps({"recorded_at": "second", "used_percent": 2, "reset_at": "new", "plan": "free"}),
                    ]
                ) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "usage", "history", "--project", str(project)],
                capture_output=True,
                encoding="utf-8",
                env={**os.environ, "CODEX_HOME": codex_directory},
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("new allowance window detected", result.stdout)
            self.assertNotIn("-68.0", result.stdout)


if __name__ == "__main__":
    unittest.main()
