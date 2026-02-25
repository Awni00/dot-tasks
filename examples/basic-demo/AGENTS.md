# AGENTS.md

<!-- dot-tasks:begin task-management -->
## Task management with `dot-tasks`

`dot-tasks` is a Python CLI (assumed installed) that tracks human/agent work in a repo-local `.tasks/` directory. Use `dot-tasks` for non-trivial work so task specs and progress stay in repo files.

- Use the "dot-tasks" skill for full behavior details.
- Prefer `dot-tasks` commands over manual edits to `.tasks/` state files.

Default workflow:

1. If `.tasks/` is missing, run `dot-tasks init` (or ask before initializing).
2. Check existing tasks first:
   - Fast path: if user provides `task_name`/`task_id`, run `dot-tasks view <task_name_or_id> --json`.
   - Otherwise run `dot-tasks list --json`, then inspect likely matches with `dot-tasks view <task_name_or_id> --json`.
3. Confirm the tracking target with the user before binding work to a task.
4. If no match and work is substantial (plan mode, likely multi-file, or >=30 minutes), ask whether to create a new task.
5. Once bound: `dot-tasks start`, write implementation plan to `plan.md`, `dot-tasks log-activity --note`, `dot-tasks complete`.

Guardrails:

- Avoid silent auto-binding on fuzzy matches.
- In plan mode, after the plan is finalized and approved by the user, write the full plan to the bound task's `plan.md` (do not only write a summary or partial plan).
- Do not rewrite `activity.md` history; append only.
- Use `dot-tasks rename` and `dot-tasks delete` rather than manual folder edits.
<!-- dot-tasks:end task-management -->
