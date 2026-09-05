"""`mf hook stop` / `mf hook session-end` -- Claude Code hook handlers
(ROADMAP.md 3.1). Each reads the hook's JSON payload from stdin, so the
settings entry is just `"command": "mf hook stop"`; no shell, no jq.

Contract (code.claude.com/docs/en/hooks.md, read 2026-09-01):

  Stop: input has `session_id`, `cwd`, `transcript_path`,
  `stop_hook_active` (true when Claude is already continuing because of
  a stop hook), `last_assistant_message`. Output
  `{"hookSpecificOutput": {"hookEventName": "Stop",
  "additionalContext": "..."}}` keeps the turn going with the text as a
  system reminder ("Stop hook feedback", no error shown); Claude Code
  caps consecutive continuations at 8.

  SessionEnd: input has `session_id`, `cwd`, `transcript_path`,
  `reason` (clear | resume | logout | prompt_input_exit | other). No
  decision control, stdout not shown, and all SessionEnd hooks share a
  1.5-second budget, which is why this handler writes a pointer and
  nothing else.

Why a pointer, not the transcript: PLAN.md section 6 costs
consolidation at ~2K tokens per raw entry; a transcript is 50-200K. The
extract worth keeping has to be written by the agent while its context
is hot, which is the Stop hook's job. The SessionEnd pointer is the
fallback that records where the transcript lives.

The Stop guidance fires once per session: `stop_hook_active` covers the
continuation turn, and a marker file under the temp dir covers later
turns, so an agent that decides there's nothing to keep isn't asked
again every turn. "Already captured" is decided from the transcript's
tool calls, not from prose: the guidance text itself names `mf write`,
and a session that merely discussed the command (a review of this
repo, say) was being counted as one that ran it.

Nothing here raises to the caller. A hook that prints a traceback into
Claude Code is worse than a hook that quietly does nothing, so
`mf/cli.py` catches everything and exits 0 either way.
"""
from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .db import DB_FILENAME
from .raw import RAW_DIRNAME, RawAddResult

_CAPTURE_RE = re.compile(r"(?:^|[;&|(\s])mf (write|raw add|hook session-end)\b")
_FENCED_RE = re.compile(r"`([^`\n]*)`")

STOP_GUIDANCE = (
    "This directory is an mf memoryfield ({field}). Before finishing: if "
    "this session produced a reusable lesson, decision, gotcha, or "
    "working command that a future session would otherwise rediscover, "
    "write it as a page (draft it outside the field, then "
    "`mf write <draft> --field {field}`; the dedup gate will tell you if "
    "it already exists). If it isn't page-shaped yet, pipe an extract of "
    "at most ~2K tokens to `mf raw add --field {field}`. If nothing is "
    "worth keeping, just finish."
)


@dataclass
class HookResult:
    acted: bool
    output: dict | None = None
    note: str = ""

    def as_dict(self) -> dict:
        return {"acted": self.acted, "output": self.output, "note": self.note}


def _field_from(payload: dict, field: str | None = None) -> Path | None:
    """The field a hook payload refers to, or None.

    Claude Code runs hooks with `cwd` set to the project root, not to
    wherever the field lives. A project that keeps its field in a
    subdirectory (this repo's `notes/`) passes `--field notes`, which is
    joined onto the payload's cwd; without it, only a project whose root
    is the field ever fires.
    """
    cwd = payload.get("cwd")
    if not cwd:
        return None
    base = Path(cwd)
    candidate = base / field if field else base
    return candidate if (candidate / DB_FILENAME).exists() else None


def _marker(session_id: str) -> Path:
    # Hashed: the id is external input and used to be interpolated into a
    # path as-is, so `../x` in it pointed the marker outside the temp dir.
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"mf-stop-{digest}"


def _commands_in(obj: object) -> list[str]:
    """Every Bash `command` in one transcript record's tool_use blocks."""
    out: list[str] = []
    message = obj.get("message") if isinstance(obj, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return out
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("name") == "Bash"
            and isinstance(block.get("input"), dict)
        ):
            command = block["input"].get("command")
            if isinstance(command, str):
                out.append(command)
    return out


def _transcript_shows_capture(payload: dict) -> bool:
    text = payload.get("last_assistant_message") or ""
    # Prose mentions don't count; a fenced command the agent just ran does.
    if any(_CAPTURE_RE.search(cmd) for cmd in _FENCED_RE.findall(text)):
        return True
    path = payload.get("transcript_path")
    if not path:
        return False
    try:
        with Path(path).expanduser().open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if "mf " not in line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if any(_CAPTURE_RE.search(cmd) for cmd in _commands_in(record)):
                    return True
    except OSError:
        return False
    return False


def stop(payload: dict, field: str | None = None) -> HookResult:
    """Decide whether to ask the agent to capture before it stops."""
    if payload.get("stop_hook_active"):
        return HookResult(False, note="already continuing from a stop hook")
    field_dir = _field_from(payload, field)
    if field_dir is None:
        return HookResult(False, note="cwd is not a field")
    session_id = str(payload.get("session_id") or "unknown")
    marker = _marker(session_id)
    if marker.exists():
        return HookResult(False, note="already asked this session")
    if _transcript_shows_capture(payload):
        return HookResult(False, note="session already wrote or staged something")
    try:
        marker.touch()
    except OSError:
        pass
    return HookResult(True, output={
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": STOP_GUIDANCE.format(field=field_dir),
        }
    })


def pointer_text(payload: dict, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    lines = [
        "kind: session-pointer",
        f"session_id: {payload.get('session_id', '')}",
        f"transcript_path: {payload.get('transcript_path', '')}",
        f"reason: {payload.get('reason', '')}",
        f"cwd: {payload.get('cwd', '')}",
        f"captured_at: {now.isoformat()}",
    ]
    return "\n".join(lines) + "\n"


def session_end(payload: dict, field: str | None = None) -> RawAddResult | None:
    """Append a pointer entry to raw/. None if cwd isn't a field."""
    field_dir = _field_from(payload, field)
    if field_dir is None:
        return None
    raw_dir = field_dir / RAW_DIRNAME
    raw_dir.mkdir(exist_ok=True)
    session_id = str(payload.get("session_id") or "")
    needle = f"session_id: {session_id}\n"
    # Dedupe on session id across the last few entries (a retried hook,
    # or `resume` then `other` for one session), not on text prefix.
    for entry in sorted(raw_dir.glob("*-session.md"))[-5:]:
        if session_id and needle in entry.read_text(encoding="utf-8", errors="replace"):
            return RawAddResult(written=False, path=entry)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = raw_dir / f"{stamp}-session.md"
    path.write_text(pointer_text(payload), encoding="utf-8")
    return RawAddResult(written=True, path=path)


def read_payload(stream) -> dict:
    data = stream.read()
    if not data.strip():
        return {}
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
