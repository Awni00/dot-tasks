"""Arrow-key selector helpers backed by InquirerPy."""

from __future__ import annotations

from dataclasses import dataclass
import sys


class SelectorUnavailableError(RuntimeError):
    """Raised when arrow-key selector UI cannot be used."""


@dataclass(frozen=True)
class _SelectionOption:
    value: str
    label: str


def _ensure_tty() -> None:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise SelectorUnavailableError("interactive selector requires a TTY")


def _inquirer():
    try:
        from InquirerPy import inquirer
    except Exception as exc:  # pragma: no cover - environment dependent
        raise SelectorUnavailableError("InquirerPy unavailable") from exc
    return inquirer


def select_one(
    title: str,
    options: list[tuple[str, str]],
    *,
    default_value: str | None = None,
) -> str | None:
    """Return selected value, None on cancel, or raise SelectorUnavailableError for fallback."""
    _ensure_tty()
    if not options:
        return None

    choices = [_SelectionOption(value=value, label=label) for value, label in options]
    inquirer = _inquirer()
    try:
        result = inquirer.select(
            message=title,
            choices=[{"name": item.label, "value": item.value} for item in choices],
            default=default_value,
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
        selected = inquirer.fuzzy(
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
