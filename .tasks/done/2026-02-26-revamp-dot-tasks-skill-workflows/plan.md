## Plan: Revamp `dot-tasks` Skill Around 3 Core Workflows (Lean + Structured)

### Summary
Rewrite `agent-tools/skills/dot-tasks/SKILL.md` into a use-case-first structure centered on the three workflows, with concise branch rules and a shared lifecycle loop. Also restore snippet marker validity and simplify snippet tests.

### Scope
1. Revamp skill structure/content in `agent-tools/skills/dot-tasks/SKILL.md`.
2. Restore missing `<!-- dot-tasks:end task-management -->` marker in `src/dot_tasks/resources/agents/task-management-dot-tasks.md`.
3. Trim `tests/test_agents_snippet.py` to lean marker/upsert validation.
4. Keep full command catalog in SKILL, grouped cleanly.

### Out of Scope
1. CLI/API/type changes.
2. Broad README rewrite.
3. New broad SKILL-content tests.

### SKILL Structure
1. Intro and `When To Use` with 3 trigger workflows.
2. Workflow 1: suggest next task with triage rubric and blocked fallback.
3. Workflow 2: begin/resume existing task with status branches and readiness gate.
4. Workflow 3: significant new work with create-and-bind prompt path.
5. Shared lifecycle loop including `update` and completion gate.
6. Full command catalog grouped by setup/discovery/lifecycle/maintenance.
7. Lean guardrails and data contract.

### Tests
1. Run `pytest tests/test_agents_snippet.py`.

### Acceptance
1. SKILL is use-case-first around 3 workflows.
2. Snippet has both begin/end markers.
3. Snippet tests are lean and pass.
