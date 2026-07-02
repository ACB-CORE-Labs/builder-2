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

                  [bold white]CORE-native governed AI platform[/]
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
        """Pop open the high-res image borderless outside the terminal."""
        import asyncio
        import os
        import tempfile

        container = self.query_one("#splash-container")
        container.display = False

        image_path = "images/builder-ii-splash-hero.jpeg"
        if not os.path.exists(image_path):
            container.display = True
            return

        swift_code = """
import Cocoa
class SplashDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    func applicationDidFinishLaunching(_ notification: Notification) {
        let imagePath = CommandLine.arguments[1]
        guard let image = NSImage(contentsOfFile: imagePath) else { exit(1) }
        let screenRect = NSScreen.main?.frame ?? NSRect(x: 0, y: 0, width: 800, height: 600)
        let maxSize = NSSize(width: 800, height: 600)
        var size = image.size
        let aspectWidth = maxSize.width / size.width
        let aspectHeight = maxSize.height / size.height
        let aspectRatio = min(aspectWidth, aspectHeight)
        if aspectRatio < 1.0 { size.width *= aspectRatio; size.height *= aspectRatio }
        let rect = NSRect(x: (screenRect.width - size.width) / 2, y: (screenRect.height - size.height) / 2, width: size.width, height: size.height)
        window = NSWindow(contentRect: rect, styleMask: [.borderless], backing: .buffered, defer: false)
        window.isOpaque = false
        window.backgroundColor = .clear
        window.level = .floating
        window.hasShadow = true
        let imageView = NSImageView(frame: NSRect(x: 0, y: 0, width: size.width, height: size.height))
        imageView.image = image
        imageView.imageScaling = .scaleProportionallyUpOrDown
        window.contentView = imageView
        window.makeKeyAndOrderFront(nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 4.0) { NSApplication.shared.terminate(nil) }
    }
}
let app = NSApplication.shared
let delegate = SplashDelegate()
app.delegate = delegate
app.run()
"""
        try:
            fd, path = tempfile.mkstemp(suffix=".swift")
            os.write(fd, swift_code.encode())
            os.close(fd)

            proc = await asyncio.create_subprocess_exec(
                "swift", path, image_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )

            await proc.wait()
            try:
                os.remove(path)
            except Exception:
                pass

        except Exception:
            pass

        container.display = True

    def on_key(self, event) -> None:
        self.dismiss(None)

    def on_mouse_down(self, event) -> None:
        self.dismiss(None)
