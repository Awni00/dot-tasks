---
task_id: t-20260710-VJ87
task_name: fix-multiline-prompt-wrap-whitespace
status: completed
date_created: '2026-07-10'
date_started: '2026-07-10'
date_completed: '2026-07-10'
priority: p1
effort: m
spec_readiness: ready
depends_on: []
blocked_by: []
owner: null
tags:
- bug
- tui
---

## Summary
- Fix interactive multiline prompt rendering that clears the terminal or emits terminal-height whitespace when the compact answered line reaches the terminal width.

## Acceptance Criteria
- Interactive multiline section submission does not clear the terminal or emit terminal-height whitespace when the compact answered line equals or exceeds terminal width.
- The fix covers narrow terminals, exact-width boundaries, long single-line answers, multiline answers, and the default configured task body sections.
- Ordinary wide-terminal interactive behavior, Esc+Enter submission, non-interactive creation, cancellation, and CPR suppression remain functional.
- A deterministic real-PTY regression test fails on the original implementation and passes with the fix.
- The implementation is minimal, readable, and introduces no unnecessary abstraction or dependency.
