#!/usr/bin/env python3
"""Frugal - spend fewer tokens in Claude Code without losing quality.

Six commands, standard library only (Python 3.8+), works on Windows, macOS
and Linux:

    frugal.py doctor       static check of what loads on every session
    frugal.py audit        rank what actually burned context in past sessions
    frugal.py handover     collect project state / write HANDOVER.md
    frugal.py init-config  propose (and optionally apply) read-deny rules and hooks
    frugal.py status       is the automatic warning working? (context now, hooks, verdict)
    frugal.py hook         run by Claude Code itself (context warning, state snapshot)

Read-only by default. Only `handover --write`, `init-config --apply` and the
PreCompact hook (a small .frugal/STATE.md snapshot) write files.

Frugal is based on save_tokens_skill by RoeeAI (MIT). See NOTICE.
"""

import argparse
import json
import locale
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

__version__ = "0.2.1"

CHARS_PER_TOKEN = 4  # rough estimate, good enough to rank things

# --------------------------------------------------------------------------
# Language (English source strings + Spanish translation)
# --------------------------------------------------------------------------

LANG = "en"

ES = {
    "FRUGAL DOCTOR": "DIAGNÓSTICO FRUGAL",
    "Project": "Proyecto",
    "Loaded on every session (estimated tokens)": "Se carga en cada sesión (tokens estimados)",
    "Always-on total": "Total siempre cargado",
    "Findings": "Hallazgos",
    "Nothing to fix. Your always-on context looks lean.": "Nada que corregir. Tu contexto fijo se ve liviano.",
    "{label} is about {tokens} tokens ({lines} lines). It is paid on every message. "
    "Keep only what Claude cannot infer from the code (aim for under ~1,000 tokens).":
        "{label} pesa unos {tokens} tokens ({lines} líneas). Se paga en cada mensaje. "
        "Deja solo lo que Claude no puede deducir del código (apunta a menos de ~1.000 tokens).",
    "{count} rule file(s) have no `paths:` filter, so they load on every session "
    "(~{tokens} tokens). Add `paths:` frontmatter so they load only when needed: {names}":
        "{count} archivo(s) de reglas no tienen filtro `paths:`, así que se cargan en cada sesión "
        "(~{tokens} tokens). Agrega `paths:` en el encabezado para que se carguen solo cuando hacen falta: {names}",
    "{count} skills are installed; their names and descriptions (~{tokens} tokens) load at startup. "
    "Remove the ones you do not use.":
        "Hay {count} skills instaladas; sus nombres y descripciones (~{tokens} tokens) se cargan al inicio. "
        "Quita las que no uses.",
    "Skill '{name}' has a very long description (~{tokens} tokens). Shorter descriptions cost less at startup.":
        "La skill '{name}' tiene una descripción muy larga (~{tokens} tokens). Descripciones más cortas cuestan menos al inicio.",
    "{count} MCP server(s) configured. Each one adds its tool list to every session "
    "(often thousands of tokens). Disconnect the ones you are not using: {names}":
        "Hay {count} servidor(es) MCP configurado(s). Cada uno agrega su lista de herramientas a cada sesión "
        "(a menudo miles de tokens). Desconecta los que no uses: {names}",
    "No read-deny rules for build/vendor folders detected for this project ({stacks}). "
    "Run `init-config` to see a safe proposal. Missing: {missing}":
        "No hay reglas que bloqueen la lectura de carpetas de compilación o dependencias para este proyecto ({stacks}). "
        "Ejecuta `init-config` para ver una propuesta segura. Faltan: {missing}",
    "{path} mentions paths that do not exist (stale instructions are followed with confidence): {names}. "
    "If a path is cited on purpose (it lives outside the project), add `frugal-ignore` to that line.":
        "{path} menciona rutas que no existen (Claude sigue con confianza las instrucciones viejas): {names}. "
        "Si una ruta se cita a propósito (está fuera del proyecto), agrega `frugal-ignore` en esa línea.",
    "HANDOVER.md exists but is not in .gitignore. It may contain project details; "
    "run `handover --write` once or add it to .gitignore.":
        "HANDOVER.md existe pero no está en .gitignore. Puede contener detalles del proyecto; "
        "ejecuta `handover --write` una vez o agrégalo a .gitignore.",
    "No CLAUDE.md found in this project. Not an error; add one only for things Claude cannot infer.":
        "No hay CLAUDE.md en este proyecto. No es un error; agrégalo solo para lo que Claude no pueda deducir.",
    "Detected stack(s)": "Tecnologías detectadas",
    "none": "ninguna",
    "TOKEN AUDIT": "AUDITORÍA DE TOKENS",
    "session(s) under": "sesión(es) en",
    "SESSIONS (newest first)": "SESIONES (más recientes primero)",
    "when": "cuándo",
    "project": "proyecto",
    "output": "salida",
    "peak ctx": "ctx máx.",
    "Totals": "Totales",
    "cache writes": "escrituras de caché",
    "cache reads": "lecturas de caché",
    "new-token spend": "gasto de tokens nuevos",
    "(cache reads are the cheap path; peak ctx is the largest context a single message carried)":
        "(las lecturas de caché son la vía barata; ctx máx. es el contexto más grande que llevó un mensaje)",
    "TOOL RESULT VOLUME (what entered the context, est. tokens)":
        "VOLUMEN POR HERRAMIENTA (lo que entró al contexto, tokens estimados)",
    "tool": "herramienta",
    "calls": "llamadas",
    "HEAVIEST INDIVIDUAL RESULTS": "RESULTADOS INDIVIDUALES MÁS PESADOS",
    "WHAT TO FIX": "QUÉ CORREGIR",
    "Nothing pathological in this window. Keep clearing between tasks and writing handovers.":
        "Nada anormal en este periodo. Sigue limpiando entre tareas y escribiendo traspasos.",
    "{count} single result(s) over ~10k tokens: bound those commands or read narrower slices.":
        "{count} resultado(s) de más de ~10k tokens: limita esos comandos o lee trozos más pequeños.",
    "Read dominates: grep for the symbol first, then read only the matching line range.":
        "Domina Read: busca primero el símbolo con grep y lee solo el rango de líneas que coincide.",
    "Bash dominates: pipe commands through `tail -n 25` / `head -n 50` and stop streaming full logs.":
        "Domina Bash: limita los comandos con `tail -n 25` / `head -n 50` y no muestres logs completos.",
    "Vendor or build folders were read: run `init-config` to block them.":
        "Se leyeron carpetas de dependencias o compilación: ejecuta `init-config` para bloquearlas.",
    "A session reached ~{tokens} tokens of context in one message. Past roughly 150k, quality and cost "
    "both suffer: write a handover and /clear between tasks.":
        "Una sesión llegó a ~{tokens} tokens de contexto en un solo mensaje. Pasados unos 150k, la calidad y el costo "
        "empeoran: escribe un traspaso y usa /clear entre tareas.",
    "No session logs found at {root}": "No se encontraron registros de sesiones en {root}",
    "No sessions matched.": "Ninguna sesión coincide.",
    "No logs for project folder {slug} under {root}": "No hay registros del proyecto {slug} en {root}",
    "Objective state": "Estado objetivo",
    "Branch": "Rama",
    "Recent commits": "Commits recientes",
    "Uncommitted changes": "Cambios sin guardar (commit)",
    "Not a git repository.": "No es un repositorio git.",
    "Recently modified files": "Archivos modificados recientemente",
    "(none)": "(ninguno)",
    "Handover": "Traspaso",
    "Goal": "Objetivo",
    "State": "Estado",
    "Key decisions": "Decisiones clave",
    "Files that matter": "Archivos importantes",
    "Next step": "Siguiente paso",
    "Traps": "Trampas",
    "Verify with": "Verificar con",
    "<one or two sentences: what this work is for>": "<una o dos frases: para qué es este trabajo>",
    "- Done: <shipped and verified>\n- In flight: <started, and exactly how far it got>\n- Not started: <known remaining scope>":
        "- Hecho: <entregado y verificado>\n- En curso: <iniciado, y hasta dónde llegó exactamente>\n- Pendiente: <alcance restante conocido>",
    "- <decision> because <reason> (do not revisit)": "- <decisión> porque <motivo> (no volver a discutir)",
    "- `path/to/file:120-160` - <why this range matters>": "- `ruta/al/archivo:120-160` - <por qué importa este rango>",
    "<the single concrete next action: command, file, expected outcome>":
        "<la siguiente acción concreta: comando, archivo, resultado esperado>",
    "- <failure already hit and its fix, or dead end already explored>":
        "- <fallo ya encontrado y su solución, o callejón sin salida ya explorado>",
    "<one command that proves the work is fine>": "<un comando que demuestre que todo está bien>",
    "Wrote {path}. Fill in the <placeholders>; keep it under ~150 lines.":
        "Se escribió {path}. Completa los <marcadores>; mantenlo en menos de ~150 líneas.",
    "Appended a new section to {path}.": "Se agregó una sección nueva a {path}.",
    "Added HANDOVER.md to {path} so it is not committed by accident.":
        "Se agregó HANDOVER.md a {path} para que no se suba por accidente.",
    "Next session: \"Read HANDOVER.md and continue from Next step.\"":
        "Próxima sesión: «Lee HANDOVER.md y continúa desde Siguiente paso.»",
    "FRUGAL INIT-CONFIG": "FRUGAL INIT-CONFIG",
    "Settings file": "Archivo de configuración",
    "Rules to add": "Reglas por agregar",
    "Already present": "Ya presentes",
    "Nothing to add: this file already blocks everything recommended.":
        "Nada que agregar: este archivo ya bloquea todo lo recomendado.",
    "Dry run. Nothing was changed. Re-run with --apply to write the rules above.":
        "Simulación. No se cambió nada. Vuelve a ejecutar con --apply para escribir las reglas de arriba.",
    "Backup saved to {path}": "Copia de seguridad guardada en {path}",
    "Wrote {count} new rule(s) to {path}": "Se escribieron {count} regla(s) nueva(s) en {path}",
    "Cannot read {path}: {error}. Nothing was changed.":
        "No se puede leer {path}: {error}. No se cambió nada.",
    "{path} is not a JSON object. Nothing was changed.": "{path} no es un objeto JSON. No se cambió nada.",
    "Denied paths cannot be read by Claude even by accident.":
        "Claude no podrá leer estas rutas ni por accidente.",
    "[Frugal] This session's context is now ~{k}k tokens (threshold {limit}k). Every new message re-sends all of it and quality drops. "
    "Do what the user asked first. Then, at the very END of your reply, add this short notice (translate nothing, keep the code block exactly):\n"
    "---\n"
    "Frugal: this conversation is getting long (~{k}k). To save tokens, do it NOW, do not wait to finish the task. STEP 1: copy and paste this:\n"
    "```\n"
    "Write HANDOVER.md (max 40 lines): goal, decisions made, files changed, pending items and the exact next step. "
    "Include uncommitted changes and any tools or scripts that live outside the repository. "
             "When you finish, end your reply with: Now type /clear, then paste this in the new session: "
             "Read HANDOVER.md and continue from its next step. (put that sentence in a code block).\n"
    "```\n"
    "STEP 2: type /clear\n"
             "STEP 3: in the new session, copy and paste this:\n"
             "```\n"
             "Read HANDOVER.md and continue from its next step.\n"
             "```\n"
    "---\n"
    "Do not write the handover yourself unless the user asks.":
        "[Frugal] El contexto de esta sesión ya es de ~{k}k tokens (umbral {limit}k). Cada mensaje nuevo reenvía todo eso y la calidad baja. "
        "Primero haz lo que el usuario pidió. Luego, al FINAL de tu respuesta, añade este aviso corto (copia el bloque de código tal cual):\n"
        "---\n"
        "Frugal: esta conversación ya es larga (~{k}k). Para ahorrar tokens, hazlo AHORA, no esperes a terminar la tarea. PASO 1: copia y pega esto:\n"
        "```\n"
        "Escribe HANDOVER.md (máx. 40 líneas): objetivo, decisiones tomadas, archivos modificados, pendientes y el siguiente paso exacto. "
        "Incluye los cambios sin commit y las herramientas o scripts que estén fuera del repositorio. "
        "Al terminar, cierra tu respuesta con: Ahora escribe /clear y luego pega esto en la sesión nueva: "
        "Lee HANDOVER.md y continúa desde su siguiente paso. (pon esa frase en un bloque de código).\n"
        "```\n"
        "PASO 2: escribe /clear\n"
        "PASO 3: en la sesión nueva, copia y pega esto:\n"
        "```\n"
        "Lee HANDOVER.md y continúa desde su siguiente paso.\n"
        "```\n"
        "---\n"
        "No escribas el traspaso tú mismo salvo que el usuario lo pida.",
    "[Frugal] {name} exists (updated {age} ago). If the user is continuing earlier work, read it first and resume from its next step; otherwise ignore it.":
        "[Frugal] Existe {name} (actualizado hace {age}). Si el usuario continúa un trabajo anterior, léelo primero y retoma desde su siguiente paso; si no, ignóralo.",
    "Outside the repo": "Fuera del repositorio",
    "- <tools, scripts or files that live outside the repository (temp folders) and may be gone>":
        "- <herramientas, scripts o archivos fuera del repositorio (carpetas temporales) que podrían haberse perdido>",
    "avg ctx": "ctx prom.",
    "[Frugal] Reading rule: for files over ~300 lines, grep first and read only the needed line range. "
    "Do not re-read a file already read in this session. Pipe long command output through head or tail.":
        "[Frugal] Regla de lectura: en archivos de más de ~300 líneas, busca primero con grep y lee solo el rango necesario. "
        "No vuelvas a leer un archivo que ya leíste en esta sesión. Limita la salida de comandos largos con head o tail.",
    "FRUGAL STATUS": "ESTADO DE FRUGAL",
    "Latest session: {name}": "Última sesión: {name}",
    "Context now: ~{k}k tokens (warning threshold {limit}k)":
        "Contexto ahora: ~{k}k tokens (umbral de aviso {limit}k)",
    "Hooks installed in {path}: {names}": "Hooks instalados en {path}: {names}",
    "No Frugal hooks found. Run: init-config --global --hooks --apply":
        "No hay hooks de Frugal. Ejecuta: init-config --global --hooks --apply",
    "Last warning was at ~{k}k tokens": "El último aviso fue a ~{k}k tokens",
    "Verdict: the context is still under the threshold, so no warning is expected yet.":
        "Veredicto: el contexto aún no pasa el umbral, así que todavía no corresponde avisar.",
    "Verdict: it already warned at ~{k}k; the next warning comes at ~{next}k.":
        "Veredicto: ya avisó a ~{k}k; el siguiente aviso llega a ~{next}k.",
    "Verdict: the context is over the threshold and no warning is recorded yet. "
    "The warning is checked when you send your next message: send one and look at the end of the reply. "
    "If it does not appear, reopen Claude Code (hooks load only at startup) and try again.":
        "Veredicto: el contexto pasó el umbral y aún no hay un aviso registrado. "
        "El aviso se revisa cuando envías tu próximo mensaje: envía uno y mira el final de la respuesta. "
        "Si no aparece, reabre Claude Code (los hooks se cargan solo al iniciar) e inténtalo de nuevo.",
    "No sessions found for this project.": "No se encontraron sesiones de este proyecto.",
    "Hooks to add ({count}):": "Hooks por agregar ({count}):",
    "Hooks already present: {names}": "Hooks ya presentes: {names}",
    "Nothing to add: rules and hooks are already in place.":
        "Nada que agregar: las reglas y los hooks ya están puestos.",
    "Wrote {count} new hook(s) to {path}": "Se escribieron {count} hook(s) nuevo(s) en {path}",
    "Dry run. Nothing was changed. Re-run with --apply to write the changes above.":
        "Simulación. No se cambió nada. Vuelve a ejecutar con --apply para escribir los cambios de arriba.",
}


