# Goal Description

Support "regression" of task status (e.g. moving a task back from `doing` to `todo` or `completed` to `doing`). The most intuitive way to handle this without introducing too many new commands is to allow the `dot-tasks update` command to accept a `--status` flag and interactive prompt choice.

## Proposed Changes

### src/dot_tasks/service.py
- **[MODIFY]** `TaskService.update_task(..., status: str | None = None)`
  - Add logic to accept `status` updates.
  - If `status` differs from the current `task.metadata.status`:
    - Move directory to the new status folder using `storage.move_task_dir`.
    - Handle date changes contextually depending on the transition:
      - To `todo`: reset `date_started` and `date_completed` to `None`.
      - To `doing`: reset `date_completed` to `None`. Set `date_started = _today()` if it was `None`.
      - To `completed`: Set `date_completed = _today()` if `None`. Set `date_started = task.metadata.date_created` if `None`.
    - Update `task.metadata.status = status`.

### src/dot_tasks/cli.py
- **[MODIFY]** `update_cmd`
  - Add `--status` option (constrained to choices `["todo", "doing", "completed"]`).
  - Pass the status down to `svc.update_task`.
  - Also ensure that if `update_form` returns a `status`, it is passed.

### src/dot_tasks/prompt_ui.py
- **[MODIFY]** `update_form`
  - Add `status` to the list of prompts with choices `["todo", "doing", "completed"]` and the default set to `task.metadata.status`.

## Verification Plan

### Automated Tests
- Run `pytest tests/test_cli.py` to ensure `update` with `--status` correctly modifies status, updates dates, and moves the directory.
- Run `pytest tests/test_prompt_ui.py` to verify `update_form` supports the new `status` prompt.
