---
name: codex-frugal
description: Reduce avoidable Codex context use in long or expensive tasks. Use when the user mentions tokens, credits, context, usage limits, slow sessions, continuing prior work, or asks to audit context overhead. Do not use for billing or account-limit questions that require the Codex usage tools.
---

# Codex Frugal

Keep context relevant in any kind of project: code, documents, analysis,
research, automation or product work. It does not prescribe a technology,
repository layout or delivery process. This skill is for controllable context
overhead, not for estimating or changing account credits.

## Working rules

- Search before reading. Use `rg` for a symbol, error, or filename, then open only the needed ranges.
- Do not load generated, vendor, cache, minified, database, or build files unless they are directly relevant.
- Keep command output bounded. Request the relevant file names, lines, or final log section rather than full output.
- Reuse facts already established in the active conversation. Do not reread a file unless it changed or a precise detail is needed.
- For a multi-file change, identify the files and validation path before editing.
- Do not skip tests, source inspection, or safety checks merely to save context.

## Improvement loop

Use the skill as an experiment, not as a promise of a fixed token reduction.

1. At the beginning of a non-trivial task, run `doctor`; run `audit` when the
   folder is broad or unfamiliar.
2. During the task, record only material observations: a large folder avoided,
   a narrow search that found the answer, a repeated read, or an instruction
   that added noise.
3. At the end, give a short report: what helped, what did not help, and one
   proposed improvement.
4. Change this skill only after there is evidence from repeated use, and keep
   the change small and reversible.

Never report estimated account-credit savings as fact. Report decisions and
observable context risks instead.

## Long conversations and handover

When a task spans many turns, context is clearly repetitive, or the user wants to continue later:

1. Run `python scripts/codex_frugal.py handover` from the project root to preview the handover.
2. Run it with `--write` only after the user asks to create the file.
3. Complete the placeholders in `HANDOVER.md` with the confirmed goal, decisions, changed files, pending work, and exact next step.
4. Tell the user that a new chat can begin with: `Read HANDOVER.md and continue from Next step.`

Codex may compact conversation state automatically. A handover is still useful for durable project state and for starting a clean, focused chat; it is not a replacement for required project documentation.

## Diagnostic commands

Run the helper from the project root when useful:

```powershell
python $env:USERPROFILE\.codex\skills\codex-frugal\scripts\codex_frugal.py doctor
python $env:USERPROFILE\.codex\skills\codex-frugal\scripts\codex_frugal.py audit
python $env:USERPROFILE\.codex\skills\codex-frugal\scripts\codex_frugal.py handover
python $env:USERPROFILE\.codex\skills\codex-frugal\scripts\codex_frugal.py report
```

- `doctor` identifies instruction files and installed skills that may add fixed context.
- `audit` is a static context-risk review of the current project. It does not claim to measure Codex account credits or hidden model tokens.
- `handover --write` creates or appends a concise `HANDOVER.md`; it is the only write operation.
- `report --write` creates or appends a concise `CODEX_FRUGAL_REPORT.md`.
  Complete its placeholders with observations from the task; do not use it to
  claim an unmeasured credit reduction.

Before recommending configuration changes, run `doctor` or `audit` and address the largest relevant contributor first. Do not alter global Codex settings, plugins, skills, or project ignore rules unless the user explicitly asks.
