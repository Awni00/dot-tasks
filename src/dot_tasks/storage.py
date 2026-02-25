"""Filesystem operations and frontmatter IO for dot-tasks."""

from __future__ import annotations

from dataclasses import MISSING, fields
import datetime as dt
from pathlib import Path
import shutil
from typing import Any, Callable, Literal

import yaml

from .models import (
    DIR_TO_STATUS,
    STATUS_TO_DIR,
    Task,
    TaskConflictError,
    TaskMetadata,
)


TASK_META_KEYS = [f.name for f in fields(TaskMetadata)]
DEFAULT_INTERACTIVE_ENABLED = True
DEFAULT_SHOW_BANNER = True
LIST_TABLE_COLUMNS_SUPPORTED = (
    "task_name",
    "task_id",
    "status",
    "priority",
    "effort",
    "spec_readiness",
    "deps",
    "created",
)
LIST_TABLE_COLUMN_DEFAULT_WIDTHS: dict[str, int] = {
    "task_name": 32,
    "task_id": 14,
    "status": 10,
    "priority": 8,
    "effort": 6,
    "spec_readiness": 14,
    "deps": 12,
    "created": 10,
}
DEFAULT_LIST_TABLE_COLUMNS: tuple[tuple[str, int], ...] = (
    ("task_name", LIST_TABLE_COLUMN_DEFAULT_WIDTHS["task_name"]),
    ("priority", LIST_TABLE_COLUMN_DEFAULT_WIDTHS["priority"]),
    ("effort", LIST_TABLE_COLUMN_DEFAULT_WIDTHS["effort"]),
    ("deps", LIST_TABLE_COLUMN_DEFAULT_WIDTHS["deps"]),
    ("created", LIST_TABLE_COLUMN_DEFAULT_WIDTHS["created"]),
)


def find_repo_root(start: Path) -> Path | None:
    start = start.resolve()
    for candidate in [start, *start.parents]:
        git_dir = candidate / ".git"
        if git_dir.exists():
            return candidate
    return None


def discover_tasks_roots(start: Path) -> list[Path]:
    start = start.resolve()
    roots: list[Path] = []
    for candidate in [start, *start.parents]:
        tasks_dir = candidate / ".tasks"
        if tasks_dir.is_dir():
            roots.append(tasks_dir)
    return roots


def choose_tasks_root(start: Path) -> tuple[Path | None, bool]:
    roots = discover_tasks_roots(start)
    if not roots:
        return None, False
    return roots[0], len(roots) > 1


def default_init_root(start: Path) -> Path:
    repo_root = find_repo_root(start)
    base = repo_root if repo_root is not None else start.resolve()
    return base / ".tasks"


def ensure_layout(tasks_root: Path) -> None:
    for name in ("todo", "doing", "done", "trash"):
        (tasks_root / name).mkdir(parents=True, exist_ok=True)


def config_path(tasks_root: Path) -> Path:
    return tasks_root / "config.yaml"


def _default_list_table_columns(
    columns: list[dict[str, int | str]] | None = None,
) -> list[dict[str, int | str]]:
    if columns is not None:
        return [{"name": str(column["name"]), "width": int(column["width"])} for column in columns]
    return [{"name": name, "width": width} for name, width in DEFAULT_LIST_TABLE_COLUMNS]


def default_config(
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
) -> dict[str, Any]:
    return {
        "settings": build_managed_settings(
            interactive_enabled,
            list_columns,
            show_banner=show_banner,
        )
    }


def build_managed_settings(
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
) -> dict[str, Any]:
    return {
        "interactive_enabled": interactive_enabled,
        "show_banner": show_banner,
        "list_table": {
            "columns": _default_list_table_columns(list_columns),
        },
    }


