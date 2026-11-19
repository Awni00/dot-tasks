# basic-demo

## Purpose

This directory is a safe, pre-populated demo workspace for `dot-tasks`.
Run commands from here to explore task lifecycle features without touching another project's `.tasks`.

What it contains:

- `.tasks/<todo|doing|done>/…/task.md`: four sample tasks. The frontmatter holds the state (status, dates, dependencies, tags), a one-line `summary` and the fields listed in `settings.fields` of `.tasks/config.yaml` (`priority`, `effort`, `owner`); the body holds the description.
- `.tasks/doing/2026-02-03-document-command-help/plan.md`: an example of a project-owned file. dot-tasks itself only writes `task.md`; which other files a task keeps is up to the project.
- `.tasks/README.md`: the demo project's workflow doc, saying when to create tasks and which files they keep.
- `AGENTS.md`: the canonical `dot-tasks` section, which points agents at `.tasks/README.md`.

## Setup

From the repository root:

```bash
uv pip install -e .
# or
pip install -e .
cd examples/basic-demo
```

The first `dot-tasks init` in a new workspace writes a starter `.tasks/README.md` (the project's workflow doc, only if missing) and `.tasks/config.yaml` with `settings.fields` (the task fields; the interactive form offers the built-ins `priority`, `effort`, `due_date`, `owner`), `settings.interactive_enabled`, `settings.show_banner`, and `settings.list_table.columns`. Columns for newly enabled fields are preselected.
In interactive terminals, `init` uses selector prompts (including checkbox multi-select) to configure these managed values, can optionally append the canonical `dot-tasks` task-management section to an AGENTS policy file, and can optionally run `npx skills add Awni00/dot-tasks --skill dot-tasks`.
Re-running interactive `dot-tasks init` updates managed config values; `--nointeractive` skips optional interactive integrations (and only appends AGENTS guidance when `--append-agents-snippet` is explicitly provided).
You can also run these integrations directly outside `init`:

```bash
dot-tasks install-skill --yes
dot-tasks add-agents-snippet --agents-file AGENTS.md --yes
```

Interactive pickers support keyboard navigation in prompt mode:

- `up/down` + `enter` for single selection
- task selectors support fuzzy search by typing
- dependency selectors support fuzzy search + multiselect (`space` or `tab` to toggle, `enter` to submit)
- other multi-select prompts still use list navigation with `space` to toggle
- in `dot-tasks create`, dependency selection is optional and only shown if you choose to set dependencies
- date fields use a segmented date picker: left/right for year/month/day, up/down for values
- if selector UI is unavailable, prompts automatically fall back to numeric entry
- `Ctrl+C` cleanly backs out of interactive prompts

## Inspect Preloaded State

**List tasks in `.tasks/`**

```bash
dot-tasks list
```

In interactive terminals, `dot-tasks list` now renders a richer styled table grouped by status.
The snippet below reflects the plain fallback format (used for non-interactive/piped output).
By default, list output omits `status` and `task_id` because rows are already grouped by status.

Expected snippet:

```text
task_name                         priority  effort  deps          created   
--------------------------------  --------  ------  ------------  ----------
build-nightly-report              p0        l       blocked(1)    2026-02-06
add-json-export                   p1        m       ready         2026-02-05
document-command-help             p2        s       ready         2026-02-03
```

Filter by any configured field with `key=value` (`key=` matches unset):

```bash
dot-tasks list all owner=alex
```

**View a particular task by name**

```bash
dot-tasks view build-nightly-report
```

Expected snippet:

```text
build-nightly-report (t-20260206-001)
[todo] [deps: blocked(1)]
summary: Build nightly report generation using exported task snapshots.
priority: p0    effort: l    owner: alex
tags: reporting, automation
created: 2026-02-06    started: -    completed: -
depends_on: add-json-export (t-20260205-001) [todo]
blocks: -
dir: 2026-02-06-build-nightly-report
files: task.md

## Acceptance Criteria
- Nightly report job reads JSON export payload.
- Missing dependency behavior is documented and tested.
```

## Dependency Enforcement Demo

```bash
dot-tasks start build-nightly-report
```

Expected snippet:

```text
Error: Unmet dependencies: t-20260205-001. Use --force to override.
```

```bash
dot-tasks start build-nightly-report --force
```

Expected snippet:

```text
Started: build-nightly-report
```

## Update + Task Files Demo

```bash
dot-tasks update build-nightly-report priority=p1 owner=sam
dot-tasks path build-nightly-report
dot-tasks view document-command-help
```

Fields are set with `key=value` (`key=` clears one). `path` prints the task's absolute folder (it moved to `doing/` when started), so you can open `task.md` or add files there. `view` lists every file in the task folder, `task.md` first:

```text
Updated: build-nightly-report
/…/examples/basic-demo/.tasks/doing/2026-02-06-build-nightly-report
…
dir: 2026-02-03-document-command-help
files: task.md | plan.md
```

## Complete Demo

```bash
dot-tasks complete add-json-export
dot-tasks list done
```

Expected snippet:

```text
add-json-export                   p1        m       ready         2026-02-05
bootstrap-dot-tasks               p1        m       ready         2026-02-01
```

## Create + Rename + Delete Demo

```bash
dot-tasks create prepare-release-notes summary="Draft release notes" priority=p2 effort=s --nointeractive
dot-tasks rename prepare-release-notes prepare-v1-release-notes
dot-tasks delete prepare-v1-release-notes
dot-tasks list --json
```

`create` prints the path of the new `task.md`; write the description in its body.

Expected snippet:

```text
Created: prepare-release-notes (t-<YYYYMMDD>-<XXXX>)
/…/examples/basic-demo/.tasks/todo/<YYYY-MM-DD>-prepare-release-notes/task.md
Renamed: prepare-v1-release-notes
Moved to trash: prepare-v1-release-notes
```

## Reset Demo State

This walkthrough mutates tracked fixture files under `examples/basic-demo/.tasks`.
To reset to committed state from repo root:

```bash
git restore examples/basic-demo/.tasks
```
