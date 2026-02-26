---
name: dot-tasks
description: Reference skill for users integrating dot-tasks into AI coding agents. Use dot-tasks to track tasks in `.tasks/` with clear, auditable state for humans and agents.
---

# dot-tasks Skill

`dot-tasks` is a Python CLI (assumed installed) that tracks human/agent work in a repo-local `.tasks/` directory.

Use this skill whenever a repository uses `dot-tasks` for task lifecycle tracking.

## When To Use

- Use this skill when the user asks for task suggestions based on existing `dot-tasks` state.
- Use this skill when the user asks to begin or resume work on an existing task.
- Use this skill when the user asks for significant new work that should likely be tracked.

## Workflow 1: Suggest What To Work On Next

1. Discover candidate work:
   - Run `dot-tasks list todo --json` (or `dot-tasks list --json` if status is not specified).
   - Inspect likely top candidates with `dot-tasks view <task_name_or_id> --json`.
2. Rank candidates using this rubric:
   - Higher priority first (`p1` before `p2`, etc).
   - Prefer unblocked tasks (`dependency_health: ready`) over blocked work.
   - Prefer tasks with clearer specs (`ready`/`autonomous`) when execution should start immediately.
   - Break ties with effort (`s`/`m` for quick wins, unless user asked for larger work).
3. Return the top few options with one-line rationale each.
4. If high-priority work is blocked, call that out explicitly and include:
   - A short unblock path for the blocked item.
   - A suggested unblocked fallback task.

## Workflow 2: Begin Or Resume Existing Task

1. Resolve the target task:
   - If the user provides `task_name`/`task_id`, run `dot-tasks view <task_name_or_id> --json`.
   - If ambiguous, list likely matches and confirm the target with the user before binding.
2. Branch by task status:
   - `doing`: resume by reading `plan.md` and recent `activity.md`, then continue from the latest checkpoint.
   - `todo`: run readiness checks before starting.
   - `done`: do not silently restart; ask whether to create a follow-up task or reopen scope explicitly.
3. Apply readiness gate before execution:
   - `spec_readiness` `unspecified`/`rough`: clarify high-level intent before starting.
   - `spec_readiness` `ready`/`autonomous`: plan lower-level implementation details.
4. If intent is unclear, ask open-ended questions in two stages:
   - Stage 1: high-level intent, scope, desired outcome.
   - Stage 2: implementation constraints, edge cases, acceptance criteria.
5. Do not proceed on unstated assumptions when high-level intent is unclear.

## Workflow 3: Significant New Work

1. Detect whether the request is substantial (multi-file, plan-heavy, or likely >=30 minutes).
2. If substantial, ask whether to create and bind a new `dot-tasks` task.
3. If the user agrees:
   - Create task with `dot-tasks create ...` (include summary and basic metadata).
   - Confirm the tracking target and bind work to that task.
4. If work is quick/simple, do not force task creation unless the user asks.

## Shared Task Lifecycle Loop

For tracked task execution (regardless of how it was triggered), follow:
`create -> start -> plan -> log-activity -> complete`

- Start active execution with `dot-tasks start`.
- Keep `plan.md` current as implementation decisions become concrete.
- Log meaningful progress with `dot-tasks log-activity --note`.
- Use `dot-tasks update` for mid-flight metadata/scope/priority changes.
- Before `dot-tasks complete`, confirm acceptance criteria are satisfied.

## Commands

```bash
# setup
dot-tasks init                                              # initialize .tasks/

# discover
dot-tasks list --json                                       # list tasks for matching
dot-tasks list [todo|doing|done] --json                    # narrow by status
dot-tasks view <task_name_or_id> --json                    # inspect one task
dot-tasks tags [todo|doing|done] --json                    # tag counts/triage

# lifecycle
dot-tasks create <task_name> --summary "..." --priority [p1|p2|p3|p4] --effort [s|m|l|xl] --tag <tag>
dot-tasks start <task_name_or_id>                          # move to doing + create plan.md
dot-tasks update <task_name_or_id> --priority p1 --effort m --tag backend
dot-tasks log-activity <task_name_or_id> --note "Progress note" [--actor agent]
dot-tasks complete <task_name_or_id>                       # move to done

# maintenance
dot-tasks rename <task_name_or_id> <new_task_name>         # rename task
dot-tasks delete <task_name_or_id>                         # soft-delete to trash
```

## Guardrails

- Prefer `dot-tasks` commands over direct edits to task state files.
- Avoid silent auto-binding on fuzzy matches.
- Confirm task binding with the user before tracked execution.
- Direct file edits are allowed for:
  1. `task.md` for writing task summary/specs after `dot-tasks create`.
  2. `plan.md` to keep implementation steps current after `dot-tasks start`.
- In plan mode, after the plan is finalized and approved by the user, write the full plan to the bound task's `plan.md`.
- Do not rewrite `activity.md` history; append only.
- Respect dependency checks.

## Data Contract

- Canonical metadata is in `task.md` frontmatter.
- Dependency references use `task_id` in metadata.
- Dependencies are displayed to humans as `task_name (task_id)`.
- `activity.md` line format is `YYYY-MM-DD HH:MM | actor | type | note`.
