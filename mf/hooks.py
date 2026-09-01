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
again every turn.
"""
from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .db import DB_FILENAME
from .raw import RAW_DIRNAME, RawAddResult

_CAPTURE_RE = re.compile(r"\bmf (write|raw add|hook session-end)\b")

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


def _field_from(payload: dict) -> Path | None:
    cwd = payload.get("cwd")
    if not cwd:
        return None
    field = Path(cwd)
    return field if (field / DB_FILENAME).exists() else None


def _marker(session_id: str) -> Path:
    return Path(tempfile.gettempdir()) / f"mf-stop-{session_id}"


def _transcript_shows_capture(payload: dict) -> bool:
    text = payload.get("last_assistant_message") or ""
    if _CAPTURE_RE.search(text):
        return True
    path = payload.get("transcript_path")
    if not path:
        return False
    try:
        with Path(path).expanduser().open("r", encoding="utf-8", errors="replace") as f:
            return any(_CAPTURE_RE.search(line) for line in f)
    except OSError:
        return False


def stop(payload: dict) -> HookResult:
    """Decide whether to ask the agent to capture before it stops."""
    if payload.get("stop_hook_active"):
        return HookResult(False, note="already continuing from a stop hook")
    field = _field_from(payload)
    if field is None:
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
            "additionalContext": STOP_GUIDANCE.format(field=field),
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


def session_end(payload: dict) -> RawAddResult | None:
    """Append a pointer entry to raw/. None if cwd isn't a field."""
    field = _field_from(payload)
    if field is None:
        return None
    raw_dir = field / RAW_DIRNAME
    raw_dir.mkdir(exist_ok=True)
    session_id = str(payload.get("session_id") or "")
    needle = f"session_id: {session_id}\n"
    # Dedupe on session id across the last few entries (a retried hook,
    # or `resume` then `other` for one session), not on text prefix.
    for entry in sorted(raw_dir.glob("*-session.md"))[-5:]:
        if session_id and needle in entry.read_text(encoding="utf-8"):
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
