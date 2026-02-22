from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_logo_svg.py"
PACK_PATH = ROOT / "assets" / "logo" / "ascii" / "logo_pack.txt"


@pytest.fixture(scope="module")
def renderer_module():
    spec = importlib.util.spec_from_file_location("render_logo_svg", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_logo_pack_has_all_sections(renderer_module) -> None:
    sections = renderer_module.parse_logo_pack(PACK_PATH)
    assert set(renderer_module.REQUIRED_VARIANTS).issubset(set(sections.keys()))
    assert "wordmark_alta.primary" in sections
    assert "wordmark_altb.primary" in sections


def test_source_is_ascii_tab_free_and_within_width_limits(renderer_module) -> None:
    sections = renderer_module.parse_logo_pack(PACK_PATH)
    renderer_module.validate_logo_sections(sections)

    for key, lines in sections.items():
        _, variant = key.split(".", maxsplit=1)
        width_limit = renderer_module.VARIANT_WIDTH_LIMITS[variant]
        for line in lines:
            assert "\t" not in line
            assert all(ord(char) <= 127 for char in line)
            assert len(line) <= width_limit


def test_validate_rejects_invalid_lines(renderer_module) -> None:
    sections = {
        "terminal_tree.primary": ["ok"],
        "terminal_tree.compact": ["ok"],
        "wordmark.primary": ["ok"],
        "wordmark.compact": ["ok"],
        "folder_icon.primary": ["ok"],
        "folder_icon.compact": ["bad\tline"],
    }
    with pytest.raises(ValueError, match="Tab character"):
        renderer_module.validate_logo_sections(sections)

    sections["folder_icon.compact"] = ["non-ascii:\u2603"]
    with pytest.raises(ValueError, match="Non-ASCII"):
        renderer_module.validate_logo_sections(sections)

    sections["folder_icon.compact"] = ["x" * 41]
    with pytest.raises(ValueError, match="Line too wide"):
        renderer_module.validate_logo_sections(sections)


def test_svg_generation_outputs_expected_files(renderer_module, tmp_path: Path) -> None:
    sections = renderer_module.parse_logo_pack(PACK_PATH)
    renderer_module.validate_logo_sections(sections)
    selected = renderer_module.select_variants(sections, all_variants=True, variants=[])
    written = renderer_module.render_selected_variants(
        sections=sections,
        output_dir=tmp_path,
        selected_variants=selected,
    )

    assert len(written) == len(sections)
    expected_names = {f"{key.replace('.', '_')}.svg" for key in sections}
    assert {path.name for path in written} == expected_names

    for path in written:
        text = path.read_text(encoding="utf-8")
        assert text.strip()
        assert "<svg" in text
        assert 'id="panel-background"' in text
        assert "<text" in text
