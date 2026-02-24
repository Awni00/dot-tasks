from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner
import yaml

from dot_tasks.cli import app


runner = CliRunner()


@pytest.fixture(autouse=True)
def _disable_skill_install_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._prompt_install_skill", lambda: False)


def _set_test_banner(monkeypatch: pytest.MonkeyPatch) -> str:
    banner = "BANNER"
    monkeypatch.setattr("dot_tasks.cli._banner_block", lambda: banner)
    monkeypatch.setattr("dot_tasks.cli._print_banner_divider", lambda width: print("-" * width))
    return banner


def _read_task_md(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    front = yaml.safe_load(text[4:end])
    body = text[end + 5 :]
    return front, body


def _task_dir(tasks_root: Path, bucket: str, task_name: str) -> Path:
    today = dt.date.today().isoformat()
    return tasks_root / bucket / f"{today}-{task_name}"


def _read_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_init_idempotent(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    r1 = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert r1.exit_code == 0
    r2 = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert r2.exit_code == 0
    assert (root / "todo").is_dir()
    assert (root / "doing").is_dir()
    assert (root / "done").is_dir()
    assert (root / "trash").is_dir()
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is True
    assert cfg["settings"]["show_banner"] is True
    assert cfg["settings"]["list_table"]["columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
        {"name": "deps", "width": 12},
        {"name": "created", "width": 10},
    ]


def test_init_nointeractive_creates_default_config(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    result = runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    assert result.exit_code == 0
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is True
    assert cfg["settings"]["show_banner"] is True
    assert cfg["settings"]["list_table"]["columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
        {"name": "deps", "width": 12},
        {"name": "created", "width": 10},
    ]


def test_init_interactive_uses_form_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": False,
            "show_banner": False,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "status", "width": 10},
                {"name": "task_id", "width": 14},
            ],
        },
    )

    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is False
    assert cfg["settings"]["show_banner"] is False
    assert cfg["settings"]["list_table"]["columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "status", "width": 10},
        {"name": "task_id", "width": 14},
    ]


def test_init_interactive_updates_existing_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": False,
            "show_banner": False,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "priority", "width": 8},
            ],
        },
    )
    runner.invoke(app, ["init", "--tasks-root", str(root)])

    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": True,
            "show_banner": True,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "task_id", "width": 14},
            ],
        },
    )
    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    cfg = _read_config(root / "config.yaml")
    assert cfg["settings"]["interactive_enabled"] is True
    assert cfg["settings"]["show_banner"] is True
    assert cfg["settings"]["list_table"]["columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "task_id", "width": 14},
    ]
    assert "Updated config:" in result.output


