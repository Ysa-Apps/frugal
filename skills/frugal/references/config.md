# Configuration levers

Permanent settings that lower token use. Apply only what fits the project.

**Before editing any settings file, read it.** Settings often already contain
hooks, MCP servers and a status line. `frugal.py init-config` merges into the
existing JSON, keeps every other key, and writes a timestamped backup first. It
is a dry run unless you pass `--apply`.

## 1. Deny reading build and vendor folders

`permissions.deny` is enforced by Claude Code: a denied path cannot be read,
even if Claude decides it is relevant. Project level
(`.claude/settings.json`) is the right home, because the list depends on the
repo, not the machine.

```json
{ "permissions": { "deny": ["Read(./node_modules/**)", "Read(./dist/**)"] } }
```

`init-config` detects the technology and proposes the right list
(see `stacks.md`). `init-config --global` adds only the universal rules to
`~/.claude/settings.json`.

## 2. Keep CLAUDE.md lean

It loads on every message. Remove anything Claude can infer from the code.
HTML comments (`<!-- note -->`) are stripped before loading, so they cost
nothing and are fine for human-only notes. `doctor` flags oversized files and
paths mentioned in them that no longer exist.

## 3. Scope rules by path

Files in `.claude/rules/` without a `paths:` list in their frontmatter load
every session. Add it so they load only when matching files are touched:

```markdown
---
paths:
  - "src/api/**"
---
API rules here.
```

## 4. Skills are cheap, MCP servers are not

A skill costs only its name and description at startup; the body loads on use.
Each MCP server adds its tool list to every session, so disconnect the ones you
are not using, and do it at the start of a session rather than in the middle.

## 5. Useful built-in commands

`/context` shows what fills the window, `/usage` shows limits, `/memory` shows
which memory files loaded, `/compact <focus>` summarises, `/clear` resets.
