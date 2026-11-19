# Task workflow

How the dot-tasks repo tracks its own work with dot-tasks. Agents are pointed here from AGENTS.md and the dot-tasks skill.

## When to create a task
- Any feature, bug fix or refactor that needs planning (heuristic: you would use plan mode) or spans more than one session.
- Quick one-off edits and questions do not need a task.
- Confirm the task with the user before starting it (`dot-tasks start <task>`).

## Files in a task folder
- `task.md`: frontmatter with a one-line `summary` (set with `summary="..."` on create/update), and the task description in the body, written directly in the file in whatever form suits the task.
- `plan.md` (optional): the approved plan from plan mode, copied verbatim once the user approves it. Keep it current if the plan changes during implementation.
- Tasks created before 0.2.0 also contain `activity.md`; leave those files as they are.

## Wrapping up a session
- Update `plan.md` if implementation departed from it.
- Commit work on the feature branch; do not merge to main until the user approves.

## Before completing a task
- Acceptance criteria are met and the user approved the result.
- Tests pass (`source .venv/bin/activate && pytest`), and every new test has a comment stating its purpose.
- The feature branch is merged to main.

## Tags
- Free-form, by area of the CLI (e.g. `list`, `tags`, `dependencies`, `agent`). Reuse existing tags (`dot-tasks tags`) before inventing new ones.

## Referring to tasks
- Cite tasks by name or id, never by folder path (folders move with status). `dot-tasks path <task>` resolves one.
