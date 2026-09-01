import json

from mf import cli, db, importers, indexer
from mf.page import load_page
from mf.schema import EMBEDDING_DIM

TOPIC = """\
---
name: deploy-freeze
description: Deploys freeze the last week of each quarter; page #release-mgmt to override.
metadata:
  node_type: memory
  type: project
  originSessionId: abc
---

The freeze is enforced by a calendar check in the deploy job, not by policy alone.

- Override needs two approvals.
"""

MEMORY_MD = """\
# Memory

- [Deploy freeze calendar](deploy-freeze.md) — last week of each quarter
- [Ghost note](ghost.md) — a line whose file was deleted
"""


def _field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: {p.uuid: [0.1] * EMBEDDING_DIM for p in pages})
    field = tmp_path / "field"
    field.mkdir()
    db.init_field(field)
    return field


def _memory_dir(tmp_path):
    src = tmp_path / "memory"
    src.mkdir()
    (src / "MEMORY.md").write_text(MEMORY_MD)
    (src / "deploy-freeze.md").write_text(TOPIC)
    return src


def test_claude_memory_import_maps_fields(tmp_path, monkeypatch):
    field = _field(tmp_path, monkeypatch)
    conn = db.open_field(field)
    src = _memory_dir(tmp_path)
    r = importers.import_claude_memory(src, field, conn)
    assert r.indexed == 2 and not r.dry_run
    page = load_page(field / "claude-memory" / "deploy-freeze.md")
    assert page.uuid == "deploy-freeze"
    assert page.title == "Deploy freeze calendar"          # index link text
    assert page.summary.startswith("Deploys freeze")       # frontmatter description
    assert page.tags == ["project"]
    assert page.source.endswith("memory/deploy-freeze.md")
    assert "calendar check" in page.body
    ghost = load_page(field / "claude-memory" / "ghost.md")
    assert ghost.title == "Ghost note" and ghost.summary == "a line whose file was deleted"
    assert any("ghost.md" in s for s in r.skipped)
    assert importers.verify_imported(field, r) == []
    # re-import is idempotent
    r2 = importers.import_claude_memory(src, field, conn)
    assert r2.indexed == 0
    conn.close()


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    field = _field(tmp_path, monkeypatch)
    conn = db.open_field(field)
    r = importers.import_claude_memory(_memory_dir(tmp_path), field, conn, dry_run=True)
    assert len(r.pages) == 2 and r.dry_run
    assert not (field / "claude-memory").exists()
    assert conn.execute("SELECT count(*) FROM pages").fetchone()[0] == 0
    conn.close()


def _wiki_dir(tmp_path):
    src = tmp_path / "wiki"
    (src / "infra").mkdir(parents=True)
    (src / "index.md").write_text(
        "# Wiki\n\n- [Rollback runbook](infra/rollback.md): kubectl rollout undo, ~90s\n"
        "- [Style guide](style.md) - how we write pages\n"
    )
    (src / "infra" / "rollback.md").write_text("# Rolling back\n\nRun `kubectl rollout undo`.\n\n## Why\n\nForward-only.\n")
    (src / "style.md").write_text("# Style\n\nShort pages.\n")
    (src / "orphan.md").write_text("# Not in the index\n\nFirst paragraph becomes the summary.\n\nMore.\n")
    return src


def test_wiki_import_flattens_and_uses_index_descriptions(tmp_path, monkeypatch):
    field = _field(tmp_path, monkeypatch)
    conn = db.open_field(field)
    r = importers.import_wiki(_wiki_dir(tmp_path), field, conn)
    assert r.indexed == 3
    rb = load_page(field / "wiki" / "infra-rollback.md")
    assert rb.uuid == "infra-rollback"
    assert rb.title == "Rollback runbook"
    assert rb.summary == "kubectl rollout undo, ~90s"
    assert "# Rolling back" not in rb.body and "Run `kubectl rollout undo`" in rb.body
    style = load_page(field / "wiki" / "style.md")
    assert style.summary == "how we write pages"
    orphan = load_page(field / "wiki" / "orphan.md")
    assert orphan.title == "Not in the index"
    assert orphan.summary == "First paragraph becomes the summary."
    assert importers.verify_imported(field, r) == []
    conn.close()


def test_cli_import_text_and_json(tmp_path, monkeypatch, capsys):
    field = _field(tmp_path, monkeypatch)
    src = _memory_dir(tmp_path)
    assert cli.main(["import", "claude-memory", str(src), "--field", str(field), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Would write 2 page(s)" in out
    assert cli.main(["import", "claude-memory", str(src), "--field", str(field), "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["indexed"] == 2 and parsed["kind"] == "claude-memory"
    assert cli.main(["import", "wiki", str(tmp_path / "nope"), "--field", str(field)]) == 1
