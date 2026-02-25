"""Prompt-based interactive helpers."""

from __future__ import annotations

from typing import Any

import typer

from .models import Task, VALID_EFFORTS, VALID_PRIORITIES, VALID_SPEC_READINESS
from .selector_ui import (
    SelectorUnavailableError,
    select_fuzzy,
    select_fuzzy_many,
    select_many,
    select_one,
    select_text,
)
from . import storage


def _warn_selector_fallback(exc: Exception) -> None:
    message = str(exc)
    if not message:
        return
    typer.echo(f"Warning: {message}; falling back to numeric prompts.", err=True)


def _safe_prompt(message: str, *, default: str = "") -> str | None:
    try:
        selected = select_text(message, default_value=default)
    except SelectorUnavailableError:
        pass
    else:
        return selected

    try:
        return typer.prompt(message, default=default)
    except (typer.Abort, KeyboardInterrupt, EOFError):
        return None


def _prompt_single_choice(title: str, options: list[tuple[str, str]], default_value: str) -> str | None:
    try:
        selected = select_one(title, options, default_value=default_value)
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        return selected

    typer.echo(title)
    default_index = 1
    for idx, (value, label) in enumerate(options, start=1):
        typer.echo(f"{idx}. {label}")
        if value == default_value:
            default_index = idx

    while True:
        raw = _safe_prompt("Enter number", default=str(default_index))
        if raw is None:
            return None
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
) -> list[str] | None:
    if not options:
        return []

    try:
        selected = select_many(title, options, default_values=default_values)
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        return selected

    defaults = set(default_values or [])
    typer.echo(title)
    default_numbers: list[str] = []
    for idx, (value, label) in enumerate(options, start=1):
        mark = "x" if value in defaults else " "
        typer.echo(f"{idx}. [{mark}] {label}")
        if value in defaults:
            default_numbers.append(str(idx))

    while True:
        raw = _safe_prompt(
            "Enter comma-separated numbers",
            default=",".join(default_numbers),
        )
        if raw is None:
            return None
        raw = raw.strip()
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


def _prompt_depends_on_choice(
    title: str,
    options: list[tuple[str, str]],
    default_values: list[str] | None = None,
) -> list[str] | None:
    if not options:
        return []

    try:
        selected = select_fuzzy_many(title, options, default_values=default_values)
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        return selected

    defaults = set(default_values or [])
    typer.echo(title)
    default_numbers: list[str] = []
    for idx, (value, label) in enumerate(options, start=1):
        mark = "x" if value in defaults else " "
        typer.echo(f"{idx}. [{mark}] {label}")
        if value in defaults:
            default_numbers.append(str(idx))

    while True:
        raw = _safe_prompt(
            "Enter comma-separated numbers",
            default=",".join(default_numbers),
        )
        if raw is None:
            return None
        raw = raw.strip()
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


def _prompt_yes_no(title: str, *, default: bool = False) -> bool | None:
    options = [("yes", "Yes"), ("no", "No")]
    default_value = "yes" if default else "no"
    try:
        selected = select_one(title, options, default_value=default_value)
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        if selected is None:
            return None
        return selected == "yes"

    prompt_label = "y/N" if not default else "Y/n"
    default_text = "y" if default else "n"
    while True:
        raw = _safe_prompt(f"{title} ({prompt_label})", default=default_text)
        if raw is None:
            return None
        raw = raw.strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        typer.echo("Invalid selection. Enter y or n.")


def choose_task(tasks: list[Task], title: str = "Select task") -> str | None:
    if not tasks:
        return None

    options = [
        (
            task.metadata.task_name,
            f"{task.metadata.task_name} ({task.metadata.task_id}) [{task.metadata.status}]",
        )
        for task in tasks
    ]
    try:
        selected = select_fuzzy(title, options)
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        return selected

    typer.echo(title)
    for idx, task in enumerate(tasks, start=1):
        typer.echo(
            f"{idx}. {task.metadata.task_name} ({task.metadata.task_id}) [{task.metadata.status}]"
        )
    typer.echo("0. cancel")

    raw = _safe_prompt("Enter number", default="1")
    if raw is None:
        return None
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

    selector_options = [(name, f"{name:<8}  {summary}".rstrip()) for name, summary in commands]
    try:
        selected = select_one(title, selector_options, default_value=commands[0][0])
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        return selected

    typer.echo("")
    typer.echo("dot-tasks command palette")
    typer.echo("=" * 72)
    typer.echo(title)
    typer.echo("-" * 72)
    for idx, (name, summary) in enumerate(commands, start=1):
        typer.echo(f"{idx:>2}. {name:<8}  {summary}")
    typer.echo(" 0. cancel")

    raw = _safe_prompt("Enter number", default="1")
    if raw is None:
        return None
    try:
        index = int(raw)
    except ValueError:
        return None
    if index == 0:
        return None
    if 1 <= index <= len(commands):
        return commands[index - 1][0]
    return None


