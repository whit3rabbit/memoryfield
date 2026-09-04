"""M0 eval harness — core utilities.

Single source of truth for:
  - corpus loading (memoryfield-spec pages)
  - query loading
  - metrics: P@3, R@5, MRR, stub-end rate

Token accounting is mf/tokens.py's job (single source of truth shared
with mf index/search); this module just imports it.

Stdlib plus the mf package itself: no numpy, no fastembed. Pages are
parsed by mf.page.load_page, the same parser `mf index` runs, so every
baseline number is measured against the corpus as the shipped tool sees
it (the harness carried its own frontmatter parser until 2026-09-03;
tests/test_eval_harness.py holds the two to parity on the 157-page
corpus before that swap was made).
"""
from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from mf.page import PageParseError
from mf.page import load_page as _mf_load_page
from mf.tokens import default_tokenize

# ---------------------------------------------------------------------------
# Token accounting
# ---------------------------------------------------------------------------
#
# PLAN.md §1 budgets:
#   - session start: < 200 tokens
#   - per lookup: < 1,200 tokens
#
# default_tokenize() lives in mf/tokens.py (single source of truth shared
# with mf index/search) and is re-imported above.

# ---------------------------------------------------------------------------
# Memoryfield-spec page loading
# ---------------------------------------------------------------------------
#
# Pages are memoryfield-spec Markdown; mf.page does the parsing.

@dataclass
class Page:
    uuid: str
    filename: str
    title: str
    summary: str
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    body: str = ""
    body_sections: list[tuple[str, str]] = field(default_factory=list)
    tokens: int = 0
    source: str = ""

    @property
    def body_l1(self) -> str:
        """The answer-first portion: any preamble plus the first `##`
        section, matching mf.page.Page.l1."""
        if not self.body_sections:
            return self.body
        parts: list[str] = []
        for heading, content in self.body_sections:
            if content:
                parts.append(content)
            if heading:
                break
        return "\n\n".join(parts)

    @property
    def full_text(self) -> str:
        """Title + summary + body, for full-corpus grep."""
        return f"{self.title}\n{self.summary}\n{self.body}".strip()


def load_page(path: Path) -> Page:
    """The harness's Page view of a corpus file, parsed by mf.page."""
    try:
        page = _mf_load_page(path, filename=str(path))
    except PageParseError:
        # A corpus file that isn't a page: keep the harness permissive
        # (it never indexed such a file as anything but its stem).
        text = path.read_text(encoding="utf-8", errors="replace")
        return Page(uuid=path.stem, filename=str(path), title=path.stem, summary="",
                    body=text.strip(), body_sections=[("", text.strip())],
                    tokens=default_tokenize(text))
    return Page(
        uuid=page.uuid,
        filename=str(path),
        title=page.title,
        summary=page.summary,
        status=page.status,
        tags=list(page.tags),
        body=page.body,
        body_sections=[(s.heading, s.body) for s in page.sections],
        tokens=default_tokenize(path.read_text(encoding="utf-8-sig")),
        source=page.source,
    )


def load_corpus(corpus_dir: Path) -> dict[str, Page]:
    pages: dict[str, Page] = {}
    for path in sorted(corpus_dir.rglob("*.md")):
        # Spec: implementations MUST NOT index subdirectories named `raw/`
        if any(part == "raw" for part in path.parts):
            continue
        page = load_page(path)
        pages[page.uuid] = page
    return pages


# ---------------------------------------------------------------------------
# Query labels
# ---------------------------------------------------------------------------


@dataclass
class Query:
    qid: str
    text: str
    answer_uuids: list[str]  # any of these counts as a hit (P/R)
    stub_sufficient: bool    # is the answer in the stub summary?
    domain: str
    query_kind: str = "lexical"  # "lexical" | "paraphrased" | "no_answer_adjacent" | "no_answer_impossible"
    query_type: str = "entity"   # "entity" | "topical"


