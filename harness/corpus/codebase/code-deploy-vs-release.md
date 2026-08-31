---
uuid: code-deploy-vs-release
title: Deploy: the difference between a deploy and a release
summary: Deploy = new code in production; release = new code serving user traffic. Feature flags separate the two.
status: active
tags: [deploy, vocabulary]
---
## Answer
- **Deploy**: a new image is running in production. May serve no
  user traffic if all features are behind flags.
- **Release**: a feature flag is enabled for some users.

We deploy continuously (many times per day) and release in
larger, slower steps (per the rollout schedule).

