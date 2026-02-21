"""Textual-powered TUI helpers with prompt fallbacks."""

from __future__ import annotations

import sys
from typing import Any

import typer

from ..models import Task


def _has_textual() -> bool:
    try:
        import textual  # noqa: F401

        return True
    except Exception:
        return False


def choose_task(tasks: list[Task], title: str = "Select task") -> str | None:
    if not tasks:
        return None
    if _has_textual() and sys.stdin.isatty() and sys.stdout.isatty():
        selected = _choose_task_textual(tasks, title=title)
        if selected:
            return selected

    typer.echo(title)
    for idx, task in enumerate(tasks, start=1):
        typer.echo(f"{idx}. {task.metadata.task_name} ({task.metadata.task_id})")
    raw = typer.prompt("Enter number", default="1")
    try:
        index = int(raw)
    except ValueError:
        return None
    if 1 <= index <= len(tasks):
        return tasks[index - 1].metadata.task_name
    return None


def create_form(default_name: str | None = None) -> dict[str, Any] | None:
    if _has_textual() and sys.stdin.isatty() and sys.stdout.isatty():
        result = _create_form_textual(default_name=default_name)
        if result is not None:
            return result

    task_name = typer.prompt("task_name", default=default_name or "")
    priority = typer.prompt("priority (p0|p1|p2|p3)", default="p2")
    effort = typer.prompt("effort (s|m|l|xl)", default="m")
    owner = typer.prompt("owner", default="")
    summary = typer.prompt("summary", default="")
    tags = typer.prompt("tags (comma separated)", default="")
    depends_on = typer.prompt("depends_on task selectors (comma separated)", default="")
    return {
        "task_name": task_name.strip(),
        "priority": priority.strip(),
        "effort": effort.strip(),
        "owner": owner.strip() or None,
        "summary": summary.strip(),
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "depends_on": [d.strip() for d in depends_on.split(",") if d.strip()],
    }


def update_form(task: Task) -> dict[str, Any] | None:
    if _has_textual() and sys.stdin.isatty() and sys.stdout.isatty():
        result = _update_form_textual(task)
        if result is not None:
            return result

    priority = typer.prompt("priority (blank to keep)", default="")
    effort = typer.prompt("effort (blank to keep)", default="")
    owner = typer.prompt("owner (blank to keep)", default=task.metadata.owner or "")
    tags = typer.prompt("add tags (comma separated, blank none)", default="")
    depends_on = typer.prompt("add depends_on selectors (comma separated)", default="")
    note = typer.prompt("update note", default="Task metadata updated")
    return {
        "priority": priority.strip() or None,
        "effort": effort.strip() or None,
        "owner": owner,
        "tags": [t.strip() for t in tags.split(",") if t.strip()],
        "depends_on": [d.strip() for d in depends_on.split(",") if d.strip()],
        "note": note.strip(),
    }


def show_board(tasks: list[Task]) -> None:
    if _has_textual() and sys.stdin.isatty() and sys.stdout.isatty():
        _show_board_textual(tasks)
        return
    typer.echo("Textual board unavailable; showing plain list instead.")
    for task in tasks:
        typer.echo(f"- {task.metadata.status}: {task.metadata.task_name} ({task.metadata.task_id})")


