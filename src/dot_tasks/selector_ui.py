"""Arrow-key selector helpers backed by InquirerPy."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import calendar
import datetime as dt
import os
import sys
from typing import TypeAlias

from prompt_toolkit.filters import is_done


class SelectorUnavailableError(RuntimeError):
    """Raised when arrow-key selector UI cannot be used."""


@dataclass(frozen=True)
class _SelectionOption:
    value: str
    label: str


@dataclass(frozen=True)
class SelectionSeparator:
    label: str


@dataclass
class DatePickerState:
    value: dt.date
    segment: int = 0
    input_buffer: str = ""
    error: str | None = None


SelectOneOption: TypeAlias = tuple[str, str] | SelectionSeparator
SelectStyle: TypeAlias = dict[str, str] | None
DATE_SEGMENTS = ("year", "month", "day")
DATE_SEGMENT_WIDTHS = (4, 2, 2)


def _clamped_date(year: int, month: int, day: int) -> dt.date:
    clamped_day = min(day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, clamped_day)


def adjust_date_segment(value: dt.date, segment: int, delta: int) -> dt.date:
    if segment == 0:
        year = max(1, min(9999, value.year + delta))
        return _clamped_date(year, value.month, value.day)
    if segment == 1:
        month_index = (value.year - 1) * 12 + (value.month - 1) + delta
        month_index = max(0, min(9999 * 12 - 1, month_index))
        year_zero_based, month_zero_based = divmod(month_index, 12)
        return _clamped_date(year_zero_based + 1, month_zero_based + 1, value.day)
    if segment == 2:
        try:
            return value + dt.timedelta(days=delta)
        except OverflowError:
            return dt.date.max if delta > 0 else dt.date.min
    raise ValueError(f"Unknown date segment: {segment}")


def replace_date_segment(value: dt.date, segment: int, replacement: int) -> dt.date:
    if segment == 0:
        if not 1 <= replacement <= 9999:
            raise ValueError("year must be between 0001 and 9999")
        return _clamped_date(replacement, value.month, value.day)
    if segment == 1:
        if not 1 <= replacement <= 12:
            raise ValueError("month must be between 01 and 12")
        return _clamped_date(value.year, replacement, value.day)
    if segment == 2:
        max_day = calendar.monthrange(value.year, value.month)[1]
        if not 1 <= replacement <= max_day:
            raise ValueError(f"day must be between 01 and {max_day:02d}")
        return dt.date(value.year, value.month, replacement)
    raise ValueError(f"Unknown date segment: {segment}")


def commit_date_buffer(state: DatePickerState) -> bool:
    if not state.input_buffer:
        state.error = None
        return True
    try:
        replacement = int(state.input_buffer)
        state.value = replace_date_segment(state.value, state.segment, replacement)
    except ValueError as exc:
        state.error = str(exc)
        return False
    state.input_buffer = ""
    state.error = None
    return True


def _date_picker_fragments(state: DatePickerState, message: str) -> list[tuple[str, str]]:
    values = (
        f"{state.value.year:04d}",
        f"{state.value.month:02d}",
        f"{state.value.day:02d}",
    )
    fragments: list[tuple[str, str]] = [("bold", f"? {message}  ")]
    for index, value in enumerate(values):
        if index:
            fragments.append(("", "-"))
        display = value
        style = ""
        if index == state.segment:
            if state.input_buffer:
                display = state.input_buffer.ljust(DATE_SEGMENT_WIDTHS[index], "_")
            style = "reverse"
            if state.error:
                style = "fg:ansired reverse"
        fragments.append((style, display))
    fragments.append(("fg:ansibrightblack", "  ←/→ field  ↑/↓ value  Enter accept"))
    if state.error:
        fragments.extend([("", "\n"), ("fg:ansired", f"  {state.error}")])
    return fragments


def _run_prompt_handlers(handlers: object, event: object) -> None:
    if not isinstance(handlers, list):
        return
    for handler in handlers:
        if not isinstance(handler, dict):
            continue
        func = handler.get("func")
        if not callable(func):
            continue
        args = handler.get("args", [])
        if not isinstance(args, list):
            args = []
        func(event, *args)


def _bind_fuzzy_submit_only(prompt: object) -> None:
    """Override fuzzy multiselect Enter to submit only selected values."""
    kb_func_lookup = getattr(prompt, "kb_func_lookup", None)
    if not isinstance(kb_func_lookup, dict):
        return

    original_answer_handlers = kb_func_lookup.get("answer")
    if not isinstance(original_answer_handlers, list):
        original_answer_handlers = []

    def _submit_only(event: object) -> None:
        try:
            from InquirerPy.base import FakeDocument
            from prompt_toolkit.validation import ValidationError
        except Exception:
            _run_prompt_handlers(original_answer_handlers, event)
            return

        try:
            validator = getattr(prompt, "_validator", None)
            result_value = list(getattr(prompt, "result_value", []))
            if validator is not None:
                validator.validate(FakeDocument(result_value))  # type: ignore[arg-type]

            selected_choices = getattr(prompt, "selected_choices", [])
            status = getattr(prompt, "status", None)
            app = getattr(event, "app", None)
            app_exit = getattr(app, "exit", None)
            if not callable(app_exit):
                _run_prompt_handlers(original_answer_handlers, event)
                return

            if isinstance(status, dict):
                status["answered"] = True
            if selected_choices:
                result_name = list(getattr(prompt, "result_name", []))
                if isinstance(status, dict):
                    status["result"] = result_name
                app_exit(result=result_value)
                return

            if isinstance(status, dict):
                status["result"] = []
            app_exit(result=[])
        except ValidationError as exc:
            set_error = getattr(prompt, "_set_error", None)
            if callable(set_error):
                set_error(str(exc))
                return
            _run_prompt_handlers(original_answer_handlers, event)
        except IndexError:
            status = getattr(prompt, "status", None)
            if isinstance(status, dict):
                status["answered"] = True
                status["result"] = []
            app = getattr(event, "app", None)
            app_exit = getattr(app, "exit", None)
            if callable(app_exit):
                app_exit(result=[])
                return
            _run_prompt_handlers(original_answer_handlers, event)
        except Exception:
            _run_prompt_handlers(original_answer_handlers, event)

    kb_func_lookup["answer"] = [{"func": _submit_only}]


def _ensure_tty() -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise SelectorUnavailableError("interactive selector requires a TTY")


def _inquirer():
    try:
        from InquirerPy import inquirer
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SelectorUnavailableError("InquirerPy unavailable") from exc
    return inquirer


@contextmanager
def _no_cpr_env():
    """Disable prompt-toolkit CPR probing for this prompt invocation."""
    previous = os.environ.get("PROMPT_TOOLKIT_NO_CPR")
    os.environ["PROMPT_TOOLKIT_NO_CPR"] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PROMPT_TOOLKIT_NO_CPR", None)
        else:
            os.environ["PROMPT_TOOLKIT_NO_CPR"] = previous


def select_one(
    title: str,
    options: list[SelectOneOption],
    *,
    default_value: str | None = None,
    style: SelectStyle = None,
) -> str | None:
    """Return selected value, None on cancel, or raise SelectorUnavailableError for fallback."""
    _ensure_tty()
    if not options:
        return None

    inquirer = _inquirer()
    try:
        resolved_style = None
        try:
            from InquirerPy.separator import Separator
        except Exception as exc:
            raise SelectorUnavailableError("InquirerPy separator support unavailable") from exc
        if style is not None:
            try:
                from InquirerPy.utils import get_style
            except Exception as exc:
                raise SelectorUnavailableError("InquirerPy style support unavailable") from exc
            resolved_style = get_style(style, style_override=False)

        choices = []
        for option in options:
            if isinstance(option, SelectionSeparator):
                choices.append(Separator(option.label))
                continue
            value, label = option
            choices.append(_SelectionOption(value=value, label=label))

        with _no_cpr_env():
            result = inquirer.select(
                message=title,
                choices=[
                    item
                    if not isinstance(item, _SelectionOption)
                    else {"name": item.label, "value": item.value}
                    for item in choices
                ],
                default=default_value,
                style=resolved_style,
                pointer=">",
                # instruction="(up/down to move, enter to select, ctrl-c to cancel)",
                vi_mode=False,
                mandatory=False,
                raise_keyboard_interrupt=True,
            ).execute()
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
    except Exception as exc:
        raise SelectorUnavailableError("selector runtime failed") from exc

    if result is None:
        return None
    return str(result)


def select_text(
    message: str,
    *,
    default_value: str = "",
    multiline: bool = False,
) -> str | None:
    """Return typed text, None on cancel, or raise SelectorUnavailableError for fallback."""
    _ensure_tty()

    inquirer = _inquirer()
    try:
        with _no_cpr_env():
            result = inquirer.text(
                message=message,
                default=default_value,
                vi_mode=False,
                mandatory=False,
                multiline=multiline,
                # A wrapped final multiline answer makes prompt-toolkit emit one
                # terminal height of whitespace. Keep wrapping while editing only.
                wrap_lines=~is_done if multiline else True,
                raise_keyboard_interrupt=True,
            ).execute()
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
    except Exception as exc:
        raise SelectorUnavailableError("selector runtime failed") from exc

    if result is None:
        return None
    return str(result)


def select_date(
    message: str,
    *,
    initial_value: dt.date | None = None,
) -> dt.date | None:
    """Return a date from a segmented prompt, or None when canceled."""
    _ensure_tty()
    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SelectorUnavailableError("prompt_toolkit date selector unavailable") from exc

    state = DatePickerState(initial_value or dt.date.today())
    key_bindings = KeyBindings()

    def _move_segment(delta: int) -> None:
        if not commit_date_buffer(state):
            return
        state.segment = (state.segment + delta) % len(DATE_SEGMENTS)

    @key_bindings.add("left")
    @key_bindings.add("s-tab")
    def _select_previous(event: object) -> None:
        _move_segment(-1)

    @key_bindings.add("right")
    @key_bindings.add("tab")
    def _select_next(event: object) -> None:
        _move_segment(1)

    @key_bindings.add("up")
    def _increment(event: object) -> None:
        if commit_date_buffer(state):
            state.value = adjust_date_segment(state.value, state.segment, 1)

    @key_bindings.add("down")
    def _decrement(event: object) -> None:
        if commit_date_buffer(state):
            state.value = adjust_date_segment(state.value, state.segment, -1)

    @key_bindings.add("backspace")
    def _backspace(event: object) -> None:
        state.input_buffer = state.input_buffer[:-1]
        state.error = None

    def _type_digit(digit: str) -> None:
        width = DATE_SEGMENT_WIDTHS[state.segment]
        if len(state.input_buffer) >= width:
            state.input_buffer = ""
        state.input_buffer += digit
        state.error = None
        if len(state.input_buffer) == width and commit_date_buffer(state):
            state.segment = (state.segment + 1) % len(DATE_SEGMENTS)

    def _digit_handler(digit: str):
        def _handler(event: object) -> None:
            _type_digit(digit)

        return _handler

    for digit in "0123456789":
        key_bindings.add(digit)(_digit_handler(digit))

    @key_bindings.add("enter")
    def _accept(event: object) -> None:
        if commit_date_buffer(state):
            event.app.exit(result=state.value)  # type: ignore[attr-defined]

    @key_bindings.add("c-c")
    @key_bindings.add("escape")
    def _cancel(event: object) -> None:
        event.app.exit(result=None)  # type: ignore[attr-defined]

    control = FormattedTextControl(
        text=lambda: _date_picker_fragments(state, message),
        focusable=True,
        show_cursor=False,
    )
    app: Application[dt.date | None] = Application(
        layout=Layout(Window(content=control, height=2)),
        key_bindings=key_bindings,
        full_screen=False,
        mouse_support=False,
    )
    try:
        with _no_cpr_env():
            result = app.run()
    except (KeyboardInterrupt, EOFError):
        return None
    except Exception as exc:
        raise SelectorUnavailableError("date selector runtime failed") from exc
    return result


def select_fuzzy(
    title: str,
    options: list[tuple[str, str]],
    *,
    default_value: str | None = None,
) -> str | None:
    """Return selected value from fuzzy prompt, None on cancel, or raise SelectorUnavailableError."""
    _ensure_tty()
    if not options:
        return None

    choices = [_SelectionOption(value=value, label=label) for value, label in options]
    inquirer = _inquirer()
    try:
        with _no_cpr_env():
            result = inquirer.fuzzy(
                message=title,
                choices=[{"name": item.label, "value": item.value} for item in choices],
                default=default_value,
                vi_mode=False,
                mandatory=False,
                raise_keyboard_interrupt=True,
            ).execute()
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
    except Exception as exc:
        raise SelectorUnavailableError("selector runtime failed") from exc

    if result is None:
        return None
    return str(result)


def select_fuzzy_many(
    title: str,
    options: list[tuple[str, str]],
    *,
    default_values: list[str] | None = None,
) -> list[str] | None:
    """Return selected values from fuzzy multiselect in source order, or None on cancel."""
    _ensure_tty()
    if not options:
        return []

    defaults = set(default_values or [])
    choices = [_SelectionOption(value=value, label=label) for value, label in options]
    inquirer = _inquirer()
    try:
        with _no_cpr_env():
            prompt = inquirer.fuzzy(
                message=title,
                choices=[
                    {
                        "name": item.label,
                        "value": item.value,
                        "enabled": item.value in defaults,
                    }
                    for item in choices
                ],
                multiselect=True,
                instruction="(space/tab to toggle, enter to submit, ctrl-c to cancel)",
                marker="[x]",
                marker_pl="[ ]",
                # InquirerPy fuzzy prompt disables space-toggle by default so users can type
                # spaces in the query; explicitly bind it for dependency multiselect UX.
                keybindings={
                    "toggle": [{"key": "space"}],
                    "toggle-down": [{"key": "c-i"}],  # tab
                    "toggle-up": [{"key": "s-tab"}],
                },
                vi_mode=False,
                mandatory=False,
                raise_keyboard_interrupt=True,
            )
            _bind_fuzzy_submit_only(prompt)
            selected = prompt.execute()
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
    except Exception as exc:
        raise SelectorUnavailableError("selector runtime failed") from exc

    if selected is None:
        return None
    selected_set = {str(value) for value in selected}
    return [item.value for item in choices if item.value in selected_set]


def select_many(
    title: str,
    options: list[tuple[str, str]],
    *,
    default_values: list[str] | None = None,
) -> list[str] | None:
    """Return selected values in source order, None on cancel, or raise SelectorUnavailableError."""
    _ensure_tty()
    if not options:
        return []

    defaults = set(default_values or [])
    choices = [_SelectionOption(value=value, label=label) for value, label in options]
    inquirer = _inquirer()
    try:
        with _no_cpr_env():
            selected = inquirer.checkbox(
                message=title,
                choices=[
                    {
                        "name": item.label,
                        "value": item.value,
                        "enabled": item.value in defaults,
                    }
                    for item in choices
                ],
                instruction="(space to toggle, enter to submit, ctrl-c to cancel)",
                vi_mode=False,
                mandatory=False,
                raise_keyboard_interrupt=True,
            ).execute()
    except KeyboardInterrupt:
        return None
    except EOFError:
        return None
    except Exception as exc:
        raise SelectorUnavailableError("selector runtime failed") from exc

    if selected is None:
        return None
    selected_set = {str(value) for value in selected}
    return [item.value for item in choices if item.value in selected_set]
