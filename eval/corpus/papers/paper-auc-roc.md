---
uuid: paper-auc-roc
title: "AUC-ROC: area under the receiver operating characteristic curve"
summary: "AUC = probability that a random positive ranks above a random negative; 0.5 = random; 1.0 = perfect; threshold-invariant metric for binary classification."
status: active
tags: [auc, evaluation, classification]
source: "https://en.wikipedia.org/wiki/Receiver_operating_characteristic"
---
## Answer
ROC curve: true positive rate vs false positive rate as the classification threshold varies.

AUC = area under that curve.

Interpretation: probability that a randomly chosen positive example is ranked higher than a randomly chosen negative example.

- 0.5 = random
- 1.0 = perfect separation
- 0.7-0.8 = decent
- 0.9+ = strong

Threshold-invariant -- good when the operating threshold isn't fixed.
