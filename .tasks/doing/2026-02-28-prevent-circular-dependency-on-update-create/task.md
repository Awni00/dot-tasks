---
task_id: t-20260228-001
task_name: prevent-circular-dependency-on-update-create
status: doing
date_created: '2026-02-28'
date_started: '2026-03-01'
date_completed: null
priority: p2
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- create
- dependencies
- update
---

## Summary
- If a dependency is specified in `create` or `update` that is circular, throw an error in TUI after dependency specification and prompt user to re-enter dependencies.

## Acceptance Criteria
- Include tests that generate circular dependencies with cycles of length 2, 3, 4 and check that circular dependence is detected.
