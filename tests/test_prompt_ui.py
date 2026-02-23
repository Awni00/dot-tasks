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


def test_create_form_cancel_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prompt_ui.typer, "prompt", lambda *args, **kwargs: "")

    selections = iter([None])
    monkeypatch.setattr(
        prompt_ui,
        "select_one",
        lambda title, options, default_value=None: next(selections),
    )

    assert prompt_ui.create_form(default_name="test-task") is None


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
