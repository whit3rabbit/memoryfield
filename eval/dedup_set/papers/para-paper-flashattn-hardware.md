---
uuid: para-paper-flashattn-hardware
title: FlashAttention needs an NVIDIA or AMD GPU - it isn't portable
summary: The FlashAttention kernel is written in hand-tuned CUDA (and now ROCm) that depends on GPU SRAM capacity and warp scheduling; CPU and Apple Silicon ports exist but see much smaller speedups since those platforms lack the same SRAM-to-HBM gap.
---
## Answer
FlashAttention's speed comes from a kernel written specifically against GPU memory hierarchy details - how much fast SRAM is available per streaming multiprocessor, and how warps get scheduled onto it. Versions 1 and 2 of the reference implementation target NVIDIA CUDA; AMD ROCm support arrived later, with some feature gaps relative to CUDA.

Ports to CPU and Apple Silicon do exist, but they deliver noticeably smaller speedups than the GPU versions. The reason is architectural, not just an unoptimized port: the whole technique is built around exploiting a large gap between fast on-chip SRAM and slow off-chip HBM, and that gap is much less pronounced on CPU and Apple Silicon memory architectures.

Practically: don't expect FlashAttention's published speedup numbers to transfer to a non-CUDA/ROCm deployment target without re-measuring.
