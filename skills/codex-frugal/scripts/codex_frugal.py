#!/usr/bin/env python3
"""Local context hygiene helper for Codex projects.

It intentionally does not inspect conversation databases or claim to measure
account credits. It reports static contributors that a user controls.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".venv", "venv", "node_modules", "dist", "build", "target", "coverage", "filestore"}
TEXT_SUFFIXES = {".py", ".xml", ".js", ".ts", ".tsx", ".jsx", ".md", ".rst", ".txt", ".json", ".toml", ".yaml", ".yml", ".csv", ".html", ".css"}


def codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def tokens(path):
    try:
        return path.stat().st_size // 4
    except OSError:
        return 0


def instructions(project):
    result = []
    global_file = codex_home() / "AGENTS.md"
    if global_file.is_file():
        result.append(global_file)
    for parent in reversed([project, *project.parents]):
        candidate = parent / "AGENTS.md"
        if candidate.is_file() and candidate not in result:
            result.append(candidate)
    return result


def skills():
    root = codex_home() / "skills"
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".") and path.name != ".system" and (path / "SKILL.md").is_file())


def git(project, args):
    try:
        result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, timeout=10, check=False)
    except OSError:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def doctor(project):
    print("CODEX FRUGAL DOCTOR")
    print(f"Project: {project}")
    files = instructions(project)
    total = sum(tokens(path) for path in files)
    print(f"Instruction files: {len(files)} (~{total:,} estimated tokens)")
    for path in files:
        print(f"  - {path} (~{tokens(path):,})")
    if total > 4000:
        print("Advice: keep persistent instructions to rules Codex cannot infer from the repository.")
    available = skills()
    print(f"User-installed skills: {len(available)}")
    for path in available:
        print(f"  - {path.name}")
    if len(available) > 20:
        print("Advice: remove unused skills or tighten descriptions so discovery stays focused.")
    found = [name for name in sorted(SKIP_DIRS) if (project / name).exists()]
    if found:
        print("Generated/vendor folders detected: " + ", ".join(found))
        print("Advice: do not inspect these folders unless directly relevant to the task.")
    return 0


def audit(project):
    print("CODEX FRUGAL STATIC AUDIT")
    print("This is a context-risk review, not a measurement of Codex credits or hidden model tokens.")
    candidates, scanned = [], 0
    for root, dirs, files in os.walk(project):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            scanned += 1
            if scanned > 5000:
                print("Scan stopped at 5,000 text files; narrow the project scope for a deeper audit.")
                break
            try:
                with path.open("r", encoding="utf-8", errors="ignore") as handle:
                    lines = sum(1 for _ in handle)
                size = path.stat().st_size
            except OSError:
                continue
            if lines > 300 or size > 50_000:
                candidates.append((size, lines, path.relative_to(project)))
        if scanned > 5000:
            break
    print(f"Text files scanned: {scanned}")
    if candidates:
        print("Largest files worth reading by search and ranges, not wholesale:")
        for size, lines, path in sorted(candidates, reverse=True)[:12]:
            print(f"  - {path} ({lines:,} lines, ~{size // 4:,} estimated tokens)")
    else:
        print("No large text files detected outside ignored folders.")
    print("Tip: use rg first, then request only the matching line range.")
    return 0


def handover(project, write):
    branch = git(project, ["branch", "--show-current"]) or "not a git repository"
    status = git(project, ["status", "--short"]) or "(clean or not a git repository)"
    commits = git(project, ["log", "--oneline", "-5"]) or "(not available)"
    content = f'''\n## Handover - {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n### Goal\n- <requested outcome>\n\n### State\n- Branch: {branch}\n- Done: <verified work>\n- In progress: <exact current state>\n- Pending: <remaining scope>\n\n### Decisions\n- <decision and reason>\n\n### Files that matter\n- <path and why it matters>\n\n### Uncommitted changes\n```text\n{status}\n```\n\n### Recent commits\n```text\n{commits}\n```\n\n### Next step\n- <one concrete action and expected result>\n\n### Verification\n- <command or functional test>\n'''
    target = project / "HANDOVER.md"
    if write:
        with target.open("a" if target.exists() else "w", encoding="utf-8") as handle:
            handle.write(content)
        print(f"Wrote {target}. Complete placeholders before starting a new chat.")
    else:
        print(content.strip())
        print("Preview only. Re-run with --write to append it to HANDOVER.md.")
    return 0


def report(project, write):
    """Preview or append a short, evidence-first improvement report."""
    content = f'''\n## Frugal report - {datetime.now().strftime("%Y-%m-%d %H:%M")}\n\n### Task\n- <brief outcome requested>\n\n### Observations\n- Helped: <search, narrow read, exclusion or handover that avoided irrelevant context>\n- Did not help: <rule or tool behavior that was not useful>\n- Risk found: <large folder, repetitive history or ambiguous instruction>\n\n### Evidence\n- <file count, command result or other observable fact; do not estimate account credits>\n\n### Proposed skill change\n- <one small, evidence-based improvement; or "none">\n'''
    target = project / "CODEX_FRUGAL_REPORT.md"
    if write:
        with target.open("a" if target.exists() else "w", encoding="utf-8") as handle:
            handle.write(content)
        print(f"Wrote {target}. Complete placeholders with task evidence.")
    else:
        print(content.strip())
        print("Preview only. Re-run with --write to append it to CODEX_FRUGAL_REPORT.md.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Local context hygiene helper for Codex")
    parser.add_argument("command", choices=("doctor", "audit", "handover", "report"))
    parser.add_argument("--project", default=".", help="Project folder; defaults to the current folder")
    parser.add_argument("--write", action="store_true", help="Write a handover or report template")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    if not project.is_dir():
        parser.error(f"Project folder does not exist: {project}")
    if args.write and args.command not in {"handover", "report"}:
        parser.error("--write is only valid with handover or report")
    if args.command == "doctor":
        return doctor(project)
    if args.command == "audit":
        return audit(project)
    if args.command == "report":
        return report(project, args.write)
    return handover(project, args.write)


if __name__ == "__main__":
    raise SystemExit(main())
