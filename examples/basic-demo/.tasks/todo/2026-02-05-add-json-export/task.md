---
task_id: t-20260205-001
task_name: add-json-export
summary: Add a JSON export mode for task listings.
status: todo
date_created: '2026-02-05'
date_started: null
date_completed: null
depends_on: []
tags:
- api
- export
priority: p1
effort: m
owner: alex
---

## Acceptance Criteria
- `dot-tasks list --json` emits machine-readable task rows.
- Output includes dependency health and metadata.
