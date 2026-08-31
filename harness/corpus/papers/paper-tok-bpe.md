---
uuid: paper-tok-bpe
title: Tokenization: BPE, WordPiece, and SentencePiece
summary: Subword tokenization splits rare words into common pieces; BPE iteratively merges frequent pairs; WordPiece uses likelihood-based merges; SentencePiece is language-agnostic.
status: active
tags: [tokenization, preprocessing]
source: https://arxiv.org/abs/1508.07909
---
## Answer
Subword tokenization addresses the open-vocabulary problem:

- **BPE (Byte Pair Encoding)**: start with characters; iteratively merge the most frequent adjacent pair. Used by GPT.
- **WordPiece**: like BPE but uses likelihood-weighted merges. Used by BERT.
- **SentencePiece**: language-agnostic; treats input as raw bytes/unicode. Used by LLaMA.

All produce a fixed vocabulary (32k-200k tokens) and handle unseen words by splitting.
