"""Renderers for list and detail command output."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Iterable

from .models import Task


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
        "deps": _health_label(unmet_count),
        "created": task.metadata.date_created,
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
    if name in {"task_id", "created"}:
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
    for status in STATUS_ORDER:
        bucket = by_status.get(status) or []
        if not bucket:
            continue

        section_title = Text(
            f"{STATUS_LABELS.get(status, status.upper())} ({len(bucket)})",
            style=f"bold {_status_style(status)}",
        )
        renderables.append(section_title)

        table = Table(
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold white",
            pad_edge=False,
        )
        for column in columns:
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
            for column in columns:
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


def render_task_detail_plain(
    task: Task,
    dependency_rows: list[tuple[str, str, str]],
    blocked_by_rows: list[tuple[str, str, str]],
    unmet_count: int,
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

    body_text = Text(_normalized_task_body(task.body))
    return Group(title, chips, owner_line, dates_line, depends_line, blocked_line, Text(""), body_text)


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
