"""Prompt-based interactive helpers."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import sys
from typing import Any, Callable

import typer

from .models import FieldDef, Task, VALID_STATUSES
from .selector_ui import (
    SelectionSeparator,
    SelectorUnavailableError,
    select_fuzzy,
    select_fuzzy_many,
    select_many,
    select_one,
    select_date,
    select_text,
)
from . import storage

_ADD_NEW_TAGS_SENTINEL = "__add_new_tags__"
_ADD_NEW_TAGS_LABEL = "+ add new tag(s)"
_COMMAND_SECTION_STYLE = {"separator": "bold ansicyan"}


@dataclass(frozen=True)
class CommandPaletteEntry:
    name: str
    summary: str


@dataclass(frozen=True)
class CommandPaletteSection:
    title: str
    commands: list[CommandPaletteEntry]


def _format_command_section_heading(title: str) -> str:
    return f"---- {title} ----"


def _echo_command_section_heading(title: str) -> None:
    heading = _format_command_section_heading(title)
    if sys.stdout.isatty():
        typer.secho(heading, fg=typer.colors.CYAN, bold=True)
        return
    typer.echo(heading)


def _warn_selector_fallback(exc: Exception) -> None:
    message = str(exc)
    if not message:
        return
    typer.echo(f"Warning: {message}; falling back to numeric prompts.", err=True)


def _safe_prompt(message: str, *, default: str = "", multiline: bool = False) -> str | None:
    try:
        selected = select_text(message, default_value=default, multiline=multiline)
    except SelectorUnavailableError:
        pass
    else:
        return selected

    fallback_message = message
    if multiline:
        fallback_message = message.replace(" (Esc+Enter to submit)", "")

    try:
        return typer.prompt(fallback_message, default=default)
    except (typer.Abort, KeyboardInterrupt, EOFError):
        return None


def _prompt_date(message: str, *, initial_value: dt.date | None = None) -> str | None:
    initial = initial_value or dt.date.today()
    try:
        selected = select_date(message, initial_value=initial)
    except SelectorUnavailableError as exc:
        message_text = str(exc)
        if message_text:
            typer.echo(
                f"Warning: {message_text}; falling back to an ISO date prompt.",
                err=True,
            )
    else:
        return selected.isoformat() if selected is not None else None

    while True:
        raw = _safe_prompt(message, default=initial.isoformat())
        if raw is None:
            return None
        cleaned = raw.strip()
        try:
            parsed = dt.date.fromisoformat(cleaned)
        except ValueError:
            typer.echo("Invalid date. Use YYYY-MM-DD.")
            continue
        if parsed.isoformat() != cleaned:
            typer.echo("Invalid date. Use YYYY-MM-DD.")
            continue
        return cleaned


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


def _prompt_tag_choice(
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


def _prompt_tags(
    tag_options: list[tuple[str, str]],
    *,
    default_values: list[str] | None = None,
) -> list[str] | None:
    selected_existing: list[str]
    created_tags: list[str] = []
    if tag_options:
        selector_options = [*tag_options, (_ADD_NEW_TAGS_SENTINEL, _ADD_NEW_TAGS_LABEL)]
        selected_tags = _prompt_tag_choice(
            "tags (select existing or add new)",
            selector_options,
            default_values=default_values,
        )
        if selected_tags is None:
            return None
        wants_new_tags = _ADD_NEW_TAGS_SENTINEL in selected_tags
        selected_existing = [tag for tag in selected_tags if tag != _ADD_NEW_TAGS_SENTINEL]
        if wants_new_tags:
            new_tags = _safe_prompt("new tags (comma separated, blank none)", default="")
            if new_tags is None:
                return None
            created_tags = [token.strip() for token in new_tags.split(",") if token.strip()]
    else:
        selected_existing = []
        new_tags = _safe_prompt("new tags (comma separated, blank none)", default="")
        if new_tags is None:
            return None
        created_tags = [token.strip() for token in new_tags.split(",") if token.strip()]

    return sorted({*selected_existing, *created_tags})


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
    sections: list[CommandPaletteSection],
    title: str = "Select command",
) -> str | None:
    commands = [command for section in sections for command in section.commands]
    if not commands:
        return None

    command_name_width = max(8, max(len(command.name) for command in commands))
    selector_options: list[tuple[str, str] | SelectionSeparator] = []
    for section in sections:
        if not section.commands:
            continue
        selector_options.append(SelectionSeparator(_format_command_section_heading(section.title)))
        selector_options.extend(
            (
                command.name,
                f"{command.name:<{command_name_width}}  {command.summary}".rstrip(),
            )
            for command in section.commands
        )
    try:
        selected = select_one(title, selector_options, style=_COMMAND_SECTION_STYLE)
    except SelectorUnavailableError as exc:
        _warn_selector_fallback(exc)
    else:
        return selected

    typer.echo("")
    typer.echo("dot-tasks command palette")
    typer.echo("=" * 72)
    typer.echo(title)
    typer.echo("-" * 72)
    index = 1
    for section in sections:
        if not section.commands:
            continue
        typer.echo("")
        _echo_command_section_heading(section.title)
        for command in section.commands:
            typer.echo(f"{index:>2}. {command.name:<{command_name_width}}  {command.summary}")
            index += 1
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
        return commands[index - 1].name
    return None


def init_config_form(
    *,
    default_interactive_enabled: bool = storage.DEFAULT_INTERACTIVE_ENABLED,
    default_show_banner: bool = storage.DEFAULT_SHOW_BANNER,
    current_field_entries: list[Any] | None = None,
    default_field_names: list[str] | None = None,
    default_list_column_names: list[str] | None = None,
    default_append_agents_snippet: bool = False,
    default_agents_file: str = "AGENTS.md",
) -> dict[str, Any] | None:
    """Interactive init settings.

    *current_field_entries* are the existing settings.fields entries (kept, except built-ins
    the user deselects); *default_field_names* are the built-ins preselected in the picker.
    """
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

    existing_entries = list(current_field_entries or [])
    previous_defs = storage.parse_field_entries(existing_entries)
    previous_names = {field_def.name for field_def in previous_defs}
    preselected = list(default_field_names if default_field_names is not None else storage.INIT_DEFAULT_FIELD_NAMES)
    field_options = [
        (name, f"{name} ({field_def.type})") for name, field_def in storage.BUILTIN_FIELDS.items()
    ]
    selected_fields = _prompt_multi_choice(
        "Task fields (built-in; add your own in settings.fields)",
        field_options,
        default_values=[name for name in preselected if name in storage.BUILTIN_FIELDS],
    )
    if selected_fields is None:
        return None

    # Keep existing entries (custom fields, overrides) except deselected built-ins; append
    # newly selected built-ins by name.
    field_entries: list[Any] = []
    kept_names: set[str] = set()
    for entry in existing_entries:
        name = entry if isinstance(entry, str) else entry.get("name") if isinstance(entry, dict) else None
        if name in storage.BUILTIN_FIELDS and name not in selected_fields:
            continue
        field_entries.append(entry)
        if isinstance(name, str):
            kept_names.add(name)
    field_entries.extend(name for name in selected_fields if name not in kept_names)
    field_defs = storage.parse_field_entries(field_entries)

    width_map = storage.column_default_widths(field_defs)
    supported_columns = storage.supported_list_columns(field_defs)
    fallback_column_names = storage.default_list_column_names(field_defs)
    if default_list_column_names is None:
        default_column_names = list(fallback_column_names)
    else:
        default_column_names = []
        for name in default_list_column_names:
            if name in supported_columns and name not in default_column_names:
                default_column_names.append(name)
        # Preselect columns for fields enabled in this run (text fields stay opt-in).
        for field_def in field_defs:
            if (
                field_def.name not in previous_names
                and field_def.type != "text"
                and field_def.name not in default_column_names
            ):
                default_column_names.append(field_def.name)
    column_options = [(name, f"{name} (width {width_map[name]})") for name in supported_columns]
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

    return {
        "interactive_enabled": interactive_choice == "enabled",
        "show_banner": banner_choice == "enabled",
        "fields": field_entries,
        "list_columns": [{"name": name, "width": width_map[name]} for name in selected_columns],
        "append_agents_snippet": append_agents_snippet,
        "agents_file": agents_file,
    }


_NONE = "__none__"
_KEEP = "__keep__"
_CLEAR = "__clear__"
_SET = "__set__"
_MISSING = object()


def _prompt_new_field_value(field_def: FieldDef) -> str | None | object:
    """Ask for a new task's field value; returns _MISSING when the user cancels."""
    if field_def.type == "choice":
        options = [(value, value) for value in field_def.values]
        if field_def.default is None:
            options.insert(0, (_NONE, "(none)"))
        selected = _prompt_single_choice(
            field_def.name,
            options,
            default_value=field_def.default or _NONE,
        )
        if selected is None:
            return _MISSING
        return None if selected == _NONE else selected
    if field_def.type == "date":
        should_set = _prompt_yes_no(f"Set {field_def.name}?", default=field_def.default is not None)
        if should_set is None:
            return _MISSING
        if not should_set:
            return None
        initial = dt.date.fromisoformat(field_def.default) if field_def.default else None
        value = _prompt_date(field_def.name, initial_value=initial)
        return _MISSING if value is None else value
    raw = _safe_prompt(field_def.name, default=field_def.default or "")
    if raw is None:
        return _MISSING
    return raw.strip() or None


