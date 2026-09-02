from mf import db, indexer, lint
from mf.schema import EMBEDDING_DIM

GOOD = """\
---
uuid: good
title: "Deploy - how to roll back"
summary: "Run `kubectl rollout undo deployment/<svc>`; takes about 90 seconds end to end."
source: runbooks/deploy.md
---

## Answer

Run `kubectl rollout undo deployment/<svc>`. It re-deploys the previous image.
"""


def _codes(result, severity=None):
    return sorted(
        f.code for f in result.findings if severity is None or f.severity == severity
    )


def _lint(tmp_path, **files):
    for name, text in files.items():
        (tmp_path / f"{name}.md").write_text(text)
    return lint.lint_field(tmp_path)


def test_clean_page_has_no_errors_or_warnings(tmp_path):
    r = _lint(tmp_path, good=GOOD)
    assert r.pages == 1
    assert _codes(r, "error") == [] and _codes(r, "warning") == []
    assert r.failed is False
    assert "orphan" in _codes(r, "info") and "short-page" in _codes(r, "info")


def test_readme_without_frontmatter_is_ignored_but_bad_frontmatter_warns(tmp_path):
    r = _lint(tmp_path, good=GOOD, readme="# hi\n\nno frontmatter\n",
              broken="---\ntitle: no uuid\n---\n\nbody\n")
    assert r.pages == 1
    assert _codes(r, "warning") == ["invalid-page"]


def test_duplicate_uuid_is_an_error(tmp_path):
    r = _lint(tmp_path, a=GOOD, b=GOOD)
    assert "duplicate-uuid" in _codes(r, "error")


def test_missing_summary_is_an_error_and_short_summary_warns(tmp_path):
    r = _lint(tmp_path,
              none=GOOD.replace('summary: "Run `kubectl rollout undo deployment/<svc>`; takes about 90 seconds end to end."\n', "").replace("uuid: good", "uuid: none"),
              short=GOOD.replace('summary: "Run `kubectl rollout undo deployment/<svc>`; takes about 90 seconds end to end."', 'summary: "Notes on rollback"').replace("uuid: good", "uuid: short"))
    assert "missing-summary" in _codes(r, "error")
    assert "summary-shape" in _codes(r, "warning")


def test_summary_that_repeats_the_title_warns(tmp_path):
    r = _lint(tmp_path, t=GOOD.replace(
        'summary: "Run `kubectl rollout undo deployment/<svc>`; takes about 90 seconds end to end."',
        'summary: "Deploy - how to roll back"'))
    assert "summary-shape" in _codes(r, "warning")


def test_table_and_copied_state_warn(tmp_path):
    body = GOOD + "\n| a | b |\n|---|---|\n| 1 | 2 |\n\nDeployed yesterday at sha 0123456789abcdef0123456789abcdef01234567.\n"
    r = _lint(tmp_path, t=body)
    codes = _codes(r, "warning")
    assert "table" in codes
    assert codes.count("copied-state") == 2  # sha + relative time


def test_negation_outside_dont_section_is_info_only(tmp_path):
    r = _lint(tmp_path, t=GOOD + "\nNever run this on Fridays.\n")
    assert "negation-in-prose" in _codes(r, "info")
    r2 = _lint(tmp_path, u=GOOD.replace("uuid: good", "uuid: u") + "\n## Don't\n\nNever run this on Fridays.\n")
    assert "negation-in-prose" not in [f.code for f in r2.findings if f.uuid == "u"]


def test_headers_under_300_excepts_dont(tmp_path):
    r = _lint(tmp_path, t=GOOD + "\n## Don't\n\nNever on Fridays.\n")
    assert "headers-under-300" not in _codes(r)
    r2 = _lint(tmp_path, u=GOOD.replace("uuid: good", "uuid: u") + "\n## History\n\nRotated quarterly.\n")
    assert "headers-under-300" in _codes(r2, "warning")


def test_oversize_page_is_an_error_and_long_page_warns(tmp_path):
    r = _lint(tmp_path, big=GOOD + ("x" * 9000))
    assert "oversize" in _codes(r, "error")
    r2 = _lint(tmp_path, long=GOOD.replace("uuid: good", "uuid: long") + ("word " * 900))
    assert "long-page" in _codes(r2, "warning")


def test_link_checks(tmp_path):
    old = GOOD.replace("uuid: good", "uuid: old")
    new = GOOD.replace("uuid: good", "uuid: new\nsupersedes: [old, ghost]")
    lonely = GOOD.replace("uuid: good", "uuid: lonely\nstatus: superseded")
    r = _lint(tmp_path, old=old, new=new, lonely=lonely)
    by_uuid = {(f.uuid, f.code) for f in r.findings}
    assert ("new", "dangling-link") in by_uuid
    assert ("old", "active-but-superseded") in by_uuid
    assert ("lonely", "superseded-not-linked") in by_uuid
    assert ("old", "orphan") not in by_uuid
    assert ("lonely", "orphan") in by_uuid


def test_bad_status_is_an_error(tmp_path):
    r = _lint(tmp_path, t=GOOD.replace("uuid: good", "uuid: t\nstatus: draft"))
    assert "bad-status" in _codes(r, "error")


def test_two_active_pages_sharing_a_slug_warn_contested(tmp_path):
    # Same filename stem in different subdirectories: two writers naming
    # a page after the same topic without seeing each other's draft.
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend" / "rollback.md").write_text(GOOD.replace("uuid: good", "uuid: a"))
    (tmp_path / "frontend" / "rollback.md").write_text(GOOD.replace("uuid: good", "uuid: b"))
    r = lint.lint_field(tmp_path)
    by_uuid = {(f.uuid, f.code) for f in r.findings}
    assert ("a", "contested-slug") in by_uuid
    assert ("b", "contested-slug") in by_uuid


def test_contested_status_page_is_exempt_from_slug_collision(tmp_path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "backend" / "rollback.md").write_text(GOOD.replace("uuid: good", "uuid: a"))
    (tmp_path / "frontend" / "rollback.md").write_text(
        GOOD.replace("uuid: good", "uuid: b\nstatus: contested")
    )
    r = lint.lint_field(tmp_path)
    assert "contested-slug" not in _codes(r, "warning")


def test_index_drift_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", lambda pages, model_code: {p.uuid: [0.1] * EMBEDDING_DIM for p in pages})
    (tmp_path / "good.md").write_text(GOOD)
    (tmp_path / "gone.md").write_text(GOOD.replace("uuid: good", "uuid: gone"))
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    (tmp_path / "gone.md").unlink()
    (tmp_path / "good.md").write_text(GOOD + "\nedited\n")
    (tmp_path / "new.md").write_text(GOOD.replace("uuid: good", "uuid: new"))
    r = lint.lint_field(tmp_path, conn)
    by = {(f.uuid, f.code) for f in r.findings}
    assert ("good", "stale-index") in by
    assert ("new", "unindexed") in by
    assert ("gone", "missing-file") in by
    conn.close()
