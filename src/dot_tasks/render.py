"""Renderers for list and detail command output."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from .models import DependencyGraph, Task


STATUS_ORDER = ("todo", "doing", "completed")
STATUS_LABELS = {
    "todo": "TODO",
    "doing": "DOING",
    "completed": "DONE",
}


def _column_name(column: dict[str, int | str]) -> str:
    return str(column["name"])


def _column_width(column: dict[str, int | str]) -> int:
    return int(column["width"])


def _health_label(unmet_count: int) -> str:
    if unmet_count <= 0:
        return "ready"
    return f"blocked({unmet_count})"


def _priority_style(priority: str) -> str:
    return {
        "p0": "bold red",
        "p1": "bold yellow",
        "p2": "cyan",
        "p3": "dim",
    }.get(priority, "white")


def _status_style(status: str) -> str:
    return {
        "todo": "magenta",
        "doing": "cyan",
        "completed": "green",
    }.get(status, "white")


def _deps_rich_label(unmet_count: int) -> tuple[str, str]:
    if unmet_count <= 0:
        return "✓ ready", "green"
    return f"⚠ blocked({unmet_count})", "yellow"


def _task_list_row(task: Task, unmet_count: int) -> dict[str, str]:
    return {
        "task_name": task.metadata.task_name,
        "task_id": task.metadata.task_id,
        "status": task.metadata.status,
        "priority": task.metadata.priority,
        "effort": task.metadata.effort,
        "spec_readiness": task.metadata.spec_readiness,
        "deps": _health_label(unmet_count),
        "created": task.metadata.date_created,
        "completed": task.metadata.date_completed or "-",
    }


def _truncate(value: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width == 1:
        return "…"
    return f"{value[: width - 1]}…"


def render_task_list_plain(
    tasks: Iterable[Task],
    unmet_counts: dict[str, int],
    columns: list[dict[str, int | str]],
) -> str:
    rows = []
    for task in tasks:
        rows.append(_task_list_row(task, unmet_counts.get(task.metadata.task_id, 0)))

    headers = [_column_name(column) for column in columns]
    if not rows:
        return "No tasks found."

    widths = {name: _column_width(column) for name, column in zip(headers, columns)}

    lines = []
    header = "  ".join(_truncate(name, widths[name]).ljust(widths[name]) for name in headers)
    lines.append(header)
    lines.append("  ".join("-" * widths[name] for name in headers))
    for row in rows:
        rendered = []
        for name in headers:
            value = _truncate(str(row[name]), widths[name]).ljust(widths[name])
            rendered.append(value)
        lines.append("  ".join(rendered))
    return "\n".join(lines)


def _column_style(name: str) -> str:
    if name == "task_name":
        return "bold"
    if name in {"task_id", "created", "completed"}:
        return "dim"
    return ""


def render_task_list_rich(
    tasks: Iterable[Task],
    unmet_counts: dict[str, int],
    columns: list[dict[str, int | str]],
):
    from rich import box
    from rich.console import Group
    from rich.table import Table
    from rich.text import Text

    task_list = list(tasks)
    if not task_list:
        return "No tasks found."

    by_status: dict[str, list[Task]] = {status: [] for status in STATUS_ORDER}
    for task in task_list:
        if task.metadata.status in by_status:
            by_status[task.metadata.status].append(task)
        else:
            by_status.setdefault(task.metadata.status, []).append(task)

    renderables = []
    apply_done_defaults = None
    if columns:
        from . import storage

        apply_done_defaults = storage.apply_done_list_defaults
    for status in STATUS_ORDER:
        bucket = by_status.get(status) or []
        if not bucket:
            continue

        section_title = Text(
            f"{STATUS_LABELS.get(status, status.upper())} ({len(bucket)})",
            style=f"bold {_status_style(status)}",
        )
        renderables.append(section_title)

        bucket_columns = columns
        if status == "completed" and apply_done_defaults is not None:
            bucket_columns = apply_done_defaults(columns)

        table = Table(
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold white",
            pad_edge=False,
        )
        for column in bucket_columns:
            name = _column_name(column)
            width = _column_width(column)
            table.add_column(
                name,
                style=_column_style(name),
                min_width=width,
                max_width=width,
                overflow="ellipsis",
                no_wrap=True,
            )

        for task in bucket:
            unmet_count = unmet_counts.get(task.metadata.task_id, 0)
            row = _task_list_row(task, unmet_count)
            rendered: list[str | Text] = []
            for column in bucket_columns:
                name = _column_name(column)
                value = row[name]
                if name == "status":
                    rendered.append(Text(value, style=_status_style(value)))
                elif name == "priority":
                    rendered.append(Text(value, style=_priority_style(value)))
                elif name == "deps":
                    deps_label, deps_style = _deps_rich_label(unmet_count)
                    rendered.append(Text(deps_label, style=deps_style))
                else:
                    rendered.append(value)
            table.add_row(*rendered)

        renderables.append(table)
        renderables.append(Text(""))

    if renderables and isinstance(renderables[-1], Text) and not renderables[-1].plain:
        renderables.pop()

    return Group(*renderables)


def render_task_list_json(tasks: Iterable[Task], unmet_counts: dict[str, int]) -> str:
    payload = []
    for task in tasks:
        item = asdict(task.metadata)
        item["dependency_health"] = _health_label(unmet_counts.get(task.metadata.task_id, 0))
        item["path"] = str(task.task_dir)
        payload.append(item)
    return json.dumps(payload, indent=2)


def _graph_scope_label(graph: DependencyGraph) -> str:
    if graph.include_done:
        return "todo,doing,done"
    return "todo,doing"


def _graph_node_order(graph: DependencyGraph) -> dict[str, int]:
    return {task_id: index for index, task_id in enumerate(graph.nodes.keys())}


def _graph_blocked_count(graph: DependencyGraph, task_id: str) -> int:
    node = graph.nodes[task_id]
    count = 0
    for dep_id in node.depends_on:
        dep = graph.nodes.get(dep_id)
        if dep is None or dep.status != "completed":
            count += 1
    return count


def _graph_node_parts(graph: DependencyGraph, task_id: str) -> dict[str, str | int]:
    node = graph.nodes[task_id]
    blocked = _graph_blocked_count(graph, task_id)
    return {
        "task_name": node.task_name,
        "task_id": node.task_id,
        "status": node.status,
        "deps_label": _health_label(blocked),
        "blocked_count": blocked,
        "hidden_count": len(node.hidden_depends_on),
    }


def _graph_node_plain_line(
    graph: DependencyGraph,
    task_id: str,
    *,
    prefix: str = "",
    shared: bool = False,
) -> str:
    parts = _graph_node_parts(graph, task_id)
    line = (
        f"{prefix}• {parts['task_name']} ({parts['task_id']}) [{parts['status']}] "
        f"[deps: {parts['deps_label']}]"
    )
    hidden_count = int(parts["hidden_count"])
    if hidden_count > 0:
        line += f" (+{hidden_count} hidden)"
    if shared:
        line += " (shared)"
    return line


def _graph_node_rich_line(
    graph: DependencyGraph,
    task_id: str,
    *,
    prefix: str = "",
    shared: bool = False,
):
    from rich.text import Text

    parts = _graph_node_parts(graph, task_id)
    text = Text()
    if prefix:
        text.append(prefix, style="bright_black")
    text.append("• ", style="bright_black")
    text.append(str(parts["task_name"]), style="bold")
    text.append(" ")
    text.append(f"({parts['task_id']})", style="dim")
    text.append(" [")
    text.append(str(parts["status"]), style=_status_style(str(parts["status"])))
    text.append("]")
    text.append(" [deps: ")
    blocked_count = int(parts["blocked_count"])
    deps_style = "green" if blocked_count <= 0 else "yellow"
    text.append(str(parts["deps_label"]), style=deps_style)
    text.append("]")

    hidden_count = int(parts["hidden_count"])
    if hidden_count > 0:
        text.append(f" (+{hidden_count} hidden)", style="dim yellow")
    if shared:
        text.append(" (shared)", style="dim yellow")
    return text


def _graph_layers(graph: DependencyGraph) -> tuple[list[int], dict[int, list[str]]]:
    order = _graph_node_order(graph)
    memo: dict[str, int] = {}

    def depth(task_id: str) -> int:
        if task_id in memo:
            return memo[task_id]
        deps = graph.nodes[task_id].depends_on
        if not deps:
            memo[task_id] = 0
            return 0
        value = 1 + max(depth(dep_id) for dep_id in deps)
        memo[task_id] = value
        return value

    layers: dict[int, list[str]] = {}
    for task_id in graph.nodes:
        level = depth(task_id)
        layers.setdefault(level, []).append(task_id)

    for level in layers:
        layers[level] = sorted(layers[level], key=lambda item: order.get(item, 10**9))
    layer_ids = sorted(layers)
    return layer_ids, layers


def render_dependency_graph_tree_plain(graph: DependencyGraph) -> str:
    if not graph.nodes:
        return "No tasks found."

    total_edges = sum(len(node.depends_on) for node in graph.nodes.values())
    roots = graph.root_ids or list(graph.nodes.keys())
    order = _graph_node_order(graph)
    roots = sorted(roots, key=lambda task_id: order.get(task_id, 10**9))

    lines = [
        f"Dependency Graph | mode=tree | scope={_graph_scope_label(graph)}",
        f"nodes={len(graph.nodes)} edges={total_edges} roots={len(roots)}",
        "",
    ]

    seen: set[str] = set()

    def walk(task_id: str, prefix: str, is_last: bool, *, is_root: bool = False) -> None:
        repeated = task_id in seen
        branch = "" if is_root else ("└─ " if is_last else "├─ ")
        lines.append(
            _graph_node_plain_line(
                graph,
                task_id,
                prefix=f"{prefix}{branch}",
                shared=repeated,
            )
        )
        if repeated:
            return

        seen.add(task_id)
        children = graph.nodes[task_id].depends_on
        if not children:
            return

        child_prefix = prefix + ("" if is_root else ("   " if is_last else "│  "))
        for index, dep_id in enumerate(children):
            walk(
                dep_id,
                child_prefix,
                index == len(children) - 1,
                is_root=False,
            )

    for index, root_id in enumerate(roots):
        walk(root_id, "", True, is_root=True)
        if index < len(roots) - 1:
            lines.append("")

    return "\n".join(lines)


def render_dependency_graph_tree_rich(graph: DependencyGraph):
    from rich.console import Group
    from rich.text import Text

    if not graph.nodes:
        return "No tasks found."

    total_edges = sum(len(node.depends_on) for node in graph.nodes.values())
    roots = graph.root_ids or list(graph.nodes.keys())
    order = _graph_node_order(graph)
    roots = sorted(roots, key=lambda task_id: order.get(task_id, 10**9))

    title = Text()
    title.append("Dependency Graph", style="bold bright_white")
    title.append(" | ", style="bright_black")
    title.append("mode", style="bright_black")
    title.append("=")
    title.append("tree", style="bold cyan")
    title.append(" | ", style="bright_black")
    title.append("scope", style="bright_black")
    title.append("=")
    title.append(_graph_scope_label(graph), style="bold")

    stats = Text()
    stats.append("nodes", style="bright_black")
    stats.append("=")
    stats.append(str(len(graph.nodes)), style="bold")
    stats.append(" ")
    stats.append("edges", style="bright_black")
    stats.append("=")
    stats.append(str(total_edges), style="bold")
    stats.append(" ")
    stats.append("roots", style="bright_black")
    stats.append("=")
    stats.append(str(len(roots)), style="bold")

    lines: list[Text] = [title, stats, Text("")]
    seen: set[str] = set()

    def walk(task_id: str, prefix: str, is_last: bool, *, is_root: bool = False) -> None:
        repeated = task_id in seen
        branch = "" if is_root else ("└─ " if is_last else "├─ ")
        lines.append(
            _graph_node_rich_line(
                graph,
                task_id,
                prefix=f"{prefix}{branch}",
                shared=repeated,
            )
        )
        if repeated:
            return

        seen.add(task_id)
        children = graph.nodes[task_id].depends_on
        if not children:
            return

        child_prefix = prefix + ("" if is_root else ("   " if is_last else "│  "))
        for index, dep_id in enumerate(children):
            walk(
                dep_id,
                child_prefix,
                index == len(children) - 1,
                is_root=False,
            )

    for index, root_id in enumerate(roots):
        walk(root_id, "", True, is_root=True)
        if index < len(roots) - 1:
            lines.append(Text(""))

    return Group(*lines)


def render_dependency_graph_layers_plain(graph: DependencyGraph) -> str:
    if not graph.nodes:
        return "No tasks found."

    total_edges = sum(len(node.depends_on) for node in graph.nodes.values())
    layer_ids, layers = _graph_layers(graph)
    lines = [
        f"Dependency Graph | mode=layers | scope={_graph_scope_label(graph)}",
        f"nodes={len(graph.nodes)} edges={total_edges} layers={len(layer_ids)}",
        "",
    ]

    for index, layer_id in enumerate(layer_ids):
        if layer_id == 0:
            lines.append("L0 (no dependencies)")
        else:
            lines.append(f"L{layer_id} depends on L{layer_id - 1}")
        for task_id in layers[layer_id]:
            lines.append(_graph_node_plain_line(graph, task_id))
        if index < len(layer_ids) - 1:
            lines.append("")

    return "\n".join(lines)


def render_dependency_graph_layers_rich(graph: DependencyGraph):
    from rich.console import Group
    from rich.text import Text

    if not graph.nodes:
        return "No tasks found."

    total_edges = sum(len(node.depends_on) for node in graph.nodes.values())
    layer_ids, layers = _graph_layers(graph)

    title = Text()
    title.append("Dependency Graph", style="bold bright_white")
    title.append(" | ", style="bright_black")
    title.append("mode", style="bright_black")
    title.append("=")
    title.append("layers", style="bold cyan")
    title.append(" | ", style="bright_black")
    title.append("scope", style="bright_black")
    title.append("=")
    title.append(_graph_scope_label(graph), style="bold")

    stats = Text()
    stats.append("nodes", style="bright_black")
    stats.append("=")
    stats.append(str(len(graph.nodes)), style="bold")
    stats.append(" ")
    stats.append("edges", style="bright_black")
    stats.append("=")
    stats.append(str(total_edges), style="bold")
    stats.append(" ")
    stats.append("layers", style="bright_black")
    stats.append("=")
    stats.append(str(len(layer_ids)), style="bold")

    lines: list[Text] = [title, stats, Text("")]

    for index, layer_id in enumerate(layer_ids):
        if layer_id == 0:
            lines.append(Text("L0 (no dependencies)", style="bold cyan"))
        else:
            lines.append(Text(f"L{layer_id} depends on L{layer_id - 1}", style="bold cyan"))
        for task_id in layers[layer_id]:
            lines.append(_graph_node_rich_line(graph, task_id))
        if index < len(layer_ids) - 1:
            lines.append(Text(""))

    return Group(*lines)


def render_tag_counts_plain(
    rows: Iterable[dict[str, str | int]],
    *,
    show_status_breakdown: bool = True,
) -> str:
    headers = ["tag", "total", "todo", "doing", "done"] if show_status_breakdown else ["tag", "total"]
    row_data = [{name: str(row[name]) for name in headers} for row in rows]
    if not row_data:
        return "No tags found."

    widths = {
        name: max(len(name), *(len(item[name]) for item in row_data))
        for name in headers
    }
    lines = []
    lines.append("  ".join(name.ljust(widths[name]) for name in headers))
    lines.append("  ".join("-" * widths[name] for name in headers))
    for row in row_data:
        lines.append("  ".join(row[name].ljust(widths[name]) for name in headers))
    return "\n".join(lines)


def render_tag_counts_rich(
    rows: Iterable[dict[str, str | int]],
    *,
    show_status_breakdown: bool = True,
):
    from rich import box
    from rich.table import Table
    from rich.text import Text

    row_data = list(rows)
    if not row_data:
        return "No tags found."

    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold white",
        pad_edge=False,
    )
    table.add_column("tag", style="bold")
    table.add_column("total", justify="right")
    if show_status_breakdown:
        table.add_column("todo", justify="right")
        table.add_column("doing", justify="right")
        table.add_column("done", justify="right")

    for row in row_data:
        tag = str(row["tag"])
        tag_cell = Text(tag, style="dim" if tag == "(untagged)" else "bold")
        values: list[str | Text] = [
            tag_cell,
            str(row["total"]),
        ]
        if show_status_breakdown:
            values.extend(
                [
                    str(row["todo"]),
                    str(row["doing"]),
                    str(row["done"]),
                ]
            )
        table.add_row(*values)
    return table


def render_tag_counts_json(rows: Iterable[dict[str, str | int]]) -> str:
    payload = [dict(row) for row in rows]
    return json.dumps(payload, indent=2)


def _inline_dependency_rows(rows: list[tuple[str, str, str]]) -> str:
    if not rows:
        return "-"
    return ", ".join(f"{task_name} ({task_id}) [{status}]" for task_name, task_id, status in rows)


def _normalized_task_body(body: str) -> str:
    return body.lstrip("\n").rstrip() or "(empty)"


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _plain_link(path: Path, label: str) -> str:
    uri = _file_uri(path)
    return f"\033]8;;{uri}\033\\{label}\033]8;;\033\\"


def _rich_link(path: Path, label: str):
    from rich.text import Text

    text = Text(label, style="underline cyan")
    text.stylize(f"link {_file_uri(path)}")
    return text


def _task_file_detail_state(
    task: Task,
) -> tuple[Path, list[tuple[Path, bool]], list[Path] | None]:
    task_dir = task.task_dir.resolve()
    canonical_files = [
        task.task_md_path,
        task.activity_path,
        task.plan_path,
    ]
    canonical_names = {path.name for path in canonical_files}
    canonical_rows = [(path.resolve(), path.exists()) for path in canonical_files]

    try:
        extras = sorted(
            path.resolve()
            for path in task.task_dir.iterdir()
            if path.name not in canonical_names
        )
    except OSError:
        return task_dir, canonical_rows, None
    return task_dir, canonical_rows, extras


def _task_file_detail_lines_plain(task: Task, *, enable_links: bool) -> list[str]:
    task_dir, canonical_rows, extras = _task_file_detail_state(task)
    lines = [f"dir: {_plain_link(task_dir, task_dir.name) if enable_links else task_dir.name}"]

    file_tokens: list[str] = []
    for path, exists in canonical_rows:
        if exists:
            file_tokens.append(_plain_link(path, path.name) if enable_links else path.name)
        else:
            file_tokens.append(f"{path.name} (missing)")
    lines.append(f"files: {' | '.join(file_tokens)}")

    if extras is None:
        lines.append("extra: (unavailable)")
    elif extras:
        lines.append(
            "extra: "
            + " | ".join(
                _plain_link(path, path.name) if enable_links else path.name
                for path in extras
            )
        )
    return lines


def _task_file_detail_lines_rich(task: Task):
    from rich.text import Text

    task_dir, canonical_rows, extras = _task_file_detail_state(task)
    first_line = Text("dir: ")
    first_line.append_text(_rich_link(task_dir, task_dir.name))
    lines = [first_line]

    files_line = Text("files: ")
    for index, (path, exists) in enumerate(canonical_rows):
        if index > 0:
            files_line.append(" | ")
        if exists:
            files_line.append_text(_rich_link(path, path.name))
        else:
            files_line.append(f"{path.name} (missing)")
    lines.append(files_line)

    if extras is None:
        lines.append(Text("extra: (unavailable)"))
    elif extras:
        extra_line = Text("extra: ")
        for index, path in enumerate(extras):
            if index > 0:
                extra_line.append(" | ")
            extra_line.append_text(_rich_link(path, path.name))
        lines.append(extra_line)
    return lines


def render_task_detail_plain(
    task: Task,
    dependency_rows: list[tuple[str, str, str]],
    blocked_by_rows: list[tuple[str, str, str]],
    unmet_count: int,
    *,
    enable_links: bool = True,
) -> str:
    meta = task.metadata
    tags = ", ".join(meta.tags) if meta.tags else "-"
    lines = [
        f"{meta.task_name} ({meta.task_id})",
        f"[{meta.status}] [{meta.priority}] [{meta.effort}] [deps: {_health_label(unmet_count)}]",
        f"owner: {meta.owner or '-'}    tags: {tags}",
        (
            f"created: {meta.date_created}    started: {meta.date_started or '-'}    "
            f"completed: {meta.date_completed or '-'}"
        ),
        f"depends_on: {_inline_dependency_rows(dependency_rows)}",
        f"blocked_by: {_inline_dependency_rows(blocked_by_rows)}",
        *_task_file_detail_lines_plain(task, enable_links=enable_links),
        "",
        _normalized_task_body(task.body),
    ]
    return "\n".join(lines)


def render_task_detail_rich(
    task: Task,
    dependency_rows: list[tuple[str, str, str]],
    blocked_by_rows: list[tuple[str, str, str]],
    unmet_count: int,
):
    from rich.console import Group
    from rich.text import Text

    meta = task.metadata
    deps_label = _health_label(unmet_count)
    deps_style = "green" if unmet_count <= 0 else "yellow"

    title = Text()
    title.append(meta.task_name, style="bold")
    title.append(f" ({meta.task_id})", style="dim")

    chips = Text()
    chips.append(f"[{meta.status}]", style=_status_style(meta.status))
    chips.append(" ")
    chips.append(f"[{meta.priority}]", style=_priority_style(meta.priority))
    chips.append(" ")
    chips.append(f"[{meta.effort}]")
    chips.append(" ")
    chips.append("[deps: ")
    chips.append(deps_label, style=deps_style)
    chips.append("]")

    tags = ", ".join(meta.tags) if meta.tags else "-"
    owner_line = Text(f"owner: {meta.owner or '-'}    tags: {tags}")
    dates_line = Text(
        f"created: {meta.date_created}    started: {meta.date_started or '-'}    "
        f"completed: {meta.date_completed or '-'}"
    )
    depends_line = Text(f"depends_on: {_inline_dependency_rows(dependency_rows)}")
    blocked_line = Text(f"blocked_by: {_inline_dependency_rows(blocked_by_rows)}")
    file_lines = _task_file_detail_lines_rich(task)

    body_text = Text(_normalized_task_body(task.body))
    return Group(
        title,
        chips,
        owner_line,
        dates_line,
        depends_line,
        blocked_line,
        *file_lines,
        Text(""),
        body_text,
    )


def render_create_success_plain(task: Task, *, enable_links: bool = True) -> str:
    task_dir = task.task_dir.resolve()
    task_md = task.task_md_path.resolve()
    dir_text = _plain_link(task_dir, "dir") if enable_links else "dir"
    task_md_text = _plain_link(task_md, "task.md") if enable_links else "task.md"
    lines = [
        f"Created: {task.metadata.task_name} ({task.metadata.task_id})",
        f"links: {dir_text} | {task_md_text}",
    ]
    return "\n".join(lines)


def render_create_success_rich(task: Task):
    from rich.console import Group
    from rich.text import Text

    task_dir = task.task_dir.resolve()
    task_md = task.task_md_path.resolve()

    created_line = Text(f"Created: {task.metadata.task_name} ({task.metadata.task_id})")
    links_line = Text("links: ")
    links_line.append_text(_rich_link(task_dir, "dir"))
    links_line.append(" | ")
    links_line.append_text(_rich_link(task_md, "task.md"))
    return Group(created_line, links_line)


def render_task_detail_json(task: Task, dependency_rows: list[tuple[str, str, str]]) -> str:
    payload = {
        "metadata": asdict(task.metadata),
        "dependencies": [
            {"task_name": task_name, "task_id": task_id, "status": status}
            for task_name, task_id, status in dependency_rows
        ],
        "body": task.body,
        "path": str(task.task_dir),
    }
    return json.dumps(payload, indent=2)
