from __future__ import annotations

import tkinter as tk

from .formatting import format_bytes, format_overlay_rate
from .monitor import SpeedSample
from .settings import Settings
from .win32util import (
    configure_taskbar_item,
    get_taskbar,
    pixel_font_size,
    sample_taskbar_color,
    window_hwnd,
)


class OverlayWindow(tk.Toplevel):
    def __init__(self, master, settings: Settings, on_open_details, on_open_settings, on_open_usage, on_quit) -> None:
        super().__init__(master)
        self.settings = settings
        self.on_open_details = on_open_details
        self.on_open_settings = on_open_settings
        self.on_open_usage = on_open_usage
        self.on_quit = on_quit
        self._drag_offset = (0, 0)
        self._hwnd = None
        self._hidden_for_fullscreen = False

        self.title("NetSpeedTrayOverlay")
        self.overrideredirect(True)
        self.resizable(False, False)
        try:
            self.attributes("-toolwindow", True)
        except tk.TclError:
            pass
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

        bg = self._bg_color(settings)
        self.configure(bg=bg, highlightthickness=0, bd=0)
        self.container = tk.Frame(self, bg=bg, highlightthickness=0, bd=0)
        self.container.place(relx=0, rely=0.5, anchor="w")

        self.adapter_label = tk.Label(self.container, text="", anchor="w", bd=0)
        self.down_arrow = tk.Label(self.container, text="↓", anchor="w", bd=0)
        self.down_value = tk.Label(self.container, text="  0.0", anchor="e", justify="right", bd=0)
        self.down_unit = tk.Label(self.container, text="KB/s", anchor="w", bd=0)
        self.up_arrow = tk.Label(self.container, text="↑", anchor="w", bd=0)
        self.up_value = tk.Label(self.container, text="  0.0", anchor="e", justify="right", bd=0)
        self.up_unit = tk.Label(self.container, text="KB/s", anchor="w", bd=0)
        self.extra_label = tk.Label(self.container, text="", anchor="w", bd=0)

        self._bind_interactions(self)
        self._bind_interactions(self.container)
        for label in (
            self.adapter_label,
            self.down_arrow,
            self.down_value,
            self.down_unit,
            self.up_arrow,
            self.up_value,
            self.up_unit,
            self.extra_label,
        ):
            self._bind_interactions(label)

        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.after(80, self._init_native)
        self.apply_settings(settings)

    def _bg_color(self, settings: Settings) -> str:
        if settings.overlay_transparent_background:
            return sample_taskbar_color()
        return settings.color_background

    def _font(self, size_delta: int = 0):
        points = max(8, self.settings.overlay_font_size + size_delta)
        pixels = pixel_font_size(points, self._hwnd)
        weight = "bold" if self.settings.overlay_font_bold else "normal"
        return (self.settings.overlay_font_family, -pixels, weight)

    def _mono_font(self, size_delta: int = 0):
        points = max(8, self.settings.overlay_font_size + size_delta)
        pixels = pixel_font_size(points, self._hwnd)
        weight = "bold" if self.settings.overlay_font_bold else "normal"
        return ("Consolas", -pixels, weight)

    def _number_width(self) -> int:
        places = max(0, min(3, int(self.settings.decimal_places)))
        return 3 + (places + 1 if places else 0)

    def _bind_interactions(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._on_drag)
        widget.bind("<ButtonRelease-1>", self._end_drag)
        widget.bind("<Double-Button-1>", lambda _e: self.on_open_details())
        widget.bind("<Button-3>", self._show_menu)

    def _init_native(self) -> None:
        try:
            self._hwnd = window_hwnd(self)
            self.apply_settings(self.settings)
        except Exception:
            self._hwnd = None

    def _apply_native(self) -> None:
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        hwnd = self._hwnd or window_hwnd(self)
        self._hwnd = hwnd
        configure_taskbar_item(
            hwnd,
            click_through=self.settings.overlay_click_through,
            transparent_background=self.settings.overlay_transparent_background,
            alpha=1.0 if self.settings.overlay_transparent_background else self.settings.overlay_opacity,
            topmost=True,
        )

    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.show_overlay:
            self.withdraw()
            return
        if self._hidden_for_fullscreen:
            return
        self.deiconify()
        bg = self._bg_color(settings)
        self.configure(bg=bg)
        self.container.configure(bg=bg)
        try:
            self.attributes("-transparentcolor", "")
        except tk.TclError:
            pass
        number_width = self._number_width()
        for arrow, value, unit, color in (
            (self.down_arrow, self.down_value, self.down_unit, settings.color_download),
            (self.up_arrow, self.up_value, self.up_unit, settings.color_upload),
        ):
            arrow.configure(font=self._font(), fg=color, bg=bg)
            value.configure(font=self._mono_font(), fg=color, bg=bg, width=number_width, anchor="e")
            unit.configure(font=self._mono_font(), fg=color, bg=bg, width=4, anchor="w")
        self.adapter_label.configure(font=self._font(-2), fg=settings.color_muted, bg=bg)
        self.extra_label.configure(font=self._font(-2), fg=settings.color_muted, bg=bg)
        self._layout_widgets()
        if self._hwnd:
            self._apply_native()
        self.reposition()

    def _layout_widgets(self) -> None:
        for widget in self.container.winfo_children():
            widget.grid_forget()
            widget.pack_forget()
        pad_x = self.settings.overlay_padding_x
        pad_y = 0 if self.settings.overlay_transparent_background else self.settings.overlay_padding_y
        gap = self.settings.overlay_gap
        show_adapter = self.settings.overlay_show_adapter
        show_extra = (
            self.settings.overlay_show_totals
            or self.settings.overlay_show_usage
            or self.settings.overlay_show_ping
            or self.settings.overlay_show_utilization
        )
        stacked = self.settings.overlay_layout != "inline"
        if stacked:
            row = 0
            if show_adapter:
                self.adapter_label.grid(row=row, column=0, columnspan=3, sticky="w", padx=pad_x, pady=(pad_y, 0))
                row += 1
            top_pad = pad_y if row == 0 else 0
            label_gap = 10
            self.up_arrow.grid(row=row, column=0, sticky="w", padx=(pad_x, label_gap), pady=(top_pad, 0))
            self.up_value.grid(row=row, column=1, sticky="e", padx=0, pady=(top_pad, 0))
            self.up_unit.grid(row=row, column=2, sticky="w", padx=(2, pad_x), pady=(top_pad, 0))
            row += 1
            bottom_pad = pad_y if not show_extra else 0
            self.down_arrow.grid(row=row, column=0, sticky="w", padx=(pad_x, label_gap), pady=(0, bottom_pad))
            self.down_value.grid(row=row, column=1, sticky="e", padx=0, pady=(0, bottom_pad))
            self.down_unit.grid(row=row, column=2, sticky="w", padx=(2, pad_x), pady=(0, bottom_pad))
            row += 1
            if show_extra:
                self.extra_label.grid(row=row, column=0, columnspan=3, sticky="w", padx=pad_x, pady=(0, pad_y))
        else:
            column = 0
            if show_adapter:
                self.adapter_label.grid(row=0, column=column, padx=(pad_x, gap), pady=pad_y)
                column += 1
            self.down_arrow.grid(row=0, column=column, sticky="w", padx=(0, 2), pady=pad_y)
            self.down_value.grid(row=0, column=column + 1, sticky="e", padx=0, pady=pad_y)
            self.down_unit.grid(row=0, column=column + 2, sticky="w", padx=(2, gap), pady=pad_y)
            column += 3
            self.up_arrow.grid(row=0, column=column, sticky="w", padx=(0, 2), pady=pad_y)
            self.up_value.grid(row=0, column=column + 1, sticky="e", padx=0, pady=pad_y)
            self.up_unit.grid(
                row=0,
                column=column + 2,
                sticky="w",
                padx=(2, pad_x if not show_extra else gap),
                pady=pad_y,
            )
            column += 3
            if show_extra:
                self.extra_label.grid(row=0, column=column, padx=(0, pad_x), pady=pad_y)

    def _arrow(self, kind: str) -> str:
        if not self.settings.overlay_show_arrows:
            return ""
        return "↓" if kind == "down" else "↑"

    def _label_prefix(self, kind: str) -> str:
        arrow = self._arrow(kind)
        if not self.settings.overlay_show_labels:
            return arrow
        word = "Down" if kind == "down" else "Up  "
        if arrow:
            return f"{arrow} {word}"
        return word.ljust(4)

    def update_sample(
        self,
        sample: SpeedSample,
        settings: Settings,
        session_down: int,
        session_up: int,
        today_down: int = 0,
        today_up: int = 0,
    ) -> None:
        self.settings = settings
        down_number, down_unit = format_overlay_rate(sample.download, settings)
        up_number, up_unit = format_overlay_rate(sample.upload, settings)
        self.down_arrow.configure(text=self._label_prefix("down"))
        self.up_arrow.configure(text=self._label_prefix("up"))
        self.down_value.configure(text=down_number)
        self.up_value.configure(text=up_number)
        self.down_unit.configure(text=down_unit)
        self.up_unit.configure(text=up_unit)
        if settings.overlay_show_adapter:
            ip = f"  {sample.ip_address}" if sample.ip_address else ""
            self.adapter_label.configure(text=f"{sample.adapter}{ip}")
        extras = []
        if settings.overlay_show_utilization and sample.link_mbps:
            extras.append(f"{min(sample.down_util, 999):.0f}% / {min(sample.up_util, 999):.0f}%")
        if settings.overlay_show_ping:
            extras.append("--" if sample.ping_ms is None else f"{sample.ping_ms:.0f} ms")
        if settings.overlay_show_totals:
            extras.append(f"Session {format_bytes(session_down, settings.binary_units)} / {format_bytes(session_up, settings.binary_units)}")
        if settings.overlay_show_usage:
            extras.append(f"Today {format_bytes(today_down + today_up, settings.binary_units)}")
        self.extra_label.configure(text="   |   ".join(extras))
        self.update_idletasks()
        self.reposition()

    def set_fullscreen_hidden(self, hidden: bool) -> None:
        self._hidden_for_fullscreen = hidden
        if hidden or not self.settings.show_overlay:
            self.withdraw()
        else:
            self.deiconify()
            self._apply_native()
            self.reposition()

    def _content_size(self) -> tuple[int, int]:
        self.container.update_idletasks()
        width = max(self.container.winfo_reqwidth(), 72)
        height = max(self.container.winfo_reqheight(), 20)
        return width, height

    def reposition(self) -> None:
        if not self.settings.show_overlay:
            return
        self.update_idletasks()
        width, content_h = self._content_size()
        taskbar = get_taskbar()
        if taskbar is None:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            self.geometry(f"{width}x{content_h}+{screen_w - width - 220}+{screen_h - content_h - 12}")
            return

        if taskbar.orientation in {"bottom", "top"}:
            height = content_h
            if self.settings.overlay_dock == "taskbar-left":
                x = 12
            elif self.settings.overlay_dock == "taskbar-center":
                x = max(8, (taskbar.width - width) // 2)
            elif self.settings.overlay_dock == "taskbar-right":
                x = max(8, taskbar.width - width - 12)
            elif self.settings.overlay_dock == "custom":
                x = self.settings.overlay_x - taskbar.left
            else:
                x = taskbar.notify_left - taskbar.left - width - 16
            x = max(8, min(x, taskbar.width - width - 8))
            screen_x = taskbar.left + int(x)
            screen_y = taskbar.top + max(0, (taskbar.height - content_h) // 2)
        else:
            width = min(width, taskbar.width)
            height = min(content_h, taskbar.width)
            x = max(0, (taskbar.width - width) // 2)
            if self.settings.overlay_dock == "taskbar-left":
                y = 12
            elif self.settings.overlay_dock == "taskbar-center":
                y = max(8, (taskbar.height - height) // 2)
            elif self.settings.overlay_dock == "custom":
                y = self.settings.overlay_y - taskbar.top
            else:
                y = max(8, taskbar.height - height - 12)
            y = max(0, min(y, taskbar.height - height))
            screen_x = taskbar.left + int(x)
            screen_y = taskbar.top + int(y)

        self.geometry(f"{int(width)}x{int(height)}+{int(screen_x)}+{int(screen_y)}")
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass

    def _can_drag(self) -> bool:
        return self.settings.overlay_draggable and not self.settings.overlay_lock_position and not self.settings.overlay_click_through

    def _start_drag(self, event) -> None:
        if not self._can_drag():
            return
        self._drag_offset = (event.x_root - self.winfo_rootx(), event.y_root - self.winfo_rooty())

    def _on_drag(self, event) -> None:
        if not self._can_drag():
            return
        taskbar = get_taskbar()
        width, _ = self._content_size()
        if taskbar is None:
            return
        screen_x = event.x_root - self._drag_offset[0]
        x = screen_x - taskbar.left
        x = max(8, min(x, taskbar.width - width - 8))
        self.settings.overlay_dock = "custom"
        self.settings.overlay_x = taskbar.left + int(x)
        self.settings.overlay_y = taskbar.top
        y = taskbar.top + max(0, (taskbar.height - self._content_size()[1]) // 2)
        self.geometry(f"{int(width)}x{int(self._content_size()[1])}+{taskbar.left + int(x)}+{int(y)}")
        self.settings.overlay_y = taskbar.top

    def _end_drag(self, _event) -> None:
        if self.settings.overlay_dock == "custom":
            self.settings.save()

    def _show_menu(self, event) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Details", command=self.on_open_details)
        menu.add_command(label="Usage", command=self.on_open_usage)
        menu.add_command(label="Settings", command=self.on_open_settings)
        menu.add_separator()
        menu.add_command(label="Quit", command=self.on_quit)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
