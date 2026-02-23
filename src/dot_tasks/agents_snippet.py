"""Helpers for loading and upserting AGENTS.md snippets."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Literal


BEGIN_MARKER = "<!-- dot-tasks:begin task-management -->"
END_MARKER = "<!-- dot-tasks:end task-management -->"
RESOURCE_PATH = "resources/agents/task-management-dot-tasks.md"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n")


def _validate_markers(text: str) -> None:
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if begin == -1 or end == -1 or begin > end:
        raise ValueError("Invalid task-management snippet: missing or misordered markers.")


def load_task_management_snippet() -> str:
    """Load canonical markdown section for AGENTS integration."""
    content = resources.files("dot_tasks").joinpath(RESOURCE_PATH).read_text(encoding="utf-8")
    normalized = _normalize_newlines(content).strip("\n")
    _validate_markers(normalized)
    return normalized + "\n"


def resolve_agents_file(project_root: Path, agents_file: Path | None) -> Path:
    target = Path("AGENTS.md") if agents_file is None else agents_file
    if target.is_absolute():
        return target
    return (project_root / target).resolve()


def upsert_task_management_snippet(
    target_file: Path,
    snippet_text: str,
) -> Literal["created", "updated", "appended", "unchanged"]:
    """Insert or replace canonical task-management snippet in target markdown file."""
    block = _normalize_newlines(snippet_text).strip("\n")
    _validate_markers(block)
    block = block + "\n"

    target_file.parent.mkdir(parents=True, exist_ok=True)
    if not target_file.exists():
        target_file.write_text(block, encoding="utf-8")
        return "created"

    existing = _normalize_newlines(target_file.read_text(encoding="utf-8"))
    begin = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)

    if begin != -1 and end != -1 and begin < end:
        end_with_marker = end + len(END_MARKER)
        replacement = existing[:begin] + block.rstrip("\n") + existing[end_with_marker:]
        if not replacement.endswith("\n"):
            replacement = replacement + "\n"
        if replacement == existing:
            return "unchanged"
        target_file.write_text(replacement, encoding="utf-8")
        return "updated"

    if block.rstrip("\n") in existing:
        return "unchanged"

    separator = ""
    if existing and not existing.endswith("\n"):
        separator = "\n"
    if existing.rstrip("\n"):
        separator = separator + "\n"

    appended = existing + separator + block
    target_file.write_text(appended, encoding="utf-8")
    return "appended"
