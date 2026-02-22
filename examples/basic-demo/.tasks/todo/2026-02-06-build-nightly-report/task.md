---
task_id: t-20260206-001
task_name: build-nightly-report
status: todo
date_created: '2026-02-06'
date_started: null
date_completed: null
priority: p0
effort: l
depends_on:
- t-20260205-001
blocked_by: []
owner: alex
tags:
- reporting
- automation
---

## Summary
- Build nightly report generation using exported task snapshots.

## Acceptance Criteria
- Nightly report job reads JSON export payload.
- Missing dependency behavior is documented and tested.