def test_init_nointeractive_existing_config_unchanged(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    before = (root / "config.yaml").read_text(encoding="utf-8")

    result = runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    after = (root / "config.yaml").read_text(encoding="utf-8")

    assert result.exit_code == 0
    assert "Using existing config:" in result.output
    assert before == after


def test_init_nointeractive_append_agents_snippet_creates_default_agents_file(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    result = runner.invoke(
        app,
        [
            "init",
            "--tasks-root",
            str(root),
            "--nointeractive",
            "--append-agents-snippet",
        ],
    )
    assert result.exit_code == 0
    agents_file = tmp_path / "AGENTS.md"
    assert agents_file.exists()
    content = agents_file.read_text(encoding="utf-8")
    assert "<!-- dot-tasks:begin task-management -->" in content
    assert "## Task management with `dot-tasks`" in content
    assert "Created AGENTS snippet:" in result.output


def test_init_nointeractive_agents_file_requires_append_flag(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    result = runner.invoke(
        app,
        [
            "init",
            "--tasks-root",
            str(root),
            "--nointeractive",
            "--agents-file",
            "TEAM_AGENTS.md",
        ],
    )
    assert result.exit_code == 1
    assert "--agents-file requires --append-agents-snippet" in result.output


def test_init_nointeractive_append_agents_snippet_custom_file(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    result = runner.invoke(
        app,
        [
            "init",
            "--tasks-root",
            str(root),
            "--nointeractive",
            "--append-agents-snippet",
            "--agents-file",
            "policy/TEAM_AGENTS.md",
        ],
    )
    assert result.exit_code == 0
    agents_file = tmp_path / "policy" / "TEAM_AGENTS.md"
    assert agents_file.exists()
    assert "<!-- dot-tasks:begin task-management -->" in agents_file.read_text(encoding="utf-8")


def test_init_interactive_preserves_unknown_config_keys(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    (root / "config.yaml").write_text(
        (
            "custom_root: keep-me\n"
            "settings:\n"
            "  interactive_enabled: true\n"
            "  show_banner: true\n"
            "  custom_setting: keep-setting\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: task_name\n"
            "        width: 32\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": False,
            "show_banner": False,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "created", "width": 10},
            ],
        },
    )
    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    cfg = _read_config(root / "config.yaml")
    assert cfg["custom_root"] == "keep-me"
    assert cfg["settings"]["custom_setting"] == "keep-setting"
    assert cfg["settings"]["interactive_enabled"] is False
    assert cfg["settings"]["show_banner"] is False
    assert cfg["settings"]["list_table"]["columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "created", "width": 10},
    ]


def test_init_interactive_uses_form_agents_file_when_append_enabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": True,
            "show_banner": True,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "priority", "width": 8},
                {"name": "effort", "width": 6},
                {"name": "deps", "width": 12},
                {"name": "created", "width": 10},
            ],
            "append_agents_snippet": True,
            "agents_file": "TEAM_AGENTS.md",
        },
    )

    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    agents_file = tmp_path / "TEAM_AGENTS.md"
    assert agents_file.exists()
    assert "<!-- dot-tasks:begin task-management -->" in agents_file.read_text(encoding="utf-8")


def test_interactive_init_install_skill_yes_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": True,
            "show_banner": True,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "priority", "width": 8},
                {"name": "effort", "width": 6},
                {"name": "deps", "width": 12},
                {"name": "created", "width": 10},
            ],
            "append_agents_snippet": False,
            "agents_file": None,
        },
    )
    monkeypatch.setattr("dot_tasks.cli._prompt_install_skill", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli._install_dot_tasks_skill_via_npx",
        lambda: (True, "Installed dot-tasks skill from Awni00/dot-tasks."),
    )

    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "Installed dot-tasks skill from Awni00/dot-tasks." in result.output


def test_interactive_init_install_skill_yes_failure_warns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": True,
            "show_banner": True,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "priority", "width": 8},
                {"name": "effort", "width": 6},
                {"name": "deps", "width": 12},
                {"name": "created", "width": 10},
            ],
            "append_agents_snippet": False,
            "agents_file": None,
        },
    )
    monkeypatch.setattr("dot_tasks.cli._prompt_install_skill", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli._install_dot_tasks_skill_via_npx",
        lambda: (False, "mock install failure"),
    )

    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "Warning: mock install failure" in result.output


def test_interactive_init_install_skill_no_skips(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": True,
            "show_banner": True,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "priority", "width": 8},
                {"name": "effort", "width": 6},
                {"name": "deps", "width": 12},
                {"name": "created", "width": 10},
            ],
            "append_agents_snippet": False,
            "agents_file": None,
        },
    )
    monkeypatch.setattr("dot_tasks.cli._prompt_install_skill", lambda: False)
    monkeypatch.setattr(
        "dot_tasks.cli._install_dot_tasks_skill_via_npx",
        lambda: pytest.fail("install helper should not run when prompt answer is no"),
    )

    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    assert result.exit_code == 0


def test_nointeractive_init_never_attempts_skill_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    monkeypatch.setattr("dot_tasks.cli._prompt_install_skill", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli._install_dot_tasks_skill_via_npx",
        lambda: pytest.fail("install helper should not run in --nointeractive mode"),
    )

    result = runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    assert result.exit_code == 0


