"""Automated tests for Frugal. Run from the repository root:

    python -m unittest discover -s tests -v

Standard library only. Every test builds its own throwaway project in a temp
directory, so nothing on the real machine is read or modified.
"""

import ast
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills" / "frugal" / "scripts" / "frugal.py"
if not SCRIPT.exists():  # installed copy: SKILL.md and scripts/ sit next to tests/
    SCRIPT = ROOT / "scripts" / "frugal.py"
sys.path.insert(0, str(SCRIPT.parent))

import frugal  # noqa: E402


def run_cli(*args, env_extra=None, stdin=None):
    """Run the real script as a subprocess, like a user would."""
    env = dict(os.environ)
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)] + list(args),
        capture_output=True, env=env, timeout=60,
        input=stdin.encode("utf-8") if stdin is not None else None,
    )
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def git(cwd, *args):
    subprocess.run(["git"] + list(args), cwd=str(cwd), check=True, capture_output=True)


class TempProject(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        # An empty fake Claude config dir so tests never see the real one.
        self.home = Path(self._tmp.name) / "claude_home"
        self.home.mkdir()
        self.env = {"CLAUDE_CONFIG_DIR": str(self.home), "HOME": self._tmp.name,
                    "USERPROFILE": self._tmp.name, "FRUGAL_LANG": "en"}

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class TestHelpers(unittest.TestCase):
    def test_project_slug_posix_and_windows(self):
        self.assertEqual(frugal.project_slug("/home/me/my_app.v2"), "-home-me-my-app-v2")
        self.assertEqual(frugal.project_slug("C:\\Users\\Ana\\Work\\app"), "C--Users-Ana-Work-app")

    def test_frontmatter_list_and_block(self):
        fm = frugal.parse_frontmatter('---\nname: x\ndescription: >-\n  one\n  two\npaths:\n  - "src/**"\n---\nbody')
        self.assertEqual(fm["name"], "x")
        self.assertEqual(fm["description"], "one two")
        self.assertEqual(fm["paths"], ["src/**"])

    def test_frontmatter_missing(self):
        self.assertEqual(frugal.parse_frontmatter("no frontmatter"), {})

    def test_human(self):
        self.assertEqual(frugal.human(999), "999")
        self.assertEqual(frugal.human(1500), "1.5k")
        self.assertEqual(frugal.human(2_000_000), "2.0M")

    def test_every_translated_string_exists(self):
        """Each English string passed to t() must have a Spanish entry."""
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        missing = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "t" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                text = node.args[0].value
                if text not in frugal.ES:
                    missing.append(text[:70])
        self.assertEqual(missing, [], "strings without a Spanish translation")

    def test_language_detection(self):
        self.assertEqual(frugal.detect_lang("es"), "es")
        self.assertEqual(frugal.detect_lang("en"), "en")
        old = os.environ.get("FRUGAL_LANG")
        os.environ["FRUGAL_LANG"] = "es_PE.UTF-8"
        try:
            self.assertEqual(frugal.detect_lang(None), "es")
        finally:
            if old is None:
                del os.environ["FRUGAL_LANG"]
            else:
                os.environ["FRUGAL_LANG"] = old


class TestStacks(TempProject):
    def test_detects_node_and_python(self):
        self.write("package.json", "{}")
        self.write("requirements.txt", "x")
        self.assertEqual(sorted(frugal.detect_stacks(self.root)), ["node", "python"])

    def test_detects_odoo_one_level_down(self):
        self.write("my_module/__manifest__.py", "{}")
        self.assertIn("odoo", frugal.detect_stacks(self.root))

    def test_no_stack(self):
        self.assertEqual(frugal.detect_stacks(self.root), [])

    def test_recommended_includes_universal_and_stack(self):
        rules = frugal.recommended_deny(["node"])
        self.assertIn("Read(./node_modules/**)", rules)
        self.assertIn("Read(./.git/**)", rules)
        self.assertEqual(len(rules), len(set(rules)))


class TestDoctor(TempProject):
    def test_flags_big_claude_md_and_unscoped_rules(self):
        self.write("CLAUDE.md", "x" * 9000)
        self.write(".claude/rules/always.md", "# always\n" + "y" * 400)
        self.write(".claude/rules/scoped.md", '---\npaths:\n  - "src/**"\n---\nonly here')
        code, out, _ = run_cli("doctor", "--project", str(self.root), env_extra=self.env)
        self.assertEqual(code, 0)
        self.assertIn("CLAUDE.md is about", out)
        self.assertIn("always.md", out)
        self.assertNotIn("scoped.md", out)

    def test_comments_do_not_count(self):
        self.write("CLAUDE.md", "<!-- " + "z" * 20000 + " -->\nshort")
        code, out, _ = run_cli("doctor", "--project", str(self.root), "--json", env_extra=self.env)
        data = json.loads(out)
        claude = [i for i in data["always_on"] if i["item"] == "CLAUDE.md"][0]
        self.assertLess(claude["tokens"], 50)

    def test_stale_paths_detected(self):
        self.write("CLAUDE.md", "Run `scripts/missing_tool.py` and see `docs/` and `real.txt`.")
        self.write("real.txt", "ok")
        code, out, _ = run_cli("doctor", "--project", str(self.root), env_extra=self.env)
        self.assertIn("scripts/missing_tool.py", out)
        self.assertNotIn("real.txt,", out)

    def test_missing_deny_rules_flagged_then_fixed(self):
        self.write("package.json", "{}")
        _, out, _ = run_cli("doctor", "--project", str(self.root), env_extra=self.env)
        self.assertIn("No read-deny rules", out)
        run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        _, out, _ = run_cli("doctor", "--project", str(self.root), env_extra=self.env)
        self.assertNotIn("No read-deny rules", out)

    def test_clean_project_has_no_warnings_in_strict_mode(self):
        self.write("CLAUDE.md", "Short and useful.")
        code, out, _ = run_cli("doctor", "--project", str(self.root), "--strict", env_extra=self.env)
        self.assertEqual(code, 0)

    def test_strict_exit_code(self):
        self.write("CLAUDE.md", "x" * 9000)
        code, _, _ = run_cli("doctor", "--project", str(self.root), "--strict", env_extra=self.env)
        self.assertEqual(code, 1)

    def test_many_mcp_servers_flagged(self):
        self.write(".mcp.json", json.dumps({"mcpServers": {"a": {}, "b": {}, "c": {}}}))
        _, out, _ = run_cli("doctor", "--project", str(self.root), env_extra=self.env)
        self.assertIn("3 MCP server(s)", out)

    def test_spanish_output(self):
        self.write("CLAUDE.md", "x" * 9000)
        _, out, _ = run_cli("--lang", "es", "doctor", "--project", str(self.root), env_extra=self.env)
        self.assertIn("DIAGNÓSTICO FRUGAL", out)
        self.assertIn("pesa unos", out)

    def test_json_output_is_valid(self):
        _, out, _ = run_cli("doctor", "--project", str(self.root), "--json", env_extra=self.env)
        data = json.loads(out)
        self.assertIn("always_on_total", data)


class TestInitConfig(TempProject):
    def test_dry_run_changes_nothing(self):
        self.write("package.json", "{}")
        code, out, _ = run_cli("init-config", "--project", str(self.root), env_extra=self.env)
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertFalse((self.root / ".claude" / "settings.json").exists())

    def test_apply_creates_file_with_rules(self):
        self.write("package.json", "{}")
        run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        data = json.loads((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Read(./node_modules/**)", data["permissions"]["deny"])

    def test_apply_preserves_existing_keys_and_makes_backup(self):
        self.write("package.json", "{}")
        original = {"hooks": {"x": 1}, "permissions": {"allow": ["Bash(ls)"], "deny": ["Read(./secret.txt)"]},
                    "statusLine": {"type": "command"}}
        settings = self.write(".claude/settings.json", json.dumps(original))
        run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["hooks"], {"x": 1})
        self.assertEqual(data["statusLine"], {"type": "command"})
        self.assertEqual(data["permissions"]["allow"], ["Bash(ls)"])
        self.assertIn("Read(./secret.txt)", data["permissions"]["deny"])
        self.assertIn("Read(./node_modules/**)", data["permissions"]["deny"])
        backups = list(settings.parent.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(json.loads(backups[0].read_text(encoding="utf-8")), original)

    def test_apply_is_idempotent(self):
        self.write("package.json", "{}")
        run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        first = (self.root / ".claude" / "settings.json").read_text(encoding="utf-8")
        _, out, _ = run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        self.assertIn("Nothing to add", out)
        self.assertEqual((self.root / ".claude" / "settings.json").read_text(encoding="utf-8"), first)

    def test_invalid_json_aborts_without_touching_file(self):
        self.write("package.json", "{}")
        settings = self.write(".claude/settings.json", "{ not json")
        code, _, err = run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        self.assertEqual(code, 1)
        self.assertIn("Nothing was changed", err)
        self.assertEqual(settings.read_text(encoding="utf-8"), "{ not json")
        self.assertEqual(list(settings.parent.glob("*.bak-*")), [])

    def test_equivalent_rule_without_dot_slash_counts_as_present(self):
        self.write("package.json", "{}")
        self.write(".claude/settings.json", json.dumps({"permissions": {"deny": ["Read(node_modules/**)"]}}))
        _, out, _ = run_cli("init-config", "--project", str(self.root), env_extra=self.env)
        self.assertNotIn("+ Read(./node_modules/**)", out)

    def test_explicit_stack_override(self):
        _, out, _ = run_cli("init-config", "--project", str(self.root), "--stack", "go", env_extra=self.env)
        self.assertIn("Read(./vendor/**)", out)

    def test_utf8_bom_settings_are_readable(self):
        self.write("package.json", "{}")
        p = self.root / ".claude" / "settings.json"
        p.parent.mkdir(parents=True)
        p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"model": "x"}).encode("utf-8"))
        code, _, _ = run_cli("init-config", "--project", str(self.root), "--apply", env_extra=self.env)
        self.assertEqual(code, 0)
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "x")


class TestHandover(TempProject):
    def test_print_state_without_git(self):
        self.write("a.txt", "x")
        code, out, _ = run_cli("handover", "--project", str(self.root), env_extra=self.env)
        self.assertEqual(code, 0)
        self.assertIn("Not a git repository.", out)
        self.assertIn("a.txt", out)

    def test_write_creates_file_with_sections(self):
        code, out, _ = run_cli("handover", "--project", str(self.root), "--write", env_extra=self.env)
        self.assertEqual(code, 0)
        text = (self.root / "HANDOVER.md").read_text(encoding="utf-8")
        for heading in ("## Goal", "## State", "## Key decisions", "## Next step", "## Traps"):
            self.assertIn(heading, text)

    def test_second_write_appends_not_overwrites(self):
        (self.root / "HANDOVER.md").write_text("MY NOTES\n", encoding="utf-8")
        run_cli("handover", "--project", str(self.root), "--write", env_extra=self.env)
        text = (self.root / "HANDOVER.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MY NOTES"))
        self.assertIn("## Next step", text)

    def test_git_repo_gets_gitignore_entry_once(self):
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "T")
        self.write("f.txt", "1")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "first")
        run_cli("handover", "--project", str(self.root), "--write", env_extra=self.env)
        run_cli("handover", "--project", str(self.root), "--write", env_extra=self.env)
        gi = (self.root / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(gi.count("HANDOVER.md"), 1)
        _, out, _ = run_cli("handover", "--project", str(self.root), env_extra=self.env)
        self.assertIn("first", out)

    def test_no_gitignore_flag(self):
        git(self.root, "init", "-q")
        run_cli("handover", "--project", str(self.root), "--write", "--no-gitignore", env_extra=self.env)
        self.assertFalse((self.root / ".gitignore").exists())

    def test_spanish_template(self):
        run_cli("--lang", "es", "handover", "--project", str(self.root), "--write", env_extra=self.env)
        text = (self.root / "HANDOVER.md").read_text(encoding="utf-8")
        self.assertIn("## Siguiente paso", text)


def make_session(path, peak=1000, big_result=5000):
    records = [
        {"type": "user", "message": {"role": "user", "content": "hello"}},
        {"type": "assistant", "message": {
            "id": "m1", "role": "assistant",
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": peak,
                      "cache_read_input_tokens": 200, "output_tokens": 50},
            "content": [{"type": "tool_use", "id": "t1", "name": "Read",
                         "input": {"file_path": "/x/node_modules/big.js"}}]}},
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "content": "a" * big_result}]}},
        {"type": "assistant", "message": {
            "id": "m1", "role": "assistant",   # duplicate id must not be double counted
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": peak,
                      "cache_read_input_tokens": 200, "output_tokens": 50},
            "content": []}},
        "not json at all",
    ]
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write((r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)) + "\n")


class TestAudit(TempProject):
    def setUp(self):
        super().setUp()
        self.logs = Path(self._tmp.name) / "logs"
        slug = frugal.project_slug(self.root.resolve())
        (self.logs / slug).mkdir(parents=True)
        make_session(self.logs / slug / "s1.jsonl")
        (self.logs / "-other-project").mkdir()
        make_session(self.logs / "-other-project" / "s2.jsonl", peak=999_999)

    def test_scan_session_counts_usage_once(self):
        slug = frugal.project_slug(self.root.resolve())
        stats = frugal.scan_session(self.logs / slug / "s1.jsonl")
        self.assertEqual(stats["usage"]["output"], 50)
        self.assertEqual(stats["usage"]["cache_write"], 1000)
        self.assertEqual(stats["tool_calls"]["Read"], 1)
        self.assertEqual(stats["tool_bytes"]["Read"], 5000)
        self.assertEqual(stats["peak"], 10 + 1000 + 200)

    def test_audit_scopes_to_project(self):
        code, out, _ = run_cli("audit", "--project", str(self.root), "--root", str(self.logs),
                               "--json", env_extra=self.env)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["sessions"], 1)
        self.assertLess(data["peak_context"], 5000)

    def test_audit_all_projects(self):
        _, out, _ = run_cli("audit", "--root", str(self.logs), "--json", env_extra=self.env)
        self.assertEqual(json.loads(out)["sessions"], 2)

    def test_audit_text_report_and_tips(self):
        _, out, _ = run_cli("audit", "--root", str(self.logs), env_extra=self.env)
        self.assertIn("TOKEN AUDIT", out)
        self.assertIn("WHAT TO FIX", out)
        self.assertIn("init-config", out)          # vendor folder was read
        self.assertIn("handover and /clear", out)  # peak context over 150k

    def test_audit_unknown_project(self):
        other = Path(self._tmp.name) / "nope"
        other.mkdir()
        code, _, err = run_cli("audit", "--project", str(other), "--root", str(self.logs), env_extra=self.env)
        self.assertEqual(code, 1)
        self.assertIn("No logs for project folder", err)

    def test_audit_missing_root(self):
        code, _, err = run_cli("audit", "--root", str(Path(self._tmp.name) / "none"), env_extra=self.env)
        self.assertEqual(code, 1)
        self.assertIn("No session logs found", err)

    def test_audit_spanish(self):
        _, out, _ = run_cli("--lang", "es", "audit", "--root", str(self.logs), env_extra=self.env)
        self.assertIn("AUDITORÍA DE TOKENS", out)
        self.assertIn("QUÉ CORREGIR", out)


def make_transcript(path, context_tokens):
    """A minimal session log whose last assistant message carried this context."""
    recs = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"id": "m1", "role": "assistant", "content": [],
            "usage": {"input_tokens": 5, "cache_creation_input_tokens": 1000,
                      "cache_read_input_tokens": context_tokens - 1005, "output_tokens": 10}}},
        {"type": "user", "message": {"role": "user", "content": "x" * 50}},
    ]
    Path(path).write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")


class TestHooks(TempProject):
    def hook(self, event, payload, lang="en", extra=None):
        return run_cli("--lang", lang, "hook", event, *(extra or []),
                       env_extra=self.env, stdin=json.dumps(payload))

    def test_current_context_reads_last_assistant_usage(self):
        tr = self.root / "t.jsonl"
        make_transcript(tr, 180_000)
        self.assertEqual(frugal.current_context(str(tr)), 180_000)
        self.assertEqual(frugal.current_context(str(self.root / "missing.jsonl")), 0)
        self.assertEqual(frugal.current_context(None), 0)

    def test_prompt_hook_silent_below_threshold(self):
        tr = self.root / "t.jsonl"
        make_transcript(tr, 90_000)
        code, out, _ = self.hook("prompt", {"transcript_path": str(tr), "session_id": "below1"})
        self.assertEqual((code, out.strip()), (0, ""))

    def test_prompt_hook_warns_once_then_waits_for_growth(self):
        tr = self.root / "t.jsonl"
        sid = "warn-%d" % os.getpid()
        marker = frugal._marker_path(sid)
        self.addCleanup(lambda: marker.exists() and marker.unlink())
        make_transcript(tr, 160_000)
        _, out, _ = self.hook("prompt", {"transcript_path": str(tr), "session_id": sid})
        self.assertIn("HANDOVER.md", out)
        self.assertIn("160k", out)
        self.assertIn("/clear", out)
        self.assertIn("STEP 3", out)
        _, again, _ = self.hook("prompt", {"transcript_path": str(tr), "session_id": sid})
        self.assertEqual(again.strip(), "")
        make_transcript(tr, 215_000)  # grew by more than the step
        _, more, _ = self.hook("prompt", {"transcript_path": str(tr), "session_id": sid})
        self.assertIn("215k", more)

    def test_prompt_hook_spanish_and_threshold_flag(self):
        tr = self.root / "t.jsonl"
        sid = "es-%d" % os.getpid()
        self.addCleanup(lambda: frugal._marker_path(sid).exists() and frugal._marker_path(sid).unlink())
        make_transcript(tr, 70_000)
        _, out, _ = self.hook("prompt", {"transcript_path": str(tr), "session_id": sid},
                              lang="es", extra=["--threshold", "50000"])
        self.assertIn("Escribe HANDOVER.md", out)
        self.assertIn("PASO 3", out)
        self.assertIn("Lee HANDOVER.md y contin", out)

    def test_hooks_never_fail_on_garbage_input(self):
        for event in ("prompt", "precompact", "start"):
            code, _, _ = run_cli("hook", event, env_extra=self.env, stdin="not json {{{")
            self.assertEqual(code, 0, event)
            code, _, _ = run_cli("hook", event, env_extra=self.env, stdin="")
            self.assertEqual(code, 0, event)

    def test_start_hook_gives_reading_rule_and_mentions_fresh_handover(self):
        _, out, _ = self.hook("start", {"cwd": str(self.root), "source": "startup"})
        self.assertIn("Reading rule", out)
        self.assertNotIn("HANDOVER.md", out)
        self.write("HANDOVER.md", "# h\n")
        _, out, _ = self.hook("start", {"cwd": str(self.root), "source": "startup"})
        self.assertIn("Reading rule", out)
        self.assertIn("HANDOVER.md", out)
        _, out, _ = self.hook("start", {"cwd": str(self.root), "source": "resume"})
        self.assertEqual(out.strip(), "")
        old = self.root / "HANDOVER.md"
        past = old.stat().st_mtime - 30 * 86400
        os.utime(str(old), (past, past))
        _, out, _ = self.hook("start", {"cwd": str(self.root), "source": "clear"})
        self.assertIn("Reading rule", out)
        self.assertNotIn("HANDOVER.md", out)

    def test_start_hook_rule_in_spanish(self):
        _, out, _ = self.hook("start", {"cwd": str(self.root), "source": "startup"}, lang="es")
        self.assertIn("Regla de lectura", out)

    def test_precompact_writes_state_and_stays_silent(self):
        git(self.root, "init", "-q")
        self.write("a.txt", "x")
        _, out, _ = self.hook("precompact", {"cwd": str(self.root)})
        self.assertEqual(out.strip(), "")
        state = (self.root / ".frugal" / "STATE.md").read_text(encoding="utf-8")
        self.assertIn("a.txt", state)
        self.assertIn(".frugal/", (self.root / ".gitignore").read_text(encoding="utf-8"))

    def test_init_config_hooks_dry_run_then_apply_is_idempotent(self):
        settings = self.root / ".claude" / "settings.json"
        settings.parent.mkdir()
        settings.write_text(json.dumps({"model": "x", "hooks": {"Stop": [
            {"hooks": [{"type": "command", "command": "echo hi"}]}]}}), encoding="utf-8")
        before = settings.read_text(encoding="utf-8")
        code, out, _ = run_cli("init-config", "--hooks", "--project", str(self.root), env_extra=self.env)
        self.assertEqual(code, 0)
        self.assertIn("UserPromptSubmit", out)
        self.assertEqual(settings.read_text(encoding="utf-8"), before)
        code, out, _ = run_cli("init-config", "--hooks", "--apply", "--project", str(self.root),
                               env_extra=self.env)
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(data["model"], "x")
        self.assertIn("Stop", data["hooks"])
        for name in ("UserPromptSubmit", "PreCompact", "SessionStart"):
            cmd = data["hooks"][name][0]["hooks"][0]["command"]
            self.assertIn("frugal.py", cmd)
        self.assertTrue(list(settings.parent.glob("settings.json.bak-*")))
        code, out, _ = run_cli("init-config", "--hooks", "--apply", "--project", str(self.root),
                               env_extra=self.env)
        data2 = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(len(data2["hooks"]["UserPromptSubmit"]), 1)

    def test_status_reports_context_and_verdict(self):
        slug = frugal.project_slug(self.root.resolve())
        logs = self.home / "projects" / slug
        logs.mkdir(parents=True)
        make_transcript(logs / "sess1.jsonl", 90_000)
        code, out, _ = run_cli("status", "--project", str(self.root), env_extra=self.env)
        self.assertEqual(code, 0)
        self.assertIn("90k", out)
        self.assertIn("under the threshold", out)
        self.assertIn("No Frugal hooks found", out)
        make_transcript(logs / "sess1.jsonl", 170_000)
        code, out, _ = run_cli("status", "--project", str(self.root), env_extra=self.env)
        self.assertIn("no warning is recorded yet", out)

    def test_stale_paths_honours_ignore_marker(self):
        text = "see `gone/file.py`\nold `legacy/old.py` <!-- frugal-ignore -->\n"
        self.assertEqual(frugal.stale_paths(text, self.root), ["gone/file.py"])

    def test_doctor_honours_ignore_marker_in_html_comment(self):
        self.write("CLAUDE.md", "Icons list: `vendor_app/icons.txt` <!-- frugal-ignore -->\n")
        _, out, _ = run_cli("doctor", "--project", str(self.root), env_extra=self.env)
        self.assertNotIn("vendor_app/icons.txt", out)

    def test_stale_paths_bare_name_found_in_subfolder(self):
        self.write("security/rules.xml", "<x/>")
        text = "see `rules.xml` and `nowhere.xml`"
        self.assertEqual(frugal.stale_paths(text, self.root), ["nowhere.xml"])

    def test_stale_paths_present_on_other_branch(self):
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        self.write("old/legacy.py", "x = 1")
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "legacy")
        git(self.root, "checkout", "-q", "-b", "next")
        git(self.root, "rm", "-q", "-r", "old")
        git(self.root, "commit", "-q", "-m", "drop")
        text = "see `old/legacy.py` and `gone/file.py`"
        self.assertEqual(frugal.stale_paths(text, self.root), ["gone/file.py"])

    def test_handover_template_has_outside_repo_section(self):
        code, _, _ = run_cli("handover", "--write", "--project", str(self.root), env_extra=self.env)
        self.assertEqual(code, 0)
        self.assertIn("Outside the repo", (self.root / "HANDOVER.md").read_text(encoding="utf-8"))


class TestCli(unittest.TestCase):
    def test_lang_accepted_after_subcommand(self):
        code, out, err = run_cli("doctor", "--lang", "es", "--project", str(ROOT))
        self.assertEqual(code, 0, err)
        self.assertIn("DIAGNÓSTICO", out)

    def test_version(self):
        code, out, _ = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn("frugal 0.2", out)

    def test_requires_command(self):
        code, _, err = run_cli()
        self.assertNotEqual(code, 0)

    def test_skill_md_frontmatter_is_valid_and_short(self):
        text = (SCRIPT.parent.parent / "SKILL.md").read_text(encoding="utf-8")
        fm = frugal.parse_frontmatter(text)
        self.assertEqual(fm["name"], "frugal")
        self.assertTrue(fm["description"])
        self.assertLess(len(fm["description"]), 1024)
        self.assertLess(len(text), 4500, "SKILL.md must stay light: it loads whenever the skill triggers")

    def test_no_non_stdlib_imports(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        allowed = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else None
        if allowed is None:
            self.skipTest("needs Python 3.10+ for sys.stdlib_module_names")
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.assertIn(a.name.split(".")[0], allowed)
            elif isinstance(node, ast.ImportFrom) and node.module:
                self.assertIn(node.module.split(".")[0], allowed)


if __name__ == "__main__":
    unittest.main()
