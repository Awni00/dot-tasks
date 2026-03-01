## Plan

### Fix Enter Semantics in Fuzzy Multiselect (`fix-tag-multiselect`)

#### Summary
Fix fuzzy multiselect so `Enter` only submits current selections and does **not** auto-select the highlighted row when nothing was toggled.
Scope (chosen): apply to **all** fuzzy multiselect prompts (tags + dependencies).
Empty submit behavior (chosen): submit `[]`; for dependency editing, that means clear dependencies when user opted into editing.

#### Important Interface/Behavior Changes
- Affects shared selector helper: `src/dot_tasks/selector_ui.py` `select_fuzzy_many(...)`.
- No CLI flag/API schema changes.
- Behavioral change:
  - Before: `Enter` with zero toggles returns `[highlighted]` (InquirerPy default).
  - After: `Enter` with zero toggles returns `[]`.
- Impacted flows:
  - Tag selector in create/update prompt flows.
  - Dependency selector (when user opens dependency editor).

#### Implementation Plan
1. Bind task lifecycle first (dot-tasks).
- `dot-tasks start fix-tag-multiselect`
- Write full approved plan into bound task `plan.md`
- Log activity during implementation/testing
- `dot-tasks complete fix-tag-multiselect` after validation

2. Add a submit-only Enter override hook for fuzzy multiselect prompts in `src/dot_tasks/selector_ui.py`.
- Introduce internal helper (e.g. `_bind_fuzzy_submit_only(prompt)`):
  - Replace prompt `"answer"` keybinding handler via `prompt.kb_func_lookup`.
  - New handler for multiselect:
    - validates current result (preserve existing validation path)
    - if selected choices exist: submit selected values
    - if selected choices empty: submit `[]`
    - preserve cancel/error behavior (`KeyboardInterrupt`/`EOFError` handling remains at caller)
- Keep this helper no-op-safe if prompt object is missing expected attributes (test doubles / future compatibility).

3. Update `select_fuzzy_many(...)` to use the override.
- Build fuzzy prompt as today (`inquirer.fuzzy(..., multiselect=True, keybindings=...)`).
- Apply submit-only binding helper before `.execute()`.
- Keep existing toggle bindings (`space`, `tab`, `shift-tab`) and instruction text.

4. Keep prompt-level call sites unchanged.
- No change needed in `src/dot_tasks/prompt_ui.py` for `_prompt_tag_choice` / `_prompt_depends_on_choice`; they already route through `select_fuzzy_many`.

5. Update tests in `tests/test_prompt_ui.py`.
- Add unit coverage for the new override behavior:
  - `Enter` with no toggles => `[]`
  - `Enter` with existing toggles => selected values
- Keep and adjust existing selector tests if needed so fake prompt objects remain compatible with new hooking logic.
- Retain current tests for ordering and keybinding wiring.

6. Run validation.
- `pytest tests/test_prompt_ui.py tests/test_cli.py`
- If any dependency-flow regression appears, add focused regression tests in `tests/test_cli.py` for dependency-clear behavior under empty submission after user opts into dependency editing.

#### Test Cases and Scenarios
- Tags (create/update): pressing `Enter` without `Space` toggles submits empty selection.
- Tags: selecting one/many with `Space` then `Enter` submits only those toggled values.
- Dependencies: after user chooses to edit dependencies, `Enter` with none toggled clears dependency set (expected).
- Existing source-order guarantee still holds for selected results.
- Keyboard interrupt/cancel behavior remains unchanged.

#### Assumptions and Defaults
- Fix is intentionally global to all fuzzy multiselect paths.
- Empty submit is valid and intentional (`[]`), not a validation error.
- Dependency clearing on empty submit is expected when the dependency editor is explicitly opened.
- No changes to non-interactive CLI behavior.
