# Frugal

**Spend fewer tokens without losing quality.** Frugal includes separate skills
for Claude Code and Codex. Both encourage smaller, relevant context and a
useful handover; each keeps its own platform-specific behavior.

**Author:** [Jonathan Leonardo Yncio Salazar](https://github.com/jsleoslzr)

**Publisher and maintainer:** [YSA Apps](https://github.com/Ysa-Apps)

**License:** MIT

Status: **0.3 beta.** Frugal is free and open source. The Claude Code edition
has automated tests on Linux (Python 3.11-3.13); the Codex edition has local
syntax, structure and command smoke-test validation. Windows and macOS checks
are listed in [MANUAL_CHECKS.md](MANUAL_CHECKS.md). Feedback is welcome.

## Editions

| Platform | Folder | What it can inspect |
|---|---|---|
| Claude Code | `skills/frugal/` | Claude settings and local session logs |
| Codex | `skills/codex-frugal/` | Project instructions, installed skills and static context risks |

The editions must not be mixed. Claude Code uses `.claude` settings and hooks;
Codex uses `AGENTS.md` and Codex's local skills folder.

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

### Codex

Requires Python 3.8+ and Codex. Copy the contents of `skills/codex-frugal/`
to the local Codex skill folder:

| Scope | Folder |
|---|---|
| All your projects (Windows) | `%USERPROFILE%\\.codex\\skills\\codex-frugal` |
| All your projects (macOS/Linux) | `~/.codex/skills/codex-frugal` |

Start a new Codex chat if the skill does not appear immediately. The Codex
edition applies the same working habits but does not read Claude logs, install
hooks, modify settings or claim a measurement of account credits.

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

### Codex edition

From the `skills/codex-frugal/` folder, or with the full path to its script:

```
python scripts/codex_frugal.py doctor --project .   # instruction and skill overhead
python scripts/codex_frugal.py audit --project .    # large files and folders to avoid loading wholesale
python scripts/codex_frugal.py handover --write --project .
python scripts/codex_frugal.py report --write --project .
python scripts/codex_frugal.py usage snapshot --plan free --used-percent 62 --days-to-reset 29.98 --record
python scripts/codex_frugal.py usage history
```

`audit` is a static context-risk review; it does not access Codex conversation
history, hidden model tokens or billing. `usage snapshot` records values
explicitly supplied from Codex Usage settings in a local JSONL file; `usage
history` compares those local records without contacting an external service.
The report records observable habits and risks so the skill can improve over
repeated use.

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