def init_config_form(
    *,
    default_interactive_enabled: bool = storage.DEFAULT_INTERACTIVE_ENABLED,
    default_show_banner: bool = storage.DEFAULT_SHOW_BANNER,
    default_list_column_names: list[str] | None = None,
    default_append_agents_snippet: bool = False,
    default_agents_file: str = "AGENTS.md",
) -> dict[str, Any] | None:
    default_interactive_value = "enabled" if default_interactive_enabled else "disabled"
    interactive_choice = _prompt_single_choice(
        "Default interactive behavior",
        [
            ("enabled", "Enable interactive prompts"),
            ("disabled", "Disable interactive prompts"),
        ],
        default_value=default_interactive_value,
    )
    if interactive_choice is None:
        return None

    default_banner_value = "enabled" if default_show_banner else "disabled"
    banner_choice = _prompt_single_choice(
        "Banner behavior for root 'dot-tasks'",
        [
            ("enabled", "Show banner"),
            ("disabled", "Hide banner"),
        ],
        default_value=default_banner_value,
    )
    if banner_choice is None:
        return None

    width_map = dict(storage.LIST_TABLE_COLUMN_DEFAULT_WIDTHS)
    fallback_column_names = [name for name, _ in storage.DEFAULT_LIST_TABLE_COLUMNS]
    if default_list_column_names is None:
        default_column_names = list(fallback_column_names)
    else:
        seen: set[str] = set()
        default_column_names = []
        for name in default_list_column_names:
            if name in storage.LIST_TABLE_COLUMNS_SUPPORTED and name not in seen:
                default_column_names.append(name)
                seen.add(name)
    column_options = [
        (name, f"{name} (width {width_map[name]})")
        for name in storage.LIST_TABLE_COLUMNS_SUPPORTED
    ]
    selected_columns = _prompt_multi_choice(
        "Select list columns",
        column_options,
        default_values=default_column_names,
    )
    if selected_columns is None:
        return None
    if not selected_columns:
        typer.echo("Warning: no list columns selected; using defaults.", err=True)
        selected_columns = fallback_column_names

    append_agents_snippet = _prompt_yes_no(
        "Append dot-tasks task-management section to AGENTS.md file?",
        default=default_append_agents_snippet,
    )
    if append_agents_snippet is None:
        return None

    agents_file: str | None = None
    if append_agents_snippet:
        selected_agents_file = _safe_prompt("AGENTS file path", default=default_agents_file)
        if selected_agents_file is None:
            return None
        agents_file = selected_agents_file.strip() or default_agents_file

    list_columns = [{"name": name, "width": width_map[name]} for name in selected_columns]
    return {
        "interactive_enabled": interactive_choice == "enabled",
        "show_banner": banner_choice == "enabled",
        "list_columns": list_columns,
        "append_agents_snippet": append_agents_snippet,
        "agents_file": agents_file,
    }


def create_form(
    default_name: str | None = None,
    dependency_options: list[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    dep_options = dependency_options or []

    task_name = _safe_prompt("task_name", default=default_name or "")
    if task_name is None:
        return None
    priority = _prompt_single_choice(
        "priority",
        [(value, value) for value in VALID_PRIORITIES],
        default_value="p2",
    )
    if priority is None:
        return None
    effort = _prompt_single_choice(
        "effort",
        [(value, value) for value in VALID_EFFORTS],
        default_value="m",
    )
    if effort is None:
        return None
    owner = _safe_prompt("owner", default="")
    if owner is None:
        return None
    summary = _safe_prompt("summary", default="")
    if summary is None:
        return None
    spec_readiness = _prompt_single_choice(
        "spec_readiness",
        [(value, value) for value in VALID_SPEC_READINESS],
        default_value="unspecified",
    )
    if spec_readiness is None:
        return None
    tags = _safe_prompt("tags (comma separated)", default="")
    if tags is None:
        return None
    if not dep_options:
        depends_on: list[str] = []
    else:
        should_set_depends = _prompt_yes_no("Set task dependencies?", default=False)
        if should_set_depends is None:
            return None
        if should_set_depends:
            selected_depends = _prompt_depends_on_choice(
                "depends_on selectors",
                dep_options,
                default_values=[],
            )
            if selected_depends is None:
                return None
            depends_on = selected_depends
        else:
            depends_on = []
    return {
        "task_name": task_name.strip(),
        "priority": priority,
        "effort": effort,
        "owner": owner.strip() or None,
        "summary": summary.strip(),
        "spec_readiness": spec_readiness,
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
    if priority is None:
        return None
    effort = _prompt_single_choice(
        "effort",
        [("__keep__", "Keep current"), *[(value, value) for value in VALID_EFFORTS]],
        default_value="__keep__",
    )
    if effort is None:
        return None
    spec_readiness = _prompt_single_choice(
        "spec_readiness",
        [("__keep__", "Keep current"), *[(value, value) for value in VALID_SPEC_READINESS]],
        default_value="__keep__",
    )
    if spec_readiness is None:
        return None
    owner = _safe_prompt("owner (blank to keep)", default=task.metadata.owner or "")
    if owner is None:
        return None
    tags = _safe_prompt("add tags (comma separated, blank none)", default="")
    if tags is None:
        return None
    depends_on = _prompt_depends_on_choice(
        "depends_on selectors (replaces current selection)",
        dep_options,
        default_values=task.metadata.depends_on,
    )
    if depends_on is None:
        return None
    return {
        "priority": None if priority == "__keep__" else priority,
        "effort": None if effort == "__keep__" else effort,
        "spec_readiness": None if spec_readiness == "__keep__" else spec_readiness,
        "owner": owner,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "depends_on": depends_on,
        "replace_depends_on": True,
    }
