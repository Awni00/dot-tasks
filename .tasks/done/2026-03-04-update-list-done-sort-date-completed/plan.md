## Plan
- Expand list table schema to support a `completed` column and separate default column sets for active vs done output.
- Update list sorting so completed tasks are ordered by `date_completed` descending, with a fallback to `date_created` when `date_completed` is missing.
- Make list rendering status-aware: todo/doing keep `deps`, done shows `completed` by default and no `deps` column.
- Wire the new defaults through config/init and interactive column selection.
- Update tests that assert default columns and list ordering; add new tests for done sorting and `completed` column rendering.

### Tests
- Update storage default-column tests to reflect active vs done defaults.
- Add CLI list tests for `list done` and `list all` sorting by `date_completed`.
- Add render tests covering the new `completed` column and confirm `deps` stays on active lists.