def _prompt_changed_field_value(field_def: FieldDef, current: object) -> str | None | object:
    """Ask for an updated value; returns _KEEP for no change and _MISSING on cancel."""
    if field_def.type == "choice":
        options = [(_KEEP, f"Keep current ({current if current is not None else '-'})")]
        options.extend((value, value) for value in field_def.values)
        if current is not None:
            options.append((_CLEAR, "Clear"))
        selected = _prompt_single_choice(field_def.name, options, default_value=_KEEP)
        if selected is None:
            return _MISSING
        if selected == _KEEP:
            return _KEEP
        return None if selected == _CLEAR else selected
    if field_def.type == "date":
        options = [(_KEEP, f"Keep current ({current if current is not None else '-'})"), (_SET, "Set or change")]
        if current is not None:
            options.append((_CLEAR, "Clear"))
        action = _prompt_single_choice(field_def.name, options, default_value=_KEEP)
        if action is None:
            return _MISSING
        if action == _CLEAR:
            return None
        if action != _SET:
            return _KEEP
        try:
            initial = dt.date.fromisoformat(str(current)) if current else None
        except ValueError:
            initial = None
        value = _prompt_date(field_def.name, initial_value=initial)
        return _MISSING if value is None else value
    current_text = "" if current is None else str(current)
    raw = _safe_prompt(f"{field_def.name} (blank to clear)", default=current_text)
    if raw is None:
        return _MISSING
    cleaned = raw.strip()
    if cleaned == current_text:
        return _KEEP
    return cleaned or None


