"""Textual-powered TUI helpers with prompt fallbacks."""

from __future__ import annotations

import sys
from typing import Any

import typer

from ..models import Task, VALID_EFFORTS, VALID_PRIORITIES


def _has_textual() -> bool:
    try:
        import textual  # noqa: F401

        return True
    except Exception:
        return False


def _use_textual(mode: str) -> bool:
    return mode == "full" and _has_textual() and sys.stdin.isatty() and sys.stdout.isatty()


def _prompt_single_choice(title: str, options: list[tuple[str, str]], default_value: str) -> str:
    typer.echo(title)
    default_index = 1
    for idx, (_, label) in enumerate(options, start=1):
        typer.echo(f"{idx}. {label}")
        if options[idx - 1][0] == default_value:
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


def choose_task(tasks: list[Task], title: str = "Select task", mode: str = "prompt") -> str | None:
    if not tasks:
        return None
    if _use_textual(mode):
        selected = _choose_task_textual(tasks, title=title)
        if selected:
            return selected

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
    mode: str = "prompt",
) -> str | None:
    if not commands:
        return None
    if _use_textual(mode):
        selected = _choose_command_textual(commands, title=title)
        if selected:
            return selected

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
    mode: str = "prompt",
) -> dict[str, Any] | None:
    dep_options = dependency_options or []
    if _use_textual(mode):
        result = _create_form_textual(default_name=default_name, dependency_options=dep_options)
        if result is not None:
            return result

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
    mode: str = "prompt",
) -> dict[str, Any] | None:
    dep_options = dependency_options or []
    if _use_textual(mode):
        result = _update_form_textual(task, dep_options)
        if result is not None:
            return result

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


def show_board(tasks: list[Task], mode: str = "prompt") -> None:
    if _use_textual(mode):
        _show_board_textual(tasks)
        return
    typer.echo("Interactive board unavailable; showing plain list instead.")
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


def _choose_command_textual(commands: list[tuple[str, str]], title: str) -> str | None:
    from textual.app import App, ComposeResult
    from textual.containers import Container
    from textual.widgets import Footer, Header, OptionList, Static
    from textual.widgets.option_list import Option

    class CommandPickerApp(App[str | None]):
        CSS = """
        Screen {
            background: #11151d;
            align: center middle;
        }
        #card {
            width: 92;
            max-width: 95%;
            border: round #4f8cff;
            background: #171c26;
            padding: 1 2;
        }
        #brand {
            color: #7fb0ff;
            text-style: bold;
            margin-bottom: 1;
        }
        #title {
            margin-bottom: 1;
            text-style: bold;
        }
        #picker {
            height: 12;
            border: round #2d3a52;
            margin-bottom: 1;
        }
        #hint {
            color: #99a3b8;
        }
        """
        BINDINGS = [("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            with Container(id="card"):
                yield Static("dot-tasks", id="brand")
                yield Static(title, id="title")
                options = [Option(f"{name:<8}  {summary}", id=name) for name, summary in commands]
                yield OptionList(*options, id="picker")
                yield Static("Use arrow keys to navigate, Enter to run, Esc to cancel.", id="hint")
            yield Footer()

        def on_mount(self) -> None:
            self.query_one("#picker", OptionList).focus()

        def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
            self.exit(str(event.option.id))

        def action_cancel(self) -> None:
            self.exit(None)

    return CommandPickerApp().run()


def _create_form_textual(
    default_name: str | None = None,
    dependency_options: list[tuple[str, str]] | None = None,
) -> dict[str, Any] | None:
    from textual.app import App, ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Checkbox, Footer, Header, Input, Select, Static

    dep_options = dependency_options or []

    class CreateApp(App[dict[str, Any] | None]):
        BINDINGS = [("ctrl+s", "submit", "Submit"), ("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static("Create Task (Ctrl+S to submit)")
            with VerticalScroll():
                yield Input(value=default_name or "", id="task_name", placeholder="task_name")
                yield Select(
                    [(value, value) for value in VALID_PRIORITIES],
                    value="p2",
                    id="priority",
                    prompt="priority",
                )
                yield Select(
                    [(value, value) for value in VALID_EFFORTS],
                    value="m",
                    id="effort",
                    prompt="effort",
                )
                yield Input(value="", id="owner", placeholder="owner")
                yield Input(value="", id="summary", placeholder="summary")
                yield Input(value="", id="tags", placeholder="tags comma-separated")
                yield Static("depends_on")
                for idx, (_, label) in enumerate(dep_options):
                    yield Checkbox(label, id=f"dep_{idx}")
            yield Footer()

        def action_submit(self) -> None:
            selected_depends: list[str] = []
            for idx, (value, _) in enumerate(dep_options):
                if self.query_one(f"#dep_{idx}", Checkbox).value:
                    selected_depends.append(value)
            self.exit(
                {
                    "task_name": self.query_one("#task_name", Input).value.strip(),
                    "priority": str(self.query_one("#priority", Select).value or "p2"),
                    "effort": str(self.query_one("#effort", Select).value or "m"),
                    "owner": self.query_one("#owner", Input).value.strip() or None,
                    "summary": self.query_one("#summary", Input).value.strip(),
                    "tags": [
                        t.strip()
                        for t in self.query_one("#tags", Input).value.split(",")
                        if t.strip()
                    ],
                    "depends_on": selected_depends,
                }
            )

        def action_cancel(self) -> None:
            self.exit(None)

    return CreateApp().run()


def _update_form_textual(
    task: Task,
    dependency_options: list[tuple[str, str]],
) -> dict[str, Any] | None:
    from textual.app import App, ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Checkbox, Footer, Header, Input, Select, Static

    dep_defaults = set(task.metadata.depends_on)
    keep_value = "__keep__"

    class UpdateApp(App[dict[str, Any] | None]):
        BINDINGS = [("ctrl+s", "submit", "Submit"), ("escape", "cancel", "Cancel")]

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static("Update Task (Ctrl+S to submit)")
            with VerticalScroll():
                yield Select(
                    [(keep_value, "Keep current"), *[(value, value) for value in VALID_PRIORITIES]],
                    value=keep_value,
                    id="priority",
                    prompt="priority",
                )
                yield Select(
                    [(keep_value, "Keep current"), *[(value, value) for value in VALID_EFFORTS]],
                    value=keep_value,
                    id="effort",
                    prompt="effort",
                )
                yield Input(value=task.metadata.owner or "", id="owner", placeholder="owner")
                yield Input(value="", id="tags", placeholder="add tags comma-separated")
                yield Static("depends_on (replaces current selection)")
                for idx, (value, label) in enumerate(dependency_options):
                    yield Checkbox(label, value=value in dep_defaults, id=f"dep_{idx}")
                yield Input(value="Task metadata updated", id="note", placeholder="activity note")
            yield Footer()

        def action_submit(self) -> None:
            selected_depends: list[str] = []
            for idx, (value, _) in enumerate(dependency_options):
                if self.query_one(f"#dep_{idx}", Checkbox).value:
                    selected_depends.append(value)
            priority = str(self.query_one("#priority", Select).value or keep_value)
            effort = str(self.query_one("#effort", Select).value or keep_value)
            self.exit(
                {
                    "priority": None if priority == keep_value else priority,
                    "effort": None if effort == keep_value else effort,
                    "owner": self.query_one("#owner", Input).value,
                    "tags": [
                        t.strip()
                        for t in self.query_one("#tags", Input).value.split(",")
                        if t.strip()
                    ],
                    "depends_on": selected_depends,
                    "replace_depends_on": True,
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
