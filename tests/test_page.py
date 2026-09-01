import pytest

from mf.page import PageParseError, parse_page, slugify

VALID_PAGE = """\
---
uuid: page-001
title: "How to rotate the key"
summary: "Run make rotate-key"
status: active
tags: [auth, ops]
supersedes: [page-000]
source: runbooks/auth.md
writer: whit3rabbit
---

## Steps

Run `make rotate-key`.

## Rationale

Short overlap windows limit blast radius.
"""


def test_parses_required_and_extended_fields():
    page = parse_page(VALID_PAGE, filename="page1.md")
    assert page.uuid == "page-001"
    assert page.title == "How to rotate the key"
    assert page.summary == "Run make rotate-key"
    assert page.status == "active"
    assert page.tags == ["auth", "ops"]
    assert page.supersedes == ["page-000"]
    assert page.source == "runbooks/auth.md"
    assert page.writer == "whit3rabbit"


def test_splits_sections_in_order_with_slugs():
    page = parse_page(VALID_PAGE, filename="page1.md")
    assert [s.slug for s in page.sections] == ["steps", "rationale"]
    assert [s.ordinal for s in page.sections] == [0, 1]


def test_l1_is_first_section_body():
    page = parse_page(VALID_PAGE, filename="page1.md")
    assert page.l1 == "Run `make rotate-key`."


def test_missing_frontmatter_is_not_a_page():
    with pytest.raises(PageParseError):
        parse_page("# Just a heading\n\nSome text.", filename="readme.md")


def test_missing_uuid_is_rejected():
    text = "---\ntitle: No uuid here\n---\n\nBody.\n"
    with pytest.raises(PageParseError):
        parse_page(text, filename="bad.md")


def test_missing_title_is_rejected():
    text = "---\nuuid: page-002\n---\n\nBody.\n"
    with pytest.raises(PageParseError):
        parse_page(text, filename="bad.md")


def test_defaults_for_optional_fields():
    text = "---\nuuid: page-003\ntitle: Minimal\n---\n\nJust a body, no sections.\n"
    page = parse_page(text, filename="minimal.md")
    assert page.status == "active"
    assert page.tags == []
    assert page.summary == ""
    # No `##` headings: the whole body is one unnamed section.
    assert len(page.sections) == 1
    assert page.sections[0].slug == ""
    assert page.l1 == "Just a body, no sections."


def test_duplicate_headings_get_disambiguated_slugs():
    text = (
        "---\nuuid: page-004\ntitle: Dup headings\n---\n\n"
        "## Notes\nFirst.\n\n## Notes\nSecond.\n"
    )
    page = parse_page(text, filename="dup.md")
    assert [s.slug for s in page.sections] == ["notes", "notes-1"]


def test_sha256_changes_when_text_changes():
    a = parse_page(VALID_PAGE, filename="page1.md")
    b = parse_page(VALID_PAGE.replace("Rationale", "Reasoning"), filename="page1.md")
    assert a.sha256 != b.sha256


def test_slugify_strips_punctuation_and_lowercases():
    assert slugify("Don't do this!") == "don-t-do-this"
    assert slugify("  Spaced  Out  ") == "spaced-out"
