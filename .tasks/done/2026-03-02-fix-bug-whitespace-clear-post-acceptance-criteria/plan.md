## Plan
1. Reproduce the bug in a real interactive TTY session for `dot-tasks create` and confirm the failure stage is the task body section prompts (`Summary`, `Acceptance Criteria`).
2. Compare behavior between standard terminal and VSCode-like terminal env to isolate whether the issue is tied to prompt rendering capabilities.
3. Trace the interactive code path:
   - `create_cmd` / `update_cmd` -> `prompt_ui.create_form` / `prompt_ui.update_form`
   - `_safe_prompt(..., multiline=True)` -> `selector_ui.select_text(..., multiline=True)` -> InquirerPy text prompt.
4. Implement a stability-first patch:
   - Avoid the problematic multiline InquirerPy path for section entry.
   - Use `typer.prompt` fallback for multiline section fields.
   - Remove multiline-only hint text (`Esc+Enter`) when fallback prompt is used.
5. Add regression tests for:
   - Selector multiline CPR gating behavior.
   - `_safe_prompt` multiline fallback behavior and messaging.
6. Verify:
   - Run focused unit tests in `tests/test_prompt_ui.py`.
   - Run interactive-related CLI tests in `tests/test_cli.py -k interactive`.
   - Perform a live TTY smoke run in VSCode-like terminal env to confirm no section-prompt whitespace clearing artifact.
