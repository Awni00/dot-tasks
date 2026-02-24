"""CLI entrypoint for dot-tasks."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import subprocess
import sys
from typing import Annotated, Literal, Sequence

import click
import typer

from . import agents_snippet, render, storage
from .models import Task, TaskError, TaskValidationError
from .prompt_ui import choose_command, choose_task, create_form, init_config_form, update_form
from .service import TaskService

REPO_ROOT = Path(__file__).resolve().parents[2]
BANNER_PATH = REPO_ROOT / "assets" / "banner.txt"
ACTIVE_CLI_ARGS: tuple[str, ...] | None = None

NoInteractiveOption = Annotated[
    bool,
    typer.Option("--nointeractive", help="Disable interactive prompts for this command"),
]
TasksRootOption = Annotated[Path | None, typer.Option("--tasks-root", help="Explicit .tasks path")]
AgentsFileOption = Annotated[
    Path | None,
    typer.Option("--agents-file", help="Target AGENTS policy file path"),
]
AppendAgentsSnippetOption = Annotated[
    bool,
    typer.Option(
        "--append-agents-snippet",
        help="Append dot-tasks task-management section to AGENTS.md file",
    ),
]


def _can_interact() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _can_prompt(interactive_enabled: bool) -> bool:
    return interactive_enabled and _can_interact()


def _can_render_rich_list_output() -> bool:
    return sys.stdout.isatty()


def _can_render_rich_detail_output() -> bool:
    return sys.stdout.isatty()


def _can_render_banner() -> bool:
    return sys.stdout.isatty()


def _argv_tokens(argv: Sequence[str] | None = None) -> list[str]:
    if argv is not None:
        return list(argv)
    if ACTIVE_CLI_ARGS is not None:
        return list(ACTIVE_CLI_ARGS)
    return sys.argv[1:]


def _argv_requests_json(argv: Sequence[str] | None = None) -> bool:
    return "--json" in _argv_tokens(argv)


@lru_cache(maxsize=1)
def _banner_block() -> str | None:
    try:
        banner_text = BANNER_PATH.read_text(encoding="utf-8")
    except OSError:
        return None

    lines = banner_text.rstrip("\n").splitlines()
    if not lines:
        return None
    return "\n".join(lines)


def _banner_divider_width(block: str) -> int:
    return max((len(line.rstrip()) for line in block.splitlines()), default=1) or 1


def _tasks_root_from_argv(argv: Sequence[str] | None = None) -> Path | None:
    tokens = _argv_tokens(argv)
    raw_root: str | None = None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            break
        if token == "--tasks-root":
            if index + 1 >= len(tokens):
                break
            raw_root = tokens[index + 1]
            index += 2
            continue
        if token.startswith("--tasks-root="):
            raw_root = token.split("=", 1)[1]
        index += 1
    if raw_root is None:
        return None
    root = Path(raw_root).expanduser().resolve()
    if root.exists():
        return root
    return None


def _is_root_only_invocation(argv: Sequence[str] | None = None) -> bool:
    tokens = _argv_tokens(argv)
    flags_without_values = {
        "--nointeractive",
        "--help",
        "-h",
        "--install-completion",
        "--show-completion",
    }
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            return index == len(tokens) - 1
        if token == "--tasks-root":
            index += 2
            continue
        if token.startswith("--tasks-root="):
            index += 1
            continue
        if token in flags_without_values:
            index += 1
            continue
        if token.startswith("-"):
            index += 1
            continue
        return False
    return True


def _root_for_banner_lookup(argv: Sequence[str] | None = None) -> Path | None:
    explicit = _tasks_root_from_argv(argv)
    if explicit is not None:
        return explicit
    root, _ = storage.choose_tasks_root(Path.cwd())
    return root


def _resolve_show_banner_enabled(tasks_root: Path | None) -> bool:
    if tasks_root is None or not tasks_root.exists():
        return storage.DEFAULT_SHOW_BANNER
    return storage.resolve_show_banner(tasks_root)


def _should_render_banner(
    argv: Sequence[str] | None = None,
    *,
    tasks_root: Path | None = None,
) -> bool:
    if not _can_render_banner():
        return False
    if _argv_requests_json(argv):
        return False
    if not _is_root_only_invocation(argv):
        return False
    root = tasks_root if tasks_root is not None else _root_for_banner_lookup(argv)
    if not _resolve_show_banner_enabled(root):
        return False
    return _banner_block() is not None


def _print_banner_divider(width: int) -> None:
    divider = "-" * max(1, width)
    try:
        from rich.text import Text
    except Exception:
        typer.echo(divider)
        return
    _print_rich(Text(divider, style="bright_black"))


def _print_banner(
    argv: Sequence[str] | None = None,
    *,
    tasks_root: Path | None = None,
) -> None:
    block = _banner_block()
    if not block or not _should_render_banner(argv, tasks_root=tasks_root):
        return
    typer.echo(block)
    typer.echo("")
    _print_banner_divider(_banner_divider_width(block))
    typer.echo("")


class DotTasksTyperGroup(typer.core.TyperGroup):
    def main(self, *args, **kwargs):
        global ACTIVE_CLI_ARGS

        cli_args = kwargs.get("args")
        if cli_args is None and args:
            candidate = args[0]
            if isinstance(candidate, (list, tuple)):
                cli_args = [str(token) for token in candidate]
        if cli_args is None:
            ACTIVE_CLI_ARGS = tuple(sys.argv[1:])
        else:
            ACTIVE_CLI_ARGS = tuple(str(token) for token in cli_args)
        try:
            return super().main(*args, **kwargs)
        finally:
            ACTIVE_CLI_ARGS = None

    def get_help(self, ctx: click.Context) -> str:
        if _should_render_banner():
            _print_banner()
        return super().get_help(ctx)


app = typer.Typer(
    cls=DotTasksTyperGroup,
    help="Human-readable and agent-readable task manager",
)


def _print_rich(renderable) -> None:
    from rich.console import Console

    Console().print(renderable)


def _echo_root_notice(root: Path, multiple_found: bool) -> None:
    typer.echo(f"Using tasks root: {root}", err=True)
    if multiple_found:
        typer.echo("Warning: multiple .tasks roots found; using nearest ancestor.", err=True)


def _warn_config(message: str) -> None:
    typer.echo(f"Warning: {message}", err=True)


def _resolve_interactive_enabled(tasks_root: Path | None, nointeractive: bool) -> bool:
    if nointeractive:
        return False
    if tasks_root is None:
        return storage.DEFAULT_INTERACTIVE_ENABLED
    return storage.resolve_interactive_enabled(tasks_root, warn=_warn_config)


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


def _root_for_interactive_lookup(tasks_root: Path | None) -> Path | None:
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
    interactive_enabled: bool,
) -> str:
    if task_name:
        return task_name
    tasks = svc.list_tasks()
    if not tasks:
        raise TaskValidationError("No tasks available.")
    if not _can_prompt(interactive_enabled):
        raise TaskValidationError("task_name is required in non-interactive mode")
    selected = choose_task(tasks, title=prompt)
    if not selected:
        _exit_canceled(1)
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


def _exit_canceled(code: int) -> None:
    typer.echo("Canceled.")
    raise typer.Exit(code=code)


def _append_agents_snippet(
    project_root: Path,
    *,
    agents_file: Path | None,
) -> tuple[str, Path]:
    try:
        snippet = agents_snippet.load_task_management_snippet()
        target = agents_snippet.resolve_agents_file(project_root, agents_file)
        status = agents_snippet.upsert_task_management_snippet(target, snippet)
    except (OSError, ValueError) as exc:
        raise TaskValidationError(f"Unable to append AGENTS snippet: {exc}") from exc
    return status, target


def _prompt_install_skill() -> bool:
    try:
        return bool(typer.confirm("Install dot-tasks skill via npx skills now?", default=False))
    except (click.Abort, EOFError, KeyboardInterrupt):
        # If prompt input is unavailable/canceled, default to skipping install.
        return False


def _install_dot_tasks_skill_via_npx() -> tuple[bool, str]:
    cmd = ["npx", "skills", "add", "Awni00/dot-tasks", "--skill", "dot-tasks"]
    cmd_text = " ".join(cmd)
    try:
        result = subprocess.run(cmd, check=False)
    except FileNotFoundError:
        return (
            False,
            f"`npx` not found. Install Node.js/npm first, then run: {cmd_text}",
        )
    except OSError as exc:
        return (
            False,
            f"Unable to run `{cmd_text}` ({exc}). You can retry manually.",
        )

    if result.returncode == 0:
        return True, "Installed dot-tasks skill from Awni00/dot-tasks."
    return (
        False,
        f"`{cmd_text}` exited with code {result.returncode}. You can retry manually.",
    )


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
    tasks_root: Path | None,
) -> None:
    command = _find_command(command_name)
    if command is None or command.callback is None:
        return
    kwargs: dict[str, object] = {}
    if tasks_root is not None:
        kwargs["tasks_root"] = tasks_root
    try:
        ctx.invoke(command.callback, **kwargs)
    except TypeError:
        fallback: dict[str, object] = {}
        if tasks_root is not None:
            fallback["tasks_root"] = tasks_root
        ctx.invoke(command.callback, **fallback)


def _run_command_picker(ctx: typer.Context, *, tasks_root: Path | None) -> None:
    choices = _command_choices()
    selected = choose_command(choices, title="Select a dot-tasks command")
    if not selected:
        _exit_canceled(0)
    _invoke_from_shell(ctx, selected, tasks_root=tasks_root)


@app.callback(invoke_without_command=True)
def root_callback(
    ctx: typer.Context,
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Open an interactive command picker when no command is provided."""
    if ctx.invoked_subcommand is not None:
        return

    root_for_interactive = _root_for_interactive_lookup(tasks_root)
    interactive_enabled = _resolve_interactive_enabled(root_for_interactive, nointeractive=nointeractive)

    if not interactive_enabled:
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)

    if not _can_interact():
        typer.echo(ctx.get_help())
        typer.echo("Error: command selection requires an interactive terminal.", err=True)
        raise typer.Exit(code=2)

    _print_banner(tasks_root=root_for_interactive)
    _run_command_picker(ctx, tasks_root=tasks_root)


