# dot-tasks 0.2.0 redesign

## Context
dot-tasks hardcodes a software workflow: `start` writes a plan.md stub, every command appends to
activity.md, and the packaged skill prescribes spec.md → plan.md → decisions.md. It is now also used
for research work (theory, experiments, writing, literature) where per-task records differ: per-session
AI-use files, human-review notes, outcomes. 0.2.0 strips the tool down to task state plus the task.md
skeleton and leaves every other convention to project-level instructions in `.tasks/README.md`.
Checks, file scaffolding and templates can be added later if practice shows a need.

Philosophy: the tool owns state (id, status/folder, dates, deps, tags and other frontmatter, changed
via commands); the model owns content (task.md body and every other file, edited directly). Agents
think about dot-tasks only at bind and wrap-up. The tool provides mechanisms; projects define
workflows (`.tasks/config.yaml` for the few mechanical settings, `.tasks/README.md` for conventions,
a one-line trigger in AGENTS.md/CLAUDE.md).

Target workflows, all served by README conventions with no special-casing in the tool:
(a) software: plan.md from plan mode, optional notes/log file; (b) research: `sessions/<date>-<id>.md`
written at session end + body sections Summary / Done when / Outcome / Human review; (c) task.md only.

## Decisions
1. **The tool writes only `task.md`.** No plan.md, activity.md or spec.md. No `task_files` config, no
   `add` command, no template mechanism, no completion checks. Other files in a task folder are
   written by the model directly, following the project README.
2. **Drop `activity.md` and `log-activity`.** Frontmatter dates record the lifecycle. A project wanting
   a log says so in its README; the model appends to a file itself.
3. **Workflow doc = `.tasks/README.md`** (fixed path, optional). Only the AGENTS snippet and the skill
   point to it ("This project's task workflow is in `.tasks/README.md`; read it before working on a
   task."). The tool itself never mentions it: the workflow is project-wide, not per-task, and the tool
   serves humans as well as agents. `start`/`view`/`complete` output and `view --json` stay as today;
   `dot-tasks path` covers finding a task's folder. (Revised 2026-11-19; supersedes the earlier
   "start/view print a pointer" decision and the configurable path-format idea.)
4. **Body sections**: keep `settings.task_body_sections` unchanged. Fix the interactive `update` form
   (the only path that edits the body) so it replaces only the configured sections and keeps
   hand-added sections and their order; today it re-renders the body and drops them.
5. **New `dot-tasks path <task>`**: prints the absolute task folder for a name or id (one line, no
   decoration). Supports the convention "refer to tasks by name or id, never by path".
6. **`init` writes a starter `.tasks/README.md`** only if none exists: a short skeleton with headed
   placeholders (when to create a task; files a task holds; wrap-up; before completing; tags) and
   one line: "Templates for task files, if any: `.tasks/templates/`". Templates are a project
   convention only; the tool has no template code (an `add` command may come in a later version).
7. **Unchanged**: status folders todo/doing/done/trash; metadata fields (priority, effort,
   spec_readiness, owner, due_date) — revisit later; no `dropped` status (tag + Outcome).
8. **Minimal skill and snippet** (see step 5 below).
9. **Migration**: no config changes needed. Old plan.md/activity.md stay as ordinary files.
   Breaking: `log-activity` removed; `start` no longer creates plan.md. Version 0.2.0.

## Implementation plan
0. After approval: `dot-tasks create v0-2-redesign` in this repo; copy this plan to
   `.tasks/todo/<date>-v0-2-redesign/plan.md`; ask whether to implement in a git worktree (AGENTS.md).
   Leave the untracked tasks and `tmp.txt` alone.
1. **Core** (`src/dot_tasks/`):
   - `models.py`: remove `Task.activity_path`, `Task.plan_path`.
   - `storage.py`: remove `append_activity`; add `write_starter_readme_if_missing(tasks_root) -> bool` with the skeleton text.
   - `service.py`: drop activity touch/logging in `create_task`, `start_task`, `complete_task`,
     `update_task`, `rename_task`, `delete_task`; drop plan.md stub in `start_task`; delete
     `log_activity`. Add `_replace_body_sections(body, values)` (reuse the split logic of
     `_parse_body_sections`): replace content of matching `## ` sections in place, keep preamble and
     non-configured sections, append missing named sections at the end; use it in `update_task`.
2. **CLI** (`cli.py`): remove `log-activity` command and its palette entry; add `path` command (selector or interactive picker like
   `start`); `init` calls `write_starter_readme_if_missing` and echoes the result; update help strings
   ("Move task to doing and initialize plan.md").
3. **Render** (`render.py`): `_task_file_detail_state` treats only `task.md` as canonical and lists
   every other entry (files and dirs like `sessions/`) as files.
4. **Tests** (`tests/test_cli.py`, `test_render.py`, `test_storage.py`, `test_examples_demo.py`): delete
   log-activity/activity/plan-stub tests; update file-listing assertions. New tests, each commented:
   - create/start/complete write no activity.md or plan.md (tool writes only task.md);
   - `path` resolves by name and by id, errors on unknown task;
   - `init` writes the starter README once and never overwrites an existing one;
   - interactive `update` keeps a hand-added section and the order of others;
   - `view` lists hand-added files/dirs (e.g. `sessions/`) next to task.md.
5. **Agent-facing docs**:
   - `agent-tools/skills/dot-tasks/SKILL.md`: rewrite as a ~40-line reference: data model (folders,
     frontmatter, body sections), state/content split (state only via commands; edit content files
     directly), refer to tasks by name/id (`dot-tasks path`), command list, and a plain statement: "This
     project's task workflow is in `.tasks/README.md`; read it before working on a task."
     Drop spec/plan deliverables, triage rubric, readiness checks, decisions.md.
   - `resources/agents/task-management-dot-tasks.md`: trigger + the same plain pointer to `.tasks/README.md` (≈5 lines); it is the only pointer, so
     word it clearly.
6. **User docs**: README (layout, typical workflow, commands table incl. `path`, removal of
   `log-activity`, new "Project workflow doc" section with a short example, "Migrating from 0.1"
   section); `examples/basic-demo/{README,AGENTS}.md` updated; `_version.py` → `0.2.0`.
7. **This repo's own `.tasks/`**: add a `.tasks/README.md` describing its software conventions
   (optional plan.md from plan mode), so the repo dogfoods the new design.

## Verification
- `source .venv/bin/activate && pytest` — all tests green.
- Manual run in a scratch dir: `dot-tasks init --nointeractive` (README skeleton created),
  `create x`, `start x` (no plan.md, no activity.md), `view x`, `path x`,
  interactive `update x` after hand-adding a section, `complete x`; `dot-tasks log-activity` →
  "No such command".
- Run against this repo's `.tasks/` (`list all`, `view` on an old done task) to confirm legacy tasks
  with activity.md/plan.md still load and display.
