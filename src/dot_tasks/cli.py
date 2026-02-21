"""CLI entrypoint for dot-tasks."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Annotated

import typer

from . import render, storage
from .models import TaskError, TaskValidationError
from .service import TaskService
from .tui import choose_task, create_form, show_board, update_form

app = typer.Typer(help="Human-readable and agent-readable task manager")


def _can_interact() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _echo_root_notice(root: Path, multiple_found: bool) -> None:
    typer.echo(f"Using tasks root: {root}", err=True)
    if multiple_found:
        typer.echo("Warning: multiple .tasks roots found; using nearest ancestor.", err=True)


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


def _service(tasks_root: Path | None = None, *, init: bool = False) -> TaskService:
    root = _resolve_init_root(tasks_root) if init else _resolve_existing_root(tasks_root)
    svc = TaskService(root)
    svc.ensure_layout()
    return svc


def _select_task_if_missing(svc: TaskService, task_name: str | None, prompt: str) -> str:
    if task_name:
        return task_name
    tasks = svc.list_tasks()
    if not tasks:
        raise TaskValidationError("No tasks available.")
    if not _can_interact():
        raise TaskValidationError("task_name is required in non-interactive mode")
    selected = choose_task(tasks, title=prompt)
    if not selected:
        raise typer.Exit(code=1)
    return selected


def _run_and_handle(fn) -> None:
    try:
        fn()
    except TaskError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("init")
def init_cmd(
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root", help="Explicit .tasks path")] = None,
) -> None:
    """Initialize .tasks directory layout."""

    def _inner() -> None:
        svc = _service(tasks_root, init=True)
        svc.ensure_layout()
        typer.echo(f"Initialized tasks root: {svc.tasks_root}")

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
    interactive: Annotated[bool, typer.Option("--interactive", help="Open Textual/prompt form")] = False,
    no_interactive: Annotated[bool, typer.Option("--no-interactive", help="Disable prompts/TUI")] = False,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Create a task in todo."""

    def _inner() -> None:
        svc = _service(tasks_root)

        open_form = interactive or (
            not no_interactive
            and _can_interact()
            and (task_name is None or (priority == "p2" and effort == "m" and not owner and not tag and not depends_on and not summary))
        )

        name = task_name
        local_priority = priority
        local_effort = effort
        local_owner = owner
        local_tags = list(tag)
        local_depends = list(depends_on)
        local_summary = summary

        if open_form:
            form = create_form(default_name=task_name)
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
    interactive: Annotated[bool, typer.Option("--interactive")] = False,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Move task to doing and initialize plan.md."""

    def _inner() -> None:
        svc = _service(tasks_root)
        selector = task_name
        if selector is None or interactive:
            selector = _select_task_if_missing(svc, selector, "Select a task to start")
        task = svc.start_task(selector, force=force)
        typer.echo(f"Started: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("complete")
def complete_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    interactive: Annotated[bool, typer.Option("--interactive")] = False,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Mark task completed and move to done."""

    def _inner() -> None:
        svc = _service(tasks_root)
        selector = task_name
        if selector is None or interactive:
            selector = _select_task_if_missing(svc, selector, "Select a task to complete")
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
    interactive: Annotated[bool, typer.Option("--interactive", help="Open board view")] = False,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """List tasks grouped by status and sorted by priority/date."""

    def _inner() -> None:
        svc = _service(tasks_root)
        tasks = svc.list_tasks(status=status)
        if interactive:
            show_board(tasks)
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
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Show a detailed view of one task."""

    def _inner() -> None:
        svc = _service(tasks_root)
        selector = _select_task_if_missing(svc, task_name, "Select a task to view")
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
    interactive: Annotated[bool, typer.Option("--interactive")] = False,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Update task metadata and append activity."""

    def _inner() -> None:
        svc = _service(tasks_root)
        selector = _select_task_if_missing(svc, task_name, "Select a task to update")
        selected_task = svc.view_task(selector)

        local_priority = priority
        local_effort = effort
        local_owner = owner
        local_tags = list(tag)
        local_depends = list(depends_on)
        local_note = note

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
        if interactive or (not has_edit_flags and _can_interact()):
            form = update_form(selected_task)
            if form is None:
                raise typer.Exit(code=1)
            local_priority = form.get("priority")
            local_effort = form.get("effort")
            local_owner = form.get("owner")
            local_tags = list(form.get("tags") or [])
            local_depends = list(form.get("depends_on") or [])
            local_note = form.get("note")

        task = svc.update_task(
            selector,
            priority=local_priority,
            effort=local_effort,
            owner=local_owner,
            tags=local_tags,
            replace_tags=replace_tags,
            depends_on=local_depends,
            clear_depends_on=clear_depends_on,
            note=local_note,
        )
        typer.echo(f"Updated: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("rename")
def rename_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    new_task_name: Annotated[str | None, typer.Argument(help="New unique kebab-case task name")] = None,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Rename a task and update metadata."""

    def _inner() -> None:
        svc = _service(tasks_root)
        selector = _select_task_if_missing(svc, task_name, "Select a task to rename")
        target_name = new_task_name
        if not target_name:
            if not _can_interact():
                raise TaskValidationError("new_task_name is required in non-interactive mode")
            target_name = typer.prompt("new_task_name")
        task = svc.rename_task(selector, target_name)
        typer.echo(f"Renamed: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("delete")
def delete_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    hard: Annotated[bool, typer.Option("--hard", help="Permanently remove task folder")] = False,
    tasks_root: Annotated[Path | None, typer.Option("--tasks-root")] = None,
) -> None:
    """Delete a task (soft-delete to trash by default)."""

    def _inner() -> None:
        svc = _service(tasks_root)
        selector = _select_task_if_missing(svc, task_name, "Select a task to delete")
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
