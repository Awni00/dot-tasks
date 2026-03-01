---
task_id: t-20260225-005
task_name: back-via-esc-in-tui
status: todo
date_created: '2026-02-25'
date_started: null
date_completed: null
priority: p3
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- agent
---

## Summary
- support going back in inquirerpy-based tui (e.g., `dot-tasks create`, `dot-tasks update`, etc.). Perhaps via esc key.

## Acceptance Criteria
- TODO

## Implementation Notes (2026-02-26)
- InquirerPy does not provide native multi-step "back" navigation for forms.
- Attempted approach: bind `Esc` to InquirerPy `skip` action, map skipped prompt to a custom back signal, and manually manage per-form step state in `dot-tasks`.
- Result: functionally works, but UX feels slow/clunky because `Esc` handling in terminal input requires timeout-based sequence disambiguation (plain `Esc` vs control-sequence prefixes), so back navigation is not snappy.
- Decision: revert this implementation and revisit with a different interaction design.
