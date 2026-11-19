# Task workflow

How this demo project tracks work with dot-tasks. Agents are pointed here from AGENTS.md and the dot-tasks skill.

## When to create a task
- Work that needs a plan or spans more than one session.

## Files in a task folder
- `task.md`: frontmatter with a one-line `summary` and the fields `priority`, `effort`, `owner` (set with `dot-tasks update <task> key=value`), and the description in the body (edit directly).
- `plan.md` (optional): the approved implementation plan, written when work starts.

## Wrapping up a session
- Update `plan.md` if the plan changed.

## Before completing a task
- Acceptance criteria in `task.md` are met.

## Tags
- By area (e.g. `api`, `cli`, `docs`, `reporting`); `dot-tasks tags` lists them.

## Referring to tasks
- Cite tasks by name or id, never by folder path (folders move with status). `dot-tasks path <task>` resolves one.
