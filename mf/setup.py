"""`mf setup`: wire mf into a project's coding-agent harness(es).

Plans a set of file edits from a `SetupChoices` (which harnesses,
which surfaces, where the field is), then applies them. The plan is
keyed by root-relative path, so three harnesses that all read
`AGENTS.md` produce one edit whose `harnesses` list names all three.
Every action is idempotent: a second run reports `unchanged` for each
file. Uninstall removes only what install wrote (the fenced block, the
tagged hook groups, the `mf` MCP entry when its command is `mf`, the
`mf` skill dir, the managed .gitignore lines) and leaves everything
else in the file as it was.

A file this module cannot parse is reported as `skip` with the reason
and never rewritten; `SetupResult.failed` is then true, and the CLI
exits 1 so a script notices. No prompts here: the wizard in
`mf/wizard.py` builds the choices and calls `install`.
"""
from __future__ import annotations

import importlib.util
import textwrap
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field as dc_field
from importlib import resources
from pathlib import Path
from typing import Literal

from . import configedit as ce
from . import harnesses as hz
from .db import DB_FILENAME

SKILL_FILES = ("SKILL.md", "reference.md")
Mode = Literal["install", "uninstall"]
Action = Literal["create", "patch", "unchanged", "remove", "skip"]
StatusState = Literal["installed", "absent", "unmanaged", "malformed", "unsupported"]

INSTRUCTION_LINES = (
    "Before exploring this codebase, run `mf search \"<question>\"{flag}`.",
    "Before finishing, write what you learned as a page with `mf write <draft>{flag}`, "
    "or stage it with `mf raw add{flag}`.",
)

# One paragraph; `seeding_prompt` wraps it, so the placeholders can be
# any length without leaving ragged lines.
SEEDING_PROMPT = (
    "Read {reference}, then explore this repo and seed the memoryfield in "
    "{where}. Write one page per question a new contributor would ask on "
    "day one: how to run the tests, how to run it locally, how a release or "
    "deploy happens, where config lives, and every gotcha you find in "
    "comments, CI config, or recent commits. Draft each page {outside} and "
    "add it with `mf write <draft>{flag}`. If write exits 2, update the "
    "page it names instead of forcing. Run `mf lint{flag}` when you are "
    "done and fix what it reports."
)


@dataclass
class SetupChoices:
    root: Path
    field: str
    harnesses: list[str]
    instructions: bool = True
    skill: bool = True
    mcp: bool = False
    hooks: bool = False

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        unknown = [h for h in self.harnesses if h not in hz.HARNESSES]
        if unknown:
            raise ValueError(f"unsupported harness: {', '.join(unknown)}")
        field_dir = (self.root / self.field).resolve()
        if field_dir != self.root and self.root not in field_dir.parents:
            raise ValueError(f"field {self.field!r} is outside the project root {self.root}")
        self.field = "." if field_dir == self.root else field_dir.relative_to(self.root).as_posix()


@dataclass
class FileAction:
    path: str
    surface: str
    harnesses: list[str]
    action: Action
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "path": self.path, "surface": self.surface, "harnesses": list(self.harnesses),
            "action": self.action, "note": self.note,
        }


@dataclass
class SetupResult:
    mode: Mode
    dry_run: bool
    root: str
    field: str
    actions: list[FileAction] = dc_field(default_factory=list)
    warnings: list[str] = dc_field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(a.action == "skip" for a in self.actions)

    def as_dict(self) -> dict:
        return {
            "mode": self.mode, "dry_run": self.dry_run, "root": self.root, "field": self.field,
            "actions": [a.as_dict() for a in self.actions], "warnings": list(self.warnings),
            "failed": self.failed,
        }


@dataclass
class StatusEntry:
    harness: str
    surface: str
    path: str | None
    state: StatusState

    def as_dict(self) -> dict:
        return {"harness": self.harness, "surface": self.surface, "path": self.path, "state": self.state}


@dataclass
class StatusResult:
    root: str
    field: str
    field_initialized: bool
    entries: list[StatusEntry] = dc_field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "root": self.root, "field": self.field, "field_initialized": self.field_initialized,
            "entries": [e.as_dict() for e in self.entries],
        }


