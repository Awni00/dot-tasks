#!/usr/bin/env python3
"""Render assets/banner.txt into theme-aware SVG banner assets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from html import escape
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "assets" / "banner.txt"
DEFAULT_OUTPUT_DARK = ROOT / "assets" / "logo" / "svg" / "banner-dark.svg"
DEFAULT_OUTPUT_LIGHT = ROOT / "assets" / "logo" / "svg" / "banner-light.svg"

DEFAULT_FONT_SIZE = 14.0
DEFAULT_CHAR_WIDTH = 8.6
DEFAULT_LINE_HEIGHT = 18.0
DEFAULT_PADDING_X = 24.0
DEFAULT_PADDING_Y = 18.0
DEFAULT_TITLE_BAR_HEIGHT = 30.0
DEFAULT_CORNER_RADIUS = 14


@dataclass(frozen=True)
class BannerTheme:
    panel_fill: str
    panel_stroke: str
    title_fill: str
    text_fill: str
    dot_red: str
    dot_yellow: str
    dot_green: str


THEMES = {
    "dark": BannerTheme(
        panel_fill="#0f172a",
        panel_stroke="#263447",
        title_fill="#111827",
        text_fill="#e5f0ff",
        dot_red="#f87171",
        dot_yellow="#fbbf24",
        dot_green="#34d399",
    ),
    "light": BannerTheme(
        panel_fill="#f8fafc",
        panel_stroke="#cbd5e1",
        title_fill="#eef2f7",
        text_fill="#0f172a",
        dot_red="#ef4444",
        dot_yellow="#f59e0b",
        dot_green="#10b981",
    ),
}


def load_banner_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("input banner is empty")
    if not any(line.strip() for line in lines):
        raise ValueError("input banner has no visible content")
    return lines


def compute_canvas_dimensions(
    lines: list[str],
    *,
    char_width: float,
    line_height: float,
    padding_x: float = DEFAULT_PADDING_X,
    padding_y: float = DEFAULT_PADDING_Y,
    title_bar_height: float = DEFAULT_TITLE_BAR_HEIGHT,
) -> tuple[int, int]:
    max_chars = max(len(line) for line in lines)
    width = math.ceil(max_chars * char_width + (2 * padding_x))
    height = math.ceil(len(lines) * line_height + (2 * padding_y) + title_bar_height)
    return width, height


def build_svg_markup(
    lines: list[str],
    *,
    theme: BannerTheme,
    title: str,
    font_size: float,
    char_width: float,
    line_height: float,
    padding_x: float = DEFAULT_PADDING_X,
    padding_y: float = DEFAULT_PADDING_Y,
    title_bar_height: float = DEFAULT_TITLE_BAR_HEIGHT,
) -> str:
    width, height = compute_canvas_dimensions(
        lines,
        char_width=char_width,
        line_height=line_height,
        padding_x=padding_x,
        padding_y=padding_y,
        title_bar_height=title_bar_height,
    )
    text_x = padding_x
    text_y = title_bar_height + padding_y

    tspans: list[str] = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(line_height)
        tspans.append(f'    <tspan x="{text_x}" dy="{dy}">{escape(line) if line else " "}</tspan>')

    markup_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" role="img"',
        f'     width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"  <title>{escape(title)}</title>",
        '  <g id="panel-background">',
        (
            f'    <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
            f'rx="{DEFAULT_CORNER_RADIUS}" fill="{theme.panel_fill}" '
            f'stroke="{theme.panel_stroke}" stroke-width="1"/>'
        ),
        '  </g>',
        '  <g id="terminal-chrome">',
        (
            f'    <rect x="1" y="1" width="{width - 2}" height="{title_bar_height}" '
            f'rx="{DEFAULT_CORNER_RADIUS - 1}" fill="{theme.title_fill}"/>'
        ),
        f'    <circle cx="16" cy="16" r="4" fill="{theme.dot_red}"/>',
        f'    <circle cx="30" cy="16" r="4" fill="{theme.dot_yellow}"/>',
        f'    <circle cx="44" cy="16" r="4" fill="{theme.dot_green}"/>',
        "  </g>",
        (
            '  <text id="banner-text" xml:space="preserve" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace" '
            f'font-size="{font_size}" fill="{theme.text_fill}" y="{text_y}">'
        ),
        *tspans,
        "  </text>",
        "</svg>",
    ]
    return "\n".join(markup_lines) + "\n"


def render_banner_pair(
    *,
    input_path: Path,
    output_dark: Path,
    output_light: Path,
    font_size: float = DEFAULT_FONT_SIZE,
    char_width: float = DEFAULT_CHAR_WIDTH,
    line_height: float = DEFAULT_LINE_HEIGHT,
) -> tuple[Path, Path]:
    lines = load_banner_lines(input_path)
    dark_markup = build_svg_markup(
        lines,
        theme=THEMES["dark"],
        title="dot-tasks banner (dark)",
        font_size=font_size,
        char_width=char_width,
        line_height=line_height,
    )
    light_markup = build_svg_markup(
        lines,
        theme=THEMES["light"],
        title="dot-tasks banner (light)",
        font_size=font_size,
        char_width=char_width,
        line_height=line_height,
    )

    output_dark.parent.mkdir(parents=True, exist_ok=True)
    output_light.parent.mkdir(parents=True, exist_ok=True)
    output_dark.write_text(dark_markup, encoding="utf-8")
    output_light.write_text(light_markup, encoding="utf-8")
    return output_dark, output_light


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render dual-theme banner SVGs from assets/banner.txt")
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Path to input banner text (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output-dark",
        type=Path,
        default=DEFAULT_OUTPUT_DARK,
        help=f"Path to dark theme SVG (default: {DEFAULT_OUTPUT_DARK})",
    )
    parser.add_argument(
        "--output-light",
        type=Path,
        default=DEFAULT_OUTPUT_LIGHT,
        help=f"Path to light theme SVG (default: {DEFAULT_OUTPUT_LIGHT})",
    )
    parser.add_argument(
        "--font-size",
        type=float,
        default=DEFAULT_FONT_SIZE,
        help=f"Font size in pixels (default: {DEFAULT_FONT_SIZE})",
    )
    parser.add_argument(
        "--char-width",
        type=float,
        default=DEFAULT_CHAR_WIDTH,
        help=f"Average monospace character width (default: {DEFAULT_CHAR_WIDTH})",
    )
    parser.add_argument(
        "--line-height",
        type=float,
        default=DEFAULT_LINE_HEIGHT,
        help=f"Line height in pixels (default: {DEFAULT_LINE_HEIGHT})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        dark_path, light_path = render_banner_pair(
            input_path=args.input,
            output_dark=args.output_dark,
            output_light=args.output_light,
            font_size=args.font_size,
            char_width=args.char_width,
            line_height=args.line_height,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(dark_path)
    print(light_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
