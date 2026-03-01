---
task_id: t-20260224-005
task_name: update-skill-agent-task-init-behavior
status: completed
date_created: '2026-02-24'
date_started: '2026-02-26'
date_completed: '2026-02-26'
priority: p2
effort: m
spec_readiness: unspecified
depends_on: []
blocked_by: []
owner: null
tags: []
---

## Summary
- Update the SKILL.md and AGENT.md snippet with more detailed instructions on what to do when asked to begin work on an existing task.
- Sometimes task description will include enough detail to define the spec of the task. Sometimes it will be just rough description jotted down quickly by the user.
- The agent should identify whether the task spec/description is fully unambiguous and ready to start or if the user needs to specify many high-level and low-level details. If high-level details and intent are unclear, agent should ask open-ended questions to define the specifications of the task. Do not make assumptions of the task is vague and unclear. Instead, just ask the user to explain. 

## Acceptance Criteria
- TODO
