"""mf.setup: plan by path, apply idempotently, uninstall only what we
wrote, and never rewrite a file we cannot parse."""
import json
from pathlib import Path

import pytest

from mf import configedit as ce
from mf import setup
from mf.db import init_field


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    init_field(root / "notes")
    return root


def _choices(root, harnesses, **kw):
    return setup.SetupChoices(root=root, field="notes", harnesses=harnesses, **kw)


def _by_path(result):
    return {a.path: a for a in result.actions}


def test_dry_run_writes_nothing_and_install_is_idempotent(tmp_path):
    root = _root(tmp_path)
    c = _choices(root, ["claude"], mcp=True, hooks=True)
    dry = setup.install(c, dry_run=True)
    assert dry.dry_run and not dry.failed
    assert {a.action for a in dry.actions} == {"create"}
    assert not (root / "CLAUDE.md").exists() and not (root / ".mcp.json").exists()

    first = setup.install(c)
    paths = _by_path(first)
    assert set(paths) == {
        "CLAUDE.md", ".claude/skills/mf/SKILL.md", ".claude/skills/mf/reference.md",
        ".mcp.json", ".claude/settings.json", "notes/.gitignore",
    }
    assert '`mf search "<question>"`' in (root / "CLAUDE.md").read_text()
    assert "--field" not in (root / "CLAUDE.md").read_text()
    settings = json.loads((root / ".claude/settings.json").read_text())
    assert settings["hooks"]["Stop"][0]["hooks"][0]["command"] == "mf hook stop --field notes"
    mcp = json.loads((root / ".mcp.json").read_text())
    assert mcp["mcpServers"]["mf"] == {"command": "mf", "args": ["mcp", "--field", "notes"]}
    assert (root / ".claude/skills/mf/SKILL.md").read_text() == setup.skill_template("SKILL.md")
    assert "mf.sqlite3" in (root / "notes/.gitignore").read_text()

    second = setup.install(c)
    assert {a.action for a in second.actions} == {"unchanged"}, _by_path(second)


def test_shared_paths_are_written_once_and_list_every_harness(tmp_path):
    root = _root(tmp_path)
    r = setup.install(_choices(root, ["codex", "amp", "pi"]))
    paths = _by_path(r)
    assert paths["AGENTS.md"].harnesses == ["codex", "amp", "pi"]
    assert paths[".agents/skills/mf/SKILL.md"].harnesses == ["codex", "amp"]
    assert paths[".pi/skills/mf/SKILL.md"].harnesses == ["pi"]
    assert (root / "AGENTS.md").read_text().count(ce.FENCE_BEGIN) == 1
    r = setup.install(_choices(root, ["claude", "copilot"], instructions=False, skill=False, mcp=True))
    assert _by_path(r)[".mcp.json"].harnesses == ["claude", "copilot"]


def test_uninstall_leaves_foreign_content(tmp_path):
    root = _root(tmp_path)
    (root / "CLAUDE.md").write_text("# My project\n\nKeep this.\n")
    (root / ".claude").mkdir()
    foreign_group = {"matcher": "Bash", "hooks": [{"type": "command", "command": "lint"}]}
    (root / ".claude/settings.json").write_text(json.dumps({"hooks": {"Stop": [foreign_group]}}))
    (root / ".mcp.json").write_text(json.dumps({"mcpServers": {"other": {"command": "node"}}}))
    (root / "notes/.gitignore").write_text("*.tmp\n")
    c = _choices(root, ["claude"], mcp=True, hooks=True)
    r = setup.install(c)
    assert {a.action for a in r.actions} == {"patch", "create"}
    assert "Keep this." in (root / "CLAUDE.md").read_text()

    r = setup.uninstall(c)
    assert not r.failed
    assert (root / "CLAUDE.md").read_text() == "# My project\n\nKeep this.\n"
    assert json.loads((root / ".claude/settings.json").read_text()) == {"hooks": {"Stop": [foreign_group]}}
    assert json.loads((root / ".mcp.json").read_text()) == {"mcpServers": {"other": {"command": "node"}}}
    assert (root / "notes/.gitignore").read_text() == "*.tmp\n"
    assert not (root / ".claude/skills/mf").exists()
    again = setup.uninstall(c)
    assert {a.action for a in again.actions} == {"unchanged"}


def test_uninstall_removes_files_that_held_only_our_content(tmp_path):
    root = _root(tmp_path)
    c = _choices(root, ["claude", "codex"], mcp=True, hooks=True)
    setup.install(c)
    r = setup.uninstall(c)
    removed = {a.path for a in r.actions if a.action == "remove"}
    assert {"CLAUDE.md", "AGENTS.md", ".mcp.json", ".claude/settings.json",
            ".codex/config.toml", "notes/.gitignore"} <= removed
    assert not (root / "CLAUDE.md").exists()
    assert not (root / ".codex/config.toml").exists()


def test_unparsable_json_is_skipped_not_rewritten(tmp_path):
    root = _root(tmp_path)
    jsonc = '{\n  // my servers\n  "mcp": {}\n}\n'
    (root / "opencode.json").write_text(jsonc)
    r = setup.install(_choices(root, ["opencode"], instructions=False, skill=False, mcp=True))
    assert r.failed
    a = _by_path(r)["opencode.json"]
    assert a.action == "skip" and "not valid JSON" in a.note
    assert (root / "opencode.json").read_text() == jsonc
    # Other files in the same run still land.
    assert _by_path(r)["notes/.gitignore"].action == "create"


