import pytest

from mf import db, indexer, write
from mf.page import PageParseError
from mf.schema import EMBEDDING_DIM

PAGE_ROTATE = """\
---
uuid: page-rotate
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""

NEW_PAGE = """\
---
uuid: page-billing
title: "How billing retries failed payments"
summary: "Dunning levels 1-4"
---

## Steps

Failed payments trigger dunning_level increments.
"""

NOT_A_PAGE = "# Just a readme\n\nNo frontmatter.\n"


def _zero_vec() -> list[float]:
    return [0.0] * EMBEDDING_DIM


def _near_dup_vec() -> list[float]:
    # L2 distance from _zero_vec() is 0.5 -- well under DEDUP_THRESHOLD.
    vec = [0.0] * EMBEDDING_DIM
    vec[-1] = 0.5
    return vec


def _far_vec() -> list[float]:
    # L2 distance from _zero_vec() is sqrt(768) =~ 27.7 -- well over DEDUP_THRESHOLD.
    return [1.0] * EMBEDDING_DIM


def _fake_embed_pages(pages, model_code):
    return {p.uuid: _zero_vec() for p in pages}


def _build_field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    (tmp_path / "rotate.md").write_text(PAGE_ROTATE)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    return conn


def test_write_new_nonduplicate_page_succeeds(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    result = write.write_page(tmp_path, conn, tmp_path / "billing.md")
    assert result.written is True
    assert result.uuid == "page-billing"
    assert result.duplicates == []

    row = conn.execute("SELECT uuid FROM pages WHERE uuid = ?", ("page-billing",)).fetchone()
    assert row is not None
    conn.close()


def test_write_blocks_near_duplicate(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    result = write.write_page(tmp_path, conn, tmp_path / "billing.md")
    assert result.written is False
    assert result.uuid == "page-billing"
    assert len(result.duplicates) == 1
    assert result.duplicates[0].uuid == "page-rotate"

    row = conn.execute("SELECT uuid FROM pages WHERE uuid = ?", ("page-billing",)).fetchone()
    assert row is None, "blocked write must not be indexed"
    conn.close()


def test_write_force_bypasses_dedup_gate(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    result = write.write_page(tmp_path, conn, tmp_path / "billing.md", force=True)
    assert result.written is True
    conn.close()


def test_write_update_matching_uuid_bypasses_dedup_gate(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    result = write.write_page(
        tmp_path, conn, tmp_path / "billing.md", update_uuid="page-billing"
    )
    assert result.written is True
    conn.close()


def test_write_update_mismatched_uuid_raises(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    with pytest.raises(write.WriteValidationError):
        write.write_page(tmp_path, conn, tmp_path / "billing.md", update_uuid="wrong-uuid")
    conn.close()


def test_write_self_update_not_blocked_as_duplicate_of_itself(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    # Re-embedding page-rotate itself with a vector identical to what's
    # already indexed under its own uuid must not self-dedup-block.
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _zero_vec())
    (tmp_path / "rotate.md").write_text(
        PAGE_ROTATE + "\n## Extra\n\nMore detail.\n"
    )

    result = write.write_page(tmp_path, conn, tmp_path / "rotate.md")
    assert result.written is True
    assert result.duplicates == []
    conn.close()


def test_write_path_outside_field_raises(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    outside = tmp_path.parent / "outside.md"
    outside.write_text(NEW_PAGE)
    try:
        with pytest.raises(write.WriteValidationError):
            write.write_page(tmp_path, conn, outside)
    finally:
        outside.unlink()
        conn.close()


def test_write_invalid_page_raises_parse_error(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    (tmp_path / "bad.md").write_text(NOT_A_PAGE)

    with pytest.raises(PageParseError):
        write.write_page(tmp_path, conn, tmp_path / "bad.md")
    conn.close()
