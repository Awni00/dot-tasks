from __future__ import annotations

from pathlib import Path

import pytest

from dot_tasks.models import Task, TaskMetadata
from dot_tasks import prompt_ui
from dot_tasks import selector_ui


class _FakePrompt:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeInquirer:
    def __init__(self, *, select_result=None, select_error: Exception | None = None, checkbox_result=None):
        self.select_result = select_result
        self.select_error = select_error
        self.checkbox_result = checkbox_result

    def select(self, **kwargs):
        return _FakePrompt(result=self.select_result, error=self.select_error)

    def checkbox(self, **kwargs):
        return _FakePrompt(result=self.checkbox_result)


def _task(name: str, task_id: str = "t-20260201-001") -> Task:
    return Task(
        metadata=TaskMetadata(
            task_id=task_id,
            task_name=name,
            status="todo",
            date_created="2026-02-01",
        ),
        body="",
        task_dir=Path("/tmp") / name,
    )


def test_choose_command_uses_selector_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_one", lambda title, options, default_value=None: "init")
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: pytest.fail("numeric prompt used"))

    selected = prompt_ui.choose_command([("init", "Initialize")])
    assert selected == "init"


def test_choose_command_falls_back_to_numeric_on_selector_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("selector runtime failed")
        ),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "2")

    selected = prompt_ui.choose_command([("init", "Initialize"), ("list", "List tasks")])
    assert selected == "list"


def test_choose_task_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_one", lambda title, options, default_value=None: None)

    selected = prompt_ui.choose_task([_task("alpha")])
    assert selected is None


def test_init_config_form_uses_selector_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_one", lambda *args, **kwargs: "disabled")
    monkeypatch.setattr(prompt_ui, "select_many", lambda *args, **kwargs: ["task_name", "status"])
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: pytest.fail("numeric prompt used"))

    payload = prompt_ui.init_config_form()
    assert payload is not None
    assert payload["interactive_enabled"] is False
    assert payload["show_banner"] is False
    assert payload["list_columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "status", "width": 10},
    ]


def test_init_config_form_uses_passed_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_defaults: dict[str, object] = {}

    def _select_one(title, options, default_value=None):
        if title == "Default interactive behavior":
            captured_defaults["interactive"] = default_value
            return "enabled"
        if title == "Banner behavior for root 'dot-tasks'":
            captured_defaults["show_banner"] = default_value
            return "disabled"
        return "enabled"

    def _select_many(title, options, default_values=None):
        captured_defaults["columns"] = default_values
        return ["status"]

    monkeypatch.setattr(prompt_ui, "select_one", _select_one)
    monkeypatch.setattr(prompt_ui, "select_many", _select_many)

    payload = prompt_ui.init_config_form(
        default_interactive_enabled=False,
        default_show_banner=True,
        default_list_column_names=["status", "task_name"],
    )
    assert payload is not None
    assert captured_defaults == {
        "interactive": "disabled",
        "show_banner": "enabled",
        "columns": ["status", "task_name"],
    }
    assert payload["show_banner"] is False
    assert payload["list_columns"] == [{"name": "status", "width": 10}]


def test_init_config_form_falls_back_to_numeric_on_selector_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda *args, **kwargs: (_ for _ in ()).throw(selector_ui.SelectorUnavailableError("fallback")),
    )
    monkeypatch.setattr(
        prompt_ui,
        "select_many",
        lambda *args, **kwargs: (_ for _ in ()).throw(selector_ui.SelectorUnavailableError("fallback")),
    )
    prompt_values = iter(["1", "1", "1,4,5"])
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: next(prompt_values))

    payload = prompt_ui.init_config_form()
    assert payload is not None
    assert payload["interactive_enabled"] is True
    assert payload["show_banner"] is True
    assert payload["list_columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
    ]


