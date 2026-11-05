#!/usr/bin/env python3
"""Estado de contexto/tokens de la sesión más reciente de DeepSeek Harness.

Lee la proyección que el harness ya escribe en
~/.dsh/storages/session_projcache/sessions/*.json y la resume.

    python estado_contexto.py           # tabla legible
    python estado_contexto.py --json    # objeto crudo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_WINDOW = 1_048_576


def sessions_dir() -> Path:
    home = Path(os.environ.get("DSH_HOME") or (Path(os.environ.get("USERPROFILE") or Path.home()) / ".dsh"))
    return home / "storages" / "session_projcache" / "sessions"


def latest_session_file() -> Path | None:
    d = sessions_dir()
    if not d.is_dir():
        return None
    files = sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def pick(rows: dict, key: str) -> dict:
    try:
        return rows[key]["val"] or {}
    except (KeyError, TypeError):
        return {}


def verdict(pct: float) -> str:
    if pct < 25:
        return "normal (<25 %): no hace falta hacer nada"
    if pct < 45:
        return "medio (25-45 %): delega lecturas pesadas a un subagente y evita skills grandes"
    if pct < 70:
        return "alto (45-70 %): propón traspaso (ESTADO.md + BITACORA.md) y sesión nueva"
    return "crítico (>70 %): traspaso inmediato, no empezar trabajo nuevo"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="imprimir el objeto crudo")
    ap.add_argument("--file", default=None, help="ruta a un projcache concreto")
    args = ap.parse_args()

    path = Path(args.file) if args.file else latest_session_file()
    if not path or not path.is_file():
        print("No encontré la proyección de la sesión. ¿DSH_HOME distinto?", file=sys.stderr)
        return 1

    record = json.loads(path.read_text(encoding="utf-8")).get("record", {})
    rows = record.get("rows", {})

    usage = pick(rows, "tokenUsage").get("totals", {})
    pressure = pick(rows, "contextPressure")
    breakdown = pick(rows, "contextBreakdown").get("breakdown", {})
    title = rows.get("title", {}).get("val") if isinstance(rows.get("title"), dict) else ""
    title = title if isinstance(title, str) else ""
    stats = pick(rows, "sessionStats")
    cwd = record.get("identity", {}).get("cwd", "")

    surface = int(pressure.get("surfaceTokens") or 0)
    window = int(pressure.get("contextWindow") or DEFAULT_WINDOW)
    press = int(pressure.get("pressureTokens") or 0)
    pct = (100.0 * surface / window) if window else 0.0

    data = {
        "session": path.stem,
        "title": title,
        "cwd": cwd,
        "window": window,
        "surface_tokens": surface,
        "pressure_tokens": press,
        "percent": round(pct, 1),
        "breakdown": {
            "system": breakdown.get("systemTokens", 0),
            "tools": breakdown.get("toolsTokens", 0),
            "messages": breakdown.get("messageTokens", 0),
        },
        "billed": {
            "input_uncached": usage.get("uncachedInputTokens", 0),
            "output": usage.get("outputTokens", 0),
            "cache_read": usage.get("cacheReadTokens", 0),
        },
        "turns": stats.get("turns", 0),
        "steps": stats.get("steps", 0),
        "verdict": verdict(pct),
    }

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    b = data["breakdown"]
    print(f"Sesión   : {data['session']}  {('· ' + title) if title else ''}")
    print(f"Ventana  : {window:,} tokens")
    print(f"Consumo  : {surface:,} ({pct:.0f} %)   presión: {press:,} ({100*press/window:.0f} %)")
    print(f"Desglose : sistema {b['system']:,} · herramientas {b['tools']:,} · mensajes {b['messages']:,}")
    print(f"Facturado: input {usage.get('uncachedInputTokens',0):,} · "
          f"output {usage.get('outputTokens',0):,} · caché {usage.get('cacheReadTokens',0):,}")
    print(f"Turnos   : {data['turns']} · pasos: {data['steps']}")
    print(f"Veredicto: {data['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
