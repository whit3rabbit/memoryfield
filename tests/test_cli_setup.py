"""`mf setup` non-interactive subcommands, and the off-terminal gate."""
import json

from mf import cli
from mf.db import init_field


def _root(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    init_field(root / "notes")
    return root


def test_install_json_dry_run_and_apply(tmp_path, capsys):
    root = _root(tmp_path)
    args = ["setup", "install", "--harness", "claude", "codex", "--instructions", "--skill",
            "--field", "notes", "--root", str(root), "--json"]
    assert cli.main([*args, "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["dry_run"] is True and data["failed"] is False and data["mode"] == "install"
    assert {a["action"] for a in data["actions"]} == {"create"}
    assert not (root / "CLAUDE.md").exists()
    assert cli.main(args) == 0
    data = json.loads(capsys.readouterr().out)
    paths = {a["path"]: a for a in data["actions"]}
    assert paths["AGENTS.md"]["harnesses"] == ["codex"]
    assert (root / "CLAUDE.md").exists() and (root / ".agents/skills/mf/SKILL.md").exists()
    assert cli.main(args) == 0
    assert {a["action"] for a in json.loads(capsys.readouterr().out)["actions"]} == {"unchanged"}


def test_install_text_output_and_all_surfaces(tmp_path, capsys):
    root = _root(tmp_path)
    assert cli.main(["setup", "install", "--harness", "claude", "--all-surfaces", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Install for field notes under ")
    assert ".claude/settings.json" in out and ".mcp.json" in out
    assert json.loads((root / ".claude/settings.json").read_text())["hooks"]["Stop"]


def test_install_requires_a_surface(tmp_path, capsys):
    root = _root(tmp_path)
    assert cli.main(["setup", "install", "--harness", "claude", "--root", str(root)]) == 1
    assert "at least one surface" in capsys.readouterr().err


def test_uninstall_and_status(tmp_path, capsys):
    root = _root(tmp_path)
    (root / "CLAUDE.md").write_text("# mine\n")
    assert cli.main(["setup", "install", "--harness", "claude", "--all-surfaces", "--root", str(root)]) == 0
    capsys.readouterr()
    assert cli.main(["setup", "status", "--root", str(root), "--harness", "claude", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["field_initialized"] is True
    states = {(e["harness"], e["surface"]): e["state"] for e in data["entries"]}
    assert states[("claude", "instructions")] == "installed"
    assert states[("claude", "mcp")] == "installed"
    assert cli.main(["setup", "uninstall", "--harness", "claude", "--all-surfaces", "--root", str(root)]) == 0
    assert (root / "CLAUDE.md").read_text() == "# mine\n"
    assert cli.main(["setup", "status", "--root", str(root), "--harness", "claude"]) == 0
    out = capsys.readouterr().out
    assert "Claude Code" in out and "absent" in out and "installed" not in out.split("Claude Code")[1]


def test_skip_exits_1(tmp_path, capsys):
    root = _root(tmp_path)
    (root / "opencode.json").write_text("{ // jsonc\n}")
    assert cli.main(["setup", "install", "--harness", "opencode", "--mcp", "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert "SKIP" in out and "not valid JSON" in out


def test_field_outside_root_is_a_user_error(tmp_path, capsys):
    root = _root(tmp_path)
    assert cli.main(["setup", "install", "--harness", "claude", "--skill", "--root", str(root), "--field", "../x"]) == 1
    assert "mf setup install: field" in capsys.readouterr().err


def test_prompt_prints_the_seeding_prompt(capsys):
    assert cli.main(["setup", "prompt", "--field", "memory"]) == 0
    out = capsys.readouterr().out
    assert "memory/" in out and "--field memory" in out and ".claude/skills/mf/reference.md" in out
    assert cli.main(["setup", "prompt", "--reference", ".pi/skills/mf/reference.md"]) == 0
    assert ".pi/skills/mf/reference.md" in capsys.readouterr().out


def test_bare_setup_off_terminal_exits_1(capsys):
    # pytest's stdin is not a TTY, so the wizard must not start.
    assert cli.main(["setup"]) == 1
    assert "not a terminal" in capsys.readouterr().err
