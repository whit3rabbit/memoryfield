"""The wizard is driven through a scripted prompter, so no test ever
builds a questionary prompt (which would print a no-TTY warning and
raise EOFError under pytest)."""
import io
import json
import sys

import pytest

from mf import cli, wizard
from mf.db import init_field


class ScriptedPrompter:
    """Answers in order; records every question so tests can assert on
    the choices offered."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.asked = []

    def _next(self, kind, message, choices=None):
        self.asked.append((kind, message, choices))
        if not self.answers:
            raise AssertionError(f"wizard asked more than scripted: {kind} {message!r}")
        return self.answers.pop(0)

    def text(self, message, default):
        del default
        return self._next("text", message)

    def checkbox(self, message, choices):
        return self._next("checkbox", message, choices)

    def confirm(self, message, default):
        del default
        return self._next("confirm", message)


def _root(tmp_path, init=True):
    root = tmp_path / "project"
    root.mkdir()
    if init:
        init_field(root / "notes")
    return root


def test_full_flow_installs_and_prints_seeding_prompt(tmp_path):
    root = _root(tmp_path)
    (root / ".claude").mkdir()
    p = ScriptedPrompter([["claude", "codex"], ["instructions", "skill", "hooks"], True])
    out = io.StringIO()
    assert wizard.run_wizard(root, p, field="notes", out=out) == 0
    kinds = [k for k, _, _ in p.asked]
    assert kinds == ["checkbox", "checkbox", "confirm"]
    harness_choices = p.asked[0][2]
    assert [c.value for c in harness_choices if not c.separator and not c.disabled][:5] == \
        ["claude", "codex", "cursor", "copilot", "opencode"]
    assert next(c for c in harness_choices if c.value == "claude").checked is True
    assert next(c for c in harness_choices if c.value == "codex").checked is False
    assert all(c.disabled == "not yet" for c in harness_choices if c.value == "roo")
    surface_values = [c.value for c in p.asked[1][2]]
    assert surface_values == ["instructions", "skill", "mcp", "hooks"]
    text = out.getvalue()
    assert "Would install for field notes" in text and "Install for field notes" in text
    assert "seed the memoryfield in notes/" in " ".join(text.split())
    assert ".claude/skills/mf/reference.md" in text
    assert (root / "CLAUDE.md").exists() and (root / "AGENTS.md").exists()
    assert json.loads((root / ".claude/settings.json").read_text())["hooks"]["Stop"]
    assert not (root / ".mcp.json").exists()


def test_hooks_offered_only_with_claude(tmp_path):
    root = _root(tmp_path)
    p = ScriptedPrompter([["pi"], ["skill"], False])
    assert wizard.run_wizard(root, p, field="notes", out=io.StringIO()) == 0
    assert [c.value for c in p.asked[1][2]] == ["instructions", "skill", "mcp"]
    assert not (root / ".pi/skills").exists()


def test_declining_the_plan_writes_nothing(tmp_path):
    root = _root(tmp_path)
    p = ScriptedPrompter([["claude"], ["instructions"], False])
    out = io.StringIO()
    assert wizard.run_wizard(root, p, field="notes", out=out) == 0
    assert "Nothing written." in out.getvalue()
    assert not (root / "CLAUDE.md").exists()


def test_asks_for_field_and_offers_init_when_missing(tmp_path):
    root = _root(tmp_path, init=False)
    p = ScriptedPrompter(["memory", True, ["claude"], ["instructions"], True])
    out = io.StringIO()
    assert wizard.run_wizard(root, p, out=out) == 0
    assert p.asked[0][0] == "text"
    assert p.asked[1] == ("confirm", "No field at memory/. Run `mf init memory`?", None)
    assert (root / "memory" / "mf.sqlite3").exists()
    assert "--field memory" in (root / "CLAUDE.md").read_text()

    other = tmp_path / "other"
    other.mkdir()
    p = ScriptedPrompter(["x", False])
    assert wizard.run_wizard(other, p, out=io.StringIO()) == 1
    assert not (other / "x").exists()

    p = ScriptedPrompter(["../escape"])
    out = io.StringIO()
    assert wizard.run_wizard(other, p, out=out) == 1
    assert "outside" in out.getvalue()


def test_empty_selection_exits_cleanly(tmp_path):
    root = _root(tmp_path)
    assert wizard.run_wizard(root, ScriptedPrompter([[]]), field="notes", out=io.StringIO()) == 0
    assert wizard.run_wizard(root, ScriptedPrompter([["claude"], []]), field="notes", out=io.StringIO()) == 0


def test_mf_init_runs_the_wizard_on_a_terminal(tmp_path, monkeypatch, capsys):
    root = _root(tmp_path, init=False)
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(
        wizard, "QuestionaryPrompter", lambda: ScriptedPrompter([["claude"], ["instructions"], True])
    )
    assert cli.main(["init", "notes"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Initialized empty field at ")
    assert "Install for field notes" in out
    assert (root / "CLAUDE.md").exists()


def test_mf_init_no_setup_or_off_terminal_prints_only_the_init_line(tmp_path, monkeypatch, capsys):
    root = _root(tmp_path, init=False)
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(wizard, "QuestionaryPrompter", lambda: pytest.fail("wizard must not start"))
    assert cli.main(["init", "notes", "--no-setup"]) == 0
    assert capsys.readouterr().out.count("\n") == 1
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert cli.main(["init", "notes2"]) == 0
    assert capsys.readouterr().out.count("\n") == 1


def test_mf_init_outside_cwd_hints_instead_of_guessing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(wizard, "QuestionaryPrompter", lambda: pytest.fail("wizard must not start"))
    elsewhere = tmp_path.parent / f"{tmp_path.name}-elsewhere"
    assert cli.main(["init", str(elsewhere)]) == 0
    assert "Run `mf setup` from the project root" in capsys.readouterr().out


def test_bare_setup_on_a_terminal_runs_the_wizard(tmp_path, monkeypatch, capsys):
    root = _root(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(wizard, "QuestionaryPrompter", lambda: ScriptedPrompter(["notes", ["claude"], ["skill"], True]))
    assert cli.main(["setup"]) == 0
    assert (root / ".claude/skills/mf/SKILL.md").exists()