def test_init_config_form_empty_columns_falls_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: "enabled")
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", lambda *args, **kwargs: [])

    payload = prompt_ui.init_config_form()
    assert payload is not None
    assert payload["show_banner"] is True
    assert payload["list_columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
        {"name": "deps", "width": 12},
        {"name": "created", "width": 10},
    ]
    captured = capsys.readouterr()
    assert "Warning: no list columns selected; using defaults." in captured.err


def test_init_config_form_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: None)
    assert prompt_ui.init_config_form() is None


def test_init_config_form_ignores_invalid_default_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _multi_choice(*args, **kwargs):
        captured["defaults"] = kwargs.get("default_values")
        return ["task_name"]

    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: "enabled")
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", _multi_choice)

    payload = prompt_ui.init_config_form(default_list_column_names=["not-a-column", "task_name", "task_name"])
    assert payload is not None
    assert captured["defaults"] == ["task_name"]


def test_init_config_form_empty_selection_uses_fallback_defaults_even_with_invalid_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: "enabled")
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", lambda *args, **kwargs: [])

    payload = prompt_ui.init_config_form(default_list_column_names=["not-a-column"])
    assert payload is not None
    assert payload["show_banner"] is True
    assert payload["list_columns"] == [
        {"name": "task_name", "width": 32},
        {"name": "priority", "width": 8},
        {"name": "effort", "width": 6},
        {"name": "deps", "width": 12},
        {"name": "created", "width": 10},
    ]


def test_init_config_form_cancel_on_banner_choice_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["enabled", None])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    assert prompt_ui.init_config_form() is None


def test_create_form_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "")

    selections = iter([None])
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None: next(selections),
    )

    assert prompt_ui.create_form(default_name="test-task") is None


def test_create_form_dependency_gate_skips_selector_on_no(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_multi_choice",
        lambda *args, **kwargs: pytest.fail("dependency selector should not be shown"),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "")

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[("t-1", "Task 1")],
    )
    assert payload is not None
    assert payload["depends_on"] == []


def test_create_form_dependency_gate_runs_selector_on_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", lambda *args, **kwargs: ["t-1"])
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "")

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[("t-1", "Task 1")],
    )
    assert payload is not None
    assert payload["depends_on"] == ["t-1"]


def test_create_form_dependency_gate_skipped_when_no_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_yes_no",
        lambda *args, **kwargs: pytest.fail("dependency gate should not be shown"),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "")

    payload = prompt_ui.create_form(default_name="test-task", dependency_options=[])
    assert payload is not None
    assert payload["depends_on"] == []


def test_create_form_cancel_at_dependency_gate_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: None)
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "")

    assert (
        prompt_ui.create_form(
            default_name="test-task",
            dependency_options=[("t-1", "Task 1")],
        )
        is None
    )


def test_select_many_preserves_source_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(checkbox_result=["b", "a"]),
    )

    values = selector_ui.select_many(
        "depends_on",
        [("a", "Task A"), ("b", "Task B")],
    )
    assert values == ["a", "b"]


def test_select_one_keyboard_interrupt_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(select_error=KeyboardInterrupt()),
    )

    assert selector_ui.select_one("pick", [("a", "A")]) is None


def test_select_one_runtime_error_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(select_error=RuntimeError("boom")),
    )

    with pytest.raises(selector_ui.SelectorUnavailableError):
        selector_ui.select_one("pick", [("a", "A")])


def test_numeric_single_choice_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui._prompt_single_choice("priority", [("p2", "p2")], "p2") is None


def test_numeric_multi_choice_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_many",
        lambda title, options, default_values=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui._prompt_multi_choice("depends_on", [("t1", "Task 1")]) is None


def test_yes_no_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_one", lambda title, options, default_value=None: None)
    assert prompt_ui._prompt_yes_no("Set deps?") is None


def test_create_form_cancel_on_text_field_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui.create_form(default_name="x", dependency_options=[]) is None


def test_update_form_cancel_on_text_field_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui.update_form(_task("alpha"), dependency_options=[]) is None
