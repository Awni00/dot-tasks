from __future__ import annotations

import os
from pathlib import Path

from InquirerPy.separator import Separator
import pytest
import typer

from dot_tasks.models import Task, TaskMetadata
from dot_tasks import prompt_ui
from dot_tasks import selector_ui
from dot_tasks.service import TaskService


class _FakePrompt:
    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeEventApp:
    def __init__(self):
        self.result = None

    def exit(self, *, result=None):
        self.result = result


class _FakeEvent:
    def __init__(self):
        self.app = _FakeEventApp()


class _FakeValidator:
    def __init__(self, *, error: Exception | None = None):
        self.error = error
        self.calls = 0

    def validate(self, _document):
        self.calls += 1
        if self.error is not None:
            raise self.error


class _FakeFuzzyPrompt:
    def __init__(
        self,
        *,
        selected_choices=None,
        result_value=None,
        result_name=None,
        validator: _FakeValidator | None = None,
    ):
        self.selected_choices = selected_choices or []
        self.result_value = result_value or []
        self.result_name = result_name or []
        self.status = {"answered": False, "result": None}
        self._validator = validator or _FakeValidator()
        self.kb_func_lookup = {"answer": [{"func": self._default_answer}]}
        self.default_answer_called = False

    def _default_answer(self, event):
        self.default_answer_called = True
        event.app.exit(result=["fallback"])

    def execute(self):
        event = _FakeEvent()
        handlers = self.kb_func_lookup.get("answer", [])
        for handler in handlers:
            func = handler.get("func")
            if callable(func):
                func(event)
        return event.app.result


class _FakeInquirer:
    def __init__(
        self,
        *,
        select_result=None,
        select_error: Exception | None = None,
        checkbox_result=None,
        fuzzy_result=None,
        fuzzy_prompt=None,
        fuzzy_error: Exception | None = None,
        text_result=None,
        text_error: Exception | None = None,
    ):
        self.select_result = select_result
        self.select_error = select_error
        self.checkbox_result = checkbox_result
        self.fuzzy_result = fuzzy_result
        self.fuzzy_prompt = fuzzy_prompt
        self.fuzzy_error = fuzzy_error
        self.text_result = text_result
        self.text_error = text_error
        self.last_select_kwargs = None
        self.last_fuzzy_kwargs = None
        self.last_text_kwargs = None

    def select(self, **kwargs):
        self.last_select_kwargs = kwargs
        return _FakePrompt(result=self.select_result, error=self.select_error)

    def checkbox(self, **kwargs):
        return _FakePrompt(result=self.checkbox_result)

    def fuzzy(self, **kwargs):
        self.last_fuzzy_kwargs = kwargs
        if self.fuzzy_prompt is not None:
            return self.fuzzy_prompt
        return _FakePrompt(result=self.fuzzy_result, error=self.fuzzy_error)

    def text(self, **kwargs):
        self.last_text_kwargs = kwargs
        return _FakePrompt(result=self.text_result, error=self.text_error)


def _task(name: str, task_id: str = "t-20260201-001", status: str = "todo") -> Task:
    return Task(
        metadata=TaskMetadata(
            task_id=task_id,
            task_name=name,
            status=status,
            date_created="2026-02-01",
        ),
        body="",
        task_dir=Path("/tmp") / name,
    )


def _command_sections() -> list[prompt_ui.CommandPaletteSection]:
    return [
        prompt_ui.CommandPaletteSection(
            title="Inspect",
            commands=[
                prompt_ui.CommandPaletteEntry("list", "List tasks"),
                prompt_ui.CommandPaletteEntry("view", "Show task"),
            ],
        ),
        prompt_ui.CommandPaletteSection(
            title="Setup",
            commands=[
                prompt_ui.CommandPaletteEntry("init", "Initialize tasks root"),
            ],
        ),
    ]


def test_choose_command_uses_grouped_select_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: ensure command picker uses grouped select path when available.
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None, style=None: "init",
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: pytest.fail("numeric prompt used"))

    selected = prompt_ui.choose_command(_command_sections())
    assert selected == "init"


def test_choose_command_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: preserve cancel semantics so grouped command picker cancellation returns None.
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None, style=None: None,
    )

    selected = prompt_ui.choose_command(_command_sections())
    assert selected is None


