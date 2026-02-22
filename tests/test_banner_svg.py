from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "render_banner_svg.py"
BANNER_PATH = ROOT / "assets" / "banner.txt"
README_PATH = ROOT / "README.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("render_banner_svg", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_banner_svg_generation(tmp_path: Path) -> None:
    module = _load_module()
    output_dark = tmp_path / "banner-dark.svg"
    output_light = tmp_path / "banner-light.svg"
    dark_path, light_path = module.render_banner_pair(
        input_path=BANNER_PATH,
        output_dark=output_dark,
        output_light=output_light,
    )
    assert dark_path == output_dark
    assert light_path == output_light
    assert output_dark.exists()
    assert output_light.exists()
    assert output_dark.read_text(encoding="utf-8").strip()
    assert output_light.read_text(encoding="utf-8").strip()


def test_banner_svg_structure(tmp_path: Path) -> None:
    module = _load_module()
    output_dark = tmp_path / "banner-dark.svg"
    output_light = tmp_path / "banner-light.svg"
    module.render_banner_pair(
        input_path=BANNER_PATH,
        output_dark=output_dark,
        output_light=output_light,
    )
    dark_text = output_dark.read_text(encoding="utf-8")
    light_text = output_light.read_text(encoding="utf-8")
    for text in (dark_text, light_text):
        assert "<svg" in text
        assert 'xml:space="preserve"' in text
        assert "<text" in text
        assert "<tspan" in text


def test_readme_picture_block_present() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    expected_prefix = (
        "<p align=\"center\">\n"
        "  <picture>\n"
        "    <source srcset=\"assets/logo/svg/banner-dark.svg\" media=\"(prefers-color-scheme: dark)\">\n"
        "    <source srcset=\"assets/logo/svg/banner-light.svg\" media=\"(prefers-color-scheme: light)\">\n"
        "    <img src=\"assets/logo/svg/banner-light.svg\" alt=\"dot-tasks logo\">\n"
        "  </picture>\n"
        "</p>\n\n"
        "# dot-tasks\n"
    )
    assert readme.startswith(expected_prefix)


def test_banner_dimensions_stable() -> None:
    module = _load_module()
    lines = module.load_banner_lines(BANNER_PATH)
    width, height = module.compute_canvas_dimensions(
        lines,
        char_width=module.DEFAULT_CHAR_WIDTH,
        line_height=module.DEFAULT_LINE_HEIGHT,
    )
    assert width > 0
    assert height > 0

    expected_width = math.ceil((max(len(line) for line in lines) * module.DEFAULT_CHAR_WIDTH) + (2 * module.DEFAULT_PADDING_X))
    expected_height = math.ceil((len(lines) * module.DEFAULT_LINE_HEIGHT) + (2 * module.DEFAULT_PADDING_Y) + module.DEFAULT_TITLE_BAR_HEIGHT)
    assert width == expected_width
    assert height == expected_height

    shorter_width, _ = module.compute_canvas_dimensions(
        ["banner"],
        char_width=module.DEFAULT_CHAR_WIDTH,
        line_height=module.DEFAULT_LINE_HEIGHT,
    )
    assert width > shorter_width
