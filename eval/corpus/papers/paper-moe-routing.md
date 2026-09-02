---
uuid: paper-moe-routing
title: "Sparse MoE: route each token to top-k experts out of N total"
summary: "Router network produces N logits; top-k are selected (typically k=2); only those experts process the token; total compute stays low while parameter count grows."
status: active
tags: [moe, sparse, transformer]
source: "https://arxiv.org/abs/1701.06538"
---
## Answer
Sparse Mixture of Experts:
- N expert FFN sub-networks (e.g., N=8 to 64).
- Router computes logits for each expert per token.
- Top-k experts (typically k=2) process each token.
- Output is a weighted sum of the selected experts' outputs.

Total parameters grow with N, but compute per token stays roughly constant. This is how Mixtral 8x7B has ~47B params but compute similar to ~13B dense.
