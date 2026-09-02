"""Spec-conformance lint checks (docs/upstream/SPEC.md, CLAUDE.md gotcha 39).

mf's parser quotes ambiguous frontmatter values itself, so these checks
parse the raw block with plain YAML the way upstream's tool or Obsidian
would, and report what those readers would reject.
"""
from mf import lint

PAGE = """\
---
uuid: {uuid}
title: {title}
summary: {summary}
created: {created}
updated: '2026-01-02T00:00:00Z'
---

## Answer

Run `make rotate-key`; it takes about a minute and logs to stdout.
"""

NO_DATES = """\
---
uuid: nodates
title: "Rotate the key"
summary: "Run make rotate-key; it takes about a minute."
---

## Answer

Run `make rotate-key`.
"""


def _lint(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return lint.lint_field(tmp_path)


def _by_code(result, code):
    return [f for f in result.findings if f.code == code]


def _page(uuid="ok", title='"Rotate: the key"', summary='"Run make rotate-key; it takes about a minute."',
          created="'2026-01-01T00:00:00Z'"):
    return PAGE.format(uuid=uuid, title=title, summary=summary, created=created)


def test_quoted_page_has_no_spec_findings(tmp_path):
    r = _lint(tmp_path, {"rotate-key.md": _page()})
    assert r.pages == 1
    assert not [f for f in r.findings if f.code.startswith("spec-")]


def test_unquoted_colon_title_parses_in_mf_but_warns_spec_yaml(tmp_path):
    r = _lint(tmp_path, {"rotate-key.md": _page(title="Rotate: the key")})
    assert r.pages == 1  # mf's own parser quotes it
    [f] = _by_code(r, "spec-yaml")
    assert f.severity == "warning" and "ScannerError" in f.message


def test_backtick_summary_warns_spec_yaml(tmp_path):
    r = _lint(tmp_path, {"rotate-key.md": _page(summary="`make rotate-key` rotates it in a minute.")})
    assert [f.severity for f in _by_code(r, "spec-yaml")] == ["warning"]


def test_unquoted_datetime_is_an_error_and_missing_dates_are_info(tmp_path):
    r = _lint(tmp_path, {"rotate-key.md": _page(created="2026-01-01"), "nodates.md": NO_DATES})
    dates = _by_code(r, "spec-dates")
    assert sorted((f.filename, f.severity) for f in dates) == [
        ("nodates.md", "info"), ("nodates.md", "info"), ("rotate-key.md", "error"),
    ]


def test_filename_and_subdirectory_checks(tmp_path):
    r = _lint(tmp_path, {"Bad_Name.md": _page(uuid="bad"), "sub/ok-page.md": _page(uuid="sub")})
    assert [(f.filename, f.severity) for f in _by_code(r, "spec-filename")] == [("Bad_Name.md", "warning")]
    assert [(f.filename, f.severity) for f in _by_code(r, "spec-subdir")] == [("sub/ok-page.md", "info")]


def test_hash_prefixed_title_as_summary_is_summary_shape(tmp_path):
    r = _lint(tmp_path, {"rotate-key.md": _page(title='"Rotate the key"', summary='"# Rotate the key"')})
    assert any("repeats the title" in f.message for f in _by_code(r, "summary-shape"))
