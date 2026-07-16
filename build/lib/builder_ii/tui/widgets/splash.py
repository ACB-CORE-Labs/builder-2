"""STRATUM opening splash.

On macOS with the Swift toolchain available, floats the real hero JPEG
(``images/builder-ii-splash-hero.jpeg``) in a borderless Cocoa window for a few
seconds — full image quality, same idea as the original splash.

Otherwise shows the ASCII BUILDER-II mark inside the terminal (no low-res
terminal pixel mosaic unless ``BUILDER_SPLASH_TERMINAL_IMAGE=1``).

Any key / click dismisses early after the native window has closed (or immediately
on the ASCII path).
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import tempfile
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.timer import Timer
from textual.widgets import Static

# Native window hold (matches original ~4s feel; slightly shorter for snappier start)
SPLASH_HOLD_SECONDS = 3.5
HERO_RELATIVE = Path("images") / "builder-ii-splash-hero.jpeg"
ENV_FORCE_TERMINAL = "BUILDER_SPLASH_TERMINAL_IMAGE"
ENV_DISABLE_NATIVE = "BUILDER_SPLASH_NATIVE"  # set to 0/false/no to skip Cocoa

ASCII_ART = """
[#00f0ff]██████╗ [#00e0ff]██╗   ██╗[#00d0ff]██╗[#00c0ff]██╗     [#00a0ff]██████╗ [#0080ff]███████╗[#0060ff]██████╗ [#0040ff]       ██╗██╗
[#00f0ff]██╔══██╗[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██╔══██╗[#0080ff]██╔════╝[#0060ff]██╔══██╗[#0040ff]█████╗ ██║██║
[#00f0ff]██████╔╝[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██║  ██║[#0080ff]█████╗  [#0060ff]██████╔╝[#0040ff]╚════╝ ██║██║
[#00f0ff]██╔══██╗[#00e0ff]██║   ██║[#00d0ff]██║[#00c0ff]██║     [#00a0ff]██║  ██║[#0080ff]██╔══╝  [#0060ff]██╔══██╗[#0040ff]       ██║██║
[#00f0ff]██████╔╝[#00e0ff]╚██████╔╝[#00d0ff]██║[#00c0ff]███████╗[#00a0ff]██████╔╝[#0080ff]███████╗[#0060ff]██║  ██║[#0040ff]       ██║██║
[#00f0ff]╚═════╝ [#00e0ff] ╚═════╝ [#00d0ff]╚═╝[#00c0ff]╚══════╝[#00a0ff]╚═════╝ [#0080ff]╚══════╝[#0060ff]╚═╝  ╚═╝[#0040ff]       ╚═╝╚═╝

                  [bold white]Generic governed AI platform[/]
"""

# Fixed Cocoa program: floats the JPEG, full quality, auto-quits after HOLD seconds.
_SWIFT_SPLASH = r"""
import Cocoa
import Foundation

class SplashDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let imagePath = CommandLine.arguments[1]
        let hold = Double(CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : "3.5") ?? 3.5
        guard let image = NSImage(contentsOfFile: imagePath) else { exit(1) }

        let screenRect = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 1280, height: 800)
        // Cap display size while preserving aspect (retina-aware NSImage)
        let maxSize = NSSize(width: min(960, screenRect.width * 0.75),
                             height: min(640, screenRect.height * 0.75))
        var size = image.size
        if size.width <= 0 || size.height <= 0 { exit(1) }
        let scale = min(maxSize.width / size.width, maxSize.height / size.height, 1.0)
        size.width *= scale
        size.height *= scale

        let origin = NSPoint(
            x: (screenRect.width - size.width) / 2,
            y: (screenRect.height - size.height) / 2
        )
        let rect = NSRect(origin: origin, size: size)

        window = NSWindow(
            contentRect: rect,
            styleMask: [.borderless],
            backing: .buffered,
            defer: false
        )
        window.isOpaque = false
        window.backgroundColor = .clear
        window.level = .floating
        window.hasShadow = true
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]

        let imageView = NSImageView(frame: NSRect(origin: .zero, size: size))
        imageView.image = image
        imageView.imageScaling = .scaleProportionallyUpOrDown
        window.contentView = imageView
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)

        DispatchQueue.main.asyncAfter(deadline: .now() + hold) {
            NSApplication.shared.terminate(nil)
        }
    }
}

let app = NSApplication.shared
let delegate = SplashDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
"""


def resolve_hero_path(project_root: Path | None = None) -> Path | None:
    """Locate splash hero image relative to project root or this package's repo."""
    candidates: list[Path] = []
    if project_root is not None:
        candidates.append(Path(project_root) / HERO_RELATIVE)
    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / HERO_RELATIVE)
    candidates.append(here.parents[2].parent / HERO_RELATIVE)
    candidates.append(Path.cwd() / HERO_RELATIVE)
    for path in candidates:
        try:
            if path.is_file():
                return path.resolve()
        except OSError:
            continue
    return None


