<!-- dot-tasks:begin task-management -->
## Task management with `dot-tasks`

Use `dot-tasks` for substantial or multi-file work so task specs and progress stay in repo files.

- Use the "dot-tasks" skill for full behavior details.
- Prefer `dot-tasks` commands over manual edits to `.tasks/` state files.

Suggested workflow:

1. Capture a new task with `dot-tasks create`.
2. If asked what to work on, run `dot-tasks list` over `todo`/`doing` and suggest up to 3 task options with one-line rationale each.
3. Start work with `dot-tasks start <task_name>`.
4. Record meaningful progress with `dot-tasks update <task_name> --note "..."`.
5. Mark complete with `dot-tasks complete <task_name>` once acceptance criteria are met.

Guardrails:

- Do not rewrite `activity.md` history; append only.
- Use `dot-tasks rename` and `dot-tasks delete` rather than manual folder edits.
<!-- dot-tasks:end task-management -->