def t(text, **kw):
    """Translate an English source string when the language is Spanish."""
    if LANG == "es":
        text = ES.get(text, text)
    return text.format(**kw) if kw else text


def detect_lang(cli_value=None):
    value = cli_value or os.environ.get("FRUGAL_LANG")
    if not value:
        value = os.environ.get("LC_ALL") or os.environ.get("LANG")
    if not value:
        try:
            value = locale.getlocale()[0]
        except Exception:  # pragma: no cover - platform specific
            value = None
    return "es" if value and value.lower().startswith("es") else "en"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def est_tokens(text):
    return max(0, len(text) // CHARS_PER_TOKEN)


def human(n):
    for unit, div in (("B", 1_000_000_000), ("M", 1_000_000), ("k", 1_000)):
        if n >= div:
            return "{:.1f}{}".format(n / div, unit)
    return str(int(n))


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def project_slug(path):
    """Claude Code names a project's log folder by replacing every character
    that is not a letter or digit with a hyphen (C:\\Users\\Me\\app -> C--Users-Me-app)."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def parse_frontmatter(text):
    """Return a dict of simple `key: value` pairs plus list values for the
    leading --- block. Not a full YAML parser; enough for skills and rules."""
    data = {}
    if not text or not text.startswith("---"):
        return data
    parts = text.split("\n")
    if parts[0].strip() != "---":
        return data
    current_key = None
    for line in parts[1:]:
        if line.strip() == "---":
            break
        if re.match(r"^\s+-\s+", line) and current_key:
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(line.split("-", 1)[1].strip().strip("\"'"))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            current_key = m.group(1)
            val = m.group(2).strip()
            if val in (">-", ">", "|", "|-", ""):
                data[current_key] = "" if val else []
                if val in (">-", ">", "|", "|-"):
                    data[current_key] = ""
                    data["_block_" + current_key] = True
            else:
                data[current_key] = val.strip("\"'")
        elif current_key and data.get("_block_" + current_key) and line.startswith(" "):
            data[current_key] = (data[current_key] + " " + line.strip()).strip()
    return data


def run_git(args, cwd):
    try:
        out = subprocess.run(
            ["git"] + args, cwd=str(cwd), capture_output=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace").strip()


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


# --------------------------------------------------------------------------
# Stack detection and recommended deny rules
# --------------------------------------------------------------------------

UNIVERSAL_DENY = [
    "Read(./.git/**)",
    "Read(./**/*.min.js)",
    "Read(./**/*.min.css)",
    "Read(./**/*.map)",
]

# name -> (marker file globs at the project root or one level down, deny rules)
STACKS = {
    "node": (
        ["package.json"],
        ["Read(./node_modules/**)", "Read(./dist/**)", "Read(./build/**)",
         "Read(./.next/**)", "Read(./coverage/**)", "Read(./package-lock.json)",
         "Read(./yarn.lock)", "Read(./pnpm-lock.yaml)"],
    ),
    "python": (
        ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
        ["Read(./venv/**)", "Read(./.venv/**)", "Read(./**/__pycache__/**)",
         "Read(./**/*.pyc)", "Read(./.pytest_cache/**)", "Read(./.mypy_cache/**)",
         "Read(./.tox/**)", "Read(./**/*.egg-info/**)"],
    ),
    "java": (
        ["pom.xml", "build.gradle", "build.gradle.kts"],
        ["Read(./target/**)", "Read(./build/**)", "Read(./.gradle/**)"],
    ),
    "go": (["go.mod"], ["Read(./vendor/**)"]),
    "rust": (["Cargo.toml"], ["Read(./target/**)", "Read(./Cargo.lock)"]),
    "php": (["composer.json"], ["Read(./vendor/**)", "Read(./composer.lock)"]),
    "ruby": (["Gemfile"], ["Read(./vendor/**)", "Read(./.bundle/**)"]),
    "dotnet": (["*.csproj", "*.sln"], ["Read(./**/bin/**)", "Read(./**/obj/**)"]),
    "flutter": (["pubspec.yaml"], ["Read(./.dart_tool/**)", "Read(./build/**)"]),
    "odoo": (
        ["__manifest__.py"],
        ["Read(./**/i18n/*.pot)", "Read(./**/static/lib/**)", "Read(./**/filestore/**)"],
    ),
}


def detect_stacks(root):
    root = Path(root)
    found = []
    try:
        children = [p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    except OSError:
        children = []
    for name, (markers, _deny) in STACKS.items():
        hit = False
        for marker in markers:
            if list(root.glob(marker)):
                hit = True
                break
        if not hit and name == "odoo":
            hit = any((c / "__manifest__.py").exists() for c in children)
        if hit:
            found.append(name)
    return found


def recommended_deny(stacks):
    rules = list(UNIVERSAL_DENY)
    for name in stacks:
        for rule in STACKS[name][1]:
            if rule not in rules:
                rules.append(rule)
    return rules


def load_json_file(path):
    """Return (data, error). A missing file is ({}, None)."""
    p = Path(path)
    if not p.exists():
        return {}, None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "not a JSON object"
    return data, None


def existing_deny_rules(root):
    rules = set()
    candidates = [
        Path(root) / ".claude" / "settings.json",
        Path(root) / ".claude" / "settings.local.json",
        claude_home() / "settings.json",
    ]
    for c in candidates:
        data, _err = load_json_file(c)
        if data:
            deny = (data.get("permissions") or {}).get("deny") or []
            if isinstance(deny, list):
                rules.update(str(r) for r in deny)
    return rules


def rule_covered(rule, existing):
    """A recommended rule counts as covered if the same rule is present, or if a
    broader read-deny exists for the same folder."""
    if rule in existing:
        return True
    norm = rule.replace("./", "")
    for e in existing:
        if e.replace("./", "") == norm:
            return True
    return False


# --------------------------------------------------------------------------
# doctor
# --------------------------------------------------------------------------


def path_like_tokens(text):
    """Backticked tokens that look like relative file paths."""
    out = []
    for m in re.finditer(r"`([^`\n]{3,80})`", text):
        tok = m.group(1).strip()
        if any(c in tok for c in (" ", "<", ">", "*", "$", "{", "|", "=", "(", ")")):
            continue
        if tok.startswith(("http", "~", "/", "-", "@", "$", "%")) or re.match(r"^[A-Za-z]:\\", tok):
            continue
        if "/" in tok or re.search(r"\.[A-Za-z0-9]{1,5}$", tok):
            if re.search(r"\.[A-Za-z0-9]{1,5}$", tok) or tok.endswith("/"):
                out.append(tok)
    seen, uniq = set(), []
    for tok in out:
        if tok not in seen:
            seen.add(tok)
            uniq.append(tok)
    return uniq


KNOWN_FILE_EXTS = {
    "py", "js", "ts", "tsx", "jsx", "json", "md", "txt", "yml", "yaml", "toml", "xml",
    "html", "css", "csv", "sh", "ps1", "sql", "cfg", "ini", "conf", "java", "go", "rs",
    "rb", "php", "c", "h", "cpp", "cs", "dart", "lock", "env",
}


IGNORE_MARK = "frugal-ignore"


VENDOR_DIRS = {"node_modules", ".git", "dist", "venv", ".venv", "__pycache__", "build", "target"}


def name_exists_in_project(name, root):
    """True when a file or folder with this name exists anywhere in the project
    (vendor and build folders are not searched)."""
    for _dirpath, dirnames, filenames in os.walk(root):
        if name in filenames or name in dirnames:
            return True
        dirnames[:] = [d for d in dirnames if d not in VENDOR_DIRS]
    return False


def paths_in_other_branches(root, limit=10):
    """Files and folders that exist on other local git branches (for example a
    branch kept for an older release). A CLAUDE.md shared by several branches
    may cite them on purpose, so they are not stale."""
    known = set()
    current = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    refs = run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], root)
    for ref in (refs or "").splitlines()[:limit]:
        if not ref or ref == current:
            continue
        for name in (run_git(["ls-tree", "-r", "--name-only", ref], root) or "").splitlines():
            parts = name.split("/")
            known.add(name)
            known.add(parts[-1])
            for i in range(1, len(parts)):
                known.add("/".join(parts[:i]))
    return known


def stale_paths(text, root):
    """Backticked paths that do not exist. Lines containing `frugal-ignore`
    (for example in an HTML comment) are skipped, for paths cited on purpose.
    A bare file name counts as present when it exists anywhere in the project,
    and any path counts as present when it exists on another local branch."""
    text = "\n".join(l for l in text.splitlines() if IGNORE_MARK not in l)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    root = Path(root)
    other = None
    missing = []
    for tok in path_like_tokens(text):
        ext = tok.rsplit(".", 1)[-1].lower() if "." in tok else ""
        if not tok.endswith("/") and ext not in KNOWN_FILE_EXTS:
            continue
        rel = tok.rstrip("/")
        if (root / rel).exists():
            continue
        if "/" not in rel and name_exists_in_project(rel, root):
            continue
        if other is None:
            other = paths_in_other_branches(root)
        if rel in other:
            continue
        missing.append(tok)
    return missing


def cmd_doctor(args):
    root = Path(args.project).resolve()
    items = []   # (label, est tokens)
    findings = []
    home = claude_home()

    # CLAUDE.md files
    claude_files = [
        ("~/.claude/CLAUDE.md", home / "CLAUDE.md"),
        ("CLAUDE.md", root / "CLAUDE.md"),
        (".claude/CLAUDE.md", root / ".claude" / "CLAUDE.md"),
        ("CLAUDE.local.md", root / "CLAUDE.local.md"),
    ]
    project_claude_found = False
    for label, path in claude_files:
        text = read_text(path)
        if text is None:
            continue
        if label in ("CLAUDE.md", ".claude/CLAUDE.md"):
            project_claude_found = True
        text_wo_comments = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        tokens = est_tokens(text_wo_comments)
        lines = text.count("\n") + 1
        items.append((label, tokens))
        if tokens > 1500 or lines > 200:
            findings.append(("warn", t(
                "{label} is about {tokens} tokens ({lines} lines). It is paid on every message. "
                "Keep only what Claude cannot infer from the code (aim for under ~1,000 tokens).",
                label=label, tokens=human(tokens), lines=lines)))
        if label in ("CLAUDE.md", ".claude/CLAUDE.md"):
            miss = stale_paths(text, root)
            if miss:
                findings.append(("warn", t(
                    "{path} mentions paths that do not exist (stale instructions are followed with "
                    "confidence): {names}. If a path is cited on purpose (it lives outside the "
                    "project), add `frugal-ignore` to that line.", path=label, names=", ".join(miss[:8]))))
    if not project_claude_found:
        findings.append(("info", t(
            "No CLAUDE.md found in this project. Not an error; add one only for things "
            "Claude cannot infer.")))

    # Rules
    always_rules = []
    for base in (root / ".claude" / "rules", home / "rules"):
        if not base.is_dir():
            continue
        for rule in sorted(base.rglob("*.md")):
            text = read_text(rule) or ""
            fm = parse_frontmatter(text)
            if not fm.get("paths"):
                always_rules.append((rule.name, est_tokens(text)))
    if always_rules:
        total = sum(tok for _n, tok in always_rules)
        items.append((".claude/rules (no paths filter)", total))
        findings.append(("warn", t(
            "{count} rule file(s) have no `paths:` filter, so they load on every session "
            "(~{tokens} tokens). Add `paths:` frontmatter so they load only when needed: {names}",
            count=len(always_rules), tokens=human(total),
            names=", ".join(n for n, _t in always_rules[:6]))))

    # Skills (name + description load at startup)
    skill_tokens, skill_count = 0, 0
    for base in (root / ".claude" / "skills", home / "skills"):
        if not base.is_dir():
            continue
        for skill_md in sorted(base.glob("*/SKILL.md")):
            fm = parse_frontmatter(read_text(skill_md) or "")
            blob = "{} {}".format(fm.get("name", ""), fm.get("description", ""))
            tokens = est_tokens(blob)
            skill_tokens += tokens
            skill_count += 1
            if tokens > 150:
                findings.append(("info", t(
                    "Skill '{name}' has a very long description (~{tokens} tokens). Shorter "
                    "descriptions cost less at startup.",
                    name=fm.get("name") or skill_md.parent.name, tokens=human(tokens))))
    if skill_count:
        items.append(("skills (names + descriptions)", skill_tokens))
        if skill_count > 25:
            findings.append(("info", t(
                "{count} skills are installed; their names and descriptions (~{tokens} tokens) "
                "load at startup. Remove the ones you do not use.",
                count=skill_count, tokens=human(skill_tokens))))

    # MCP servers (counted, not priced: cost varies a lot by server)
    mcp_names = set()
    for path in (root / ".mcp.json", home / "settings.json", root / ".claude" / "settings.json"):
        data, _e = load_json_file(path)
        if data and isinstance(data.get("mcpServers"), dict):
            mcp_names.update(data["mcpServers"].keys())
    user_cfg, _e = load_json_file(Path.home() / ".claude.json")
    if user_cfg:
        if isinstance(user_cfg.get("mcpServers"), dict):
            mcp_names.update(user_cfg["mcpServers"].keys())
        proj = (user_cfg.get("projects") or {}).get(str(root)) or {}
        if isinstance(proj.get("mcpServers"), dict):
            mcp_names.update(proj["mcpServers"].keys())
    if len(mcp_names) >= 3:
        findings.append(("warn", t(
            "{count} MCP server(s) configured. Each one adds its tool list to every session "
            "(often thousands of tokens). Disconnect the ones you are not using: {names}",
            count=len(mcp_names), names=", ".join(sorted(mcp_names)[:8]))))

    # Deny rules
    stacks = detect_stacks(root)
    recommended = recommended_deny(stacks)
    existing = existing_deny_rules(root)
    missing = [r for r in recommended if not rule_covered(r, existing)]
    # Only flag when something project-specific is missing (not just universal).
    project_missing = [r for r in missing if r not in UNIVERSAL_DENY]
    if project_missing:
        findings.append(("warn", t(
            "No read-deny rules for build/vendor folders detected for this project ({stacks}). "
            "Run `init-config` to see a safe proposal. Missing: {missing}",
            stacks=", ".join(stacks) or t("none"),
            missing=", ".join(project_missing[:6]) + (" ..." if len(project_missing) > 6 else ""))))

    # HANDOVER.md hygiene
    handover = root / "HANDOVER.md"
    if handover.exists() and run_git(["rev-parse", "--is-inside-work-tree"], root) == "true":
        ignored = run_git(["check-ignore", "HANDOVER.md"], root)
        if not ignored:
            findings.append(("warn", t(
                "HANDOVER.md exists but is not in .gitignore. It may contain project details; "
                "run `handover --write` once or add it to .gitignore.")))

    total = sum(tok for _l, tok in items)
    if args.json:
        print(json.dumps({
            "project": str(root), "stacks": stacks,
            "always_on": [{"item": l, "tokens": tok} for l, tok in items],
            "always_on_total": total,
            "findings": [{"level": lv, "message": msg} for lv, msg in findings],
        }, indent=2, ensure_ascii=False))
        return 1 if (args.strict and any(lv == "warn" for lv, _ in findings)) else 0

    print()
    print("=" * 78)
    print(t("FRUGAL DOCTOR"))
    print("=" * 78)
    print("{}: {}".format(t("Project"), root))
    print("{}: {}".format(t("Detected stack(s)"), ", ".join(stacks) or t("none")))
    print("\n{}".format(t("Loaded on every session (estimated tokens)")))
    for label, tokens in items:
        print("  {:<38}{:>8}".format(label, human(tokens)))
    print("  {:<38}{:>8}".format(t("Always-on total"), human(total)))
    print("\n{}".format(t("Findings")))
    warns = [f for f in findings if f[0] == "warn"]
    infos = [f for f in findings if f[0] == "info"]
    if not findings:
        print("  [ok] {}".format(t("Nothing to fix. Your always-on context looks lean.")))
    for lv, msg in warns + infos:
        print("  [{}] {}".format("!" if lv == "warn" else "i", msg))
    print()
    return 1 if (args.strict and warns) else 0


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


def block_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict):
                val = b.get("text") or b.get("content") or ""
                out.append(val if isinstance(val, str) else json.dumps(val))
            elif isinstance(b, str):
                out.append(b)
        return "".join(out)
    if content is None:
        return ""
    return json.dumps(content)


def scan_session(path):
    usage = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0}
    seen = set()
    tool_names = {}
    tool_calls = defaultdict(int)
    tool_bytes = defaultdict(int)
    results = []
    peak = 0
    turns = 0
    ctx_sum = 0
    ctx_n = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            rtype = rec.get("type")
            msg = rec.get("message") or {}
            if not isinstance(msg, dict):
                continue
            if rtype == "assistant":
                mid = msg.get("id")
                u = msg.get("usage") or {}
                if u and (mid is None or mid not in seen):
                    if mid:
                        seen.add(mid)
                    inp = u.get("input_tokens", 0) or 0
                    cw = u.get("cache_creation_input_tokens", 0) or 0
                    cr = u.get("cache_read_input_tokens", 0) or 0
                    usage["input"] += inp
                    usage["cache_write"] += cw
                    usage["cache_read"] += cr
                    usage["output"] += u.get("output_tokens", 0) or 0
                    peak = max(peak, inp + cw + cr)
                    ctx_sum += inp + cw + cr
                    ctx_n += 1
                content = msg.get("content")
                for b in content if isinstance(content, list) else []:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tool = b.get("name", "?")
                        inp_ = b.get("input") or {}
                        detail = (inp_.get("command") or inp_.get("file_path")
                                  or inp_.get("pattern") or inp_.get("path")
                                  or inp_.get("skill") or "")
                        detail = " ".join(str(detail).split())[:90]
                        tool_names[b.get("id")] = (tool, detail)
                        tool_calls[tool] += 1
            elif rtype == "user":
                content = msg.get("content")
                if isinstance(content, list):
                    for b in content:
                        if isinstance(b, dict) and b.get("type") == "tool_result":
                            tool, detail = tool_names.get(b.get("tool_use_id"), ("?", ""))
                            size = len(block_text(b.get("content")))
                            tool_bytes[tool] += size
                            results.append((size, tool, detail))
                        elif isinstance(b, dict) and b.get("type") == "text":
                            turns += 1
                elif isinstance(content, str):
                    turns += 1
    return {
        "path": path, "session": path.stem, "project": path.parent.name,
        "mtime": path.stat().st_mtime, "usage": usage, "peak": peak,
        "tool_calls": tool_calls, "tool_bytes": tool_bytes,
        "results": results, "turns": turns,
        "calls": ctx_n, "avg_ctx": (ctx_sum // ctx_n) if ctx_n else 0,
    }


def find_session_files(root, project, days, limit):
    if project:
        slug = project_slug(Path(project).resolve())
        dirs = [d for d in root.iterdir() if d.is_dir()]
        match = [d for d in dirs if d.name == slug] or [d for d in dirs if d.name.lower() == slug.lower()]
        if not match:
            return None, slug
        files = [f for d in match for f in d.glob("*.jsonl")]
    else:
        files = list(root.glob("*/*.jsonl"))
    if days:
        cutoff = time.time() - days * 86400
        files = [f for f in files if f.stat().st_mtime >= cutoff]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files[:limit], None


def cmd_audit(args):
    root = Path(args.root) if args.root else claude_home() / "projects"
    if not root.is_dir():
        print(t("No session logs found at {root}", root=root), file=sys.stderr)
        return 1
    files, slug = find_session_files(root, args.project, args.days, args.sessions)
    if files is None:
        print(t("No logs for project folder {slug} under {root}", slug=slug, root=root), file=sys.stderr)
        return 1
    if not files:
        print(t("No sessions matched."), file=sys.stderr)
        return 1
    stats = [scan_session(f) for f in files]

    tot_calls, tot_bytes = defaultdict(int), defaultdict(int)
    all_results = []
    grand = defaultdict(int)
    for s in stats:
        for k, v in s["tool_calls"].items():
            tot_calls[k] += v
        for k, v in s["tool_bytes"].items():
            tot_bytes[k] += v
        all_results.extend(s["results"])
        for k, v in s["usage"].items():
            grand[k] += v
    new_spend = grand["input"] + grand["cache_write"] + grand["output"]
    ranked = sorted(tot_bytes.items(), key=lambda kv: kv[1], reverse=True)[: args.top]
    all_results.sort(reverse=True)
    peak = max(s["peak"] for s in stats)

    if args.json:
        print(json.dumps({
            "sessions": len(stats),
            "totals": dict(grand), "new_token_spend": new_spend, "peak_context": peak,
            "avg_context_per_message": (sum(x["avg_ctx"] * x["calls"] for x in stats) // max(1, sum(x["calls"] for x in stats))),
            "messages": sum(x["calls"] for x in stats),
            "tool_result_tokens": {k: v // CHARS_PER_TOKEN for k, v in ranked},
            "heaviest_results": [
                {"tokens": size // CHARS_PER_TOKEN, "tool": tool, "detail": d}
                for size, tool, d in all_results[: args.top]],
        }, indent=2, ensure_ascii=False))
        return 0

    print()
    print("=" * 78)
    print("{}  ({} {} {})".format(t("TOKEN AUDIT"), len(stats), t("session(s) under"), root))
    print("=" * 78)
    print("\n{}".format(t("SESSIONS (newest first)")))
    print("{:<17}{:<30}{:>8}{:>10}{:>10}{:>10}{:>10}".format(
        t("when"), t("project"), t("output"), "cache wr", "cache rd", t("peak ctx"), t("avg ctx")))
    for s in sorted(stats, key=lambda x: x["mtime"], reverse=True):
        u = s["usage"]
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["mtime"]))
        print("{:<17}{:<30}{:>8}{:>10}{:>10}{:>10}{:>10}".format(
            when, s["project"][-29:], human(u["output"]), human(u["cache_write"]),
            human(u["cache_read"]), human(s["peak"]), human(s["avg_ctx"])))
    print("\n{}: output {} | {} {} | {} {} | {} ~{}".format(
        t("Totals"), human(grand["output"]), t("cache writes"), human(grand["cache_write"]),
        t("cache reads"), human(grand["cache_read"]), t("new-token spend"), human(new_spend)))
    print(t("(cache reads are the cheap path; peak ctx is the largest context a single message carried)"))

    print("\n{}".format(t("TOOL RESULT VOLUME (what entered the context, est. tokens)")))
    print("{:<22}{:>8}{:>15}{:>10}".format(t("tool"), t("calls"), "chars", "~tokens"))
    for tool, nbytes in ranked:
        print("{:<22}{:>8}{:>15}{:>10}".format(
            tool, tot_calls.get(tool, 0), human(nbytes), human(nbytes // CHARS_PER_TOKEN)))
    print("\n{}".format(t("HEAVIEST INDIVIDUAL RESULTS")))
    for size, tool, detail in all_results[: args.top]:
        print("  ~{:>6} tok  {:<12} {}".format(human(size // CHARS_PER_TOKEN), tool, detail))

    print("\n{}".format(t("WHAT TO FIX")))
    tips = []
    heaviest = ranked[0][0] if ranked else None
    if heaviest == "Bash":
        tips.append(t("Bash dominates: pipe commands through `tail -n 25` / `head -n 50` and stop streaming full logs."))
    if heaviest == "Read":
        tips.append(t("Read dominates: grep for the symbol first, then read only the matching line range."))
    if any(tool in ("Read", "Grep", "Glob")
           and re.search(r"node_modules|[\\/]\.git[\\/]|[\\/]dist[\\/]|__pycache__|[\\/]venv[\\/]", d)
           for _s, tool, d in all_results[:40]):
        tips.append(t("Vendor or build folders were read: run `init-config` to block them."))
    big = [r for r in all_results if r[0] > 40_000]
    if big:
        tips.append(t("{count} single result(s) over ~10k tokens: bound those commands or read narrower slices.",
                      count=len(big)))
    if peak > 150_000:
        tips.append(t("A session reached ~{tokens} tokens of context in one message. Past roughly 150k, "
                      "quality and cost both suffer: write a handover and /clear between tasks.",
                      tokens=human(peak)))
    if not tips:
        tips.append(t("Nothing pathological in this window. Keep clearing between tasks and writing handovers."))
    for tip in tips:
        print("  - {}".format(tip))
    print()
    return 0


# --------------------------------------------------------------------------
# handover
# --------------------------------------------------------------------------


def objective_state(root):
    lines = ["## {} ({})".format(t("Objective state"), datetime.now().strftime("%Y-%m-%d %H:%M")), ""]
    lines.append("{}: `{}`".format(t("Project"), root))
    inside = run_git(["rev-parse", "--is-inside-work-tree"], root) == "true"
    if inside:
        branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"], root) or "?"
        short = run_git(["rev-parse", "--short", "HEAD"], root) or "no commits"
        lines.append("{}: `{}` @ `{}`".format(t("Branch"), branch, short))
        lines += ["", "### {}".format(t("Recent commits")), "```",
                  run_git(["log", "--oneline", "-8"], root) or t("(none)"), "```"]
        status = run_git(["status", "--short"], root) or ""
        status_lines = status.splitlines()
        shown = status_lines[:30]
        if len(status_lines) > 30:
            shown.append("... +{}".format(len(status_lines) - 30))
        lines += ["", "### {}".format(t("Uncommitted changes")), "```",
                  "\n".join(shown) or t("(none)"), "```"]
    else:
        lines += ["", t("Not a git repository."), "", "### {}".format(t("Recently modified files")), "```"]
        skip = {"node_modules", ".git", "dist", "venv", ".venv", "__pycache__", "build", "target"}
        cutoff = time.time() - 2 * 86400
        recent = []
        for dirpath, dirnames, filenames in os.walk(str(root)):
            dirnames[:] = [d for d in dirnames if d not in skip]
            for name in filenames:
                fp = Path(dirpath) / name
                try:
                    if fp.stat().st_mtime >= cutoff:
                        recent.append(str(fp.relative_to(root)))
                except OSError:
                    pass
            if len(recent) >= 20:
                break
        lines += ["\n".join(recent[:20]) or t("(none)"), "```"]
    return "\n".join(lines)


def handover_template(root, state):
    title = "# {} - {} - {}".format(t("Handover"), root.name, datetime.now().strftime("%Y-%m-%d"))
    parts = [
        title, "",
        "## {}".format(t("Goal")), t("<one or two sentences: what this work is for>"), "",
        "## {}".format(t("State")),
        t("- Done: <shipped and verified>\n- In flight: <started, and exactly how far it got>\n"
          "- Not started: <known remaining scope>"), "",
        "## {}".format(t("Key decisions")), t("- <decision> because <reason> (do not revisit)"), "",
        "## {}".format(t("Files that matter")), t("- `path/to/file:120-160` - <why this range matters>"), "",
        "## {}".format(t("Next step")),
        t("<the single concrete next action: command, file, expected outcome>"), "",
        "## {}".format(t("Outside the repo")),
        t("- <tools, scripts or files that live outside the repository (temp folders) and may be gone>"), "",
        "## {}".format(t("Traps")),
        t("- <failure already hit and its fix, or dead end already explored>"), "",
        "## {}".format(t("Verify with")), t("<one command that proves the work is fine>"), "",
        state, "",
    ]
    return "\n".join(parts)


def ensure_gitignored(root, filename):
    """Add filename to .gitignore when the project is a git repo and it is not
    already ignored. Returns the .gitignore path if it was changed."""
    if run_git(["rev-parse", "--is-inside-work-tree"], root) != "true":
        return None
    if run_git(["check-ignore", filename], root):
        return None
    gi = root / ".gitignore"
    current = read_text(gi) or ""
    if current and not current.endswith("\n"):
        current += "\n"
    gi.write_text(current + filename + "\n", encoding="utf-8")
    return gi


def cmd_handover(args):
    root = Path(args.project).resolve()
    state = objective_state(root)
    if not args.write:
        print(state)
        return 0
    target = root / args.file
    body = handover_template(root, state)
    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="replace")
        target.write_text(existing.rstrip("\n") + "\n\n---\n\n" + body, encoding="utf-8")
        print(t("Appended a new section to {path}.", path=target))
    else:
        target.write_text(body, encoding="utf-8")
        print(t("Wrote {path}. Fill in the <placeholders>; keep it under ~150 lines.", path=target))
    if not args.no_gitignore:
        changed = ensure_gitignored(root, args.file)
        if changed:
            print(t("Added HANDOVER.md to {path} so it is not committed by accident.", path=changed))
    print(t('Next session: "Read HANDOVER.md and continue from Next step."'))
    return 0



# --------------------------------------------------------------------------
# hooks (run by Claude Code itself; never raise, never block)
# --------------------------------------------------------------------------

HOOK_THRESHOLD = 150_000   # warn once the context passes this many tokens
HOOK_STEP = 50_000         # then warn again only after it grows this much more
STATE_DIR = ".frugal"
STATE_FILE = "STATE.md"


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def read_hook_input():
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def current_context(transcript_path):
    """Tokens carried by the most recent assistant message (0 when unknown)."""
    try:
        p = Path(transcript_path)
        size = p.stat().st_size
    except (OSError, TypeError, ValueError):
        return 0
    for tail in (400_000, 8_000_000):
        try:
            with p.open("rb") as fh:
                if size > tail:
                    fh.seek(size - tail)
                chunk = fh.read().decode("utf-8", errors="replace")
        except OSError:
            return 0
        for line in reversed(chunk.splitlines()):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("type") != "assistant":
                continue
            u = (rec.get("message") or {}).get("usage") or {}
            total = sum((u.get(k) or 0) for k in
                        ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            if total:
                return total
        if size <= tail:
            break
    return 0


def _marker_path(session_id):
    import tempfile
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or "x"))[:64] or "x"
    return Path(tempfile.gettempdir()) / ("frugal-warned-" + safe + ".txt")


def hook_prompt(data, threshold=HOOK_THRESHOLD):
    """UserPromptSubmit: stdout is added to Claude's context, so print only
    when the context is large and we have not warned at this size yet."""
    ctx = current_context(data.get("transcript_path"))
    if ctx < threshold:
        return ""
    marker = _marker_path(data.get("session_id"))
    try:
        last = int(marker.read_text().strip() or 0)
    except (OSError, ValueError):
        last = 0
    if last and ctx < last + HOOK_STEP:
        return ""
    try:
        marker.write_text(str(ctx))
    except OSError:
        pass
    return t("[Frugal] This session's context is now ~{k}k tokens (threshold {limit}k). "
             "Every new message re-sends all of it and quality drops. "
             "Do what the user asked first. Then, at the very END of your reply, add this short notice "
             "(translate nothing, keep the code block exactly):\n"
             "---\n"
             "Frugal: this conversation is getting long (~{k}k). To save tokens, do it NOW, do not wait to finish the task. STEP 1: copy and paste this:\n"
             "```\n"
             "Write HANDOVER.md (max 40 lines): goal, decisions made, files changed, pending items and the exact next step. "
             "Include uncommitted changes and any tools or scripts that live outside the repository. "
             "When you finish, end your reply with: Now type /clear, then paste this in the new session: "
             "Read HANDOVER.md and continue from its next step. (put that sentence in a code block).\n"
             "```\n"
             "STEP 2: type /clear\n"
             "STEP 3: in the new session, copy and paste this:\n"
             "```\n"
             "Read HANDOVER.md and continue from its next step.\n"
             "```\n"
             "---\n"
             "Do not write the handover yourself unless the user asks.",
             k=ctx // 1000, limit=threshold // 1000)


def age_text(seconds):
    if seconds < 3600:
        return "{} min".format(max(1, int(seconds // 60)))
    if seconds < 86400:
        return "{} h".format(int(seconds // 3600))
    return "{} d".format(int(seconds // 86400))


def hook_start(data, max_age_days=14):
    """SessionStart: a one-line reading rule on every fresh session, plus a
    line when a recent handover exists, so the user does not have to type
    'read HANDOVER.md'. Skipped on resume/compact (the context already has it)."""
    if data.get("source") in ("resume", "compact"):
        return ""
    lines = [t("[Frugal] Reading rule: for files over ~300 lines, grep first and read only the needed line range. "
               "Do not re-read a file already read in this session. Pipe long command output through head or tail.")]
    root = Path(data.get("cwd") or os.getcwd())
    for rel in ("HANDOVER.md", Path(STATE_DIR) / STATE_FILE):
        f = root / rel
        try:
            age = time.time() - f.stat().st_mtime
        except OSError:
            continue
        if age <= max_age_days * 86400:
            lines.append(t("[Frugal] {name} exists (updated {age} ago). If the user is continuing earlier work, "
                           "read it first and resume from its next step; otherwise ignore it.",
                           name=str(rel).replace("\\", "/"), age=age_text(age)))
            break
    return "\n".join(lines)


def hook_precompact(data):
    """PreCompact: stdout does not reach Claude, so save the objective state
    to disk. Decisions still need Claude (see the context warning)."""
    root = Path(data.get("cwd") or os.getcwd())
    folder = root / STATE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    (folder / STATE_FILE).write_text(objective_state(root) + "\n", encoding="utf-8")
    ensure_gitignored(root, STATE_DIR + "/")
    return ""


def cmd_status(args):
    root = Path(args.project).resolve()
    logs = claude_home() / "projects"
    files, _slug = find_session_files(logs, str(root), None, 1) if logs.is_dir() else (None, None)
    print()
    print(t("FRUGAL STATUS"))
    if not files:
        print(t("No sessions found for this project."))
        return 1
    latest = files[0]
    ctx = current_context(str(latest))
    limit = args.threshold
    print(t("Latest session: {name}", name=latest.stem))
    print(t("Context now: ~{k}k tokens (warning threshold {limit}k)", k=ctx // 1000, limit=limit // 1000))
    found = False
    for settings in (claude_home() / "settings.json", root / ".claude" / "settings.json",
                     root / ".claude" / "settings.local.json"):
        data, _err = load_json_file(settings)
        hooks = (data or {}).get("hooks")
        if isinstance(hooks, dict):
            _missing, present = plan_hooks(hooks)
            if present:
                found = True
                print(t("Hooks installed in {path}: {names}", path=settings,
                        names=", ".join(n for n, _e in present)))
    if not found:
        print(t("No Frugal hooks found. Run: init-config --global --hooks --apply"))
    marker = _marker_path(latest.stem)
    try:
        last = int(marker.read_text().strip() or 0)
    except (OSError, ValueError):
        last = 0
    if last:
        print(t("Last warning was at ~{k}k tokens", k=last // 1000))
    if ctx < limit:
        print(t("Verdict: the context is still under the threshold, so no warning is expected yet."))
    elif last and ctx < last + HOOK_STEP:
        print(t("Verdict: it already warned at ~{k}k; the next warning comes at ~{next}k.",
                k=last // 1000, next=(last + HOOK_STEP) // 1000))
    else:
        print(t("Verdict: the context is over the threshold and no warning is recorded yet. "
                "The warning is checked when you send your next message: send one and look at the end of the reply. "
                "If it does not appear, reopen Claude Code (hooks load only at startup) and try again."))
    return 0


def cmd_hook(args):
    try:
        data = read_hook_input()
        if args.event == "prompt":
            out = hook_prompt(data, args.threshold)
        elif args.event == "start":
            out = hook_start(data)
        else:
            out = hook_precompact(data)
        if out:
            print(out)
    except Exception:
        pass  # a hook must never break the user's session
    return 0


# --------------------------------------------------------------------------
# init-config
# --------------------------------------------------------------------------


HOOK_EVENTS = (("UserPromptSubmit", "prompt"), ("PreCompact", "precompact"), ("SessionStart", "start"))


def hook_command(event):
    python = "python" if os.name == "nt" else "python3"
    script = Path(__file__).resolve()
    return '{} "{}" --lang {} hook {}'.format(python, script, LANG, event)


def plan_hooks(hooks):
    """Return (to_add, present): which Frugal hook events are missing."""
    to_add, present = [], []
    for name, event in HOOK_EVENTS:
        groups = hooks.get(name) or []
        found = any("frugal" in (h.get("command") or "") and " hook " in (h.get("command") or "")
                    for g in groups if isinstance(g, dict)
                    for h in (g.get("hooks") or []) if isinstance(h, dict))
        (present if found else to_add).append((name, event))
    return to_add, present


def cmd_init_config(args):
    root = Path(args.project).resolve()
    if args.global_:
        target = claude_home() / "settings.json"
        stacks = []
    else:
        target = root / ".claude" / "settings.json"
        stacks = args.stack.split(",") if args.stack else detect_stacks(root)
        stacks = [s.strip() for s in stacks if s.strip() in STACKS]
    data, err = load_json_file(target)
    if data is None:
        print(t("Cannot read {path}: {error}. Nothing was changed.", path=target, error=err), file=sys.stderr)
        return 1
    permissions = data.get("permissions")
    if permissions is not None and not isinstance(permissions, dict):
        print(t("{path} is not a JSON object. Nothing was changed.", path=target), file=sys.stderr)
        return 1
    hooks = data.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        print(t("{path} is not a JSON object. Nothing was changed.", path=target), file=sys.stderr)
        return 1
    current = list((permissions or {}).get("deny") or [])
    wanted = recommended_deny(stacks)
    to_add = [r for r in wanted if not rule_covered(r, set(current))]
    present = [r for r in wanted if r not in to_add]
    hooks_add, hooks_present = plan_hooks(hooks or {}) if args.hooks else ([], [])

    print()
    print(t("FRUGAL INIT-CONFIG"))
    print("{}: {}".format(t("Settings file"), target))
    print("{}: {}".format(t("Detected stack(s)"), ", ".join(stacks) or t("none")))
    print("\n{} ({}):".format(t("Rules to add"), len(to_add)))
    for r in to_add:
        print("  + {}".format(r))
    if present:
        print("\n{} ({}):".format(t("Already present"), len(present)))
        for r in present:
            print("  = {}".format(r))
    print("\n{}".format(t("Denied paths cannot be read by Claude even by accident.")))
    if args.hooks:
        print("\n" + t("Hooks to add ({count}):", count=len(hooks_add)))
        for name, event in hooks_add:
            print("  + {}: {}".format(name, hook_command(event)))
        if hooks_present:
            print(t("Hooks already present: {names}", names=", ".join(n for n, _e in hooks_present)))
    if not to_add and not hooks_add:
        print(t("Nothing to add: rules and hooks are already in place.") if args.hooks
              else t("Nothing to add: this file already blocks everything recommended."))
        return 0
    if not args.apply:
        print(t("Dry run. Nothing was changed. Re-run with --apply to write the changes above."))
        return 0
    if target.exists():
        backup = target.with_name(target.name + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S"))
        backup.write_bytes(target.read_bytes())
        print(t("Backup saved to {path}", path=backup))
    if to_add:
        permissions = dict(permissions or {})
        permissions["deny"] = current + to_add
        data["permissions"] = permissions
    if hooks_add:
        hooks = dict(hooks or {})
        for name, event in hooks_add:
            groups = list(hooks.get(name) or [])
            groups.append({"hooks": [{"type": "command", "command": hook_command(event), "timeout": 10}]})
            hooks[name] = groups
        data["hooks"] = hooks
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if to_add:
        print(t("Wrote {count} new rule(s) to {path}", count=len(to_add), path=target))
    if hooks_add:
        print(t("Wrote {count} new hook(s) to {path}", count=len(hooks_add), path=target))
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser():
    ap = argparse.ArgumentParser(
        prog="frugal", description="Spend fewer tokens in Claude Code without losing quality.")
    ap.add_argument("--version", action="version", version="frugal " + __version__)
    ap.add_argument("--lang", choices=["en", "es"], help="output language (default: auto)")
    # Also accept --lang after the subcommand (`frugal.py doctor --lang es`).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--lang", choices=["en", "es"], default=argparse.SUPPRESS,
                        help="output language (default: auto)")
    sub = ap.add_subparsers(dest="command", required=True)

    d = sub.add_parser("doctor", parents=[common], help="check what loads on every session")
    d.add_argument("--project", default=".")
    d.add_argument("--json", action="store_true")
    d.add_argument("--strict", action="store_true", help="exit 1 when there are warnings")
    d.set_defaults(func=cmd_doctor)

    a = sub.add_parser("audit", parents=[common], help="rank what burned context in past sessions")
    a.add_argument("--project", help="limit to this project directory (default: all)")
    a.add_argument("--sessions", type=int, default=10)
    a.add_argument("--top", type=int, default=10)
    a.add_argument("--days", type=float)
    a.add_argument("--root", help="session logs folder (default: ~/.claude/projects)")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_audit)

    h = sub.add_parser("handover", parents=[common], help="print project state, or write HANDOVER.md")
    h.add_argument("--project", default=".")
    h.add_argument("--write", action="store_true", help="write/append HANDOVER.md")
    h.add_argument("--file", default="HANDOVER.md")
    h.add_argument("--no-gitignore", action="store_true")
    h.set_defaults(func=cmd_handover)

    c = sub.add_parser("init-config", parents=[common], help="propose safe read-deny rules (dry run by default)")
    c.add_argument("--project", default=".")
    c.add_argument("--stack", help="comma-separated stacks to use instead of auto-detect")
    c.add_argument("--global", dest="global_", action="store_true",
                   help="target ~/.claude/settings.json (universal rules only)")
    c.add_argument("--hooks", action="store_true",
                   help="also install the Frugal hooks (context warning, state snapshot, resume note)")
    c.add_argument("--apply", action="store_true", help="write the changes (a backup is made first)")
    c.set_defaults(func=cmd_init_config)

    st = sub.add_parser("status", parents=[common], help="check the latest session's context and whether the hooks are working")
    st.add_argument("--project", default=".")
    st.add_argument("--threshold", type=int, default=env_int("FRUGAL_THRESHOLD", HOOK_THRESHOLD))
    st.set_defaults(func=cmd_status)

    k = sub.add_parser("hook", parents=[common], help="entry point used by the hooks (not meant to be run by hand)")
    k.add_argument("event", choices=["prompt", "precompact", "start"])
    k.add_argument("--threshold", type=int, default=env_int("FRUGAL_THRESHOLD", HOOK_THRESHOLD),
                   help="warn above this many tokens of context (default 150000)")
    k.set_defaults(func=cmd_hook)
    return ap


def main(argv=None):
    global LANG
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:  # pragma: no cover
            pass
    args = build_parser().parse_args(argv)
    LANG = detect_lang(args.lang)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
