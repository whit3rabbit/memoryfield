---
uuid: sib-paper-flashattn-hardware
title: FlashAttention avoids materializing the full attention matrix in memory
summary: Instead of writing the N x N attention score matrix to slow HBM, FlashAttention tiles the computation into SRAM-sized blocks and computes softmax incrementally, cutting memory reads/writes rather than floating-point operations - the reason it speeds up training and inference without changing the math.
---
## Answer
Standard attention implementations compute the full N x N score matrix, write it to HBM, apply softmax, then read it back for the weighted sum with V - two full round trips through slow memory for a matrix that can be enormous at long sequence lengths.

FlashAttention restructures this as a tiled, fused kernel: it loads small blocks of Q, K, and V into fast on-chip SRAM, computes partial attention outputs and a running softmax normalization for each block, and never writes the intermediate N x N matrix to HBM at all.

The key point is that this is an IO-optimization, not an algorithmic approximation - the output is numerically identical to standard attention. The speedup comes from cutting memory bandwidth usage, since attention on modern GPUs is memory-bound rather than compute-bound at the sequence lengths where it matters.
