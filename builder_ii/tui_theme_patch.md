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
| `chargers` | `#FFC20E` bolt gold | `#FFC20E` bolt gold | `#FFC20E` bolt gold | `#0080C6` powder blue |

## Swatch

```
Chargers palette
  app bg        ████  #0080C6  Powder Blue
  panel         ████  #002244  Navy
  panel-light   ████  #003366  Lighter Navy
  hover         ████  #004080  Navy Hover
  pass/warn     ████  #FFC20E  Bolt Gold
  fail          ████  #F85149  Red (universal danger, unchanged)
  active/bold   ████  #FFFFFF  White
  hint          ████  #80CFFF  Light Blue
  dim/border    ████  #0080C6  Powder Blue
```

## Design decisions

- `fail` is kept red across all themes. Red = danger is a universal convention
  that should not be overridden by brand colour.
- Verified/success glyphs use Bolt Gold in the Chargers theme to preserve the
  lightning-bolt read while keeping failure red and HITL/warning states visible.
- Navy (#002244) is used for floating panels. Powder Blue (#0080C6) is used for
  the app field, selected state, dim token, and panel border. This keeps the
  8-token contract clean while still letting the TUI consume extended surface
  tokens through `theme_extras()`.
- Light/Powder Blue surfaces naturally as `hint` and `dim` — the same structural
  role muted/secondary colors play in the default theme.
