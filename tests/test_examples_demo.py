from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from dot_tasks.cli import app


runner = CliRunner()


def _copy_demo_tasks(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "examples" / "basic-demo" / ".tasks"
    target_root = tmp_path / "demo"
    target_root.mkdir(parents=True, exist_ok=True)
    target_tasks = target_root / ".tasks"
    shutil.copytree(source, target_tasks)
    return target_root


def test_example_demo_list_and_view_and_blocked_start(monkeypatch, tmp_path: Path) -> None:
    demo_root = _copy_demo_tasks(tmp_path)
    monkeypatch.chdir(demo_root)

    listed = runner.invoke(app, ["list"])
    assert listed.exit_code == 0
    assert "build-nightly-report" in listed.output
    assert "blocked(1)" in listed.output

    viewed = runner.invoke(app, ["view", "build-nightly-report"])
    assert viewed.exit_code == 0
    assert "build-nightly-report (t-20260206-001)" in viewed.output
    assert "[todo] [p0] [l] [deps: blocked(1)]" in viewed.output
    assert "depends_on: add-json-export (t-20260205-001) [todo]" in viewed.output

    blocked = runner.invoke(app, ["start", "build-nightly-report"])
    assert blocked.exit_code == 1
    assert "Unmet dependencies: t-20260205-001" in blocked.output
