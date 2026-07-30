from __future__ import annotations

import datetime as dt

from dot_tasks.selector_ui import (
    DatePickerState,
    adjust_date_segment,
    commit_date_buffer,
    replace_date_segment,
)


def test_adjust_day_crosses_month_and_year_boundaries() -> None:
    assert adjust_date_segment(dt.date(2026, 12, 31), 2, 1) == dt.date(2027, 1, 1)
    assert adjust_date_segment(dt.date(2026, 1, 1), 2, -1) == dt.date(2025, 12, 31)


def test_adjust_month_clamps_day_and_crosses_year() -> None:
    assert adjust_date_segment(dt.date(2024, 1, 31), 1, 1) == dt.date(2024, 2, 29)
    assert adjust_date_segment(dt.date(2026, 12, 31), 1, 1) == dt.date(2027, 1, 31)


def test_adjust_year_clamps_leap_day() -> None:
    assert adjust_date_segment(dt.date(2024, 2, 29), 0, 1) == dt.date(2025, 2, 28)


def test_replace_date_segment_validates_selected_field() -> None:
    assert replace_date_segment(dt.date(2026, 7, 29), 1, 2) == dt.date(2026, 2, 28)

    try:
        replace_date_segment(dt.date(2026, 7, 29), 1, 13)
    except ValueError as exc:
        assert "month" in str(exc)
    else:
        raise AssertionError("invalid month accepted")


def test_commit_date_buffer_keeps_invalid_input_editable() -> None:
    state = DatePickerState(
        value=dt.date(2026, 7, 29),
        segment=1,
        input_buffer="13",
    )

    assert commit_date_buffer(state) is False
    assert state.value == dt.date(2026, 7, 29)
    assert state.input_buffer == "13"
    assert state.error == "month must be between 01 and 12"


def test_commit_date_buffer_applies_valid_replacement() -> None:
    state = DatePickerState(
        value=dt.date(2026, 7, 29),
        segment=2,
        input_buffer="03",
    )

    assert commit_date_buffer(state) is True
    assert state.value == dt.date(2026, 7, 3)
    assert state.input_buffer == ""
    assert state.error is None
