---
name: frugal
description: >-
  Spend fewer tokens without losing quality. Use when the user mentions tokens,
  usage limits, context window, cost, /compact or /clear, or a long or slow
  session; before clearing or restarting a session (write a handover); when a
  task would read large files or logs; or to audit and slim down CLAUDE.md,
  rules, skills and settings.
---

# Frugal

Keep the context small and relevant. Two jobs: work in a way that fills the
context slowly, and never lose progress when a session is cleared.

## Always (no need to be asked)

- **Search, then read.** Grep for the symbol or error first; open only the matching file.
- **Read slices.** Files over ~300 lines: read a line range, not the whole file.
- **Patch, do not rewrite.** Change the lines that change.
- **Cap output.** Pipe long commands through `tail -n 25` / `head -n 50`. No full logs.
- **Skip vendor and build folders** (`node_modules`, `venv`, `dist`, `target`, `.git`).
- **Plan before a multi-file edit:** list files and reason, then write.
- **Do not re-read** what is already in context or re-explain settled decisions.

## Handover before any clear (hard rule)

Before `/clear`, `/compact`, a restart, or when context is clearly large:

1. Run `python scripts/frugal.py handover --write` (use `python3` or `py` if needed;
   the path is relative to this skill's folder).
2. Fill the `<placeholders>` in `HANDOVER.md`: goal, state, decisions, next step, traps.
   Keep it under ~150 lines. No transcripts, no logs.
3. Tell the user: next session starts with "Read HANDOVER.md and continue from Next step."

Compact with a focus, never bare: `/compact keep <decisions and files>; drop logs`.

## Commands

| Need | Run |
|---|---|
| What loads on every session, and what to trim | `frugal.py doctor` |
| What burned context in past sessions | `frugal.py audit --project .` |
| Warn automatically when context passes 150k | `frugal.py init-config --global --hooks` (dry run), then `--apply` |
| Block reading of build/vendor folders | `frugal.py init-config` (dry run), then `--apply` |
| Handover skeleton | `frugal.py handover --write` |

Add `--lang es` for Spanish (before or after the command). Read-only unless `--write` / `--apply` is given.
Run `doctor` or `audit` before suggesting changes; fix the real top offender.

## More detail (load only when needed)

- `references/rules.md` - the full rule list with reasons
- `references/handover.md` - handover template and what to leave out
- `references/config.md` - settings levers and cautions
- `references/stacks.md` - what `init-config` blocks per technology
