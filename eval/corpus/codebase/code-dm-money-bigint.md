---
uuid: code-dm-money-bigint
title: "Data model: how monetary amounts are stored"
summary: "`BIGINT` storing the smallest currency unit (cents/pence/yen); never `FLOAT` or `NUMERIC` for money; conversion happens at API boundaries."
status: active
tags: [data-model, money]
---
## Answer
Amounts are `BIGINT` representing the smallest currency unit
(cents, pence, yen, etc.). The column's currency is named
`<amount>_<currency>` (e.g., `amount_usd_cents`).

## Don't
Don't use `NUMERIC` or `FLOAT` for money. Float gives you
wrong answers; numeric is fine but slower and harder to work
with in client SDKs.

