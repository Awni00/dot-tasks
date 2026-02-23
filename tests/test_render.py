from __future__ import annotations

from pathlib import Path

import pytest

from dot_tasks import render
from dot_tasks.models import Task, TaskMetadata


def _task(name: str, status: str, priority: str, task_id: str, created: str) -> Task:
    return Task(
        metadata=TaskMetadata(
            task_id=task_id,
            task_name=name,
            status=status,
            date_created=created,
            priority=priority,
            effort="m",
        ),
        body="",
        task_dir=Path("/tmp") / name,
    )


def _columns(*items: tuple[str, int]) -> list[dict[str, int | str]]:
    return [{"name": name, "width": width} for name, width in items]


def test_render_task_list_plain_shape_stable() -> None:
    tasks = [
        _task("alpha", "todo", "p2", "t-20260222-001", "2026-02-22"),
        _task("beta", "doing", "p1", "t-20260222-002", "2026-02-22"),
    ]
    unmet = {"t-20260222-001": 0, "t-20260222-002": 1}
    columns = _columns(
        ("task_name", 16),
        ("priority", 8),
        ("effort", 6),
        ("deps", 12),
        ("created", 10),
    )

    output = render.render_task_list_plain(tasks, unmet, columns)
    lines = output.splitlines()
    assert lines[0].startswith("task_name")
    assert "task_id" not in lines[0]
    assert "deps" in lines[0]
    assert "ready" in output
    assert "blocked(1)" in output


def test_render_task_list_plain_applies_truncation() -> None:
    tasks = [_task("very-long-task-name", "todo", "p2", "t-20260222-001", "2026-02-22")]
    unmet = {"t-20260222-001": 0}
    columns = _columns(("task_name", 8), ("created", 10))

    output = render.render_task_list_plain(tasks, unmet, columns)
    assert "very-lo…" in output
    assert "2026-02-22" in output


def test_render_task_list_rich_sections_and_labels() -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    tasks = [
        _task("todo-task", "todo", "p0", "t-20260222-001", "2026-02-22"),
        _task("doing-task", "doing", "p1", "t-20260222-002", "2026-02-22"),
        _task("done-task", "completed", "p3", "t-20260222-003", "2026-02-22"),
    ]
    unmet = {
        "t-20260222-001": 1,
        "t-20260222-002": 0,
        "t-20260222-003": 0,
    }
    columns = _columns(
        ("task_name", 20),
        ("priority", 8),
        ("effort", 6),
        ("deps", 12),
        ("created", 10),
    )

    renderable = render.render_task_list_rich(tasks, unmet, columns)
    console = Console(record=True, width=140, force_terminal=False, color_system=None)
    console.print(renderable)
    text = console.export_text()

    assert "TODO (1)" in text
    assert "DOING (1)" in text
    assert "DONE (1)" in text
    assert "⚠ blocked(1)" in text
    assert "✓ ready" in text
    assert "p0" in text
    assert "p1" in text
    assert "p3" in text
