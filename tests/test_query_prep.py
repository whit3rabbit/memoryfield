from mf.query_prep import fts_query


def test_or_joins_kept_tokens():
    result = fts_query("rotate the JWT signing key")
    assert result.expr == '"rotate" OR "jwt" OR "signing" OR "key"'


def test_drops_stopwords_and_short_tokens():
    # Single-character tokens ("i", "a") and stopwords are dropped, and
    # every dropped token is reported so a caller can see what was lost.
    result = fts_query("how do I rotate a key")
    assert "how" not in result.dropped
    assert result.dropped == ["do", "i", "a"]
    assert result.expr == '"how" OR "rotate" OR "key"'
    assert result.terms == ["how", "rotate", "key"]


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
    result = fts_query("is the a of")
    assert result.expr == ""
    assert result.dropped == ["is", "the", "a", "of"]


def test_digits_and_non_latin_words_are_terms():
    # HTTP status codes, version numbers, and non-Latin scripts used to be
    # dropped by a leading-ASCII-letter requirement.
    assert fts_query("HTTP 401 vs 403").terms == ["http", "401", "vs", "403"]
    assert fts_query("v2.5 migration").terms == ["v2", "migration"]
    assert fts_query("日本語 検索").terms == ["日本語", "検索"]
