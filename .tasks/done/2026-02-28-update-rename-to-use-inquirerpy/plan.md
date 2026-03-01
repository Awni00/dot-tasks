# Goal Description
Update `dot-tasks rename` to use `inquirerpy` instead of `typer.prompt` for asking for the `new_task_name`. This matches the behavior of interactive prompts in other parts of the CLI like `create` and `update`. I will also check if `log-activity` needs a similar fix for its `note` prompt.

## Proposed Changes
### src/dot_tasks/cli.py
- Update `rename_cmd` to use `_safe_prompt("new_task_name")` instead of `typer.prompt("new_task_name")`.
- Import `_safe_prompt` from `.prompt_ui` if not already imported.
- Update `log_activity_cmd` to use `_safe_prompt("note")` instead of `typer.prompt("note")` for consistency.

## Verification Plan
### Automated Tests
- Run `pytest tests/test_cli.py -k test_rename` to ensure the rename tests pass.
- Run `pytest tests/test_cli.py -k test_log_activity` if I modify `log_activity_cmd`.
- Ensure all tests pass with `pytest`.

### Manual Verification
- Run `dot-tasks rename <id>` and ensure it prompts using inquirerpy.
