<p align="center">
  <picture>
    <source srcset="assets/logo/svg/banner-dark.svg" media="(prefers-color-scheme: dark)">
    <source srcset="assets/logo/svg/banner-light.svg" media="(prefers-color-scheme: light)">
    <img src="assets/logo/svg/banner-light.svg" alt="dot-tasks logo">
  </picture>
</p>

# dot-tasks

`dot-tasks` is a Python CLI/TUI task manager designed to be readable by both humans and AI agents.

## Installation

### End-User Install (from Git)

Install directly into your current Python environment:

```bash
pip install "git+https://github.com/<org-or-user>/dot-tasks.git"
```

After install:

```bash
dot-tasks --help
```

### Development Install (with uv)

```bash
git clone https://github.com/awni00/dot-tasks.git
cd dot-tasks
uv sync --dev
uv run dot-tasks --help
```

Alternative editable development install:

```bash
uv pip install -e ".[dev]"
```

Once the package is published to PyPI, this section can also include a simple `pip install dot-tasks`.

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

Running `dot-tasks` with no command opens an interactive command palette in TTY shells. In non-interactive shells, dot-tasks prints help plus an explicit error and exits non-zero.

When selectors or metadata are missing in an interactive shell, dot-tasks opens a Textual UI when available and falls back to prompt dialogs otherwise.

## Interactive Demo

See the pre-populated walkthrough in:

- `examples/basic-demo/README.md`
