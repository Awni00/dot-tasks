from __future__ import annotations

from pathlib import Path

from dot_tasks import agents_snippet


def test_load_task_management_snippet_has_markers() -> None:
    snippet = agents_snippet.load_task_management_snippet()
    assert snippet.startswith(agents_snippet.BEGIN_MARKER)
    assert agents_snippet.END_MARKER in snippet


def test_resolve_agents_file_defaults_to_project_agents_md(tmp_path: Path) -> None:
    resolved = agents_snippet.resolve_agents_file(tmp_path, None)
    assert resolved == (tmp_path / "AGENTS.md").resolve()


def test_upsert_task_management_snippet_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    snippet = agents_snippet.load_task_management_snippet()
    status = agents_snippet.upsert_task_management_snippet(target, snippet)
    assert status == "created"
    assert target.exists()
    assert agents_snippet.BEGIN_MARKER in target.read_text(encoding="utf-8")


def test_upsert_task_management_snippet_appends_when_no_markers(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("# Team policy\n", encoding="utf-8")
    snippet = agents_snippet.load_task_management_snippet()
    status = agents_snippet.upsert_task_management_snippet(target, snippet)
    assert status == "appended"
    content = target.read_text(encoding="utf-8")
    assert "# Team policy" in content
    assert agents_snippet.BEGIN_MARKER in content


def test_upsert_task_management_snippet_updates_existing_marked_block(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    old = (
        "preamble\n"
        "<!-- dot-tasks:begin task-management -->\n"
        "old block\n"
        "<!-- dot-tasks:end task-management -->\n"
        "postamble\n"
    )
    target.write_text(old, encoding="utf-8")
    snippet = agents_snippet.load_task_management_snippet()
    status = agents_snippet.upsert_task_management_snippet(target, snippet)
    assert status == "updated"
    content = target.read_text(encoding="utf-8")
    assert "old block" not in content
    assert "preamble" in content
    assert "postamble" in content


def test_upsert_task_management_snippet_reports_unchanged_when_already_present(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    snippet = agents_snippet.load_task_management_snippet()
    target.write_text(snippet, encoding="utf-8")
    status = agents_snippet.upsert_task_management_snippet(target, snippet)
    assert status == "unchanged"


def test_snippet_and_skill_point_agents_to_workflow_doc() -> None:
    # Purpose: since 0.2.0 the CLI never mentions .tasks/README.md, so the AGENTS snippet and
    # the skill are the only pointers to the project's workflow doc; both must state it plainly.
    pointer = "This project's task workflow is in `.tasks/README.md`"
    skill = Path(__file__).resolve().parents[1] / "agent-tools" / "skills" / "dot-tasks" / "SKILL.md"
    assert pointer in agents_snippet.load_task_management_snippet()
    assert pointer in skill.read_text(encoding="utf-8")
