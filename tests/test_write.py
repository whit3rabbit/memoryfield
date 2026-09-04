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
    # The "existing page" vector: one-hot on axis 0. (A literal zero
    # vector has no cosine distance -- sqlite-vec returns NULL.)
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    return vec


def _near_dup_vec() -> list[float]:
    # Cosine distance from _zero_vec() is ~0.005 -- well under DEDUP_THRESHOLD.
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    vec[-1] = 0.1
    return vec


def _far_vec() -> list[float]:
    # Orthogonal to _zero_vec(): cosine distance 1.0 -- well over DEDUP_THRESHOLD.
    vec = [0.0] * EMBEDDING_DIM
    vec[1] = 1.0
    return vec


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


def _field_and_draft(tmp_path, monkeypatch, draft_name="billing-draft.md", text=NEW_PAGE):
    field = tmp_path / "field"
    field.mkdir()
    conn = _build_field(field, monkeypatch)
    drafts = tmp_path / "drafts"
    drafts.mkdir()
    draft = drafts / draft_name
    draft.write_text(text)
    return field, conn, draft


def test_draft_outside_field_is_copied_in_on_pass(tmp_path, monkeypatch):
    field, conn, draft = _field_and_draft(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())

    result = write.write_page(field, conn, draft)
    assert result.written is True
    assert result.path == "billing-draft.md"
    assert (field / "billing-draft.md").read_text() == NEW_PAGE
    assert draft.exists()  # the draft itself is left alone
    row = conn.execute("SELECT filename FROM pages WHERE uuid = 'page-billing'").fetchone()
    assert row == ("billing-draft.md",)
    conn.close()


def test_blocked_draft_outside_field_leaves_nothing_behind(tmp_path, monkeypatch):
    field, conn, draft = _field_and_draft(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())

    result = write.write_page(field, conn, draft)
    assert result.written is False
    assert result.warning is None
    assert not (field / "billing-draft.md").exists()
    assert conn.execute("SELECT 1 FROM pages WHERE uuid = 'page-billing'").fetchone() is None
    conn.close()


def test_blocked_in_field_draft_warns_it_will_be_indexed_anyway(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    (tmp_path / "billing.md").write_text(NEW_PAGE)

    result = write.write_page(tmp_path, conn, tmp_path / "billing.md")
    assert result.written is False
    assert result.warning == write.IN_FIELD_WARNING
    conn.close()


def test_dest_name_overrides_draft_filename(tmp_path, monkeypatch):
    field, conn, draft = _field_and_draft(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())

    result = write.write_page(field, conn, draft, dest_name="billing.md")
    assert result.path == "billing.md"
    assert (field / "billing.md").exists()
    conn.close()


def test_dest_rejected_for_in_field_path(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    with pytest.raises(write.WriteValidationError, match="--dest"):
        write.write_page(tmp_path, conn, tmp_path / "rotate.md", dest_name="other.md")
    conn.close()


def test_dest_existing_with_other_uuid_rejected(tmp_path, monkeypatch):
    field, conn, draft = _field_and_draft(tmp_path, monkeypatch)
    with pytest.raises(write.WriteValidationError, match="different uuid"):
        write.write_page(field, conn, draft, dest_name="rotate.md")
    conn.close()


def test_uuid_already_indexed_elsewhere_rejected(tmp_path, monkeypatch):
    # A draft of page-rotate under a new filename would leave two files
    # with one uuid.
    field, conn, draft = _field_and_draft(
        tmp_path, monkeypatch, draft_name="rotate-v2.md", text=PAGE_ROTATE
    )
    with pytest.raises(write.WriteValidationError, match=r"already indexed at rotate\.md"):
        write.write_page(field, conn, draft, update_uuid="page-rotate")
    conn.close()


def test_write_indexes_only_the_written_page(tmp_path, monkeypatch):
    field, conn, draft = _field_and_draft(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())
    # A hand-dropped page in the field that never went through the gate.
    (field / "stray.md").write_text(PAGE_ROTATE.replace("page-rotate", "page-stray"))

    write.write_page(field, conn, draft)
    uuids = {r[0] for r in conn.execute("SELECT uuid FROM pages")}
    assert "page-billing" in uuids
    assert "page-stray" not in uuids  # waits for an explicit `mf index`
    conn.close()


def test_write_text_from_stdin_style_input(tmp_path, monkeypatch):
    field = tmp_path / "field"
    field.mkdir()
    conn = _build_field(field, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())

    result = write.write_text(field, conn, NEW_PAGE, "billing.md")
    assert result.written is True
    assert (field / "billing.md").read_text() == NEW_PAGE
    with pytest.raises(write.WriteValidationError, match="escapes"):
        write.write_text(field, conn, NEW_PAGE, "../escape.md")
    conn.close()


def test_write_invalid_page_raises_parse_error(tmp_path, monkeypatch):
    conn = _build_field(tmp_path, monkeypatch)
    (tmp_path / "bad.md").write_text(NOT_A_PAGE)

    with pytest.raises(PageParseError):
        write.write_page(tmp_path, conn, tmp_path / "bad.md")
    conn.close()
