---
task_id: t-20260224-008
task_name: add-spec-readiness-attribute
status: completed
date_created: '2026-02-24'
date_started: '2026-02-25'
date_completed: '2026-02-25'
priority: p2
effort: s
spec_readiness: unspecified
depends_on: []
blocked_by: []
owner: null
tags:
- automation
- create
---

## Summary
- different tasks might have different levels of detail in the initial spec/description written by the user. some might be detailed and ready for implementation (e.g., by LLM with little user-guidance) and some might be very rough and only understandable by user (i.e., just serves as a reminder to get back to something). by having an explicit attribute (prompted after "summary" prompt in `dot-tasks create`, with default to none/not set/etc), this can serve as helpful metadata for an llm (beyond simply evaluating based on level of detail in spec). in particular, this might be helpful for automations that do work overnight; it helps an llm agent determine what can be done without user input and what can't etc.

## Acceptance Criteria
- TODO