def test_choose_command_passes_grouped_options_to_select(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: keep grouped command labels aligned and include visible section separators in selector UI.
    captured: dict[str, object] = {}

    def _select_one(title, options, default_value=None, style=None):
        captured["title"] = title
        captured["options"] = options
        captured["default_value"] = default_value
        captured["style"] = style
        return "init"

    monkeypatch.setattr(prompt_ui, "select_one", _select_one)

    selected = prompt_ui.choose_command(_command_sections())
    assert selected == "init"
    assert captured["title"] == "Select command"
    assert captured["options"] == [
        prompt_ui.SelectionSeparator("---- Inspect ----"),
        ("list", "list      List tasks"),
        ("view", "view      Show task"),
        prompt_ui.SelectionSeparator("---- Setup ----"),
        ("init", "init      Initialize tasks root"),
    ]
    assert captured["default_value"] is None
    assert captured["style"] == {"separator": "bold ansicyan"}


def test_choose_command_falls_back_to_numeric_on_selector_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Purpose: ensure grouped selector failures still fall back to numeric command selection.
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None, style=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("selector runtime failed")
        ),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "2")

    selected = prompt_ui.choose_command(_command_sections())
    assert selected == "view"


def test_choose_command_numeric_fallback_renders_section_headings_and_global_indexes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Purpose: ensure numeric fallback mirrors grouped layout with section headings and global numbering.
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None, style=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("selector runtime failed")
        ),
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "0")

    selected = prompt_ui.choose_command(_command_sections())

    assert selected is None
    output = capsys.readouterr().out
    assert "---- Inspect ----" in output
    assert "---- Setup ----" in output
    assert " 1. list      List tasks" in output
    assert " 2. view      Show task" in output
    assert " 3. init      Initialize tasks root" in output


def test_echo_command_section_heading_uses_secho_for_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: ensure numeric fallback headings use styled output when a terminal is available.
    class _FakeStdout:
        def isatty(self) -> bool:
            return True

    captured: dict[str, object] = {}
    monkeypatch.setattr(prompt_ui.sys, "stdout", _FakeStdout())
    monkeypatch.setattr(
        prompt_ui.typer,
        "secho",
        lambda message, **kwargs: captured.update({"message": message, "kwargs": kwargs}),
    )
    monkeypatch.setattr(
        prompt_ui.typer,
        "echo",
        lambda *_args, **_kwargs: pytest.fail("plain echo should not be used for tty section headings"),
    )

    prompt_ui._echo_command_section_heading("Inspect")

    assert captured["message"] == "---- Inspect ----"
    assert captured["kwargs"] == {"fg": typer.colors.CYAN, "bold": True}


def test_choose_task_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_fuzzy", lambda title, options, default_value=None: None)

    selected = prompt_ui.choose_task([_task("alpha")])
    assert selected is None


def test_choose_task_uses_fuzzy_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _select_fuzzy(title, options, default_value=None):
        captured["options"] = options
        return "alpha"

    monkeypatch.setattr(prompt_ui, "select_fuzzy", _select_fuzzy)
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: pytest.fail("numeric prompt used"))
    selected = prompt_ui.choose_task([_task("alpha")])
    assert selected == "alpha"
    assert captured["options"] == [("alpha", "alpha (t-20260201-001) [todo]")]


def test_choose_task_fuzzy_default_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _select_fuzzy(title, options, default_value=None):
        captured["default_value"] = default_value
        return "alpha"

    monkeypatch.setattr(prompt_ui, "select_fuzzy", _select_fuzzy)
    selected = prompt_ui.choose_task([_task("alpha")])
    assert selected == "alpha"
    assert captured["default_value"] is None


def test_choose_task_fuzzy_failure_falls_back_to_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_fuzzy",
        lambda title, options, default_value=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("selector runtime failed")
        ),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "1")
    selected = prompt_ui.choose_task([_task("alpha")], title="Select task")
    assert selected == "alpha"


