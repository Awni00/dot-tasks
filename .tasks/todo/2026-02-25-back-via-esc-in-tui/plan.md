# ESC Back Navigation in InquirerPy TUI (`t-20260225-005`)

## Summary
Implement `Esc` as “back one step” across all InquirerPy-based interactive flows, while preserving `Ctrl-C` as full cancel.
If a subcommand is launched from the root command picker, `Esc` at that subcommand’s first step should return to the picker.
If a subcommand is run directly (no parent picker), `Esc` at first step should cancel the command (current behavior).

## Important Interface/Type Changes
- In `src/dot_tasks/selector_ui.py`, add a new internal exception type (e.g., `SelectorBackError`) to represent back-navigation distinctly from cancel.
- `select_*` helpers keep existing return types for normal/cancel paths, but now additionally raise `SelectorBackError` when user presses `Esc`.
- No CLI flag/argument/schema changes; JSON output contracts remain unchanged.

## Implementation Plan

1. Add back-navigation signaling in selector layer
- File: `src/dot_tasks/selector_ui.py`
- Add `Esc` keybinding to all InquirerPy prompts used here (`select_one`, `select_text`, `select_fuzzy`, `select_many`, `select_fuzzy_many`) via `keybindings` with `skip` action including `escape`.
- Preserve existing multiselect toggle bindings in `select_fuzzy_many` while merging in `skip`.
- Interpret prompt result `None` (from `Esc` skip path) as back by raising `SelectorBackError`.
- Keep `KeyboardInterrupt`/`EOFError` behavior as cancel (`None`), preserving `Ctrl-C` semantics.
- Update instruction text where present to include `esc to go back` for clarity.

2. Make form flows back-aware (state-machine style)
- File: `src/dot_tasks/prompt_ui.py`
- Keep fallback numeric mode behavior unchanged.
- For InquirerPy mode, propagate `SelectorBackError` and handle it in multi-step forms by moving to previous step.
- Refactor these to explicit step indices/loops:
  - `init_config_form`
  - `create_form`
  - `update_form`
- Back behavior rules:
  - Middle step `Esc`: go to previous step, preserving already-entered values.
  - First step `Esc`: bubble up `SelectorBackError` (caller decides parent/back vs cancel).
- For `_prompt_tags`, support nested back:
  - Back from “new tags” returns to existing-tags selector.
  - Back from existing-tags selector bubbles to previous outer form step.

3. Integrate parent-menu back in CLI
- File: `src/dot_tasks/cli.py`
- Add internal “in command picker session” context + internal exception (e.g., `BackToCommandPicker`).
- Change `_run_command_picker` to loop:
  - Select command.
  - Invoke command.
  - If command raises back-to-picker signal, re-open command picker instead of exiting.
- In `_run_and_handle`, catch `SelectorBackError`:
  - If currently invoked from root picker session: raise `BackToCommandPicker`.
  - Otherwise: call existing canceled exit path (`Canceled.`, exit code 1).
- Keep top-level command picker `Esc` as cancel/exit code 0 (no parent above picker).

4. Documentation update
- File: `README.md`
- Add a short interactive UX note:
  - `Esc` = back
  - `Ctrl-C` = cancel
  - In root picker session, first-step `Esc` in subcommand returns to picker

5. Task lifecycle updates when implementation starts
- Use `dot-tasks` workflow against `t-20260225-005`:
  - `dot-tasks start t-20260225-005`
  - append implementation progress via `dot-tasks log-activity --note ...`
  - `dot-tasks complete t-20260225-005` after acceptance criteria pass

## Test Cases and Scenarios

1. Selector layer tests (`tests/test_prompt_ui.py`)
- `select_one/text/fuzzy/many/fuzzy_many` raise `SelectorBackError` when prompt returns `None` (Esc skip path).
- Existing keyboard-interrupt tests still pass (`Ctrl-C` returns cancel path, not back).

2. Form back-navigation tests (`tests/test_prompt_ui.py`)
- `create_form`: Esc in mid-form goes back and allows editing prior field.
- `create_form`: Esc at first field bubbles back signal.
- `update_form`: same back behavior as create.
- `init_config_form`: back from agents-file prompt returns to append-agents choice.
- `_prompt_tags`: back from new-tags input returns to existing-tags selection.

3. CLI parent-picker behavior tests (`tests/test_cli.py`)
- Root picker -> choose `create` -> Esc on first create prompt returns to command picker.
- Direct `dot-tasks create` -> Esc on first prompt exits canceled with code 1.
- Root picker Esc at command selection still exits canceled with code 0.
- `Ctrl-C` within subcommand prompt remains full cancel (no forced return to picker).

4. Regression tests
- Existing interactive cancel tests keep expected outputs/codes where behavior is intentionally unchanged.
- Run targeted suites:
  - `pytest -q tests/test_prompt_ui.py`
  - `pytest -q tests/test_cli.py -k "interactive or cancel or picker or create or update"`

## Assumptions and Defaults
- Bound task: `t-20260225-005` (`back-via-esc-in-tui`).
- Scope: all InquirerPy-based prompts.
- Top-level behavior in picker session: first-step Esc in subcommand returns to command picker.
- Direct subcommand behavior: first-step Esc cancels command.
- Numeric fallback prompts do not gain new back semantics (unchanged).
- No changes to task file formats, command signatures, or JSON payload structure.