def test_install_skill_success_prints_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dot_tasks.cli._install_dot_tasks_skill_via_npx",
        lambda: (True, "Installed dot-tasks skill from Awni00/dot-tasks."),
    )
    result = runner.invoke(app, ["install-skill", "--yes"])
    assert result.exit_code == 0
    assert "Installed dot-tasks skill from Awni00/dot-tasks." in result.output


def test_install_skill_failure_exits_nonzero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._install_dot_tasks_skill_via_npx", lambda: (False, "mock install failure"))
    result = runner.invoke(app, ["install-skill", "--yes"])
    assert result.exit_code == 1
    assert "Error: mock install failure" in result.output


def test_install_skill_yes_bypasses_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli._confirm_action",
        lambda prompt, default: pytest.fail("confirm should not run with --yes"),
    )
    monkeypatch.setattr("dot_tasks.cli._install_dot_tasks_skill_via_npx", lambda: (True, "ok"))
    result = runner.invoke(app, ["install-skill", "--yes"])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_install_skill_nointeractive_bypasses_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli._confirm_action",
        lambda prompt, default: pytest.fail("confirm should not run with --nointeractive"),
    )
    monkeypatch.setattr("dot_tasks.cli._install_dot_tasks_skill_via_npx", lambda: (True, "ok"))
    result = runner.invoke(app, ["install-skill", "--nointeractive"])
    assert result.exit_code == 0
    assert "ok" in result.output


def test_install_skill_prompt_decline_cancels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli._confirm_action", lambda prompt, default: False)
    monkeypatch.setattr(
        "dot_tasks.cli._install_dot_tasks_skill_via_npx",
        lambda: pytest.fail("install helper should not run when prompt is declined"),
    )
    result = runner.invoke(app, ["install-skill"])
    assert result.exit_code == 0
    assert "Canceled." in result.output


