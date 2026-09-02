---
uuid: code-obs-log-levels
title: "Observability: log levels in production"
summary: "Default INFO; DEBUG only when actively debugging, scoped to one service for ≤30 minutes, never in a steady-state service."
status: active
tags: [observability, logging]
---
## Answer
- **INFO**: normal operation events.
- **DEBUG**: turned on per-service when debugging. Auto-revert
  after 30 minutes via the log-level controller.
- **WARN/ERROR**: genuine anomalies.

