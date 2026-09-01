---
uuid: para-code-dm-money-bigint
title: How we represent currency values in the schema
summary: Money columns are `BIGINT` holding the smallest unit of the currency - never `FLOAT`, never `NUMERIC`.
---
## Answer
Every monetary column is a `BIGINT` and it stores the smallest
possible unit of whatever currency is involved - cents for USD,
pence for GBP, yen for JPY, and so on. Naming follows the pattern
`<amount>_<currency>`, so a USD price column would be
`amount_usd_cents`.

Two types are off limits here. `FLOAT` is out because binary
floating point cannot represent currency exactly, which produces
rounding errors that compound over many transactions. `NUMERIC`
technically works and avoids that problem, but it is noticeably
slower and most client SDKs handle it awkwardly compared to a
plain integer. Any currency conversion or formatting for display
happens at the API boundary, not in the stored value.
