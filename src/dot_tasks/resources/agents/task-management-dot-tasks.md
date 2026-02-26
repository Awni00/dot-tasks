<!-- dot-tasks:begin task-management -->
## Task management with `dot-tasks`

`dot-tasks` is a Python CLI (assumed installed) that tracks human/agent work in a repo-local `.tasks/` directory. Use `dot-tasks` for non-trivial work so task specs and progress stay in repo files.

- Use the "dot-tasks" skill for full behavior details.
- Prefer `dot-tasks` commands over manual edits to `.tasks/` state files.

Default workflow:

Use `dot-tasks` for non-trivial work tracked in `.tasks/`.

Trigger the `dot-tasks` skill when:
1. User asks what to work on next.
2. User asks to begin/resume an existing task.
3. User asks for significant new work (create and bind a task).

The skill is the source of truth for workflow details (triage, readiness checks, clarification flow, and lifecycle execution).

Guardrails:
- Prefer `dot-tasks` commands over manual `.tasks/` edits.
- Confirm task binding with the user before tracked execution.
- Keep `activity.md` append-only.
- Use `dot-tasks rename/delete` for maintenance operations.

Lifecycle (high-level): `create -> start -> log-activity -> complete`.
<!-- dot-tasks:end task-management -->
