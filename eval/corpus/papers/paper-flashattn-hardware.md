---
uuid: paper-flashattn-hardware
title: "FlashAttention: requires GPU SRAM and CUDA; not portable"
summary: "FlashAttention is GPU-specific (NVIDIA initially; AMD support came later); CPU/Apple Silicon versions exist but with smaller speedups."
status: active
tags: [flashattention, hardware]
source: "https://arxiv.org/abs/2205.14135"
---
## Answer
FlashAttention v1/v2 require NVIDIA GPUs (now AMD ROCm too, with some caveats). The kernel is hand-written CUDA relying on SRAM size and warp scheduling.

Apple Silicon and CPU backends exist but the speedup is smaller because the SRAM/HBM gap is less dramatic.