def test_choose_task_numeric_fallback_shows_status_suffix(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_fuzzy",
        lambda title, options, default_value=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("selector runtime failed")
        ),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "1")

    selected = prompt_ui.choose_task([_task("alpha", status="doing")], title="Select task")
    assert selected == "alpha"
    output = capsys.readouterr().out
    assert "1. alpha (t-20260201-001) [doing]" in output


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
    prompt_values = iter(["1", "1", "1,4,5", "n"])
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
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)

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
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)

    payload = prompt_ui.init_config_form(default_list_column_names=["not-a-column", "task_name", "task_name"])
    assert payload is not None
    assert captured["defaults"] == ["task_name"]


def test_init_config_form_empty_selection_uses_fallback_defaults_even_with_invalid_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: "enabled")
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)

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


def test_init_config_form_include_agents_prompt_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["enabled", "enabled"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", lambda *args, **kwargs: ["task_name"])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "TEAM_AGENTS.md")

    payload = prompt_ui.init_config_form()
    assert payload is not None
    assert payload["append_agents_snippet"] is True
    assert payload["agents_file"] == "TEAM_AGENTS.md"


def test_init_config_form_cancel_on_agents_file_prompt_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["enabled", "enabled"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_prompt_multi_choice", lambda *args, **kwargs: ["task_name"])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)

    assert prompt_ui.init_config_form() is None


def test_create_form_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)

    assert prompt_ui.create_form(default_name="test-task") is None


def test_create_form_reprompts_for_invalid_task_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Purpose: ensure invalid kebab-case names are rejected immediately and re-prompted.
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["Invalid Name", "valid-name", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[],
        validate_task_name=TaskService.validate_task_name,
    )
    assert payload is not None
    assert payload["task_name"] == "valid-name"
    assert (
        "Error: task_name must be kebab-case with lowercase letters, numbers, and hyphens"
        in capsys.readouterr().err
    )


def test_create_form_reprompts_for_duplicate_task_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Purpose: ensure duplicate-name validation errors are surfaced immediately at the name prompt.
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["existing-task", "fresh-task", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])

    def _validate_task_name(value: str) -> None:
        if value == "existing-task":
            raise ValueError("Task name already exists: existing-task")

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[],
        validate_task_name=_validate_task_name,
    )
    assert payload is not None
    assert payload["task_name"] == "fresh-task"
    assert "Error: Task name already exists: existing-task" in capsys.readouterr().err


def test_create_form_reprompts_for_blank_task_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Purpose: ensure blank names are rejected before running other create-form prompts.
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["   ", "valid-name", ""])
    validator_calls: list[str] = []
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])

    def _validate_task_name(value: str) -> None:
        validator_calls.append(value)

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[],
        validate_task_name=_validate_task_name,
    )
    assert payload is not None
    assert payload["task_name"] == "valid-name"
    assert validator_calls == ["valid-name"]
    assert "Error: task_name is required" in capsys.readouterr().err


def test_create_form_cancel_during_task_name_reprompt_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Purpose: preserve cancel semantics when user aborts during the name validation loop.
    prompts = iter(["Invalid Name", None])
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_single_choice",
        lambda *args, **kwargs: pytest.fail("create_form should exit before later prompts"),
    )

    assert (
        prompt_ui.create_form(
            default_name="test-task",
            dependency_options=[],
            validate_task_name=TaskService.validate_task_name,
        )
        is None
    )


def test_create_form_dependency_gate_skips_selector_on_no(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["test-task", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_depends_on_choice",
        lambda *args, **kwargs: pytest.fail("dependency selector should not be shown"),
    )

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[("t-1", "Task 1")],
    )
    assert payload is not None
    assert payload["spec_readiness"] == "unspecified"
    assert payload["depends_on"] == []


