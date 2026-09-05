"""Where each coding-agent harness keeps its project-local config, for
`mf setup`. Ten harnesses in the first cut, in a fixed popularity
order for the menu; the other fifteen ids the upstream schema knows
are listed as `NOT_YET` so the wizard can show them disabled.

Source: whit3rabbit/agent-config v0.4.0, `docs/agents/<id>.md` and
`schema/agents.json` (vendored at docs/upstream/agent-config-agents.json).
`tests/test_harnesses.py` checks every path here against that schema.
Paths are relative to the project root, POSIX form. Global (home
directory) scope is deliberately not modeled.

Why the registry is hand-written rather than read from the schema at
runtime: the schema records paths, not config shapes. Whether an MCP
file wants `mcpServers` JSON, OpenCode's `mcp` key with a command
list, or a Codex TOML table is per-harness knowledge that only the
per-agent docs carry, and that is what each `mcp_format` encodes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Surface = Literal["instructions", "skill", "mcp", "hooks"]
SURFACES: tuple[Surface, ...] = ("instructions", "skill", "mcp", "hooks")
McpFormat = Literal["mcp_servers", "opencode", "codex_toml"]

SKILL_NAME = "mf"


@dataclass(frozen=True)
class Harness:
    id: str
    name: str
    # Instruction file: a fenced block inside a shared file ("block",
    # e.g. CLAUDE.md) or a standalone rules file mf owns outright
    # ("file", e.g. .agents/rules/mf.md). Both carry the fence.
    instructions: str | None
    instructions_kind: Literal["block", "file"]
    skills_dir: str | None          # the skill lands at <skills_dir>/mf/
    mcp_file: str | None
    mcp_format: McpFormat
    hooks_file: str | None          # Claude Code only in this cut
    detect: tuple[str, ...]         # any of these present pre-checks the harness
    note: str = ""                  # shown beside the menu entry

    def supports(self, surface: Surface) -> bool:
        return {
            "instructions": self.instructions,
            "skill": self.skills_dir,
            "mcp": self.mcp_file,
            "hooks": self.hooks_file,
        }[surface] is not None

    @property
    def skill_path(self) -> str | None:
        return f"{self.skills_dir}/{SKILL_NAME}" if self.skills_dir else None


_TOP = (
    Harness(
        id="claude", name="Claude Code",
        instructions="CLAUDE.md", instructions_kind="block",
        skills_dir=".claude/skills", mcp_file=".mcp.json", mcp_format="mcp_servers",
        hooks_file=".claude/settings.json", detect=(".claude",),
    ),
    Harness(
        id="codex", name="Codex CLI",
        instructions="AGENTS.md", instructions_kind="block",
        skills_dir=".agents/skills", mcp_file=".codex/config.toml", mcp_format="codex_toml",
        hooks_file=None, detect=(".codex", "AGENTS.md"),
        note="MCP loads only in a project Codex trusts",
    ),
    Harness(
        id="cursor", name="Cursor",
        instructions=None, instructions_kind="block",
        skills_dir=".cursor/skills", mcp_file=".cursor/mcp.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".cursor",),
        note="no project instruction file upstream; skill and MCP only",
    ),
    Harness(
        id="copilot", name="GitHub Copilot",
        instructions=".github/copilot-instructions.md", instructions_kind="block",
        skills_dir=".github/skills", mcp_file=".mcp.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".github/copilot-instructions.md",),
    ),
    Harness(
        id="opencode", name="OpenCode",
        instructions="AGENTS.md", instructions_kind="block",
        skills_dir=".opencode/skills", mcp_file="opencode.json", mcp_format="opencode",
        hooks_file=None, detect=(".opencode", "opencode.json"),
    ),
    Harness(
        id="gemini", name="Gemini CLI",
        instructions="GEMINI.md", instructions_kind="block",
        skills_dir=".gemini/skills", mcp_file=".gemini/settings.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".gemini",),
        note="consumer tiers ended 2026-06-18; paid API and enterprise remain",
    ),
    Harness(
        id="antigravity", name="Google Antigravity",
        instructions=".agents/rules/mf.md", instructions_kind="file",
        skills_dir=".agents/skills", mcp_file=".agents/mcp_config.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".agents",),
    ),
    Harness(
        id="windsurf", name="Windsurf",
        instructions=".windsurf/rules/mf.md", instructions_kind="file",
        skills_dir=".windsurf/skills", mcp_file=".windsurf/mcp_config.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".windsurf",),
    ),
    Harness(
        id="amp", name="Amp",
        instructions="AGENTS.md", instructions_kind="block",
        skills_dir=".agents/skills", mcp_file=".amp/settings.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".amp",),
    ),
    Harness(
        id="pi", name="Pi",
        instructions="AGENTS.md", instructions_kind="block",
        skills_dir=".pi/skills", mcp_file=".pi/mcp.json", mcp_format="mcp_servers",
        hooks_file=None, detect=(".pi",),
    ),
)

HARNESSES: dict[str, Harness] = {h.id: h for h in _TOP}
MENU_ORDER: tuple[str, ...] = tuple(h.id for h in _TOP)

# Known upstream, not wired yet. Schema order.
NOT_YET: tuple[tuple[str, str], ...] = (
    ("openclaw", "OpenClaw"),
    ("hermes", "Hermes Agent"),
    ("cline", "Cline"),
    ("roo", "Roo Code"),
    ("kilocode", "Kilo Code"),
    ("antigravitycli", "Antigravity CLI"),
    ("codebuddy", "CodeBuddy CLI"),
    ("crush", "Charm Crush"),
    ("forge", "Forge"),
    ("iflow", "iFlow CLI"),
    ("junie", "JetBrains Junie"),
    ("qodercli", "Qoder CLI"),
    ("qwen", "Qwen Code"),
    ("tabnine", "Tabnine CLI"),
    ("trae", "Trae"),
)


def detect(root: Path) -> list[str]:
    """Harness ids, in menu order, whose fingerprint exists under root."""
    return [h.id for h in _TOP if any((root / p).exists() for p in h.detect)]
