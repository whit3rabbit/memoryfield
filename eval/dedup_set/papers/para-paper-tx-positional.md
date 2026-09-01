---
uuid: para-paper-tx-positional
title: Transformer position information comes from fixed sine and cosine waves per dimension
summary: Even embedding dimensions get sin(pos / 10000^(2i/d_model)), odd dimensions get the matching cosine, giving every sequence position a unique fixed vector without any learned parameters.
---
## Answer
Because self-attention has no built-in sense of token order, the transformer injects position information by adding a fixed vector to each token embedding before the first layer. That vector is built dimension by dimension: even-indexed dimensions use a sine wave, odd-indexed dimensions use the cosine at the same frequency, and the frequency itself varies smoothly across dimensions via the 10000^(2i/d_model) term.

The wavelengths span from short (early dimensions) to very long (later dimensions), so nearby positions differ mostly in the fast-varying dimensions while distant positions differ across the whole spectrum. Because these encodings are computed with a formula rather than learned, the authors expected the model would be able to generalize to sequence lengths longer than anything seen in training, though later work found this extrapolation benefit was weaker in practice than the original hypothesis suggested.