def test_create_form_dependency_gate_runs_selector_on_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m", "ready"])
    prompts = iter(["test-task", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(prompt_ui, "_prompt_depends_on_choice", lambda *args, **kwargs: ["t-1"])

    payload = prompt_ui.create_form(
        default_name="test-task",
        dependency_options=[("t-1", "Task 1")],
    )
    assert payload is not None
    assert payload["spec_readiness"] == "ready"
    assert payload["depends_on"] == ["t-1"]


def test_create_form_dependency_gate_skipped_when_no_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["test-task", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_yes_no",
        lambda *args, **kwargs: pytest.fail("dependency gate should not be shown"),
    )

    payload = prompt_ui.create_form(default_name="test-task", dependency_options=[])
    assert payload is not None
    assert payload["spec_readiness"] == "unspecified"
    assert payload["depends_on"] == []


def test_create_form_cancel_at_dependency_gate_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["test-task", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: None)

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


def test_select_fuzzy_many_preserves_source_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(fuzzy_result=["b", "a"]),
    )

    values = selector_ui.select_fuzzy_many(
        "depends_on",
        [("a", "Task A"), ("b", "Task B")],
    )
    assert values == ["a", "b"]


def test_select_fuzzy_many_binds_space_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    fake = _FakeInquirer(fuzzy_result=["a"])
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: fake)

    values = selector_ui.select_fuzzy_many("depends_on", [("a", "Task A")])
    assert values == ["a"]
    assert fake.last_fuzzy_kwargs is not None
    assert fake.last_fuzzy_kwargs["instruction"] == "(space/tab to toggle, enter to submit, ctrl-c to cancel)"
    assert fake.last_fuzzy_kwargs["keybindings"]["toggle"] == [{"key": "space"}]


def test_select_fuzzy_many_enter_without_toggle_submits_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    fake_prompt = _FakeFuzzyPrompt(
        selected_choices=[],
        result_value=["a"],
        result_name=["Task A"],
    )
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: _FakeInquirer(fuzzy_prompt=fake_prompt))

    values = selector_ui.select_fuzzy_many("depends_on", [("a", "Task A")])
    assert values == []
    assert fake_prompt.default_answer_called is False
    assert fake_prompt.status["answered"] is True
    assert fake_prompt.status["result"] == []


def test_select_fuzzy_many_enter_with_toggled_values_submits_selected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    fake_prompt = _FakeFuzzyPrompt(
        selected_choices=[{"name": "Task A", "value": "a"}],
        result_value=["a"],
        result_name=["Task A"],
    )
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: _FakeInquirer(fuzzy_prompt=fake_prompt))

    values = selector_ui.select_fuzzy_many("depends_on", [("a", "Task A")])
    assert values == ["a"]
    assert fake_prompt.default_answer_called is False
    assert fake_prompt.status["answered"] is True
    assert fake_prompt.status["result"] == ["Task A"]


def test_select_fuzzy_keyboard_interrupt_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(fuzzy_error=KeyboardInterrupt()),
    )

    assert selector_ui.select_fuzzy("pick", [("a", "A")]) is None


def test_select_fuzzy_many_keyboard_interrupt_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(fuzzy_error=KeyboardInterrupt()),
    )

    assert selector_ui.select_fuzzy_many("pick", [("a", "A")]) is None


def test_select_fuzzy_runtime_error_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(fuzzy_error=RuntimeError("boom")),
    )

    with pytest.raises(selector_ui.SelectorUnavailableError):
        selector_ui.select_fuzzy("pick", [("a", "A")])


def test_select_fuzzy_many_runtime_error_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(fuzzy_error=RuntimeError("boom")),
    )

    with pytest.raises(selector_ui.SelectorUnavailableError):
        selector_ui.select_fuzzy_many("pick", [("a", "A")])


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


def test_select_one_passes_separator_entries_to_inquirer(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: ensure grouped select options preserve non-pickable section headers for the root picker UI.
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    fake = _FakeInquirer(select_result="b")
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: fake)

    value = selector_ui.select_one(
        "pick",
        [
            selector_ui.SelectionSeparator("---- Inspect ----"),
            ("a", "Alpha"),
            selector_ui.SelectionSeparator("---- Setup ----"),
            ("b", "Beta"),
        ],
        style={"separator": "bold ansicyan"},
    )

    assert value == "b"
    assert fake.last_select_kwargs is not None
    choices = fake.last_select_kwargs["choices"]
    assert isinstance(choices[0], Separator)
    assert str(choices[0]) == "---- Inspect ----"
    assert choices[1] == {"name": "Alpha", "value": "a"}
    assert isinstance(choices[2], Separator)
    assert str(choices[2]) == "---- Setup ----"
    assert choices[3] == {"name": "Beta", "value": "b"}
    assert fake.last_select_kwargs["style"].dict["separator"] == "bold ansicyan"