@app.command("init")
def init_cmd(
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
    append_agents_snippet: AppendAgentsSnippetOption = False,
    agents_file: AgentsFileOption = None,
) -> None:
    """Initialize .tasks directory layout."""

    def _inner() -> None:
        svc = _service(tasks_root, init=True)
        svc.ensure_layout()
        cfg_path = storage.config_path(svc.tasks_root)
        interactive_session = _can_interact() and not nointeractive
        should_append_agents_snippet = append_agents_snippet
        selected_agents_file = agents_file

        if nointeractive and agents_file is not None and not append_agents_snippet:
            raise TaskValidationError(
                "--agents-file requires --append-agents-snippet when --nointeractive is used"
            )

        if interactive_session:
            current_interactive_enabled = storage.resolve_interactive_enabled(
                svc.tasks_root,
                warn=_warn_config,
            )
            current_show_banner = storage.resolve_show_banner(
                svc.tasks_root,
                warn=_warn_config,
            )
            current_columns = storage.resolve_list_table_columns(
                svc.tasks_root,
                warn=_warn_config,
            )
            form = init_config_form(
                default_interactive_enabled=current_interactive_enabled,
                default_show_banner=current_show_banner,
                default_list_column_names=[str(column["name"]) for column in current_columns],
                default_append_agents_snippet=append_agents_snippet,
                default_agents_file=str(agents_file) if agents_file is not None else "AGENTS.md",
            )
            if form is None:
                _exit_canceled(1)
            selected_interactive_enabled = bool(form["interactive_enabled"])
            selected_show_banner = bool(form["show_banner"])
            selected_list_columns = form["list_columns"]
            should_append_agents_snippet = bool(form.get("append_agents_snippet", append_agents_snippet))
            selected_agents_value = form.get("agents_file")
            if selected_agents_value:
                selected_agents_file = Path(str(selected_agents_value))
            status = storage.upsert_init_config(
                svc.tasks_root,
                interactive_enabled=selected_interactive_enabled,
                list_columns=selected_list_columns,
                show_banner=selected_show_banner,
            )
            typer.echo(f"Initialized tasks root: {svc.tasks_root}")
            typer.echo(
                f"{'Created' if status == 'created' else 'Updated'} config: {cfg_path} "
                f"(interactive_enabled={selected_interactive_enabled}, "
                f"show_banner={selected_show_banner})"
            )
        else:
            typer.echo(f"Initialized tasks root: {svc.tasks_root}")
            if cfg_path.exists():
                typer.echo(f"Using existing config: {cfg_path}")
            else:
                status = storage.upsert_init_config(svc.tasks_root)
                typer.echo(
                    f"{'Created' if status == 'created' else 'Updated'} config: {cfg_path} "
                    f"(interactive_enabled={storage.DEFAULT_INTERACTIVE_ENABLED}, "
                    f"show_banner={storage.DEFAULT_SHOW_BANNER})"
                )

        if should_append_agents_snippet:
            status, target = _append_agents_snippet(
                svc.tasks_root.parent,
                agents_file=selected_agents_file,
            )
            action = {
                "created": "Created",
                "updated": "Updated",
                "appended": "Appended",
                "unchanged": "Unchanged",
            }[status]
            typer.echo(f"{action} AGENTS snippet: {target}")

        if interactive_session and _prompt_install_skill():
            installed, message = _install_dot_tasks_skill_via_npx()
            if installed:
                typer.echo(message)
            else:
                typer.echo(f"Warning: {message}", err=True)

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
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Create a task in todo."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )

        open_form = task_name is None and _can_prompt(interactive_enabled)
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
            )
            if form is None:
                _exit_canceled(1)
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
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Move task to doing and initialize plan.md."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )
        selector = _select_task_if_missing(
            svc,
            task_name,
            "Select a task to start",
            interactive_enabled=interactive_enabled,
        )
        task = svc.start_task(selector, force=force)
        typer.echo(f"Started: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("complete")
def complete_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Mark task completed and move to done."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )
        selector = _select_task_if_missing(
            svc,
            task_name,
            "Select a task to complete",
            interactive_enabled=interactive_enabled,
        )
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
    tag: Annotated[list[str], typer.Option("--tag", help="Can be repeated")] = [],
    exclude_tag: Annotated[list[str], typer.Option("--exclude-tag", help="Can be repeated")] = [],
    all_tags: Annotated[bool, typer.Option("--all-tags")] = False,
    untagged: Annotated[bool, typer.Option("--untagged")] = False,
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """List tasks grouped by status and sorted by priority/date."""

    def _inner() -> None:
        svc = _service(tasks_root)
        tasks = svc.list_tasks(
            status=status,
            include_tags=tag,
            exclude_tags=exclude_tag,
            require_all_tags=all_tags,
            untagged_only=untagged,
        )
        list_columns = storage.resolve_list_table_columns(svc.tasks_root, warn=_warn_config)

        unmet_counts = {task.metadata.task_id: svc.dependency_health(task)[0] for task in tasks}
        if as_json:
            typer.echo(render.render_task_list_json(tasks, unmet_counts))
        elif _can_render_rich_list_output():
            _print_rich(render.render_task_list_rich(tasks, unmet_counts, list_columns))
        else:
            typer.echo(render.render_task_list_plain(tasks, unmet_counts, list_columns))

    _run_and_handle(_inner)


@app.command("tags")
def tags_cmd(
    status: Annotated[
        str | None,
        typer.Argument(help="Optional status filter: todo, doing, done", show_default=False),
    ] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    sort: Annotated[Literal["count", "name"], typer.Option("--sort")] = "count",
    include_untagged: Annotated[
        bool,
        typer.Option("--include-untagged/--no-include-untagged"),
    ] = True,
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Show task counts grouped by tag."""

    def _inner() -> None:
        _ = nointeractive
        svc = _service(tasks_root)
        rows = svc.tag_counts(status=status, include_untagged=include_untagged)

        if sort == "count":
            rows = sorted(rows, key=lambda row: (-int(row["total"]), str(row["tag"])))
        else:
            rows = sorted(rows, key=lambda row: str(row["tag"]))
        if limit is not None:
            rows = rows[:limit]

        show_status_breakdown = status is None
        if as_json:
            typer.echo(render.render_tag_counts_json(rows))
        elif _can_render_rich_list_output():
            _print_rich(
                render.render_tag_counts_rich(
                    rows,
                    show_status_breakdown=show_status_breakdown,
                )
            )
        else:
            typer.echo(
                render.render_tag_counts_plain(
                    rows,
                    show_status_breakdown=show_status_breakdown,
                )
            )

    _run_and_handle(_inner)


@app.command("view")
def view_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Show a detailed view of one task."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )
        selector = _select_task_if_missing(
            svc,
            task_name,
            "Select a task to view",
            interactive_enabled=interactive_enabled,
        )
        task = svc.view_task(selector)
        deps = svc.dependency_rows(task)
        if as_json:
            typer.echo(render.render_task_detail_json(task, deps))
        else:
            blocked_by = svc.blocked_by_rows(task)
            unmet_count, _ = svc.dependency_health(task)
            if _can_render_rich_detail_output():
                _print_rich(render.render_task_detail_rich(task, deps, blocked_by, unmet_count))
            else:
                typer.echo(render.render_task_detail_plain(task, deps, blocked_by, unmet_count))

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
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Update task metadata and append activity."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )

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

        selector = _select_task_if_missing(
            svc,
            task_name,
            "Select a task to update",
            interactive_enabled=interactive_enabled,
        )
        selected_task = svc.view_task(selector)

        local_priority = priority
        local_effort = effort
        local_owner = owner
        local_tags = list(tag)
        local_depends = list(depends_on)
        local_replace_depends = clear_depends_on
        local_note = note

        open_form = _can_prompt(interactive_enabled) and (task_name is None or not has_edit_flags)
        if open_form:
            dependency_options = _dependency_choices(
                svc.list_tasks(),
                exclude_task_id=selected_task.metadata.task_id,
            )
            form = update_form(selected_task, dependency_options=dependency_options)
            if form is None:
                _exit_canceled(1)
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
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Rename a task and update metadata."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )
        selector = _select_task_if_missing(
            svc,
            task_name,
            "Select a task to rename",
            interactive_enabled=interactive_enabled,
        )
        target_name = new_task_name
        if not target_name:
            if not _can_prompt(interactive_enabled):
                raise TaskValidationError("new_task_name is required in non-interactive mode")
            target_name = typer.prompt("new_task_name")
        task = svc.rename_task(selector, target_name)
        typer.echo(f"Renamed: {task.metadata.task_name}")

    _run_and_handle(_inner)


@app.command("delete")
def delete_cmd(
    task_name: Annotated[str | None, typer.Argument(help="Task name or task_id")] = None,
    hard: Annotated[bool, typer.Option("--hard", help="Permanently remove task folder")] = False,
    nointeractive: NoInteractiveOption = False,
    tasks_root: TasksRootOption = None,
) -> None:
    """Delete a task (soft-delete to trash by default)."""

    def _inner() -> None:
        svc = _service(tasks_root)
        interactive_enabled = _resolve_interactive_enabled(
            svc.tasks_root,
            nointeractive=nointeractive,
        )
        selector = _select_task_if_missing(
            svc,
            task_name,
            "Select a task to delete",
            interactive_enabled=interactive_enabled,
        )
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
