# Configurable task.md Body Sections + Multiline Summary Input

Make the hardcoded `## Summary` / `## Acceptance Criteria` body template user-configurable via `.tasks/config.yaml`, and enable multiline input for the summary field.

## Proposed Changes

### Config Layer

#### [MODIFY] storage.py

Add `task_body_sections` config under `settings`:

```yaml
settings:
  task_body_sections:
    - name: Summary
      default: "- TODO"
    - name: Acceptance Criteria
      default: "- TODO"
```

- Add `DEFAULT_TASK_BODY_SECTIONS` constant
- Add `resolve_task_body_sections(tasks_root)` resolver (same pattern as `resolve_list_table_columns`)
- Include in `build_managed_settings()` so `dot-tasks init` writes defaults
- Add to `supported_settings_keys` in all resolvers

---

### Service Layer

#### [MODIFY] service.py

- Add `_render_task_body(sections, summary)` helper — builds body string from sections config; the `Summary` section gets the user's text, others get their `default`
- `create_task()` calls `storage.resolve_task_body_sections()` and uses the helper instead of hardcoded body

---

### Multiline Input

#### [MODIFY] selector_ui.py

- Add `multiline` parameter to `select_text()` → passes `multiline=True` to `inquirer.text()`

#### [MODIFY] prompt_ui.py

- Add `multiline` parameter to `_safe_prompt()` → passes through to `select_text()`
- Summary prompts in `create_form()` use `_safe_prompt("summary", default="", multiline=True)`

---

### No CLI changes needed

`--summary` CLI flag and config-driven sections work without CLI modifications.

## Verification Plan

### Automated Tests
```bash
python -m pytest tests/ -x -q --tb=short
```

**New tests:**
1. `test_resolve_task_body_sections_defaults` — falls back when config has no sections
2. `test_resolve_task_body_sections_custom` — reads custom sections
3. `test_resolve_task_body_sections_invalid_falls_back` — bad config → defaults
4. `test_create_uses_custom_sections_from_config` — custom sections appear in task.md body
5. `test_create_summary_populates_summary_section` — summary content goes to Summary section
6. `test_init_writes_task_body_sections_to_config` — init config includes sections
7. `test_select_text_multiline_parameter` — multiline flag passes through
