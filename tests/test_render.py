from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from dot_tasks import render, storage
from dot_tasks.models import DependencyGraph, DependencyGraphNode, Task, TaskMetadata

OSC8_LINK_RE = re.compile(r"\x1b\]8;;[^\x1b]*\x1b\\(.*?)\x1b\]8;;\x1b\\")


def _strip_osc8(text: str) -> str:
    return OSC8_LINK_RE.sub(r"\1", text)


def _task(
    name: str,
    status: str,
    priority: str,
    task_id: str,
    created: str,
    completed: str | None = None,
) -> Task:
    return Task(
        metadata=TaskMetadata(
            task_id=task_id,
            task_name=name,
            status=status,
            date_created=created,
            date_completed=completed,
            priority=priority,
            effort="m",
        ),
        body="",
        task_dir=Path("/tmp") / name,
    )


def _columns(*items: tuple[str, int]) -> list[dict[str, int | str]]:
    return [{"name": name, "width": width} for name, width in items]


def _graph(
    nodes: list[DependencyGraphNode],
    *,
    root_ids: list[str],
    source_ids: list[str],
    include_done: bool = False,
) -> DependencyGraph:
    graph_nodes = {node.task_id: node for node in nodes}
    dependent_ids_by_node = {node.task_id: [] for node in nodes}
    for node in nodes:
        for dep_id in node.depends_on:
            dependent_ids_by_node[dep_id].append(node.task_id)
    return DependencyGraph(
        nodes=graph_nodes,
        root_ids=root_ids,
        source_ids=source_ids,
        dependent_ids_by_node=dependent_ids_by_node,
        include_done=include_done,
    )


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


def test_render_task_list_plain_supports_spec_readiness_column() -> None:
    tasks = [_task("alpha", "todo", "p2", "t-20260222-001", "2026-02-22")]
    unmet = {"t-20260222-001": 0}
    columns = _columns(("task_name", 16), ("spec_readiness", 14))

    output = render.render_task_list_plain(tasks, unmet, columns)
    assert "spec_readiness" in output
    assert "unspecified" in output


def test_render_task_list_plain_supports_completed_column() -> None:
    # Purpose: ensure list rendering can show completed dates when requested.
    tasks = [
        _task(
            "done-task",
            "completed",
            "p2",
            "t-20260222-003",
            "2026-02-22",
            completed="2026-02-23",
        )
    ]
    unmet = {"t-20260222-003": 0}
    columns = _columns(("task_name", 16), ("completed", 10))

    output = render.render_task_list_plain(tasks, unmet, columns)
    assert "completed" in output.splitlines()[0]
    assert "2026-02-23" in output


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


def test_render_task_list_rich_done_defaults_swap_deps_for_completed() -> None:
    # Purpose: ensure done-only lists swap deps for completed date by default.
    pytest.importorskip("rich")
    from rich.console import Console

    tasks = [
        _task(
            "done-task",
            "completed",
            "p3",
            "t-20260222-003",
            "2026-02-22",
            completed="2026-02-23",
        )
    ]
    unmet = {"t-20260222-003": 0}
    columns = storage.default_list_table_columns()

    renderable = render.render_task_list_rich(tasks, unmet, columns)
    console = Console(width=120, record=True)
    console.print(renderable)
    text = console.export_text()
    assert "completed" in text
    assert "deps" not in text


def test_render_dependency_graph_tree_marks_shared_nodes() -> None:
    # Purpose: ensure tree mode marks repeated dependency nodes as shared across roots.
    graph = _graph(
        [
            DependencyGraphNode(
                task_id="t-1",
                task_name="release-cli",
                status="doing",
                priority="p1",
                effort="l",
                depends_on=["t-2", "t-3"],
            ),
            DependencyGraphNode(
                task_id="t-2",
                task_name="package-wheel",
                status="todo",
                priority="p2",
                effort="m",
                depends_on=["t-4"],
            ),
            DependencyGraphNode(
                task_id="t-3",
                task_name="finalize-readme",
                status="todo",
                priority="p2",
                effort="s",
            ),
            DependencyGraphNode(
                task_id="t-4",
                task_name="generate-changelog",
                status="doing",
                priority="p2",
                effort="m",
            ),
            DependencyGraphNode(
                task_id="t-5",
                task_name="publish-blog",
                status="todo",
                priority="p2",
                effort="m",
                depends_on=["t-2"],
            ),
        ],
        root_ids=["t-1", "t-5"],
        source_ids=["t-3", "t-4"],
    )

    output = render.render_dependency_graph_tree_plain(graph)
    assert "Dependency Graph | mode=tree | scope=todo,doing" in output
    assert "nodes=5 edges=4 roots=2" in output
    assert "• package-wheel (t-2) [todo] [deps: blocked(1)] (shared)" in output
    assert "├─ • package-wheel (t-2) [todo] [deps: blocked(1)]" in output


