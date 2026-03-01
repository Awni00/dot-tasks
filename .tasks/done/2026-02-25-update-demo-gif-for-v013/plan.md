# Update Demo GIF for v0.1.3

## Goal Description
The `dot-tasks` interactive CLI flows have been significantly augmented since version `v0.1.2`, notably adding:
- Status labels in interactive task pickers
- Spec readiness metadata
- Two-step interactive tag picker 
- Configurable multiline task body sections
- Additional `dot-tasks` commands (`install-skill`, `add-agents-snippet`, `log-activity`)

This task updates the `cli-demo.tape` VHS recording to showcase these new features, generating an updated `cli-demo.gif` for the README.

## Proposed Changes

### Tape File
#### [MODIFY] [cli-demo.tape](file:///Users/awni/Documents/project-code/dot-tasks/assets/demo/cli-demo.tape)
- Update down-arrow navigation for root menu selection (to select `list` correctly, which is now the 7th command, index 6).
- Update the `create` flow recording:
  - Input task name `cli-demo-task`.
  - Provide `priority` (p3) and `effort` (s).
  - Leave `owner` blank.
  - Provide `Summary` using the new multiline block (finish with Esc+Enter).
  - Provide `Acceptance Criteria` using the new multiline block (finish with Esc+Enter).
  - Set `spec_readiness` to `ready`.
  - Use the new tag picker (fuzzy search to add tags `demo`, `readme`).
  - Set dependencies (select "no" or "yes" with a sample).
