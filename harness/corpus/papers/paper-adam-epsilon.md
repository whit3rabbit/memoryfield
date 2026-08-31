---
uuid: paper-adam-epsilon
title: Adam: epsilon in the denominator prevents division by zero
summary: `1e-8` is the default `eps`; adding it inside the sqrt avoids NaN when v_hat has zeros; larger eps dampens the update step.
status: active
tags: [adam, epsilon]
source: https://arxiv.org/abs/1412.6980
---
## Answer
`ε` (epsilon) appears in the denominator: `θ_t = θ_{t-1} - α * m_hat / (sqrt(v_hat) + ε)`.

Default `ε = 1e-8`. Larger values (e.g., `1e-6`) dampen the update for small-v_hat parameters and can improve stability for some tasks.
