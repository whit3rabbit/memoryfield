---
uuid: paper-mamba-selective
title: "Mamba: the selective mechanism makes the recurrence input-dependent"
summary: "Unlike S4 (which uses fixed A, B, C), Mamba makes the discretization parameters functions of the input; this lets the model selectively remember or forget."
status: active
tags: [mamba, ssm, design]
source: "https://arxiv.org/abs/2312.00752"
---
## Answer
S4 (predecessor): fixed A, B, C parameters per layer; can't adapt to input.

Mamba (improvement): makes B, C, and the discretization step size functions of the input:
```
B = W_B * x
C = W_C * x
delta = softplus(W_delta * x)
```

This lets the model selectively choose what to keep in state and what to overwrite -- the key capability missing from earlier SSMs.
