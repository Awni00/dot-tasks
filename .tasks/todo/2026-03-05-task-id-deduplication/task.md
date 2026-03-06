---
task_id: t-20260305-001
task_name: task-id-deduplication
status: todo
date_created: '2026-03-05'
date_started: null
date_completed: null
priority: p1
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- bug
---

## Summary
- Currently, since task-id's are generated sequentially via +=1 on task-id within a day, it is possible to duplicate task id's by adding different tasks on different branches, then merging.
- A simple fix is to only create *new* tasks on the main branch (you can still update existing tasks on branches/worktrees and merge). If we want to promote this approach, we can automatically detect branch name at the start of `dot-tasks create` and check if it is in ('main', 'master'). If not, print warning and ask user if they want to proceed. Can add config option check_main_bracnh: true|false.
- Alternatively, we can do away with task id's because task-names are already constrained to be unique (not backwards compatible; dependencies are task-id-based)
- Or: we can add a `dot-tasks deduplicate-task-id` utility. Which checks for duplicate task-id's and "reindexes" affected task-id's. We need to make sure to do this right so that the utility doesn't accidentally break unaffected tasks, etc. It is more complicated when there are task dependencies that refer to duplicate task-id's. If that is detected, perhaps we would prompt the user to decide which task the dependency is meant to refer to one by one. If a duplicate task-id issue is detected during another command, we can warn the user and ask them to run this utility.

## Acceptance Criteria
- Need careful tests to make sure logic is entirely correct and there is no risk of breaking things in the process of fixing duplication....
