"""Smoke tests for the Codex edition without requiring Codex itself."""

from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
