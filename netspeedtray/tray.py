from __future__ import annotations

import io
import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw, ImageFont

from .formatting import format_bytes, format_compact_rate, format_rate
from .monitor import SpeedSample
from .settings import Settings


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\tahomabd.ttf",
        r"C:\Windows\Fonts\consola.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _hex_rgb(value: str) -> tuple[int, int, int]:
    text = value.lstrip("#")
    if len(text) != 6:
        return (255, 255, 255)
    return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def app_icon(size: int = 256) -> Image.Image:
    image = Image.new("RGBA", (size, size), (21, 21, 21, 255))
    draw = ImageDraw.Draw(image)
    margin = size // 8
    draw.rounded_rectangle((margin, margin, size - margin, size - margin), radius=size // 6, fill=(30, 30, 30, 255))
    draw.polygon(
        [(size * 0.32, size * 0.22), (size * 0.52, size * 0.22), (size * 0.42, size * 0.48), (size * 0.22, size * 0.48)],
        fill=(61, 220, 151, 255),
    )
    draw.polygon(
        [(size * 0.48, size * 0.52), (size * 0.78, size * 0.52), (size * 0.68, size * 0.78), (size * 0.38, size * 0.78)],
        fill=(91, 157, 255, 255),
    )
    return image


def icon_to_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    return buffer.getvalue()


class TrayIcon:
    def __init__(
        self,
        settings: Settings,
        on_details: Callable[[], None],
        on_settings: Callable[[], None],
        on_usage: Callable[[], None],
        on_toggle_pause: Callable[[], None],
        on_toggle_overlay: Callable[[], None],
        on_quit: Callable[[], None],
        is_paused: Callable[[], bool],
    ) -> None:
        self.settings = settings
        self.on_details = on_details
        self.on_settings = on_settings
        self.on_usage = on_usage
        self.on_toggle_pause = on_toggle_pause
        self.on_toggle_overlay = on_toggle_overlay
        self.on_quit = on_quit
        self.is_paused = is_paused
        self._history: list[tuple[float, float]] = []
        self.icon = pystray.Icon("NetSpeedTray", app_icon(64), "NetSpeedTray", self._menu())
        self._thread: threading.Thread | None = None

    def _menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Details", lambda: self.on_details(), default=True),
            pystray.MenuItem("Usage", lambda: self.on_usage()),
            pystray.MenuItem("Settings", lambda: self.on_settings()),
            pystray.MenuItem("Show overlay", lambda: self.on_toggle_overlay(), checked=lambda _: self.settings.show_overlay),
            pystray.MenuItem("Pause", lambda: self.on_toggle_pause(), checked=lambda _: self.is_paused()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self.on_quit()),
        )

    def start(self) -> None:
        self._thread = threading.Thread(target=self.icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self.icon.stop()
        except Exception:
            pass

    def update(self, sample: SpeedSample, settings: Settings) -> None:
        self.settings = settings
        if not settings.show_tray:
            if self.icon.visible:
                self.icon.visible = False
            return
        if not self.icon.visible:
            self.icon.visible = True
        self._history.append((sample.download, sample.upload))
        self._history = self._history[-24:]
        tooltip = (
            f"↓ {format_rate(sample.download, settings)}\n"
            f"↑ {format_rate(sample.upload, settings)}\n"
            f"{sample.adapter}"
        )
        if sample.ip_address:
            tooltip += f"\n{sample.ip_address}"
        today = settings.daily_down_bytes + settings.daily_up_bytes
        if today:
            tooltip += f"\nToday {format_bytes(today, settings.binary_units)}"
        image = self._draw_icon(sample, settings)
        try:
            self.icon.icon = image
            self.icon.title = tooltip
        except Exception:
            pass

    def _draw_icon(self, sample: SpeedSample, settings: Settings) -> Image.Image:
        size = 64
        bg = (*_hex_rgb(settings.color_background), 255)
        image = Image.new("RGBA", (size, size), bg)
        draw = ImageDraw.Draw(image)
        down = _hex_rgb(settings.color_download)
        up = _hex_rgb(settings.color_upload)
        style = settings.tray_style
        if style == "arrows":
            draw.polygon([(32, 6), (48, 28), (16, 28)], fill=down)
            draw.polygon([(16, 36), (48, 36), (32, 58)], fill=up)
        elif style == "bars":
            peak = max(sample.download, sample.upload, 1.0)
            down_h = int(48 * min(sample.download / peak, 1))
            up_h = int(48 * min(sample.upload / peak, 1))
            draw.rectangle((10, 56 - down_h, 28, 56), fill=down)
            draw.rectangle((36, 56 - up_h, 54, 56), fill=up)
        elif style == "graph":
            if len(self._history) >= 2:
                peak = max(max(d, u) for d, u in self._history) or 1
                self._spark(draw, [d for d, _ in self._history], peak, down, 4, 6, 56, 24)
                self._spark(draw, [u for _, u in self._history], peak, up, 4, 34, 56, 24)
        else:
            font = _font(18)
            down_text = format_compact_rate(sample.download, settings)
            up_text = format_compact_rate(sample.upload, settings)
            draw.text((4, 8), down_text, fill=down, font=font)
            draw.text((4, 34), up_text, fill=up, font=font)
        return image

    def _spark(self, draw: ImageDraw.ImageDraw, values: list[float], peak: float, color, x: int, y: int, w: int, h: int) -> None:
        if len(values) < 2:
            return
        points = []
        last = len(values) - 1
        for index, value in enumerate(values):
            px = x + int(w * (index / last))
            py = y + h - int(h * min(value / peak, 1.0))
            points.append((px, py))
        draw.line(points, fill=color, width=2)