def instruction_body(field: str) -> str:
    # A field at the project root or default notes/ needs no flag: `--field` defaults to cwd or ./notes.
    flag = "" if field in (".", "notes") else f" --field {field}"
    return "\n".join(line.format(flag=flag) for line in INSTRUCTION_LINES)


def seeding_prompt(field: str, reference_path: str | None = None) -> str:
    ref = reference_path or f"{hz.HARNESSES['claude'].skill_path}/reference.md"
    if field == ".":
        # The project root is the field: no `--field`, and "outside the
        # field" means a temp dir, not "outside the repo".
        text = SEEDING_PROMPT.format(
            reference=ref, where="the repo root (pages sit beside the code)",
            outside="in a temp directory", flag="",
        )
    elif field == "notes":
        text = SEEDING_PROMPT.format(
            reference=ref, where="notes/", outside="outside notes/", flag="",
        )
    else:
        text = SEEDING_PROMPT.format(
            reference=ref, where=f"{field}/", outside=f"outside {field}/", flag=f" --field {field}",
        )
    return textwrap.fill(text, width=72) + "\n"


def mcp_extra_installed() -> bool:
    return importlib.util.find_spec("mcp") is not None


def skill_template(name: str) -> str:
    return resources.files("mf").joinpath("templates", "skill", name).read_text(encoding="utf-8")


def _skill_is_ours(text: str) -> bool:
    return text.startswith(f"---\nname: {hz.SKILL_NAME}\n")


# --- planning --------------------------------------------------------------

@dataclass
class _Edit:
    path: str
    surface: str
    harnesses: list[str]
    action: Action
    new_text: str | None = None      # None for unchanged/skip/remove
    note: str = ""


def _plan_text_edit(
    edits: dict[str, _Edit], root: Path, rel: str, surface: str, harness: str,
    transform, *, mode: Mode,
) -> None:
    """Register one file edit; a second harness mapping to the same path
    only adds its name. `transform(old_text) -> new_text` may raise
    ConfigParseError, which becomes a skip."""
    if rel in edits:
        if harness not in edits[rel].harnesses:
            edits[rel].harnesses.append(harness)
        return
    path = root / rel
    old = ce.read_text(path)
    exists = path.exists()
    try:
        new = transform(old)
    except ce.ConfigParseError as e:
        edits[rel] = _Edit(rel, surface, [harness], "skip", note=str(e))
        return
    if mode == "uninstall" and exists and not new.strip():
        edits[rel] = _Edit(rel, surface, [harness], "remove")
    elif new == old and (exists or not new):
        edits[rel] = _Edit(rel, surface, [harness], "unchanged")
    else:
        edits[rel] = _Edit(rel, surface, [harness], "patch" if exists else "create", new_text=new)


def _json_transform(mutate):
    """Wrap a `mutate(doc) -> changed` into a text transform. The
    document is re-serialized only when something changed, so a file
    with its own formatting is left byte-identical on a no-op."""
    def transform(old: str) -> str:
        doc = ce.load_json(old)
        changed = mutate(doc)
        if not changed:
            return old
        return ce.dump_json(doc) if doc else ""
    return transform


Transform = Callable[[str], str]


def _instructions_transform(install: bool, body: str) -> Transform:
    if install:
        return lambda old: ce.upsert_block(old, body)
    return ce.remove_block


def _mcp_transform(install: bool, fmt: hz.McpFormat, fld: str) -> Transform:
    if fmt == "codex_toml":
        if install:
            return lambda old: ce.codex_toml_upsert(old, fld)
        return ce.codex_toml_remove
    key = ce.mcp_key(fmt)
    if install:
        entry = ce.mcp_entry(fmt, fld)
        return _json_transform(lambda doc: ce.upsert_mcp_server(doc, key, entry))
    return _json_transform(lambda doc: ce.remove_mcp_server(doc, key))


def _hooks_transform(install: bool, fld: str) -> Transform:
    if install:
        commands = ce.hook_commands(fld)
        return _json_transform(lambda doc: ce.upsert_hook_groups(doc, commands))
    return _json_transform(ce.remove_hook_groups)


