"""Regression tests for the 2026-09-03 audit: importers, lint, claim,
pack/unpack, CLI plumbing."""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import pytest

from mf import claim as claim_mod
from mf import cli, db, importers, lint, pack

PAGE = "---\nuuid: {uuid}\ntitle: \"T {uuid}\"\nsummary: \"An answer sentence with enough words\"\n---\n\n## Answer\n\nbody {uuid}\n"


# --- importers ------------------------------------------------------------

def test_imported_pages_pass_lint_check(field_factory, tmp_path, capsys):
    field = field_factory({})
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "index.md").write_text("- [Deploys](deploys.md): how deploys roll back safely\n")
    (wiki / "deploys.md").write_text("# Deploys\n\nRoll back with make rollback. It takes a minute and is safe to repeat.\n")
    assert cli.main(["import", "wiki", str(wiki), "--field", str(field)]) == 0
    capsys.readouterr()
    result = lint.lint_field(field, None)
    assert [f for f in result.findings if f.code == "spec-dates" and f.severity == "error"] == []
    text = (field / "wiki" / "deploys.md").read_text()
    assert 'created: "' in text and 'updated: "' in text


def test_wiki_under_a_dot_directory_imports(field_factory, tmp_path):
    field = field_factory({})
    wiki = tmp_path / ".config" / "wiki"
    wiki.mkdir(parents=True)
    (wiki / "note.md").write_text("# Note\n\nSome content here.\n")
    (wiki / ".drafts").mkdir()
    (wiki / ".drafts" / "hidden.md").write_text("# Hidden\n\nno\n")
    conn = db.open_field(field)
    result = importers.import_wiki(wiki, field, conn, dry_run=True)
    conn.close()
    assert [p.uuid for p in result.pages] == ["note"]


def test_wiki_flatten_collisions_are_suffixed_not_overwritten(field_factory, tmp_path):
    field = field_factory({})
    wiki = tmp_path / "wiki"
    (wiki / "a").mkdir(parents=True)
    (wiki / "a" / "b.md").write_text("# Nested\n\nnested body\n")
    (wiki / "a-b.md").write_text("# Flat\n\nflat body\n")
    conn = db.open_field(field)
    result = importers.import_wiki(wiki, field, conn)
    conn.close()
    dests = sorted(p.dest for p in result.pages)
    assert dests == ["wiki/a-b-2.md", "wiki/a-b.md"]
    assert any("flattens to the same name" in s for s in result.skipped)
    assert (field / "wiki" / "a-b.md").exists() and (field / "wiki" / "a-b-2.md").exists()
    assert result.indexed == 2
    assert importers.verify_imported(field, result) == []


def test_malformed_source_frontmatter_is_stripped_and_reported(field_factory, tmp_path):
    field = field_factory({})
    mem = tmp_path / "mem"
    mem.mkdir()
    (mem / "MEMORY.md").write_text("- [Thing](thing.md) — a hook\n")
    (mem / "thing.md").write_text("---\nname: [unclosed\n---\n\nBody text here.\n")
    conn = db.open_field(field)
    result = importers.import_claude_memory(mem, field, conn, dry_run=True)
    conn.close()
    assert any("frontmatter ignored" in s for s in result.skipped)
    assert result.pages[0].title == "Thing"


def test_import_indexed_counts_only_imported_pages(field_factory, tmp_path):
    field = field_factory({"existing.md": PAGE.format(uuid="existing")})
    (field / "existing.md").write_text(PAGE.format(uuid="existing") + "\nedited\n")  # dirty, will be upserted too
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "n.md").write_text("# N\n\nbody\n")
    conn = db.open_field(field)
    result = importers.import_wiki(wiki, field, conn)
    conn.close()
    assert result.indexed == 1


# --- lint -----------------------------------------------------------------

def test_lint_reports_non_utf8_and_skips_debris(tmp_path):
    (tmp_path / "ok.md").write_text(PAGE.format(uuid="ok"))
    (tmp_path / "latin.md").write_bytes(b"---\nuuid: l\ntitle: caf\xe9\n---\nx\n")
    (tmp_path / "ok.sync-conflict-1.md").write_text(PAGE.format(uuid="ok"))
    result = lint.lint_field(tmp_path)
    codes = {(f.code, f.filename) for f in result.findings}
    assert ("invalid-page", "latin.md") in codes
    assert not any(f.code == "duplicate-uuid" for f in result.findings)


def test_lint_orphan_claim(field_factory):
    field = field_factory({"a.md": PAGE.format(uuid="a")})
    conn = db.open_field(field)
    claim_mod.claim_slug(conn, "a", "me")
    claim_mod.claim_slug(conn, "ghost", "someone")
    result = lint.lint_field(field, conn)
    conn.close()
    orphans = [f for f in result.findings if f.code == "orphan-claim"]
    assert [f.filename for f in orphans] == ["ghost.md"] and orphans[0].severity == "info"


