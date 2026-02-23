"""Prompt-based interactive helpers."""

from __future__ import annotations

from typing import Any

import typer

from .models import Task, VALID_EFFORTS, VALID_PRIORITIES


def _prompt_single_choice(title: str, options: list[tuple[str, str]], default_value: str) -> str:
    typer.echo(title)
    default_index = 1
    for idx, (value, label) in enumerate(options, start=1):
        typer.echo(f"{idx}. {label}")
        if value == default_value:
            default_index = idx

    while True:
        raw = typer.prompt("Enter number", default=str(default_index))
        try:
            index = int(raw)
        except ValueError:
            typer.echo("Invalid selection. Enter a number.")
            continue
        if 1 <= index <= len(options):
            return options[index - 1][0]
        typer.echo("Selection out of range.")


def _prompt_multi_choice(
    title: str,
    options: list[tuple[str, str]],
    default_values: list[str] | None = None,
) -> list[str]:
    if not options:
        return []

    defaults = set(default_values or [])
    typer.echo(title)
    default_numbers: list[str] = []
    for idx, (value, label) in enumerate(options, start=1):
        mark = "x" if value in defaults else " "
        typer.echo(f"{idx}. [{mark}] {label}")
        if value in defaults:
            default_numbers.append(str(idx))

    while True:
        raw = typer.prompt(
            "Enter comma-separated numbers",
            default=",".join(default_numbers),
        ).strip()
        if not raw:
            return []

        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        try:
            indexes = [int(token) for token in tokens]
        except ValueError:
            typer.echo("Invalid selection. Use comma-separated numbers.")
            continue

        if any(index < 1 or index > len(options) for index in indexes):
            typer.echo("Selection out of range.")
            continue

        selected = {index - 1 for index in indexes}
        return [value for idx, (value, _) in enumerate(options) if idx in selected]


def choose_task(tasks: list[Task], title: str = "Select task") -> str | None:
    if not tasks:
        return None

    typer.echo(title)
    for idx, task in enumerate(tasks, start=1):
        typer.echo(f"{idx}. {task.metadata.task_name} ({task.metadata.task_id})")
    typer.echo("0. cancel")

    raw = typer.prompt("Enter number", default="1")
    try:
        index = int(raw)
    except ValueError:
        return None
    if index == 0:
        return None
    if 1 <= index <= len(tasks):
        return tasks[index - 1].metadata.task_name
    return None


def choose_command(
    commands: list[tuple[str, str]],
    title: str = "Select command",
) -> str | None:
    if not commands:
        return None

    typer.echo("")
    typer.echo("dot-tasks command palette")
    typer.echo("=" * 72)
    typer.echo(title)
    typer.echo("-" * 72)
    for idx, (name, summary) in enumerate(commands, start=1):
        typer.echo(f"{idx:>2}. {name:<8}  {summary}")
    typer.echo(" 0. cancel")

    raw = typer.prompt("Enter number", default="1")
    try:
        index = int(raw)
    except ValueError:
        return None
    if index == 0:
        return None
    if 1 <= index <= len(commands):
        return commands[index - 1][0]
    return None


def create_form(
    default_name: str | None = None,
    dependency_options: list[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    dep_options = dependency_options or []

    task_name = typer.prompt("task_name", default=default_name or "")
    priority = _prompt_single_choice(
        "priority",
        [(value, value) for value in VALID_PRIORITIES],
        default_value="p2",
    )
    effort = _prompt_single_choice(
        "effort",
        [(value, value) for value in VALID_EFFORTS],
        default_value="m",
    )
    owner = typer.prompt("owner", default="")
    summary = typer.prompt("summary", default="")
    tags = typer.prompt("tags (comma separated)", default="")
    depends_on = _prompt_multi_choice(
        "depends_on selectors",
        dep_options,
        default_values=[],
    )
    return {
        "task_name": task_name.strip(),
        "priority": priority,
        "effort": effort,
        "owner": owner.strip() or None,
        "summary": summary.strip(),
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "depends_on": depends_on,
    }


def update_form(
    task: Task,
    dependency_options: list[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    dep_options = dependency_options or []

    priority = _prompt_single_choice(
        "priority",
        [("__keep__", "Keep current"), *[(value, value) for value in VALID_PRIORITIES]],
        default_value="__keep__",
    )
    effort = _prompt_single_choice(
        "effort",
        [("__keep__", "Keep current"), *[(value, value) for value in VALID_EFFORTS]],
        default_value="__keep__",
    )
    owner = typer.prompt("owner (blank to keep)", default=task.metadata.owner or "")
    tags = typer.prompt("add tags (comma separated, blank none)", default="")
    depends_on = _prompt_multi_choice(
        "depends_on selectors (replaces current selection)",
        dep_options,
        default_values=task.metadata.depends_on,
    )
    note = typer.prompt("update note", default="Task metadata updated")
    return {
        "priority": None if priority == "__keep__" else priority,
        "effort": None if effort == "__keep__" else effort,
        "owner": owner,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "depends_on": depends_on,
        "replace_depends_on": True,
        "note": note.strip(),
    }
