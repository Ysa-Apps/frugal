# What init-config blocks

Universal (always): `.git/`, `*.min.js`, `*.min.css`, `*.map`.

| Technology | Detected by | Also blocked |
|---|---|---|
| Node | `package.json` | `node_modules/`, `dist/`, `build/`, `.next/`, `coverage/`, lockfiles |
| Python | `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile` | `venv/`, `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.mypy_cache/`, `.tox/`, `*.egg-info/` |
| Java | `pom.xml`, `build.gradle(.kts)` | `target/`, `build/`, `.gradle/` |
| Go | `go.mod` | `vendor/` |
| Rust | `Cargo.toml` | `target/`, `Cargo.lock` |
| PHP | `composer.json` | `vendor/`, `composer.lock` |
| Ruby | `Gemfile` | `vendor/`, `.bundle/` |
| .NET | `*.csproj`, `*.sln` | `bin/`, `obj/` |
| Flutter | `pubspec.yaml` | `.dart_tool/`, `build/` |
| Odoo | `__manifest__.py` | `i18n/*.pot`, `static/lib/`, `filestore/` |

Override detection with `--stack node,python`. Rules are only ever added, never
removed, and existing keys in the settings file are preserved.

To support another technology, add an entry to `STACKS` in `scripts/frugal.py`.
