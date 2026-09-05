"""The interactive half of `mf init` and `mf setup`: pick harnesses and
surfaces, show the dry-run plan, apply, then print the prompt that
has an agent seed the field.

Prompts go through a `Prompter` so tests drive the flow with scripted
answers and never open a terminal. `QuestionaryPrompter` is the real
one; it imports questionary inside `__init__` because the library
warns on stderr the moment a prompt is built without a TTY, and the
CLI already decided we have one before getting here.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

from . import db, embedder, schema
from . import harnesses as hz
from . import setup as setup_mod
from .db import DB_FILENAME


@dataclass(frozen=True)
class Choice:
    value: str
    label: str
    checked: bool = False
    disabled: str | None = None     # reason text, shown greyed out
    separator: bool = False         # a label-only divider


class Prompter(Protocol):
    def text(self, message: str, default: str) -> str: ...
    def checkbox(self, message: str, choices: list[Choice]) -> list[str]: ...
    def confirm(self, message: str, default: bool) -> bool: ...


class QuestionaryPrompter:
    def __init__(self) -> None:
        import questionary  # lazy: see module docstring

        self._q = questionary

    def text(self, message: str, default: str) -> str:
        return str(self._q.text(message, default=default).unsafe_ask())

    def checkbox(self, message: str, choices: list[Choice]) -> list[str]:
        q = self._q
        items = [
            q.Separator(c.label) if c.separator
            else q.Choice(title=c.label, value=c.value, checked=c.checked, disabled=c.disabled)
            for c in choices
        ]
        return list(q.checkbox(message, choices=items).unsafe_ask() or [])

    def confirm(self, message: str, default: bool) -> bool:
        return bool(self._q.confirm(message, default=default).unsafe_ask())


def harness_choices(root: Path) -> list[Choice]:
    detected = set(hz.detect(root))
    out = []
    for hid in hz.MENU_ORDER:
        h = hz.HARNESSES[hid]
        label = f"{h.name}  ({h.note})" if h.note else h.name
        out.append(Choice(hid, label, checked=hid in detected))
    out.append(Choice("", "not yet supported", separator=True))
    out.extend(Choice(hid, name, disabled="not yet") for hid, name in hz.NOT_YET)
    return out


def surface_choices(selected: list[str]) -> list[Choice]:
    hs = [hz.HARNESSES[h] for h in selected]
    out = []
    if any(h.supports("instructions") for h in hs):
        out.append(Choice("instructions", "instructions: two lines in CLAUDE.md / AGENTS.md / rules", checked=True))
    if any(h.supports("skill") for h in hs):
        out.append(Choice("skill", "skill: the mf skill (SKILL.md + reference.md)", checked=True))
    if any(h.supports("mcp") for h in hs):
        note = "" if setup_mod.mcp_extra_installed() else "  (mcp package missing: reinstall memoryfield)"
        out.append(Choice("mcp", f"mcp: an `mf mcp` server entry{note}", checked=True))
    if any(h.supports("hooks") for h in hs):
        out.append(Choice("hooks", "hooks: Stop and SessionEnd reminders (Claude Code)", checked=True))
    return out


def run_wizard(
    root: Path, prompter: Prompter, *, field: str | None = None,
    model_code: str | None = None, is_init: bool = False,
    out: TextIO | None = None,
) -> int:
    out = out or sys.stdout
    root = root.resolve()
    if field is None:
        field = prompter.text("Field directory (relative to the project root)", "notes").strip() or "notes"
    try:
        probe = setup_mod.SetupChoices(root=root, field=field, harnesses=[])
    except ValueError as e:
        print(f"mf setup: {e}", file=out)
        return 1
    field = probe.field
    field_dir = root / field
    if (field_dir / DB_FILENAME).exists():
        if is_init:
            sys.stderr.write(f"mf init: {field_dir / DB_FILENAME} already exists; nothing to do.\n")
            return 1
    else:
        if not is_init:
            if not prompter.confirm(f"No field at {field}/. Run `mf init {field}`?", True):
                print("Nothing written.", file=out)
                return 1
        model = model_code or schema.DEFAULT_MODEL_CODE
        entry = embedder.registry_entry(model)
        db_path = db.init_field(field_dir, model_code=model, embedding_dim=entry["dim"])
        print(f"Initialized empty field at {db_path} (model {model}, {entry['dim']}-d)", file=out)

    selected = prompter.checkbox("Which coding agents use this project?", harness_choices(root))
    selected = [h for h in hz.MENU_ORDER if h in selected]
    if not selected:
        print("No harness selected. Nothing written.", file=out)
        return 0

    surfaces = set(prompter.checkbox("What should mf set up?", surface_choices(selected)))
    if not surfaces:
        print("No surface selected. Nothing written.", file=out)
        return 0
    choices = setup_mod.SetupChoices(
        root=root, field=field, harnesses=selected,
        instructions="instructions" in surfaces, skill="skill" in surfaces,
        mcp="mcp" in surfaces, hooks="hooks" in surfaces,
    )

    plan = setup_mod.install(choices, dry_run=True)
    print(setup_mod.render_setup_text(plan), file=out)
    if not prompter.confirm("Apply?", True):
        print("Nothing written.", file=out)
        return 0
    result = setup_mod.install(choices)
    print(setup_mod.render_setup_text(result), file=out)

    reference = None
    if choices.skill:
        for hid in selected:
            path = hz.HARNESSES[hid].skill_path
            if path:
                reference = f"{path}/reference.md"
                break
    print(file=out)
    print("Next, paste this into your agent from the project root to seed the field", file=out)
    print("(`mf setup prompt` prints it again):", file=out)
    print(file=out)
    print(setup_mod.seeding_prompt(field, reference), file=out, end="")
    return 1 if result.failed else 0
