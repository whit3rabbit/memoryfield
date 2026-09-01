---
uuid: sib-paper-bert-size
title: BERT is pretrained with masked language modeling plus next sentence prediction
summary: BERT's pretraining combines two objectives - predicting randomly masked tokens (15% of input, mostly replaced with [MASK]) and a binary next-sentence-prediction task over sentence pairs; later work found NSP contributes little.
---
## Answer
BERT's pretraining recipe has two objectives run simultaneously. Masked language modeling (MLM) randomly selects 15% of input tokens; of those, 80% are replaced with a [MASK] token, 10% with a random token, and 10% left unchanged, and the model predicts the original token at each masked position.

Next sentence prediction (NSP) feeds the model two sentences separated by a [SEP] token and asks it to classify whether the second sentence actually follows the first in the source text, or is a random sentence from elsewhere in the corpus.

Follow-up work (notably RoBERTa) found that removing NSP entirely and training longer on MLM alone did not hurt downstream performance, and in some cases improved it - the objective added training-time cost without a clear payoff.
