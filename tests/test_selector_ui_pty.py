from __future__ import annotations

import errno
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import time

import pytest


def _read_until(fd: int, needle: bytes, timeout: float = 5.0) -> bytes:
    output = bytearray()
    deadline = time.monotonic() + timeout
    while needle not in output:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise AssertionError(f"timed out waiting for {needle!r}; output={bytes(output)!r}")
        output.extend(os.read(fd, 4096))
    return bytes(output)


def _read_to_exit(fd: int, process: subprocess.Popen[bytes], timeout: float = 5.0) -> bytes:
    output = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        readable = select.select([fd], [], [], 0.05)[0]
        if readable:
            try:
                chunk = os.read(fd, 4096)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                break
            if not chunk:
                break
            output.extend(chunk)
        elif process.poll() is not None:
            break
    else:
        process.kill()
        process.wait()
        raise AssertionError("interactive prompt did not exit")
    process.wait(timeout=1)
    return bytes(output)


@pytest.mark.skipif(os.name != "posix", reason="requires a POSIX pseudo-terminal")
@pytest.mark.parametrize(
    ("rows", "columns", "answer"),
    [
        (12, 40, "12345678"),
        (7, 20, "a short summary"),
        (24, 80, "x" * 60),
        (12, 40, "first\nsecond line"),
        (12, 30, "界" * 10),
        (12, 80, "a short summary"),
    ],
)
def test_multiline_text_submit_does_not_emit_terminal_height_whitespace(
    rows: int,
    columns: int,
    answer: str,
) -> None:
    # Purpose: reproduce the real renderer bug where an exact/wrapped answered line emits one blank terminal height.
    import fcntl
    import pty
    import termios

    master_fd, slave_fd = pty.openpty()
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))
    env = os.environ.copy()
    env.update({"TERM": "xterm-256color", "TERM_PROGRAM": "vscode"})
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, env.get("PYTHONPATH")) if value
    )
    script = (
        "from dot_tasks.selector_ui import select_text; "
        "print('RESULT', repr(select_text('Summary (Esc+Enter to submit)', "
        "default_value='- TODO', multiline=True)))"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
    )
    os.close(slave_fd)
    try:
        _read_until(master_fd, b"Summary")
        entered_answer = answer.replace("\n", "\r").encode()
        os.write(master_fd, b"\x01\x0b" + entered_answer + b"\x1b\r")
        output = _read_to_exit(master_fd, process)
    finally:
        os.close(master_fd)
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 0
    assert f"RESULT {answer!r}".encode() in output
    assert output.count(b"\n") < rows


@pytest.mark.skipif(os.name != "posix", reason="requires a POSIX pseudo-terminal")
def test_segmented_date_picker_handles_arrow_navigation() -> None:
    import fcntl
    import pty
    import termios

    master_fd, slave_fd = pty.openpty()
    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 8, 80, 0, 0))
    env = os.environ.copy()
    env.update({"TERM": "xterm-256color", "TERM_PROGRAM": "vscode"})
    source_root = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        value for value in (source_root, env.get("PYTHONPATH")) if value
    )
    script = (
        "import datetime as dt; "
        "from dot_tasks.selector_ui import select_date; "
        "result = select_date('due_date', initial_value=dt.date(2026, 7, 29)); "
        "print('RESULT', result.isoformat() if result else None)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
    )
    os.close(slave_fd)
    try:
        _read_until(master_fd, b"due_date")
        # Select month, increment it, select day, decrement it, and submit.
        os.write(master_fd, b"\x1b[C\x1b[A\x1b[C\x1b[B\r")
        output = _read_to_exit(master_fd, process)
    finally:
        os.close(master_fd)
        if process.poll() is None:
            process.kill()
            process.wait()

    assert process.returncode == 0
    assert b"RESULT 2026-08-28" in output
