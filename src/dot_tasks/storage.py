"""Filesystem operations and frontmatter IO for dot-tasks."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import secrets
import shutil
from typing import Any, Callable, Literal

import yaml

from .models import (
    DIR_TO_STATUS,
    FIELD_NAME_RE,
    FIELD_TYPES,
    FIXED_KEYS,
    RESERVED_FIELD_NAMES,
    RETIRED_KEYS,
    STATUS_TO_DIR,
    FieldDef,
    Task,
    TaskConflictError,
    TaskMetadata,
)


DEFAULT_INTERACTIVE_ENABLED = True
DEFAULT_SHOW_BANNER = True
SUPPORTED_SETTINGS_KEYS = {
    "interactive_enabled",
    "show_banner",
    "fields",
    "list_table",
}
# Settings removed in 0.2.0, with what replaces them.
RETIRED_SETTINGS = {
    "due_dates": "list `due_date` in settings.fields to enable due dates",
    "task_body_sections": "put a body template in .tasks/templates/task.md",
}

# Built-in field definitions, referenced by name in settings.fields.
BUILTIN_FIELDS: dict[str, FieldDef] = {
    "priority": FieldDef("priority", "choice", ("p0", "p1", "p2", "p3"), "p2", ranked=True),
    "effort": FieldDef("effort", "choice", ("s", "m", "l", "xl"), "m"),
    "due_date": FieldDef("due_date", "date"),
    "owner": FieldDef("owner", "text"),
}
# Fields used when a config has no settings.fields key.
DEFAULT_FIELD_NAMES = ("priority", "effort", "due_date", "owner")
# Built-in fields preselected by `init` for a new project.
INIT_DEFAULT_FIELD_NAMES = ("priority", "effort", "due_date")

# List columns that are always available; configured fields are available too.
FIXED_LIST_COLUMNS = (
    "task_name",
    "task_id",
    "status",
    "summary",
    "deps",
    "created",
    "completed",
)
FIXED_LIST_COLUMN_WIDTHS: dict[str, int] = {
    "task_name": 32,
    "task_id": 15,
    "status": 10,
    "summary": 48,
    "deps": 12,
    "created": 10,
    "completed": 12,
}
TASK_ID_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
TASK_ID_SUFFIX_LEN = 4


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


STARTER_README = """\
# Task workflow

How this project tracks work with dot-tasks. Agents are pointed here from AGENTS.md /
CLAUDE.md and the dot-tasks skill, so keep it short.

## When to create a task
- TODO: e.g. work spanning sessions or needing a record.

## Files in a task folder
- `task.md`: metadata (changed only through dot-tasks commands) and the task description
  (edit directly).
- TODO: other files tasks keep, e.g. `plan.md`, `sessions/<date>-<id>.md`.
- Templates for task files, if any: `.tasks/templates/`.

## Wrapping up a session
- TODO: what to record before ending a work session.

## Before completing a task
- TODO: what must be filled in before `dot-tasks complete`.

## Tags
- TODO: project-specific tags and their meaning.

## Referring to tasks
- Cite tasks by name or id, never by folder path (folders move with status).
  `dot-tasks path <task>` resolves one.
