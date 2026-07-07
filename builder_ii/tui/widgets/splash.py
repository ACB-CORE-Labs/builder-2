from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

ASCII_ART = """
[#00f0ff]██████╗ [#00e0ff]██╗   ██╗[#00d0ff]██╗[#00c0ff]██╗     [#00a0ff]██████╗ [#0080ff]███████╗[#0060ff]██████╗ [#0040ff]       ██╗██╗
[#00f0ff]██╔══██╗[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██╔══██╗[#0080ff]██╔════╝[#0060ff]██╔══██╗[#0040ff]█████╗ ██║██║
[#00f0ff]██████╔╝[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██║  ██║[#0080ff]█████╗  [#0060ff]██████╔╝[#0040ff]╚════╝ ██║██║
[#00f0ff]██╔══██╗[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██║  ██║[#0080ff]██╔══╝  [#0060ff]██╔══██╗[#0040ff]       ██║██║
[#00f0ff]██████╔╝[#00e0ff]╚██████╔╝[#00d0ff]██║[#00c0ff]███████╗[#00a0ff]██████╔╝[#0080ff]███████╗[#0060ff]██║  ██║[#0040ff]       ██║██║
[#00f0ff]╚═════╝ [#00e0ff] ╚═════╝ [#00d0ff]╚═╝[#00c0ff]╚══════╝[#00a0ff]╚═════╝ [#0080ff]╚══════╝[#0060ff]╚═╝  ╚═╝[#0040ff]       ╚═╝╚═╝

                  [bold white]Generic governed AI platform[/]
"""


class SplashScreen(ModalScreen[None]):
    """A splash screen that shows on startup."""

    CSS = """
    SplashScreen {
        align: center middle;
        background: rgba(13, 17, 23, 0.95);
    }
    #splash-container {
        width: auto;
        height: auto;
        padding: 2 4;
        border: heavy #58a6ff;
        background: #161b22;
        content-align: center middle;
    }
    #splash-art {
        text-align: center;
        margin-bottom: 2;
    }
    #splash-hint {
        text-align: center;
        color: #8b949e;
        text-style: italic;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="splash-container"):
            with Center():
                yield Static(ASCII_ART, id="splash-art")
            yield Static("Press any key to initialize...", id="splash-hint")

    async def on_mount(self) -> None:
        """Display the splash container."""
        container = self.query_one("#splash-container")
        container.display = True

    def on_key(self, event) -> None:
        self.dismiss(None)

    def on_mouse_down(self, event) -> None:
        self.dismiss(None)