def _choose_task_textual(tasks: list[Task], title: str) -> str | None:
    from textual.app import App, ComposeResult
    from textual.widgets import Footer, Header, OptionList, Static
    from textual.widgets.option_list import Option

    class PickerApp(App[str | None]):
        BINDINGS = [("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(title)
            options = [
                Option(f"{task.metadata.task_name} ({task.metadata.task_id})", id=task.metadata.task_name)
                for task in tasks
            ]
            yield OptionList(*options, id="picker")
            yield Footer()

        def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
            self.exit(str(event.option.id))

        def action_cancel(self) -> None:
            self.exit(None)

    return PickerApp().run()


def _create_form_textual(default_name: str | None = None) -> dict[str, Any] | None:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Input, Static

    class CreateApp(App[dict[str, Any] | None]):
        BINDINGS = [("ctrl+s", "submit", "Submit"), ("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static("Create Task (Ctrl+S to submit)")
            with Vertical():
                yield Input(value=default_name or "", id="task_name", placeholder="task_name")
                yield Input(value="p2", id="priority", placeholder="priority")
                yield Input(value="m", id="effort", placeholder="effort")
                yield Input(value="", id="owner", placeholder="owner")
                yield Input(value="", id="summary", placeholder="summary")
                yield Input(value="", id="tags", placeholder="tags comma-separated")
                yield Input(value="", id="depends_on", placeholder="depends_on selectors")
            yield Footer()

        def action_submit(self) -> None:
            task_name = self.query_one("#task_name", Input).value.strip()
            self.exit(
                {
                    "task_name": task_name,
                    "priority": self.query_one("#priority", Input).value.strip() or "p2",
                    "effort": self.query_one("#effort", Input).value.strip() or "m",
                    "owner": self.query_one("#owner", Input).value.strip() or None,
                    "summary": self.query_one("#summary", Input).value.strip(),
                    "tags": [
                        t.strip()
                        for t in self.query_one("#tags", Input).value.split(",")
                        if t.strip()
                    ],
                    "depends_on": [
                        d.strip()
                        for d in self.query_one("#depends_on", Input).value.split(",")
                        if d.strip()
                    ],
                }
            )

        def action_cancel(self) -> None:
            self.exit(None)

    return CreateApp().run()


def _update_form_textual(task: Task) -> dict[str, Any] | None:
    from textual.app import App, ComposeResult
    from textual.containers import Vertical
    from textual.widgets import Footer, Header, Input, Static

    class UpdateApp(App[dict[str, Any] | None]):
        BINDINGS = [("ctrl+s", "submit", "Submit"), ("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static("Update Task (blank means keep current, Ctrl+S to submit)")
            with Vertical():
                yield Input(value="", id="priority", placeholder="priority")
                yield Input(value="", id="effort", placeholder="effort")
                yield Input(value=task.metadata.owner or "", id="owner", placeholder="owner")
                yield Input(value="", id="tags", placeholder="add tags comma-separated")
                yield Input(value="", id="depends_on", placeholder="add depends_on selectors")
                yield Input(value="Task metadata updated", id="note", placeholder="activity note")
            yield Footer()

        def action_submit(self) -> None:
            self.exit(
                {
                    "priority": self.query_one("#priority", Input).value.strip() or None,
                    "effort": self.query_one("#effort", Input).value.strip() or None,
                    "owner": self.query_one("#owner", Input).value,
                    "tags": [
                        t.strip()
                        for t in self.query_one("#tags", Input).value.split(",")
                        if t.strip()
                    ],
                    "depends_on": [
                        d.strip()
                        for d in self.query_one("#depends_on", Input).value.split(",")
                        if d.strip()
                    ],
                    "note": self.query_one("#note", Input).value.strip(),
                }
            )

        def action_cancel(self) -> None:
            self.exit(None)

    return UpdateApp().run()


def _show_board_textual(tasks: list[Task]) -> None:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import DataTable, Footer, Header, Static

    class BoardApp(App[None]):
        BINDINGS = [("q", "quit", "Quit")]

        def compose(self) -> ComposeResult:
            yield Header()
            with Horizontal():
                yield DataTable(id="table")
                yield Static("Select a task to view details", id="detail")
            yield Footer()

        def on_mount(self) -> None:
            table = self.query_one("#table", DataTable)
            table.add_columns("status", "task_name", "task_id", "priority", "effort")
            for task in tasks:
                table.add_row(
                    task.metadata.status,
                    task.metadata.task_name,
                    task.metadata.task_id,
                    task.metadata.priority,
                    task.metadata.effort,
                    key=task.metadata.task_id,
                )

        def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
            task_id = str(event.row_key)
            selected = next((task for task in tasks if task.metadata.task_id == task_id), None)
            if selected is None:
                return
            detail = self.query_one("#detail", Static)
            detail.update(
                f"{selected.metadata.task_name}\n"
                f"status={selected.metadata.status}\n"
                f"depends_on={', '.join(selected.metadata.depends_on) or '-'}"
            )

    BoardApp().run()
