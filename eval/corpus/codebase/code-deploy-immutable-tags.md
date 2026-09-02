---
uuid: code-deploy-immutable-tags
title: "Deploy: why we use immutable image tags"
summary: "Tags are git SHAs (e.g., `billing:a7c9d2e`), not semver; you can never deploy the same tag twice with different code."
status: active
tags: [deploy, immutability]
---
## Answer
Every image tag is `<service>:<git-sha>`. The tag is set at
build time and never changed. If you want to re-deploy "the same
code", you re-tag from the same SHA — but you can never have two
different builds share a tag.

This means rollbacks are always to a specific known commit,
not "the thing that was at this tag yesterday".

