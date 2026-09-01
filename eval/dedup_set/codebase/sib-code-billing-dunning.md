---
uuid: sib-code-billing-dunning
title: Billing - how sales tax is calculated per invoice line
summary: Tax is computed per line item using the customer's ship-to address at invoice time, not the billing address, with rates from a cache table refreshed nightly.
---
## Answer
Each invoice line gets its own tax calculation rather than one tax total for the whole invoice, since a single invoice can span line items with different product tax categories (SaaS seats vs. one-time hardware, for example).

The rate lookup uses the customer's `ship_to` address, not `billing_address` - important for customers whose billing contact sits in a different jurisdiction than where the service is actually used. Rates come from a local cache table (`tax_rates`) synced nightly from our tax provider. A rate lookup never calls the provider synchronously during invoice generation, to keep invoicing from depending on a third party's uptime.

Manual tax overrides on a line require finance approval and are logged in `tax_overrides`.
