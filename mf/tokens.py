"""default_tokenize() — the single source of truth for token accounting.

PLAN.md section 1 budgets (session start < 200 tokens, per-lookup < 1,200)
are meaningless if `mf index`, `mf search`, and the eval harness each
count tokens differently. Extracted here so both sides call one function.
"""
from __future__ import annotations

import math


def default_tokenize(text: str) -> int:
    """Approximate tokens as max(len/4, word_count/0.75).

    The word-count term catches short-symbol-heavy content (commands,
    paths) that char/4 alone undercounts. We take the max of the two.
    This is a char/4 approximation, within ~15% of tiktoken cl100k for
    English prose -- precise enough for budget decisions at this scale.
    """
    if not text:
        return 0
    char_estimate = max(1, math.ceil(len(text) / 4))
    word_count = len(text.split())
    word_estimate = max(1, math.ceil(word_count / 0.75))
    return max(char_estimate, word_estimate)
