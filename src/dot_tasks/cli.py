"""CLI entrypoint for dot-tasks."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

import typer

from . import render, storage
from .models import Task, TaskError, TaskValidationError
from .service import TaskService
from .tui import choose_command, choose_task, create_form, show_board, update_form

app = typer.Typer(help="Human-readable and agent-readable task manager")

ModeOption = Annotated[
    str | None,
    typer.Option("--mode", help="Interaction mode: off|prompt|full"),
]
TasksRootOption = Annotated[Path | None, typer.Option("--tasks-root", help="Explicit .tasks path")]


def _can_interact() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _interactive_enabled(mode: str) -> bool:
    return mode in {"prompt", "full"}


def _can_interact_in_mode(mode: str) -> bool:
    return _interactive_enabled(mode) and _can_interact()


def _echo_root_notice(root: Path, multiple_found: bool) -> None:
    typer.echo(f"Using tasks root: {root}", err=True)
    if multiple_found:
        typer.echo("Warning: multiple .tasks roots found; using nearest ancestor.", err=True)


def _warn_config(message: str) -> None:
    typer.echo(f"Warning: {message}", err=True)


def _normalize_mode(mode: str | None) -> str | None:
    if mode is None:
        return None
    normalized = mode.strip().lower()
    if normalized not in storage.INTERACTIVE_MODES:
        allowed = ", ".join(storage.INTERACTIVE_MODES)
        raise typer.BadParameter(f"invalid mode '{mode}', expected one of: {allowed}")
    return normalized


def _resolve_mode(tasks_root: Path | None, mode_override: str | None) -> str:
    explicit = _normalize_mode(mode_override)
    if explicit is not None:
        return explicit
    if tasks_root is None:
        return storage.DEFAULT_INTERACTIVE_MODE
    return storage.resolve_interactive_mode(tasks_root, warn=_warn_config)


def _resolve_existing_root(tasks_root: Path | None) -> Path:
    if tasks_root is not None:
        root = tasks_root.resolve()
        if not root.exists():
            raise typer.BadParameter(f"tasks root not found: {root}")
        return root

    root, multiple = storage.choose_tasks_root(Path.cwd())
    if root is None:
        raise TaskValidationError(
            "No .tasks root found from current directory upward. Run 'dot-tasks init' first."
        )
    _echo_root_notice(root, multiple)
    return root


def _resolve_init_root(tasks_root: Path | None) -> Path:
    if tasks_root is not None:
        return tasks_root.resolve()

    root, multiple = storage.choose_tasks_root(Path.cwd())
    if root is not None:
        _echo_root_notice(root, multiple)
        return root

    default_root = storage.default_init_root(Path.cwd())
    typer.echo(f"No .tasks found. Initializing at: {default_root}", err=True)
    return default_root


def _root_for_mode_lookup(tasks_root: Path | None) -> Path | None:
    if tasks_root is not None:
        root = tasks_root.resolve()
        if root.exists():
            return root
        return None
    root, _ = storage.choose_tasks_root(Path.cwd())
    return root


def _service(tasks_root: Path | None = None, *, init: bool = False) -> TaskService:
    root = _resolve_init_root(tasks_root) if init else _resolve_existing_root(tasks_root)
    svc = TaskService(root)
    svc.ensure_layout()
    return svc


def _select_task_if_missing(
    svc: TaskService,
    task_name: str | None,
    prompt: str,
    *,
    mode: str,
) -> str:
    if task_name:
        return task_name
    tasks = svc.list_tasks()
    if not tasks:
        raise TaskValidationError("No tasks available.")
    if not _can_interact_in_mode(mode):
        raise TaskValidationError("task_name is required in non-interactive mode")
    selected = choose_task(tasks, title=prompt, mode=mode)
    if not selected:
        raise typer.Exit(code=1)
    return selected


def _dependency_choices(tasks: list[Task], *, exclude_task_id: str | None = None) -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for task in tasks:
        if exclude_task_id is not None and task.metadata.task_id == exclude_task_id:
            continue
        choices.append(
            (
                task.metadata.task_id,
                f"{task.metadata.task_name} ({task.metadata.task_id}) [{task.metadata.status}]",
            )
        )
    return choices


def _run_and_handle(fn) -> None:
    try:
        fn()
    except TaskError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


def _command_choices() -> list[tuple[str, str]]:
    choices: list[tuple[str, str]] = []
    for command in app.registered_commands:
        if not command.name or command.callback is None:
            continue
        doc = (command.callback.__doc__ or "").strip()
        summary = doc.splitlines()[0] if doc else ""
        choices.append((command.name, summary))
    return choices


def _find_command(name: str):
    for command in app.registered_commands:
        if command.name == name and command.callback is not None:
            return command
    return None


def _invoke_from_shell(
    ctx: typer.Context,
    command_name: str,
    *,
    mode: str,
    tasks_root: Path | None,
) -> None:
    command = _find_command(command_name)
    if command is None or command.callback is None:
        return
    kwargs: dict[str, object] = {"mode": mode}
    if tasks_root is not None:
        kwargs["tasks_root"] = tasks_root
    try:
        ctx.invoke(command.callback, **kwargs)
    except TypeError:
        fallback: dict[str, object] = {}
        if tasks_root is not None:
            fallback["tasks_root"] = tasks_root
        ctx.invoke(command.callback, **fallback)


def _run_command_shell(ctx: typer.Context, *, mode: str, tasks_root: Path | None) -> None:
    choices = _command_choices()
    while True:
        selected = choose_command(choices, title="Select a dot-tasks command", mode=mode)
        if not selected:
            raise typer.Exit(code=1)
        try:
            _invoke_from_shell(ctx, selected, mode=mode, tasks_root=tasks_root)
        except typer.Exit:
            # Keep shell running so users can continue navigating between commands.
            continue


def _prompt_init_mode() -> str:
    options = [
        ("prompt", "Prompt mode"),
        ("full", "Full-screen mode"),
        ("off", "Non-interactive mode"),
    ]
    typer.echo("Select default interactive mode for this tasks root:")
    for idx, (_, label) in enumerate(options, start=1):
        typer.echo(f"{idx}. {label}")
    while True:
        raw = typer.prompt("Enter number", default="1")
        try:
            index = int(raw)
        except ValueError:
            typer.echo("Invalid selection. Enter a number.")
            continue
        if 1 <= index <= len(options):
            return options[index - 1][0]
        typer.echo("Selection out of range.")


@app.callback(invoke_without_command=True)
def root_callback(
    ctx: typer.Context,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Open an interactive command shell when no command is provided."""
    if ctx.invoked_subcommand is not None:
        return

    root_for_mode = _root_for_mode_lookup(tasks_root)
    local_mode = _resolve_mode(root_for_mode, mode)

    if local_mode == "off":
        typer.echo(ctx.get_help())
        typer.echo("Error: interactive mode is disabled (mode=off).", err=True)
        raise typer.Exit(code=2)

    if not _can_interact():
        typer.echo(ctx.get_help())
        typer.echo("Error: command selection requires an interactive terminal.", err=True)
        raise typer.Exit(code=2)

    _run_command_shell(ctx, mode=local_mode, tasks_root=tasks_root)


