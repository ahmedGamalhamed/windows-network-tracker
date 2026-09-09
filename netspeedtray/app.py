from __future__ import annotations

import tempfile
import time
from pathlib import Path

import customtkinter as ctk

from . import startup
from .details import DetailsWindow
from .monitor import NetworkMonitor, SpeedSample
from .overlay import OverlayWindow
from .settings import Settings
from .settings_ui import SettingsWindow
from .tray import TrayIcon, app_icon
from .usage import UsageStore
from .usage_ui import UsageWindow
from .win32util import apps_use_light_theme, is_foreground_fullscreen, set_dpi_aware, single_instance


class NetSpeedApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.withdraw()
        self.settings = Settings.load()
        self.usage = UsageStore()
        self.monitor = NetworkMonitor(self.settings, self.usage)
        self.paused = False
        self._last_alert = 0.0
        self._totals_save_at = time.time()

        self.title("NetSpeedTray")
        self.geometry("1x1+0+0")
        self.overrideredirect(True)
        self.withdraw()

        self._apply_theme()
        self._set_icon()

        self.overlay = OverlayWindow(
            self,
            self.settings,
            on_open_details=self.show_details,
            on_open_settings=self.show_settings,
            on_open_usage=self.show_usage,
            on_quit=self.quit_app,
        )
        self.details = DetailsWindow(
            self,
            self.monitor,
            self.settings,
            on_open_settings=self.show_settings,
            on_open_usage=self.show_usage,
        )
        self.usage_window = UsageWindow(self, self.usage, self.settings)
        self.settings_window = SettingsWindow(
            self,
            self.settings,
            adapters=self.monitor.list_adapters(),
            on_apply=self.apply_settings,
        )
        self.tray = TrayIcon(
            self.settings,
            on_details=lambda: self.after(0, self.show_details),
            on_settings=lambda: self.after(0, self.show_settings),
            on_usage=lambda: self.after(0, self.show_usage),
            on_toggle_pause=lambda: self.after(0, self.toggle_pause),
            on_toggle_overlay=lambda: self.after(0, self.toggle_overlay),
            on_quit=lambda: self.after(0, self.quit_app),
            is_paused=lambda: self.paused,
        )

        if self.settings.start_with_windows:
            try:
                startup.set_enabled(True)
            except OSError:
                pass

        self.tray.start()
        if not self.settings.start_hidden:
            self.after(400, self.show_details)
        self.after(300, self._tick)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _set_icon(self) -> None:
        try:
            path = Path(tempfile.gettempdir()) / "netspeedtray.ico"
            if not path.exists():
                app_icon(256).save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
            self.iconbitmap(str(path))
        except Exception:
            pass

    def _apply_theme(self) -> None:
        theme = self.settings.theme
        if theme == "system":
            theme = "light" if apps_use_light_theme() else "dark"
        ctk.set_appearance_mode(theme)
        ctk.set_default_color_theme("blue")

    def apply_settings(self) -> None:
        self.monitor.update_settings(self.settings)
        self._apply_theme()
        self.overlay.apply_settings(self.settings)
        self.details.apply_theme(self.settings)
        self.usage_window.apply_theme(self.settings)
        self.settings_window.refresh_adapters(self.monitor.list_adapters())

    def show_details(self) -> None:
        if not self.settings.show_details_on_click:
            self.show_settings()
            return
        self.details.apply_theme(self.settings)
        self.details.show()

    def show_usage(self) -> None:
        self.usage_window.apply_theme(self.settings)
        self.usage_window.show()

    def show_settings(self) -> None:
        self.settings_window.refresh_adapters(self.monitor.list_adapters())
        self.settings_window.load_from_settings(self.settings)
        self.settings_window.show()

    def toggle_pause(self) -> None:
        self.paused = not self.paused

    def toggle_overlay(self) -> None:
        self.settings.show_overlay = not self.settings.show_overlay
        self.settings.save()
        self.overlay.apply_settings(self.settings)

    def _tick(self) -> None:
        try:
            if not self.paused:
                sample = self.monitor.poll()
            else:
                sample = self.monitor.latest
            self._update_ui(sample)
            self._check_alerts(sample)
            self._check_usage_cap()
            if time.time() - self._totals_save_at > 15:
                self.settings.save()
                self.usage.save()
                self._totals_save_at = time.time()
        except Exception:
            pass
        interval = 1000 if self.paused else max(200, self.settings.update_interval_ms)
        self.after(interval, self._tick)

    def _update_ui(self, sample: SpeedSample) -> None:
        hide = self.settings.overlay_hide_fullscreen and is_foreground_fullscreen()
        self.overlay.set_fullscreen_hidden(hide)
        if self.settings.show_overlay and not hide:
            today = self.usage.today()
            self.overlay.update_sample(
                sample,
                self.settings,
                self.monitor.session_down,
                self.monitor.session_up,
                today.down,
                today.up,
            )
        self.details.update_sample(sample, self.settings)
        self.usage_window.refresh()
        self.tray.update(sample, self.settings)

    def _check_alerts(self, sample: SpeedSample) -> None:
        if not self.settings.alerts_enabled:
            return
        if time.time() - self._last_alert < 30:
            return
        down_mb = sample.download / (1024 * 1024)
        up_mb = sample.upload / (1024 * 1024)
        down_kb = sample.download / 1024
        message = None
        if self.settings.alert_download_above_mbps and down_mb >= self.settings.alert_download_above_mbps:
            message = f"Download is {down_mb:.1f} MB/s"
        elif self.settings.alert_upload_above_mbps and up_mb >= self.settings.alert_upload_above_mbps:
            message = f"Upload is {up_mb:.1f} MB/s"
        elif self.settings.alert_download_below_kbps and down_kb <= self.settings.alert_download_below_kbps:
            message = f"Download dropped to {down_kb:.1f} KB/s"
        if message and self.settings.alert_notify:
            try:
                self.tray.icon.notify(message, "NetSpeedTray")
                self._last_alert = time.time()
            except Exception:
                pass

    def _check_usage_cap(self) -> None:
        cap_gb = float(self.settings.usage_daily_cap_gb or 0)
        if not self.settings.usage_cap_notify or cap_gb <= 0:
            return
        today = self.usage.today()
        if self.usage.quota_notified_on == today.day:
            return
        binary = self.settings.binary_units
        cap_bytes = int(cap_gb * (1024 ** 3 if binary else 1000 ** 3))
        used = self.usage.cap_value(today, self.settings.usage_cap_metric)
        if used < cap_bytes:
            return
        try:
            self.tray.icon.notify(
                f"Daily {self.settings.usage_cap_metric} usage reached {cap_gb:g} GB",
                "NetSpeedTray",
            )
            self.usage.quota_notified_on = today.day
            self.usage.save(force=True)
        except Exception:
            pass

    def quit_app(self) -> None:
        self.settings.save()
        self.usage.save(force=True)
        self.monitor.stop()
        self.tray.stop()
        self.destroy()


def main() -> None:
    set_dpi_aware()
    if not single_instance():
        return
    app = NetSpeedApp()
    app.mainloop()


if __name__ == "__main__":
    main()
