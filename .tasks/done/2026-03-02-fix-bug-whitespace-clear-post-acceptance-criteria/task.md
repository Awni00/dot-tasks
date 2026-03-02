---
task_id: t-20260302-002
task_name: fix-bug-whitespace-clear-post-acceptance-criteria
status: completed
date_created: '2026-03-02'
date_started: '2026-03-02'
date_completed: '2026-03-02'
priority: p2
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- bug
---

## Summary
- Currently, there seems to sometimes be a bug after filling the task.md text sections where some portions of the TUI are cleared and a lot of whitespace newlines are introduced. Figure out how to reproduce, cause, and fix.
- See `artifacts/example.txt` for an example of what was observed in a VSCode terminal instance.

## Acceptance Criteria
- Reproduce the interactive whitespace/clear bug deterministically in a VSCode-like terminal path.
- Identify and document root cause in prompt_toolkit CPR probing/redraw behavior during InquirerPy prompt rendering.
- Keep InquirerPy active for both single-line and multiline text prompts.
- Implement a fix that avoids multiline whitespace/clear artifacts without removing InquirerPy.
- Add/adjust tests covering selector prompt behavior and CPR suppression behavior.
- Verify with focused automated tests and interactive smoke checks.
