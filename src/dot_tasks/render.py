"""Renderers for list and detail command output."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Iterable

from .models import Task


def _health_label(unmet_count: int) -> str:
    if unmet_count <= 0:
        return "ready"
    return f"blocked({unmet_count})"


def render_task_list_plain(tasks: Iterable[Task], unmet_counts: dict[str, int]) -> str:
    rows = []
    for task in tasks:
        rows.append(
            {
                "task_name": task.metadata.task_name,
                "task_id": task.metadata.task_id,
                "status": task.metadata.status,
                "priority": task.metadata.priority,
                "effort": task.metadata.effort,
                "deps": _health_label(unmet_counts.get(task.metadata.task_id, 0)),
                "created": task.metadata.date_created,
            }
        )

    headers = ["task_name", "task_id", "status", "priority", "effort", "deps", "created"]
    if not rows:
        return "No tasks found."

    widths = {h: len(h) for h in headers}
    for row in rows:
        for key, value in row.items():
            widths[key] = max(widths[key], len(str(value)))

    lines = []
    header = "  ".join(h.ljust(widths[h]) for h in headers)
    lines.append(header)
    lines.append("  ".join("-" * widths[h] for h in headers))
    for row in rows:
        lines.append("  ".join(str(row[h]).ljust(widths[h]) for h in headers))
    return "\n".join(lines)


def render_task_list_json(tasks: Iterable[Task], unmet_counts: dict[str, int]) -> str:
    payload = []
    for task in tasks:
        item = asdict(task.metadata)
        item["dependency_health"] = _health_label(unmet_counts.get(task.metadata.task_id, 0))
        item["path"] = str(task.task_dir)
        payload.append(item)
    return json.dumps(payload, indent=2)


def render_task_detail_plain(task: Task, dependency_rows: list[tuple[str, str, str]]) -> str:
    meta = task.metadata
    lines = [
        f"task_name: {meta.task_name}",
        f"task_id: {meta.task_id}",
        f"status: {meta.status}",
        f"priority: {meta.priority}",
        f"effort: {meta.effort}",
        f"owner: {meta.owner or '-'}",
        f"tags: {', '.join(meta.tags) if meta.tags else '-'}",
        f"created: {meta.date_created}",
        f"started: {meta.date_started or '-'}",
        f"completed: {meta.date_completed or '-'}",
        "dependencies:",
    ]
    if not dependency_rows:
        lines.append("- none")
    else:
        for task_name, task_id, status in dependency_rows:
            lines.append(f"- {task_name} ({task_id}) [{status}]")

    lines.append("")
    lines.append("body:")
    lines.append(task.body.rstrip() or "(empty)")
    return "\n".join(lines)


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