@app.command("init")
def init_cmd(
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Initialize .tasks directory layout."""

    def _inner() -> None:
        svc = _service(tasks_root, init=True)
        svc.ensure_layout()

        selected_mode = _normalize_mode(mode)
        if selected_mode is None:
            selected_mode = _prompt_init_mode() if _can_interact() else storage.DEFAULT_INTERACTIVE_MODE

        created = storage.write_default_config_if_missing(svc.tasks_root, mode=selected_mode)
        typer.echo(f"Initialized tasks root: {svc.tasks_root}")
        cfg = storage.config_path(svc.tasks_root)
        if created:
            typer.echo(f"Created config: {cfg} (interactive_mode={selected_mode})")
        else:
            typer.echo(f"Using existing config: {cfg}")

    _run_and_handle(_inner)


@app.command("create")
def create_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Unique kebab-case task name")] = None,
    priority: Annotated[str, typer.Option("--priority")] = "p2",
    effort: Annotated[str, typer.Option("--effort")] = "m",
    owner: Annotated[str | None, typer.Option("--owner")] = None,
    tag: Annotated[list[str], typer.Option("--tag", help="Can be repeated")] = [],
    depends_on: Annotated[list[str], typer.Option("--depends-on", help="Task name or task_id")] = [],
    summary: Annotated[str, typer.Option("--summary")] = "",
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Create a task in todo."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)

        open_form = task_name is None and _can_interact_in_mode(local_mode)
        if task_name is None and not open_form:
            raise TaskValidationError("task_name is required in non-interactive mode")

        name = task_name
        local_priority = priority
        local_effort = effort
        local_owner = owner
        local_tags = list(tag)
        local_depends = list(depends_on)
        local_summary = summary

        if open_form:
            dependency_options = _dependency_choices(svc.list_tasks())
            form = create_form(
                default_name=task_name,
                dependency_options=dependency_options,
                mode=local_mode,
            )
            if form is None:
                raise typer.Exit(code=1)
            name = form["task_name"]
            local_priority = form["priority"]
            local_effort = form["effort"]
            local_owner = form["owner"]
            local_tags = form["tags"]
            local_depends = form["depends_on"]
            local_summary = form["summary"]

        if not name:
            raise TaskValidationError("task_name is required")

        task = svc.create_task(
            name,
            summary=local_summary,
            priority=local_priority,
            effort=local_effort,
            owner=local_owner,
            tags=local_tags,
            depends_on=local_depends,
        )
        typer.echo(f"Created: {task.metadata.task_name} ({task.metadata.task_id})")

    _run_and_handle(_inner)


@app.command("start")
def start_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    force: Annotated[bool, typer.Option("--force", help="Ignore unmet dependencies")] = False,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Move task to doing and initialize plan.md."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)
        selector = _select_task_if_missing(svc, task_name, "Select a task to start", mode=local_mode)
        task = svc.start_task(selector, force=force)
        typer.echo(f"Started: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("complete")
def complete_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Mark task completed and move to done."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)
        selector = _select_task_if_missing(svc, task_name, "Select a task to complete", mode=local_mode)
        task = svc.complete_task(selector)
        typer.echo(f"Completed: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("list")
def list_cmd(
    status: Annotated[
        str | None,
        typer.Argument(help="Optional status filter: todo, doing, done", show_default=False),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """List tasks grouped by status and sorted by priority/date."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)
        tasks = svc.list_tasks(status=status)

        interactive_view = status is None and not as_json and _can_interact_in_mode(local_mode)
        if interactive_view:
            show_board(tasks, mode=local_mode)
            return

        unmet_counts = {task.metadata.task_id: svc.dependency_health(task)[0] for task in tasks}
        if as_json:
            typer.echo(render.render_task_list_json(tasks, unmet_counts))
        else:
            typer.echo(render.render_task_list_plain(tasks, unmet_counts))

    _run_and_handle(_inner)


@app.command("view")
def view_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Show a detailed view of one task."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)
        selector = _select_task_if_missing(svc, task_name, "Select a task to view", mode=local_mode)
        task = svc.view_task(selector)
        deps = svc.dependency_rows(task)
        if as_json:
            typer.echo(render.render_task_detail_json(task, deps))
        else:
            typer.echo(render.render_task_detail_plain(task, deps))

    _run_and_handle(_inner)


@app.command("update")
def update_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    priority: Annotated[str | None, typer.Option("--priority")] = None,
    effort: Annotated[str | None, typer.Option("--effort")] = None,
    owner: Annotated[str | None, typer.Option("--owner")] = None,
    tag: Annotated[list[str], typer.Option("--tag")] = [],
    replace_tags: Annotated[bool, typer.Option("--replace-tags")] = False,
    depends_on: Annotated[list[str], typer.Option("--depends-on")] = [],
    clear_depends_on: Annotated[bool, typer.Option("--clear-depends-on")] = False,
    note: Annotated[str | None, typer.Option("--note")] = None,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Update task metadata and append activity."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)

        has_edit_flags = any(
            [
                priority is not None,
                effort is not None,
                owner is not None,
                bool(tag),
                replace_tags,
                bool(depends_on),
                clear_depends_on,
                note is not None,
            ]
        )

        selector = _select_task_if_missing(svc, task_name, "Select a task to update", mode=local_mode)
        selected_task = svc.view_task(selector)

        local_priority = priority
        local_effort = effort
        local_owner = owner
        local_tags = list(tag)
        local_depends = list(depends_on)
        local_replace_depends = clear_depends_on
        local_note = note

        open_form = _can_interact_in_mode(local_mode) and (task_name is None or not has_edit_flags)
        if open_form:
            dependency_options = _dependency_choices(
                svc.list_tasks(),
                exclude_task_id=selected_task.metadata.task_id,
            )
            form = update_form(selected_task, dependency_options=dependency_options, mode=local_mode)
            if form is None:
                raise typer.Exit(code=1)
            local_priority = form.get("priority")
            local_effort = form.get("effort")
            local_owner = form.get("owner")
            local_tags = list(form.get("tags") or [])
            local_depends = list(form.get("depends_on") or [])
            local_replace_depends = bool(form.get("replace_depends_on"))
            local_note = form.get("note")

        task = svc.update_task(
            selector,
            priority=local_priority,
            effort=local_effort,
            owner=local_owner,
            tags=local_tags,
            replace_tags=replace_tags,
            depends_on=local_depends,
            clear_depends_on=clear_depends_on or local_replace_depends,
            note=local_note,
        )
        typer.echo(f"Updated: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("rename")
def rename_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    new_task_name: Annotated[str | None, typer.Argument(help="New unique kebab-case task name")] = None,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Rename a task and update metadata."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)
        selector = _select_task_if_missing(svc, task_name, "Select a task to rename", mode=local_mode)
        target_name = new_task_name
        if not target_name:
            if not _can_interact_in_mode(local_mode):
                raise TaskValidationError("new_task_name is required in non-interactive mode")
            target_name = typer.prompt("new_task_name")
        task = svc.rename_task(selector, target_name)
        typer.echo(f"Renamed: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("delete")
def delete_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    hard: Annotated[bool, typer.Option("--hard", help="Permanently remove task folder")] = False,
    mode: ModeOption = None,
    tasks_root: TasksRootOption = None,
) -> None:
    """Delete a task (soft-delete to trash by default)."""

    def _inner() -> None:
        svc = _service(tasks_root)
        local_mode = _resolve_mode(svc.tasks_root, mode)
        selector = _select_task_if_missing(svc, task_name, "Select a task to delete", mode=local_mode)
        svc.delete_task(selector, hard=hard)
        if hard:
            typer.echo(f"Hard deleted: {selector}")
        else:
            typer.echo(f"Moved to trash: {selector}")

    _run_and_handle(_inner)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
