"""fts_query() — the single source of truth for turning a natural-
language query into a forgiving SQLite FTS5 MATCH expression.

Shared between the eval FTS/hybrid baselines and (later) `mf search`'s
FTS stage, so this doesn't drift into two implementations the way
embedding_text once did (CLAUDE.md gotchas 2 and 3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+")

_STOPWORDS = {
    "a", "an", "the", "is", "of", "to", "in", "on", "for", "with",
    "and", "or", "do", "i", "you", "we", "it", "this", "that",
}


@dataclass
class FtsQuery:
    """An FTS5 MATCH expression, plus the tokens dropped building it.

    `dropped` exists so a caller can log when a query lost most of its
    content to stopword/short-token filtering (a likely cause of a
    weak-recall FTS lookup) without the library forcing a logging
    policy on them.
    """
    expr: str
    dropped: list[str] = field(default_factory=list)


def fts_query(text: str) -> FtsQuery:
    """Convert a natural-language query to a forgiving FTS5 MATCH expression.

    Strategy: tokenize, drop very short / stopword-ish tokens, OR-join
    the rest. This catches the common case where the user's wording
    doesn't exactly match the page's wording but shares enough
    vocabulary to be a hit. Pure prefix match (no quoting, no
    operators) is the safest mode.

    Quotes and other FTS5-special characters are never passed through:
    tokenization only captures word characters and internal hyphens, so
    anything else (quotes, colons, parens) is silently excluded rather
    than risking a MATCH syntax error.
    """
    all_tokens = _TOKEN_RE.findall(text.lower())
    kept: list[str] = []
    dropped: list[str] = []
    for t in all_tokens:
        if len(t) >= 2 and t not in _STOPWORDS:
            kept.append(t)
        else:
            dropped.append(t)
    if not kept:
        return FtsQuery(expr="", dropped=dropped)
    safe = [t.replace('"', '""') for t in kept]
    return FtsQuery(expr=" OR ".join(f'"{t}"' for t in safe), dropped=dropped)
