---
task_id: t-20260228-002
task_name: update-rename-to-use-inquirerpy
status: completed
date_created: '2026-02-28'
date_started: '2026-03-01'
date_completed: '2026-03-01'
priority: p2
effort: s
spec_readiness: autonomous
depends_on: []
blocked_by: []
owner: null
tags: []
---

## Summary
- It seems `dot-tasks rename` currently uses typer.prompt rather than inquirerpy for new_task_name. Update to inquirerpy text field, matching `create`, `update`, etc.

## Acceptance Criteria
- TODO
