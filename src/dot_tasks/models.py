"""Core task models and constants."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
import re

VALID_STATUSES = ("todo", "doing", "completed")
VALID_PRIORITIES = ("p0", "p1", "p2", "p3")
VALID_EFFORTS = ("s", "m", "l", "xl")
VALID_SPEC_READINESS = ("unspecified", "rough", "ready", "autonomous")
TASK_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

STATUS_TO_DIR = {
    "todo": "todo",
    "doing": "doing",
    "completed": "done",
}
DIR_TO_STATUS = {value: key for key, value in STATUS_TO_DIR.items()}


@dataclass(slots=True)
class TaskMetadata:
    task_id: str
    task_name: str
    status: str
    date_created: str
    date_started: str | None = None
    date_completed: str | None = None
    priority: str = "p2"
    effort: str = "m"
    spec_readiness: str = "unspecified"
    depends_on: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    owner: str | None = None
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Task:
    metadata: TaskMetadata
    body: str
    task_dir: Path

    @property
    def task_md_path(self) -> Path:
        return self.task_dir / "task.md"

    @property
    def activity_path(self) -> Path:
        return self.task_dir / "activity.md"

    @property
    def plan_path(self) -> Path:
        return self.task_dir / "plan.md"


class TaskError(Exception):
    """Base error for task operations."""


class TaskValidationError(TaskError):
    """Raised when task metadata or graph is invalid."""


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be located."""


class TaskConflictError(TaskError):
    """Raised for collisions and ambiguous actions."""