def create_form(
    default_name: str | None = None,
    dependency_options: list[tuple[str, str]] | None = None,
    tag_options: list[tuple[str, str]] | None = None,
    field_defs: list[FieldDef] | None = None,
    validate_task_name: Callable[[str], None] | None = None,
    validate_depends_on: Callable[[list[str]], None] | None = None,
) -> dict[str, Any] | None:
    """Interactive create: name, one-line summary, configured fields, tags, dependencies.

    The task description itself is written in task.md with an editor afterwards.
    """
    dep_options = dependency_options or []
    available_tags = tag_options or []

    while True:
        raw_task_name = _safe_prompt("task_name", default=default_name or "")
        if raw_task_name is None:
            return None
        task_name = raw_task_name.strip()
        if not task_name:
            typer.echo("Error: task_name is required", err=True)
            continue
        if validate_task_name is not None:
            try:
                validate_task_name(task_name)
            except Exception as e:
                typer.echo(f"Error: {e}", err=True)
                continue
        break

    summary = _safe_prompt("summary (one line, optional)", default="")
    if summary is None:
        return None
    field_values: dict[str, str | None] = {"summary": summary.strip() or None}
    for field_def in field_defs or []:
        value = _prompt_new_field_value(field_def)
        if value is _MISSING:
            return None
        field_values[field_def.name] = value  # type: ignore[assignment]

    tags = _prompt_tags(available_tags)
    if tags is None:
        return None
    depends_on: list[str] = []
    if dep_options:
        should_set_depends = _prompt_yes_no("Set task dependencies?", default=False)
        if should_set_depends is None:
            return None
        if should_set_depends:
            while True:
                selected_depends = _prompt_depends_on_choice(
                    "depends_on selectors",
                    dep_options,
                    default_values=[],
                )
                if selected_depends is None:
                    return None
                if validate_depends_on is not None:
                    try:
                        validate_depends_on(selected_depends)
                    except Exception as e:
                        typer.echo(f"Error: {e}", err=True)
                        continue
                depends_on = selected_depends
                break
    return {
        "task_name": task_name,
        "field_values": field_values,
        "tags": tags,
        "depends_on": depends_on,
    }


def update_form(
    task: Task,
    dependency_options: list[tuple[str, str]] | None = None,
    tag_options: list[tuple[str, str]] | None = None,
    field_defs: list[FieldDef] | None = None,
    validate_depends_on: Callable[[list[str]], None] | None = None,
) -> dict[str, Any] | None:
    """Interactive update of frontmatter only; the body is edited directly in task.md."""
    dep_options = dependency_options or []
    available_tags = tag_options or []

    status = _prompt_single_choice(
        "status",
        [(_KEEP, "Keep current"), *[(value, value) for value in VALID_STATUSES]],
        default_value=_KEEP,
    )
    if status is None:
        return None

    field_values: dict[str, str | None] = {}
    summary = _safe_prompt("summary (blank to clear)", default=task.metadata.summary)
    if summary is None:
        return None
    if summary.strip() != task.metadata.summary:
        field_values["summary"] = summary.strip() or None
    for field_def in field_defs or []:
        value = _prompt_changed_field_value(field_def, task.metadata.fields.get(field_def.name))
        if value is _MISSING:
            return None
        if value is not _KEEP:
            field_values[field_def.name] = value  # type: ignore[assignment]

    tags = _prompt_tags(available_tags, default_values=task.metadata.tags)
    if tags is None:
        return None
    replace_depends_on = False
    depends_on: list[str] = []
    if dep_options:
        should_update_depends = _prompt_yes_no("Update task dependencies?", default=False)
        if should_update_depends is None:
            return None
        if should_update_depends:
            while True:
                selected_depends = _prompt_depends_on_choice(
                    "depends_on selectors (replaces current selection)",
                    dep_options,
                    default_values=task.metadata.depends_on,
                )
                if selected_depends is None:
                    return None
                if validate_depends_on is not None:
                    try:
                        validate_depends_on(selected_depends)
                    except Exception as e:
                        typer.echo(f"Error: {e}", err=True)
                        continue
                depends_on = selected_depends
                replace_depends_on = True
                break
    return {
        "status": None if status == _KEEP else status,
        "field_values": field_values,
        "tags": tags,
        "depends_on": depends_on,
        "replace_depends_on": replace_depends_on,
    }
