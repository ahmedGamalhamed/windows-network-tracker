from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .formatting import format_bytes
from .settings import Settings
from .usage import DayUsage, UsageStore


PERIODS = ("Today", "7 days", "30 days", "This month", "All")


def _day_label(iso: str) -> str:
    try:
        value = date.fromisoformat(iso)
    except ValueError:
        return iso
    today = date.today()
    if value == today:
        return "Today"
    if value == today - timedelta(days=1):
        return "Yesterday"
    return value.strftime("%a, %b %d")


def _percent(current: int, previous: int) -> str:
    if previous <= 0:
        return "new"
    change = (current - previous) / previous * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.0f}%"


class UsageWindow(ctk.CTkToplevel):
    def __init__(self, master, store: UsageStore, settings: Settings) -> None:
        super().__init__(master)
        self.store = store
        self.settings = settings
        self.period = tk.StringVar(value="30 days")
        self._user_opened = False
        self._table_rows: list[ctk.CTkFrame] = []
        self._last_table = 0.0

        self.title("Usage history")
        self.geometry("720x640")
        self.minsize(620, 520)
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        header = ctk.CTkLabel(self, text="Daily usage", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(anchor="w", padx=18, pady=(16, 2))
        self.subtitle = ctk.CTkLabel(self, text="Download and upload totals kept each day.")
        self.subtitle.pack(anchor="w", padx=18, pady=(0, 8))

        period_row = ctk.CTkFrame(self, fg_color="transparent")
        period_row.pack(fill="x", padx=18, pady=(0, 8))
        self.period_buttons = ctk.CTkSegmentedButton(
            period_row,
            values=list(PERIODS),
            variable=self.period,
            command=lambda _v: self.refresh(rebuild=True),
        )
        self.period_buttons.pack(side="left")
        self.period_buttons.set("30 days")

        stats = ctk.CTkFrame(self)
        stats.pack(fill="x", padx=18, pady=6)
        self.down_stat = self._stat_card(stats, "Download", 0)
        self.up_stat = self._stat_card(stats, "Upload", 1)
        self.total_stat = self._stat_card(stats, "Total", 2)
        stats.grid_columnconfigure((0, 1, 2), weight=1)

        self.compare = ctk.CTkLabel(self, text="", anchor="w")
        self.compare.pack(fill="x", padx=18, pady=(4, 2))
        self.quota_label = ctk.CTkLabel(self, text="", anchor="w")
        self.quota_label.pack(fill="x", padx=18)
        self.quota_bar = ctk.CTkProgressBar(self)
        self.quota_bar.pack(fill="x", padx=18, pady=(0, 8))
        self.quota_bar.set(0)

        self.canvas = tk.Canvas(self, height=150, highlightthickness=0, bd=0)
        self.canvas.pack(fill="x", padx=18, pady=6)

        table_header = ctk.CTkFrame(self, fg_color="transparent")
        table_header.pack(fill="x", padx=18)
        for text in ("Date", "Download", "Upload", "Total"):
            ctk.CTkLabel(table_header, text=text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
                side="left", expand=True, fill="x"
            )
        self.table = ctk.CTkScrollableFrame(self, height=180)
        self.table.pack(fill="both", expand=True, padx=14, pady=(4, 8))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=18, pady=(0, 14))
        ctk.CTkButton(buttons, text="Export CSV", width=120, command=self._export).pack(side="left")
        ctk.CTkButton(buttons, text="Reset today", width=120, fg_color="gray30", command=self._reset_today).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Clear history", width=120, fg_color="gray30", command=self._clear).pack(side="left")
        ctk.CTkButton(buttons, text="Close", width=100, command=self.withdraw).pack(side="right")

        self.withdraw()
        self.after(400, lambda: None if self._user_opened else self.withdraw())

    def _stat_card(self, parent, title: str, column: int) -> dict[str, ctk.CTkLabel]:
        card = ctk.CTkFrame(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=6, pady=8)
        caption = ctk.CTkLabel(card, text=title)
        value = ctk.CTkLabel(card, text="0 B", font=ctk.CTkFont(size=22, weight="bold"))
        caption.pack(anchor="w", padx=12, pady=(10, 0))
        value.pack(anchor="w", padx=12, pady=(0, 10))
        return {"caption": caption, "value": value}

    def show(self) -> None:
        self._user_opened = True
        self.deiconify()
        self.lift()
        self.focus_force()
        self.refresh(rebuild=True)

    def apply_theme(self, settings: Settings) -> None:
        self.settings = settings
        self.canvas.configure(bg=settings.color_background)
        self.down_stat["value"].configure(text_color=settings.color_download)
        self.up_stat["value"].configure(text_color=settings.color_upload)
        self.total_stat["value"].configure(text_color=settings.color_text)

    def _period_rows(self) -> list[DayUsage]:
        choice = self.period.get()
        if choice == "Today":
            return [self.store.today()]
        if choice == "7 days":
            return self.store.last_n_days(7)
        if choice == "This month":
            return self.store.month_days()
        if choice == "All":
            rows = self.store.all_days()
            return rows or [self.store.today()]
        return self.store.last_n_days(30)

    def refresh(self, rebuild: bool = False) -> None:
        if not self.winfo_exists():
            return
        if not self.winfo_viewable() and not rebuild:
            return
        binary = self.settings.binary_units
        rows = self._period_rows()
        summary = self.store.summarize(rows)
        today = self.store.today()
        self.down_stat["value"].configure(text=format_bytes(summary.down, binary))
        self.up_stat["value"].configure(text=format_bytes(summary.up, binary))
        self.total_stat["value"].configure(text=format_bytes(summary.total, binary))

        yesterday = self.store.get((date.today() - timedelta(days=1)).isoformat())
        days_with_data = max(1, len([row for row in rows if row.total]))
        average = summary.total / days_with_data
        self.compare.configure(
            text=(
                f"Today {format_bytes(today.total, binary)}"
                f"  ·  Yesterday {format_bytes(yesterday.total, binary)} ({_percent(today.total, yesterday.total)})"
                f"  ·  Average {format_bytes(int(average), binary)} / day"
            )
        )
        self._update_quota(today, binary)
        self._draw_chart(rows)
        now = datetime.now().timestamp()
        if rebuild or not self._table_rows or now - self._last_table > 5:
            self._rebuild_table(rows, binary)
            self._last_table = now

    def _update_quota(self, today: DayUsage, binary: bool) -> None:
        cap_gb = max(0.0, float(self.settings.usage_daily_cap_gb or 0))
        if cap_gb <= 0:
            self.quota_label.configure(text="No daily cap set. Add one in Settings → Usage.")
            self.quota_bar.set(0)
            return
        cap_bytes = int(cap_gb * (1024 ** 3 if binary else 1000 ** 3))
        used = self.store.cap_value(today, self.settings.usage_cap_metric)
        ratio = min(1.0, used / cap_bytes) if cap_bytes else 0
        self.quota_bar.set(ratio)
        metric = self.settings.usage_cap_metric
        self.quota_label.configure(
            text=f"Daily {metric} cap: {format_bytes(used, binary)} of {format_bytes(cap_bytes, binary)} ({ratio:.0%})"
        )

    def _draw_chart(self, rows: list[DayUsage]) -> None:
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 200)
        height = max(canvas.winfo_height(), 120)
        canvas.configure(bg=self.settings.color_background)
        chart_rows = rows[-30:]
        if not any(row.total for row in chart_rows):
            canvas.create_text(
                width / 2,
                height / 2,
                text="Usage will appear here as traffic is recorded.",
                fill=self.settings.color_muted,
            )
            return
        peak = max(row.total for row in chart_rows) or 1
        pad_l, pad_r, pad_t, pad_b = 8, 8, 10, 22
        usable_w = width - pad_l - pad_r
        usable_h = height - pad_t - pad_b
        bar_space = usable_w / max(1, len(chart_rows))
        bar_w = max(4, bar_space * 0.62)
        for index, row in enumerate(chart_rows):
            x = pad_l + bar_space * index + (bar_space - bar_w) / 2
            down_h = usable_h * (row.down / peak)
            up_h = usable_h * (row.up / peak)
            y_base = pad_t + usable_h
            canvas.create_rectangle(x, y_base - down_h, x + bar_w, y_base, fill=self.settings.color_download, outline="")
            canvas.create_rectangle(
                x,
                y_base - down_h - up_h,
                x + bar_w,
                y_base - down_h,
                fill=self.settings.color_upload,
                outline="",
            )
            if len(chart_rows) <= 14 or index in (0, len(chart_rows) - 1) or row.day == date.today().isoformat():
                label = datetime.fromisoformat(row.day).strftime("%m/%d")
                canvas.create_text(x + bar_w / 2, height - 8, text=label, fill=self.settings.color_muted, font=("Segoe UI", 8))

    def _rebuild_table(self, rows: list[DayUsage], binary: bool) -> None:
        for child in self.table.winfo_children():
            child.destroy()
        self._table_rows = []
        display = list(reversed([row for row in rows if row.total or row.day == date.today().isoformat()]))
        if not display:
            empty = ctk.CTkLabel(self.table, text="No usage recorded yet.")
            empty.pack(anchor="w", padx=8, pady=8)
            return
        for row in display:
            line = ctk.CTkFrame(self.table, fg_color="transparent")
            line.pack(fill="x", pady=2)
            values = (
                _day_label(row.day),
                format_bytes(row.down, binary),
                format_bytes(row.up, binary),
                format_bytes(row.total, binary),
            )
            for text in values:
                ctk.CTkLabel(line, text=text, anchor="w").pack(side="left", expand=True, fill="x")
            self._table_rows.append(line)

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export usage",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="netspeed-usage.csv",
        )
        if not path:
            return
        self.store.export_csv(path)
        messagebox.showinfo("Usage exported", f"Saved to:\n{path}", parent=self)

    def _reset_today(self) -> None:
        if not messagebox.askyesno("Reset today", "Clear today's download and upload totals?", parent=self):
            return
        self.store.reset_today()
        self.settings.daily_down_bytes = 0
        self.settings.daily_up_bytes = 0
        self.settings.save()
        self.refresh(rebuild=True)

    def _clear(self) -> None:
        if not messagebox.askyesno("Clear history", "Delete all stored daily usage history?", parent=self):
            return
        self.store.clear_all()
        self.refresh(rebuild=True)
