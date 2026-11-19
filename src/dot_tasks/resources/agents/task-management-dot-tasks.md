<!-- dot-tasks:begin task-management -->
## Task management with `dot-tasks`

This project tracks work with the `dot-tasks` CLI in `.tasks/`. **This project's task workflow is in `.tasks/README.md`; read it before working on a task.**

- Change task state (create, start, complete, dependencies, tags) only through `dot-tasks` commands. Write the task description in the `task.md` body and other task files directly; `summary` and project fields can be set with `dot-tasks update <task> key=value` or edited by hand.
- Refer to tasks by name or id, never by folder path (`dot-tasks path <task>` resolves one).
- Use the `dot-tasks` skill for the command reference.
<!-- dot-tasks:end task-management -->
