from __future__ import annotations

import tkinter as tk

from .formatting import format_bytes, format_rate
from .monitor import SpeedSample
from .settings import Settings
from .win32util import configure_overlay_window, get_taskbar, hwnd_from_widget, keep_topmost


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
        self.attributes("-topmost", True)
        self.resizable(False, False)
        try:
            self.attributes("-toolwindow", True)
        except tk.TclError:
            pass

        self.configure(bg=settings.color_background)
        self.container = tk.Frame(self, bg=settings.color_background, highlightthickness=0, bd=0)
        self.container.pack(fill="both", expand=True)

        self.adapter_label = tk.Label(self.container, text="", anchor="w", bd=0)
        self.down_label = tk.Label(self.container, text="↓ 0 KB/s", anchor="w", bd=0)
        self.up_label = tk.Label(self.container, text="↑ 0 KB/s", anchor="w", bd=0)
        self.extra_label = tk.Label(self.container, text="", anchor="w", bd=0)

        self._bind_interactions(self)
        self._bind_interactions(self.container)
        for label in (self.adapter_label, self.down_label, self.up_label, self.extra_label):
            self._bind_interactions(label)

        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.after(50, self._init_native)
        self.apply_settings(settings)
        self._place_initial()

    def _bind_interactions(self, widget) -> None:
        widget.bind("<ButtonPress-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._on_drag)
        widget.bind("<ButtonRelease-1>", self._end_drag)
        widget.bind("<Double-Button-1>", lambda _e: self.on_open_details())
        widget.bind("<Button-3>", self._show_menu)

    def _init_native(self) -> None:
        try:
            self._hwnd = hwnd_from_widget(self)
            configure_overlay_window(
                self._hwnd,
                click_through=self.settings.overlay_click_through,
                topmost=self.settings.overlay_always_on_top,
            )
        except Exception:
            self._hwnd = None

    def _font(self, size_delta: int = 0):
        size = max(8, self.settings.overlay_font_size + size_delta)
        weight = "bold" if self.settings.overlay_font_bold else "normal"
        return (self.settings.overlay_font_family, size, weight)

    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.show_overlay:
            self.withdraw()
            return
        if self._hidden_for_fullscreen:
            return
        self.deiconify()
        self.attributes("-alpha", max(0.35, min(1.0, settings.overlay_opacity)))
        self.attributes("-topmost", bool(settings.overlay_always_on_top))
        bg = settings.color_background
        self.configure(bg=bg)
        self.container.configure(bg=bg)
        self.down_label.configure(font=self._font(), fg=settings.color_download, bg=bg)
        self.up_label.configure(font=self._font(), fg=settings.color_upload, bg=bg)
        self.adapter_label.configure(font=self._font(-2), fg=settings.color_muted, bg=bg)
        self.extra_label.configure(font=self._font(-2), fg=settings.color_muted, bg=bg)
        self._layout_widgets()
        if self._hwnd:
            configure_overlay_window(
                self._hwnd,
                click_through=settings.overlay_click_through,
                topmost=settings.overlay_always_on_top,
            )
        if settings.overlay_dock != "custom":
            self.reposition()

    def _layout_widgets(self) -> None:
        for widget in self.container.winfo_children():
            widget.grid_forget()
            widget.pack_forget()
        pad_x = self.settings.overlay_padding_x
        pad_y = self.settings.overlay_padding_y
        gap = self.settings.overlay_gap
        show_adapter = self.settings.overlay_show_adapter
        show_extra = (
            self.settings.overlay_show_totals
            or self.settings.overlay_show_usage
            or self.settings.overlay_show_ping
            or self.settings.overlay_show_utilization
        )
        if self.settings.overlay_layout == "inline":
            column = 0
            if show_adapter:
                self.adapter_label.grid(row=0, column=column, padx=(pad_x, gap), pady=pad_y)
                column += 1
            self.down_label.grid(row=0, column=column, padx=(0, gap), pady=pad_y)
            column += 1
            self.up_label.grid(row=0, column=column, padx=(0, pad_x if not show_extra else gap), pady=pad_y)
            column += 1
            if show_extra:
                self.extra_label.grid(row=0, column=column, padx=(0, pad_x), pady=pad_y)
        else:
            row = 0
            if show_adapter:
                self.adapter_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=pad_x, pady=(pad_y, 0))
                row += 1
            self.down_label.grid(row=row, column=0, sticky="w", padx=pad_x, pady=(pad_y if row == 0 else 0, 0))
            row += 1
            self.up_label.grid(row=row, column=0, sticky="w", padx=pad_x, pady=(0, pad_y if not show_extra else 0))
            row += 1
            if show_extra:
                self.extra_label.grid(row=row, column=0, sticky="w", padx=pad_x, pady=(0, pad_y))

    def _arrow(self, kind: str) -> str:
        if not self.settings.overlay_show_arrows:
            return ""
        return "↓ " if kind == "down" else "↑ "

    def _label_prefix(self, kind: str) -> str:
        if not self.settings.overlay_show_labels:
            return self._arrow(kind)
        word = "Down " if kind == "down" else "Up "
        return f"{self._arrow(kind)}{word}"

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
        down = format_rate(sample.download, settings)
        up = format_rate(sample.upload, settings)
        if settings.overlay_layout == "compact":
            self.down_label.configure(text=f"{self._arrow('down')}{down}")
            self.up_label.configure(text=f"{self._arrow('up')}{up}")
        else:
            self.down_label.configure(text=f"{self._label_prefix('down')}{down}")
            self.up_label.configure(text=f"{self._label_prefix('up')}{up}")
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
        if settings.overlay_always_on_top and self._hwnd:
            keep_topmost(self._hwnd)
        self.update_idletasks()
        if settings.overlay_dock != "custom":
            self.reposition()

    def set_fullscreen_hidden(self, hidden: bool) -> None:
        self._hidden_for_fullscreen = hidden
        if hidden or not self.settings.show_overlay:
            self.withdraw()
        else:
            self.deiconify()
            self.reposition()

    def _place_initial(self) -> None:
        if self.settings.overlay_dock == "custom" and (self.settings.overlay_x or self.settings.overlay_y):
            self.geometry(f"+{self.settings.overlay_x}+{self.settings.overlay_y}")
        else:
            self.after(120, self.reposition)

    def reposition(self) -> None:
        if not self.settings.show_overlay:
            return
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), 80)
        height = max(self.winfo_reqheight(), 28)
        taskbar = get_taskbar()
        dock = self.settings.overlay_dock
        if dock == "custom":
            self.geometry(f"+{self.settings.overlay_x}+{self.settings.overlay_y}")
            return
        if taskbar is None:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            x = screen_w - width - 220
            y = screen_h - height - 12
            self.geometry(f"{width}x{height}+{x}+{y}")
            return

        if taskbar.orientation in {"bottom", "top"}:
            y = taskbar.top + max(0, (taskbar.height - height) // 2)
            if dock == "taskbar-left":
                x = taskbar.left + 12
            elif dock == "taskbar-center":
                x = taskbar.left + (taskbar.width - width) // 2
            elif dock == "taskbar-right":
                x = taskbar.right - width - 12
            else:
                x = taskbar.notify_left - width - 12
                if x < taskbar.left + 8:
                    x = taskbar.left + 8
        else:
            x = taskbar.left + max(0, (taskbar.width - width) // 2)
            if dock == "taskbar-left":
                y = taskbar.top + 12
            elif dock == "taskbar-center":
                y = taskbar.top + (taskbar.height - height) // 2
            else:
                y = taskbar.bottom - height - 12
        self.geometry(f"+{int(x)}+{int(y)}")

    def _can_drag(self) -> bool:
        return self.settings.overlay_draggable and not self.settings.overlay_lock_position and not self.settings.overlay_click_through

    def _start_drag(self, event) -> None:
        if not self._can_drag():
            return
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _on_drag(self, event) -> None:
        if not self._can_drag():
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.settings.overlay_dock = "custom"
        self.settings.overlay_x = int(x)
        self.settings.overlay_y = int(y)
        self.geometry(f"+{int(x)}+{int(y)}")

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
