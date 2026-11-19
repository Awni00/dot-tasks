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

It started as a personal workflow tool: keep task specs in files, let agents work from those specs, and keep progress records in the repo instead of chat history. It is shared here in case the same approach is useful to others.

dot-tasks owns task *state* (id, status, dates, priority, tags, dependencies) and changes it only through commands. Everything else in a task folder is *content*: the `task.md` body and any other files your project keeps there (plans, notes, session records), edited directly like ordinary files. Your project describes its own workflow in `.tasks/README.md`; the tool does not prescribe one.

![dot-tasks CLI demo](https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/demo/cli-demo.gif)


## Quick Start

Quick start commands:

```bash
# Initialize .tasks/ dir in the current project
dot-tasks init
# Create a new todo task with an initial summary.
dot-tasks create rename-variables-for-vibes --summary "Refactor variable names for maximum vibes"
# Move the task from todo/ to doing/.
dot-tasks start rename-variables-for-vibes
# Print the task folder (to open or add files there).
dot-tasks path rename-variables-for-vibes
# Mark the task complete and move it to done/.
dot-tasks complete rename-variables-for-vibes
```

### Task directory layout

```text
.tasks/
  README.md      # your project's workflow doc (starter written by `init`)
  config.yaml
  todo/
  doing/
  done/
  trash/
```

Each task lives in `.tasks/<status-bucket>/<created-date>-<task_name>/`. The folder moves when the status changes, so refer to tasks by name or id, not by path (`dot-tasks path <task>` resolves one).

dot-tasks writes only `task.md`: YAML frontmatter with the task's metadata, and a body built from the sections in `settings.task_body_sections` (default: `## Summary`). Any other file in the folder (`plan.md`, `notes.md`, `sessions/…`) belongs to your project, and `dot-tasks view` lists it.

### Typical workflow:

| Step | What happens | Command(s) | Files touched |
| --- | --- | --- | --- |
| Make note of new to-do | Write down the task spec. Often I have an agent draft a spec from a rough note. | `dot-tasks create` | Creates task dir `.tasks/todo/<created-date>-<task_name>/` with `task.md` |
| Choose task to work on | Scan what is in `todo`/`doing` and pick the next task to start. | `dot-tasks list` | read-only inspection of `.tasks/` |
| Start active work | Move the task to active status when work begins. | `dot-tasks start` | Move task from `.tasks/todo/` to `.tasks/doing/` |
| Work loop | Edit the task description and the files your workflow keeps (plans, notes, records). | none, edit files directly | `task.md` body, project files in the task folder |
| Finish and archive state | Mark done when the work is finished, preserving its files. | `dot-tasks complete` | task directory moves to `.tasks/done/`|

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
| `init` | Create `.tasks/`, write/update managed config settings and a starter `.tasks/README.md` (if missing); can also append the dot-tasks section to AGENTS.md and install the skill via `npx skills`. | `dot-tasks init` |
| `install-skill` | Install the canonical `dot-tasks` skill via `npx skills`. | `dot-tasks install-skill [--yes]` |
| `add-agents-snippet` | Add or update the canonical `dot-tasks` section in AGENTS policy markdown. | `dot-tasks add-agents-snippet [--agents-file <path>] [--yes]` |
| `create` | Add a new task to `todo/`, optionally with a date-only due date. | `dot-tasks create <task_name> [--due-date YYYY-MM-DD] [--spec-readiness unspecified|rough|ready|autonomous]` |
| `start` | Move a task to `doing/` (checks dependencies; `--force` overrides). | `dot-tasks start <task_name>` |
| `complete` | Move a task to `done/`. | `dot-tasks complete <task_name>` |
| `list` | List tasks by status and optional tag filters (rich/plain/JSON depending on context). | `dot-tasks list [todo|doing|done|all] [--tag <tag> ...] [--json]` |
| `tags` | Show task counts by tag with optional status filter (rich/plain/JSON depending on context). | `dot-tasks tags [todo|doing|done] [--sort count|name] [--json]` |
| `view` | Show full details for one task, including clickable links to `task.md` and every other file in its folder. | `dot-tasks view <task_name> [--json]` |
| `path` | Print the absolute path of a task's folder. | `dot-tasks path <task_name>` |
| `graph` | Visualize task dependencies as a DAG in terminal output (`tree` or `layers` modes). | `dot-tasks graph [--mode tree|layers] [--include-done]` |
| `update` | Update metadata, dependencies, tags, owner, effort, priority, spec readiness, or due date. | `dot-tasks update <task_name> [--due-date YYYY-MM-DD|--clear-due-date] ...` |
| `rename` | Rename a task. | `dot-tasks rename <task_name> <new_task_name>` |
| `delete` | Move a task to `trash/`, or delete permanently with `--hard`. | `dot-tasks delete <task_name> [--hard]` |