def test_select_text_uses_inquirer_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    fake = _FakeInquirer(text_result="typed value")
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: fake)

    value = selector_ui.select_text("task_name", default_value="default-value")

    assert value == "typed value"
    assert fake.last_text_kwargs is not None
    assert fake.last_text_kwargs["message"] == "task_name"
    assert fake.last_text_kwargs["default"] == "default-value"
    assert fake.last_text_kwargs["vi_mode"] is False
    assert fake.last_text_kwargs["mandatory"] is False
    assert fake.last_text_kwargs["raise_keyboard_interrupt"] is True


def test_select_text_keyboard_interrupt_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(text_error=KeyboardInterrupt()),
    )

    assert selector_ui.select_text("task_name", default_value="x") is None


def test_select_text_runtime_error_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(
        selector_ui,
        "_inquirer",
        lambda: _FakeInquirer(text_error=RuntimeError("boom")),
    )

    with pytest.raises(selector_ui.SelectorUnavailableError):
        selector_ui.select_text("task_name", default_value="x")


def test_select_text_scopes_prompt_toolkit_no_cpr_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: ensure selector calls run with CPR probing disabled and env is restored.
    class _AssertInquirer:
        def text(self, **kwargs):
            assert os.environ.get("PROMPT_TOOLKIT_NO_CPR") == "1"
            return _FakePrompt(result="typed value")

    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: _AssertInquirer())
    monkeypatch.delenv("PROMPT_TOOLKIT_NO_CPR", raising=False)

    assert selector_ui.select_text("task_name", default_value="x") == "typed value"
    assert os.environ.get("PROMPT_TOOLKIT_NO_CPR") is None


def test_select_text_multiline_uses_inquirer(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: keep multiline editor behavior through InquirerPy text prompt.
    monkeypatch.setattr(selector_ui, "_ensure_tty", lambda: None)
    fake = _FakeInquirer(text_result="typed value")
    monkeypatch.setattr(selector_ui, "_inquirer", lambda: fake)

    value = selector_ui.select_text("summary", default_value="- TODO", multiline=True)

    assert value == "typed value"
    assert fake.last_text_kwargs is not None
    assert fake.last_text_kwargs["multiline"] is True


def test_no_cpr_env_sets_and_restores(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: ensure CPR suppression is scoped to one prompt invocation.
    monkeypatch.delenv("PROMPT_TOOLKIT_NO_CPR", raising=False)
    assert os.environ.get("PROMPT_TOOLKIT_NO_CPR") is None
    with selector_ui._no_cpr_env():
        assert os.environ.get("PROMPT_TOOLKIT_NO_CPR") == "1"
    assert os.environ.get("PROMPT_TOOLKIT_NO_CPR") is None


def test_safe_prompt_uses_selector_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_text", lambda message, default_value="", multiline=False: "value-from-selector")
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: pytest.fail("fallback prompt used"))

    assert prompt_ui._safe_prompt("summary", default="default") == "value-from-selector"


def test_safe_prompt_multiline_uses_selector_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: keep multiline prompts on the InquirerPy path when selector is available.
    monkeypatch.setattr(
        prompt_ui,
        "select_text",
        lambda message, default_value="", multiline=False: "value-from-selector",
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: pytest.fail("fallback prompt used"))

    assert (
        prompt_ui._safe_prompt("Summary (Esc+Enter to submit)", default="- TODO", multiline=True)
        == "value-from-selector"
    )


def test_safe_prompt_falls_back_to_typer_on_selector_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_text",
        lambda message, default_value="", multiline=False: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "value-from-typer")

    assert prompt_ui._safe_prompt("summary", default="default") == "value-from-typer"


