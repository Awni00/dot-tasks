## Plan

### Implementation
1. Add a status filter parser in `/Users/awni/Documents/project-code/dot-tasks/src/dot_tasks/service.py` that accepts `todo|doing|done`, normalizes `done` → `completed`, treats `all` as no filter (returns None), and raises `TaskValidationError` for unknown tokens or empty segments.
2. Update `Service.list_tasks` in `/Users/awni/Documents/project-code/dot-tasks/src/dot_tasks/service.py` to filter by a set of statuses from the parser (supporting multiple statuses), preserving the existing tag filtering and sorting behavior.
3. Change the CLI default for `list` to `todo|doing` and update the help text to mention multi-status filters and `all` in `/Users/awni/Documents/project-code/dot-tasks/src/dot_tasks/cli.py`.
4. Update docs to reflect the new status filter format and default in `/Users/awni/Documents/project-code/dot-tasks/README.md` (and optionally `/Users/awni/Documents/project-code/dot-tasks/agent-tools/skills/dot-tasks/SKILL.md` if you want the skill text to stay accurate).

### Tests
1. Update `test_list_json_sorted_by_status_and_date_created_desc` in `/Users/awni/Documents/project-code/dot-tasks/tests/test_cli.py` to call `list all` so it still validates cross-status ordering. Add a one-line purpose comment.
2. Add a test that `dot-tasks list` (no status) returns only `todo` + `doing` via `--json` (purpose comment required).
3. Add a test that `dot-tasks list todo|doing --json` returns both statuses (purpose comment required).
4. Add a test that `dot-tasks list all --json` returns all statuses (purpose comment required).
