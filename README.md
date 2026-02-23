<p align="center">
  <picture>
    <source srcset="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-dark.svg" media="(prefers-color-scheme: dark)">
    <source srcset="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-light.svg" media="(prefers-color-scheme: light)">
    <img src="https://raw.githubusercontent.com/Awni00/dot-tasks/main/assets/logo/svg/banner-light.svg" alt="dot-tasks logo">
  </picture>
</p>

# dot-tasks

`dot-tasks` is a Python CLI task manager designed to be readable by both humans and AI agents.

<p align="center">
  <a href="https://github.com/Awni00/dot-tasks/actions/workflows/tests.yml"><img src="https://github.com/Awni00/dot-tasks/actions/workflows/tests.yml/badge.svg" alt="Unit Tests"></a>
  <a href="https://github.com/Awni00/dot-tasks/actions/workflows/publish.yml"><img src="https://github.com/Awni00/dot-tasks/actions/workflows/publish.yml/badge.svg" alt="Publish"></a>
  <a href="https://pypi.org/project/dot-tasks/"><img src="https://img.shields.io/pypi/v/dot-tasks" alt="PyPI version"></a>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
</p>

## Installation

### Install via pip (PyPI)

```bash
pip install dot-tasks
```

After install:

```bash
dot-tasks --help
```

### Install Latest from GitHub

Install directly into your current Python environment:

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

Alternative editable development install:

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

`dot-tasks list` output behavior:

- Interactive TTY terminals: rich sectioned table grouped by status with styled priority/dependency health.
- Non-interactive/piped output: plain ASCII table fallback for stable scripting/parsing.
- `--json`: unchanged machine-readable output.
- Human-readable columns/widths are configurable via `.tasks/config.yaml` (`settings.list_table.columns`).

### Interactive Behavior

`dot-tasks` uses prompt-based interaction only (no full-screen mode).

Config file:

- `.tasks/config.yaml` stores `settings.interactive_enabled: true|false`
- `.tasks/config.yaml` stores `settings.show_banner: true|false` (root command banner visibility)
- `.tasks/config.yaml` also stores `settings.list_table.columns` for list output formatting
- `dot-tasks init` creates this file if missing; re-running interactive `init` updates managed settings in-place
- In interactive terminals, `init` uses interactive selector prompts for:
  - default interactivity setting
  - root banner visibility
  - list columns (multi-select checkbox)
- In non-interactive contexts, `init --nointeractive` does not modify existing config values (and creates defaults only when config is missing)
- Unsupported config keys are ignored with warnings
- Invalid `interactive_enabled` values warn and fall back to `true`
- Invalid `show_banner` values warn and fall back to `true`
- Invalid list-table config values warn and fall back to defaults
- When selecting list columns in `init`, widths are filled from built-in defaults per column

One-off override:

- `--nointeractive` disables prompts for a single command invocation

Default list-table config:

```yaml
settings:
  interactive_enabled: true
  show_banner: true
  list_table:
    columns:
      - name: task_name
        width: 32
      - name: priority
        width: 8
      - name: effort
        width: 6
      - name: deps
        width: 12
      - name: created
        width: 10
```

Supported column names: `task_name`, `task_id`, `status`, `priority`, `effort`, `deps`, `created`.

Keyboard controls in interactive prompts:

- single-choice lists: `up/down` to move, `enter` to select, `ctrl-c` to cancel
- task selection lists (`start`/`complete`/`view`/`update`/`rename`/`delete`): type to fuzzy-search, `enter` to select, `ctrl-c` to cancel
- dependency multi-select (`depends_on`): type to filter, `space` or `tab` to toggle, `enter` to submit, `ctrl-c` to cancel
- other multi-choice lists (for example init list columns): `space` to toggle, `up/down` to move, `enter` to submit, `ctrl-c` to cancel
- in `dot-tasks create`, dependency selection is optional; the selector is only shown if you choose to set dependencies
- if arrow-key selectors cannot run, dot-tasks automatically falls back to numeric prompts
- `Ctrl+C` cleanly cancels the current prompt in both selector and numeric fallback modes
- canceling from root `dot-tasks` command picker quits with exit `0`
- canceling inside a command flow aborts that command with `Canceled.` and exit `1`

Behavior:

- `dot-tasks` (no command):
  - if banner is enabled and a TTY is present: prints banner + divider before output
  - if interaction is enabled and a TTY is present: opens a one-shot command picker
  - if interaction is disabled: prints help and exits `0`
  - if interaction is enabled but no TTY is present: prints help + explicit error and exits `2`
- `dot-tasks <command>`:
  - does not print the root banner
  - if required args are missing and interaction is enabled: opens one-shot prompts and runs the command
  - if required args are missing and interaction is disabled: errors
  - if required args are provided: runs non-interactive command path

## AI Agent Integration

Reusable agent-integration reference assets live in `agent-tools/`.

- `agent-tools/README.md` explains how to install and use the skill and snippets.
- `agent-tools/skills/dot-tasks/SKILL.md` is the canonical `dot-tasks` skill file.

These files are intended for package users integrating `dot-tasks` into their own repositories.

## Interactive Demo

See the pre-populated walkthrough in:

- `examples/basic-demo/README.md`
