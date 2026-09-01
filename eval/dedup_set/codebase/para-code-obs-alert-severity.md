---
uuid: para-code-obs-alert-severity
title: The five-tier alert priority scale
summary: P5 logs only, P4 posts to Slack, P3 pages the primary on-call, P2 escalates to secondary after 15 minutes, P1 wakes the whole team.
---
## Answer
Alerts are classified into five priorities that determine how
loudly they interrupt someone:

- **P5** - written to logs, nobody is notified.
- **P4** - posted to a Slack channel, no page is sent.
- **P3** - pages whoever is primary on-call.
- **P2** - escalates to the secondary on-call if the P3 page is
  still unacknowledged after 15 minutes.
- **P1** - pages every engineer on the team plus the incident
  commander immediately.

The ladder is designed so severity maps directly to urgency of
response: lower tiers are informational noise you can review
later, while P1 assumes something is actively broken for users
and needs everyone's attention right away.
