# Manual checks (things automated tests on Linux cannot prove)

Do these once on a real install before calling a release stable. Tick and note the OS and
Python version.

## Windows (PowerShell)

1. `python --version` (or `py --version`) shows 3.8 or newer.
2. Copy `skills\frugal` to `%USERPROFILE%\.claude\skills\frugal`.
3. In a real project: `python <skill>\scripts\frugal.py doctor` runs with no error and the
   text is readable (accents appear correctly with `--lang es`).
4. `audit --project .` finds that project's sessions. **Confirm the log folder name**: open
   `%USERPROFILE%\.claude\projects` and check the project folder is named like
   `C--Users-Name-Folder` (drive letter, then every symbol replaced by `-`). If not, report it.
5. `init-config` (dry run) lists sensible rules; `--apply` creates `.claude\settings.json`
   and, on a second run, a `.bak-` file appears and nothing else changes.
6. In a git project, `handover --write` creates HANDOVER.md and adds it to `.gitignore`.
7. Start Claude Code, say "my session is getting long, I want to clear it": Frugal should
   trigger and write a handover before the clear.

## macOS / Linux

Same steps with `python3` and `~/.claude/...`.

## After a week of use

Run `audit --json` and compare `new_token_spend` / `peak_context` with a week before for
comparable work. Record the real numbers in the README instead of any marketing figure.