def _plan(choices: SetupChoices, mode: Mode) -> tuple[dict[str, _Edit], list[str]]:
    root = choices.root
    edits: dict[str, _Edit] = {}
    warnings: list[str] = []
    fld = choices.field
    body = instruction_body(fld)
    install = mode == "install"

    for hid in choices.harnesses:
        h = hz.HARNESSES[hid]
        if choices.instructions and h.instructions:
            _plan_text_edit(
                edits, root, h.instructions, "instructions", hid,
                _instructions_transform(install, body), mode=mode,
            )

        if choices.skill and h.skill_path:
            for name in SKILL_FILES:
                rel = f"{h.skill_path}/{name}"
                _plan_skill_file(edits, root, rel, h.skill_path, hid, name, mode)

        if choices.mcp and h.mcp_file:
            _plan_text_edit(
                edits, root, h.mcp_file, "mcp", hid,
                _mcp_transform(install, h.mcp_format, fld), mode=mode,
            )

        if choices.hooks and h.hooks_file:
            _plan_text_edit(
                edits, root, h.hooks_file, "hooks", hid,
                _hooks_transform(install, fld), mode=mode,
            )

    if choices.mcp and install and any(hz.HARNESSES[h].mcp_file for h in choices.harnesses):
        if not mcp_extra_installed():
            warnings.append(
                "the MCP entry runs `mf mcp`, but the mcp package is not importable here; "
                "reinstall with `uv tool install --force memoryfield`"
            )

    gi_rel = ".gitignore" if fld == "." else f"{fld}/.gitignore"
    _plan_text_edit(
        edits, root, gi_rel, "gitignore", "field",
        ce.upsert_gitignore if install else ce.remove_gitignore, mode=mode,
    )
    return edits, warnings


def _plan_skill_file(
    edits: dict[str, _Edit], root: Path, rel: str, skill_dir: str, hid: str, name: str, mode: Mode,
) -> None:
    if rel in edits:
        if hid not in edits[rel].harnesses:
            edits[rel].harnesses.append(hid)
        return
    marker = root / skill_dir / "SKILL.md"
    marker_text = ce.read_text(marker)
    if marker.exists() and not _skill_is_ours(marker_text):
        edits[rel] = _Edit(rel, "skill", [hid], "skip", note=f"{skill_dir}/SKILL.md is not mf's skill; not touched")
        return
    path = root / rel
    old = ce.read_text(path)
    if mode == "install":
        new = skill_template(name)
        if path.exists() and old == new:
            edits[rel] = _Edit(rel, "skill", [hid], "unchanged")
        else:
            edits[rel] = _Edit(rel, "skill", [hid], "patch" if path.exists() else "create", new_text=new)
    else:
        edits[rel] = _Edit(rel, "skill", [hid], "remove" if path.exists() else "unchanged")


def _apply(root: Path, edits: dict[str, _Edit]) -> None:
    for e in edits.values():
        path = root / e.path
        if e.action in ("create", "patch"):
            assert e.new_text is not None
            ce.atomic_write(path, e.new_text)
        elif e.action == "remove":
            path.unlink(missing_ok=True)
            parent = path.parent
            # A skill dir emptied by uninstall goes too; anything else stays.
            if parent != root and parent.name == hz.SKILL_NAME and parent.exists() and not any(parent.iterdir()):
                parent.rmdir()


def _run(choices: SetupChoices, mode: Mode, dry_run: bool) -> SetupResult:
    edits, warnings = _plan(choices, mode)
    result = SetupResult(mode=mode, dry_run=dry_run, root=str(choices.root), field=choices.field, warnings=warnings)
    result.actions = [FileAction(e.path, e.surface, list(e.harnesses), e.action, e.note) for e in edits.values()]
    if not dry_run:
        _apply(choices.root, edits)
    return result


def install(choices: SetupChoices, *, dry_run: bool = False) -> SetupResult:
    return _run(choices, "install", dry_run)


def uninstall(choices: SetupChoices, *, dry_run: bool = False) -> SetupResult:
    return _run(choices, "uninstall", dry_run)


# --- status ----------------------------------------------------------------

