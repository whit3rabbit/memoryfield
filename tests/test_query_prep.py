from mf.query_prep import fts_query


def test_or_joins_kept_tokens():
    result = fts_query("rotate the JWT signing key")
    assert result.expr == '"rotate" OR "jwt" OR "signing" OR "key"'


def test_drops_stopwords_and_short_tokens():
    # Single-character tokens ("i", "a") never reach the tokenizer at all
    # (the regex requires 2+ chars), so only "do" shows up as dropped.
    result = fts_query("how do I rotate a key")
    assert "how" not in result.dropped
    assert result.dropped == ["do"]
    assert result.expr == '"how" OR "rotate" OR "key"'


def test_keeps_internal_hyphens():
    result = fts_query("bge-large embedding model")
    assert '"bge-large"' in result.expr


def test_quotes_never_reach_the_expression():
    # Tokenization only captures word chars, so literal quote characters
    # from the input can never appear as MATCH syntax.
    result = fts_query('search for "exact phrase" here')
    for token in ("search", "exact", "phrase", "here"):
        assert f'"{token}"' in result.expr


def test_empty_query_returns_empty_expression():
    result = fts_query("   ")
    assert result.expr == ""


def test_all_stopwords_returns_empty_expression_with_dropped_tokens():
    # "a" is a single char and never reaches the tokenizer (see above).
    result = fts_query("is the a of")
    assert result.expr == ""
    assert result.dropped == ["is", "the", "of"]
