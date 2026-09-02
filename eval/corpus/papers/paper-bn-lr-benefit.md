---
uuid: paper-bn-lr-benefit
title: "BatchNorm: enables higher learning rates and reduces the importance of careful initialization"
summary: "By keeping activations normalized, gradients don't explode/vanish as easily, so larger learning rates become safe."
status: active
tags: [batchnorm, training, lr]
source: "https://arxiv.org/abs/1502.03167"
---
## Answer
BatchNorm reduces internal covariate shift (the change in layer input distributions during training). This:
1. Allows larger learning rates (gradients don't explode).
2. Reduces sensitivity to weight initialization.
3. Acts as a mild regularizer.
