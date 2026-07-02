# Theme Wiring Patch Notes

## What changed

### `tui.py`
- `_C` dict is now populated from `tui_theme.theme_palette()` at module load.
- Section rule and panel border helpers delegate to `tui_theme`.
- New `builder theme` Typer subcommand: `show` and `list`.

### `agent_tui.py` + `hitl_tui.py`
- ANSI-mode `_c()` helpers now pull hex values from `tui_theme.theme_palette()`
  when the module is available, falling back to original hard-coded values if not.
- Non-TTY / pipe path is unchanged (no ANSI ever emitted).

## How to activate

```bash
export BUILDER_THEME=chargers   # powder blue / bolt gold
export BUILDER_THEME=default    # original slate/indigo (default when unset)
```

## Available themes

| Theme      | pass         | warn         | accent       | border  |
|------------|-------------|-------------|-------------|--------|
| `default`  | `#4ade80` green | `#fbbf24` amber | `#818cf8` indigo | `#475569` slate |
| `chargers` | `#0080C6` powder blue | `#FFC20E` bolt gold | `#FFC20E` bolt gold | `#002244` navy |

## Swatch

```
Chargers palette
  pass/active   ████  #0080C6  Powder Blue
  warn/accent   ████  #FFC20E  Bolt Gold
  fail          ████  #f87171  Red (universal danger, unchanged)
  bold          ████  #FFFFFF  White
  hint          ████  #3399CC  Muted Blue
  dim           ████  #005A8E  Deep Blue
  _navy (border)████  #002244  Navy
```

## Design decisions

- `fail` is kept red across all themes. Red = danger is a universal convention
  that should not be overridden by brand colour.
- `pass` and `active` share Powder Blue in the Chargers theme intentionally;
  the glyph (●/◆) carries the semantic distinction, not colour alone.
- Navy (#002244) is an *extended* token (`_navy`), not a core token. It appears
  only as panel borders and section rules via `theme_panel_border()`. This keeps
  the 8-token contract clean while still using the full Chargers palette.
- Blue (#3399CC / #005A8E) surfaces naturally as `hint` and `dim` — the same
  structural role they play in the default theme.
