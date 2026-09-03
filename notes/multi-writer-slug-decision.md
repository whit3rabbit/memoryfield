---
uuid: mf-multi-writer-slug-decision
title: "Multi-writer: why the claim slug is the filename stem, not the uuid"
summary: "Two writers collide on the filename they independently pick for the same topic, not on uuid (each writer mints its own); `mf claim` locks the filename stem via an atomic ON CONFLICT DO NOTHING insert."
status: active
tags: [multi-writer, claim, design-decision]
---
## Answer
`Page.slug` (`mf/page.py`) is the filename stem, not the `uuid`. Two
agents drafting a page for the same topic without seeing each other's
draft tend to pick the same descriptive filename, but each mints its
own `uuid` independently, so `uuid` can't be the collision signal.

`mf claim SLUG --by WRITER` (`mf/claim.py`) does the atomic
conditional insert: `INSERT INTO claims ... ON CONFLICT(slug) DO
NOTHING`, then reads back who holds it. This is safe across processes,
not just within one connection, because SQLite serializes writers at
the file level: a second process's insert blocks until the first
commits, then sees the conflict.

Exit codes mirror `write`'s dedup-gate convention: 0 if the caller now
holds the slug (won, or already held it -- re-claiming your own slug
is a no-op success), 2 if someone else does. A losing caller gets the
winner's identity back so it can `write --update` that page instead of
creating a duplicate.

`contested` status needed no new plumbing (it was already a valid
`status` value handled generically everywhere); what was missing was a
trigger. `mf lint` now warns `contested-slug` when two `active` pages
share a slug, catching the case where a hand-written page or a
bypassed claim collides without ever calling `mf claim`.

**Not built:** `write` does not call `claim` automatically. Deferred
until a real multi-writer collision is observed.