def test_render_dependency_graph_tree_shows_hidden_dependency_count() -> None:
    # Purpose: ensure filtered dependencies are reported with (+N hidden) in tree nodes.
    graph = _graph(
        [
            DependencyGraphNode(
                task_id="t-1",
                task_name="release-cli",
                status="doing",
                priority="p1",
                effort="l",
                depends_on=["t-2"],
                hidden_depends_on=["t-9"],
            ),
            DependencyGraphNode(
                task_id="t-2",
                task_name="package-wheel",
                status="todo",
                priority="p2",
                effort="m",
            ),
        ],
        root_ids=["t-1"],
        source_ids=["t-2"],
    )

    output = render.render_dependency_graph_tree_plain(graph)
    assert "• release-cli (t-1) [doing] [deps: blocked(1)] (+1 hidden)" in output


def test_render_dependency_graph_layers_layout_and_order() -> None:
    # Purpose: ensure layers mode groups nodes by prerequisite depth with stable ordering.
    graph = _graph(
        [
            DependencyGraphNode(
                task_id="t-4",
                task_name="generate-changelog",
                status="doing",
                priority="p2",
                effort="m",
            ),
            DependencyGraphNode(
                task_id="t-3",
                task_name="finalize-readme",
                status="todo",
                priority="p2",
                effort="s",
            ),
            DependencyGraphNode(
                task_id="t-2",
                task_name="package-wheel",
                status="todo",
                priority="p2",
                effort="m",
                depends_on=["t-4"],
            ),
            DependencyGraphNode(
                task_id="t-5",
                task_name="publish-blog",
                status="todo",
                priority="p2",
                effort="m",
                depends_on=["t-2"],
            ),
            DependencyGraphNode(
                task_id="t-1",
                task_name="release-cli",
                status="doing",
                priority="p1",
                effort="l",
                depends_on=["t-2", "t-3"],
            ),
        ],
        root_ids=["t-5", "t-1"],
        source_ids=["t-4", "t-3"],
    )

    output = render.render_dependency_graph_layers_plain(graph)
    assert "Dependency Graph | mode=layers | scope=todo,doing" in output
    assert "nodes=5 edges=4 layers=3" in output
    assert "L0 (no dependencies)" in output
    assert "• generate-changelog (t-4) [doing] [deps: ready]" in output
    assert "• finalize-readme (t-3) [todo] [deps: ready]" in output
    assert "L1 depends on L0" in output
    assert "• package-wheel (t-2) [todo] [deps: blocked(1)]" in output
    assert "L2 depends on L1" in output


def test_render_dependency_graph_tree_rich_contains_expected_tokens() -> None:
    # Purpose: ensure rich tree output preserves the intended node text markers and connectors.
    pytest.importorskip("rich")
    from rich.console import Console

    graph = _graph(
        [
            DependencyGraphNode(
                task_id="t-1",
                task_name="release-cli",
                status="doing",
                priority="p1",
                effort="l",
                depends_on=["t-2"],
                hidden_depends_on=["t-9"],
            ),
            DependencyGraphNode(
                task_id="t-2",
                task_name="package-wheel",
                status="todo",
                priority="p2",
                effort="m",
            ),
            DependencyGraphNode(
                task_id="t-3",
                task_name="publish-blog",
                status="todo",
                priority="p2",
                effort="m",
                depends_on=["t-2"],
            ),
        ],
        root_ids=["t-1", "t-3"],
        source_ids=["t-2"],
    )

    renderable = render.render_dependency_graph_tree_rich(graph)
    console = Console(record=True, width=180, force_terminal=False, color_system=None)
    console.print(renderable)
    text = console.export_text()

    assert "Dependency Graph | mode=tree | scope=todo,doing" in text
    assert "• release-cli (t-1) [doing] [deps: blocked(1)] (+1 hidden)" in text
    assert "└─ • package-wheel (t-2) [todo] [deps: ready] (shared)" in text


