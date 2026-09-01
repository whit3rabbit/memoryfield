---
uuid: paper-beam-search
title: Beam search: keep top-k partial hypotheses at each step
summary: At each decoding step, expand each hypothesis with all next tokens; keep top-k by cumulative log-probability; trades compute for search quality; greedy is beam=1.
status: active
tags: [beam-search, decoding]
source: https://en.wikipedia.org/wiki/Beam_search
---
## Answer
Beam search with beam size k:
- Start with <bos> as the only hypothesis.
- At each step: expand each hypothesis with all next tokens.
- Keep top-k by cumulative log-prob.
- Stop when all beams hit <eos> or max length.

Beam 1 = greedy. Beam 4-8 is typical for translation. Larger beams give diminishing returns.
