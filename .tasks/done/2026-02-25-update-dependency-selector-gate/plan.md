## Plan

### Update Dependency Selector Gate (`update-dependency-selector-gate`)

#### Summary
Add a dependency-edit confirmation gate to interactive `dot-tasks update` so users are asked before opening dependency multiselect.
Chosen default: **No** (pressing Enter skips dependency editing).

#### Public Interfaces / Behavior Changes
- Interactive `update` flow in `src/dot_tasks/prompt_ui.py` will include:
  - New yes/no prompt: `Update task dependencies?`
  - Default answer: `No`
- If user answers `No`, dependencies are left unchanged.
- If user answers `Yes`, existing dependency multiselect opens as today.
- Non-interactive CLI flags (`--depends-on`, `--clear-depends-on`) remain unchanged.
- No new CLI flags or data schema changes.

#### Implementation Plan
1. Update `update_form(...)` dependency section in `src/dot_tasks/prompt_ui.py`.
- Keep current priority/effort/spec_readiness/owner/tags prompts unchanged.
- Replace unconditional dependency selector call with gated flow:
  - If `dependency_options` is empty:
    - skip gate and selector
    - return `depends_on=[]`, `replace_depends_on=False`
  - If options exist:
    - ask `_prompt_yes_no("Update task dependencies?", default=False)`
    - `None` => cancel form (`return None`)
    - `False` => skip selector, keep deps unchanged (`replace_depends_on=False`)
    - `True` => run `_prompt_depends_on_choice(..., default_values=task.metadata.depends_on)`
      - `None` => cancel form
      - selected list => return it with `replace_depends_on=True`

2. Keep `update_cmd` behavior in `src/dot_tasks/cli.py` as-is.
- It already consumes `replace_depends_on` from form and only clears/replaces when true.
- No code changes expected unless tests reveal a gap.

3. Update prompt-level tests in `tests/test_prompt_ui.py`.
- Adjust existing dependency-default test to include gate decision (`Yes`) before selector is exercised.
- Add tests:
  - Gate `No` skips selector and returns `replace_depends_on=False`
  - Gate `Yes` runs selector and returns `replace_depends_on=True`
  - Gate cancel (`None`) returns `None`
  - Empty dependency options skip gate and preserve unchanged behavior (`replace_depends_on=False`)

4. Update CLI-level regression coverage in `tests/test_cli.py`.
- Add scenario where task already has dependencies and interactive form returns:
  - `depends_on=[]`
  - `replace_depends_on=False`
- Assert dependencies remain unchanged after `update`.

5. Task tracking workflow for implementation (bound task `t-20260225-004`).
- `dot-tasks start update-dependency-selector-gate`
- Write full approved plan to task `plan.md`
- `dot-tasks log-activity ...` during implementation/testing
- `dot-tasks complete update-dependency-selector-gate` when done

#### Test Cases and Scenarios
- Interactive update, choose **No** at dependency gate:
  - dependency selector not shown
  - existing dependencies unchanged
- Interactive update, choose **Yes**:
  - dependency selector shown with current dependencies preselected
  - selection replaces current dependency set
- Cancel at dependency gate:
  - command exits canceled path
- Cancel inside dependency selector after choosing Yes:
  - command exits canceled path
- No dependency candidates available:
  - no gate shown, no dependency mutation

#### Assumptions and Defaults
- Dependency gate appears only when there are available dependency candidates.
- Default gate answer is `No`.
- Choosing `No` means “do not modify dependencies” (not “clear dependencies”).
- Existing behavior for non-interactive updates and flag-driven updates is unchanged.
