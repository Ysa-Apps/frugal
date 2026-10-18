# Handover protocol

A handover file bridges a `/clear`. Everything else in the session is lost; this
is what the next session reads to continue without paying for the old history.

## When to write one (before, never after)

- the user types or mentions `/clear` or `/compact`
- the user says the session is slow, full, or they are starting fresh
- a work block ends (feature done, bug fixed, end of day)
- the user asks for a summary to continue from

If a clear is imminent and there is no handover yet, write it first and say so.

## What goes in

1. **Goal** - one or two sentences.
2. **State** - done, in flight (and how far), not started.
3. **Key decisions** - and the reason, so they are not reopened. Highest value section.
4. **Files that matter** - path and line range, not contents.
5. **Next step** - one concrete action: command, file, expected result.
6. **Traps** - failures already hit, dead ends already explored.
7. **Verify with** - one command that proves the work is fine.

## What stays out

- transcript or a story of what happened
- logs, stack traces (keep the one-line conclusion)
- file contents the next session can read itself
- anything already in git history, README or CLAUDE.md
- speculative future work nobody asked for
- secrets, passwords, tokens, customer data

Aim for under ~150 lines. A handover that needs skimming has already failed.

## Tooling

`frugal.py handover --write` creates `HANDOVER.md` with this structure and the
objective state (branch, recent commits, uncommitted changes). If the file
already exists it appends a dated section instead of overwriting. In a git
repository it also adds `HANDOVER.md` to `.gitignore` (use `--no-gitignore` to
skip), because handovers often hold project details.

Start the next session with: "Read HANDOVER.md and continue from Next step."
