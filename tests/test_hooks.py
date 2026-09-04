import io
import json

from mf import cli, db, hooks


def _field(tmp_path):
    field = tmp_path / "field"
    field.mkdir()
    db.init_field(field)
    return field


def _payload(field, **extra):
    base = {"session_id": "sess-1", "cwd": str(field), "transcript_path": str(field.parent / "t.jsonl")}
    base.update(extra)
    return base


def test_stop_asks_once_per_session(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path))
    field = _field(tmp_path)
    r = hooks.stop(_payload(field))
    assert r.acted is True and r.output is not None
    ctx = r.output["hookSpecificOutput"]
    assert ctx["hookEventName"] == "Stop"
    assert "mf write" in ctx["additionalContext"] and str(field) in ctx["additionalContext"]
    # second turn, same session: silent
    assert hooks.stop(_payload(field)).acted is False


def test_stop_is_silent_when_not_a_field_or_already_continuing(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    assert hooks.stop({"session_id": "s", "cwd": str(plain)}).acted is False
    field = _field(tmp_path)
    assert hooks.stop(_payload(field, stop_hook_active=True)).acted is False


def _tool_use_line(command):
    return json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": command}}]}}) + "\n"


def test_stop_is_silent_when_session_already_captured(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path))
    field = _field(tmp_path)
    assert hooks.stop(_payload(field, last_assistant_message="Done: `mf write draft.md --field x`")).acted is False
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("garbage line\n" + _tool_use_line("cd /x && mf raw add --field x < extract.md"))
    assert hooks.stop(_payload(field, transcript_path=str(transcript))).acted is False


def test_stop_ignores_prose_mentions_of_mf_write(tmp_path, monkeypatch):
    """The guidance text itself says `mf write`; talking about the command
    is not running it."""
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path))
    field = _field(tmp_path)
    transcript = tmp_path / "t.jsonl"
    prose = json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": "You could run mf write later. " + hooks.STOP_GUIDANCE}]}})
    transcript.write_text(prose + "\n" + _tool_use_line("grep -rn 'mf write' docs/"))
    payload = _payload(field, transcript_path=str(transcript),
                       last_assistant_message="I reviewed how mf write and mf raw add behave.")
    assert hooks.stop(payload).acted is True


def test_marker_path_never_leaves_the_temp_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path))
    marker = hooks._marker("../../etc/evil")
    assert marker.parent == tmp_path and "/" not in marker.name and ".." not in marker.name


def test_cli_hook_never_raises(tmp_path, monkeypatch, capsys):
    field = _field(tmp_path)
    monkeypatch.setattr(hooks, "session_end", lambda payload: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(field))))
    assert cli.main(["hook", "session-end"]) == 0
    assert "disk full" in capsys.readouterr().err


def test_session_end_writes_a_pointer_and_dedupes_on_session_id(tmp_path):
    field = _field(tmp_path)
    r = hooks.session_end(_payload(field, reason="other"))
    assert r is not None and r.written is True
    text = r.path.read_text()
    assert "kind: session-pointer" in text and "session_id: sess-1" in text
    assert "transcript_path:" in text and "reason: other" in text
    assert r.path.name.endswith("-session.md")
    again = hooks.session_end(_payload(field, reason="resume"))
    assert again is not None and again.written is False
    assert hooks.session_end({"session_id": "x", "cwd": str(tmp_path)}) is None


def test_cli_hook_stop_and_session_end(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hooks.tempfile, "gettempdir", lambda: str(tmp_path))
    field = _field(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(field))))
    assert cli.main(["hook", "stop"]) == 0
    assert "additionalContext" in json.loads(capsys.readouterr().out)["hookSpecificOutput"]
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(_payload(field, reason="clear"))))
    assert cli.main(["hook", "session-end"]) == 0
    assert capsys.readouterr().out == ""
    assert list((field / "raw").glob("*-session.md"))
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert cli.main(["hook", "stop"]) == 0  # malformed payload: silent no-op