def test_render_dependency_graph_layers_rich_contains_updated_l0_heading() -> None:
    # Purpose: ensure rich layers output uses the updated L0 heading and bullet node rows.
    pytest.importorskip("rich")
    from rich.console import Console

    graph = _graph(
        [
            DependencyGraphNode(
                task_id="t-1",
                task_name="base",
                status="todo",
                priority="p2",
                effort="m",
            ),
            DependencyGraphNode(
                task_id="t-2",
                task_name="top",
                status="doing",
                priority="p1",
                effort="m",
                depends_on=["t-1"],
            ),
        ],
        root_ids=["t-2"],
        source_ids=["t-1"],
    )

    renderable = render.render_dependency_graph_layers_rich(graph)
    console = Console(record=True, width=180, force_terminal=False, color_system=None)
    console.print(renderable)
    text = console.export_text()

    assert "Dependency Graph | mode=layers | scope=todo,doing" in text
    assert "L0 (no dependencies)" in text
    assert "• base (t-1) [todo] [deps: ready]" in text
    assert "L1 depends on L0" in text


def test_render_task_detail_plain_header_first_layout(tmp_path: Path) -> None:
    task_dir = tmp_path / "build-nightly-report"
    task_dir.mkdir()
    (task_dir / "task.md").write_text("task", encoding="utf-8")
    (task_dir / "activity.md").write_text("activity", encoding="utf-8")
    (task_dir / "plan.md").write_text("plan", encoding="utf-8")
    (task_dir / "notes.txt").write_text("extra", encoding="utf-8")

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
        task_dir=task_dir,
    )
    deps = [("add-json-export", "t-20260205-001", "todo")]
    blocked_by = [("downstream-task", "t-20260207-001", "doing")]

    output = _strip_osc8(render.render_task_detail_plain(task, deps, blocked_by, 1))
    lines = output.splitlines()

    assert lines[0] == "build-nightly-report (t-20260206-001)"
    assert lines[1] == "[todo] [p0] [l] [deps: blocked(1)]"
    assert lines[2] == "owner: alex    tags: reporting, automation"
    assert lines[3] == "created: 2026-02-06    started: -    completed: -"
    assert lines[4] == "depends_on: add-json-export (t-20260205-001) [todo]"
    assert lines[5] == "blocked_by: downstream-task (t-20260207-001) [doing]"
    assert lines[6] == f"dir: {task_dir.name}"
    assert lines[7] == "files: task.md | activity.md | plan.md"
    assert lines[8] == "extra: notes.txt"
    assert "## Summary" in output


def test_render_task_detail_plain_uses_dash_for_empty_fields(tmp_path: Path) -> None:
    task_dir = tmp_path / "build-nightly-report"
    task_dir.mkdir()
    (task_dir / "task.md").write_text("task", encoding="utf-8")
    (task_dir / "activity.md").write_text("activity", encoding="utf-8")

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
        task_dir=task_dir,
    )

    raw_output = render.render_task_detail_plain(task, [], [], 0)
    output = _strip_osc8(raw_output)
    assert "[todo] [p2] [m] [deps: ready]" in output
    assert "owner: -    tags: -" in output
    assert "started: -    completed: -" in output
    assert "depends_on: -" in output
    assert "blocked_by: -" in output
    assert f"dir: {task_dir.name}" in output
    assert "files: task.md | activity.md | plan.md (missing)" in output
    assert "extra:" not in output
    assert "(empty)" in output
    linked_labels = OSC8_LINK_RE.findall(raw_output)
    assert "task.md" in linked_labels
    assert "activity.md" in linked_labels
    assert "plan.md" not in linked_labels


def test_render_task_detail_plain_extra_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    task_dir = tmp_path / "build-nightly-report"
    task_dir.mkdir()
    (task_dir / "task.md").write_text("task", encoding="utf-8")
    (task_dir / "activity.md").write_text("activity", encoding="utf-8")
    (task_dir / "plan.md").write_text("plan", encoding="utf-8")

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
        task_dir=task_dir,
    )

    original_iterdir = Path.iterdir

    def _broken_iterdir(self: Path):
        if self.resolve() == task_dir.resolve():
            raise OSError("unreadable")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _broken_iterdir)
    output = render.render_task_detail_plain(task, [], [], 0, enable_links=False)

    assert "files: task.md | activity.md | plan.md" in output
    assert "extra: (unavailable)" in output


def test_render_task_detail_rich_header_first_layout(tmp_path: Path) -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    task_dir = tmp_path / "build-nightly-report"
    task_dir.mkdir()
    (task_dir / "task.md").write_text("task", encoding="utf-8")
    (task_dir / "activity.md").write_text("activity", encoding="utf-8")
    (task_dir / "plan.md").write_text("plan", encoding="utf-8")

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
        task_dir=task_dir,
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
    assert f"dir: {task_dir.name}" in text
    assert "files: task.md | activity.md | plan.md" in text
    assert "extra:" not in text
    assert "## Summary" in text