def test_safe_prompt_multiline_fallback_strips_esc_enter_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    # Purpose: avoid showing multiline-only instructions when fallback uses single-line typer input.
    monkeypatch.setattr(
        prompt_ui,
        "select_text",
        lambda message, default_value="", multiline=False: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    captured: dict[str, str] = {}

    def _fake_prompt(message: str, default: str = "") -> str:
        captured["message"] = message
        return "value-from-typer"

    monkeypatch.setattr(prompt_ui.typer, "prompt", _fake_prompt)

    value = prompt_ui._safe_prompt(
        "Acceptance Criteria (Esc+Enter to submit)",
        default="- TODO",
        multiline=True,
    )
    assert value == "value-from-typer"
    assert captured["message"] == "Acceptance Criteria"


def test_safe_prompt_returns_none_when_typer_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_text",
        lambda message, default_value="", multiline=False: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    monkeypatch.setattr(
        prompt_ui.typer,
        "prompt",
        lambda *args, **kwargs: (_ for _ in ()).throw(typer.Abort()),
    )

    assert prompt_ui._safe_prompt("summary", default="default") is None


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


def test_depends_on_choice_fuzzy_failure_falls_back_to_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_fuzzy_many",
        lambda title, options, default_values=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "2,1")
    values = prompt_ui._prompt_depends_on_choice("depends_on", [("a", "Task A"), ("b", "Task B")])
    assert values == ["a", "b"]


def test_depends_on_choice_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_fuzzy_many", lambda *args, **kwargs: None)
    assert prompt_ui._prompt_depends_on_choice("depends_on", [("a", "Task A")]) is None


def test_tag_choice_fuzzy_failure_falls_back_to_numeric(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "select_fuzzy_many",
        lambda title, options, default_values=None: (_ for _ in ()).throw(
            selector_ui.SelectorUnavailableError("fallback")
        ),
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "2,1")
    values = prompt_ui._prompt_tag_choice("tags", [("a", "Tag A"), ("b", "Tag B")])
    assert values == ["a", "b"]


def test_tag_choice_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_fuzzy_many", lambda *args, **kwargs: None)
    assert prompt_ui._prompt_tag_choice("tags", [("a", "Tag A")]) is None


def test_prompt_tags_adds_sentinel_and_skips_new_prompt_when_not_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def _prompt_tag_choice(title, options, default_values=None):
        captured["title"] = title
        captured["options"] = options
        captured["default_values"] = default_values
        return ["backend"]

    monkeypatch.setattr(prompt_ui, "_prompt_tag_choice", _prompt_tag_choice)
    monkeypatch.setattr(
        prompt_ui,
        "_safe_prompt",
        lambda *args, **kwargs: pytest.fail("new tag prompt should be skipped"),
    )

    values = prompt_ui._prompt_tags(
        [("backend", "backend"), ("api", "api")],
        default_values=["api"],
    )
    assert values == ["backend"]
    assert captured["title"] == "tags (select existing or add new)"
    assert captured["options"] == [
        ("backend", "backend"),
        ("api", "api"),
        (prompt_ui._ADD_NEW_TAGS_SENTINEL, prompt_ui._ADD_NEW_TAGS_LABEL),
    ]
    assert captured["default_values"] == ["api"]


def test_prompt_tags_merges_existing_and_new_when_add_new_selected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_tag_choice",
        lambda *args, **kwargs: ["backend", "api", prompt_ui._ADD_NEW_TAGS_SENTINEL],
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "api, new-tag")

    values = prompt_ui._prompt_tags([("backend", "backend"), ("api", "api")])
    assert values == ["api", "backend", "new-tag"]


def test_prompt_tags_cancel_when_existing_selection_canceled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "_prompt_tag_choice", lambda *args, **kwargs: None)
    assert prompt_ui._prompt_tags([("backend", "backend")]) is None


def test_prompt_tags_no_existing_options_prompts_new_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_tag_choice",
        lambda *args, **kwargs: pytest.fail("tag choice should not run without options"),
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "x, y")
    assert prompt_ui._prompt_tags([]) == ["x", "y"]


def test_prompt_tags_cancel_when_new_tag_prompt_canceled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_tag_choice",
        lambda *args, **kwargs: ["backend", prompt_ui._ADD_NEW_TAGS_SENTINEL],
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui._prompt_tags([("backend", "backend")]) is None


def test_prompt_tags_blank_new_tag_input_preserves_existing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_tag_choice",
        lambda *args, **kwargs: ["backend", prompt_ui._ADD_NEW_TAGS_SENTINEL],
    )
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "   ")
    assert prompt_ui._prompt_tags([("backend", "backend")]) == ["backend"]


