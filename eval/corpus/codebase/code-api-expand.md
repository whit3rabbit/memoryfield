---
uuid: code-api-expand
title: API: what `expand` parameters do
summary: Pass `expand[]=customer` to inline related objects; one level deep by default, recursion requires `expand[]=customer.invoices`.
status: active
tags: [api, expand]
---
## Answer
`?expand[]=customer` inlines the related `customer` object in the
response instead of returning just its ID. Multiple expands:
`?expand[]=customer&expand[]=line_items`.

Nested: `?expand[]=customer.invoices` (one level deeper, by
request only — otherwise unbounded).

