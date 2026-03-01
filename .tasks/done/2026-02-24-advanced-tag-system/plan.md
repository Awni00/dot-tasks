## Plan

### Advanced Tag System: Two-Step Picker for `create` + `update`

#### Summary
Implement a shared interactive tag UX for `dot-tasks create` and `dot-tasks update`:
1. Fuzzy multi-select existing tags.
2. Optional entry of new tags (comma-separated).
Existing tag suggestions come from all non-trash tasks (`todo`, `doing`, `done`).
For interactive `update`, selected tags are treated as the final set (deselect removes tag).

#### Public Interfaces and Behavioral Changes
- Interactive `create` changes from a single `"tags (comma separated)"` text prompt to the two-step tag flow.
- Interactive `update` changes from `"add tags..."` to the same two-step flow with current tags preselected.
- Interactive `update` form path now applies replace semantics for tags.
- Non-interactive CLI behavior (`--tag`, `--replace-tags`) remains unchanged.
- Internal function signatures to extend:
  - `create_form(..., tag_options=...)`
  - `update_form(..., tag_options=...)`

#### Implementation Plan
1. Add tag-option construction helper in `src/dot_tasks/cli.py`.
   Define `_tag_choices(tasks: list[Task]) -> list[tuple[str, str]]` that dedupes tags, counts usage, and returns labels like `backend (3)` with raw tag value.

2. Wire tag options into interactive `create`.
   In `create_cmd`, when `open_form` is true, load tasks once, build `dependency_options` and `tag_options`, and pass both to `create_form`.

3. Wire tag options into interactive `update`.
   In `update_cmd`, when `open_form` is true, load tasks once, build `dependency_options` (excluding selected task) and `tag_options`, and pass both to `update_form`.

4. Enforce replace semantics for interactive `update`.
   Add `local_replace_tags` in `update_cmd`.
   Initialize from CLI `replace_tags`.
   Set `local_replace_tags = True` when the interactive form path is used.
   Pass `replace_tags=local_replace_tags` to `svc.update_task`.

5. Add reusable tag prompt helpers in `src/dot_tasks/prompt_ui.py`.
   Implement a two-step `_prompt_tags(...)` helper using existing selector primitives (`select_fuzzy_many` + numeric fallback).
   If no existing tags are available, skip selection and prompt only for new tags.
   Return merged/deduped tags or `None` on cancel.

6. Update `create_form` and `update_form` to use `_prompt_tags(...)`.
   `create_form` uses empty defaults.
   `update_form` preselects `task.metadata.tags`.
   Keep all non-tag form fields and dependency behavior unchanged.

7. Update tests in `tests/test_prompt_ui.py`.
   Add coverage for create/update tag flow, cancel paths, preselected defaults, and fallback behavior.
   Adjust existing form monkeypatches for new `tag_options` parameter.

8. Update tests in `tests/test_cli.py`.
   Add/adjust tests to verify `tag_options` are passed to forms and interactive `update` forces replace semantics.
   Keep regressions for non-interactive `--tag`/`--replace-tags` behavior.

9. Add brief docs note in `README.md`.
   Document that interactive create/update support selecting existing tags and adding new ones.

#### Test Cases and Scenarios
- Interactive create with existing tags: select-only, new-only, mixed, dedupe behavior.
- Interactive create with no existing tags: new-tag prompt only.
- Interactive update: preselected current tags, deselect removes tags, adding new tags works.
- Cancel behavior in each tag step returns `Canceled.` flow.
- Non-interactive create/update unchanged for `--tag` and `--replace-tags`.
- Dependency selection and other command behavior unchanged.

#### Assumptions and Defaults
- Tag suggestions include all non-trash tasks.
- Tag option labels show counts; stored value stays the raw tag string.
- Interactive `update` form mode is authoritative replace mode for tags.
- Explicit flag-driven update paths preserve existing semantics.
