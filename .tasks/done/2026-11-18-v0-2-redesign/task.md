---
task_id: t-20261118-J3EK
task_name: v0-2-redesign
summary: ''
status: completed
date_created: '2026-11-18'
date_started: '2026-11-19'
date_completed: '2026-11-19'
depends_on: []
tags: []
due_date: null
priority: p1
effort: l
spec_readiness: ready
owner: null
---

## Summary
- Redesign for 0.2.0: tool writes only task.md (state + body skeleton); drop plan.md/activity.md/log-activity; workflow conventions live in .tasks/README.md; add `path` command and starter README. Full plan in plan.md.

## Acceptance Criteria
- All decisions and implementation steps in plan.md are done; `pytest` green.
- Manual verification in plan.md passes; legacy tasks in this repo still load and display.
- Version is 0.2.0 with migration notes in README.
