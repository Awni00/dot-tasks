# dot-tasks

`dot-tasks` is a Python CLI/TUI task manager designed to be readable by both humans and AI agents.

## Quick Start

```bash
dot-tasks init
dot-tasks create add-task-manager --summary "Build initial package"
dot-tasks start add-task-manager
dot-tasks update add-task-manager --note "Implemented storage layer"
dot-tasks complete add-task-manager
```

## Task Layout

```text
.tasks/
  todo/
  doing/
  done/
  trash/
```

Each task lives in `.tasks/<status-bucket>/<created-date>-<task_name>/` and contains:

- `task.md` (canonical metadata frontmatter + task body)
- `activity.md` (append-only audit log)
- `plan.md` (created when the task is started)

## Commands

- `dot-tasks init`
- `dot-tasks create <task_name>`
- `dot-tasks start <task_name>`
- `dot-tasks complete <task_name>`
- `dot-tasks list [todo|doing|done] [--json]`
- `dot-tasks view <task_name> [--json]`
- `dot-tasks update <task_name> ...`
- `dot-tasks rename <task_name> <new_task_name>`
- `dot-tasks delete <task_name> [--hard]`

When selectors or metadata are missing in an interactive shell, dot-tasks opens a Textual UI when available and falls back to prompt dialogs otherwise.
