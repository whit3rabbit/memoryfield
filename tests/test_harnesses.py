"""The hand-written registry must agree with the vendored agent-config
schema, so an upstream path change fails here instead of writing into
the wrong file."""
import json
from pathlib import Path

from mf import configedit as ce
from mf import harnesses as hz

REPO = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((REPO / "docs" / "upstream" / "agent-config-agents.json").read_text(encoding="utf-8"))
AGENTS = {a["id"]: a for a in SCHEMA["agents"]}


def _local_paths(agent: dict, surface: str) -> set[str]:
    scope = agent["surfaces"].get(surface, {}).get("scopes", {}).get("local")
    if not scope:
        return set()
    out = set()
    for p in scope["config_files"] + scope["directories"]:
        out.add(p.replace("<project>/", "").replace("placeholder", "mf").replace("PLACEHOLDER", "mf"))
    return out


def test_menu_order_is_the_ten_supported_ids():
    assert hz.MENU_ORDER == ("claude", "codex", "cursor", "copilot", "opencode",
                             "gemini", "antigravity", "windsurf", "amp", "pi")
    assert set(hz.HARNESSES) == set(hz.MENU_ORDER)


def test_registry_and_not_yet_cover_the_schema_exactly():
    not_yet = {i for i, _ in hz.NOT_YET}
    assert not_yet.isdisjoint(hz.MENU_ORDER)
    assert set(hz.MENU_ORDER) | not_yet == set(AGENTS)
    for i, name in hz.NOT_YET:
        assert AGENTS[i]["display_name"] == name


def test_every_registry_path_exists_in_the_schema():
    for h in hz.HARNESSES.values():
        agent = AGENTS[h.id]
        assert agent["display_name"] == h.name
        if h.instructions:
            # Prompt rules live on the hook surface in the schema; standalone
            # rules files live on the instruction surface.
            assert h.instructions in _local_paths(agent, "hook") | _local_paths(agent, "instruction"), h.id
        if h.skill_path:
            assert h.skill_path in _local_paths(agent, "skill"), h.id
        if h.mcp_file:
            assert h.mcp_file in _local_paths(agent, "mcp"), h.id
        if h.hooks_file:
            assert h.hooks_file in _local_paths(agent, "hook"), h.id


def test_marker_conventions_match_upstream():
    conv = SCHEMA["marker_conventions"]
    assert conv["json_tag_field"] == ce.TAG_KEY
    assert conv["markdown_fence"]["begin"].replace("<NAME>", ce.TAG) == ce.FENCE_BEGIN
    assert conv["markdown_fence"]["end"].replace("<NAME>", ce.TAG) == ce.FENCE_END


def test_supports_and_detect(tmp_path):
    assert hz.HARNESSES["claude"].supports("hooks")
    assert not hz.HARNESSES["codex"].supports("hooks")
    assert not hz.HARNESSES["cursor"].supports("instructions")
    assert hz.detect(tmp_path) == []
    (tmp_path / ".claude").mkdir()
    (tmp_path / "AGENTS.md").write_text("x")
    (tmp_path / ".pi").mkdir()
    assert hz.detect(tmp_path) == ["claude", "codex", "pi"]
