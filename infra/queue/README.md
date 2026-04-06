# Queue integration

Production flow: Slack/webhook → **enqueue** JSON envelope → worker consumes → calls `orchestrator.triggers.dispatch` (or separate service per agent).

- Use a dead-letter queue for failed steps; replay with the same `idempotency_key` from `contracts/control.json`.
- Payload shape: `{ "command": "/deepdive", "operator_id": "...", "correlation_id": "..." }`.
