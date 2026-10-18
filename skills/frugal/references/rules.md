# Frugal rules

Why these work: every message re-sends the whole conversation. Anything Claude
reads stays in that history and is paid for again on every later turn. Keeping
the history small is cheaper and also keeps answers sharper, because there is
less noise to reason around.

## Working habits (Claude applies these by itself)

1. **Search, then read.** Locate first (`grep -rn "name" src`), open second.
2. **Read slices.** Use line ranges for big files. Whole-file reads are a last resort.
3. **Patch, do not rewrite.** Rewriting 400 lines to fix one is the commonest avoidable cost.
4. **Cap command output.** `tail`, `head`, `wc -l`. Never print a whole build log or `ls -R`.
5. **No polling loops.** Check once, or read the specific log. Repeating a failing command wastes tokens.
6. **Skip vendor and build folders.** Dependencies are never the answer to your question.
7. **Plan before multi-file edits.** A wrong edit costs the write and the undo.
8. **Do not re-read or re-derive.** If it is in the conversation, use it.
9. **Ask for the narrow version.** If a task would pull in something huge, say so and propose a smaller slice first.

## Session habits (the user applies these; Claude reminds)

10. **One task per session.** Finish, write a handover, `/clear`.
11. **Compact with a focus.** Name what must survive; drop logs and dead ends.
12. **Check `/context` and `/usage`** before a big push, and size the task to fit.
13. **Keep CLAUDE.md short.** It is paid on every message. Keep only what Claude cannot learn from the code.
14. **Scope rules with `paths:`.** Rules without it load every session.
15. **Disconnect MCP servers you are not using.** Each adds its tool list to every session.
16. **Paste less.** Save large text to a file and point Claude at it; pasted text rides along every turn.

## What not to do

- Do not switch off reasoning or force one-line answers on hard problems. That trades tokens for wrong answers.
- Do not send complex architecture or tricky bugs to a weaker model just to save cost.
- Do not trust any saving figure you have not measured: run `audit --json` before and after.
