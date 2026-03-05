# Early `create` Name Validation: Format + Uniqueness + Full Name Validity

## Summary
Extend interactive `dot-tasks create` so `task_name` is validated immediately and repeatedly before any other fields are collected.
“Complete validity” for this task means: non-empty, kebab-case format, and uniqueness (same rule used by create today, including trashed tasks).

## Public/API/Type Changes
1. Add `TaskService.validate_new_task_name(task_name: str) -> None`:
   - Use existing `validate_task_name` for kebab-case format.
   - Use existing `_ensure_unique_task_name` for uniqueness.
   - Preserve existing error messages/exceptions.
2. Update `create_form` signature in `prompt_ui.py`:
   - Add optional callback `validate_task_name: Callable[[str], None] | None = None`.
3. Update `create_cmd` in `cli.py`:
   - Pass `validate_task_name=svc.validate_new_task_name` to `create_form(...)`.

## Implementation Steps
1. Replace one-shot `task_name` prompt in `create_form` with a loop:
   - Prompt name.
   - If canceled: return `None`.
   - Trim.
   - If empty: print `Error: task_name is required` and re-prompt.
   - Run validator callback when provided.
   - On validation exception: print `Error: <message>` and re-prompt.
   - On success: continue form flow.
2. Keep dependency validation loop unchanged.
3. Keep service-level `create_task` validation for defense-in-depth.

## Tests
1. `tests/test_prompt_ui.py`
   - Invalid kebab-case then valid: re-prompt and succeed.
   - Duplicate validator error then valid: re-prompt and succeed.
   - Blank then valid: re-prompt and succeed.
   - Cancel during name loop: returns `None`.
2. `tests/test_cli.py`
   - `create_cmd` passes `svc.validate_new_task_name` to `create_form`.
   - Keep existing non-interactive duplicate-name test unchanged.

## Acceptance Criteria
1. Interactive create does not proceed past `task_name` until non-empty, kebab-case, and unique.
2. Duplicate names are rejected immediately at the name prompt.
3. Existing invalid-format and duplicate-name error texts remain consistent.
4. Existing non-interactive/service behaviors remain unchanged.
5. Targeted and full pytest suite pass.
