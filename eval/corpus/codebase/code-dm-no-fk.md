---
uuid: code-dm-no-fk
title: Data model: why we don't use foreign key constraints
summary: We enforce referential integrity at the application layer because delete-then-cascade order matters across services; FKs would lock too aggressively.
status: active
tags: [data-model, integrity]
---
## Answer
Foreign keys would force cascading deletes to lock in the
wrong order across services. We enforce the integrity in the
application layer, where we can control the order.

The tradeoff: occasional orphaned rows during partial
failures. We have a daily `orphan-check` job to detect them.

