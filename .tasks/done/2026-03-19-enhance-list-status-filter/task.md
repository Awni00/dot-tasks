---
task_id: t-20260319-FGUF
task_name: enhance-list-status-filter
status: completed
date_created: '2026-03-19'
date_started: '2026-03-19'
date_completed: '2026-03-19'
priority: p0
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- list
---

## Summary
- Currently, `dot-tasks list` lists all tasks include done, while status filter can only filter one status type (i.e., `todo` only or `doing` only, etc)
- In many cases, we want to see todo and doing, but not done (because done will accumulate and be very large).
- Features: 1) add support for string-parsed status filter of the format "todo|doing|done" or "todo|doing" etc. 2) change the default for `dot-tasks list` to "todo|doing" (these are the tasks that require attention). We can also a dd a special convenience status filter "all" that corresponds to "todo|doing|done" so we don't have to type that long filter string.

## Acceptance Criteria
- TODO
