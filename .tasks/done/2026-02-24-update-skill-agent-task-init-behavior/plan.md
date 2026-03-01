## Plan: Update Existing-Task Start Guidance (`t-20260224-005`)

### Summary
Revise `dot-tasks` agent guidance so starting an existing task is gated by spec clarity.  
If task intent is vague, agents must ask open-ended clarifying questions first (explicit two-stage sequence), not assume details.

### Scope
1. Update canonical AGENTS snippet content:
`src/dot_tasks/resources/agents/task-management-dot-tasks.md`

2. Update packaged skill guidance:
`agent-tools/skills/dot-tasks/SKILL.md`

3. Sync repository AGENTS managed block to canonical snippet text:
`AGENTS.md`

4. Update snippet-focused tests only:
`tests/test_agents_snippet.py`

### Out of Scope
1. CLI behavior changes (`create/start/update` logic).
2. README-wide workflow rewrite.
3. Broader CLI test additions.

### Behavior Spec To Encode In Docs
1. When user asks to begin an existing task, agent must inspect task metadata and body first (`dot-tasks view ... --json`).
2. `spec_readiness` is a strong signal:
   - `unspecified` or `rough`: require clarification before starting.
   - `ready` or `autonomous`: proceed faster, still validate obvious gaps.
3. If unclear, agent must ask clarifying questions in two stages:
   - Stage 1: high-level intent/outcome/scope.
   - Stage 2: implementation constraints and acceptance criteria.
4. Agent must not proceed on unstated assumptions when high-level intent is unclear.
5. Once clarity is achieved and tracking is bound, continue normal lifecycle (`start` -> plan/logs -> complete).

### Public APIs / Interfaces / Types
1. No Python API, CLI flags, or schema changes.
2. Documentation contract changes only:
   - Agent policy in canonical snippet.
   - Agent behavior instructions in skill file.

### Test Plan
1. Update existing assertion test in:
`tests/test_agents_snippet.py`
   - Keep existing checks for discovery/confirmation flow.
   - Add assertions for new start-with-clarity guidance language (readiness gate + two-stage clarification + no assumption behavior).
2. Run targeted test:
   - `pytest tests/test_agents_snippet.py`
3. If needed, run related AGENTS snippet tests in CLI suite only when failures indicate coupling.

### Implementation Steps
1. Edit canonical snippet text with new “begin existing task” guidance and guardrails.
2. Mirror equivalent policy in packaged skill `Default Agent Loop` and `Working Rules`.
3. Regenerate/sync repository `AGENTS.md` managed block from canonical snippet (or edit managed block to exact canonical text).
4. Update snippet unit-test assertions to match new wording.
5. Run targeted tests and adjust wording only as needed for deterministic assertions.

### Acceptance Criteria
1. Canonical snippet explicitly defines strong `spec_readiness` gating and two-stage clarifying flow.
2. Packaged skill contains the same policy (no contradictory wording).
3. Repo `AGENTS.md` snippet matches canonical policy.
4. `tests/test_agents_snippet.py` passes with new assertions.
5. No CLI/API behavior changed.

### Assumptions And Defaults
1. Bound task is `t-20260224-005` (`update-skill-agent-task-init-behavior`).
2. “Mainly update SKILL.md and AGENTS snippet” means no broad docs sweep.
3. “Update snippet tests only” means only `tests/test_agents_snippet.py` is required unless failures force minor related updates.
