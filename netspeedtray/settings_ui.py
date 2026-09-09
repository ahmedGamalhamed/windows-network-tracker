from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser, font as tkfont

import customtkinter as ctk

from . import startup
from .settings import Settings


INTERVALS = ["200", "500", "1000", "1500", "2000", "3000", "5000"]
LAYOUTS = ["stacked", "inline", "compact"]
DOCKS = ["taskbar-tray", "taskbar-left", "taskbar-center", "taskbar-right", "custom"]
ADAPTER_MODES = ["auto", "all", "specific"]
THEMES = ["dark", "light", "system"]
SCALES = ["auto", "B", "KB", "MB", "GB", "TB"]
TRAY_STYLES = ["text", "arrows", "bars", "graph"]
DECIMALS = ["0", "1", "2", "3"]
MIN_UNITS = ["B", "KB", "MB"]


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, settings: Settings, adapters: list[str], on_apply) -> None:
        super().__init__(master)
        self.settings = settings
        self.adapters = adapters
        self.on_apply = on_apply
        self._vars: dict[str, tk.Variable] = {}
        self._updating = False

        self.title("NetSpeedTray settings")
        self.geometry("760x680")
        self.minsize(640, 560)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        header = ctk.CTkLabel(self, text="NetSpeedTray", font=ctk.CTkFont(size=22, weight="bold"))
        subtitle = ctk.CTkLabel(self, text="Live upload and download speeds in the taskbar and tray.")
        header.pack(anchor="w", padx=18, pady=(16, 0))
        subtitle.pack(anchor="w", padx=18, pady=(0, 8))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        for name in ("General", "Display", "Appearance", "Units", "Usage", "Alerts", "Advanced"):
            self.tabs.add(name)

        self._build_general()
        self._build_display()
        self._build_appearance()
        self._build_units()
        self._build_usage()
        self._build_alerts()
        self._build_advanced()

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(buttons, text="Reset defaults", fg_color="gray30", width=140, command=self._reset).pack(side="left")
        ctk.CTkButton(buttons, text="Close", width=120, command=self.withdraw).pack(side="right")

        self._user_opened = False
        self.load_from_settings(settings)
        self.withdraw()
        self.after(400, lambda: None if self._user_opened else self.withdraw())

    def show(self) -> None:
        self._user_opened = True
        self.deiconify()
        self.lift()
        self.focus_force()

    def refresh_adapters(self, adapters: list[str]) -> None:
        self.adapters = adapters
        combo = getattr(self, "adapter_combo", None)
        if combo is not None:
            values = adapters or ["No active adapters"]
            combo.configure(values=values)

    def _bool(self, key: str, default: bool) -> tk.BooleanVar:
        var = tk.BooleanVar(value=default)
        self._vars[key] = var
        var.trace_add("write", lambda *_: self._changed())
        return var

    def _str(self, key: str, default: str) -> tk.StringVar:
        var = tk.StringVar(value=str(default))
        self._vars[key] = var
        var.trace_add("write", lambda *_: self._changed())
        return var

    def _double(self, key: str, default: float) -> tk.DoubleVar:
        var = tk.DoubleVar(value=float(default))
        self._vars[key] = var
        var.trace_add("write", lambda *_: self._changed())
        return var

    def _changed(self) -> None:
        if self._updating:
            return
        self._collect()
        self.settings.save()
        self.on_apply()

    def _switch(self, parent, text: str, key: str, default: bool) -> ctk.CTkSwitch:
        var = self._bool(key, default)
        widget = ctk.CTkSwitch(parent, text=text, variable=var)
        widget.pack(anchor="w", pady=6)
        return widget

    def _combo(self, parent, label: str, key: str, values: list[str], default: str) -> ctk.CTkComboBox:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left")
        var = self._str(key, default)
        combo = ctk.CTkComboBox(row, values=values, variable=var, width=280, command=lambda _v: self._changed())
        combo.pack(side="left", padx=(8, 0))
        return combo

    def _entry(self, parent, label: str, key: str, default: str, width: int = 280) -> ctk.CTkEntry:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left")
        var = self._str(key, default)
        entry = ctk.CTkEntry(row, textvariable=var, width=width)
        entry.pack(side="left", padx=(8, 0))
        return entry

    def _slider(self, parent, label: str, key: str, default: float, from_: float, to: float, value_fmt) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        caption = ctk.CTkLabel(row, text=label, width=220, anchor="w")
        caption.pack(side="left")
        var = self._double(key, default)
        value_label = ctk.CTkLabel(row, text=value_fmt(default), width=70)
        slider = ctk.CTkSlider(row, from_=from_, to=to, variable=var, width=250)

        def updated(*_):
            value_label.configure(text=value_fmt(var.get()))

        var.trace_add("write", updated)
        slider.pack(side="left", padx=(8, 8))
        value_label.pack(side="left")

    def _color(self, parent, label: str, key: str, default: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text=label, width=220, anchor="w").pack(side="left")
        var = self._str(key, default)
        preview = ctk.CTkButton(row, text=default, width=140, fg_color=default, hover=False)

        def pick():
            chosen = colorchooser.askcolor(color=var.get(), parent=self, title=label)
            if chosen and chosen[1]:
                var.set(chosen[1])
                preview.configure(text=chosen[1], fg_color=chosen[1])

        var.trace_add("write", lambda *_: preview.configure(text=var.get(), fg_color=var.get() or default))
        preview.configure(command=pick)
        preview.pack(side="left", padx=(8, 0))

    def _scroll(self, tab_name: str) -> ctk.CTkScrollableFrame:
        frame = ctk.CTkScrollableFrame(self.tabs.tab(tab_name), fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        return frame

    def _build_general(self) -> None:
        frame = self._scroll("General")
        self._switch(frame, "Start NetSpeedTray when Windows starts", "start_with_windows", False)
        self._switch(frame, "Start with the details window hidden", "start_hidden", True)
        self._combo(frame, "Update interval (ms)", "update_interval_ms", INTERVALS, "1000")
        self._combo(frame, "Network adapter", "adapter_mode", ADAPTER_MODES, "auto")
        self.adapter_combo = self._combo(frame, "Specific adapter", "adapter_name", self.adapters or [""], "")
        self._switch(frame, "Ignore virtual adapters (Hyper-V, VMware, loopback, etc.)", "ignore_virtual", True)
        self._switch(frame, "Still include VPN adapters", "include_vpn", True)
        note = ctk.CTkLabel(
            frame,
            text="Adapter modes: auto uses the busiest NIC, all sums every included adapter, specific locks to one interface.",
            wraplength=640,
            justify="left",
            text_color=("gray40", "gray70"),
        )
        note.pack(anchor="w", pady=(12, 0))

    def _build_display(self) -> None:
        frame = self._scroll("Display")
        self._switch(frame, "Show speeds on the taskbar", "show_overlay", True)
        self._switch(frame, "Show speeds in the system tray icon", "show_tray", True)
        self._switch(frame, "Open the details window when the tray icon is clicked", "show_details_on_click", True)
        self._combo(frame, "Taskbar layout", "overlay_layout", LAYOUTS, "stacked")
        self._combo(frame, "Taskbar position", "overlay_dock", DOCKS, "taskbar-tray")
        self._combo(frame, "Tray icon style", "tray_style", TRAY_STYLES, "text")
        self._switch(frame, "Transparent background", "overlay_transparent_background", True)
        self._switch(frame, "Allow dragging along the taskbar", "overlay_draggable", True)
        self._switch(frame, "Lock position", "overlay_lock_position", False)
        self._switch(frame, "Click-through (ignore mouse)", "overlay_click_through", False)
        self._switch(frame, "Hide during fullscreen apps / games", "overlay_hide_fullscreen", True)
        self._switch(frame, "Show adapter name", "overlay_show_adapter", False)
        self._switch(frame, "Show Down/Up labels", "overlay_show_labels", True)
        self._switch(frame, "Show arrows", "overlay_show_arrows", True)
        self._switch(frame, "Show session totals", "overlay_show_totals", False)
        self._switch(frame, "Show today's usage", "overlay_show_usage", True)
        self._switch(frame, "Show ping", "overlay_show_ping", False)
        self._switch(frame, "Show link utilization", "overlay_show_utilization", False)
        self._switch(frame, "Show units on the tray icon", "tray_show_units", False)
        self._slider(frame, "Opacity (when background is solid)", "overlay_opacity", 1.0, 0.4, 1.0, lambda v: f"{v:.0%}")
        self._combo(frame, "Graph history (seconds)", "graph_history_seconds", ["30", "60", "120", "180", "300"], "60")
        self._switch(frame, "Fill area under the details graph", "graph_fill", True)

    def _build_appearance(self) -> None:
        frame = self._scroll("Appearance")
        self._combo(frame, "Theme", "theme", THEMES, "dark")
        families = sorted(set(tkfont.families()))
        preferred = [name for name in ("Segoe UI", "Segoe UI Variable", "Tahoma", "Consolas", "Arial") if name in families]
        self._combo(frame, "Overlay font", "overlay_font_family", preferred + families, "Segoe UI")
        self._combo(frame, "Font size", "overlay_font_size", [str(n) for n in range(8, 25)], "11")
        self._switch(frame, "Bold overlay text", "overlay_font_bold", True)
        self._combo(frame, "Horizontal padding", "overlay_padding_x", [str(n) for n in range(2, 25)], "10")
        self._combo(frame, "Vertical padding", "overlay_padding_y", [str(n) for n in range(0, 17)], "4")
        self._combo(frame, "Spacing", "overlay_gap", [str(n) for n in range(0, 21)], "6")
        self._color(frame, "Download color", "color_download", "#3DDC97")
        self._color(frame, "Upload color", "color_upload", "#5B9DFF")
        self._color(frame, "Background color", "color_background", "#151515")
        self._color(frame, "Text color", "color_text", "#F4F4F4")
        self._color(frame, "Muted text color", "color_muted", "#A0A0A0")
        self._color(frame, "Border color", "color_border", "#2A2A2A")

    def _build_units(self) -> None:
        frame = self._scroll("Units")
        self._switch(frame, "Show bits per second (b/s) instead of bytes (B/s)", "use_bits", False)
        self._switch(frame, "Use binary units (1024) instead of decimal (1000)", "binary_units", True)
        self._combo(frame, "Unit scale", "unit_scale", SCALES, "auto")
        self._combo(frame, "Minimum unit", "min_display_unit", MIN_UNITS, "KB")
        self._combo(frame, "Decimal places", "decimal_places", DECIMALS, "1")
        note = ctk.CTkLabel(
            frame,
            text="Auto scale picks KB/s, MB/s, or GB/s from the current speed. Minimum unit keeps tiny values from jumping down to B/s.",
            wraplength=640,
            justify="left",
            text_color=("gray40", "gray70"),
        )
        note.pack(anchor="w", pady=(12, 0))

    def _build_usage(self) -> None:
        frame = self._scroll("Usage")
        self._switch(frame, "Track daily download and upload totals", "persist_daily_totals", True)
        self._combo(frame, "Keep history for (days)", "usage_retention_days", ["30", "90", "180", "365", "730"], "365")
        self._entry(frame, "Daily cap (GB, 0 = off)", "usage_daily_cap_gb", "0")
        self._combo(frame, "Cap applies to", "usage_cap_metric", ["total", "download", "upload"], "total")
        self._switch(frame, "Notify when the daily cap is reached", "usage_cap_notify", True)
        note = ctk.CTkLabel(
            frame,
            text="Usage is stored locally and rolls over at midnight. Open Usage history from the tray menu to see daily, weekly, and monthly totals.",
            wraplength=640,
            justify="left",
            text_color=("gray40", "gray70"),
        )
        note.pack(anchor="w", pady=(12, 0))

    def _build_alerts(self) -> None:
        frame = self._scroll("Alerts")
        self._switch(frame, "Enable speed alerts", "alerts_enabled", False)
        self._switch(frame, "Show a Windows notification when an alert fires", "alert_notify", True)
        self._entry(frame, "Alert if download exceeds (MB/s)", "alert_download_above_mbps", "0")
        self._entry(frame, "Alert if upload exceeds (MB/s)", "alert_upload_above_mbps", "0")
        self._entry(frame, "Alert if download stays below (KB/s)", "alert_download_below_kbps", "0")
        note = ctk.CTkLabel(
            frame,
            text="Set any threshold to 0 to disable that rule. Alerts fire at most once every 30 seconds.",
            wraplength=640,
            justify="left",
            text_color=("gray40", "gray70"),
        )
        note.pack(anchor="w", pady=(12, 0))

    def _build_advanced(self) -> None:
        frame = self._scroll("Advanced")
        self._switch(frame, "Measure ping in the background", "ping_enabled", False)
        self._entry(frame, "Ping host", "ping_host", "1.1.1.1")
        self._combo(frame, "Ping interval (ms)", "ping_interval_ms", ["1000", "2000", "3000", "5000", "10000"], "3000")
        note = ctk.CTkLabel(
            frame,
            text="Ping uses the Windows ping command and does not require administrator rights.",
            wraplength=640,
            justify="left",
            text_color=("gray40", "gray70"),
        )
        note.pack(anchor="w", pady=(12, 0))

    def load_from_settings(self, settings: Settings) -> None:
        self._updating = True
        mapping = {
            "start_with_windows": settings.start_with_windows,
            "start_hidden": settings.start_hidden,
            "update_interval_ms": str(settings.update_interval_ms),
            "adapter_mode": settings.adapter_mode,
            "adapter_name": settings.adapter_name,
            "ignore_virtual": settings.ignore_virtual,
            "include_vpn": settings.include_vpn,
            "show_overlay": settings.show_overlay,
            "show_tray": settings.show_tray,
            "show_details_on_click": settings.show_details_on_click,
            "overlay_layout": settings.overlay_layout,
            "overlay_dock": settings.overlay_dock,
            "tray_style": settings.tray_style,
            "overlay_transparent_background": settings.overlay_transparent_background,
            "overlay_always_on_top": settings.overlay_always_on_top,
            "overlay_draggable": settings.overlay_draggable,
            "overlay_lock_position": settings.overlay_lock_position,
            "overlay_click_through": settings.overlay_click_through,
            "overlay_hide_fullscreen": settings.overlay_hide_fullscreen,
            "overlay_show_adapter": settings.overlay_show_adapter,
            "overlay_show_labels": settings.overlay_show_labels,
            "overlay_show_arrows": settings.overlay_show_arrows,
            "overlay_show_totals": settings.overlay_show_totals,
            "overlay_show_usage": settings.overlay_show_usage,
            "overlay_show_ping": settings.overlay_show_ping,
            "overlay_show_utilization": settings.overlay_show_utilization,
            "tray_show_units": settings.tray_show_units,
            "overlay_opacity": settings.overlay_opacity,
            "graph_history_seconds": str(settings.graph_history_seconds),
            "graph_fill": settings.graph_fill,
            "theme": settings.theme,
            "overlay_font_family": settings.overlay_font_family,
            "overlay_font_size": str(settings.overlay_font_size),
            "overlay_font_bold": settings.overlay_font_bold,
            "overlay_padding_x": str(settings.overlay_padding_x),
            "overlay_padding_y": str(settings.overlay_padding_y),
            "overlay_gap": str(settings.overlay_gap),
            "color_download": settings.color_download,
            "color_upload": settings.color_upload,
            "color_background": settings.color_background,
            "color_text": settings.color_text,
            "color_muted": settings.color_muted,
            "color_border": settings.color_border,
            "use_bits": settings.use_bits,
            "binary_units": settings.binary_units,
            "unit_scale": settings.unit_scale,
            "min_display_unit": settings.min_display_unit,
            "decimal_places": str(settings.decimal_places),
            "alerts_enabled": settings.alerts_enabled,
            "alert_notify": settings.alert_notify,
            "alert_download_above_mbps": str(settings.alert_download_above_mbps),
            "alert_upload_above_mbps": str(settings.alert_upload_above_mbps),
            "alert_download_below_kbps": str(settings.alert_download_below_kbps),
            "ping_enabled": settings.ping_enabled,
            "ping_host": settings.ping_host,
            "ping_interval_ms": str(settings.ping_interval_ms),
            "persist_daily_totals": settings.persist_daily_totals,
            "usage_retention_days": str(settings.usage_retention_days),
            "usage_daily_cap_gb": str(settings.usage_daily_cap_gb),
            "usage_cap_metric": settings.usage_cap_metric,
            "usage_cap_notify": settings.usage_cap_notify,
        }
        for key, value in mapping.items():
            if key in self._vars:
                self._vars[key].set(value)
        self._updating = False

    def _int(self, key: str, default: int) -> int:
        try:
            return int(float(str(self._vars[key].get()).strip()))
        except (TypeError, ValueError, KeyError):
            return default

    def _float(self, key: str, default: float) -> float:
        try:
            return float(str(self._vars[key].get()).strip())
        except (TypeError, ValueError, KeyError):
            return default

    def _collect(self) -> None:
        s = self.settings
        getb = lambda key: bool(self._vars[key].get())
        gets = lambda key: str(self._vars[key].get())
        s.start_with_windows = getb("start_with_windows")
        s.start_hidden = getb("start_hidden")
        s.update_interval_ms = max(200, self._int("update_interval_ms", 1000))
        s.adapter_mode = gets("adapter_mode")
        s.adapter_name = gets("adapter_name")
        s.ignore_virtual = getb("ignore_virtual")
        s.include_vpn = getb("include_vpn")
        s.show_overlay = getb("show_overlay")
        s.show_tray = getb("show_tray")
        s.show_details_on_click = getb("show_details_on_click")
        s.overlay_layout = gets("overlay_layout")
        s.overlay_dock = gets("overlay_dock")
        s.tray_style = gets("tray_style")
        s.overlay_transparent_background = getb("overlay_transparent_background")
        s.overlay_always_on_top = getb("overlay_always_on_top") if "overlay_always_on_top" in self._vars else False
        s.overlay_draggable = getb("overlay_draggable")
        s.overlay_lock_position = getb("overlay_lock_position")
        s.overlay_click_through = getb("overlay_click_through")
        s.overlay_hide_fullscreen = getb("overlay_hide_fullscreen")
        s.overlay_show_adapter = getb("overlay_show_adapter")
        s.overlay_show_labels = getb("overlay_show_labels")
        s.overlay_show_arrows = getb("overlay_show_arrows")
        s.overlay_show_totals = getb("overlay_show_totals")
        s.overlay_show_usage = getb("overlay_show_usage")
        s.overlay_show_ping = getb("overlay_show_ping")
        s.overlay_show_utilization = getb("overlay_show_utilization")
        s.tray_show_units = getb("tray_show_units")
        s.overlay_opacity = min(1.0, max(0.4, self._float("overlay_opacity", 0.94)))
        s.graph_history_seconds = max(15, self._int("graph_history_seconds", 60))
        s.graph_fill = getb("graph_fill")
        s.theme = gets("theme")
        s.overlay_font_family = gets("overlay_font_family")
        s.overlay_font_size = max(8, self._int("overlay_font_size", 11))
        s.overlay_font_bold = getb("overlay_font_bold")
        s.overlay_padding_x = self._int("overlay_padding_x", 10)
        s.overlay_padding_y = self._int("overlay_padding_y", 4)
        s.overlay_gap = self._int("overlay_gap", 6)
        s.color_download = gets("color_download")
        s.color_upload = gets("color_upload")
        s.color_background = gets("color_background")
        s.color_text = gets("color_text")
        s.color_muted = gets("color_muted")
        s.color_border = gets("color_border")
        s.use_bits = getb("use_bits")
        s.binary_units = getb("binary_units")
        s.unit_scale = gets("unit_scale")
        s.min_display_unit = gets("min_display_unit")
        s.decimal_places = self._int("decimal_places", 1)
        s.alerts_enabled = getb("alerts_enabled")
        s.alert_notify = getb("alert_notify")
        s.alert_download_above_mbps = self._float("alert_download_above_mbps", 0)
        s.alert_upload_above_mbps = self._float("alert_upload_above_mbps", 0)
        s.alert_download_below_kbps = self._float("alert_download_below_kbps", 0)
        s.ping_enabled = getb("ping_enabled")
        s.ping_host = gets("ping_host").strip() or "1.1.1.1"
        s.ping_interval_ms = max(1000, self._int("ping_interval_ms", 3000))
        s.persist_daily_totals = getb("persist_daily_totals")
        s.usage_retention_days = max(30, self._int("usage_retention_days", 365))
        s.usage_daily_cap_gb = max(0.0, self._float("usage_daily_cap_gb", 0))
        s.usage_cap_metric = gets("usage_cap_metric")
        s.usage_cap_notify = getb("usage_cap_notify")
        try:
            startup.set_enabled(s.start_with_windows)
        except OSError:
            pass

    def _reset(self) -> None:
        defaults = Settings()
        defaults.start_with_windows = self.settings.start_with_windows
        self.settings.__dict__.update(defaults.__dict__)
        self.load_from_settings(self.settings)
        self.settings.save()
        self.on_apply()