def _state_of(root: Path, h: hz.Harness, surface: str, fld: str) -> tuple[str | None, StatusState]:
    if not h.supports(surface):  # type: ignore[arg-type]
        return None, "unsupported"
    try:
        if surface == "instructions":
            assert h.instructions
            return h.instructions, _norm(ce.block_state(ce.read_text(root / h.instructions)))
        if surface == "skill":
            assert h.skill_path
            marker = root / h.skill_path / "SKILL.md"
            if not marker.exists():
                return h.skill_path, "absent"
            text = marker.read_text(encoding="utf-8")
            if not _skill_is_ours(text):
                return h.skill_path, "unmanaged"
            current = all(
                ce.read_text(root / h.skill_path / n) == skill_template(n) for n in SKILL_FILES
            )
            return h.skill_path, "installed" if current else "unmanaged"
        if surface == "mcp":
            assert h.mcp_file
            text = ce.read_text(root / h.mcp_file)
            if h.mcp_format == "codex_toml":
                return h.mcp_file, _norm(ce.codex_toml_state(text, fld))
            doc = ce.load_json(text)
            return h.mcp_file, _norm(ce.mcp_state(doc, ce.mcp_key(h.mcp_format), ce.mcp_entry(h.mcp_format, fld)))
        assert h.hooks_file
        doc = ce.load_json(ce.read_text(root / h.hooks_file))
        return h.hooks_file, _norm(ce.hook_state(doc, ce.hook_commands(fld)))
    except ce.ConfigParseError:
        return {"instructions": h.instructions, "skill": h.skill_path, "mcp": h.mcp_file, "hooks": h.hooks_file}[surface], "malformed"


def _norm(state: ce.State) -> StatusState:
    return state  # the two literal sets overlap on every value configedit emits


def status(root: Path, field: str, harnesses: list[str] | None = None) -> StatusResult:
    choices = SetupChoices(root=root, field=field, harnesses=list(harnesses or hz.MENU_ORDER))
    root = choices.root
    fld = choices.field
    result = StatusResult(root=str(root), field=fld, field_initialized=(root / fld / DB_FILENAME).exists())
    for hid in choices.harnesses:
        h = hz.HARNESSES[hid]
        for surface in hz.SURFACES:
            path, state = _state_of(root, h, surface, fld)
            result.entries.append(StatusEntry(hid, surface, path, state))
    gi = ".gitignore" if fld == "." else f"{fld}/.gitignore"
    result.entries.append(StatusEntry("field", "gitignore", gi, _norm(ce.gitignore_state(ce.read_text(root / gi)))))
    return result


# --- rendering -------------------------------------------------------------

_VERB = {"create": "create   ", "patch": "patch    ", "unchanged": "unchanged", "remove": "remove   ", "skip": "SKIP     "}


def render_setup_text(result: SetupResult) -> str:
    head = f"{'Would ' if result.dry_run else ''}{result.mode} for field {result.field} under {result.root}"
    lines = [head[0].upper() + head[1:]]
    for a in result.actions:
        who = ", ".join(a.harnesses)
        line = f"  {_VERB[a.action]} {a.path}  ({a.surface}: {who})"
        if a.note:
            line += f"\n             {a.note}"
        lines.append(line)
    for w in result.warnings:
        lines.append(f"warning: {w}")
    if result.failed:
        lines.append("Some files were skipped; fix them by hand and rerun.")
    return "\n".join(lines)


def render_status_text(result: StatusResult) -> str:
    lines = [
        f"Field {result.field} under {result.root}: "
        f"{'initialized' if result.field_initialized else 'not initialized (run mf init)'}"
    ]
    by_harness: dict[str, list[StatusEntry]] = {}
    for e in result.entries:
        by_harness.setdefault(e.harness, []).append(e)
    for hid, entries in by_harness.items():
        name = hz.HARNESSES[hid].name if hid in hz.HARNESSES else hid
        lines.append(f"{name}")
        for e in entries:
            where = f"  {e.path}" if e.path else ""
            lines.append(f"  {e.surface:<13}{e.state:<12}{where}")
    return "\n".join(lines)
