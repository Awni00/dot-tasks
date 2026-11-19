"""Business logic for task lifecycle and dependency integrity."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable, Iterable

from .models import (
    DependencyGraph,
    DependencyGraphNode,
    FIELD_NAME_RE,
    STRUCTURAL_KEYS,
    TASK_NAME_RE,
    VALID_STATUSES,
    FieldDef,
    Task,
    TaskConflictError,
    TaskMetadata,
    TaskNotFoundError,
    TaskValidationError,
)
from . import storage


STATUS_SORT = {"todo": 0, "doing": 1, "completed": 2}


def _parse_status_filter(status: str | None) -> set[str] | None:
    if status is None:
        return None
    value = status.strip()
    if not value:
        raise TaskValidationError("Invalid status filter: empty value")
    if value == "all":
        return None
    tokens = [token.strip() for token in value.split("|")]
    if any(not token for token in tokens):
        raise TaskValidationError(f"Invalid status filter: {status}")
    normalized: set[str] = set()
    for token in tokens:
        if token == "done":
            token = "completed"
        if token == "all":
            raise TaskValidationError("Invalid status filter: 'all' must be used alone")
        if token not in VALID_STATUSES:
            raise TaskValidationError(f"Invalid status filter: {status}")
        normalized.add(token)
    return normalized


def _task_sort_date(task: Task) -> int:
    if task.metadata.status == "completed":
        date_value = task.metadata.date_completed or task.metadata.date_created
    else:
        date_value = task.metadata.date_created
    return int(date_value.replace("-", ""))


def _task_order_key(task: Task) -> tuple[int, int, str]:
    return (
        STATUS_SORT.get(task.metadata.status, 99),
        -_task_sort_date(task),
        task.metadata.task_name,
    )


def _today() -> str:
    return dt.date.today().isoformat()


def parse_assignments(tokens: Iterable[str]) -> dict[str, str | None]:
    """Parse ``key=value`` tokens; ``key=`` means "clear". Later tokens win."""
    values: dict[str, str | None] = {}
    for token in tokens:
        key, sep, value = token.partition("=")
        key = key.strip()
        if not sep or not key:
            raise TaskValidationError(f"Expected key=value, got '{token}'")
        if not FIELD_NAME_RE.fullmatch(key):
            raise TaskValidationError(f"Invalid field name '{key}'")
        values[key] = value if value.strip() else None
    return values


def parse_filters(tokens: Iterable[str]) -> dict[str, list[str | None]]:
    """Parse ``key=value`` list filters; repeating a key accepts any of its values."""
    filters: dict[str, list[str | None]] = {}
    for token in tokens:
        key, value = next(iter(parse_assignments([token]).items()))
        filters.setdefault(key, []).append(value)
    return filters


def scalar_text(value: object) -> str | None:
    """Canonical text of a stored scalar (YAML may load `2` as an int); None stays None."""
    if value is None or isinstance(value, (list, dict)):
        return None if value is None else str(value)
    return str(value)


def check_field_value(field_def: FieldDef, value: object) -> str | None:
    """Return the normalized value, or raise ValueError with a reason."""
    if value is None:
        return None
    if field_def.type == "choice":
        text = str(value)
        if text not in field_def.values:
            raise ValueError(f"'{text}' is not one of {', '.join(field_def.values)}")
        return text
    if field_def.type == "date":
        try:
            return storage.normalize_date(str(value))
        except ValueError:
            raise ValueError(f"'{value}' is not a YYYY-MM-DD date") from None
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ValueError(f"expected text, got {type(value).__name__}")
    return str(value)


def _normalize_tags(tags: Iterable[str] | None) -> list[str]:
    if not tags:
        return []
    return sorted({tag.strip() for tag in tags if tag.strip()})


class TaskService:
    def __init__(
        self,
        tasks_root: Path,
        *,
        warn: Callable[[str], None] | None = None,
    ) -> None:
        self.tasks_root = tasks_root.resolve()
        self.warn = warn
        self._field_defs: list[FieldDef] | None = None
        self._field_values_checked = False

    @property
    def field_defs(self) -> list[FieldDef]:
        """Fields configured in settings.fields (read once per service)."""
        if self._field_defs is None:
            self._field_defs = storage.resolve_fields(self.tasks_root, self.warn)
        return self._field_defs

    def field_def(self, name: str) -> FieldDef | None:
        return next((field_def for field_def in self.field_defs if field_def.name == name), None)

    def _warn_invalid_field_values(self, tasks: Iterable[Task]) -> None:
        """Report stored values that do not fit their configured field; never fail.

        Runs once per service (one command); trashed tasks are not reported.
        """
        if self.warn is None or self._field_values_checked:
            return
        self._field_values_checked = True
        for task in tasks:
            if task.task_dir.parent.name == "trash":
                continue
            for field_def in self.field_defs:
                value = task.metadata.fields.get(field_def.name)
                try:
                    check_field_value(field_def, value)
                except ValueError as exc:
                    self.warn(f"{task.metadata.task_name}: {field_def.name}: {exc}")

    def _set_field_values(self, meta: TaskMetadata, values: dict[str, str | None]) -> None:
        """Apply key=value assignments to *meta*, validating against configured fields."""
        for key, value in values.items():
            if key == "summary":
                meta.summary = (value or "").strip()
                continue
            if key in STRUCTURAL_KEYS:
                hint = {
                    "tags": "use --tag",
                    "depends_on": "use --depends-on",
                    "status": "use start/complete or update --status",
                    "task_name": "use rename",
                }.get(key, "it is managed by dot-tasks")
                raise TaskValidationError(f"Cannot set '{key}' with key=value: {hint}")
            field_def = self.field_def(key)
            if field_def is None:
                configured = ", ".join(["summary", *(f.name for f in self.field_defs)])
                raise TaskValidationError(
                    f"Unknown field '{key}'. Configured fields: {configured} "
                    "(add fields in settings.fields of .tasks/config.yaml)"
                )
            try:
                meta.fields[key] = check_field_value(field_def, value)
            except ValueError as exc:
                raise TaskValidationError(f"Invalid {key}: {exc}") from None

    @staticmethod
    def validate_task_name(task_name: str) -> None:
        if not TASK_NAME_RE.fullmatch(task_name):
            raise TaskValidationError(
                "task_name must be kebab-case with lowercase letters, numbers, and hyphens"
            )

    def validate_new_task_name(self, task_name: str) -> None:
        self.validate_task_name(task_name)
        self._ensure_unique_task_name(task_name)

    def ensure_layout(self) -> None:
        storage.ensure_layout(self.tasks_root)

    def _load(self, include_trash: bool = False) -> list[Task]:
        tasks = storage.load_tasks(self.tasks_root, include_trash=include_trash)
        # `blocks` is derived: the tasks whose depends_on names this task.
        blocks: dict[str, list[str]] = {task.metadata.task_id: [] for task in tasks}
        for task in tasks:
            for dep_id in task.metadata.depends_on:
                if dep_id in blocks:
                    blocks[dep_id].append(task.metadata.task_id)
        for task in tasks:
            task.metadata.blocks = sorted(blocks[task.metadata.task_id])
        self._warn_invalid_field_values(tasks)
        return tasks

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

    def check_circular_dependencies(self, task_id: str | None, extra_depends_on: list[str]) -> None:
        """Validate if adding extra_depends_on creates a cycle."""
        if not extra_depends_on:
            return

        tasks = self._all_active()
        try:
            resolved_extras = self._resolve_dependency_refs(extra_depends_on)
        except TaskNotFoundError:
            return

        graph: dict[str, list[str]] = {}
        for task in tasks:
            tid = task.metadata.task_id
            if tid == task_id:
                graph[tid] = sorted(set([*task.metadata.depends_on, *resolved_extras]))
            else:
                graph[tid] = list(task.metadata.depends_on)

        dummy_id = task_id or "__new_task__"
        if dummy_id not in graph:
            graph[dummy_id] = resolved_extras

        for tid, deps in graph.items():
            for dep in deps:
                if dep == tid:
                    raise TaskValidationError(f"Task cannot depend on itself")

        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str, stack: list[str]) -> None:
            if node in visiting:
                cycle = " -> ".join(stack + [node])
                raise TaskValidationError(f"Dependency cycle detected: {cycle}")
            if node in visited:
                return
            if node not in graph:
                return
            visiting.add(node)
            for dep in graph[node]:
                dfs(dep, stack + [node])
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            dfs(node, [])

    def _persist_tasks(self, tasks: Iterable[Task]) -> None:
        for task in tasks:
            storage.write_task_if_changed(task)

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
        field_filters: dict[str, list[str | None]] | None = None,
    ) -> list[Task]:
        filters = self._normalize_field_filters(field_filters or {})
        tasks = self._load(include_trash=include_trash)
        status_filter = _parse_status_filter(status)
        if status_filter is not None:
            tasks = [task for task in tasks if task.metadata.status in status_filter]
        for key, accepted in filters.items():
            # Same key repeated: any of its values; different keys: all must match.
            tasks = [task for task in tasks if scalar_text(task.metadata.fields.get(key)) in accepted]

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

        return sorted(tasks, key=_task_order_key)

    def _normalize_field_filters(
        self,
        filters: dict[str, list[str | None]],
    ) -> dict[str, list[str | None]]:
        normalized: dict[str, list[str | None]] = {}
        for key, values in filters.items():
            field_def = self.field_def(key)
            if field_def is None:
                configured = ", ".join(f.name for f in self.field_defs) or "(none)"
                raise TaskValidationError(
                    f"Cannot filter on '{key}': not a configured field. Configured fields: {configured}"
                )
            accepted: list[str | None] = []
            for value in values:
                try:
                    accepted.append(check_field_value(field_def, value))
                except ValueError as exc:
                    raise TaskValidationError(f"Invalid filter {key}: {exc}") from None
            normalized[key] = accepted
        return normalized

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

    def build_dependency_graph(self, *, include_done: bool = False) -> DependencyGraph:
        tasks = self.list_tasks(status=None)

        scoped_tasks: list[Task]
        scoped_ids: set[str]
        # Default graph scope: active tasks plus their direct dependencies.
        # Completed dependencies are intentionally shown as terminal leaves to
        # keep the default graph focused on active work.
        if include_done:
            scoped_tasks = list(tasks)
            scoped_ids = {task.metadata.task_id for task in scoped_tasks}
        else:
            active_tasks = [task for task in tasks if task.metadata.status in {"todo", "doing"}]
            active_ids = {task.metadata.task_id for task in active_tasks}
            active_direct_dep_ids = {
                dep_id
                for task in active_tasks
                for dep_id in task.metadata.depends_on
            }
            scoped_ids = active_ids.union(active_direct_dep_ids)
            scoped_tasks = [
                task
                for task in tasks
                if task.metadata.task_id in scoped_ids
            ]

        if not scoped_tasks:
            return DependencyGraph(include_done=include_done)

        scoped_order = {
            task.metadata.task_id: index
            for index, task in enumerate(scoped_tasks)
        }
        all_order = {
            task.metadata.task_id: index
            for index, task in enumerate(sorted(tasks, key=_task_order_key))
        }

        nodes: dict[str, DependencyGraphNode] = {}
        for task in scoped_tasks:
            task_id = task.metadata.task_id
            if not include_done and task.metadata.status == "completed":
                scoped_deps = []
            else:
                scoped_deps = sorted(
                    {dep_id for dep_id in task.metadata.depends_on if dep_id in scoped_ids},
                    key=lambda dep_id: scoped_order[dep_id],
                )
            hidden_deps = sorted(
                {dep_id for dep_id in task.metadata.depends_on if dep_id not in scoped_ids},
                key=lambda dep_id: all_order.get(dep_id, 10**9),
            )
            nodes[task_id] = DependencyGraphNode(
                task_id=task_id,
                task_name=task.metadata.task_name,
                status=task.metadata.status,
                depends_on=scoped_deps,
                hidden_depends_on=hidden_deps,
            )

        dependent_ids_by_node: dict[str, list[str]] = {task_id: [] for task_id in nodes}
        for task_id, node in nodes.items():
            for dep_id in node.depends_on:
                dependent_ids_by_node[dep_id].append(task_id)

        for dep_id in dependent_ids_by_node:
            dependent_ids_by_node[dep_id] = sorted(
                dependent_ids_by_node[dep_id],
                key=lambda task_id: scoped_order[task_id],
            )

        root_ids = sorted(
            [task_id for task_id, dependents in dependent_ids_by_node.items() if not dependents],
            key=lambda task_id: scoped_order[task_id],
        )
        source_ids = sorted(
            [task_id for task_id, node in nodes.items() if not node.depends_on],
            key=lambda task_id: scoped_order[task_id],
        )

        return DependencyGraph(
            nodes=nodes,
            root_ids=root_ids,
            source_ids=source_ids,
            dependent_ids_by_node=dependent_ids_by_node,
            include_done=include_done,
        )

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
        field_values: dict[str, str | None] | None = None,
        tags: Iterable[str] | None = None,
        depends_on: Iterable[str] | None = None,
    ) -> Task:
        """Create a todo task. *field_values* holds key=value assignments (incl. summary)."""
        self.validate_task_name(task_name)
        self._ensure_unique_task_name(task_name)
        today = _today()
        task_id = storage.next_task_id(self.tasks_root, today)
        dep_ids = self._resolve_dependency_refs(depends_on or [])

        meta = TaskMetadata(
            task_id=task_id,
            task_name=task_name,
            status="todo",
            date_created=today,
            depends_on=dep_ids,
            tags=_normalize_tags(tags),
            # Every configured field is written, in config order, with its default.
            fields={field_def.name: field_def.default for field_def in self.field_defs},
        )
        self._set_field_values(meta, field_values or {})
        body = storage.read_task_template(self.tasks_root)
        task_dir = storage.task_dir_path(self.tasks_root, "todo", today, task_name)
        task = Task(metadata=meta, body=body, task_dir=task_dir)

        active = self._all_active() + [task]
        self._validate_graph(active)

        storage.write_task(task)

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

        self._validate_and_persist_all()
        return self._find_by_selector(task.metadata.task_id)

    def update_task(
        self,
        selector: str,
        *,
        status: str | None = None,
        field_values: dict[str, str | None] | None = None,
        tags: Iterable[str] | None = None,
        replace_tags: bool = False,
        depends_on: Iterable[str] | None = None,
        clear_depends_on: bool = False,
    ) -> Task:
        """Update frontmatter. *field_values* holds key=value assignments (incl. summary)."""
        task = self._find_by_selector(selector, include_trash=False)
        if status is not None and status not in VALID_STATUSES:
            raise TaskValidationError(f"Invalid status: {status}")
        # Validate everything (assignments, dependencies, graph) before anything moves on disk.
        self._set_field_values(task.metadata, field_values or {})
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
        self._validate_graph(snapshot)

        if status is not None and status != task.metadata.status:
            storage.move_task_dir(task, self.tasks_root, status)
            task.metadata.status = status
            if status == "todo":
                task.metadata.date_started = None
                task.metadata.date_completed = None
            elif status == "doing":
                if not task.metadata.date_started:
                    task.metadata.date_started = _today()
                task.metadata.date_completed = None
            elif status == "completed":
                if not task.metadata.date_started:
                    task.metadata.date_started = task.metadata.date_created
                if not task.metadata.date_completed:
                    task.metadata.date_completed = _today()

        self._validate_and_persist_snapshot(snapshot)
        return self._find_by_selector(task.metadata.task_id)

    def rename_task(self, selector: str, new_task_name: str) -> Task:
        self.validate_task_name(new_task_name)
        task = self._find_by_selector(selector, include_trash=False)
        self._ensure_unique_task_name(new_task_name, ignore_task_id=task.metadata.task_id)

        task.metadata.task_name = new_task_name
        storage.move_task_dir(task, self.tasks_root, task.metadata.status, target_name=new_task_name)
        storage.write_task(task)

        # Cross-task consistency pass: validates the dependency graph.
        self._validate_and_persist_all()
        return self._find_by_selector(task.metadata.task_id)

    def delete_task(self, selector: str, *, hard: bool = False) -> None:
        task = self._find_by_selector(selector, include_trash=True)
        if hard:
            storage.hard_delete(task.task_dir)
            return

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

    def blocks_rows(self, task: Task) -> list[tuple[str, str, str]]:
        """Tasks that depend on *task*, as (task_name, task_id, status)."""
        by_id = self._by_id(include_trash=False)
        rows: list[tuple[str, str, str]] = []
        for blocked_id in task.metadata.blocks:
            blocked = by_id.get(blocked_id)
            if blocked is None:
                rows.append(("missing", blocked_id, "unknown"))
                continue
            rows.append((blocked.metadata.task_name, blocked.metadata.task_id, blocked.metadata.status))
        return rows
