# dot-tasks Logo Assets

This directory contains the reusable ASCII-style logo pack for `dot-tasks`.

## Source of Truth

- ASCII source: `/Users/awni/Documents/project-code/dot-tasks/assets/logo/ascii/logo_pack.txt`
- Renderer: `/Users/awni/Documents/project-code/dot-tasks/scripts/render_logo_svg.py`
- Generated outputs: `/Users/awni/Documents/project-code/dot-tasks/assets/logo/svg/*.svg`

## Variants

Naming convention:

- `<family>_<variant>.svg`
- Families: `terminal_tree`, `wordmark`, `wordmark_alta`, `wordmark_altb`, `folder_icon`
- Variants: `primary` (max line width 60), `compact` (max line width 40)

Wordmark variants now render `.tasks/` as the label (not `dot-tasks`).

## Regeneration

Render all variants:

```bash
python /Users/awni/Documents/project-code/dot-tasks/scripts/render_logo_svg.py --all
```

Render a single variant:

```bash
python /Users/awni/Documents/project-code/dot-tasks/scripts/render_logo_svg.py --variant terminal_tree.primary
```

Render the dual-theme README banner from `/Users/awni/Documents/project-code/dot-tasks/assets/banner.txt`:

```bash
python /Users/awni/Documents/project-code/dot-tasks/scripts/render_banner_svg.py
```

Banner outputs:

- `/Users/awni/Documents/project-code/dot-tasks/assets/logo/svg/banner-dark.svg`
- `/Users/awni/Documents/project-code/dot-tasks/assets/logo/svg/banner-light.svg`

## Dimensions and Style

- Deterministic layout using fixed character cell metrics.
- Dark terminal panel with subtle window chrome and monospace text.
- Strict ASCII validation on source art (no tabs, no non-ASCII characters).

## Hero Candidate (for later README integration)

Start with `terminal_tree_primary.svg` as the likely top-of-README hero, then select after visual review.
