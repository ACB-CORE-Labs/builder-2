"""STRATUM opening splash — hero artwork, brief hold, then console.

Shows ``images/builder-ii-splash-hero.jpeg`` when available (rich-pixels / PIL),
otherwise the BUILDER-II ASCII mark. Auto-dismisses after ~3 seconds; any key
or click dismisses early.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Static

SPLASH_HOLD_SECONDS = 3.0
HERO_RELATIVE = Path("images") / "builder-ii-splash-hero.jpeg"
# Terminal cells for the hero (rich-pixels uses ~2 vertical pixels per cell)
HERO_MAX_WIDTH = 72
HERO_MAX_HEIGHT = 20

ASCII_ART = """
[#00f0ff]██████╗ [#00e0ff]██╗   ██╗[#00d0ff]██╗[#00c0ff]██╗     [#00a0ff]██████╗ [#0080ff]███████╗[#0060ff]██████╗ [#0040ff]       ██╗██╗
[#00f0ff]██╔══██╗[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██╔══██╗[#0080ff]██╔════╝[#0060ff]██╔══██╗[#0040ff]█████╗ ██║██║
[#00f0ff]██████╔╝[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██║  ██║[#0080ff]█████╗  [#0060ff]██████╔╝[#0040ff]╚════╝ ██║██║
[#00f0ff]██╔══██╗[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██║  ██║[#0080ff]██╔══╝  [#0060ff]██╔══██╗[#0040ff]       ██║██║
[#00f0ff]██████╔╝[#00e0ff]╚██████╔╝[#00d0ff]██║[#00c0ff]███████╗[#00a0ff]██████╔╝[#0080ff]███████╗[#0060ff]██║  ██║[#0040ff]       ██║██║
[#00f0ff]╚═════╝ [#00e0ff] ╚═════╝ [#00d0ff]╚═╝[#00c0ff]╚══════╝[#00a0ff]╚═════╝ [#0080ff]╚══════╝[#0060ff]╚═╝  ╚═╝[#0040ff]       ╚═╝╚═╝

                  [bold white]Generic governed AI platform[/]
"""


def resolve_hero_path(project_root: Path | None = None) -> Path | None:
    """Locate splash hero image relative to project root or this package's repo."""
    candidates: list[Path] = []
    if project_root is not None:
        candidates.append(Path(project_root) / HERO_RELATIVE)
    here = Path(__file__).resolve()
    # builder_ii/tui/widgets/splash.py → parents[3] is repo root
    candidates.append(here.parents[3] / HERO_RELATIVE)
    candidates.append(here.parents[2].parent / HERO_RELATIVE)
    candidates.append(Path.cwd() / HERO_RELATIVE)
    for path in candidates:
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def load_hero_renderable(path: Path) -> Any | None:
    """Return a Rich renderable for the hero image, or None."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("RGB")
    except OSError:
        return None

    img.thumbnail((HERO_MAX_WIDTH, HERO_MAX_HEIGHT * 2), Image.Resampling.LANCZOS)

    try:
        from rich_pixels import Pixels

        return Pixels.from_image(img)
    except Exception:
        pass

    # Fallback: half-block ANSI markup string
    return _halfblock_markup(img)


def _halfblock_markup(img: Any) -> str:
    w, h = img.size
    if h % 2 == 1:
        h -= 1
        img = img.crop((0, 0, w, h))
    pixels = img.load()
    lines: list[str] = []
    for y in range(0, h, 2):
        parts: list[str] = []
        for x in range(w):
            r1, g1, b1 = pixels[x, y]
            r2, g2, b2 = pixels[x, y + 1] if y + 1 < h else (0, 0, 0)
            parts.append(f"[rgb({r1},{g1},{b1}) on rgb({r2},{g2},{b2})]▀[/]")
        lines.append("".join(parts))
    return "\n".join(lines)


class SplashArt(Static):
    """Renders hero image renderable or ASCII markup."""

    def __init__(self, content: Any, *, use_markup: bool, **kwargs: Any) -> None:
        super().__init__(id="splash-art", **kwargs)
        self._content = content
        self._use_markup = use_markup

    def render(self) -> Any:
        return self._content


class SplashScreen(ModalScreen[None]):
    """Opening splash: hero image (or ASCII), ~3s hold, any key skips."""

    CSS = """
    SplashScreen {
        align: center middle;
        background: rgba(10, 14, 20, 0.97);
    }
    #splash-container {
        width: auto;
        max-width: 94%;
        height: auto;
        max-height: 94%;
        padding: 1 2;
        border: heavy #79c0ff;
        background: #0d1117;
        content-align: center middle;
    }
    #splash-art {
        text-align: center;
        margin-bottom: 1;
        height: auto;
        max-height: 22;
    }
    #splash-tag {
        text-align: center;
        color: #c9d1d9;
        text-style: bold;
    }
    #splash-hint {
        text-align: center;
        color: #6e7681;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(self, project_root: Path | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._project_root = project_root
        self._dismiss_timer: Timer | None = None
        self._closed = False

    def compose(self) -> ComposeResult:
        hero_path = resolve_hero_path(self._project_root)
        renderable: Any = None
        if hero_path is not None:
            renderable = load_hero_renderable(hero_path)

        with Vertical(id="splash-container"):
            with Center():
                if renderable is not None:
                    # Pixels / str both work via SplashArt.render
                    use_markup = isinstance(renderable, str)
                    art = SplashArt(renderable, use_markup=use_markup)
                    if use_markup:
                        # Static markup path for half-block fallback
                        yield Static(renderable, id="splash-art", markup=True)
                    else:
                        yield art
                else:
                    yield Static(ASCII_ART, id="splash-art", markup=True)
            yield Static("builder-II  ·  governed local control plane", id="splash-tag")
            yield Static(
                f"STRATUM starting…  ({int(SPLASH_HOLD_SECONDS)}s · any key to skip)",
                id="splash-hint",
            )

    def on_mount(self) -> None:
        self._dismiss_timer = self.set_timer(SPLASH_HOLD_SECONDS, self._auto_dismiss)

    def _auto_dismiss(self) -> None:
        self._close()

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
            self._dismiss_timer = None
        self.dismiss(None)

    def on_key(self, event: Any) -> None:
        event.stop()
        self._close()

    def on_mouse_down(self, event: Any) -> None:
        event.stop()
        self._close()
