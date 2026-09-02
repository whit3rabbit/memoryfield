---
uuid: paper-flashattn-tiling
title: "FlashAttention: IO-aware exact attention via tiling"
summary: "Computes attention without materializing the N×N attention matrix in HBM; tiles the softmax into blocks that fit in SRAM; exact, not approximate."
status: active
tags: [flashattention, memory, kernel]
source: "https://arxiv.org/abs/2205.14135"
---
## Answer
Standard attention materializes the `N×N` attention matrix in HBM (`O(N^2)` memory).

FlashAttention tiles the computation: process blocks of Q,K,V that fit in SRAM, compute partial softmax, accumulate output, write final result.

The result is *exact* (not low-rank approximation), but `O(N)` HBM access instead of `O(N^2)`.

This gives 2-4x wallclock speedup and ~10x memory reduction for long contexts.
