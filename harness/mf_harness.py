"""M0 eval harness — core utilities.

Single source of truth for:
  - corpus loading (memoryfield-spec pages)
  - query loading
  - metrics: P@3, R@5, MRR, stub-end rate
  - token accounting (char/4 approximation, plus a real tokenizer stub)

Stdlib only — no numpy, no fastembed, no yaml. The whole point of M0 is
the harness works on a clean checkout. Deps come in M1.
"""
from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Token accounting
# ---------------------------------------------------------------------------
#
# PLAN.md §1 budgets:
#   - session start: < 200 tokens
#   - per lookup: < 1,200 tokens
#
# We use a char/4 approximation as the default. It's within ~15% of tiktoken
# cl100k for English prose, which is more than precise enough for budget
# decisions at this scale. Callers that want exact counts can pass a custom
# `tokenize` callable (e.g. loaded with tiktoken) — but the harness should
# not require it.


def default_tokenize(text: str) -> int:
    """Approximate tokens as max(len/4, word_count/0.75).

    The word-count term catches short-symbol-heavy content (commands, paths)
    that char/4 alone undercounts. We take the max of the two.
    """
    if not text:
        return 0
    char_estimate = max(1, math.ceil(len(text) / 4))
    word_count = len(text.split())
    word_estimate = max(1, math.ceil(word_count / 0.75))
    return max(char_estimate, word_estimate)


# ---------------------------------------------------------------------------
# Memoryfield-spec page loading
# ---------------------------------------------------------------------------
#
# Minimal Markdown frontmatter parser. Handles `---` delimited YAML-ish
# blocks with `key: value` and `key: [a, b, c]` lines. Good enough for M0's
# generated corpus; full YAML comes in M1.

FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL
)


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
        """First section (the 'answer-first' portion)."""
        if self.body_sections:
            return self.body_sections[0][1]
        return self.body

    @property
    def full_text(self) -> str:
        """Title + summary + body, for full-corpus grep."""
        return f"{self.title}\n{self.summary}\n{self.body}".strip()


def _parse_frontmatter(blob: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(blob)
    if not m:
        return {}, blob
    fm_blob, body = m.group(1), m.group(2)
    fm: dict = {}
    for line in fm_blob.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if inner:
                fm[k] = [x.strip().strip('"').strip("'") for x in inner.split(",")]
            else:
                fm[k] = []
        else:
            fm[k] = v.strip('"').strip("'")
    return fm, body


_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Return list of (heading, content) for `## heading` sections.

    The preamble before any `##` is returned as ("", preamble).
    """
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return [("", body.strip())]
    out = []
    if matches[0].start() > 0:
        out.append(("", body[: matches[0].start()].strip()))
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((heading, body[start:end].strip()))
    return out


def load_page(path: Path) -> Page:
    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    return Page(
        uuid=fm.get("uuid") or path.stem,
        filename=str(path),
        title=fm.get("title") or path.stem,
        summary=fm.get("summary", ""),
        status=fm.get("status", "active"),
        tags=fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
        body=body.strip(),
        body_sections=_split_sections(body),
        tokens=default_tokenize(text),
        source=fm.get("source", ""),
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
            raise ValueError(f"Bad query line in {path}: {line!r}\n{e}")
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


def bootstrap_ci(values: list[int], stat="mean", n_resamples: int = 1000,
                 alpha: float = 0.05, rng_seed: int = 0) -> tuple[float, float, float]:
    """Return (point_estimate, ci_low, ci_high) for `stat` over `values`.

    `stat` may be 'mean' or 'sum'. values are 0/1 ints.
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