def load_queries(path: Path, domain: str) -> list[Query]:
    """Load queries from a JSONL file.

    Each line is a JSON object. Optional fields:
      - `query_kind`: "lexical" (default), "paraphrased", "no_answer_*"
      - `query_type`: "entity" (default), "topical"
    """
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Bad query line in {path}: {line!r}\n{e}") from e
        out.append(
            Query(
                qid=obj["qid"],
                text=obj["text"],
                answer_uuids=list(obj.get("answer_uuids", [])),
                stub_sufficient=bool(obj.get("stub_sufficient", False)),
                domain=domain,
                query_kind=obj.get("query_kind", "lexical"),
                query_type=obj.get("query_type", "entity"),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class LookupTrace:
    """One retrieval trace. Enough to compute all metrics."""

    qid: str
    baseline: str
    rank: int | None            # 1-based rank of first relevant page
    topk_uuids: list[str]
    stub_tokens: int            # tokens if agent stops at stub
    l1_tokens: int              # tokens if agent reads L1 of top-1
    full_tokens: int            # tokens if agent reads the full body of top-1
    ended_at_stub: bool         # would stub summary have been enough?


@dataclass
class BaselineMetrics:
    baseline: str
    domain: str
    n_queries: int
    p_at_3: float
    p_at_5: float
    r_at_5: float
    mrr: float
    stub_end_rate: float
    stub_end_given_hit_rate: float
    tokens_stub_median: float
    tokens_stub_p95: float
    tokens_l1_median: float
    tokens_full_median: float
    details_path: Path
    p_at_3_ci: tuple[float, float, float] = (0.0, 0.0, 0.0)
    p_at_5_ci: tuple[float, float, float] = (0.0, 0.0, 0.0)
    r_at_5_ci: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mrr_ci: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def as_dict(self) -> dict:
        return {
            "baseline": self.baseline,
            "domain": self.domain,
            "n_queries": self.n_queries,
            "p_at_3": self.p_at_3,
            "p_at_5": self.p_at_5,
            "r_at_5": self.r_at_5,
            "mrr": self.mrr,
            "stub_end_rate": self.stub_end_rate,
            "stub_end_given_hit_rate": self.stub_end_given_hit_rate,
            "tokens_stub_median": self.tokens_stub_median,
            "tokens_stub_p95": self.tokens_stub_p95,
            "tokens_l1_median": self.tokens_l1_median,
            "tokens_full_median": self.tokens_full_median,
            "p_at_3_ci_low": self.p_at_3_ci[1],
            "p_at_3_ci_high": self.p_at_3_ci[2],
            "p_at_5_ci_low": self.p_at_5_ci[1],
            "p_at_5_ci_high": self.p_at_5_ci[2],
            "r_at_5_ci_low": self.r_at_5_ci[1],
            "r_at_5_ci_high": self.r_at_5_ci[2],
            "mrr_ci_low": self.mrr_ci[1],
            "mrr_ci_high": self.mrr_ci[2],
            "details": str(self.details_path),
        }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def bootstrap_ci(values: Sequence[float], stat="mean", n_resamples: int = 1000,
                 alpha: float = 0.05, rng_seed: int = 0) -> tuple[float, float, float]:
    """Return (point_estimate, ci_low, ci_high) for `stat` over `values`.

    `stat` may be 'mean' or 'sum'. `values` are usually 0/1 ints (P@k
    hits) but any bounded floats work the same way (e.g. per-query R@5
    or MRR contributions, which are fractional, not binary).
    Resampling is non-parametric (sampling with replacement).
    """
    if not values:
        return 0.0, 0.0, 0.0
    rng = random.Random(rng_seed)
    n = len(values)
    if stat == "mean":
        point = sum(values) / n
    elif stat == "sum":
        point = float(sum(values))
    else:
        raise ValueError(f"unknown stat {stat}")
    samples = []
    for _ in range(n_resamples):
        s = sum(rng.choice(values) for _ in range(n))
        samples.append(s / n if stat == "mean" else s)
    samples.sort()
    lo_idx = int((alpha / 2) * n_resamples)
    hi_idx = int((1 - alpha / 2) * n_resamples) - 1
    return point, samples[lo_idx], samples[hi_idx]


# ---------------------------------------------------------------------------
# Stub rendering
# ---------------------------------------------------------------------------
#
# The harness needs to measure tokens the same way the agent will see them.
# `render_stub` is the canonical stub format from PLAN.md §2.


def render_stub(page: Page, include_status: bool = True) -> str:
    parts = [f"- [{page.uuid}] {page.title}"]
    if page.summary:
        parts.append(f"    {page.summary}")
    if include_status and page.status != "active":
        parts.append(f"    status: {page.status}")
    return "\n".join(parts)


def stub_tokens(page: Page) -> int:
    return default_tokenize(render_stub(page))


def l1_tokens(page: Page) -> int:
    return stub_tokens(page) + default_tokenize(page.body_l1)


def full_tokens(page: Page) -> int:
    return stub_tokens(page) + default_tokenize(page.body)


# ---------------------------------------------------------------------------
# Tiny TF-IDF scorer (used by `dense` baseline as a deterministic stand-in)
# ---------------------------------------------------------------------------


def build_tfidf(corpus: Iterable[Page]) -> tuple[list[list[str]], dict[str, float], Counter]:
    docs: list[list[str]] = []
    df: Counter = Counter()
    n_docs = 0
    for page in corpus:
        terms = _tokenize(page.full_text)
        docs.append(terms)
        n_docs += 1
        for term in set(terms):
            df[term] += 1
    idf: dict[str, float] = {
        term: math.log((1 + n_docs) / (1 + freq)) + 1
        for term, freq in df.items()
    }
    return docs, idf, df


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./-]+")


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def tfidf_vector(terms: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf: Counter = Counter(terms)
    total = sum(tf.values()) or 1
    return {term: (count / total) * idf.get(term, 0.0) for term, count in tf.items()}


def cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[k] * b[k] for k in common)
    denom_a = math.sqrt(sum(v * v for v in a.values()))
    denom_b = math.sqrt(sum(v * v for v in b.values()))
    if denom_a == 0 or denom_b == 0:
        return 0.0
    return num / (denom_a * denom_b)
