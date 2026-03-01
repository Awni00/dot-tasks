# Walkthrough: Configurable task.md Body Sections

## Changes Made

### storage.py
- Added `DEFAULT_TASK_BODY_SECTIONS` constant (Summary + Acceptance Criteria)
- Added `resolve_task_body_sections()` config resolver with validation and graceful fallback
- Threaded `task_body_sections` through `build_managed_settings()`, `default_config()`, `merge_managed_config()`, `upsert_init_config()`
- Added `"task_body_sections"` to `supported_settings_keys` in all 4 resolver functions

### service.py
- Added `_render_task_body(sections, summary)` — builds task.md body from config sections; `Summary` section gets user text, others get defaults
- `create_task()` now calls `resolve_task_body_sections()` instead of hardcoding the body

### selector_ui.py + prompt_ui.py
- `select_text()` now accepts `multiline=True` → passes to `inquirer.text()`
- `_safe_prompt()` accepts and forwards `multiline` param
- Summary prompt in `create_form()` now uses `multiline=True` with hint text

## Config Format

```yaml
settings:
  task_body_sections:
    - name: Summary
      default: "- TODO"
    - name: Acceptance Criteria
      default: "- TODO"
```

## Testing

| Test file | New tests | Status |
|---|---|---|
| `test_storage.py` | 8 | ✅ |
| `test_cli.py` | 4 | ✅ |
| `test_prompt_ui.py` | 3 mock fixes | ✅ |

**205 tests passed** across all test files.
