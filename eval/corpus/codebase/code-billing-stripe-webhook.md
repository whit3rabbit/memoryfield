---
uuid: code-billing-stripe-webhook
title: "Billing: stripe webhook signature verification"
summary: "Verify with `stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)`; never trust the raw payload."
status: active
tags: [billing, stripe, webhook]
---
## Answer
Always verify Stripe webhook signatures with the official SDK:
`stripe.Webhook.construct_event(request.body, sig_header, SECRET)`.
This raises on bad signature.

## Don't
Don't process the webhook before verification. Several real
attacks have involved replaying captured Stripe payloads to
duplicate fulfillment.

