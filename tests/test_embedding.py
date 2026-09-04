import pytest

from mf.embedding import document_text, embedding_text, query_text


def test_embedding_text_joins_title_summary_l1():
    text = embedding_text("Title", "A summary.", "First section body.")
    assert text == "Title. A summary. First section body."


def test_embedding_text_with_empty_summary_and_l1():
    # ". " from the join survives `.strip()`, so this is "Only Title."
    # rather than a clean "Only Title" -- pre-existing behavior, not a
    # bug introduced by extracting this into a shared function.
    assert embedding_text("Only Title", "", "") == "Only Title."


def test_document_text_applies_nomic_prefix():
    text = document_text("T", "S", "L", "nomic")
    assert text == "search_document: T. S L"


def test_document_text_bge_prefix_is_empty():
    text = document_text("T", "S", "L", "bge")
    assert text == "T. S L"


def test_document_text_rejects_unknown_model_kind():
    with pytest.raises(ValueError):
        document_text("T", "S", "L", "unknown")


def test_query_text_nomic_prefix():
    assert query_text("how do I rotate keys", "nomic") == "search_query: how do I rotate keys"


def test_query_text_bge_prefix():
    text = query_text("how do I rotate keys", "bge")
    assert text == (
        "Represent this sentence for searching relevant passages: "
        "how do I rotate keys"
    )


def test_query_text_rejects_unknown_model_kind():
    with pytest.raises(ValueError):
        query_text("q", "unknown")
