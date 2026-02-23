from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from typer.testing import CliRunner
import yaml

from dot_tasks.cli import app


runner = CliRunner()


def _read_task_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    front = yaml.safe_load(text[4:end])
    body = text[end + 5 :]
    return front, body


def _task_dir(tasks_root: Path, bucket: str, task_name: str) -> Path:
    today = dt.date.today().isoformat()
    return tasks_root / bucket / f"{today}-{task_name}"


def _read_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_init_idempotent(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    r1 = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert r1.exit_code == 0
    r2 = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert r2.exit_code == 0
    assert (root / "todo").is_dir()
    assert (root / "doing").is_dir()
    assert (root / "done").is_dir()
    assert (root / "trash").is_dir()
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is True


def test_init_nointeractive_creates_default_config(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    result = runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    assert result.exit_code == 0
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is True


def test_init_does_not_overwrite_existing_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli._prompt_init_interactive_enabled", lambda: False)
    runner.invoke(app, ["init", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._prompt_init_interactive_enabled", lambda: True)
    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is False


def test_create_rejects_duplicate_name(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    r1 = runner.invoke(app, ["create", "a-task", "--tasks-root", str(root)])
    r2 = runner.invoke(app, ["create", "a-task", "--tasks-root", str(root)])
    assert r1.exit_code == 0
    assert r2.exit_code == 1
    assert "already exists" in r2.output


def test_create_writes_task_and_activity(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    result = runner.invoke(
        app,
        [
            "create",
            "write-files",
            "--summary",
            "hello",
            "--priority",
            "p1",
            "--effort",
            "l",
            "--tasks-root",
            str(root),
        ],
    )
    assert result.exit_code == 0
    task_dir = _task_dir(root, "todo", "write-files")
    assert (task_dir / "task.md").exists()
    assert (task_dir / "activity.md").exists()
    meta, _ = _read_task_md(task_dir / "task.md")
    assert meta["task_name"] == "write-files"
    assert meta["priority"] == "p1"
    assert meta["effort"] == "l"


def test_start_blocks_unmet_dependencies_without_force(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep", "--tasks-root", str(root)])
    result = runner.invoke(
        app,
        ["create", "main", "--depends-on", "dep", "--tasks-root", str(root)],
    )
    assert result.exit_code == 0
    blocked = runner.invoke(app, ["start", "main", "--tasks-root", str(root)])
    assert blocked.exit_code == 1
    assert "Unmet dependencies" in blocked.output


def test_start_creates_plan_md(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plan-task", "--tasks-root", str(root)])
    result = runner.invoke(app, ["start", "plan-task", "--tasks-root", str(root)])
    assert result.exit_code == 0
    doing_dir = _task_dir(root, "doing", "plan-task")
    assert (doing_dir / "plan.md").exists()


def test_complete_moves_and_sets_date(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "done-task", "--tasks-root", str(root)])
    result = runner.invoke(app, ["complete", "done-task", "--tasks-root", str(root)])
    assert result.exit_code == 0
    done_dir = _task_dir(root, "done", "done-task")
    meta, _ = _read_task_md(done_dir / "task.md")
    assert meta["status"] == "completed"
    assert meta["date_completed"] == dt.date.today().isoformat()


def test_rename_preserves_dependencies_by_task_id(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "base", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "child", "--depends-on", "base", "--tasks-root", str(root)])

    base_meta, _ = _read_task_md(_task_dir(root, "todo", "base") / "task.md")
    base_id = base_meta["task_id"]

    result = runner.invoke(app, ["rename", "base", "base-renamed", "--tasks-root", str(root)])
    assert result.exit_code == 0

    child_meta, _ = _read_task_md(_task_dir(root, "todo", "child") / "task.md")
    assert child_meta["depends_on"] == [base_id]


def test_view_renders_dependencies_as_name_and_id(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-view", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "task-view", "--depends-on", "dep-view", "--tasks-root", str(root)])
    dep_meta, _ = _read_task_md(_task_dir(root, "todo", "dep-view") / "task.md")
    dep_id = dep_meta["task_id"]

    result = runner.invoke(app, ["view", "task-view", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert f"dep-view ({dep_id})" in result.output


def test_list_grouped_sorted(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "a", "--priority", "p2", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "b", "--priority", "p0", "--tasks-root", str(root)])
    runner.invoke(app, ["start", "a", "--tasks-root", str(root)])
    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    table_lines = [line for line in lines if "task_name" not in line and not line.startswith("-")]
    joined = "\n".join(table_lines)
    assert "todo" in joined
    assert "doing" in joined


def test_subdirectory_discovers_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    root = repo / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "root-task", "--tasks-root", str(root)])

    with runner.isolated_filesystem(temp_dir=str(nested)):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Using tasks root:" in result.output


def test_delete_soft_and_hard(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "to-trash", "--tasks-root", str(root)])
    soft = runner.invoke(app, ["delete", "to-trash", "--tasks-root", str(root)])
    assert soft.exit_code == 0
    assert any((root / "trash").iterdir())

    runner.invoke(app, ["create", "to-hard", "--tasks-root", str(root)])
    hard = runner.invoke(app, ["delete", "to-hard", "--tasks-root", str(root), "--hard"])
    assert hard.exit_code == 0
    assert not (_task_dir(root, "todo", "to-hard")).exists()


def test_missing_selector_triggers_prompt_picker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "pick-me", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli.choose_task", lambda tasks, title: "pick-me")

    result = runner.invoke(app, ["start", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "Started: pick-me" in result.output


def test_no_args_interactive_runs_selected_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli._prompt_init_interactive_enabled", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.choose_command",
        lambda commands, title: "init",
    )

    with runner.isolated_filesystem(temp_dir=str(tmp_path)):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Initialized tasks root:" in result.output
        assert (Path(".tasks") / "todo").is_dir()
        cfg = _read_config(Path(".tasks") / "config.yaml")
        assert cfg["settings"]["interactive_enabled"] is True


def test_no_args_interactive_cancel_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli.choose_command", lambda commands, title: None)

    result = runner.invoke(app, [])
    assert result.exit_code == 1


def test_no_args_non_interactive_prints_help_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: False)

    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "interactive terminal" in result.output


def test_root_nointeractive_prints_help_and_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    result = runner.invoke(app, ["--tasks-root", str(root), "--nointeractive"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_missing_required_arg_with_nointeractive_errors(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "task_name is required in non-interactive mode" in result.output


def test_unsupported_config_key_warns_and_ignores(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        "settings:\n  interactive_mode: prompt\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "Warning: Unsupported settings key 'interactive_mode'" in result.output


def test_invalid_interactive_enabled_warns_and_falls_back(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        "settings:\n  interactive_enabled: maybe\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "Warning: Invalid settings.interactive_enabled" in result.output


def test_update_interactive_form_replaces_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-a", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-b", "--tasks-root", str(root)])
    runner.invoke(
        app,
        ["create", "main-task", "--depends-on", "dep-a", "--tasks-root", str(root)],
    )

    dep_b_meta, _ = _read_task_md(_task_dir(root, "todo", "dep-b") / "task.md")
    dep_b_id = dep_b_meta["task_id"]

    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.update_form",
        lambda task, dependency_options: {
            "priority": None,
            "effort": None,
            "owner": task.metadata.owner or "",
            "tags": [],
            "depends_on": [dep_b_id],
            "replace_depends_on": True,
            "note": "Replaced deps",
        },
    )

    result = runner.invoke(app, ["update", "main-task", "--tasks-root", str(root)])
    assert result.exit_code == 0
    meta, _ = _read_task_md(_task_dir(root, "todo", "main-task") / "task.md")
    assert meta["depends_on"] == [dep_b_id]
