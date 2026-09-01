---
uuid: sib-paper-auc-roc
title: PR curves beat ROC-AUC under heavy class imbalance
summary: When negatives vastly outnumber positives, ROC-AUC can look deceptively high because the false-positive rate denominator is dominated by negatives; precision-recall curves surface the same errors as a much bigger drop.
---
## Answer
ROC-AUC's false positive rate is FP / (FP + TN). When negatives massively outnumber positives (fraud detection, rare disease screening), TN is huge, so even a large absolute number of false positives barely moves the FPR - the ROC curve stays close to the top-left corner and AUC looks strong.

Precision, by contrast, is TP / (TP + FP): it's driven entirely by how many of the flagged cases were actually positive, with no large TN term diluting the signal. On a 1000:1 imbalance, a classifier with a respectable 0.95 AUC can still have single-digit precision at any threshold that catches most positives.

Rule of thumb: report precision-recall curves alongside or instead of ROC-AUC whenever the positive class is rare, since PR curves expose the imbalance-driven false-positive cost that ROC hides.
