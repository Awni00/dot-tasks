<p align="center">
  <picture>
    <source srcset="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-dark.svg" media="(prefers-color-scheme: dark)">
    <source srcset="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-light.svg" media="(prefers-color-scheme: light)">
    <img src="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-light.svg" alt="dot-tasks logo">
  </picture>
</p>

# dot-tasks

`dot-tasks` is a small CLI for managing project-level tasks in a local `.tasks/` directory, using human- and agent-readable files.

It started as a personal workflow tool: keep task specs in files, let agents work from those specs, and keep progress updates in the repo instead of chat history. It is shared here in case the same approach is useful to others.

![dot-tasks CLI demo](assets/demo/cli-demo.gif)

<p align="center">
  <a href="https://github.com/Awni00/dot-tasks/actions/workflows/tests.yml"><img src="https://github.com/Awni00/dot-tasks/actions/workflows/tests.yml/badge.svg" alt="Unit Tests"></a>
  <a href="https://github.com/Awni00/dot-tasks/actions/workflows/publish.yml"><img src="https://github.com/Awni00/dot-tasks/actions/workflows/publish.yml/badge.svg" alt="Publish"></a>
  <a href="https://pypi.org/project/dot-tasks/"><img src="https://img.shields.io/pypi/v/dot-tasks" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

## High-level Workflow

This is the workflow I usually follow.

| Step | What happens | Command(s) | Files touched |
| --- | --- | --- | --- |
| Make note of new to-do | Write down the task spec. Often I have an agent draft a spec from a rough note. | `dot-tasks create` | Creates task dir `.tasks/todo/<created-date>-<task_name>/` with `task.md`, `activity.md`|
| Choose task to work on | Scan what is in `todo`/`doing` and pick the next task to start. | `dot-tasks list` | read-only inspection of `.tasks/` |
| Start active work | Move the task to active status when implementation begins. | `dot-tasks start` | Move task from `.tasks/todo/` to `.tasks/doing/`; `plan.md` created |
| Work loop | Log notable progress updates so humans and agents share context. | `dot-tasks update` | `task.md`, `activity.md` |
| Finish and archive state | Mark done when acceptance criteria are met, preserving full history in files. | `dot-tasks complete` | task directory moves to `.tasks/done/`|

## Contents

- [High-level Workflow](#high-level-workflow)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Task Layout](#task-layout)
- [Commands](#commands)
- [AI Agent Integration](#ai-agent-integration)

## Installation

### Install via pip (PyPI)

```bash
pip install dot-tasks
```

Quick check:

```bash
dot-tasks --help
```

### Install Latest from GitHub

Install the latest from GitHub:

```bash
pip install "git+https://github.com/Awni00/dot-tasks.git"
```

### Development Install (with uv)

```bash
git clone https://github.com/Awni00/dot-tasks.git
cd dot-tasks
uv sync --dev
uv run dot-tasks --help
```

Editable install:

```bash
uv pip install -e ".[dev]"
```

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

| Command | Purpose | Typical usage |
| --- | --- | --- |
| `init` | Create `.tasks/` and write/update managed config settings. | `dot-tasks init` |
| `create` | Add a new task to `todo/`. | `dot-tasks create <task_name>` |
| `start` | Move a task to `doing/` and create `plan.md`. | `dot-tasks start <task_name>` |
| `complete` | Move a task to `done/`. | `dot-tasks complete <task_name>` |
| `list` | List tasks by status (rich/plain/JSON depending on context). | `dot-tasks list [todo|doing|done] [--json]` |
| `view` | Show full details for one task. | `dot-tasks view <task_name> [--json]` |
| `update` | Update metadata, dependencies, tags, or add notes. | `dot-tasks update <task_name> ...` |
| `rename` | Rename a task. | `dot-tasks rename <task_name> <new_task_name>` |
| `delete` | Move a task to `trash/`, or delete permanently with `--hard`. | `dot-tasks delete <task_name> [--hard]` |

## AI Agent Integration

Reusable reference assets for agent workflows live in `agent-tools/`.

- `agent-tools/README.md` explains how to install and use the skill and snippets.
- `agent-tools/skills/dot-tasks/SKILL.md` is the canonical `dot-tasks` skill file.

These files are for package users integrating `dot-tasks` into their own repos.

See the pre-populated walkthrough in [`examples/basic-demo/README.md`](examples/basic-demo/README.md).