def _native_splash_allowed() -> bool:
    if platform.system() != "Darwin":
        return False
    flag = os.environ.get(ENV_DISABLE_NATIVE, "1").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return shutil.which("swift") is not None


def _want_terminal_image() -> bool:
    return os.environ.get(ENV_FORCE_TERMINAL, "").strip().lower() in ("1", "true", "yes", "on")


def load_hero_renderable(path: Path) -> Any | None:
    """Optional low-res terminal render (opt-in only — not the default path)."""
    if not _want_terminal_image():
        return None
    try:
        from PIL import Image
        from rich_pixels import Pixels
    except ImportError:
        return None
    try:
        img = Image.open(path).convert("RGB")
    except OSError:
        return None
    # Larger than the old 72×40 so opt-in looks less broken
    img.thumbnail((120, 68), Image.Resampling.LANCZOS)
    try:
        return Pixels.from_image(img)
    except Exception:
        return None


async def run_native_hero_splash(image_path: Path, hold_seconds: float = SPLASH_HOLD_SECONDS) -> bool:
    """Float the real JPEG via Swift/Cocoa. Returns True if the window ran."""
    if not _native_splash_allowed():
        return False
    if not image_path.is_file():
        return False

    fd, swift_path = tempfile.mkstemp(suffix=".swift", prefix="builder_ii_splash_")
    try:
        os.write(fd, _SWIFT_SPLASH.encode("utf-8"))
        os.close(fd)
        fd = -1
        # Fixed argv, shell=False — only the image path and hold duration
        proc = await asyncio.create_subprocess_exec(
            "swift",
            swift_path,
            str(image_path),
            f"{hold_seconds:g}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.remove(swift_path)
        except OSError:
            pass


class SplashScreen(ModalScreen[None]):
    """Native high-quality hero when possible; ASCII otherwise."""

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
        self._hero_path = resolve_hero_path(project_root)
        self._used_native = False

    def compose(self) -> ComposeResult:
        # Prefer ASCII inside the terminal; native image is outside.
        # Opt-in terminal pixel image only if env set.
        terminal_img = None
        if self._hero_path is not None and _want_terminal_image():
            terminal_img = load_hero_renderable(self._hero_path)

        with Vertical(id="splash-container"):
            with Center():
                if terminal_img is not None:
                    if isinstance(terminal_img, str):
                        yield Static(terminal_img, id="splash-art", markup=True)
                    else:
                        art = Static(id="splash-art")
                        yield art
                        self._pending_renderable = terminal_img
                else:
                    yield Static(ASCII_ART, id="splash-art", markup=True)
            yield Static("builder-II  ·  governed local control plane", id="splash-tag")
            yield Static("STRATUM starting…  (any key to continue)", id="splash-hint")

    async def on_mount(self) -> None:
        container = self.query_one("#splash-container")
        # Hide terminal chrome while native float is up
        if self._hero_path is not None and _native_splash_allowed():
            container.display = False
            self._used_native = await run_native_hero_splash(self._hero_path, SPLASH_HOLD_SECONDS)
            container.display = True

        if hasattr(self, "_pending_renderable"):
            try:
                art = self.query_one("#splash-art", Static)
                art.update(self._pending_renderable)
            except Exception:
                pass

        # After native window, brief beat then enter console (or wait for key)
        if self._used_native:
            # Native already held ~SPLASH_HOLD_SECONDS — dismiss almost immediately
            self._dismiss_timer = self.set_timer(0.35, self._auto_dismiss)
        else:
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
