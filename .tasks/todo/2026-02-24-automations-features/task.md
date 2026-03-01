---
task_id: t-20260224-001
task_name: automations-features
status: todo
date_created: '2026-02-24'
date_started: null
date_completed: null
priority: p1
effort: m
spec_readiness: unspecified
depends_on: []
blocked_by: []
owner: null
tags:
- automation
---

## Summary
- setup automation features that run codex/etc on highest priority s/m effort (configurable) dot-tasks tasks and creates branch/PR. agent should explicitly think about prioritizing tasks that are fully-speced and don't require human input to complete. avoid tasks that have vague or incomplete specs.
- automation feature: 
    1. begining of day triage of tasks to work on
    2. begining of day "pulse" on recent work
    3. Begining of week "pulse" report summarizing work in the past week
    4. overnight work 
    5. end-of-day prompt user to define specs of tasks to make them fully-speced and ready for overnight work  
    6. what else can we do?
- in the package, this can just be some demo/example of automations. i.e., prompt text that can be copy-pasteable to codex automations to create.
- think about whether possible/appropriate to have CLI command to setup automations (i.e., `dot-tasks automations` to setup and turn on/off automations). e.g., does codex app support project-specific automations settable from CLI? not sure. probably sufficient to have copy-pasteable examples. 
- is it possible to have some utility `dot-tasks` command to set up/define automations for the given project/repo (e.g., setup on codex app, or claude app, etc)? is there some API available for this? would be nice if automations can be tracked in the repo itslelf. Can set up as multi-select that prompts user to select what automations to enable for the given repo (and for which agent, claude or codex, etc). if not available, can write automations to .agents/automations in seperate markdown files for each automation, user can then copy-paste in agent app interface.

## Acceptance Criteria
- TODO
