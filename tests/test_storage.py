from __future__ import annotations

from pathlib import Path

import yaml

from dot_tasks import storage


def _write_config(tasks_root: Path, content: str) -> None:
    tasks_root.mkdir(parents=True, exist_ok=True)
    (tasks_root / "config.yaml").write_text(content, encoding="utf-8")


def test_resolve_list_table_columns_uses_defaults_when_missing(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    warnings: list[str] = []
    columns = storage.resolve_list_table_columns(root, warn=warnings.append)
    assert columns == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
        {"name": "deps", "width": 12},
        {"name": "created", "width": 10},
    ]
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
    assert columns == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
        {"name": "deps", "width": 12},
        {"name": "created", "width": 10},
    ]
    assert any("Unsupported list column 'not_real'" in message for message in warnings)
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


def test_write_default_config_if_missing_writes_provided_list_columns(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    root.mkdir(parents=True, exist_ok=True)

    created = storage.write_default_config_if_missing(
        root,
        interactive_enabled=False,
        show_banner=False,
        list_columns=[{"name": "task_name", "width": 20}, {"name": "status", "width": 10}],
    )
    assert created is True

    cfg = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["settings"]["interactive_enabled"] is False
    assert cfg["settings"]["show_banner"] is False
    assert cfg["settings"]["list_table"]["columns"] == [
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


def test_parse_task_backfills_missing_spec_readiness(tmp_path: Path) -> None:
    task_dir = tmp_path / "todo" / "2026-02-24-legacy-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(
        (
            "---\n"
            "task_id: t-20260224-001\n"
            "task_name: legacy-task\n"
            "status: todo\n"
            "date_created: '2026-02-24'\n"
            "date_started: null\n"
            "date_completed: null\n"
            "priority: p2\n"
            "effort: m\n"
            "depends_on: []\n"
            "blocked_by: []\n"
            "owner: null\n"
            "tags: []\n"
            "---\n\n"
            "## Summary\n"
            "- legacy\n"
        ),
        encoding="utf-8",
    )

    task = storage.parse_task(task_dir)
    assert task.metadata.spec_readiness == "unspecified"


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