Interactive `create` and interactive `update` use a single tag selector flow with an optional `+ add new tag(s)` path.

Status filter supports `todo|doing` style multi-select and `all`. Default is `todo|doing`.

### Optional due dates

Due dates are stored in task frontmatter as an optional ISO `due_date: YYYY-MM-DD`.
They contain no time or timezone. Explicit `create --due-date`, `update --due-date`,
and `update --clear-due-date` options remain available for scripts regardless of
the interactive feature setting.

Due dates are enabled by default. Their interactive prompts and human-readable
output can be disabled:

```yaml
settings:
  due_dates:
    enabled: true
  list_table:
    columns:
      - name: task_name
        width: 32
      - name: due_date
        width: 10
```

When due dates are enabled, `init` offers `due_date` in the list-column
selector and selects it by default; users may unselect it. When due dates are
disabled, the column is omitted from the selector and suppressed from list
output. In Rich terminal output, dates before today render in red and dates due
today render in orange for `todo` and `doing` tasks. Completed tasks are not
highlighted.

The interactive date picker starts at today after choosing to set a date.
Use left/right to select year, month, or day; up/down to adjust it; type digits
to replace a segment; and press Enter to accept.

Tag examples:

```bash
dot-tasks list --tag bug
dot-tasks list todo|doing --tag backend --tag api --all-tags
dot-tasks list all
dot-tasks tags
dot-tasks tags todo --sort name
```

## AI Agent Integration

`dot-tasks` is designed so humans and agents can work from the same file-based task state in `.tasks/` instead of relying on chat context.

The pieces:

- **`.tasks/README.md`**: your project's workflow doc. It says when to create tasks, which files a task keeps (e.g. `plan.md`, per-session AI-use records), what to record when wrapping up and before completing. `init` writes a starter skeleton; edit it to fit the project.
- **AGENTS.md section**: a short trigger that tells agents the project uses dot-tasks and to read `.tasks/README.md` before working on a task.
- **`dot-tasks` skill**: a compact command and data-model reference.

The CLI itself never prints workflow guidance, so commands stay the same for humans and agents.

You can set up agent integration pieces either during `dot-tasks init` or with standalone commands:

- During `dot-tasks init` (interactive flow), `dot-tasks` can optionally append the AGENTS section and install the skill.
- Standalone commands:

```bash
dot-tasks install-skill
dot-tasks install-skill --yes
dot-tasks add-agents-snippet
dot-tasks add-agents-snippet --agents-file TEAM_AGENTS.md --yes
```

## Project workflow doc

`.tasks/README.md` is plain Markdown that you own. A research project might say:

```markdown
## Files in a task folder
- `task.md` sections: Summary, Done when, Outcome, Human review.
- `sessions/<date>-<session-id>.md`: one AI-use record per session (model, who did what,
  outcome, initial and major prompts), written at wrap-up from `.tasks/templates/session.md`.

## Before completing a task
- Fill Outcome and Human review. Abandoned work is completed with an explanatory Outcome
  and the `dropped` tag.
```

The body sections in `task.md` come from `settings.task_body_sections` in `.tasks/config.yaml`:

```yaml
settings:
  task_body_sections:
    - {name: Summary, default: "- TODO"}
    - {name: Done when, default: "- TODO"}
    - {name: Outcome, default: "- TODO"}
    - {name: Human review, default: "- TODO"}
```

## Migrating from 0.1

0.2.0 removes the workflow the tool used to hardcode:

- `start` no longer creates `plan.md`, and no command writes `activity.md`. Existing `plan.md` and `activity.md` files stay in their task folders as ordinary files.
- `log-activity` is removed. If you want a log, describe it in `.tasks/README.md` and keep it as a file in the task folder.
- New: `dot-tasks path <task>`, and `init` writes a starter `.tasks/README.md` if missing.

No config changes are needed. To refresh agent instructions, run `dot-tasks add-agents-snippet` and `dot-tasks install-skill`, then write your workflow in `.tasks/README.md` (run `dot-tasks init` to get the starter).

## Example Project

For a full demo of the workflow, see [`examples/basic-demo/`](examples/basic-demo/) and the walkthrough in [`examples/basic-demo/README.md`](examples/basic-demo/README.md).
