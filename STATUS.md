# MF — Status

## What's committed here

This is the M0 + M0.5 eval harness plus the canonical PLAN.md. **No tool
implementation yet** (no `mf init`, `mf index`, `mf search`, `mf read`).
The CLI ships in M1.

## Eval state at this commit

All M0.5 baselines ran end-to-end on the expanded 458-query set EXCEPT
hybrid (FTS + nomic RRF). Hybrid was running when a foreground tool-call
limit fired and the process was killed mid-flight; the partial hybrid
results were lost. Re-run with:

```
~/.hermes/hermes-agent/venv/bin/python3 -m harness.run_baselines --baseline hybrid
```

The other 10 (baseline × domain) cells are present in
`harness/results/*.json` and aggregated in `harness/results/summary.json`.

## M0.5 exit criteria

- [x] Real dense baselines (nomic, bge-large) integrated
- [x] Paraphrased queries generated blind to pages
- [x] No-answer queries added (adjacent + impossible)
- [x] Topical vs entity tagging of all queries
- [x] De-biased stub-end labels
- [x] Per-axis breakdown in `harness/axis_breakdown.md`
- [ ] `M0.5_REPORT.md` generated (pending headline-correction pass)
- [ ] Hybrid baseline re-run

## Subagent-generated artifacts (cannot be regenerated identically)

These files were produced by background subagents with non-zero sampling
temperature. They are committed because:

- Paraphrases (`harness/paraphrased_queries.jsonl`): regenerating would
  yield a different set. Median Jaccard 0.29 with originals; max 0.50.
- Topical/entity tags (`harness/query_type_tags.jsonl`): reasonable to
  reproduce but the exact labels may differ.
- De-biased stub judgments (`harness/stub_sufficiency_debiased.jsonl`):
  99.1% sufficient; the two "insufficient" cases are substantive
  disagreements, not noise.

If anyone needs to regenerate, the same three subagent goals can be
re-dispatched with the same input files.
