---
uuid: paper-tok-special
title: "Tokenization: special tokens and their roles"
summary: "<bos>, <eos>, <pad>, <unk>, <mask> mark sequence boundaries, padding, unknown words, and masked positions; each model family has its own vocabulary."
status: active
tags: [tokenization, preprocessing]
source: "https://huggingface.co/docs/transformers/tokenizer_summary"
---
## Answer
Standard special tokens:
- `<bos>` / `<s>`: beginning of sequence.
- `<eos>` / `</s>`: end of sequence. Used for chat to mark turn boundaries.
- `<pad>`: padding for variable-length batches.
- `<unk>`: out-of-vocabulary (rarely seen with subword vocab).
- `<mask>`: masked language modeling (BERT).

Each tokenizer has its own. Always check the tokenizer's special tokens before fine-tuning.
