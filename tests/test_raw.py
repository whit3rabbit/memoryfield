import pytest

from mf import raw


def test_add_raw_creates_file(tmp_path):
    result = raw.add_raw(tmp_path, "Session summary: fixed the flaky test.")
    assert result.written is True
    assert result.path.exists()
    assert result.path.parent == tmp_path / "raw"
    assert result.path.read_text(encoding="utf-8").strip() == "Session summary: fixed the flaky test."


def test_add_raw_creates_raw_dir_if_missing(tmp_path):
    assert not (tmp_path / "raw").exists()
    raw.add_raw(tmp_path, "First extract.")
    assert (tmp_path / "raw").is_dir()


def test_add_raw_exact_duplicate_is_skipped(tmp_path):
    first = raw.add_raw(tmp_path, "Same session extract.")
    second = raw.add_raw(tmp_path, "Same session extract.")
    assert second.written is False
    assert second.path == first.path
    assert len(list((tmp_path / "raw").glob("*.md"))) == 1


def test_add_raw_prefix_of_existing_is_skipped(tmp_path):
    first = raw.add_raw(tmp_path, "Full session extract with lots of detail.")
    second = raw.add_raw(tmp_path, "Full session extract")
    assert second.written is False
    assert second.path == first.path


def test_add_raw_fuller_version_of_existing_is_skipped(tmp_path):
    first = raw.add_raw(tmp_path, "Partial extract")
    second = raw.add_raw(tmp_path, "Partial extract with more detail added on retry.")
    assert second.written is False
    assert second.path == first.path


def test_add_raw_genuinely_different_text_creates_new_file(tmp_path):
    first = raw.add_raw(tmp_path, "First session's extract.")
    second = raw.add_raw(tmp_path, "Completely unrelated second session's extract.")
    assert second.written is True
    assert second.path != first.path
    assert len(list((tmp_path / "raw").glob("*.md"))) == 2


def test_add_raw_empty_text_raises(tmp_path):
    with pytest.raises(raw.EmptyRawTextError):
        raw.add_raw(tmp_path, "   \n  ")