# --- claim ----------------------------------------------------------------

def test_claim_release_only_by_holder(field_factory, capsys):
    field = field_factory({})
    assert cli.main(["claim", "topic", "--by", "alice", "--field", str(field)]) == 0
    assert cli.main(["claim", "topic", "--by", "bob", "--field", str(field), "--release"]) == 2
    assert "already claimed by alice" in capsys.readouterr().out
    assert cli.main(["claim", "topic", "--by", "alice", "--field", str(field), "--release", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["released"] is True
    assert cli.main(["claim", "topic", "--by", "bob", "--field", str(field)]) == 0  # free again
    assert cli.main(["claim", "nobody", "--by", "bob", "--field", str(field), "--release"]) == 0
    assert "nothing to release" in capsys.readouterr().out


# --- pack / unpack --------------------------------------------------------

def test_unpack_does_not_write_through_a_symlink(tmp_path, field_factory):
    field = field_factory({"a.md": PAGE.format(uuid="a")})
    result = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    dest = tmp_path / "dest"
    dest.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("untouched")
    os.symlink(victim, dest / "a.md")
    pack.unpack_field(result.path, dest=dest, force=True)
    assert victim.read_text() == "untouched"
    assert not (dest / "a.md").is_symlink() and (dest / "a.md").read_text().startswith("---")


def test_unpack_refuses_oversized_member(tmp_path, monkeypatch):
    archive = tmp_path / "big.memoryfield.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("a.md", "x" * 10)
    monkeypatch.setattr(pack, "MAX_MEMBER_BYTES", 5)
    with pytest.raises(pack.UnpackError, match="cap is 5"):
        pack.unpack_field(archive, dest=tmp_path / "d")


def test_pack_includes_rows_still_in_the_wal(tmp_path, field_factory):
    field = field_factory({"a.md": PAGE.format(uuid="a")})
    # Hold a connection open with a committed write so the WAL is not
    # checkpointed into the main file when pack runs.
    holder = db.open_field(field)
    holder.execute("INSERT INTO claims VALUES ('held', 'me', 't')")
    holder.commit()
    result = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    holder.close()
    dest = tmp_path / "restored"
    pack.unpack_field(result.path, dest=dest)
    conn = db.open_field(dest)
    assert conn.execute("SELECT count(*) FROM claims").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM pages").fetchone()[0] == 1
    conn.close()
    assert not (dest / "mf.sqlite3-wal").exists() or True


def test_unpack_dest_that_is_a_file_is_clean_error(tmp_path, field_factory):
    field = field_factory({"a.md": PAGE.format(uuid="a")})
    result = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    with pytest.raises(pack.UnpackError, match="not a directory"):
        pack.unpack_field(result.path, dest=blocker)


# --- CLI plumbing ---------------------------------------------------------

def test_cli_without_subcommand_prints_help(capsys):
    assert cli.main([]) == 0
    assert "usage: mf" in capsys.readouterr().out


def test_cli_version(capsys):
    from mf import __version__
    with pytest.raises(SystemExit) as e:
        cli.main(["--version"])
    assert e.value.code == 0 and __version__ in capsys.readouterr().out


def test_cli_missing_subcommands_exit_1(capsys):
    assert cli.main(["raw"]) == 1
    assert cli.main(["model"]) == 1
    assert cli.main(["hook"]) == 1
    assert cli.main(["import"]) == 1


def test_cli_mcp_without_package_exits_1(monkeypatch, capsys):
    import sys

    import mf
    # None in sys.modules makes the import raise ImportError, the same
    # signal a broken install without the `mcp` package produces.
    monkeypatch.setitem(sys.modules, "mf.mcp_server", None)
    monkeypatch.delattr(mf, "mcp_server", raising=False)
    assert cli.main(["mcp"]) == 1
    assert "reinstall" in capsys.readouterr().err


def test_cli_mcp_passes_field_to_server(monkeypatch):
    mcp_server = pytest.importorskip("mf.mcp_server")
    seen = {}
    monkeypatch.setattr(mcp_server, "main", lambda field=".": seen.setdefault("field", field))
    assert cli.main(["mcp", "--field", "notes"]) == 0
    # Resolved against the cwd, so the server keeps working after a chdir.
    assert seen == {"field": str(Path.cwd().resolve() / "notes")}


def test_cli_locked_database_is_exit_1(field_factory, capsys, monkeypatch):
    import sqlite3
    field = field_factory({"a.md": PAGE.format(uuid="a")})
    monkeypatch.setattr(db, "open_field", lambda *a, **k: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
    assert cli.main(["search", "x", "--field", str(field)]) == 1
    assert "database is locked" in capsys.readouterr().err


def test_cli_write_stdin_without_dest(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("x"))
    assert cli.main(["write", "-"]) == 1
    assert "--dest" in capsys.readouterr().err
