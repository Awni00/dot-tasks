### Implement Type-to-Search for Root Command Picker (`t-20260305-002`)

### Summary
- Bind this work to existing task `t-20260305-002` (`dot-tasks-base-command-type-search-cmd`).
- Keep work in current workspace (no new worktree).
- Change the root `dot-tasks` command picker to use fuzzy type-to-search by default, while preserving current numeric fallback behavior when selector UI is unavailable.

### Implementation Changes
- In [prompt_ui.py](/Users/awni/Documents/project-code/dot-tasks/src/dot_tasks/prompt_ui.py), update `choose_command(...)` to use `select_fuzzy(...)` instead of `select_one(...)`.
- Keep command option rendering shape (`command name + summary`) so fuzzy matching can hit both command name and visible description text.
- Preserve all existing fallback semantics:
  - On `SelectorUnavailableError`, print warning and fall back to numeric menu.
  - `None`/cancel from fuzzy prompt returns `None` and lets caller keep current cancel flow.
- Do not change `cli.py` invocation flow; root callback behavior remains the same except improved command selection UX.

### Test Plan
- Update/add tests in [test_prompt_ui.py](/Users/awni/Documents/project-code/dot-tasks/tests/test_prompt_ui.py):
  1. `choose_command` uses fuzzy selector when available (and does not hit numeric prompt).
  2. `choose_command` returns `None` on fuzzy cancel.
  3. `choose_command` falls back to numeric picker on selector failure (existing behavior preserved).
  4. (Optional but recommended) ensure command options passed to fuzzy selector include formatted summary text.
- Keep existing CLI tests in [test_cli.py](/Users/awni/Documents/project-code/dot-tasks/tests/test_cli.py) green to confirm root command execution/cancel behavior is unchanged.
- Add a short purpose comment for each new or modified test per repo guidance.

### Assumptions and Defaults
- No public CLI flags or command names change; this is UX behavior-only.
- No docs update is required unless we find an explicit arrow-only statement during implementation.
- When execution begins (outside Plan Mode), lifecycle will follow:
  1. `dot-tasks start t-20260305-002`
  2. write this full approved plan to the task’s `plan.md`
  3. implement + test
  4. `dot-tasks log-activity ...` during progress
  5. `dot-tasks complete ...` only after acceptance criteria are met.
