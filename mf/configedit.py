"""Idempotent edits to the files a coding-agent harness reads: a fenced
block in a Markdown instruction file, tagged hook groups and an `mf`
MCP entry in a JSON config, a `[mcp_servers.mf]` table in Codex's
TOML, and the field's `.gitignore`. Pure text-in, text-out, so `mf
setup` can plan without touching disk and the tests need no fixtures.

Marker conventions are agent-config's (whit3rabbit/agent-config,
schema/agents.json `marker_conventions`), so anything written here is
recognizable to that crate: the Markdown fence is
`<!-- BEGIN AGENT-CONFIG:mf -->` and JSON hook groups carry
`"_agent_config_tag": "mf"`. MCP entries and skill dirs are owned by
name (`mf`) plus a content check, no ledger files.

Nothing here writes a `.bak`: the project is expected to be under git.
Nothing here rewrites a file it cannot parse, either. `load_json`
raises `ConfigParseError` and the caller reports the file as skipped
(a JSONC `opencode.json` lands there), because stripping comments to
force a parse would destroy what the user wrote.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Literal

TAG = "mf"
TAG_KEY = "_agent_config_tag"
FENCE_BEGIN = f"<!-- BEGIN AGENT-CONFIG:{TAG} -->"
FENCE_END = f"<!-- END AGENT-CONFIG:{TAG} -->"
MCP_SERVER_NAME = "mf"
GITIGNORE_COMMENT = "# mf: pages are committed, the index is derived (managed by mf setup)"
GITIGNORE_LINES = ("mf.sqlite3", "mf.sqlite3-*")

State = Literal["absent", "installed", "unmanaged", "malformed"]


class ConfigParseError(ValueError):
    """A config file exists but cannot be parsed, so it is not edited."""


# --- Markdown fenced block -------------------------------------------------

_BLOCK_RE = re.compile(
    re.escape(FENCE_BEGIN) + r"\n.*?" + re.escape(FENCE_END) + r"\n?",
    re.DOTALL,
)


def render_block(body: str) -> str:
    return f"{FENCE_BEGIN}\n{body.rstrip()}\n{FENCE_END}\n"


def block_state(text: str) -> State:
    begins = text.count(FENCE_BEGIN)
    ends = text.count(FENCE_END)
    if begins == 0 and ends == 0:
        return "absent"
    if begins != 1 or ends != 1:
        return "malformed"
    m = _BLOCK_RE.search(text)
    if m is None:
        return "malformed"
    return "installed"


def upsert_block(text: str, body: str) -> str:
    """Replace the fenced block in place, or append it after one blank
    line. Raises ConfigParseError on a malformed fence."""
    state = block_state(text)
    if state == "malformed":
        raise ConfigParseError("managed block fence is malformed (unbalanced BEGIN/END)")
    block = render_block(body)
    if state == "installed":
        return _BLOCK_RE.sub(lambda _m: block, text, count=1)
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def remove_block(text: str) -> str:
    if block_state(text) == "malformed":
        raise ConfigParseError("managed block fence is malformed (unbalanced BEGIN/END)")
    out = _BLOCK_RE.sub("", text, count=1)
    # Drop the blank line upsert added, but keep the user's own spacing.
    return re.sub(r"\n{3,}\Z", "\n\n", out).rstrip("\n") + "\n" if out.strip() else ""


# --- JSON documents --------------------------------------------------------

def load_json(text: str, *, what: str = "config") -> dict:
    if not text.strip():
        return {}
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as e:
        raise ConfigParseError(f"{what} is not valid JSON ({e.msg} at line {e.lineno})") from e
    if not isinstance(doc, dict):
        raise ConfigParseError(f"{what} is not a JSON object")
    return doc


def dump_json(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def hook_commands(field: str) -> dict[str, str]:
    suffix = "" if field in (".", "") else f" --field {field}"
    return {"Stop": f"mf hook stop{suffix}", "SessionEnd": f"mf hook session-end{suffix}"}


def _hook_group(command: str) -> dict:
    return {"hooks": [{"type": "command", "command": command}], TAG_KEY: TAG}


def _is_ours(group: object) -> bool:
    return isinstance(group, dict) and group.get(TAG_KEY) == TAG


def hook_state(doc: dict, commands: dict[str, str]) -> State:
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return "absent"
    found = 0
    for event, command in commands.items():
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        ours = [g for g in groups if _is_ours(g)]
        if not ours:
            continue
        found += 1
        if len(ours) != 1 or ours[0] != _hook_group(command):
            return "unmanaged"
    if found == 0:
        return "absent"
    return "installed" if found == len(commands) else "unmanaged"


def upsert_hook_groups(doc: dict, commands: dict[str, str]) -> bool:
    """One tagged group per event, foreign groups untouched. Returns
    whether anything changed."""
    hooks = doc.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ConfigParseError('"hooks" is not an object')
    changed = False
    for event, command in commands.items():
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ConfigParseError(f'"hooks.{event}" is not an array')
        want = _hook_group(command)
        kept = [g for g in groups if not _is_ours(g)]
        ours = [g for g in groups if _is_ours(g)]
        if ours == [want]:
            continue
        hooks[event] = [*kept, want]
        changed = True
    return changed


def remove_hook_groups(doc: dict) -> bool:
    hooks = doc.get("hooks")
    if not isinstance(hooks, dict):
        return False
    changed = False
    for event in list(hooks):
        groups = hooks[event]
        if not isinstance(groups, list):
            continue
        kept = [g for g in groups if not _is_ours(g)]
        if len(kept) != len(groups):
            changed = True
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
    if not hooks:
        del doc["hooks"]
    return changed


McpFormat = Literal["mcp_servers", "opencode", "codex_toml"]


def mcp_args(field: str) -> list[str]:
    return ["mcp"] if field in (".", "") else ["mcp", "--field", field]


def mcp_entry(fmt: McpFormat, field: str) -> dict:
    args = mcp_args(field)
    if fmt == "opencode":
        return {"type": "local", "command": ["mf", *args]}
    return {"command": "mf", "args": args}


def mcp_key(fmt: McpFormat) -> str:
    return "mcp" if fmt == "opencode" else "mcpServers"


def _mcp_entry_is_ours(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    command = entry.get("command")
    if isinstance(command, list):
        return bool(command) and command[0] == "mf"
    return command == "mf"


def mcp_state(doc: dict, key: str, entry: dict) -> State:
    servers = doc.get(key)
    if not isinstance(servers, dict) or MCP_SERVER_NAME not in servers:
        return "absent"
    current = servers[MCP_SERVER_NAME]
    if current == entry:
        return "installed"
    return "unmanaged"


def upsert_mcp_server(doc: dict, key: str, entry: dict) -> bool:
    servers = doc.setdefault(key, {})
    if not isinstance(servers, dict):
        raise ConfigParseError(f'"{key}" is not an object')
    if servers.get(MCP_SERVER_NAME) == entry:
        return False
    servers[MCP_SERVER_NAME] = entry
    return True


def remove_mcp_server(doc: dict, key: str) -> bool:
    """Remove the `mf` entry only when it is ours (its command is `mf`)."""
    servers = doc.get(key)
    if not isinstance(servers, dict) or not _mcp_entry_is_ours(servers.get(MCP_SERVER_NAME)):
        return False
    del servers[MCP_SERVER_NAME]
    if not servers:
        del doc[key]
    return True


# --- Codex config.toml -----------------------------------------------------
# tomllib reads; the stdlib has no writer, so the table is appended and
# removed as text. Safe only because the table is ours by name and its
# content is checked through tomllib before anything is removed.

_CODEX_TABLE = f"mcp_servers.{MCP_SERVER_NAME}"
_CODEX_HEADER_RE = re.compile(r"^\[" + re.escape(_CODEX_TABLE) + r"\]\s*$", re.MULTILINE)
_TOML_HEADER_RE = re.compile(r"^\[", re.MULTILINE)


def codex_toml_entry(field: str) -> dict:
    return {"command": "mf", "args": mcp_args(field)}


def render_codex_table(field: str) -> str:
    args = ", ".join(json.dumps(a) for a in mcp_args(field))
    return f"[{_CODEX_TABLE}]\ncommand = \"mf\"\nargs = [{args}]\n"


def _codex_current(text: str) -> dict | None:
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigParseError(f"config.toml is not valid TOML ({e})") from e
    servers = doc.get("mcp_servers")
    if not isinstance(servers, dict):
        return None
    entry = servers.get(MCP_SERVER_NAME)
    return entry if isinstance(entry, dict) else None


def codex_toml_state(text: str, field: str) -> State:
    current = _codex_current(text)
    if current is None:
        return "absent"
    return "installed" if current == codex_toml_entry(field) else "unmanaged"


def codex_toml_upsert(text: str, field: str) -> str:
    state = codex_toml_state(text, field)
    if state == "installed":
        return text
    if state == "unmanaged":
        raise ConfigParseError(f"[{_CODEX_TABLE}] exists with different content; edit it by hand")
    table = render_codex_table(field)
    if not text.strip():
        return table
    return text.rstrip("\n") + "\n\n" + table


def codex_toml_remove(text: str) -> str:
    current = _codex_current(text)
    if current is None or current.get("command") != "mf":
        return text
    m = _CODEX_HEADER_RE.search(text)
    if m is None:
        return text
    nxt = _TOML_HEADER_RE.search(text, m.end())
    end = nxt.start() if nxt else len(text)
    out = text[: m.start()] + text[end:]
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.rstrip("\n") + "\n" if out.strip() else ""


# --- .gitignore ------------------------------------------------------------

def _gitignore_patterns(text: str) -> set[str]:
    return {line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")}


def gitignore_state(text: str) -> State:
    if GITIGNORE_COMMENT in text:
        return "installed"
    if set(GITIGNORE_LINES) <= _gitignore_patterns(text):
        return "installed"
    return "absent"


def upsert_gitignore(text: str) -> str:
    if gitignore_state(text) == "installed":
        return text
    block = GITIGNORE_COMMENT + "\n" + "\n".join(GITIGNORE_LINES) + "\n"
    if not text.strip():
        return block
    return text.rstrip("\n") + "\n\n" + block


def remove_gitignore(text: str) -> str:
    """Remove the managed comment and the two lines directly under it.
    Patterns the user wrote themselves stay."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].rstrip("\n") == GITIGNORE_COMMENT:
            i += 1
            while i < len(lines) and lines[i].strip() in GITIGNORE_LINES:
                i += 1
            continue
        out.append(lines[i])
        i += 1
    joined = "".join(out)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined.rstrip("\n") + "\n" if joined.strip() else ""


# --- disk ------------------------------------------------------------------

def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def atomic_write(path: Path, text: str) -> None:
    """Write via a sibling temp file and os.replace, so a crash leaves
    either the old file or the new one, never a torn one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
