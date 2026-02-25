"""Business logic for task lifecycle and dependency integrity."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Iterable

from .models import (
    TASK_NAME_RE,
    VALID_EFFORTS,
    VALID_PRIORITIES,
    VALID_STATUSES,
    Task,
    TaskConflictError,
    TaskMetadata,
    TaskNotFoundError,
    TaskValidationError,
)
from . import storage


STATUS_SORT = {"todo": 0, "doing": 1, "completed": 2}
PRIORITY_SORT = {"p0": 0, "p1": 1, "p2": 2, "p3": 3}


def _today() -> str:
    return dt.date.today().isoformat()


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if not tags:
        return []
    return sorted({tag.strip() for tag in tags if tag.strip()})


class TaskService:
    def __init__(self, tasks_root: Path) -> None:
        self.tasks_root = tasks_root.resolve()

    @staticmethod
    def validate_task_name(task_name: str) -> None:
        if not TASK_NAME_RE.fullmatch(task_name):
            raise TaskValidationError(
                "task_name must be kebab-case with lowercase letters, numbers, and hyphens"
            )

    def ensure_layout(self) -> None:
        storage.ensure_layout(self.tasks_root)

    def _load(self, include_trash: bool = False) -> list[Task]:
        return storage.load_tasks(self.tasks_root, include_trash=include_trash)

    def _all_active(self) -> list[Task]:
        return self._load(include_trash=False)

    def _find_by_selector(self, selector: str, include_trash: bool = False) -> Task:
        selector = selector.strip()
        matches: list[Task] = []
        for task in self._load(include_trash=include_trash):
            if selector in {
                task.metadata.task_name,
                task.metadata.task_id,
                task.task_dir.name,
            }:
                matches.append(task)
        if not matches:
            raise TaskNotFoundError(f"Task not found: {selector}")
        if len(matches) > 1:
            names = ", ".join(task.metadata.task_name for task in matches)
            raise TaskConflictError(f"Ambiguous task selector '{selector}': {names}")
        return matches[0]

    def _ensure_unique_task_name(self, task_name: str, ignore_task_id: str | None = None) -> None:
        for task in self._load(include_trash=True):
            if task.metadata.task_name == task_name and task.metadata.task_id != ignore_task_id:
                raise TaskConflictError(f"Task name already exists: {task_name}")

    def _by_id(self, include_trash: bool = False) -> dict[str, Task]:
        return {task.metadata.task_id: task for task in self._load(include_trash=include_trash)}

    def _resolve_dependency_refs(self, refs: Iterable[str]) -> list[str]:
        resolved: list[str] = []
        for ref in refs:
            token = ref.strip()
            if not token:
                continue
            task = self._find_by_selector(token, include_trash=False)
            resolved.append(task.metadata.task_id)
        return sorted(set(resolved))

    def _validate_graph(self, tasks: list[Task]) -> None:
        by_id: dict[str, Task] = {}
        names: set[str] = set()
        for task in tasks:
            task_id = task.metadata.task_id
            if task_id in by_id:
                raise TaskValidationError(f"Duplicate task_id found: {task_id}")
            by_id[task_id] = task
            if task.metadata.task_name in names:
                raise TaskValidationError(f"Duplicate task_name found: {task.metadata.task_name}")
            names.add(task.metadata.task_name)
            if task.metadata.status not in VALID_STATUSES:
                raise TaskValidationError(f"Invalid status for {task.metadata.task_name}")
            if task.metadata.priority not in VALID_PRIORITIES:
                raise TaskValidationError(f"Invalid priority for {task.metadata.task_name}")
            if task.metadata.effort not in VALID_EFFORTS:
                raise TaskValidationError(f"Invalid effort for {task.metadata.task_name}")

        graph: dict[str, list[str]] = {}
        for task in tasks:
            deps = sorted(set(task.metadata.depends_on))
            task.metadata.depends_on = deps
            for dep_id in deps:
                if dep_id == task.metadata.task_id:
                    raise TaskValidationError(
                        f"Task {task.metadata.task_name} cannot depend on itself"
                    )
                if dep_id not in by_id:
                    raise TaskValidationError(
                        f"Task {task.metadata.task_name} has unknown dependency {dep_id}"
                    )
            graph[task.metadata.task_id] = deps

        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str, stack: list[str]) -> None:
            if node in visiting:
                cycle = " -> ".join(stack + [node])
                raise TaskValidationError(f"Dependency cycle detected: {cycle}")
            if node in visited:
                return
            visiting.add(node)
            for dep in graph[node]:
                dfs(dep, stack + [node])
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            dfs(node, [])

        blocked_by: dict[str, list[str]] = {task_id: [] for task_id in graph}
        for task_id, deps in graph.items():
            for dep in deps:
                blocked_by[dep].append(task_id)

        for task in tasks:
            task.metadata.blocked_by = sorted(blocked_by[task.metadata.task_id])

    def _persist_tasks(self, tasks: Iterable[Task]) -> None:
        for task in tasks:
            storage.write_task(task)

    def _snapshot_with(self, updated: Task) -> list[Task]:
        tasks = self._all_active()
        replaced = False
        for idx, task in enumerate(tasks):
            if task.metadata.task_id == updated.metadata.task_id:
                tasks[idx] = updated
                replaced = True
                break
        if not replaced:
            tasks.append(updated)
        return tasks

    def _validate_and_persist_snapshot(self, tasks: list[Task]) -> None:
        self._validate_graph(tasks)
        self._persist_tasks(tasks)

    def _validate_and_persist_all(self) -> None:
        tasks = self._all_active()
        self._validate_and_persist_snapshot(tasks)

    def list_tasks(
        self,
        status: str | None = None,
        include_trash: bool = False,
        *,
        include_tags: Iterable[str] | None = None,
        exclude_tags: Iterable[str] | None = None,
        require_all_tags: bool = False,
        untagged_only: bool = False,
    ) -> list[Task]:
        tasks = self._load(include_trash=include_trash)
        if status:
            desired = "completed" if status == "done" else status
            tasks = [task for task in tasks if task.metadata.status == desired]

        include_tag_set = set(_normalize_tags(include_tags))
        exclude_tag_set = set(_normalize_tags(exclude_tags))
        if include_tag_set or exclude_tag_set or untagged_only:
            filtered: list[Task] = []
            for task in tasks:
                task_tags = set(task.metadata.tags)
                if untagged_only and task_tags:
                    continue
                if include_tag_set:
                    if require_all_tags:
                        if not include_tag_set.issubset(task_tags):
                            continue
                    elif not task_tags.intersection(include_tag_set):
                        continue
                if exclude_tag_set and task_tags.intersection(exclude_tag_set):
                    continue
                filtered.append(task)
            tasks = filtered

        return sorted(
            tasks,
            key=lambda task: (
                STATUS_SORT.get(task.metadata.status, 99),
                PRIORITY_SORT.get(task.metadata.priority, 99),
                task.metadata.date_created,
                task.metadata.task_name,
            ),
        )

    def tag_counts(
        self,
        status: str | None = None,
        *,
        include_untagged: bool = True,
    ) -> list[dict[str, str | int]]:
        counts: dict[str, dict[str, int]] = {}
        for task in self.list_tasks(status=status):
            status_key = "done" if task.metadata.status == "completed" else task.metadata.status
            tags = sorted(set(task.metadata.tags))
            if not tags:
                if not include_untagged:
                    continue
                tags = ["(untagged)"]
            for tag in tags:
                if tag not in counts:
                    counts[tag] = {"total": 0, "todo": 0, "doing": 0, "done": 0}
                counts[tag]["total"] += 1
                counts[tag][status_key] += 1

        rows: list[dict[str, str | int]] = []
        for tag in sorted(counts):
            row = counts[tag]
            rows.append(
                {
                    "tag": tag,
                    "total": row["total"],
                    "todo": row["todo"],
                    "doing": row["doing"],
                    "done": row["done"],
                }
            )
        return rows

    def dependency_health(self, task: Task) -> tuple[int, list[Task]]:
        by_id = self._by_id(include_trash=False)
        missing = []
        for dep_id in task.metadata.depends_on:
            dep = by_id.get(dep_id)
            if dep is None or dep.metadata.status != "completed":
                if dep is not None:
                    missing.append(dep)
        return len(missing), missing

    def create_task(
        self,
        task_name: str,
        *,
        summary: str = "",
        priority: str = "p2",
        effort: str = "m",
        owner: str | None = None,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
    ) -> Task:
        self.validate_task_name(task_name)
        if priority not in VALID_PRIORITIES:
            raise TaskValidationError(f"Invalid priority: {priority}")
        if effort not in VALID_EFFORTS:
            raise TaskValidationError(f"Invalid effort: {effort}")

        self._ensure_unique_task_name(task_name)
        today = _today()
        task_id = storage.next_task_id(self.tasks_root, today)
        dep_ids = self._resolve_dependency_refs(depends_on or [])

        body_summary = summary.strip() or "TODO"
        body = (
            "## Summary\n"
            f"- {body_summary}\n\n"
            "## Acceptance Criteria\n"
            "- TODO\n"
        )

        meta = TaskMetadata(
            task_id=task_id,
            task_name=task_name,
            status="todo",
            date_created=today,
            priority=priority,
            effort=effort,
            owner=owner,
            depends_on=dep_ids,
            blocked_by=[],
            tags=_normalize_tags(tags),
        )
        task_dir = storage.task_dir_path(self.tasks_root, "todo", today, task_name)
        task = Task(metadata=meta, body=body, task_dir=task_dir)

        active = self._all_active() + [task]
        self._validate_graph(active)

        storage.write_task(task)
        task.activity_path.touch(exist_ok=True)
        storage.append_activity(task, "human", "create", f"Task created ({task_id})")

        self._validate_and_persist_all()
        return self._find_by_selector(task_id)

    def start_task(self, selector: str, *, force: bool = False) -> Task:
        task = self._find_by_selector(selector, include_trash=False)
        if task.metadata.status == "completed":
            raise TaskValidationError("Cannot start a completed task")

        by_id = self._by_id(include_trash=False)
        incomplete: list[str] = []
        for dep_id in task.metadata.depends_on:
            dep = by_id.get(dep_id)
            if dep is None or dep.metadata.status != "completed":
                incomplete.append(dep_id)
        if incomplete and not force:
            raise TaskValidationError(
                f"Unmet dependencies: {', '.join(incomplete)}. Use --force to override."
            )

        if not task.metadata.date_started:
            task.metadata.date_started = _today()
        task.metadata.status = "doing"
        task.metadata.date_completed = None

        storage.move_task_dir(task, self.tasks_root, "doing")
        storage.write_task(task)
        if not task.plan_path.exists():
            task.plan_path.write_text(
                "## Plan\n"
                "1. Confirm scope and success criteria\n"
                "2. Implement incrementally\n"
                "3. Validate with tests/checks\n"
                "4. Update activity and complete\n",
                encoding="utf-8",
            )
        storage.append_activity(task, "human", "plan", "Task started")

        self._validate_and_persist_all()
        return self._find_by_selector(task.metadata.task_id)

    def complete_task(self, selector: str) -> Task:
        task = self._find_by_selector(selector, include_trash=False)
        if task.metadata.status == "completed":
            return task

        self._validate_and_persist_all()

        task.metadata.status = "completed"
        task.metadata.date_completed = _today()
        if not task.metadata.date_started:
            task.metadata.date_started = task.metadata.date_created

        storage.move_task_dir(task, self.tasks_root, "completed")
        storage.write_task(task)
        storage.append_activity(task, "human", "complete", "Task marked completed")

        self._validate_and_persist_all()
        return self._find_by_selector(task.metadata.task_id)

    def update_task(
        self,
        selector: str,
        *,
        priority: str | None = None,
        effort: str | None = None,
        owner: str | None = None,
        tags: Iterable[str] | None = None,
        replace_tags: bool = False,
        depends_on: Iterable[str] | None = None,
        clear_depends_on: bool = False,
    ) -> Task:
        task = self._find_by_selector(selector, include_trash=False)

        if priority is not None:
            if priority not in VALID_PRIORITIES:
                raise TaskValidationError(f"Invalid priority: {priority}")
            task.metadata.priority = priority
        if effort is not None:
            if effort not in VALID_EFFORTS:
                raise TaskValidationError(f"Invalid effort: {effort}")
            task.metadata.effort = effort
        if owner is not None:
            task.metadata.owner = owner or None

        if replace_tags:
            task.metadata.tags = _normalize_tags(tags)
        elif tags:
            task.metadata.tags = _normalize_tags([*task.metadata.tags, *list(tags)])

        if clear_depends_on:
            task.metadata.depends_on = []
        if depends_on:
            dep_ids = self._resolve_dependency_refs(depends_on)
            task.metadata.depends_on = sorted(set([*task.metadata.depends_on, *dep_ids]))

        snapshot = self._snapshot_with(task)
        self._validate_and_persist_snapshot(snapshot)
        storage.append_activity(task, "human", "update", "Task metadata updated")
        return self._find_by_selector(task.metadata.task_id)

    def log_activity(self, selector: str, note: str, actor: str = "unknown") -> Task:
        task = self._find_by_selector(selector, include_trash=False)

        cleaned_note = note.strip()
        if not cleaned_note:
            raise TaskValidationError("note is required")

        cleaned_actor = actor.strip() or "unknown"
        storage.append_activity(task, cleaned_actor, "update", cleaned_note)
        return self._find_by_selector(task.metadata.task_id)

    def rename_task(self, selector: str, new_task_name: str) -> Task:
        self.validate_task_name(new_task_name)
        task = self._find_by_selector(selector, include_trash=False)
        self._ensure_unique_task_name(new_task_name, ignore_task_id=task.metadata.task_id)

        task.metadata.task_name = new_task_name
        storage.move_task_dir(task, self.tasks_root, task.metadata.status, target_name=new_task_name)
        storage.write_task(task)
        storage.append_activity(task, "human", "update", f"Task renamed to {new_task_name}")

        # Cross-task consistency pass: validates graph and recomputes blocked_by indexes.
        self._validate_and_persist_all()
        return self._find_by_selector(task.metadata.task_id)

    def delete_task(self, selector: str, *, hard: bool = False) -> None:
        task = self._find_by_selector(selector, include_trash=True)
        if hard:
            storage.hard_delete(task.task_dir)
            return

        storage.append_activity(task, "human", "update", "Task moved to trash")
        target = storage.unique_trash_path(self.tasks_root, task)
        task.task_dir.rename(target)

    def view_task(self, selector: str) -> Task:
        return self._find_by_selector(selector, include_trash=False)

    def dependency_rows(self, task: Task) -> list[tuple[str, str, str]]:
        by_id = self._by_id(include_trash=False)
        rows: list[tuple[str, str, str]] = []
        for dep_id in task.metadata.depends_on:
            dep = by_id.get(dep_id)
            if dep is None:
                rows.append(("missing", dep_id, "unknown"))
                continue
            rows.append((dep.metadata.task_name, dep.metadata.task_id, dep.metadata.status))
        return rows

    def blocked_by_rows(self, task: Task) -> list[tuple[str, str, str]]:
        by_id = self._by_id(include_trash=False)
        rows: list[tuple[str, str, str]] = []
        for blocked_id in task.metadata.blocked_by:
            blocked = by_id.get(blocked_id)
            if blocked is None:
                rows.append(("missing", blocked_id, "unknown"))
                continue
            rows.append((blocked.metadata.task_name, blocked.metadata.task_id, blocked.metadata.status))
        return rows
