---
uuid: code-dm-soft-delete
title: "Data model: how soft deletes work"
summary: "`deleted_at` column; queries default to `WHERE deleted_at IS NULL`; the `with_deleted` scope is opt-in for admin tools."
status: active
tags: [data-model, soft-delete]
---
## Answer
Every table has a nullable `deleted_at TIMESTAMPTZ` column. The
ORM scopes all default queries to `deleted_at IS NULL`. Admin
tools can use the `with_deleted` scope.

Hard deletes are reserved for GDPR right-to-be-forgotten and
never for ordinary data cleanup.

