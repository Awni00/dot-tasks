---
task_id: t-20260304-002
task_name: kebab-case-error-early-during-create
status: completed
date_created: '2026-03-04'
date_started: '2026-03-04'
date_completed: '2026-03-04'
priority: p0
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- create
- update
---

## Summary
- Currently, in `dot-tasks create`, if task_name is provided an invalid name (non kebab-case), it will only fail at the end after submission: `Error: task_name must be kebab-case with lowercase letters, numbers, and hyphens`
- This can cause somebody to spend a lot of time writing the task specs/etc, and lose all that through a silly error at the end
- Let's have the check occur after task_name is submitted, and simply indicate invalid error and ask for a different name, until a valid name is given.

## Acceptance Criteria
- TODO
