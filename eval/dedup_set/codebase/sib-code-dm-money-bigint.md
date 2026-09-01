---
uuid: sib-code-dm-money-bigint
title: Data model - how historical exchange rates are stored
summary: Rates live in a `fx_rates` table keyed by currency pair and `effective_at`, stored as `BIGINT` micro-units, never overwritten.
---
## Answer
Exchange rates are tracked in a dedicated `fx_rates` table, one
row per `(base_currency, quote_currency, effective_at)` tuple.
The rate itself is stored as a `BIGINT` scaled by 1,000,000 (a
rate of 1.2345 USD/EUR is stored as `1234500`), which keeps the
same "no floating point" discipline used elsewhere for money.

Rows are append-only: a new rate never overwrites an old one, it
inserts a new row with a later `effective_at`. This lets any past
transaction be re-priced against the rate that was actually in
effect at the time, which matters for refunds and financial
reporting. Lookups use `effective_at <= transaction_time ORDER BY
effective_at DESC LIMIT 1`. Rates are pulled from the provider
every 15 minutes.
