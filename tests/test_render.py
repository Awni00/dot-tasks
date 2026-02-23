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


def test_render_task_detail_plain_header_first_layout() -> None:
    task = Task(
        metadata=TaskMetadata(
            task_id="t-20260206-001",
            task_name="build-nightly-report",
            status="todo",
            date_created="2026-02-06",
            priority="p0",
            effort="l",
            owner="alex",
            tags=["reporting", "automation"],
        ),
        body="\n\n## Summary\n- demo\n",
        task_dir=Path("/tmp") / "build-nightly-report",
    )
    deps = [("add-json-export", "t-20260205-001", "todo")]
    blocked_by = [("downstream-task", "t-20260207-001", "doing")]

    output = render.render_task_detail_plain(task, deps, blocked_by, 1)
    lines = output.splitlines()

    assert lines[0] == "build-nightly-report (t-20260206-001)"
    assert lines[1] == "[todo] [p0] [l] [deps: blocked(1)]"
    assert lines[2] == "owner: alex    tags: reporting, automation"
    assert lines[3] == "created: 2026-02-06    started: -    completed: -"
    assert lines[4] == "depends_on: add-json-export (t-20260205-001) [todo]"
    assert lines[5] == "blocked_by: downstream-task (t-20260207-001) [doing]"
    assert "## Summary" in output


def test_render_task_detail_plain_uses_dash_for_empty_fields() -> None:
    task = Task(
        metadata=TaskMetadata(
            task_id="t-20260206-001",
            task_name="build-nightly-report",
            status="todo",
            date_created="2026-02-06",
            priority="p2",
            effort="m",
        ),
        body="",
        task_dir=Path("/tmp") / "build-nightly-report",
    )

    output = render.render_task_detail_plain(task, [], [], 0)
    assert "[todo] [p2] [m] [deps: ready]" in output
    assert "owner: -    tags: -" in output
    assert "started: -    completed: -" in output
    assert "depends_on: -" in output
    assert "blocked_by: -" in output
    assert "(empty)" in output


def test_render_task_detail_rich_header_first_layout() -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    task = Task(
        metadata=TaskMetadata(
            task_id="t-20260206-001",
            task_name="build-nightly-report",
            status="todo",
            date_created="2026-02-06",
            priority="p0",
            effort="l",
            owner="alex",
            tags=["reporting", "automation"],
        ),
        body="\n\n## Summary\n- demo\n",
        task_dir=Path("/tmp") / "build-nightly-report",
    )
    deps = [("add-json-export", "t-20260205-001", "todo")]
    blocked_by = [("downstream-task", "t-20260207-001", "doing")]

    renderable = render.render_task_detail_rich(task, deps, blocked_by, 1)
    console = Console(record=True, width=200, force_terminal=False, color_system=None)
    console.print(renderable)
    text = console.export_text()

    assert "build-nightly-report (t-20260206-001)" in text
    assert "[todo] [p0] [l] [deps: blocked(1)]" in text
    assert "owner: alex    tags: reporting, automation" in text
    assert "depends_on: add-json-export (t-20260205-001) [todo]" in text
    assert "blocked_by: downstream-task (t-20260207-001) [doing]" in text
    assert "## Summary" in text
