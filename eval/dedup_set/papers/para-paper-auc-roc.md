---
uuid: para-paper-auc-roc
title: ROC-AUC score - probability a positive scores above a negative
summary: The area under the ROC curve equals the chance a randomly picked positive example outranks a randomly picked negative one; it runs from 0.5 (random guessing) to 1.0 (perfect separation) and doesn't depend on choosing a threshold.
---
## Answer
The ROC curve plots true positive rate against false positive rate as you sweep the classification threshold from one extreme to the other. The area beneath that curve, AUC, has a clean probabilistic reading: pick one positive example and one negative example at random, and AUC is the probability the classifier scores the positive one higher.

Scale: 0.5 sits at chance level (no better than a coin flip), 1.0 means every positive outranks every negative. Rough bands in practice - 0.7 to 0.8 is considered decent, 0.9 and above is strong separation.

Because it's computed by sweeping every possible threshold, AUC doesn't commit to any single operating point, which makes it the right metric to report when the deployment threshold hasn't been fixed yet.
