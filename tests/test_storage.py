from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from dot_tasks import storage


def _legacy_fields():
    """Fields used by configs without settings.fields (all four built-ins)."""
    return [storage.BUILTIN_FIELDS[name] for name in storage.DEFAULT_FIELD_NAMES]


def _write_config(tasks_root: Path, content: str) -> None:
    tasks_root.mkdir(parents=True, exist_ok=True)
    (tasks_root / "config.yaml").write_text(content, encoding="utf-8")


def test_resolve_list_table_columns_uses_defaults_when_missing(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    warnings: list[str] = []
    columns = storage.resolve_list_table_columns(root, warn=warnings.append)
    assert columns == storage.default_list_table_columns(_legacy_fields())
    assert warnings == []


def test_resolve_list_table_columns_reads_valid_custom_columns(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    _write_config(
        root,
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: task_name\n"
            "        width: 24\n"
            "      - name: deps\n"
            "        width: 14\n"
        ),
    )

    warnings: list[str] = []
    columns = storage.resolve_list_table_columns(root, warn=warnings.append)
    assert columns == [{"name": "task_name", "width": 24}, {"name": "deps", "width": 14}]
    assert warnings == []


def test_done_list_columns_swap_deps_for_completed() -> None:
    # Purpose: for done tasks, `deps` is replaced by `completed` (dependency health is moot).
    columns = storage.apply_done_list_columns(storage.default_list_table_columns(_legacy_fields()))
    names = storage.list_column_names(columns)
    assert "completed" in names
    assert "deps" not in names
    completed_column = next(column for column in columns if column["name"] == "completed")
    assert completed_column["width"] == storage.FIXED_LIST_COLUMN_WIDTHS["completed"]


def test_done_list_columns_apply_to_custom_columns_too() -> None:
    # Purpose: the swap also applies to a project's own column set, and is a no-op when
    # `completed` is already shown.
    columns = [{"name": "task_name", "width": 20}, {"name": "deps", "width": 12}]
    assert storage.list_column_names(storage.apply_done_list_columns(columns)) == ["task_name", "completed"]
    with_completed = [{"name": "completed", "width": 12}, {"name": "deps", "width": 12}]
    assert storage.apply_done_list_columns(with_completed) == with_completed


def test_next_task_id_uses_date_prefix_and_suffix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Ensure next_task_id formats IDs as t-YYYYMMDD-XXXX using the configured alphabet.
    def _choice(alphabet: str) -> str:
        assert alphabet == storage.TASK_ID_ALPHABET
        return "K"

    monkeypatch.setattr("dot_tasks.storage.secrets.choice", _choice)
    task_id = storage.next_task_id(tmp_path, "2026-03-19")
    assert task_id == "t-20260319-KKKK"
    assert len(task_id) == 15


def test_resolve_list_table_columns_invalid_entries_warn_and_fallback(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    _write_config(
        root,
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: not_real\n"
            "        width: 10\n"
            "      - name: task_name\n"
            "        width: 0\n"
        ),
    )

    warnings: list[str] = []
    columns = storage.resolve_list_table_columns(root, warn=warnings.append)
    assert columns == storage.default_list_table_columns(_legacy_fields())
    assert any("List column 'not_real'" in message for message in warnings)
    assert any("Invalid width for list column 'task_name'" in message for message in warnings)
    assert any("No valid settings.list_table.columns" in message for message in warnings)


def test_resolve_list_table_columns_duplicate_keeps_first(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    _write_config(
        root,
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: task_name\n"
            "        width: 20\n"
            "      - name: priority\n"
            "        width: 8\n"
            "      - name: task_name\n"
            "        width: 10\n"
        ),
    )

    warnings: list[str] = []
    columns = storage.resolve_list_table_columns(root, warn=warnings.append)
    assert columns == [{"name": "task_name", "width": 20}, {"name": "priority", "width": 8}]
    assert any("Duplicate list column 'task_name'" in message for message in warnings)


def test_default_config_uses_provided_list_columns() -> None:
    payload = storage.default_config(
        interactive_enabled=False,
        show_banner=False,
        list_columns=[{"name": "task_name", "width": 20}, {"name": "status", "width": 10}],
    )
    assert payload["settings"]["interactive_enabled"] is False
    assert payload["settings"]["show_banner"] is False
    assert payload["settings"]["list_table"]["columns"] == [
        {"name": "task_name", "width": 20},
        {"name": "status", "width": 10},
    ]


def test_merge_managed_config_preserves_unknown_keys() -> None:
    existing = {
        "custom_root": "keep",
        "settings": {
            "custom_setting": "keep-setting",
            "interactive_enabled": True,
            "show_banner": True,
            "list_table": {"columns": [{"name": "task_name", "width": 32}]},
        },
    }
    merged = storage.merge_managed_config(
        existing,
        interactive_enabled=False,
        show_banner=False,
        list_columns=[{"name": "created", "width": 10}],
    )
    assert merged["custom_root"] == "keep"
    assert merged["settings"]["custom_setting"] == "keep-setting"
    assert merged["settings"]["interactive_enabled"] is False
    assert merged["settings"]["show_banner"] is False
    assert merged["settings"]["list_table"]["columns"] == [{"name": "created", "width": 10}]


def test_upsert_init_config_reports_created_and_updated_and_preserves_unknown(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    root.mkdir(parents=True, exist_ok=True)

    created = storage.upsert_init_config(
        root,
        interactive_enabled=True,
        show_banner=True,
        list_columns=[{"name": "task_name", "width": 32}],
    )
    assert created == "created"

    (root / "config.yaml").write_text(
        (
            "custom_root: keep\n"
            "settings:\n"
            "  custom_setting: keep-setting\n"
            "  interactive_enabled: true\n"
            "  show_banner: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: task_name\n"
            "        width: 32\n"
        ),
        encoding="utf-8",
    )
    updated = storage.upsert_init_config(
        root,
        interactive_enabled=False,
        show_banner=False,
        list_columns=[{"name": "created", "width": 10}],
    )
    assert updated == "updated"

    cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["custom_root"] == "keep"
    assert cfg["settings"]["custom_setting"] == "keep-setting"
    assert cfg["settings"]["interactive_enabled"] is False
    assert cfg["settings"]["show_banner"] is False
    assert cfg["settings"]["list_table"]["columns"] == [{"name": "created", "width": 10}]


def test_default_config_sets_show_banner_true() -> None:
    payload = storage.default_config()
    assert payload["settings"]["show_banner"] is True


def test_resolve_show_banner_defaults_true_when_missing(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    assert storage.resolve_show_banner(root) is True


def test_resolve_show_banner_reads_valid_bool(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    _write_config(
        root,
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  show_banner: false\n"
        ),
    )
    assert storage.resolve_show_banner(root) is False


def test_parse_task_keeps_unknown_keys_and_drops_blocked_by(tmp_path: Path) -> None:
    # Purpose: 0.1 task files load unchanged: old fields (including the deleted spec_readiness)
    # become plain frontmatter fields kept verbatim and in order, unquoted dates become ISO
    # strings, and the retired blocked_by key is dropped when the task is written back.
    task_dir = tmp_path / "todo" / "2026-02-24-legacy-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(
        (
            "---\n"
            "task_id: t-20260224-001\n"
            "task_name: legacy-task\n"
            "status: todo\n"
            "date_created: 2026-02-24\n"
            "date_started: null\n"
            "date_completed: null\n"
            "priority: p2\n"
            "effort: m\n"
            "spec_readiness: ready\n"
            "depends_on: []\n"
            "blocked_by: [t-20260225-002]\n"
            "owner: null\n"
            "tags: []\n"
            "kind: theory\n"
            "---\n\n"
            "## Summary\n"
            "- legacy\n"
        ),
        encoding="utf-8",
    )

    task = storage.parse_task(task_dir)
    storage.write_task(task)
    meta, _ = yaml.safe_load_all((task_dir / "task.md").read_text(encoding="utf-8")).__next__(), None

    assert task.metadata.date_created == "2026-02-24"
    assert task.metadata.summary == ""
    assert list(task.metadata.fields) == ["priority", "effort", "spec_readiness", "owner", "kind"]
    assert task.metadata.fields["spec_readiness"] == "ready"
    assert "blocked_by" not in meta
    assert meta["kind"] == "theory"
    assert "## Summary\n- legacy" in (task_dir / "task.md").read_text(encoding="utf-8")


def _field(raw, warnings=None):
    parsed = storage.parse_field_entries([raw], warnings.append if warnings is not None else None)
    return parsed[0] if parsed else None


def test_resolve_fields_defaults_to_all_builtins_without_fields_key(tmp_path: Path) -> None:
    # Purpose: configs without settings.fields keep every 0.1 field (priority, effort,
    # due_date, owner); an explicit empty list means no optional fields.
    root = tmp_path / ".tasks"
    _write_config(root, "settings:\n  show_banner: true\n")
    assert [f.name for f in storage.resolve_fields(root)] == list(storage.DEFAULT_FIELD_NAMES)

    _write_config(root, "settings:\n  fields: []\n")
    assert storage.resolve_fields(root) == []


def test_parse_field_entries_builtins_overrides_and_custom_fields() -> None:
    # Purpose: entries can name a built-in, override parts of a built-in, or define a new
    # typed field (choice/date/text) with an optional default.
    assert _field("priority") == storage.BUILTIN_FIELDS["priority"]
    effort = _field({"name": "effort", "values": ["hours", "days"], "default": "days"})
    assert (effort.type, effort.values, effort.default) == ("choice", ("hours", "days"), "days")
    kind = _field({"name": "kind", "type": "choice", "values": ["theory", "writing"]})
    assert (kind.type, kind.values, kind.default, kind.ranked) == ("choice", ("theory", "writing"), None, False)
    review = _field({"name": "review_date", "type": "date", "default": "2026-12-01"})
    assert (review.type, review.default) == ("date", "2026-12-01")
    assert _field({"name": "venue", "type": "text"}).type == "text"


def test_parse_field_entries_warns_and_skips_invalid_entries() -> None:
    # Purpose: malformed field definitions never break commands; each is reported and skipped
    # (or, for a bad default, kept without the default).
    cases = {
        "unknown_builtin": ("nope", "Unknown built-in field 'nope'"),
        "missing_type": ({"name": "kind"}, "needs a type"),
        "empty_values": ({"name": "kind", "type": "choice", "values": []}, "non-empty 'values'"),
        "reserved": ({"name": "status", "type": "text"}, "reserved"),
    }
    for raw, expected in cases.values():
        warnings: list[str] = []
        assert _field(raw, warnings) is None
        assert any(expected in message for message in warnings), (raw, warnings)

    warnings = []
    kind = _field({"name": "kind", "type": "choice", "values": ["a"], "default": "b"}, warnings)
    assert kind is not None and kind.default is None
    assert any("not one of its values" in message for message in warnings)

    warnings = []
    parsed = storage.parse_field_entries(["priority", "priority"], warnings.append)
    assert [f.name for f in parsed] == ["priority"]
    assert any("Duplicate field 'priority'" in message for message in warnings)


def test_merge_managed_config_keeps_fields_and_drops_retired_settings() -> None:
    # Purpose: re-running init keeps a project's settings.fields (custom fields included) unless
    # new entries are given, and removes settings retired in 0.2.0.
    custom = ["priority", {"name": "kind", "type": "choice", "values": ["a", "b"]}]
    merged = storage.merge_managed_config(
        {"settings": {"fields": custom, "due_dates": {"enabled": True}, "task_body_sections": []}},
    )
    assert merged["settings"]["fields"] == custom
    assert "due_dates" not in merged["settings"]
    assert "task_body_sections" not in merged["settings"]


def test_read_task_template_is_optional(tmp_path: Path) -> None:
    # Purpose: .tasks/templates/task.md is the only template the tool reads; without it the
    # body of a new task is empty.
    root = tmp_path / ".tasks"
    root.mkdir()
    assert storage.read_task_template(root) == ""
    (root / "templates").mkdir()
    (root / "templates" / "task.md").write_text("## Outcome\n", encoding="utf-8")
    assert storage.read_task_template(root) == "## Outcome\n"


def _leading_newline_count(text: str) -> int:
    return len(text) - len(text.lstrip("\n"))


def test_render_frontmatter_roundtrip_does_not_accumulate_leading_newlines() -> None:
    metadata = {
        "task_id": "t-20260226-001",
        "task_name": "roundtrip-stability",
        "status": "todo",
        "date_created": "2026-02-26",
        "date_started": None,
        "date_completed": None,
        "priority": "p2",
        "effort": "m",
        "spec_readiness": "unspecified",
        "depends_on": [],
        "blocked_by": [],
        "owner": None,
        "tags": [],
    }
    body = "## Summary\n- demo\n\n## Acceptance Criteria\n- TODO\n"
    counts: list[int] = []

    for _ in range(5):
        text = storage.render_frontmatter(metadata, body)
        _, body = storage.split_frontmatter(text)
        counts.append(_leading_newline_count(body))

    assert counts == [1, 1, 1, 1, 1]


def test_render_frontmatter_strips_extra_leading_blank_lines() -> None:
    metadata = {"task_id": "t-20260226-002"}
    body = "\n\n\n## Summary\n- demo\n\n## Acceptance Criteria\n- TODO\n\n"

    text = storage.render_frontmatter(metadata, body)
    _, parsed_body = storage.split_frontmatter(text)

    assert parsed_body.startswith("\n## Summary\n")
    assert not parsed_body.startswith("\n\n")


def test_resolve_show_banner_invalid_warns_and_falls_back(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    _write_config(
        root,
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  show_banner: maybe\n"
        ),
    )
    warnings: list[str] = []
    assert storage.resolve_show_banner(root, warn=warnings.append) is True
    assert any("Invalid settings.show_banner" in message for message in warnings)


