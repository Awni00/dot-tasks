<p align="center">
  <picture>
    <source srcset="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-dark.svg" media="(prefers-color-scheme: dark)">
    <source srcset="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-light.svg" media="(prefers-color-scheme: light)">
    <img src="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-light.svg" alt="dot-tasks logo">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/Awni00/dot-tasks/actions/workflows/tests.yml"><img src="https://github.com/Awni00/dot-tasks/actions/workflows/tests.yml/badge.svg" alt="Unit Tests"></a>
  <a href="https://github.com/Awni00/dot-tasks/actions/workflows/publish.yml"><img src="https://github.com/Awni00/dot-tasks/actions/workflows/publish.yml/badge.svg" alt="Publish"></a>
  <a href="https://pypi.org/project/dot-tasks/"><img src="https://img.shields.io/pypi/v/dot-tasks" alt="PyPI version"></a>
  <a href="https://github.com/Awni00/dot-tasks/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#installation">Install</a> •
  <!-- <a href="#commands">Commands</a> • -->
  <a href="#ai-agent-integration">AI Agent Integration</a> •
  <a href="#example-project">Example Project</a> •
  <a href="https://deepwiki.com/Awni00/dot-tasks">DeepWiki</a>
</p>

`dot-tasks` is a simple CLI for managing project-level tasks in a local `.tasks/` directory, using human- and agent-readable files.

It started as a personal workflow tool: keep task specs in files, let agents work from those specs, and keep progress updates in the repo instead of chat history. It is shared here in case the same approach is useful to others.

![dot-tasks CLI demo](https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/demo/cli-demo.gif)


## Quick Start

Quick start commands:

```bash
# Initialize .tasks/ dir in the current project
dot-tasks init
# Create a new todo task with an initial summary.
dot-tasks create rename-variables-for-vibes --summary "Refactor variable names for maximum vibes"
# Move the task from todo/ to doing/ and create its plan.md.
dot-tasks start rename-variables-for-vibes
# Append a progress note while work is in progress.
dot-tasks update rename-variables-for-vibes --note "Replaced cryptic names with vibes-based naming"
# Mark the task complete and move it to done/.
dot-tasks complete rename-variables-for-vibes
```

### Task directory layout

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

### Typical workflow:

| Step | What happens | Command(s) | Files touched |
| --- | --- | --- | --- |
| Make note of new to-do | Write down the task spec. Often I have an agent draft a spec from a rough note. | `dot-tasks create` | Creates task dir `.tasks/todo/<created-date>-<task_name>/` with `task.md`, `activity.md`|
| Choose task to work on | Scan what is in `todo`/`doing` and pick the next task to start. | `dot-tasks list` | read-only inspection of `.tasks/` |
| Start active work | Move the task to active status when implementation begins. | `dot-tasks start` | Move task from `.tasks/todo/` to `.tasks/doing/`; `plan.md` created |
| Work loop | Log notable progress updates so humans and agents share context. | `dot-tasks update` | `task.md`, `activity.md` |
| Finish and archive state | Mark done when acceptance criteria are met, preserving full history in files. | `dot-tasks complete` | task directory moves to `.tasks/done/`|

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

## Commands

| Command | Purpose | Typical usage |
| --- | --- | --- |
| `init` | Create `.tasks/` and write/update managed config settings; can also append workflow guidance section AGENTS.md and install the skill via `npx skills`. | `dot-tasks init` |
| `create` | Add a new task to `todo/`. | `dot-tasks create <task_name>` |
| `start` | Move a task to `doing/` and create `plan.md`. | `dot-tasks start <task_name>` |
| `complete` | Move a task to `done/`. | `dot-tasks complete <task_name>` |
| `list` | List tasks by status and optional tag filters (rich/plain/JSON depending on context). | `dot-tasks list [todo|doing|done] [--tag <tag> ...] [--json]` |
| `tags` | Show task counts by tag with optional status filter (rich/plain/JSON depending on context). | `dot-tasks tags [todo|doing|done] [--sort count|name] [--json]` |
| `view` | Show full details for one task. | `dot-tasks view <task_name> [--json]` |
| `update` | Update metadata, dependencies, tags, or add notes. | `dot-tasks update <task_name> ...` |
| `rename` | Rename a task. | `dot-tasks rename <task_name> <new_task_name>` |
| `delete` | Move a task to `trash/`, or delete permanently with `--hard`. | `dot-tasks delete <task_name> [--hard]` |

Tag examples:

```bash
dot-tasks list --tag bug
dot-tasks list doing --tag backend --tag api --all-tags
dot-tasks tags
dot-tasks tags todo --sort name
```

## AI Agent Integration

`dot-tasks` is designed so humans and agents can work from the same file-based task state in `.tasks/` instead of relying on chat context.

Typical agent workflow:

1. Capture or refine a task spec with `dot-tasks create`.
2. If asked what to work on, check `dot-tasks list` (`todo`/`doing`) and propose the top few options with a short rationale.
3. Move selected work into active state with `dot-tasks start`.
4. Log meaningful progress with `dot-tasks update --note ...` as work evolves.
5. Close the loop with `dot-tasks complete` when acceptance criteria are met.

`dot-tasks init` can also set up integration pieces:

- It can append a canonical **“Task management with `dot-tasks`”** section to your project `AGENTS.md`.
- It can run:
  `npx skills add Awni00/dot-tasks --skill dot-tasks`
  to install the `dot-tasks` skill.

## Example Project

For a full demo of the workflow, see [`examples/basic-demo/`](examples/basic-demo/) and the walkthrough in [`examples/basic-demo/README.md`](examples/basic-demo/README.md).
