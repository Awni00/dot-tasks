#!/usr/bin/env python3
"""Render ASCII logo variants into SVG assets."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK_PATH = ROOT / "assets" / "logo" / "ascii" / "logo_pack.txt"
DEFAULT_OUTPUT_DIR = ROOT / "assets" / "logo" / "svg"

VARIANT_WIDTH_LIMITS = {
    "primary": 60,
    "compact": 40,
}

REQUIRED_VARIANTS = [
    "terminal_tree.primary",
    "terminal_tree.compact",
    "wordmark.primary",
    "wordmark.compact",
    "folder_icon.primary",
    "folder_icon.compact",
]

SECTION_PATTERN = re.compile(r"^\[([a-z_]+)\.(primary|compact)\]$")

# Deterministic text metrics.
CHAR_WIDTH = 9
LINE_HEIGHT = 18
PADDING_X = 24
PADDING_Y = 18
TITLE_BAR_HEIGHT = 30
CORNER_RADIUS = 14


def parse_logo_pack(path: Path) -> dict[str, list[str]]:
    """Parse sectioned ASCII logos from a plain-text pack file."""
    sections: dict[str, list[str]] = {}
    current_key: str | None = None

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = SECTION_PATTERN.match(raw_line)
        if match:
            current_key = f"{match.group(1)}.{match.group(2)}"
            if current_key in sections:
                raise ValueError(f"Duplicate section '{current_key}' at line {line_number}")
            sections[current_key] = []
            continue

        if current_key is None:
            if raw_line.strip() == "":
                continue
            raise ValueError(f"Content before first section at line {line_number}")

        sections[current_key].append(raw_line)

    return sections


def _check_ascii(line: str, key: str, line_index: int) -> None:
    for char in line:
        if ord(char) > 127:
            raise ValueError(
                f"Non-ASCII character in section '{key}' line {line_index}: {char!r}"
            )


def validate_logo_sections(sections: dict[str, list[str]]) -> None:
    """Validate required sections and line constraints."""
    section_keys = set(sections)
    expected_keys = set(REQUIRED_VARIANTS)

    missing = sorted(expected_keys - section_keys)
    if missing:
        raise ValueError(f"Missing required sections: {', '.join(missing)}")

    for key, lines in sections.items():
        if not lines:
            raise ValueError(f"Section '{key}' has no content")

        _, variant = key.split(".", maxsplit=1)
        width_limit = VARIANT_WIDTH_LIMITS[variant]

        for index, line in enumerate(lines, start=1):
            if "\t" in line:
                raise ValueError(f"Tab character in section '{key}' line {index}")
            _check_ascii(line, key, index)
            if len(line) > width_limit:
                raise ValueError(
                    f"Line too wide in section '{key}' line {index}: "
                    f"{len(line)} > {width_limit}"
                )


def _build_svg_markup(title: str, lines: list[str]) -> str:
    max_chars = max(len(line) for line in lines)
    text_block_width = max_chars * CHAR_WIDTH
    text_block_height = len(lines) * LINE_HEIGHT

    width = PADDING_X * 2 + text_block_width
    height = TITLE_BAR_HEIGHT + PADDING_Y * 2 + text_block_height
    text_x = PADDING_X
    text_y = TITLE_BAR_HEIGHT + PADDING_Y

    tspans = []
    for index, line in enumerate(lines):
        dy = "0" if index == 0 else str(LINE_HEIGHT)
        display_text = escape(line) if line else " "
        tspans.append(f'    <tspan x="{text_x}" dy="{dy}">{display_text}</tspan>')

    escaped_title = escape(title)

    svg_lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" role="img"',
        f'     width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'  <title>{escaped_title}</title>',
        '  <g id="panel-background">',
        (
            f'    <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" '
            f'rx="{CORNER_RADIUS}" fill="#0f172a" stroke="#263447" stroke-width="1"/>'
        ),
        '  </g>',
        '  <g id="terminal-chrome">',
        (
            f'    <rect x="1" y="1" width="{width - 2}" height="{TITLE_BAR_HEIGHT}" '
            f'rx="{CORNER_RADIUS - 1}" fill="#111827"/>'
        ),
        '    <circle cx="16" cy="16" r="4" fill="#f87171"/>',
        '    <circle cx="30" cy="16" r="4" fill="#fbbf24"/>',
        '    <circle cx="44" cy="16" r="4" fill="#34d399"/>',
        '  </g>',
        (
            '  <text id="logo-text" xml:space="preserve" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, Liberation Mono, monospace" '
            'font-size="14" fill="#d1fae5" y="{}">'.format(text_y)
        ),
        *tspans,
        '  </text>',
        '</svg>',
    ]

    return "\n".join(svg_lines) + "\n"


def render_variant(key: str, lines: list[str], output_dir: Path) -> Path:
    """Render one variant to output directory and return file path."""
    family, variant = key.split(".", maxsplit=1)
    output_path = output_dir / f"{family}_{variant}.svg"
    title = f"dot-tasks logo: {family} ({variant})"
    markup = _build_svg_markup(title=title, lines=lines)
    output_path.write_text(markup, encoding="utf-8")
    return output_path


def select_variants(sections: dict[str, list[str]], all_variants: bool, variants: Iterable[str]) -> list[str]:
    requested = list(variants)
    if all_variants:
        requested.extend(sections.keys())

    if not requested:
        raise ValueError("Specify --all or at least one --variant <family.variant>")

    deduped = []
    seen = set()
    for key in requested:
        if key in seen:
            continue
        if key not in sections:
            raise ValueError(f"Unknown variant '{key}'")
        seen.add(key)
        deduped.append(key)
    return deduped


def render_selected_variants(
    sections: dict[str, list[str]],
    output_dir: Path,
    selected_variants: list[str],
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key in selected_variants:
        written.append(render_variant(key, sections[key], output_dir))
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render dot-tasks ASCII logos to SVG")
    parser.add_argument("--all", action="store_true", help="Render all variants")
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        metavar="FAMILY.VARIANT",
        help="Render only selected variants (repeatable)",
    )
    parser.add_argument(
        "--pack-path",
        type=Path,
        default=DEFAULT_PACK_PATH,
        help=f"Path to ASCII source file (default: {DEFAULT_PACK_PATH})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for SVG files (default: {DEFAULT_OUTPUT_DIR})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sections = parse_logo_pack(args.pack_path)
    validate_logo_sections(sections)

    selected = select_variants(sections, all_variants=args.all, variants=args.variant)
    written_paths = render_selected_variants(sections, output_dir=args.output_dir, selected_variants=selected)

    for path in written_paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
