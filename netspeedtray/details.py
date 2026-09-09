from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from .formatting import format_bytes, format_rate
from .monitor import NetworkMonitor, SpeedSample
from .settings import Settings


class DetailsWindow(ctk.CTkToplevel):
    def __init__(self, master, monitor: NetworkMonitor, settings: Settings, on_open_settings, on_open_usage) -> None:
        super().__init__(master)
        self.monitor = monitor
        self.settings = settings
        self.on_open_settings = on_open_settings
        self.on_open_usage = on_open_usage
        self.title("Network speed")
        self.geometry("460x500")
        self.minsize(400, 420)
        self.resizable(True, True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        self.down_value = ctk.CTkLabel(self, text="0 KB/s", font=ctk.CTkFont(size=28, weight="bold"))
        self.up_value = ctk.CTkLabel(self, text="0 KB/s", font=ctk.CTkFont(size=28, weight="bold"))
        self.down_caption = ctk.CTkLabel(self, text="Download")
        self.up_caption = ctk.CTkLabel(self, text="Upload")
        self.today_down = ctk.CTkLabel(self, text="Today 0 B", font=ctk.CTkFont(size=13))
        self.today_up = ctk.CTkLabel(self, text="Today 0 B", font=ctk.CTkFont(size=13))
        self.meta = ctk.CTkLabel(self, text="", justify="left")
        self.canvas = tk.Canvas(self, height=140, highlightthickness=0, bd=0)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_btn = ctk.CTkButton(buttons, text="Open settings", command=self.on_open_settings, width=130)
        self.usage_btn = ctk.CTkButton(buttons, text="Usage history", command=self.on_open_usage, width=130)
        self.reset_btn = ctk.CTkButton(buttons, text="Reset session", command=self._reset, width=130, fg_color="gray30")

        self.down_caption.grid(row=0, column=0, pady=(18, 0))
        self.up_caption.grid(row=0, column=1, pady=(18, 0))
        self.down_value.grid(row=1, column=0, padx=12)
        self.up_value.grid(row=1, column=1, padx=12)
        self.today_down.grid(row=2, column=0, padx=12, pady=(0, 4))
        self.today_up.grid(row=2, column=1, padx=12, pady=(0, 4))
        self.meta.grid(row=3, column=0, columnspan=2, sticky="w", padx=18, pady=8)
        self.canvas.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=16)
        buttons.grid(row=5, column=0, columnspan=2, pady=14)
        self.settings_btn.pack(side="left", padx=4)
        self.usage_btn.pack(side="left", padx=4)
        self.reset_btn.pack(side="left", padx=4)
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure(4, weight=1)
        self._user_opened = False
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.withdraw()
        self.after(400, lambda: None if self._user_opened else self.withdraw())

    def _reset(self) -> None:
        self.monitor.reset_session()
        self.settings.save()

    def show(self) -> None:
        self._user_opened = True
        self.deiconify()
        self.lift()
        self.focus_force()

    def apply_theme(self, settings: Settings) -> None:
        self.settings = settings
        self.canvas.configure(bg=settings.color_background)
        self.down_value.configure(text_color=settings.color_download)
        self.up_value.configure(text_color=settings.color_upload)
        self.down_caption.configure(text_color=settings.color_muted)
        self.up_caption.configure(text_color=settings.color_muted)
        self.today_down.configure(text_color=settings.color_download)
        self.today_up.configure(text_color=settings.color_upload)
        self.meta.configure(text_color=settings.color_text)

    def update_sample(self, sample: SpeedSample, settings: Settings) -> None:
        if not self.winfo_viewable():
            return
        self.settings = settings
        self.down_value.configure(text=format_rate(sample.download, settings), text_color=settings.color_download)
        self.up_value.configure(text=format_rate(sample.upload, settings), text_color=settings.color_upload)
        today = self.monitor.usage.today()
        self.today_down.configure(text=f"Today {format_bytes(today.down, settings.binary_units)}")
        self.today_up.configure(text=f"Today {format_bytes(today.up, settings.binary_units)}")
        ping = "-" if sample.ping_ms is None else f"{sample.ping_ms:.0f} ms"
        util = ""
        if sample.link_mbps:
            util = f"\nLink: {sample.link_mbps:.0f} Mbps   Use: {sample.down_util:.0f}% down / {sample.up_util:.0f}% up"
        self.meta.configure(
            text=(
                f"Adapter: {sample.adapter}"
                + (f"   IP: {sample.ip_address}" if sample.ip_address else "")
                + util
                + f"\nPing: {ping}"
                + f"\nSession: {format_bytes(self.monitor.session_down, settings.binary_units)} down  ·  {format_bytes(self.monitor.session_up, settings.binary_units)} up"
                + f"\nToday: {format_bytes(today.total, settings.binary_units)} total"
            )
        )
        self._draw_graph(settings)

    def _draw_graph(self, settings: Settings) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 100)
        height = max(canvas.winfo_height(), 80)
        canvas.configure(bg=settings.color_background)
        points = self.monitor.history_points()
        if len(points) < 2:
            canvas.create_text(width / 2, height / 2, text="Collecting samples…", fill=settings.color_muted)
            return
        downs = [p.download for p in points]
        ups = [p.upload for p in points]
        peak = max(max(downs), max(ups), 1.0)
        self._polyline(canvas, downs, peak, width, height, settings.color_download, settings.graph_fill)
        self._polyline(canvas, ups, peak, width, height, settings.color_upload, settings.graph_fill)

    def _polyline(self, canvas, values, peak, width, height, color, fill: bool) -> None:
        pad = 8
        usable_w = width - pad * 2
        usable_h = height - pad * 2
        coords = []
        last = max(1, len(values) - 1)
        for index, value in enumerate(values):
            x = pad + usable_w * (index / last)
            y = pad + usable_h * (1 - min(value / peak, 1.0))
            coords.extend((x, y))
        canvas.create_line(*coords, fill=color, width=2, smooth=True)
        if fill:
            fill_coords = [pad, pad + usable_h, *coords, pad + usable_w, pad + usable_h]
            canvas.create_polygon(*fill_coords, fill=color, stipple="gray50", outline="")
