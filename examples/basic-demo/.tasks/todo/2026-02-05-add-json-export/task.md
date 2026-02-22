---
task_id: t-20260205-001
task_name: add-json-export
status: todo
date_created: '2026-02-05'
date_started: null
date_completed: null
priority: p1
effort: m
depends_on: []
blocked_by:
- t-20260206-001
owner: alex
tags:
- api
- export
---

## Summary
- Add a JSON export mode for task listings.

## Acceptance Criteria
- `dot-tasks list --json` emits machine-readable task rows.
- Output includes dependency health and metadata.
