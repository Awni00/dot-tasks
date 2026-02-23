"""Filesystem operations and frontmatter IO for dot-tasks."""

from __future__ import annotations

from dataclasses import fields
import datetime as dt
from pathlib import Path
import shutil
from typing import Any, Callable

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


def default_config(interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED) -> dict[str, Any]:
    return {
        "settings": {
            "interactive_enabled": interactive_enabled,
        }
    }


def write_default_config_if_missing(
    tasks_root: Path,
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
) -> bool:
    path = config_path(tasks_root)
    if path.exists():
        return False
    payload = yaml.safe_dump(
        default_config(interactive_enabled),
        sort_keys=False,
        default_flow_style=False,
    )
    path.write_text(payload, encoding="utf-8")
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

    supported_settings_keys = {"interactive_enabled"}
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
    missing = [key for key in TASK_META_KEYS if key not in data]
    if missing:
        raise ValueError(f"Task metadata missing keys {missing} in {task_md}")
    meta = TaskMetadata(**{key: data[key] for key in TASK_META_KEYS})
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
