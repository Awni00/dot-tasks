# basic-demo

## Purpose

This directory is a safe, pre-populated demo workspace for `dot-tasks`.
Run commands from here to explore task lifecycle features without touching another project's `.tasks`.

## Setup

From the repository root:

```bash
uv pip install -e .
# or
pip install -e .
cd examples/basic-demo
```

The first `dot-tasks init` in a new workspace writes `.tasks/config.yaml` with `settings.interactive_enabled: true|false`.

Interactive pickers support keyboard navigation in prompt mode:

- `up/down` + `enter` for single selection
- `space` to toggle multi-select options and `enter` to submit
- in `dot-tasks create`, dependency selection is optional and only shown if you choose to set dependencies
- if selector UI is unavailable, prompts automatically fall back to numeric entry
- `Ctrl+C` cleanly backs out of interactive prompts

## Inspect Preloaded State

**List tasks in `.tasks/`**

```bash
dot-tasks list
```

Expected snippet:

```text
task_name              task_id         status     priority  effort  deps        created   
---------------------  --------------  ---------  --------  ------  ----------  ----------
build-nightly-report   t-20260206-001  todo       p0        l       blocked(1)  2026-02-06
add-json-export        t-20260205-001  todo       p1        m       ready       2026-02-05
document-command-help  t-20260203-001  doing      p2        s       ready       2026-02-03
bootstrap-dot-tasks    t-20260201-001  completed  p1        m       ready       2026-02-01
```

**View a particular task by name**

```bash
dot-tasks view build-nightly-report
```

Expected snippet:

```text
task_name: build-nightly-report
task_id: t-20260206-001
status: todo
priority: p0
effort: l
owner: alex
tags: reporting, automation
created: 2026-02-06
started: -
completed: -
dependencies:
- add-json-export (t-20260205-001) [todo]

body:

## Summary
- Build nightly report generation using exported task snapshots.

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

## Update Demo

```bash
dot-tasks update build-nightly-report --priority p0 --effort l --note "Escalated after dependency bypass"
```

Expected snippet:

```text
Updated: build-nightly-report
```

## Complete Demo

```bash
dot-tasks complete add-json-export
dot-tasks list done
```

Expected snippet:

```text
add-json-export         t-20260205-001  completed  p1  m  ready  2026-02-05
bootstrap-dot-tasks     t-20260201-001  completed  p1  m  ready  2026-02-01
```

## Create + Rename + Delete Demo

```bash
dot-tasks create prepare-release-notes --summary "Draft release notes" --priority p2 --effort s --nointeractive
dot-tasks rename prepare-release-notes prepare-v1-release-notes
dot-tasks delete prepare-v1-release-notes
dot-tasks list --json
```

Expected snippet:

```text
Created: prepare-release-notes (t-<YYYYMMDD>-<NNN>)
Renamed: prepare-v1-release-notes
Moved to trash: prepare-v1-release-notes
```

## Reset Demo State

This walkthrough mutates tracked fixture files under `examples/basic-demo/.tasks`.
To reset to committed state from repo root:

```bash
git restore examples/basic-demo/.tasks
```