def test_foreign_skill_dir_is_skipped(tmp_path):
    root = _root(tmp_path)
    (root / ".claude/skills/mf").mkdir(parents=True)
    (root / ".claude/skills/mf/SKILL.md").write_text("---\nname: other\n---\n")
    r = setup.install(_choices(root, ["claude"]))
    assert r.failed
    assert _by_path(r)[".claude/skills/mf/SKILL.md"].action == "skip"
    assert (root / ".claude/skills/mf/SKILL.md").read_text() == "---\nname: other\n---\n"


def test_codex_toml_and_opencode_shapes(tmp_path):
    root = _root(tmp_path)
    (root / ".codex").mkdir()
    (root / ".codex/config.toml").write_text('model = "x"\n')
    (root / "opencode.json").write_text('{"model": "y"}')
    r = setup.install(_choices(root, ["codex", "opencode"], instructions=False, skill=False, mcp=True))
    assert not r.failed
    toml = (root / ".codex/config.toml").read_text()
    assert toml.startswith('model = "x"\n\n[mcp_servers.mf]\n')
    oc = json.loads((root / "opencode.json").read_text())
    assert oc == {"model": "y", "mcp": {"mf": {"type": "local", "command": ["mf", "mcp", "--field", "notes"]}}}


def test_mcp_warning_when_extra_missing(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(setup, "mcp_extra_installed", lambda: False)
    r = setup.install(_choices(root, ["claude"], mcp=True), dry_run=True)
    assert any("reinstall" in w for w in r.warnings)
    r = setup.install(_choices(root, ["claude"], mcp=False), dry_run=True)
    assert r.warnings == []


def test_root_as_field_drops_the_field_flag(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    init_field(root)
    c = setup.SetupChoices(root=root, field=".", harnesses=["claude"], mcp=True, hooks=True)
    setup.install(c)
    assert "--field ." not in (root / "CLAUDE.md").read_text()
    assert json.loads((root / ".mcp.json").read_text())["mcpServers"]["mf"]["args"] == ["mcp"]
    assert "mf hook stop" == json.loads((root / ".claude/settings.json").read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert (root / ".gitignore").exists()


def test_choices_reject_unknown_harness_and_field_outside_root(tmp_path):
    root = _root(tmp_path)
    with pytest.raises(ValueError, match="unsupported harness"):
        setup.SetupChoices(root=root, field="notes", harnesses=["roo"])
    with pytest.raises(ValueError, match="outside"):
        setup.SetupChoices(root=root, field="../elsewhere", harnesses=["claude"])
    c = setup.SetupChoices(root=root, field=str(root / "notes"), harnesses=["claude"])
    assert c.field == "notes"


def test_status_reports_each_surface(tmp_path):
    root = _root(tmp_path)
    s = setup.status(root, "notes", ["cursor", "claude"])
    assert s.field_initialized
    states = {(e.harness, e.surface): e.state for e in s.entries}
    assert states[("cursor", "instructions")] == "unsupported"
    assert states[("cursor", "hooks")] == "unsupported"
    assert states[("claude", "instructions")] == "absent"
    setup.install(_choices(root, ["claude"], mcp=True, hooks=True))
    (root / ".mcp.json").write_text("{not json")
    s = setup.status(root, "notes", ["claude"])
    states = {(e.harness, e.surface): e.state for e in s.entries}
    assert states[("claude", "instructions")] == "installed"
    assert states[("claude", "skill")] == "installed"
    assert states[("claude", "hooks")] == "installed"
    assert states[("claude", "mcp")] == "malformed"
    assert states[("field", "gitignore")] == "installed"
    (root / ".claude/skills/mf/SKILL.md").write_text("---\nname: other\n---\n")
    s = setup.status(root, "notes", ["claude"])
    assert {(e.harness, e.surface): e.state for e in s.entries}[("claude", "skill")] == "unmanaged"
    text = setup.render_status_text(s)
    assert "Claude Code" in text and "unmanaged" in text


def test_render_and_as_dict_shapes(tmp_path):
    root = _root(tmp_path)
    r = setup.install(_choices(root, ["claude"]), dry_run=True)
    d = r.as_dict()
    assert d["mode"] == "install" and d["dry_run"] is True and d["failed"] is False
    assert d["actions"][0].keys() == {"path", "surface", "harnesses", "action", "note"}
    text = setup.render_setup_text(r)
    assert text.startswith("Would install for field notes")
    assert "create    CLAUDE.md  (instructions: claude)" in text


def test_seeding_prompt_and_instruction_body_substitute_the_field():
    assert "--field" not in setup.instruction_body("notes")
    p = " ".join(setup.seeding_prompt("notes").split())
    assert "seed the memoryfield in notes/" in p and ".claude/skills/mf/reference.md" in p
    assert "outside notes/" in p and "`mf lint`" in p and "`mf write <draft>`" in p
    assert max(len(line) for line in setup.seeding_prompt("notes").splitlines()) <= 72
    assert ".agents/skills/mf/reference.md" in setup.seeding_prompt("notes", ".agents/skills/mf/reference.md")

    assert "--field memory" in setup.instruction_body("memory")
    p_mem = " ".join(setup.seeding_prompt("memory").split())
    assert "seed the memoryfield in memory/" in p_mem and "`mf lint --field memory`" in p_mem

    root = " ".join(setup.seeding_prompt(".").split())
    assert "--field" not in root and "./" not in root and ".." not in root
    assert "the repo root" in root and "in a temp directory" in root and "`mf lint`" in root
