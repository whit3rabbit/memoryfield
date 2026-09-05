import pytest
from mcp import Client

from mf import db, indexer, mcp_server, search, write
from mf.schema import EMBEDDING_DIM

pytestmark = pytest.mark.anyio

PAGE_ROTATE = """\
---
uuid: mcp-rotate
title: "How to rotate the signing key"
summary: "Run make rotate-key"
---

## Steps

Run `make rotate-key`.
"""

NEW_PAGE = """\
---
uuid: mcp-billing
title: "How billing retries failed payments"
summary: "Dunning levels 1-4"
---

## Steps

Failed payments trigger dunning_level increments.
"""


def _zero_vec() -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    return vec


def _near_dup_vec() -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[0] = 1.0
    vec[-1] = 0.1
    return vec


def _far_vec() -> list[float]:
    vec = [0.0] * EMBEDDING_DIM
    vec[1] = 1.0
    return vec


def _fake_embed_pages(pages, model_code):
    return {p.uuid: _zero_vec() for p in pages}


def _fake_embed_query(query, model_code):
    return _zero_vec()


def _fake_embed_page(page, model_code):
    return _zero_vec()


def _build_field(tmp_path, monkeypatch):
    monkeypatch.setattr(indexer, "_embed_pages", _fake_embed_pages)
    monkeypatch.setattr(search, "_embed_query", _fake_embed_query)
    monkeypatch.setattr(write, "_embed_page", _fake_embed_page)
    (tmp_path / "rotate.md").write_text(PAGE_ROTATE)
    db.init_field(tmp_path)
    conn = db.open_field(tmp_path)
    indexer.index_field(tmp_path, conn)
    conn.close()


async def test_search_returns_same_shape_as_cli_json(tmp_path, monkeypatch):
    _build_field(tmp_path, monkeypatch)
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("search", {"query": "rotate signing key", "field": str(tmp_path)})
    assert result.is_error is not True
    data = result.structured_content
    assert data["confidence"] in ("high", "low", "none")
    assert data["results"][0]["uuid"] == "mcp-rotate"


async def test_search_no_field_raises_tool_error(tmp_path):
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("search", {"query": "anything", "field": str(tmp_path)})
    assert result.is_error is True
    assert "mf init" in getattr(result.content[0], "text", "")


async def test_read_wraps_list_under_results_key(tmp_path, monkeypatch):
    _build_field(tmp_path, monkeypatch)
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("read", {"refs": ["mcp-rotate"], "field": str(tmp_path)})
    assert result.is_error is not True
    data = result.structured_content
    assert data["results"][0]["uuid"] == "mcp-rotate"
    assert data["results"][0]["tier"] == "L1"


async def test_read_not_found_raises_tool_error(tmp_path, monkeypatch):
    _build_field(tmp_path, monkeypatch)
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("read", {"refs": ["does-not-exist"], "field": str(tmp_path)})
    assert result.is_error is True
    assert "not found" in getattr(result.content[0], "text", "")


async def test_write_new_page_succeeds(tmp_path, monkeypatch):
    _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _far_vec())
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(
            "write", {"text": NEW_PAGE, "dest": "billing.md", "field": str(tmp_path)}
        )
    assert result.is_error is not True
    data = result.structured_content
    assert data["written"] is True
    assert data["uuid"] == "mcp-billing"
    assert (tmp_path / "billing.md").exists()


async def test_write_duplicate_blocked_returns_candidates(tmp_path, monkeypatch):
    _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(write, "_embed_page", lambda page, model_code: _near_dup_vec())
    dup_text = NEW_PAGE.replace("mcp-billing", "mcp-billing-dup")
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool(
            "write", {"text": dup_text, "dest": "billing-dup.md", "field": str(tmp_path)}
        )
    assert result.is_error is not True
    data = result.structured_content
    assert data["written"] is False
    assert len(data["duplicates"]) >= 1


async def test_raw_add_appends_and_dedupes(tmp_path):
    db.init_field(tmp_path)
    async with Client(mcp_server.mcp) as client:
        first = await client.call_tool("raw_add", {"text": "Session extract.", "field": str(tmp_path)})
        second = await client.call_tool("raw_add", {"text": "Session extract.", "field": str(tmp_path)})
    assert first.structured_content["written"] is True
    assert second.structured_content["written"] is False
    assert len(list((tmp_path / "raw").glob("*.md"))) == 1


async def test_raw_add_empty_text_raises_tool_error(tmp_path):
    db.init_field(tmp_path)
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("raw_add", {"text": "   ", "field": str(tmp_path)})
    assert result.is_error is True


async def test_server_default_field_applies_when_call_omits_it(tmp_path, monkeypatch):
    _build_field(tmp_path, monkeypatch)
    monkeypatch.setattr(mcp_server, "_DEFAULT_FIELD", ".")
    mcp_server.set_default_field(str(tmp_path))
    async with Client(mcp_server.mcp) as client:
        result = await client.call_tool("search", {"query": "rotate signing key"})
    assert result.is_error is not True
    assert result.structured_content["results"][0]["uuid"] == "mcp-rotate"