def test_add_agents_snippet_default_path_creates_agents_md(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    result = runner.invoke(app, ["add-agents-snippet", "--tasks-root", str(root), "--yes"])
    assert result.exit_code == 0
    agents_file = tmp_path / "AGENTS.md"
    assert agents_file.exists()
    content = agents_file.read_text(encoding="utf-8")
    assert "<!-- dot-tasks:begin task-management -->" in content
    assert "Created AGENTS snippet:" in result.output


def test_add_agents_snippet_custom_file_writes_target(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    result = runner.invoke(
        app,
        [
            "add-agents-snippet",
            "--tasks-root",
            str(root),
            "--agents-file",
            "policy/TEAM_AGENTS.md",
            "--yes",
        ],
    )
    assert result.exit_code == 0
    agents_file = tmp_path / "policy" / "TEAM_AGENTS.md"
    assert agents_file.exists()
    assert "<!-- dot-tasks:begin task-management -->" in agents_file.read_text(encoding="utf-8")


def test_add_agents_snippet_second_run_reports_unchanged(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    r1 = runner.invoke(app, ["add-agents-snippet", "--tasks-root", str(root), "--yes"])
    r2 = runner.invoke(app, ["add-agents-snippet", "--tasks-root", str(root), "--yes"])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    assert "Unchanged AGENTS snippet:" in r2.output


def test_add_agents_snippet_yes_bypasses_prompt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli._confirm_action",
        lambda prompt, default: pytest.fail("confirm should not run with --yes"),
    )
    result = runner.invoke(app, ["add-agents-snippet", "--tasks-root", str(root), "--yes"])
    assert result.exit_code == 0


def test_add_agents_snippet_prompt_decline_cancels(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli._confirm_action", lambda prompt, default: False)
    monkeypatch.setattr(
        "dot_tasks.cli._append_agents_snippet",
        lambda project_root, agents_file: pytest.fail("append helper should not run when prompt is declined"),
    )
    result = runner.invoke(app, ["add-agents-snippet", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "Canceled." in result.output


def test_add_agents_snippet_without_tasks_root_fails() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["add-agents-snippet", "--nointeractive"])
        assert result.exit_code == 1
        assert "Run 'dot-tasks init' first." in result.output


def test_create_rejects_duplicate_name(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    r1 = runner.invoke(app, ["create", "a-task", "--tasks-root", str(root)])
    r2 = runner.invoke(app, ["create", "a-task", "--tasks-root", str(root)])
    assert r1.exit_code == 0
    assert r2.exit_code == 1
    assert "already exists" in r2.output


def test_create_writes_task_and_activity(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    result = runner.invoke(
        app,
        [
            "create",
            "write-files",
            "--summary",
            "hello",
            "--priority",
            "p1",
            "--effort",
            "l",
            "--tasks-root",
            str(root),
        ],
    )
    assert result.exit_code == 0
    task_dir = _task_dir(root, "todo", "write-files")
    assert (task_dir / "task.md").exists()
    assert (task_dir / "activity.md").exists()
    meta, _ = _read_task_md(task_dir / "task.md")
    assert meta["task_name"] == "write-files"
    assert meta["priority"] == "p1"
    assert meta["effort"] == "l"


def test_start_blocks_unmet_dependencies_without_force(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep", "--tasks-root", str(root)])
    result = runner.invoke(
        app,
        ["create", "main", "--depends-on", "dep", "--tasks-root", str(root)],
    )
    assert result.exit_code == 0
    blocked = runner.invoke(app, ["start", "main", "--tasks-root", str(root)])
    assert blocked.exit_code == 1
    assert "Unmet dependencies" in blocked.output


def test_start_creates_plan_md(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plan-task", "--tasks-root", str(root)])
    result = runner.invoke(app, ["start", "plan-task", "--tasks-root", str(root)])
    assert result.exit_code == 0
    doing_dir = _task_dir(root, "doing", "plan-task")
    assert (doing_dir / "plan.md").exists()


def test_complete_moves_and_sets_date(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "done-task", "--tasks-root", str(root)])
    result = runner.invoke(app, ["complete", "done-task", "--tasks-root", str(root)])
    assert result.exit_code == 0
    done_dir = _task_dir(root, "done", "done-task")
    meta, _ = _read_task_md(done_dir / "task.md")
    assert meta["status"] == "completed"
    assert meta["date_completed"] == dt.date.today().isoformat()


def test_rename_preserves_dependencies_by_task_id(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "base", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "child", "--depends-on", "base", "--tasks-root", str(root)])

    base_meta, _ = _read_task_md(_task_dir(root, "todo", "base") / "task.md")
    base_id = base_meta["task_id"]

    result = runner.invoke(app, ["rename", "base", "base-renamed", "--tasks-root", str(root)])
    assert result.exit_code == 0

    child_meta, _ = _read_task_md(_task_dir(root, "todo", "child") / "task.md")
    assert child_meta["depends_on"] == [base_id]


def test_view_renders_dependencies_as_name_and_id(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-view", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "task-view", "--depends-on", "dep-view", "--tasks-root", str(root)])
    dep_meta, _ = _read_task_md(_task_dir(root, "todo", "dep-view") / "task.md")
    task_meta, _ = _read_task_md(_task_dir(root, "todo", "task-view") / "task.md")
    dep_id = dep_meta["task_id"]
    task_id = task_meta["task_id"]

    result = runner.invoke(app, ["view", "task-view", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert f"task-view ({task_id})" in result.output
    assert "[todo] [p2] [m] [deps: blocked(1)]" in result.output
    assert f"depends_on: dep-view ({dep_id}) [todo]" in result.output
    assert "blocked_by: -" in result.output


def test_view_renders_blocked_by_as_name_and_id(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-view", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "task-view", "--depends-on", "dep-view", "--tasks-root", str(root)])
    task_meta, _ = _read_task_md(_task_dir(root, "todo", "task-view") / "task.md")
    task_id = task_meta["task_id"]

    result = runner.invoke(app, ["view", "dep-view", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert f"blocked_by: task-view ({task_id}) [todo]" in result.output


def test_view_non_tty_uses_plain_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plain-view", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_detail_output", lambda: False)
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_task_detail_plain",
        lambda task, deps, blocked_by, unmet_count: "PLAIN-DETAIL",
    )
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_task_detail_rich",
        lambda task, deps, blocked_by, unmet_count: pytest.fail("rich detail renderer should not run"),
    )

    result = runner.invoke(app, ["view", "plain-view", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "PLAIN-DETAIL" in result.output


def test_view_tty_uses_rich_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "rich-view", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_detail_output", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_task_detail_plain",
        lambda task, deps, blocked_by, unmet_count: pytest.fail("plain detail renderer should not run"),
    )
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_task_detail_rich",
        lambda task, deps, blocked_by, unmet_count: "RICH-DETAIL",
    )
    captured: list[object] = []
    monkeypatch.setattr("dot_tasks.cli._print_rich", lambda renderable: captured.append(renderable))

    result = runner.invoke(app, ["view", "rich-view", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert captured == ["RICH-DETAIL"]


def test_list_grouped_sorted(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "a", "--priority", "p2", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "b", "--priority", "p0", "--tasks-root", str(root)])
    runner.invoke(app, ["start", "a", "--tasks-root", str(root)])
    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    table_lines = [line for line in lines if "task_name" not in line and not line.startswith("-")]
    joined = "\n".join(table_lines)
    assert "b" in joined
    assert "a" in joined


def test_list_filters_by_tag_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "backend-task", "--tag", "backend", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "frontend-task", "--tag", "frontend", "--tasks-root", str(root)])

    result = runner.invoke(app, ["list", "--tag", "backend", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [item["task_name"] for item in payload] == ["backend-task"]


def test_list_filters_by_any_tags_default_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(
        app,
        ["create", "backend-api-task", "--tag", "backend", "--tag", "api", "--tasks-root", str(root)],
    )
    runner.invoke(app, ["create", "frontend-task", "--tag", "frontend", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "untagged-task", "--tasks-root", str(root)])

    result = runner.invoke(
        app,
        ["list", "--tag", "backend", "--tag", "frontend", "--json", "--tasks-root", str(root)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {item["task_name"] for item in payload} == {"backend-api-task", "frontend-task"}


def test_list_filters_by_all_tags_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(
        app,
        ["create", "backend-api-task", "--tag", "backend", "--tag", "api", "--tasks-root", str(root)],
    )
    runner.invoke(app, ["create", "backend-task", "--tag", "backend", "--tasks-root", str(root)])

    result = runner.invoke(
        app,
        ["list", "--tag", "backend", "--tag", "api", "--all-tags", "--json", "--tasks-root", str(root)],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [item["task_name"] for item in payload] == ["backend-api-task"]


def test_list_excludes_tag_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "wip-task", "--tag", "wip", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "ready-task", "--tag", "ready", "--tasks-root", str(root)])

    result = runner.invoke(app, ["list", "--exclude-tag", "wip", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [item["task_name"] for item in payload] == ["ready-task"]


def test_list_untagged_only_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "untagged-task", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "tagged-task", "--tag", "backend", "--tasks-root", str(root)])

    result = runner.invoke(app, ["list", "--untagged", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [item["task_name"] for item in payload] == ["untagged-task"]


def test_list_tag_filter_with_status_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "backend-doing", "--tag", "backend", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "backend-todo", "--tag", "backend", "--tasks-root", str(root)])
    runner.invoke(app, ["start", "backend-doing", "--tasks-root", str(root)])

    result = runner.invoke(app, ["list", "doing", "--tag", "backend", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [item["task_name"] for item in payload] == ["backend-doing"]


def test_tags_json_includes_counts_and_breakdown(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "backend-doing", "--tag", "backend", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "backend-todo", "--tag", "backend", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "api-todo", "--tag", "api", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "untagged-doing", "--tasks-root", str(root)])
    runner.invoke(app, ["start", "backend-doing", "--tasks-root", str(root)])
    runner.invoke(app, ["start", "untagged-doing", "--tasks-root", str(root)])

    result = runner.invoke(app, ["tags", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    by_tag = {item["tag"]: item for item in payload}
    assert by_tag["backend"] == {"tag": "backend", "total": 2, "todo": 1, "doing": 1, "done": 0}
    assert by_tag["api"] == {"tag": "api", "total": 1, "todo": 1, "doing": 0, "done": 0}
    assert by_tag["(untagged)"] == {"tag": "(untagged)", "total": 1, "todo": 0, "doing": 1, "done": 0}


def test_tags_status_filter_plain_omits_breakdown_columns(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "backend-todo", "--tag", "backend", "--tasks-root", str(root)])

    result = runner.invoke(app, ["tags", "todo", "--tasks-root", str(root)])
    assert result.exit_code == 0
    first_line = next(line for line in result.output.splitlines() if line.strip())
    assert first_line.split() == ["tag", "total"]


def test_tags_sort_name_and_limit_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "a-task", "--tag", "b", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "b-task", "--tag", "a", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "c-task", "--tag", "c", "--tasks-root", str(root)])

    result = runner.invoke(app, ["tags", "--sort", "name", "--limit", "2", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [item["tag"] for item in payload] == ["a", "b"]


def test_tags_no_include_untagged_json(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "untagged-task", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "tagged-task", "--tag", "backend", "--tasks-root", str(root)])

    result = runner.invoke(app, ["tags", "--no-include-untagged", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {item["tag"] for item in payload} == {"backend"}


def test_tags_non_tty_uses_plain_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plain-tags", "--tag", "backend", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: False)
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_tag_counts_plain",
        lambda rows, show_status_breakdown: "PLAIN-TAGS",
    )
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_tag_counts_rich",
        lambda rows, show_status_breakdown: pytest.fail("rich tags renderer should not run"),
    )

    result = runner.invoke(app, ["tags", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "PLAIN-TAGS" in result.output


def test_tags_tty_uses_rich_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "rich-tags", "--tag", "backend", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_tag_counts_rich",
        lambda rows, show_status_breakdown: "RICH-TAGS",
    )
    captured: list[object] = []
    monkeypatch.setattr("dot_tasks.cli._print_rich", lambda renderable: captured.append(renderable))

    result = runner.invoke(app, ["tags", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert captured == ["RICH-TAGS"]


def test_list_non_tty_uses_plain_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plain-view", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: False)
    monkeypatch.setattr("dot_tasks.cli.render.render_task_list_plain", lambda tasks, unmet, columns: "PLAIN-OUT")
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_task_list_rich",
        lambda tasks, unmet, columns: pytest.fail("rich renderer should not run"),
    )

    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "PLAIN-OUT" in result.output


def test_list_tty_uses_rich_renderer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "rich-view", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.render.render_task_list_rich",
        lambda tasks, unmet, columns: "RICH-OUT",
    )
    captured: list[object] = []
    monkeypatch.setattr("dot_tasks.cli._print_rich", lambda renderable: captured.append(renderable))

    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert captured == ["RICH-OUT"]


def test_help_tty_includes_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    banner = _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: True)

    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert result.output.startswith(banner)
    assert "Usage:" in result.output


def test_root_no_command_flow_prints_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    banner = _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: True)
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli.choose_command", lambda commands, title: None)

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert result.output.startswith(banner)
    assert "Canceled." in result.output


def test_subcommand_tty_does_not_print_banner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: True)

    result = runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    assert result.exit_code == 0
    assert "BANNER" not in result.output
    assert "Initialized tasks root:" in result.output


def test_json_output_suppresses_banner_even_in_tty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    runner.invoke(app, ["create", "json-view", "--tasks-root", str(root)])

    _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: True)

    result = runner.invoke(app, ["list", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "BANNER" not in result.output
    assert '"task_name": "json-view"' in result.output


def test_view_json_output_unchanged_shape(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-json-view", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "json-view", "--depends-on", "dep-json-view", "--tasks-root", str(root)])

    result = runner.invoke(app, ["view", "json-view", "--json", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert '"metadata"' in result.output
    assert '"dependencies"' in result.output
    assert '"task_name": "json-view"' in result.output
    assert '"task_name": "dep-json-view"' in result.output
    assert '"body"' in result.output
    assert '"path"' in result.output


def test_subcommand_help_does_not_print_banner(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: True)

    result = runner.invoke(app, ["list", "--help"])
    assert result.exit_code == 0
    assert "BANNER" not in result.output
    assert "Usage:" in result.output


def test_root_help_respects_show_banner_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    cfg = _read_config(root / "config.yaml")
    cfg["settings"]["show_banner"] = False
    (root / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: True)

    result = runner.invoke(app, ["--tasks-root", str(root), "--help"])
    assert result.exit_code == 0
    assert "BANNER" not in result.output
    assert "Usage:" in result.output


def test_non_tty_suppresses_banner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _set_test_banner(monkeypatch)
    monkeypatch.setattr("dot_tasks.cli._can_render_banner", lambda: False)

    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "BANNER" not in result.output
    assert "Usage:" in result.output


def test_list_non_tty_passes_configured_columns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plain-view", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: task_name\n"
            "        width: 20\n"
            "      - name: created\n"
            "        width: 10\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: False)
    captured_columns: list[list[dict[str, int | str]]] = []

    def _fake_plain(tasks, unmet, columns):
        captured_columns.append(columns)
        return "PLAIN-OUT"

    monkeypatch.setattr("dot_tasks.cli.render.render_task_list_plain", _fake_plain)

    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert captured_columns == [[{"name": "task_name", "width": 20}, {"name": "created", "width": 10}]]


def test_list_tty_passes_configured_columns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "rich-view", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: task_name\n"
            "        width: 22\n"
            "      - name: deps\n"
            "        width: 12\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: True)
    captured_columns: list[list[dict[str, int | str]]] = []

    def _fake_rich(tasks, unmet, columns):
        captured_columns.append(columns)
        return "RICH-OUT"

    monkeypatch.setattr("dot_tasks.cli.render.render_task_list_rich", _fake_rich)
    captured: list[object] = []
    monkeypatch.setattr("dot_tasks.cli._print_rich", lambda renderable: captured.append(renderable))

    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert captured == ["RICH-OUT"]
    assert captured_columns == [[{"name": "task_name", "width": 22}, {"name": "deps", "width": 12}]]


def test_list_invalid_column_config_warns_and_uses_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "plain-view", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        (
            "settings:\n"
            "  interactive_enabled: true\n"
            "  list_table:\n"
            "    columns:\n"
            "      - name: not_real\n"
            "        width: 10\n"
            "      - name: task_name\n"
            "        width: 0\n"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("dot_tasks.cli._can_render_rich_list_output", lambda: False)
    captured_columns: list[list[dict[str, int | str]]] = []

    def _fake_plain(tasks, unmet, columns):
        captured_columns.append(columns)
        return "PLAIN-OUT"

    monkeypatch.setattr("dot_tasks.cli.render.render_task_list_plain", _fake_plain)

    result = runner.invoke(app, ["list", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "Warning: No valid settings.list_table.columns" in result.output
    assert captured_columns == [
        [
            {"name": "task_name", "width": 32},
            {"name": "priority", "width": 8},
            {"name": "effort", "width": 6},
            {"name": "deps", "width": 12},
            {"name": "created", "width": 10},
        ]
    ]


def test_subdirectory_discovers_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    root = repo / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "root-task", "--tasks-root", str(root)])

    with runner.isolated_filesystem(temp_dir=str(nested)):
        result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "Using tasks root:" in result.output


def test_delete_soft_and_hard(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "to-trash", "--tasks-root", str(root)])
    soft = runner.invoke(app, ["delete", "to-trash", "--tasks-root", str(root)])
    assert soft.exit_code == 0
    assert any((root / "trash").iterdir())

    runner.invoke(app, ["create", "to-hard", "--tasks-root", str(root)])
    hard = runner.invoke(app, ["delete", "to-hard", "--tasks-root", str(root), "--hard"])
    assert hard.exit_code == 0
    assert not (_task_dir(root, "todo", "to-hard")).exists()


def test_missing_selector_triggers_prompt_picker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "pick-me", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli.choose_task", lambda tasks, title: "pick-me")

    result = runner.invoke(app, ["start", "--tasks-root", str(root)])
    assert result.exit_code == 0
    assert "Started: pick-me" in result.output


def test_no_args_interactive_runs_selected_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.init_config_form",
        lambda **kwargs: {
            "interactive_enabled": True,
            "show_banner": True,
            "list_columns": [
                {"name": "task_name", "width": 32},
                {"name": "priority", "width": 8},
                {"name": "effort", "width": 6},
                {"name": "deps", "width": 12},
                {"name": "created", "width": 10},
            ],
        },
    )
    monkeypatch.setattr(
        "dot_tasks.cli.choose_command",
        lambda commands, title: "init",
    )

    with runner.isolated_filesystem(temp_dir=str(tmp_path)):
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "Initialized tasks root:" in result.output
        assert (Path(".tasks") / "todo").is_dir()
        cfg = _read_config(Path(".tasks") / "config.yaml")
        assert cfg["settings"]["interactive_enabled"] is True
        assert cfg["settings"]["show_banner"] is True


def test_init_interactive_cancel_exits_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root), "--nointeractive"])
    before = (root / "config.yaml").read_text(encoding="utf-8")
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli.init_config_form", lambda **kwargs: None)

    result = runner.invoke(app, ["init", "--tasks-root", str(root)])
    after = (root / "config.yaml").read_text(encoding="utf-8")
    assert result.exit_code == 1
    assert "Canceled." in result.output
    assert before == after


def test_no_args_interactive_cancel_exits_0(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr("dot_tasks.cli.choose_command", lambda commands, title: None)

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Canceled." in result.output


def test_no_args_non_interactive_prints_help_and_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: False)

    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "interactive terminal" in result.output


def test_root_nointeractive_prints_help_and_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    result = runner.invoke(app, ["--tasks-root", str(root), "--nointeractive"])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_missing_required_arg_with_nointeractive_errors(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "task_name is required in non-interactive mode" in result.output


def test_unsupported_config_key_warns_and_ignores(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        "settings:\n  interactive_mode: prompt\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "Warning: Unsupported settings key 'interactive_mode'" in result.output


def test_invalid_interactive_enabled_warns_and_falls_back(tmp_path: Path) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    (root / "config.yaml").write_text(
        "settings:\n  interactive_enabled: maybe\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "Warning: Invalid settings.interactive_enabled" in result.output


def test_update_interactive_form_replaces_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-a", "--tasks-root", str(root)])
    runner.invoke(app, ["create", "dep-b", "--tasks-root", str(root)])
    runner.invoke(
        app,
        ["create", "main-task", "--depends-on", "dep-a", "--tasks-root", str(root)],
    )

    dep_b_meta, _ = _read_task_md(_task_dir(root, "todo", "dep-b") / "task.md")
    dep_b_id = dep_b_meta["task_id"]

    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.update_form",
        lambda task, dependency_options: {
            "priority": None,
            "effort": None,
            "owner": task.metadata.owner or "",
            "tags": [],
            "depends_on": [dep_b_id],
            "replace_depends_on": True,
            "note": "Replaced deps",
        },
    )

    result = runner.invoke(app, ["update", "main-task", "--tasks-root", str(root)])
    assert result.exit_code == 0
    meta, _ = _read_task_md(_task_dir(root, "todo", "main-task") / "task.md")
    assert meta["depends_on"] == [dep_b_id]


def test_create_interactive_cancel_prints_canceled_and_exits_1(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / ".tasks"
    runner.invoke(app, ["init", "--tasks-root", str(root)])

    monkeypatch.setattr("dot_tasks.cli._can_interact", lambda: True)
    monkeypatch.setattr(
        "dot_tasks.cli.create_form",
        lambda default_name, dependency_options: None,
    )

    result = runner.invoke(app, ["create", "--tasks-root", str(root)])
    assert result.exit_code == 1
    assert "Canceled." in result.output
