# Pseudorandom Task IDs (Option A, 4-char suffix)

## Summary
- Switch task ID generation to `t-YYYYMMDD-XXXX` with a 4-char pseudorandom suffix (human-safe base32 alphabet).
- Keep existing task IDs unchanged; only new tasks use the new format.
- Widen the default `task_id` column width so list output can show the full ID.

## Key Changes
- Update `storage.next_task_id` to build `prefix = f"t-{YYYYMMDD}-"` and append `suffix = "".join(secrets.choice(ALPHABET) for _ in range(4))`. No scan/retry loop; collisions fall through to existing duplicate-ID validation and surface as an error.
- Update `LIST_TABLE_COLUMN_DEFAULT_WIDTHS["task_id"]` from 14 to 15 so the full 15-char ID fits without truncation.
- Add a small unit test in `tests/test_storage.py` that monkeypatches `secrets.choice` to a deterministic value and asserts the ID format and length. Include a brief comment at the top of the test explaining purpose.

## Public Interface / Behavior Changes
- New task IDs will look like `t-20260319-K7M3` (date prefix + 4-char random).
- Task creation can fail on rare collisions with existing IDs (current validation already raises a duplicate error). No auto-retry.

## Test Plan
- `pytest tests/test_storage.py`
- If any list config UI relies on the default width, add `pytest tests/test_prompt_ui.py` or `pytest tests/test_cli.py` as needed after code review.

## Assumptions
- Use Crockford-style base32 without ambiguous characters: `23456789ABCDEFGHJKMNPQRSTUVWXYZ`.
- Accept rare collisions and surface them as a standard duplicate task_id error (no regeneration loop).
- No worktree; changes are made in the current working copy.
