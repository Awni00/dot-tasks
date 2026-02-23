<p align="center">
  <picture>
    <source srcset="assets/logo/svg/banner-dark.svg" media="(prefers-color-scheme: dark)">
    <source srcset="assets/logo/svg/banner-light.svg" media="(prefers-color-scheme: light)">
    <img src="assets/logo/svg/banner-light.svg" alt="dot-tasks logo">
  </picture>
</p>

# dot-tasks

`dot-tasks` is a Python CLI task manager designed to be readable by both humans and AI agents.

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
- `config.yaml` (interactive preferences)

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

### Interactive Behavior

`dot-tasks` uses prompt-based interaction only (no full-screen mode).

Config file:

- `.tasks/config.yaml` stores `settings.interactive_enabled: true|false`
- `dot-tasks init` creates this file if missing
- In interactive terminals, `init` prompts for enabled/disabled
- In non-interactive contexts, `init` defaults to `interactive_enabled: true`
- Unsupported config keys are ignored with warnings
- Invalid `interactive_enabled` values warn and fall back to `true`

One-off override:

- `--nointeractive` disables prompts for a single command invocation

Behavior:

- `dot-tasks` (no command):
  - if interaction is enabled and a TTY is present: opens a one-shot command picker
  - if interaction is disabled: prints help and exits `0`
  - if interaction is enabled but no TTY is present: prints help + explicit error and exits `2`
- `dot-tasks <command>`:
  - if required args are missing and interaction is enabled: opens one-shot prompts and runs the command
  - if required args are missing and interaction is disabled: errors
  - if required args are provided: runs non-interactive command path

## Interactive Demo

See the pre-populated walkthrough in:

- `examples/basic-demo/README.md`
