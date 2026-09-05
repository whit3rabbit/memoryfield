"""configedit: every transform is idempotent, leaves foreign content
alone, and refuses to touch what it cannot parse."""
import json
import os

import pytest

from mf import configedit as ce

BODY = "Before exploring, run `mf search`.\nBefore finishing, run `mf write`."


# --- Markdown block

def test_block_appends_after_one_blank_line_and_replaces_in_place():
    text = "# CLAUDE.md\n\nSome prose.\n"
    out = ce.upsert_block(text, BODY)
    assert out == text + "\n" + ce.render_block(BODY)
    assert ce.block_state(out) == "installed"
    assert ce.upsert_block(out, BODY) == out
    changed = ce.upsert_block(out + "\nTrailing prose.\n", "new body")
    assert "new body" in changed and BODY not in changed
    assert changed.startswith("# CLAUDE.md\n\nSome prose.\n") and changed.endswith("Trailing prose.\n")
    assert ce.upsert_block("", BODY) == ce.render_block(BODY)


def test_block_remove_keeps_surrounding_prose():
    text = "# Title\n\nKeep me.\n"
    out = ce.remove_block(ce.upsert_block(text, BODY))
    assert out == text
    assert ce.remove_block(ce.render_block(BODY)) == ""
    assert ce.remove_block("untouched\n") == "untouched\n"


def test_block_malformed_fence_is_refused():
    text = f"x\n{ce.FENCE_BEGIN}\nno end\n"
    assert ce.block_state(text) == "malformed"
    with pytest.raises(ce.ConfigParseError):
        ce.upsert_block(text, BODY)
    with pytest.raises(ce.ConfigParseError):
        ce.remove_block(text)


# --- JSON hooks

def test_hook_groups_are_tagged_and_foreign_groups_survive():
    foreign = {"matcher": "Bash", "hooks": [{"type": "command", "command": "other"}]}
    doc = {"hooks": {"PreToolUse": [foreign], "Stop": [foreign]}}
    commands = ce.hook_commands("notes")
    assert commands["Stop"] == "mf hook stop --field notes"
    assert ce.hook_state(doc, commands) == "absent"
    assert ce.upsert_hook_groups(doc, commands) is True
    assert ce.upsert_hook_groups(doc, commands) is False
    assert ce.hook_state(doc, commands) == "installed"
    assert doc["hooks"]["Stop"][0] is foreign
    assert doc["hooks"]["Stop"][1][ce.TAG_KEY] == "mf"
    assert doc["hooks"]["SessionEnd"][0]["hooks"][0]["command"] == "mf hook session-end --field notes"
    # A changed field rewrites our group only.
    assert ce.upsert_hook_groups(doc, ce.hook_commands(".")) is True
    assert doc["hooks"]["Stop"][1]["hooks"][0]["command"] == "mf hook stop"
    assert ce.hook_state(doc, commands) == "unmanaged"
    assert ce.remove_hook_groups(doc) is True
    assert doc == {"hooks": {"PreToolUse": [foreign], "Stop": [foreign]}}
    assert ce.remove_hook_groups(doc) is False
    empty = {"hooks": {}}
    ce.upsert_hook_groups(empty, commands)
    ce.remove_hook_groups(empty)
    assert empty == {}


def test_load_json_refuses_jsonc_and_non_objects():
    assert ce.load_json("") == {}
    assert ce.load_json("  \n") == {}
    with pytest.raises(ce.ConfigParseError, match="not valid JSON"):
        ce.load_json('{\n  // comment\n  "mcp": {}\n}')
    with pytest.raises(ce.ConfigParseError, match="not a JSON object"):
        ce.load_json("[]")
    assert ce.dump_json({"a": 1}).endswith("}\n")


# --- MCP entries

