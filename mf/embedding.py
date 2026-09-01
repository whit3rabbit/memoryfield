"""embedding_text() — the single source of truth for what gets embedded.

Codifies the M0.5 lesson (CLAUDE.md gotchas 2 and 3): embedding input
text and model task-prefix conventions must live in exactly one place.
A one-line bug in the embedder input string cost 30 points of dense
recall on one domain before this existed; a missing BGE query prefix
cost 8 more. `index`, `search`, and (later) `write`'s dedup gate must
all call this instead of building the text themselves.
"""
from __future__ import annotations

# Document-side task prefix, per model. Nomic is asymmetric and requires
# it; BGE-large is symmetric in raw form but conventionally takes the
# empty prefix on the document side (its asymmetry is query-side only,
# see QUERY_PREFIXES).
DOCUMENT_PREFIXES: dict[str, str] = {
    "nomic": "search_document: ",
    "bge": "",
}

# Query-side task prefix, per model. fastembed adds the nomic prefix
# convention implicitly for some call paths but never adds BGE's, so
# both are made explicit here rather than relying on library behavior.
QUERY_PREFIXES: dict[str, str] = {
    "nomic": "search_query: ",
    "bge": "Represent this sentence for searching relevant passages: ",
}


def embedding_text(title: str, summary: str, l1: str) -> str:
    """Title + summary + first body section (L0+L1 per PLAN.md).

    This is the canonical text embedded on the document side, before
    any model-specific prefix is applied. Falls back to title alone if
    summary and l1 are both empty, so a page is never embedded as "".
    """
    piece = f"{title}. {summary} {l1}".strip()
    return piece or title


def document_text(title: str, summary: str, l1: str, model_kind: str) -> str:
    """`embedding_text()` with the model's document-side prefix applied."""
    if model_kind not in DOCUMENT_PREFIXES:
        raise ValueError(f"unknown model_kind: {model_kind!r}")
    return DOCUMENT_PREFIXES[model_kind] + embedding_text(title, summary, l1)


def query_text(query: str, model_kind: str) -> str:
    """A raw query string with the model's query-side prefix applied."""
    if model_kind not in QUERY_PREFIXES:
        raise ValueError(f"unknown model_kind: {model_kind!r}")
    return QUERY_PREFIXES[model_kind] + query
