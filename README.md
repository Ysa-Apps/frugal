# Frugal

**Spend fewer tokens in Claude Code without losing quality.** A small skill plus one
cross-platform Python tool that shows what fills your context, trims what loads on
every session, and saves your progress before you clear a long session.

Status: **0.1 beta.** Tested with automated tests on Linux (Python 3.11-3.13). Windows and
macOS checks are listed in [MANUAL_CHECKS.md](MANUAL_CHECKS.md). Feedback welcome.

## Why

Every message you send re-sends the whole conversation. Everything Claude has read stays in
that history and is paid for again on each later turn, and long, noisy contexts also make
answers worse. Frugal attacks the three things you can control:

1. **What loads on every session** (`doctor`): oversized CLAUDE.md, rules with no path filter,
   too many skills or MCP servers, stale instructions.
2. **What actually burned context** (`audit`): your own session logs, ranked by tool and by
   single result, plus the peak context any message reached.
3. **What you lose when you clear** (`handover`): a short HANDOVER.md so the next session starts
   small and still knows the goal, decisions and next step.

It also installs a few cheap working habits (search before reading, read slices, patch instead
of rewrite, cap command output) and can add read-deny rules for build and vendor folders.

It does **not** disable reasoning, shorten answers, or switch models. Those can lower quality.

## Install

Requires Python 3.8+ and Claude Code. No other dependencies.

Copy the `skills/frugal` folder to one of:

| Scope | Folder |
|---|---|
| Just this project | `<project>/.claude/skills/frugal` |
| All your projects (macOS/Linux) | `~/.claude/skills/frugal` |
| All your projects (Windows) | `%USERPROFILE%\.claude\skills\frugal` |

That is all. Claude loads the skill when you talk about tokens, context, cost, `/clear` or
`/compact`, and applies the habits on long tasks.

## Use

Run these yourself, or ask Claude to run them. From the skill folder (use `python3` or `py`
if `python` is not found):

```
python scripts/frugal.py doctor                 # what loads on every session
python scripts/frugal.py audit --project .      # what burned context in this project
python scripts/frugal.py handover --write       # create/append HANDOVER.md
python scripts/frugal.py init-config            # dry run: proposed read-deny rules
python scripts/frugal.py init-config --apply    # write them (backup made first)
python scripts/frugal.py init-config --global --hooks --apply   # automatic warning at ~150k context
```

Add `--lang es` for Spanish, `--json` to `doctor` or `audit` for machine-readable output.

### Safety

- Everything is read-only except `handover --write` and `init-config --apply`.
- `init-config` never removes rules or other settings, refuses to touch a settings file it
  cannot parse, and writes a timestamped backup before any change.
- `handover --write` appends instead of overwriting, and adds `HANDOVER.md` to `.gitignore`
  (git repositories only; `--no-gitignore` to skip) because handovers can hold project details.
- `audit` reads the logs Claude Code keeps on your own machine and sends nothing anywhere.
  Its output can contain commands and file names: check it before sharing.

### Measure, do not guess

Savings depend on how you work. To see yours:

```
python scripts/frugal.py audit --json > before.json
# work for a while with Frugal's habits and settings
python scripts/frugal.py audit --json > after.json
```

Compare `new_token_spend` and `peak_context` for similar tasks.

## Supported technologies for `init-config`

Node, Python, Java, Go, Rust, PHP, Ruby, .NET, Flutter and Odoo, detected from marker files.
See `skills/frugal/references/stacks.md`. Adding one is a single entry in `STACKS`.

## Develop

```
python -m unittest discover -s tests -v
```

## License

MIT. Based on [save_tokens_skill](https://github.com/roeea2/save_tokens_skill) by RoeeAI
(MIT); see [NOTICE](NOTICE). Made by YSA Apps.