def test_update_form_depends_on_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    captured: dict[str, object] = {}

    def _depends(title, options, default_values=None):
        captured["defaults"] = default_values
        return ["t-2"]

    task = _task("alpha")
    task.metadata.depends_on = ["t-1"]
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(prompt_ui, "_prompt_depends_on_choice", _depends)

    payload = prompt_ui.update_form(task, dependency_options=[("t-1", "Task 1"), ("t-2", "Task 2")])
    assert payload is not None
    assert captured["defaults"] == ["t-1"]
    assert payload["spec_readiness"] is None
    assert payload["depends_on"] == ["t-2"]
    assert payload["replace_depends_on"] is True
    assert "note" not in payload


def test_update_form_dependency_gate_no_skips_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    task = _task("alpha")
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_depends_on_choice",
        lambda *args, **kwargs: pytest.fail("depends_on selector should be skipped when gate is no"),
    )

    payload = prompt_ui.update_form(task, dependency_options=[("t-1", "Task 1")], tag_options=[])
    assert payload is not None
    assert payload["depends_on"] == []
    assert payload["replace_depends_on"] is False


def test_update_form_dependency_gate_yes_empty_selection_replaces_with_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    task = _task("alpha")
    task.metadata.depends_on = ["t-1"]
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: True)
    monkeypatch.setattr(prompt_ui, "_prompt_depends_on_choice", lambda *args, **kwargs: [])

    payload = prompt_ui.update_form(task, dependency_options=[("t-1", "Task 1")], tag_options=[])
    assert payload is not None
    assert payload["depends_on"] == []
    assert payload["replace_depends_on"] is True


def test_update_form_dependency_gate_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    task = _task("alpha")
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: None)

    assert prompt_ui.update_form(task, dependency_options=[("t-1", "Task 1")], tag_options=[]) is None


def test_update_form_no_dependency_options_skips_gate_and_selector(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    task = _task("alpha")
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_yes_no",
        lambda *args, **kwargs: pytest.fail("dependency gate should be skipped without options"),
    )
    monkeypatch.setattr(
        prompt_ui,
        "_prompt_depends_on_choice",
        lambda *args, **kwargs: pytest.fail("depends_on selector should be skipped without options"),
    )

    payload = prompt_ui.update_form(task, dependency_options=[], tag_options=[])
    assert payload is not None
    assert payload["depends_on"] == []
    assert payload["replace_depends_on"] is False


def test_create_form_uses_prompt_tags_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["p2", "m", "unspecified"])
    prompts = iter(["test-task", ""])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_prompt_yes_no", lambda *args, **kwargs: False)
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: next(prompts))
    monkeypatch.setattr(prompt_ui, "_prompt_tags", lambda *args, **kwargs: ["backend", "api"])

    payload = prompt_ui.create_form(default_name="test-task", dependency_options=[], tag_options=[])
    assert payload is not None
    assert payload["tags"] == ["backend", "api"]


def test_update_form_tag_prompt_uses_existing_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    captured: dict[str, object] = {}

    def _prompt_tags(tag_options, default_values=None):
        captured["defaults"] = default_values
        return ["new-tag"]

    task = _task("alpha")
    task.metadata.tags = ["backend", "ops"]
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: "")
    monkeypatch.setattr(prompt_ui, "_prompt_tags", _prompt_tags)

    payload = prompt_ui.update_form(task, dependency_options=[], tag_options=[("backend", "backend")])
    assert payload is not None
    assert captured["defaults"] == ["backend", "ops"]
    assert payload["tags"] == ["new-tag"]


def test_yes_no_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "select_one", lambda title, options, default_value=None: None)
    assert prompt_ui._prompt_yes_no("Set deps?") is None


def test_create_form_cancel_on_text_field_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui.create_form(default_name="x", dependency_options=[]) is None


def test_update_form_cancel_on_text_field_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    choices = iter(["__keep__", "__keep__", "__keep__", "__keep__"])
    monkeypatch.setattr(prompt_ui, "_prompt_single_choice", lambda *args, **kwargs: next(choices))
    monkeypatch.setattr(prompt_ui, "_safe_prompt", lambda *args, **kwargs: None)
    assert prompt_ui.update_form(_task("alpha"), dependency_options=[]) is None