"""


def workflow_doc_path(tasks_root: Path) -> Path:
    return tasks_root / "README.md"


def write_starter_readme_if_missing(tasks_root: Path) -> bool:
    """Write the starter workflow doc unless `.tasks/README.md` already exists."""
    path = workflow_doc_path(tasks_root)
    if path.exists():
        return False
    path.write_text(STARTER_README, encoding="utf-8")
    return True


def config_path(tasks_root: Path) -> Path:
    return tasks_root / "config.yaml"


def field_column_width(field_def: FieldDef) -> int:
    if field_def.type == "date":
        return 10
    if field_def.type == "choice":
        return max([len(field_def.name), *(len(value) for value in field_def.values)])
    return 16


def column_default_widths(field_defs: list[FieldDef]) -> dict[str, int]:
    widths = dict(FIXED_LIST_COLUMN_WIDTHS)
    for field_def in field_defs:
        widths[field_def.name] = field_column_width(field_def)
    return widths


def supported_list_columns(field_defs: list[FieldDef]) -> list[str]:
    names = list(FIXED_LIST_COLUMNS)
    names.extend(field_def.name for field_def in field_defs if field_def.name not in names)
    return names


def default_list_column_names(field_defs: list[FieldDef]) -> list[str]:
    """task_name, the configured choice/date fields, created, deps."""
    names = ["task_name"]
    names.extend(field_def.name for field_def in field_defs if field_def.type != "text")
    names.extend(["created", "deps"])
    return names


def default_list_table_columns(field_defs: list[FieldDef]) -> list[dict[str, int | str]]:
    widths = column_default_widths(field_defs)
    return [{"name": name, "width": widths[name]} for name in default_list_column_names(field_defs)]


def list_column_names(columns: list[dict[str, int | str]]) -> list[str]:
    return [str(column["name"]) for column in columns]


def apply_done_list_defaults(
    columns: list[dict[str, int | str]],
    field_defs: list[FieldDef],
) -> list[dict[str, int | str]]:
    """For the default column set, show `completed` instead of `deps` for done tasks."""
    names = list_column_names(columns)
    if "completed" in names or names != default_list_column_names(field_defs):
        return columns
    width = FIXED_LIST_COLUMN_WIDTHS["completed"]
    return [
        {"name": "completed", "width": width} if str(column["name"]) == "deps" else column
        for column in columns
    ]


def build_managed_settings(
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
    fields: list[Any] | None = None,
) -> dict[str, Any]:
    """Settings that `init` manages. *fields* holds settings.fields entries as written."""
    field_entries = list(fields) if fields is not None else list(INIT_DEFAULT_FIELD_NAMES)
    field_defs = parse_field_entries(field_entries)
    columns = list_columns if list_columns is not None else default_list_table_columns(field_defs)
    return {
        "interactive_enabled": interactive_enabled,
        "show_banner": show_banner,
        "fields": field_entries,
        "list_table": {
            "columns": [{"name": str(column["name"]), "width": int(column["width"])} for column in columns],
        },
    }


def default_config(
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
    fields: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "settings": build_managed_settings(
            interactive_enabled,
            list_columns,
            show_banner=show_banner,
            fields=fields,
        )
    }


def merge_managed_config(
    existing_config: dict[str, Any],
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
    fields: list[Any] | None = None,
) -> dict[str, Any]:
    """Overwrite only the managed settings; keep every other key; drop retired settings.

    When *fields* is None the existing settings.fields (if any) is kept as written.
    """
    merged = dict(existing_config) if isinstance(existing_config, dict) else {}
    existing_settings = merged.get("settings", {})
    settings = dict(existing_settings) if isinstance(existing_settings, dict) else {}
    if fields is None and isinstance(settings.get("fields"), list):
        fields = list(settings["fields"])
    settings.update(
        build_managed_settings(
            interactive_enabled,
            list_columns,
            show_banner=show_banner,
            fields=fields,
        )
    )
    for key in RETIRED_SETTINGS:
        settings.pop(key, None)
    merged["settings"] = settings
    return merged


def write_config(tasks_root: Path, payload: dict[str, Any]) -> None:
    path = config_path(tasks_root)
    dumped = yaml.safe_dump(
        payload,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    path.write_text(dumped, encoding="utf-8")


def upsert_init_config(
    tasks_root: Path,
    interactive_enabled: bool = DEFAULT_INTERACTIVE_ENABLED,
    list_columns: list[dict[str, int | str]] | None = None,
    show_banner: bool = DEFAULT_SHOW_BANNER,
    fields: list[Any] | None = None,
) -> Literal["created", "updated"]:
    path = config_path(tasks_root)
    exists = path.exists()
    existing = read_config(tasks_root) if exists else {}
    merged = merge_managed_config(
        existing,
        interactive_enabled=interactive_enabled,
        list_columns=list_columns,
        show_banner=show_banner,
        fields=fields,
    )
    write_config(tasks_root, merged)
    return "updated" if exists else "created"


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


def _read_settings(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
) -> dict[str, Any] | None:
    """Read `settings` from config.yaml, warning about unsupported or invalid keys.

    Returns None when the settings section is invalid (callers fall back to defaults).
    """
    data = read_config(tasks_root, warn=warn)
    for key in data.keys():
        if key != "settings" and warn is not None:
            warn(f"Unsupported config key '{key}' in {config_path(tasks_root)}. Ignoring.")

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        if warn is not None:
            warn(f"Invalid settings section in {config_path(tasks_root)}. Using defaults.")
        return None

    for key in settings.keys():
        if warn is None or key in SUPPORTED_SETTINGS_KEYS:
            continue
        if key in RETIRED_SETTINGS:
            warn(
                f"settings.{key} in {config_path(tasks_root)} is no longer supported: "
                f"{RETIRED_SETTINGS[key]}. Ignoring."
            )
        else:
            warn(f"Unsupported settings key '{key}' in {config_path(tasks_root)}. Ignoring.")
    return settings


def resolve_interactive_enabled(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
) -> bool:
    settings = _read_settings(tasks_root, warn)
    if settings is None:
        return DEFAULT_INTERACTIVE_ENABLED

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
    settings = _read_settings(tasks_root, warn)
    if settings is None:
        return DEFAULT_SHOW_BANNER

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


def _parse_field_entry(
    raw: Any,
    index: int,
    warn: Callable[[str], None],
) -> FieldDef | None:
    where = f"settings.fields[{index}]"
    if isinstance(raw, str):
        builtin = BUILTIN_FIELDS.get(raw)
        if builtin is None:
            known = ", ".join(BUILTIN_FIELDS)
            warn(f"Unknown built-in field '{raw}' at {where} (built-ins: {known}). Ignoring.")
        return builtin
    if not isinstance(raw, dict):
        warn(f"Invalid entry at {where}: expected a field name or a mapping. Ignoring.")
        return None

    name = raw.get("name")
    if not isinstance(name, str) or not FIELD_NAME_RE.fullmatch(name):
        warn(f"Missing or invalid 'name' at {where}. Ignoring.")
        return None
    unknown_keys = set(raw) - {"name", "type", "values", "default", "ranked"}
    for key in sorted(unknown_keys):
        warn(f"Unsupported key '{key}' for field '{name}' at {where}. Ignoring.")

    base = BUILTIN_FIELDS.get(name)
    field_type = raw.get("type", base.type if base else None)
    if field_type not in FIELD_TYPES:
        warn(f"Field '{name}' at {where} needs a type: one of {', '.join(FIELD_TYPES)}. Ignoring.")
        return None

    values: tuple[str, ...] = ()
    ranked = False
    if field_type == "choice":
        raw_values = raw.get("values", list(base.values) if base and base.type == "choice" else None)
        if not isinstance(raw_values, list) or not raw_values:
            warn(f"Choice field '{name}' at {where} needs a non-empty 'values' list. Ignoring.")
            return None
        values = tuple(str(value) for value in raw_values)
        ranked = bool(raw.get("ranked", base.ranked if base and base.type == "choice" else False))
    elif "values" in raw:
        warn(f"'values' only applies to choice fields; ignored for '{name}' at {where}.")

    default = raw.get("default", base.default if base and base.type == field_type else None)
    if default is not None:
        default = str(default)
        if field_type == "choice" and default not in values:
            warn(f"Default '{default}' of field '{name}' is not one of its values. Ignoring default.")
            default = None
        elif field_type == "date":
            try:
                default = normalize_date(default)
            except ValueError:
                warn(f"Default of date field '{name}' must be YYYY-MM-DD. Ignoring default.")
                default = None
    return FieldDef(name, field_type, values, default, ranked)


def parse_field_entries(
    entries: list[Any],
    warn: Callable[[str], None] | None = None,
) -> list[FieldDef]:
    """Parse settings.fields entries (built-in names or mappings) into field definitions."""
    emit = warn or (lambda message: None)
    parsed: list[FieldDef] = []
    seen: set[str] = set()
    for index, raw in enumerate(entries):
        field_def = _parse_field_entry(raw, index, emit)
        if field_def is None:
            continue
        if field_def.name in RESERVED_FIELD_NAMES:
            emit(f"Field name '{field_def.name}' is reserved by dot-tasks. Ignoring.")
            continue
        if field_def.name in seen:
            emit(f"Duplicate field '{field_def.name}' in settings.fields. Keeping the first.")
            continue
        seen.add(field_def.name)
        parsed.append(field_def)
    return parsed


def resolve_fields(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
) -> list[FieldDef]:
    """Configured fields; without settings.fields, the built-in default set."""
    defaults = [BUILTIN_FIELDS[name] for name in DEFAULT_FIELD_NAMES]
    settings = _read_settings(tasks_root, warn)
    if settings is None or "fields" not in settings:
        return defaults
    entries = settings["fields"]
    if entries is None:
        return []
    if not isinstance(entries, list):
        if warn is not None:
            warn(f"Invalid settings.fields in {config_path(tasks_root)}: expected a list. Using defaults.")
        return defaults
    return parse_field_entries(entries, warn)


def normalize_date(value: str) -> str:
    """Return *value* as an ISO date (YYYY-MM-DD); raise ValueError otherwise."""
    cleaned = value.strip()
    if len(cleaned) != 10:
        raise ValueError(value)
    return dt.date.fromisoformat(cleaned).isoformat()


def resolve_list_table_columns(
    tasks_root: Path,
    warn: Callable[[str], None] | None = None,
    field_defs: list[FieldDef] | None = None,
) -> list[dict[str, int | str]]:
    if field_defs is None:
        field_defs = resolve_fields(tasks_root, warn)
    supported = supported_list_columns(field_defs)
    defaults = default_list_table_columns(field_defs)
    settings = _read_settings(tasks_root, warn)
    if settings is None:
        return defaults

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
        if name not in supported:
            if warn is not None:
                warn(
                    f"List column '{name}' in {config_path(tasks_root)} is neither a built-in "
                    "column nor a configured field. Ignoring."
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


def task_template_path(tasks_root: Path) -> Path:
    return tasks_root / "templates" / "task.md"


def migrate_retired_settings(tasks_root: Path) -> list[str]:
    """Migrate 0.1 settings in config.yaml; return messages describing what changed.

    - settings.task_body_sections becomes .tasks/templates/task.md (unless a template exists);
      the Summary section is skipped because the summary now lives in the frontmatter.
    - settings.due_dates is dropped (due dates are enabled by listing `due_date` in fields).
    """
    config = read_config(tasks_root)
    settings = config.get("settings")
    if not isinstance(settings, dict) or not any(key in settings for key in RETIRED_SETTINGS):
        return []
    messages: list[str] = []
    sections = settings.get("task_body_sections")
    template = task_template_path(tasks_root)
    if isinstance(sections, list) and not template.exists():
        parts = []
        for section in sections:
            if not isinstance(section, dict) or not isinstance(section.get("name"), str):
                continue
            if section["name"].strip().lower() == "summary":
                continue
            default = str(section.get("default", "")).strip()
            parts.append(f"## {section['name']}\n{default}\n" if default else f"## {section['name']}\n")
        if parts:
            template.parent.mkdir(parents=True, exist_ok=True)
            template.write_text("\n".join(parts), encoding="utf-8")
            messages.append(f"Moved settings.task_body_sections to body template: {template}")
    due_dates = settings.get("due_dates")
    if (
        isinstance(due_dates, dict)
        and due_dates.get("enabled") is False
        and isinstance(settings.get("fields"), list) is False
    ):
        settings["fields"] = [name for name in DEFAULT_FIELD_NAMES if name != "due_date"]
        messages.append("Replaced settings.due_dates (disabled) with settings.fields without due_date")
    for key in RETIRED_SETTINGS:
        if key in settings:
            settings.pop(key)
            messages.append(f"Removed retired setting settings.{key}")
    config["settings"] = settings
    write_config(tasks_root, config)
    return messages


def read_task_template(tasks_root: Path) -> str:
    """Body for new tasks: .tasks/templates/task.md if it exists, else empty."""
    path = task_template_path(tasks_root)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


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
    dumped = yaml.safe_dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=1_000_000,  # never fold long values (e.g. summaries) across lines
    ).strip()
    body = _normalize_body(body)
    if not body:
        return f"---\n{dumped}\n---\n"
    return f"---\n{dumped}\n---\n\n{body}\n"


_REQUIRED_KEYS = ("task_id", "task_name", "status", "date_created")


def _yaml_dates_to_iso(value: Any) -> Any:
    # YAML parses unquoted dates (e.g. `due_date: 2026-03-01`) as date objects;
    # the rest of the code expects ISO strings.
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


def parse_task(task_dir: Path) -> Task:
    task_md = task_dir / "task.md"
    text = task_md.read_text(encoding="utf-8")
    data, body = split_frontmatter(text)
    data = {str(key): _yaml_dates_to_iso(value) for key, value in data.items()}
    missing_required = [key for key in _REQUIRED_KEYS if data.get(key) in (None, "")]
    if missing_required:
        raise ValueError(f"Task metadata missing keys {missing_required} in {task_md}")

    meta = TaskMetadata(
        task_id=str(data["task_id"]),
        task_name=str(data["task_name"]),
        status=str(data["status"]),
        date_created=str(data["date_created"]),
        date_started=data.get("date_started"),
        date_completed=data.get("date_completed"),
        summary="" if data.get("summary") is None else str(data["summary"]),
        depends_on=[str(item) for item in data.get("depends_on") or []],
        tags=[str(item) for item in data.get("tags") or []],
        # Configured fields and custom keys, kept verbatim and in file order.
        fields={
            key: value
            for key, value in data.items()
            if key not in FIXED_KEYS and key not in RETIRED_KEYS
        },
    )
    return Task(metadata=meta, body=body, task_dir=task_dir)


def write_task(task: Task) -> None:
    task.task_dir.mkdir(parents=True, exist_ok=True)
    text = render_frontmatter(task.metadata.frontmatter(), task.body)
    task.task_md_path.write_text(text, encoding="utf-8")


def write_task_if_changed(task: Task) -> bool:
    """Write *task* unless its file already holds the same metadata and body.

    Avoids rewriting untouched task files, which would otherwise churn their
    formatting (e.g. adding newly introduced keys such as ``due_date: null``).
    """
    if task.task_md_path.exists():
        try:
            on_disk = parse_task(task.task_dir)
        except Exception:
            on_disk = None
        if (
            on_disk is not None
            and on_disk.metadata == task.metadata
            and _normalize_body(on_disk.body) == _normalize_body(task.body)
        ):
            return False
    write_task(task)
    return True


def _normalize_body(body: str) -> str:
    return body.lstrip("\n").rstrip()


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
    suffix = "".join(secrets.choice(TASK_ID_ALPHABET) for _ in range(TASK_ID_SUFFIX_LEN))
    return f"{prefix}{suffix}"


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
