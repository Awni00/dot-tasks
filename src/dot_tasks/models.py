"""Core task models and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

VALID_STATUSES = ("todo", "doing", "completed")
TASK_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIELD_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
FIELD_TYPES = ("choice", "date", "text")

STATUS_TO_DIR = {
    "todo": "todo",
    "doing": "doing",
    "completed": "done",
}
DIR_TO_STATUS = {value: key for key, value in STATUS_TO_DIR.items()}

# Frontmatter keys the tool attaches logic to, in the order they are written. Everything
# else in the frontmatter (configured fields and custom keys) lives in TaskMetadata.fields.
FIXED_KEYS = (
    "task_id",
    "task_name",
    "summary",
    "status",
    "date_created",
    "date_started",
    "date_completed",
    "depends_on",
    "tags",
)
# Structural fields change only through dedicated commands, never via key=value.
STRUCTURAL_KEYS = frozenset(FIXED_KEYS) - {"summary"}
# Keys written by older versions that are no longer stored (dropped on rewrite).
RETIRED_KEYS = frozenset({"blocked_by"})
# Names that cannot be used for configured fields.
RESERVED_FIELD_NAMES = frozenset(FIXED_KEYS) | RETIRED_KEYS | {"blocks"}


@dataclass(frozen=True, slots=True)
class FieldDef:
    """A project-configured frontmatter field (see ``settings.fields``)."""

    name: str
    type: str
    values: tuple[str, ...] = ()
    default: str | None = None
    # For choice fields: values are ordered from most to least important and the first
    # ones are highlighted (used by the built-in ``priority``).
    ranked: bool = False


@dataclass(slots=True)
class TaskMetadata:
    task_id: str
    task_name: str
    status: str
    date_created: str
    date_started: str | None = None
    date_completed: str | None = None
    summary: str = ""
    depends_on: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    # Configured field values and custom keys, in frontmatter order.
    fields: dict[str, Any] = field(default_factory=dict)
    # Tasks that depend on this one; computed on load, never stored.
    blocks: list[str] = field(default_factory=list, compare=False)

    def frontmatter(self) -> dict[str, Any]:
        """Return the stored frontmatter: fixed keys in order, then other fields."""
        data: dict[str, Any] = {key: getattr(self, key) for key in FIXED_KEYS}
        for key, value in self.fields.items():
            if key not in data:
                data[key] = value
        return data

    def to_dict(self) -> dict[str, Any]:
        """Frontmatter plus computed values, for JSON output."""
        data = self.frontmatter()
        data["blocks"] = list(self.blocks)
        return data


@dataclass(slots=True)
class Task:
    metadata: TaskMetadata
    body: str
    task_dir: Path

    @property
    def task_md_path(self) -> Path:
        return self.task_dir / "task.md"


@dataclass(slots=True)
class DependencyGraphNode:
    task_id: str
    task_name: str
    status: str
    depends_on: list[str] = field(default_factory=list)
    hidden_depends_on: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DependencyGraph:
    nodes: dict[str, DependencyGraphNode] = field(default_factory=dict)
    root_ids: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    dependent_ids_by_node: dict[str, list[str]] = field(default_factory=dict)
    include_done: bool = False


class TaskError(Exception):
    """Base error for task operations."""


class TaskValidationError(TaskError):
    """Raised when task metadata or graph is invalid."""


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be located."""


class TaskConflictError(TaskError):
    """Raised for collisions and ambiguous actions."""
