"""Build merged per-domain query files for the M0.5 eval.

Inputs:
  - eval/queries/<domain>/queries.jsonl (original lexical queries)
  - eval/paraphrased_queries.jsonl (paraphrases + no-answer queries)
  - eval/query_type_tags.jsonl (qid -> topical/entity)

Output:
  - eval/queries/<domain>/queries.jsonl (overwritten with merged set,
    including paraphrases and no-answer queries; query_kind + query_type
    fields populated; answer_uuids resolved to real page UUIDs)

For no-answer queries, answer_uuids is empty.

For paraphrases, the original_qid is used to look up the original answer
uuids, then they're mapped through the title-to-uuid resolution in
build_corpus.py's slug maps.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
ORIG_CODE = ROOT / "queries" / "codebase" / "queries.jsonl"
ORIG_PAPERS = ROOT / "queries" / "papers" / "queries.jsonl"
PARAPHRASED = ROOT / "paraphrased_queries.jsonl"
TAGS = ROOT / "query_type_tags.jsonl"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_title_to_uuid(corpus_dir: Path) -> dict[str, str]:
    """Map page title -> uuid by reading the page frontmatter."""
    out = {}
    for p in corpus_dir.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        for line in m.group(1).splitlines():
            if line.startswith("title:"):
                title = line.split(":", 1)[1].strip()
                uuid = p.stem
                out[title] = uuid
                break
    return out


def main() -> int:
    code_titles = build_title_to_uuid(ROOT / "corpus" / "codebase")
    papers_titles = build_title_to_uuid(ROOT / "corpus" / "papers")

    # Existing queries, normalized to include query_kind + query_type
    code_orig = []
    for q in load_jsonl(ORIG_CODE):
        code_orig.append({
            "qid": q["qid"],
            "text": q["text"],
            "answer_uuids": q["answer_uuids"],
            "stub_sufficient": q.get("stub_sufficient", False),
            "query_kind": "lexical",
            "query_type": "entity",  # filled in below from tags
        })
    papers_orig = []
    for q in load_jsonl(ORIG_PAPERS):
        papers_orig.append({
            "qid": q["qid"],
            "text": q["text"],
            "answer_uuids": q["answer_uuids"],
            "stub_sufficient": q.get("stub_sufficient", False),
            "query_kind": "lexical",
            "query_type": "entity",
        })

    # Apply query_type tags
    tags = {row["qid"]: row["query_type"] for row in load_jsonl(TAGS)}
    for q in code_orig + papers_orig:
        q["query_type"] = tags.get(q["qid"], q["query_type"])

    # Build merged per-domain sets
    merged_code = list(code_orig)
    merged_papers = list(papers_orig)

    # Paraphrases + no-answer queries
    paraphrased = load_jsonl(PARAPHRASED)
    n_paraphrase_added = 0
    n_no_answer_added = 0
    n_unresolved_titles = 0
    for q in paraphrased:
        new_q = {
            "qid": q["qid"],
            "text": q["text"],
            "answer_uuids": [],  # filled below for paraphrases
            "stub_sufficient": False,
            "query_kind": q["query_kind"],
            "query_type": q.get("query_type", "entity"),
        }
        if q["query_kind"] == "paraphrased":
            # Resolve expected_pages (titles) -> uuids
            corpus_titles = code_titles if q["domain"] == "code" else papers_titles
            resolved = []
            for title in q.get("expected_pages", []):
                uuid = corpus_titles.get(title)
                if uuid:
                    resolved.append(uuid)
                else:
                    n_unresolved_titles += 1
                    print(f"  WARN: title not in {q['domain']} corpus: {title!r}")
            new_q["answer_uuids"] = resolved
            # Inherit query_type from the original
            orig_qid = q.get("original_qid")
            if orig_qid and orig_qid in tags:
                new_q["query_type"] = tags[orig_qid]
            # Inherit stub_sufficient from the original
            orig_pool = merged_code if q["domain"] == "code" else merged_papers
            orig = next((oq for oq in orig_pool if oq["qid"] == orig_qid), None)
            if orig is not None:
                new_q["stub_sufficient"] = orig.get("stub_sufficient", False)
            n_paraphrase_added += 1
        else:
            n_no_answer_added += 1

        if q["domain"] == "code":
            merged_code.append(new_q)
        elif q["domain"] == "papers":
            merged_papers.append(new_q)
        else:
            print(f"  WARN: unknown domain {q['domain']} for {q['qid']}")

    # Write merged files (overwrite)
    ORIG_CODE.parent.mkdir(parents=True, exist_ok=True)
    ORIG_PAPERS.parent.mkdir(parents=True, exist_ok=True)
    ORIG_CODE.write_text("\n".join(json.dumps(q) for q in merged_code) + "\n")
    ORIG_PAPERS.write_text("\n".join(json.dumps(q) for q in merged_papers) + "\n")

    print(f"wrote {len(merged_code)} code queries "
          f"({sum(1 for q in merged_code if q['query_kind']=='lexical')} lexical, "
          f"{sum(1 for q in merged_code if q['query_kind']=='paraphrased')} paraphrased, "
          f"{sum(1 for q in merged_code if q['query_kind'].startswith('no_answer'))} no_answer)")
    print(f"wrote {len(merged_papers)} papers queries "
          f"({sum(1 for q in merged_papers if q['query_kind']=='lexical')} lexical, "
          f"{sum(1 for q in merged_papers if q['query_kind']=='paraphrased')} paraphrased, "
          f"{sum(1 for q in merged_papers if q['query_kind'].startswith('no_answer'))} no_answer)")
    print(f"added: {n_paraphrase_added} paraphrases, {n_no_answer_added} no-answer")

    if n_unresolved_titles:
        print(f"  ({n_unresolved_titles} paraphrase titles could not be resolved to UUIDs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