def merge_managed_config(
    existing_config: dict[str, Any],
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
) -> dict[str, Any]:
    merged = dict(existing_config) if isinstance(existing_config, dict) else {}
    existing_settings = merged.get("settings", {})
    settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}
    settings.update(
        build_managed_settings(
            interactive_enabled,
            list_columns,
            show_banner=show_banner,
        )
    )
    merged["settings"] = settings
    return merged


def write_config(tasks_root: Path, payload: dict[str, Any]) -> None:
    path = config_path(tasks_root)
    dumped = yaml.safe_dump(
        payload,
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(dumped, encoding="utf-8")


def upsert_init_config(
    tasks_root: Path,
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
) -> Literal["created", "updated"]:
    path = config_path(tasks_root)
    exists = path.exists()
    existing = read_config(tasks_root) if exists else {}
    merged = merge_managed_config(
        existing,
        interactive_enabled=interactive_enabled,
        list_columns=list_columns,
        show_banner=show_banner,
    )
    write_config(tasks_root, merged)
    return "updated" if exists else "created"


def write_default_config_if_missing(
    tasks_root: Path,
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
) -> bool:
    path = config_path(tasks_root)
    if path.exists():
        return False
    write_config(
        tasks_root,
        default_config(
            interactive_enabled,
            list_columns=list_columns,
            show_banner=show_banner,
        ),
    )
    return True


def read_config(tasks_root: Path, warn: Callable[[str], None] | None = None) -> dict[str, Any]:
    path = config_path(tasks_root)
    if not path.exists():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        if warn is not None:
            warn(f"Unable to parse config at {path}. Falling back to defaults.")
        return {}
    if not isinstance(payload, dict):
        if warn is not None:
            warn(f"Invalid config format at {path}. Falling back to defaults.")
        return {}
    return payload


def resolve_interactive_enabled(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
) -> bool:
    data = read_config(tasks_root, warn=warn)
    supported_top_keys = {"settings"}
    for key in data.keys():
        if key not in supported_top_keys and warn is not None:
            warn(f"Unsupported config key '{key}' in {config_path(tasks_root)}. Ignoring.")

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        if warn is not None:
            warn(f"Invalid settings section in {config_path(tasks_root)}. Using defaults.")
        return DEFAULT_INTERACTIVE_ENABLED

    supported_settings_keys = {"interactive_enabled", "show_banner", "list_table"}
    for key in settings.keys():
        if key not in supported_settings_keys and warn is not None:
            warn(f"Unsupported settings key '{key}' in {config_path(tasks_root)}. Ignoring.")

    interactive_enabled = settings.get("interactive_enabled")
    if interactive_enabled is None:
        return DEFAULT_INTERACTIVE_ENABLED
    if not isinstance(interactive_enabled, bool):
        if warn is not None:
            warn(
                f"Invalid settings.interactive_enabled in {config_path(tasks_root)}. "
                f"Using default '{DEFAULT_INTERACTIVE_ENABLED}'."
            )
        return DEFAULT_INTERACTIVE_ENABLED
    return interactive_enabled


def resolve_show_banner(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
) -> bool:
    data = read_config(tasks_root, warn=warn)
    supported_top_keys = {"settings"}
    for key in data.keys():
        if key not in supported_top_keys and warn is not None:
            warn(f"Unsupported config key '{key}' in {config_path(tasks_root)}. Ignoring.")

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        if warn is not None:
            warn(f"Invalid settings section in {config_path(tasks_root)}. Using defaults.")
        return DEFAULT_SHOW_BANNER

    supported_settings_keys = {"interactive_enabled", "show_banner", "list_table"}
    for key in settings.keys():
        if key not in supported_settings_keys and warn is not None:
            warn(f"Unsupported settings key '{key}' in {config_path(tasks_root)}. Ignoring.")

    show_banner = settings.get("show_banner")
    if show_banner is None:
        return DEFAULT_SHOW_BANNER
    if not isinstance(show_banner, bool):
        if warn is not None:
            warn(
                f"Invalid settings.show_banner in {config_path(tasks_root)}. "
                f"Using default '{DEFAULT_SHOW_BANNER}'."
            )
        return DEFAULT_SHOW_BANNER
    return show_banner


def resolve_list_table_columns(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
) -> list[dict[str, int | str]]:
    defaults = _default_list_table_columns()
    data = read_config(tasks_root, warn=warn)
    supported_top_keys = {"settings"}
    for key in data.keys():
        if key not in supported_top_keys and warn is not None:
            warn(f"Unsupported config key '{key}' in {config_path(tasks_root)}. Ignoring.")

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        if warn is not None:
            warn(f"Invalid settings section in {config_path(tasks_root)}. Using defaults.")
        return defaults

    supported_settings_keys = {"interactive_enabled", "show_banner", "list_table"}
    for key in settings.keys():
        if key not in supported_settings_keys and warn is not None:
            warn(f"Unsupported settings key '{key}' in {config_path(tasks_root)}. Ignoring.")

    list_table = settings.get("list_table")
    if list_table is None:
        return defaults
    if not isinstance(list_table, dict):
        if warn is not None:
            warn(
                f"Invalid settings.list_table section in {config_path(tasks_root)}. "
                "Using defaults."
            )
        return defaults

    supported_list_table_keys = {"columns"}
    for key in list_table.keys():
        if key not in supported_list_table_keys and warn is not None:
            warn(
                f"Unsupported settings.list_table key '{key}' in {config_path(tasks_root)}. Ignoring."
            )

    columns = list_table.get("columns")
    if columns is None:
        return defaults
    if not isinstance(columns, list):
        if warn is not None:
            warn(
                f"Invalid settings.list_table.columns in {config_path(tasks_root)}. "
                "Using defaults."
            )
        return defaults

    validated: list[dict[str, int | str]] = []
    seen: set[str] = set()
    for index, raw_column in enumerate(columns, start=1):
        if not isinstance(raw_column, dict):
            if warn is not None:
                warn(
                    f"Invalid column entry at settings.list_table.columns[{index}] in "
                    f"{config_path(tasks_root)}. Ignoring."
                )
            continue

        name = raw_column.get("name")
        width = raw_column.get("width")
        if name not in LIST_TABLE_COLUMNS_SUPPORTED:
            if warn is not None:
                warn(
                    f"Unsupported list column '{name}' in {config_path(tasks_root)}. "
                    "Ignoring."
                )
            continue
        if name in seen:
            if warn is not None:
                warn(
                    f"Duplicate list column '{name}' in {config_path(tasks_root)}. "
                    "Keeping first occurrence."
                )
            continue
        if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
            if warn is not None:
                warn(
                    f"Invalid width for list column '{name}' in {config_path(tasks_root)}. "
                    "Expected a positive integer."
                )
            continue

        validated.append({"name": name, "width": width})
        seen.add(name)

    if validated:
        return validated

    if warn is not None:
        warn(
            f"No valid settings.list_table.columns in {config_path(tasks_root)}. "
            "Using defaults."
        )
    return defaults


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = "\n---\n"
    end = text.find(marker, 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + len(marker) :]
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        data = {}
    return data, body


def render_frontmatter(data: dict[str, Any], body: str) -> str:
    ordered: dict[str, Any] = {}
    for key in TASK_META_KEYS:
        if key in data:
            ordered[key] = data[key]
    dumped = yaml.safe_dump(ordered, sort_keys=False, default_flow_style=False).strip()
    body = body.rstrip() + "\n"
    return f"---\n{dumped}\n---\n\n{body}"


def parse_task(task_dir: Path) -> Task:
    task_md = task_dir / "task.md"
    text = task_md.read_text(encoding="utf-8")
    data, body = split_frontmatter(text)
    payload: dict[str, Any] = {}
    missing_required: list[str] = []
    for field in fields(TaskMetadata):
        if field.name in data:
            payload[field.name] = data[field.name]
            continue
        if field.default is not MISSING:
            payload[field.name] = field.default
            continue
        if field.default_factory is not MISSING:
            payload[field.name] = field.default_factory()
            continue
        missing_required.append(field.name)
    if missing_required:
        raise ValueError(f"Task metadata missing keys {missing_required} in {task_md}")
    meta = TaskMetadata(**payload)
    return Task(metadata=meta, body=body, task_dir=task_dir)


def write_task(task: Task) -> None:
    task.task_dir.mkdir(parents=True, exist_ok=True)
    text = render_frontmatter(task.metadata.to_dict(), task.body)
    task.task_md_path.write_text(text, encoding="utf-8")


def append_activity(task: Task, actor: str, kind: str, note: str, when: dt.datetime | None = None) -> None:
    stamp = (when or dt.datetime.now()).strftime("%Y-%m-%d %H:%M")
    line = f"{stamp} | {actor} | {kind} | {note}\n"
    with task.activity_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def iter_task_dirs(tasks_root: Path, include_trash: bool = False) -> list[Path]:
    dirs: list[Path] = []
    buckets = ["todo", "doing", "done"]
    if include_trash:
        buckets.append("trash")
    for bucket in buckets:
        bucket_dir = tasks_root / bucket
        if not bucket_dir.exists():
            continue
        for child in sorted(bucket_dir.iterdir()):
            if child.is_dir() and (child / "task.md").exists():
                dirs.append(child)
    return dirs


def load_tasks(tasks_root: Path, include_trash: bool = False) -> list[Task]:
    tasks: list[Task] = []
    for task_dir in iter_task_dirs(tasks_root, include_trash=include_trash):
        task = parse_task(task_dir)
        bucket = task_dir.parent.name
        if bucket in DIR_TO_STATUS:
            task.metadata.status = DIR_TO_STATUS[bucket]
        tasks.append(task)
    return tasks


def next_task_id(tasks_root: Path, created_date: str) -> str:
    ymd = created_date.replace("-", "")
    prefix = f"t-{ymd}-"
    max_seq = 0
    for task in load_tasks(tasks_root, include_trash=True):
        task_id = task.metadata.task_id
        if task_id.startswith(prefix):
            try:
                seq = int(task_id.split("-")[-1])
            except ValueError:
                continue
            max_seq = max(max_seq, seq)
    return f"{prefix}{max_seq + 1:03d}"


def make_task_dir_name(created_date: str, task_name: str) -> str:
    return f"{created_date}-{task_name}"


def status_bucket(status: str) -> str:
    if status not in STATUS_TO_DIR:
        raise ValueError(f"Unknown status: {status}")
    return STATUS_TO_DIR[status]


def task_dir_path(tasks_root: Path, status: str, created_date: str, task_name: str) -> Path:
    bucket = status_bucket(status)
    return tasks_root / bucket / make_task_dir_name(created_date, task_name)


def move_task_dir(task: Task, tasks_root: Path, target_status: str, target_name: str | None = None) -> None:
    task_name = target_name or task.metadata.task_name
    target_dir = task_dir_path(tasks_root, target_status, task.metadata.date_created, task_name)
    if target_dir == task.task_dir:
        return
    if target_dir.exists():
        raise TaskConflictError(f"Target task directory already exists: {target_dir}")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    task.task_dir.rename(target_dir)
    task.task_dir = target_dir


def hard_delete(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def unique_trash_path(tasks_root: Path, task: Task) -> Path:
    trash_dir = tasks_root / "trash"
    trash_dir.mkdir(parents=True, exist_ok=True)
    base = make_task_dir_name(task.metadata.date_created, task.metadata.task_name)
    candidate = trash_dir / base
    if not candidate.exists():
        return candidate
    suffix = dt.datetime.now().strftime("%H%M%S")
    return trash_dir / f"{base}-{suffix}"