def test_render_create_success_plain_with_links(tmp_path: Path) -> None:
    task_dir = tmp_path / "create-task"
    task_dir.mkdir()
    task = Task(
        metadata=TaskMetadata(
            task_id="t-20260225-001",
            task_name="create-task",
            status="todo",
            date_created="2026-02-25",
            priority="p2",
            effort="m",
        ),
        body="",
        task_dir=task_dir,
    )

    raw_output = render.render_create_success_plain(task, enable_links=True)
    output = _strip_osc8(raw_output)

    assert "\x1b]8;;" in raw_output
    assert "Created: create-task (t-20260225-001)" in output
    assert "links: dir | task.md" in output
    assert str(task_dir.resolve()) not in output
    assert str(task.task_md_path.resolve()) not in output


def test_render_create_success_plain_without_links(tmp_path: Path) -> None:
    task_dir = tmp_path / "create-task"
    task_dir.mkdir()
    task = Task(
        metadata=TaskMetadata(
            task_id="t-20260225-001",
            task_name="create-task",
            status="todo",
            date_created="2026-02-25",
            priority="p2",
            effort="m",
        ),
        body="",
        task_dir=task_dir,
    )

    output = render.render_create_success_plain(task, enable_links=False)

    assert "\x1b]8;;" not in output
    assert "Created: create-task (t-20260225-001)" in output
    assert "links: dir | task.md" in output
    assert str(task_dir.resolve()) not in output
    assert str(task.task_md_path.resolve()) not in output


def test_render_create_success_rich(tmp_path: Path) -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    task_dir = tmp_path / "create-task"
    task_dir.mkdir()
    task = Task(
        metadata=TaskMetadata(
            task_id="t-20260225-001",
            task_name="create-task",
            status="todo",
            date_created="2026-02-25",
            priority="p2",
            effort="m",
        ),
        body="",
        task_dir=task_dir,
    )

    renderable = render.render_create_success_rich(task)
    console = Console(record=True, width=240, force_terminal=False, color_system=None)
    console.print(renderable)
    text = console.export_text()

    assert "Created: create-task (t-20260225-001)" in text
    assert "links: dir | task.md" in text
    assert str(task_dir.resolve()) not in text
    assert str(task.task_md_path.resolve()) not in text


def test_render_tag_counts_plain_with_status_breakdown() -> None:
    rows = [
        {"tag": "backend", "total": 3, "todo": 1, "doing": 1, "done": 1},
        {"tag": "(untagged)", "total": 1, "todo": 1, "doing": 0, "done": 0},
    ]

    output = render.render_tag_counts_plain(rows, show_status_breakdown=True)
    lines = output.splitlines()
    assert lines[0].split() == ["tag", "total", "todo", "doing", "done"]
    assert "backend" in output
    assert "(untagged)" in output


def test_render_tag_counts_plain_without_status_breakdown() -> None:
    rows = [
        {"tag": "backend", "total": 2, "todo": 1, "doing": 1, "done": 0},
    ]

    output = render.render_tag_counts_plain(rows, show_status_breakdown=False)
    lines = output.splitlines()
    assert lines[0].split() == ["tag", "total"]
    assert "doing" not in lines[0]
    assert "done" not in lines[0]


def test_render_tag_counts_plain_empty() -> None:
    output = render.render_tag_counts_plain([], show_status_breakdown=True)
    assert output == "No tags found."


def test_render_tag_counts_rich() -> None:
    pytest.importorskip("rich")
    from rich.console import Console

    rows = [
        {"tag": "backend", "total": 2, "todo": 1, "doing": 1, "done": 0},
        {"tag": "(untagged)", "total": 1, "todo": 1, "doing": 0, "done": 0},
    ]

    renderable = render.render_tag_counts_rich(rows, show_status_breakdown=True)
    console = Console(record=True, width=120, force_terminal=False, color_system=None)
    console.print(renderable)
    text = console.export_text()

    assert "tag" in text
    assert "total" in text
    assert "backend" in text
    assert "(untagged)" in text


def test_render_tag_counts_json_shape() -> None:
    rows = [
        {"tag": "backend", "total": 2, "todo": 1, "doing": 1, "done": 0},
    ]

    output = render.render_tag_counts_json(rows)
    payload = json.loads(output)
    assert payload == rows
