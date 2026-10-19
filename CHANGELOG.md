# Changelog

## 0.3.0
- Added `skills/codex-frugal`, a Codex-specific edition for general context
  hygiene across code, documents, analysis, research, automation and product
  work.
- Added Codex `doctor`, static `audit`, `handover` and `report` commands.
- Documented both editions and their separate installation paths. The Codex
  edition does not inspect Claude logs or claim to measure account credits.

## 0.2.1
- `--lang` now works before or after the subcommand (`frugal.py doctor --lang es` used to fail).
- `doctor`, stale paths: the `frugal-ignore` marker inside an HTML comment now works (comments were
  removed before the marker was checked). Fewer false alarms: a bare file name counts as present when
  it exists anywhere in the project, and any path counts as present when it exists on another local
  git branch (one CLAUDE.md shared by several release branches). The warning says how to silence a
  path cited on purpose.

## 0.2.0 (beta)
- Automatic mode: `init-config --hooks` installs three hooks (dry run first, backup on apply):
  - UserPromptSubmit: when the context passes 150k tokens (`--threshold` / `FRUGAL_THRESHOLD`),
    Claude ends its reply with a short notice and a copy-paste handover prompt. Repeats only
    after +50k more.
  - PreCompact: saves the objective project state to `.frugal/STATE.md` (git-ignored).
  - SessionStart: a one-line reading rule on every fresh session (grep first, read ranges, do not
    re-read files, trim command output) plus a line when a fresh HANDOVER.md exists.
  - The 150k notice now says to do it right away instead of finishing the task first.
- `status`: shows the latest session's context, whether the hooks are installed, the last warning and a plain verdict.
- `audit`: new columns for average context per message.
- Hooks never raise and never block the session.
- Handover template gains an "Outside the repo" section (tools living in temp folders).
- `doctor`: lines containing `frugal-ignore` are skipped by the stale-path check.

## 0.1.0 (beta)
- `doctor`: static check of what loads on every session (CLAUDE.md, unscoped rules,
  skills, MCP servers, missing deny rules, stale paths, HANDOVER.md in .gitignore).
- `audit`: ranks sessions, tools and single results by context cost; reports peak context.
- `handover`: prints project state or writes/appends HANDOVER.md; keeps it out of git.
- `init-config`: detects the technology, proposes read-deny rules, dry run by default,
  merges into existing settings with a backup.
- English and Spanish output (`--lang`). Python 3.8+, standard library only.
- Differences from the original: logs are always read as UTF-8 (the platform default
  encoding can corrupt them on Windows), and project log folders are found by replacing every
  non-alphanumeric character with a hyphen, which also covers Windows drive letters
  (to be confirmed on a real Windows install: see MANUAL_CHECKS.md).
