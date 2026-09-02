import zipfile

import pytest

from mf import db, indexer, pack, read
from mf.schema import EMBEDDING_DIM

PAGE = """\
---
uuid: {uuid}
title: "Rotate the key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""

SPEC_PLAIN = """\
---
uuid: plain-001
title: A spec-plain page with no extended fields
created: 2026-01-01
updated: 2026-01-02
---

Nothing but the four spec fields and a body about elevator maintenance.
"""


def _fake_embed(pages, model_code):
    return {p.uuid: [0.1] * EMBEDDING_DIM for p in pages}


def _build(tmp_path, monkeypatch, with_index=True):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed)
    field = tmp_path / "field"
    (field / "sub").mkdir(parents=True)
    (field / "a.md").write_text(PAGE.format(uuid="a"))
    (field / "sub" / "b.md").write_text(PAGE.format(uuid="b"))
    (field / "raw").mkdir()
    (field / "raw" / "20260101T000000Z.md").write_text("session extract\n")
    (field / ".git").mkdir()
    (field / ".git" / "HEAD").write_text("ref\n")
    if with_index:
        db.init_field(field)
        conn = db.open_field(field)
        indexer.index_field(field, conn)
        conn.close()
    return field


def test_pack_is_reproducible_and_skips_dotdirs(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    r1 = pack.pack_field(field, out=tmp_path / "one.memoryfield.zip")
    r2 = pack.pack_field(field, out=tmp_path / "two.memoryfield.zip")
    assert r1.sha256 == r2.sha256
    names = zipfile.ZipFile(r1.path).namelist()
    assert set(names) == {"a.md", "sub/b.md", "raw/20260101T000000Z.md", "mf.sqlite3"}
    sidecar = r1.path.with_name(r1.path.name + ".sha256").read_text()
    assert sidecar == f"{r1.sha256}  one.memoryfield.zip\n"


def test_pack_flags_drop_index_and_raw(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    r = pack.pack_field(field, out=tmp_path / "x.memoryfield.zip", include_index=False, include_raw=False)
    assert set(zipfile.ZipFile(r.path).namelist()) == {"a.md", "sub/b.md"}


def test_round_trip_keeps_the_index_usable(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    r = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    dest = tmp_path / "restored"
    u = pack.unpack_field(r.path, dest)
    assert u.verified is True and u.has_index and u.index_drift == 0
    assert (dest / "sub" / "b.md").read_text() == PAGE.format(uuid="b")
    conn = db.open_field(dest)
    assert indexer.index_field(dest, conn).upserted == []  # nothing changed
    assert "make rotate-key" in read.read(conn, ["b"], field_dir=dest)[0].body
    conn.close()


def test_unpack_refuses_tampered_archive(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    r = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    with r.path.open("ab") as f:
        f.write(b"\n")
    with pytest.raises(pack.PackVerifyError):
        pack.unpack_field(r.path, tmp_path / "out")
    with pytest.raises(pack.PackVerifyError):
        pack.unpack_field(r.path, tmp_path / "out", expected_sha256="0" * 64)


def test_unpack_without_sidecar_is_unverified(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    r = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    r.path.with_name(r.path.name + ".sha256").unlink()
    u = pack.unpack_field(r.path, tmp_path / "out")
    assert u.verified is None


def test_unpack_refuses_non_empty_dest_unless_forced(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    r = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "keep.txt").write_text("x")
    with pytest.raises(pack.UnpackError):
        pack.unpack_field(r.path, dest)
    pack.unpack_field(r.path, dest, force=True)
    assert (dest / "a.md").exists() and (dest / "keep.txt").exists()


def test_unpack_rejects_path_traversal(tmp_path):
    z = tmp_path / "evil.memoryfield.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../escape.md", "x")
    with pytest.raises(pack.UnpackError):
        pack.unpack_field(z, tmp_path / "out")
    assert not (tmp_path / "escape.md").exists()


def test_unpack_strips_single_top_level_folder(tmp_path):
    z = tmp_path / "folder.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("myfield/a.md", PAGE.format(uuid="a"))
        zf.writestr("myfield/sub/b.md", PAGE.format(uuid="b"))
    u = pack.unpack_field(z, tmp_path / "out")
    assert u.stripped_prefix == "myfield"
    assert (tmp_path / "out" / "a.md").exists() and (tmp_path / "out" / "sub" / "b.md").exists()
    assert u.has_index is False and any("mf init" in n for n in u.notes)


def test_spec_plain_memoryfield_round_trips_and_indexes(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed)
    field = tmp_path / "plain"
    field.mkdir()
    (field / "plain.md").write_text(SPEC_PLAIN)
    r = pack.pack_field(field, out=tmp_path / "plain.memoryfield.zip")
    dest = tmp_path / "out"
    u = pack.unpack_field(r.path, dest)
    assert u.has_index is False
    db.init_field(dest)
    conn = db.open_field(dest)
    assert indexer.index_field(dest, conn).upserted == ["plain-001"]
    assert read.read(conn, ["plain-001"], field_dir=dest)[0].title.startswith("A spec-plain")
    conn.close()


def test_unpack_reports_index_drift(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch)
    (field / "a.md").write_text(PAGE.format(uuid="a") + "\nedited after indexing\n")
    r = pack.pack_field(field, out=tmp_path / "f.memoryfield.zip")
    u = pack.unpack_field(r.path, tmp_path / "out")
    assert u.index_drift == 1


# --- `pack --spec` (docs/upstream/SPEC.md) ---------------------------------

def _fake_embed_texts(texts, model_code):
    return [[0.5] * EMBEDDING_DIM for _ in texts]


def test_pack_spec_emits_root_pages_and_a_spec_index(tmp_path, monkeypatch):
    import json
    import sqlite3

    field = _build(tmp_path, monkeypatch)
    (field / "Bad_Name.md").write_text(PAGE.format(uuid="bad"))
    monkeypatch.setattr(pack, "_embed_texts", _fake_embed_texts)
    r = pack.pack_field(field, out=tmp_path / "s.memoryfield.zip", spec=True)
    assert set(zipfile.ZipFile(r.path).namelist()) == {"a.md", "snowflake-arctic-embed-xs.sqlite3"}
    assert r.spec_index == "snowflake-arctic-embed-xs.sqlite3"
    assert sorted(r.skipped) == ["Bad_Name.md", "sub/b.md"]  # bad filename, subdirectory
    assert r.files == 2
    idx = tmp_path / "idx.sqlite3"
    idx.write_bytes(zipfile.ZipFile(r.path).read(r.spec_index))
    conn = sqlite3.connect(idx)
    rows = conn.execute("SELECT filename, frontmatter, length(sha256_hash), length(embedding) FROM pages").fetchall()
    conn.close()
    assert len(rows) == 1
    filename, fm, sha_len, emb_len = rows[0]
    assert filename == "a.md" and sha_len == 32 and emb_len == EMBEDDING_DIM * 4
    assert json.loads(fm) == {"uuid": "a", "title": "Rotate the key", "summary": "Run make rotate-key"}


def test_pack_spec_embeds_the_whole_file_per_the_spec(tmp_path, monkeypatch):
    captured = {}

    def fake(texts, model_code):
        captured["texts"], captured["model"] = texts, model_code
        return _fake_embed_texts(texts, model_code)

    field = _build(tmp_path, monkeypatch)
    monkeypatch.setattr(pack, "_embed_texts", fake)
    pack.pack_field(field, out=tmp_path / "s.memoryfield.zip", spec=True)
    assert captured["model"] == "snowflake-arctic-embed-xs"
    # Frontmatter included, no mf-style title+summary+L1 construction.
    assert captured["texts"] == [(field / "a.md").read_text()]


def test_pack_spec_without_an_index_writes_pages_only(tmp_path, monkeypatch):
    field = _build(tmp_path, monkeypatch, with_index=False)
    r = pack.pack_field(field, out=tmp_path / "s.memoryfield.zip", spec=True)
    assert set(zipfile.ZipFile(r.path).namelist()) == {"a.md"}
    assert r.spec_index == "" and r.skipped == ["sub/b.md"]


def test_unpack_notes_a_spec_index_it_does_not_read(tmp_path):
    z = tmp_path / "s.memoryfield.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("a.md", PAGE.format(uuid="a"))
        zf.writestr("nomic-embed-text-v1.5.sqlite3", b"not read")
    u = pack.unpack_field(z, tmp_path / "out")
    assert u.has_index is False
    assert any("nomic-embed-text-v1.5.sqlite3" in n and "mf init" in n for n in u.notes)