def test_mcp_server_entry_shapes_and_ownership():
    assert ce.mcp_entry("mcp_servers", "notes") == {"command": "mf", "args": ["mcp", "--field", "notes"]}
    assert ce.mcp_entry("mcp_servers", ".") == {"command": "mf", "args": ["mcp"]}
    assert ce.mcp_entry("opencode", "notes") == {"type": "local", "command": ["mf", "mcp", "--field", "notes"]}
    doc = {"mcpServers": {"other": {"command": "node"}}}
    entry = ce.mcp_entry("mcp_servers", "notes")
    assert ce.mcp_state(doc, "mcpServers", entry) == "absent"
    assert ce.upsert_mcp_server(doc, "mcpServers", entry) is True
    assert ce.upsert_mcp_server(doc, "mcpServers", entry) is False
    assert ce.mcp_state(doc, "mcpServers", entry) == "installed"
    assert ce.remove_mcp_server(doc, "mcpServers") is True
    assert doc == {"mcpServers": {"other": {"command": "node"}}}
    # An `mf` key someone else wrote is not ours to delete.
    doc = {"mcpServers": {"mf": {"command": "node", "args": ["mf.js"]}}}
    assert ce.mcp_state(doc, "mcpServers", entry) == "unmanaged"
    assert ce.remove_mcp_server(doc, "mcpServers") is False
    assert doc["mcpServers"]["mf"]["command"] == "node"
    oc = {}
    ce.upsert_mcp_server(oc, "mcp", ce.mcp_entry("opencode", "notes"))
    assert ce.remove_mcp_server(oc, "mcp") is True
    assert oc == {}


# --- Codex TOML

def test_codex_toml_append_unchanged_conflict_remove():
    text = '[model]\nname = "x"\n\n[mcp_servers.other]\ncommand = "node"\n'
    assert ce.codex_toml_state(text, "notes") == "absent"
    out = ce.codex_toml_upsert(text, "notes")
    assert out.endswith('\n\n[mcp_servers.mf]\ncommand = "mf"\nargs = ["mcp", "--field", "notes"]\n')
    assert ce.codex_toml_state(out, "notes") == "installed"
    assert ce.codex_toml_upsert(out, "notes") == out
    assert ce.codex_toml_state(out, ".") == "unmanaged"
    with pytest.raises(ce.ConfigParseError, match="different content"):
        ce.codex_toml_upsert(out, ".")
    assert ce.codex_toml_remove(out) == text
    assert ce.codex_toml_upsert("", ".") == '[mcp_servers.mf]\ncommand = "mf"\nargs = ["mcp"]\n'
    assert ce.codex_toml_remove(ce.codex_toml_upsert("", ".")) == ""
    # Table in the middle of the file: everything after it survives.
    middle = ce.codex_toml_upsert("", "notes") + '\n[mcp_servers.z]\ncommand = "z"\n'
    assert ce.codex_toml_remove(middle) == '[mcp_servers.z]\ncommand = "z"\n'
    foreign = '[mcp_servers.mf]\ncommand = "node"\n'
    assert ce.codex_toml_remove(foreign) == foreign
    with pytest.raises(ce.ConfigParseError, match="not valid TOML"):
        ce.codex_toml_upsert("[broken\n", "notes")


# --- .gitignore

def test_gitignore_idempotent_and_respects_user_patterns():
    out = ce.upsert_gitignore("")
    assert out == ce.GITIGNORE_COMMENT + "\nmf.sqlite3\nmf.sqlite3-*\n"
    assert ce.upsert_gitignore(out) == out
    user = "*.log\nmf.sqlite3\nmf.sqlite3-*\n"
    assert ce.gitignore_state(user) == "installed"
    assert ce.upsert_gitignore(user) == user
    assert ce.remove_gitignore(user) == user
    mixed = ce.upsert_gitignore("*.log\n")
    assert ce.remove_gitignore(mixed) == "*.log\n"
    assert ce.remove_gitignore(out) == ""


# --- disk

def test_atomic_write_replaces_and_leaves_no_temp_file(tmp_path):
    target = tmp_path / "sub" / "settings.json"
    ce.atomic_write(target, ce.dump_json({"a": 1}))
    ce.atomic_write(target, ce.dump_json({"a": 2}))
    assert json.loads(target.read_text()) == {"a": 2}
    assert os.listdir(target.parent) == ["settings.json"]
